# -*- coding: utf-8 -*-
"""The texts of the individual findings, kept apart from the code that finds them.

Each check composes its own sentence while it analyses: the scientific
module concatenates Italian and observed values into an ``issue`` column, and
that sentence is the only place in which certain information exists — how many
occurrences, which position, which relation is reached by going up. Three
defects follow from this.

The first is that the information is not readable by a program: to know in how
many occurrences out of how many a relation is rare, one has to parse an
Italian sentence. The second is that the language is decided at the time of the
analysis: whoever runs in Italian and then switches to English finds an English
interface with Italian sentences inside, and exports them that way. The third
is that the scientific backend contains prose, which is exactly the place where
it must not be.

Here the finding carries two structured fields — ``issue_key``, which says
which sentence, and ``issue_params``, which carries the typed values — and the
sentence is composed at the moment it is shown, in the requested language. The
``issue`` column remains, with the same observable content, but it is a
**cache**: it is derived from key and parameters, and is never the source.

Three rules hold for all the texts of this module.

1. **No proposed value.** The proposed correction lives in
   ``suggested_postag``, ``suggested_lemma``, ``suggested_relation``,
   ``suggested_form``, ``suggested_head`` and is read at the “Correct” step,
   where one decides whether to apply it. Step 3 says what does not add up,
   not what to write in its place: if it already contained the answer, the
   separation between diagnosis and correction would be fictitious.

2. **No duplicated data.** The parameters contain only what cannot be derived
   from the columns of the finding. The form, the lemma, the tag, the relation,
   the head are already there, and with them everything that can be derived by
   projection: the character in slot *n* is character *n* of the tag, and the
   length of the tag is its length. What goes in the parameters is what is a
   conclusion of the check: which slot to look at, the relation reached by going
   up the tree, the value of the head, a count on the corpus, the base relation
   on which a statistic is computed.

3. **No words in the parameters.** The parameters carry codes and numbers —
   ``{"slot": 6, "valore": "c"}`` — and the Italian or English name of that
   code is derived here, with the bilingual dictionaries of the scheme. A
   parameter that contained “genere” (gender) would bring Italian into the
   backend.
"""
from __future__ import annotations

import json
import unicodedata
from string import Formatter
from typing import Callable

import numpy as np
import pandas as pd

from .agdt_schema import (
    POSITION_NAMES,
    describe_postag,
    describe_value,
)
from .fastmap import map_unique

# ---------------------------------------------------------------------------
# Names derived from a code
# ---------------------------------------------------------------------------

#: The ordinals of the nine positions, in the two languages.
_ORDINALI: dict[str, tuple[str, ...]] = {
    "it": ("prima", "seconda", "terza", "quarta", "quinta",
           "sesta", "settima", "ottava", "nona"),
    "en": ("first", "second", "third", "fourth", "fifth",
           "sixth", "seventh", "eighth", "ninth"),
}


def _lingua(lingua: object) -> str:
    return "en" if str(lingua) == "en" else "it"


def nome_posizione(slot: int, lingua: str = "it") -> str:
    """``'Diatesi'`` / ``'Voice'`` — the name of the position."""
    coppia = POSITION_NAMES.get(int(slot), ("?", "?"))
    return coppia[0] if _lingua(lingua) == "it" else coppia[1]


def posizione(slot: int, lingua: str = "it") -> str:
    """``'sesta posizione (Diatesi)'`` / ``'sixth position (Voice)'``."""
    slot = int(slot)
    ordinale = _ORDINALI[_lingua(lingua)][slot]
    nome = nome_posizione(slot, lingua)
    if _lingua(lingua) == "it":
        return f"{ordinale} posizione ({nome})"
    return f"{ordinale} position ({nome})"


def la_posizione(slot: int, lingua: str = "it") -> str:
    """The same, with the article: ``'L'ottava posizione (Caso)'``."""
    testo = posizione(slot, lingua)
    if _lingua(lingua) == "en":
        return "The " + testo
    return ("L'" if testo.startswith("o") else "La ") + testo


def valore(slot: int, carattere: str, lingua: str = "it") -> str:
    """``'«e» (medio-passivo)'`` — the character e and what it means."""
    return f"«{carattere}» ({describe_value(int(slot), str(carattere), _lingua(lingua))})"


def etichetta(tag: object, lingua: str = "it") -> str:
    """``'«v-sppamn-» (verbo · singolare · …)'`` — the tag and its reading."""
    return f"«{tag}» ({describe_postag(tag, _lingua(lingua))})"


def nome_unicode(codepoint: object) -> str:
    """The Unicode name of a code point written ``U+0313``.

    The name is English in both languages because it is an identifier: the standard
    defines it once, and translating it would mean inventing a second one that no table
    reports.
    """
    testo = str(codepoint or "")
    if not testo.upper().startswith("U+"):
        return testo
    try:
        carattere = chr(int(testo[2:], 16))
    except (ValueError, TypeError):
        return testo
    try:
        return unicodedata.name(carattere)
    except ValueError:
        return testo


def carattere_di(codepoint: object) -> str:
    """The character written by a code point ``U+0313``, or the code point itself."""
    testo = str(codepoint or "")
    if not testo.upper().startswith("U+"):
        return testo
    try:
        return chr(int(testo[2:], 16))
    except (ValueError, TypeError):
        return testo


def numero(valore_numerico: object, lingua: str = "it") -> str:
    """An integer inside a sentence.

    Without a thousands separator, and the choice has to be explained because elsewhere
    in the interface the separator is there. Here the number sits inside the sentence of
    a finding, which is composed as plain text: putting a full stop or a comma in it
    would change the text of every finding that counts something, for a typographical
    reason.
    """
    try:
        return str(int(valore_numerico))
    except (TypeError, ValueError):
        return str(valore_numerico)


def percentuale(quota: object, lingua: str = "it", cifre: int = 2) -> str:
    """``'0,63'`` in Italian, ``'0.63'`` in English — without the sign.

    The decimal digits are those that the number really has, with at least one: ``1,0``
    stays ``1,0`` and does not become ``1``. Removing it would be cleaner and would say
    something different — a percentage rounded to one decimal is not an integer — and
    would change the text of every finding that comes out round.
    """
    try:
        testo = str(round(float(quota), cifre))
    except (TypeError, ValueError):
        return str(quota)
    return testo.replace(".", ",") if _lingua(lingua) == "it" else testo


def quanti(numero_grezzo: object, singolare: str, plurale: str) -> str:
    """``'1 congiunto'``, ``'2 congiunti'``: the numeral and the noun that agrees with it.

    A numeral followed by a plural noun — “regge 1 congiunti” — is an error of grammar,
    not of content, and in this program it appeared two hundred times.
    """
    try:
        conto = int(numero_grezzo)
    except (TypeError, ValueError):
        return f"{numero_grezzo} {plurale}"
    return f"{conto} {singolare if abs(conto) == 1 else plurale}"


def elenco(voci: "list[str]", lingua: str = "it") -> str:
    """``'a, b e c'`` / ``'a, b and c'``."""
    voci = [str(v) for v in voci if str(v)]
    if not voci:
        return ""
    if len(voci) == 1:
        return voci[0]
    ultima = voci[-1]
    congiunzione = " e " if _lingua(lingua) == "it" else " and "
    return ", ".join(voci[:-1]) + congiunzione + ultima


# ---------------------------------------------------------------------------
# The parameters
# ---------------------------------------------------------------------------

#: The columns that the finding already carries: a text that needs them reads them from
#: the row and does not repeat them in the parameters.
COLONNE_FINDING: frozenset[str] = frozenset({
    "form", "lemma", "postag", "relation", "head",
    "source_file", "document_id", "sentence_id", "token_id",
})


def _semplifica(valore_grezzo: object) -> object:
    """From numpy and pandas to types that JSON knows."""
    if valore_grezzo is None or valore_grezzo is pd.NA:
        return None
    if isinstance(valore_grezzo, (np.integer,)):
        return int(valore_grezzo)
    if isinstance(valore_grezzo, (np.floating,)):
        return float(valore_grezzo)
    if isinstance(valore_grezzo, (np.bool_,)):
        return bool(valore_grezzo)
    if isinstance(valore_grezzo, (list, tuple)):
        return [_semplifica(v) for v in valore_grezzo]
    if isinstance(valore_grezzo, dict):
        return {str(k): _semplifica(v) for k, v in valore_grezzo.items()}
    try:
        if pd.isna(valore_grezzo):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(valore_grezzo, (str, int, float, bool)):
        return valore_grezzo
    return str(valore_grezzo)


def serializza(valori: "dict | None") -> str:
    """The parameters as JSON: sorted keys, UTF-8, Greek not escaped.

    The order of the keys is fixed because two runs of the same analysis must produce
    the same file, byte for byte; Greek stays Greek because nobody can read a CSV that
    writes ``\\u1f00``.
    """
    if not valori:
        return ""
    pulito = {str(k): _semplifica(v) for k, v in valori.items()}
    return json.dumps(pulito, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _uno(valore_grezzo: object) -> str:
    """A single value, in JSON: it serves to group the composite columns."""
    return json.dumps(_semplifica(valore_grezzo), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def parametri(**valori: object) -> "str | pd.Series":
    """The parameters of a finding, as a string or as a column.

    Each argument is a constant value or a column. If there is at least one column, the
    result is a column of JSON aligned with it, computed once per distinct combination
    and not once per row: in a corpus the combinations are a few dozen even when the
    rows are a hundred thousand.
    """
    colonne = {nome: v for nome, v in valori.items() if isinstance(v, pd.Series)}
    if not colonne:
        return serializza(valori)
    indice = next(iter(colonne.values())).index
    grezze = {nome: (v if isinstance(v, pd.Series)
                     else pd.Series([v] * len(indice), index=indice))
              for nome, v in valori.items()}
    # A column can be grouped if its values can be compared. A composite value — a list
    # of pairs, for example — cannot, and so it is first written as JSON and the
    # grouping is done on that. The longer route is needed only for the columns that
    # require it, and they are few rows.
    chiavi = {}
    composte = set()
    for nome, colonna in grezze.items():
        campione = next((v for v in colonna if v is not None), None)
        try:
            hash(campione)
        except TypeError:
            composte.add(nome)
            chiavi[nome] = pd.Series(
                [_uno(v) for v in colonna], index=indice, dtype="string")
        else:
            chiavi[nome] = colonna
    frame = pd.DataFrame(chiavi, index=indice)
    codici, unici = pd.MultiIndex.from_frame(frame).factorize()
    nomi = list(frame.columns)
    testi = np.array(
        [serializza({nome: (json.loads(cella) if nome in composte else cella)
                     for nome, cella in zip(nomi, riga)})
         for riga in unici], dtype=object)
    return pd.Series(testi[codici], index=indice, dtype="string")


# ---------------------------------------------------------------------------
# The texts
# ---------------------------------------------------------------------------

#: ``issue_key -> (Italian, English)``. The key is the identifier of the rule, except for
#: the few rules that say different things in different cases: those carry an explicit
#: suffix after the full stop.
TESTI: dict[str, tuple[str, str]] = {}

#: The derivations: what the text shows but the parameters do not carry, because it is
#: derived from a code or from a count.
_DERIVAZIONI: dict[str, Callable[[dict, str], dict]] = {}

#: Fields of the finding that a derivation reads without the text naming them directly.
_CAMPI_EXTRA: dict[str, tuple[str, ...]] = {}


def _derivazione(*chiavi: str, extra: tuple[str, ...] = ()):
    def decoratore(funzione):
        for chiave in chiavi:
            _DERIVAZIONI[chiave] = funzione
            if extra:
                _CAMPI_EXTRA[chiave] = extra
        return funzione
    return decoratore


_CAMPI_RIGA: dict[str, tuple[str, ...]] = {}


def campi_riga(issue_key: str) -> tuple[str, ...]:
    """The columns of the finding that this text reads."""
    if issue_key in _CAMPI_RIGA:
        return _CAMPI_RIGA[issue_key]
    modelli = TESTI.get(issue_key)
    trovati: set[str] = set(_CAMPI_EXTRA.get(issue_key, ()))
    if modelli is not None:
        for modello in modelli:
            for _, campo, _, _ in Formatter().parse(modello):
                if campo and campo in COLONNE_FINDING:
                    trovati.add(campo)
    risultato = tuple(sorted(trovati))
    _CAMPI_RIGA[issue_key] = risultato
    return risultato


def _testo_riga(riga: object, campo: str) -> str:
    if riga is None:
        return ""
    try:
        valore_grezzo = riga[campo]
    except (KeyError, IndexError, TypeError):
        valore_grezzo = getattr(riga, campo, None)
    if valore_grezzo is None:
        return ""
    try:
        if pd.isna(valore_grezzo):
            return ""
    except (TypeError, ValueError):
        pass
    testo = str(valore_grezzo).strip()
    return "" if testo.lower() in ("nan", "<na>", "none") else testo


def rendi(issue_key: object, issue_params: object = None,
          lingua: str = "it", riga: object = None) -> str:
    """The sentence of a finding, in the requested language.

    A pure function: same key, same parameters, same row, same sentence. A key that the
    module does not know produces neither an error nor an invented sentence: it produces
    nothing, and the finding remains readable from its columns.
    """
    chiave = str(issue_key or "")
    modelli = TESTI.get(chiave)
    if modelli is None:
        return ""
    modello = modelli[0] if _lingua(lingua) == "it" else modelli[1]
    valori: dict[str, object] = {
        campo: _testo_riga(riga, campo) for campo in campi_riga(chiave)}
    if isinstance(issue_params, str) and issue_params.strip():
        try:
            valori.update(json.loads(issue_params))
        except (ValueError, TypeError):
            pass
    elif isinstance(issue_params, dict):
        valori.update(issue_params)
    derivazione = _DERIVAZIONI.get(chiave)
    if derivazione is not None:
        valori.update(derivazione(valori, _lingua(lingua)))
    try:
        return modello.format(**valori)
    except (KeyError, IndexError, ValueError):
        return ""


_SEPARATORE = "\x1f"


def rendi_serie(frame: pd.DataFrame, lingua: str = "it") -> pd.Series:
    """The ``issue`` column of a set of findings, in the requested language.

    Composed once per distinct combination of key, parameters and fields read:
    over a hundred thousand findings the combinations are a few thousand.
    """
    if frame is None or len(frame) == 0:
        return pd.Series(dtype="string", index=getattr(frame, "index", None))
    if "issue_key" not in frame.columns:
        return pd.Series([""] * len(frame), index=frame.index, dtype="string")
    chiavi = frame["issue_key"].astype("string").fillna("")
    if "issue_params" in frame.columns:
        params = frame["issue_params"].astype("string").fillna("")
    else:
        params = pd.Series([""] * len(frame), index=frame.index, dtype="string")

    campi: list[str] = sorted({
        campo
        for chiave in chiavi.dropna().unique()
        for campo in campi_riga(str(chiave))
        if campo in frame.columns})
    pezzi = [params] + [frame[campo].astype("string").fillna("") for campo in campi]
    codice = chiavi.str.cat(pezzi, sep=_SEPARATORE)

    def _componi(testo: object) -> str:
        parti = str(testo).split(_SEPARATORE)
        riga = dict(zip(campi, parti[2:]))
        return rendi(parti[0], parti[1], lingua, riga)

    return map_unique(codice, _componi).astype("string")


def issue_keys_note() -> tuple[str, ...]:
    """The known keys, in order: it serves the coverage checks."""
    return tuple(sorted(TESTI))


# ===========================================================================
# Family: morphological label
# ===========================================================================

TESTI.update({

    "missing-postag": (
        "Il campo dell'etichetta morfologica è vuoto: il token non dice né "
        "che parte del discorso è né che forma ha. Non viene proposta nessuna "
        "correzione: l'etichetta va scritta a mano leggendo la frase.",
        "The morphological tag is empty: the token says neither what part of "
        "speech it is nor what form it has. No correction is proposed: the tag "
        "has to be written by hand, from the sentence."),

    "invalid-length-padding.piu-di-nove": (
        "L'etichetta «{postag}» è lunga {quanti_caratteri} invece dei nove "
        "previsti dallo schema AGDT, e i caratteri in più sono tutti trattini, "
        "cioè posizioni vuote: nessun valore dello schema è coinvolto, solo la "
        "lunghezza della stringa.",
        "The tag «{postag}» is {quanti_caratteri} long instead of the nine the "
        "AGDT scheme prescribes, and the surplus characters are all hyphens, "
        "that is, empty slots: no value of the scheme is involved, only the "
        "length of the string."),

    "invalid-length-padding.otto": (
        "L'etichetta «{postag}» è lunga otto caratteri invece dei nove "
        "previsti dallo schema AGDT, e dopo la parte del discorso contiene "
        "solo trattini: manca l'ultimo trattino.",
        "The tag «{postag}» is eight characters long instead of the nine the "
        "AGDT scheme prescribes, and after the part of speech it holds nothing "
        "but hyphens: the last hyphen is missing."),

    "invalid-length-broken": (
        "L'etichetta «{postag}» è lunga {quanti_caratteri} invece dei nove "
        "previsti dallo schema AGDT, e i caratteri che mancano (o quelli in "
        "più) non sono trattini. Non viene proposta nessuna correzione: quali "
        "posizioni manchino, e con che valore, si stabilisce solo rileggendo "
        "la parola.",
        "The tag «{postag}» is {quanti_caratteri} long instead of the nine the "
        "AGDT scheme prescribes, and the characters that are missing (or the "
        "ones in excess) are not hyphens. No correction is proposed: which "
        "slots are missing, and with what value, can only be settled by "
        "reading the word again."),

    "invalid-character": (
        "{la_posizione} contiene «{valore}», che non è uno dei valori ammessi "
        "in quella posizione. Non viene proposta nessuna correzione: quale sia "
        "il valore giusto dipende dalla parola, non dall'etichetta.",
        "{la_posizione} holds «{valore}», which is not one of the values "
        "allowed in that slot. No correction is proposed: which value is the "
        "right one depends on the word, not on the tag."),

    "case-letter-l": (
        "L'ottava posizione (Caso) contiene «l», il locativo: è un valore "
        "previsto dallo schema, ma il resto del corpus non lo usa quasi mai. "
        "Nessuna correzione proposta: ricondurlo al dativo cancellerebbe una "
        "distinzione che lo schema ammette.",
        "The eighth position (Case) holds «l», the locative: it is a value the "
        "scheme provides for, but the rest of the corpus hardly ever uses it. "
        "No correction is proposed: rewriting it as a dative would erase a "
        "distinction the scheme allows."),

    "grade-p": (
        "La nona posizione (Grado) contiene «p» per il grado positivo, ma lo "
        "schema ammette qui soltanto «c» (comparativo) e «s» (superlativo): il "
        "positivo si scrive con il trattino.",
        "The ninth position (Degree) holds «p» for the positive degree, but "
        "here the scheme allows only «c» (comparative) and «s» (superlative): "
        "the positive is written with the hyphen."),

    "pedalion-b-pos": (
        "La prima posizione contiene «b», che non appartiene all'inventario "
        "AGDT. Non è una svista: il README dei Pedalion Trees la dichiara: "
        "«For experimental reasons, some trees exhibit the part-of-speech "
        "designation 'b', equalling in most cases 'd' or 'c'». Le occorrenze "
        "cadono in prevalenza su coordinanti. Non viene proposta nessuna "
        "correzione, perché la dichiarazione dice «in most cases 'd' or 'c'»: "
        "il valore AGDT corrispondente non è uno solo e sceglierlo è un atto "
        "di analisi, non di formato.",
        "The first position holds «b», which does not belong to the AGDT "
        "inventory. It is not an oversight: the Pedalion Trees README declares "
        "it: «For experimental reasons, some trees exhibit the part-of-speech "
        "designation 'b', equalling in most cases 'd' or 'c'». The occurrences "
        "fall mostly on coordinators. No correction is proposed, because the "
        "declaration says «in most cases 'd' or 'c'»: the corresponding AGDT "
        "value is not a single one, and choosing it is an act of analysis, not "
        "of formatting."),

    "nonlexical-z-pos": (
        "La prima posizione contiene «z», che non appartiene all'inventario "
        "AGDT e che i corpora dell'area di Lovanio usano per i record che non "
        "sono parole del testo: i tratti guasti o illeggibili, scritti «G?», e "
        "i segnaposto dei nodi ellittici. Non viene proposta nessuna "
        "correzione: la domanda non è quale etichetta morfologica dare a "
        "questo record, ma se contarlo.",
        "The first position holds «z», which does not belong to the AGDT "
        "inventory and which the Leuven corpora use for records that are not "
        "words of the text: damaged or illegible stretches, written «G?», and "
        "the placeholders of elliptic nodes. No correction is proposed: the "
        "question is not which morphological tag this record should carry, but "
        "whether to count it."),

    "common-gender-c": (
        "La settima posizione (Genere) contiene «c» per il genere comune, "
        "valore che l'inventario AGDT 2.0 non elenca: lì il genere è soltanto "
        "maschile, femminile o neutro. Non è una svista, perché il valore "
        "ricorre dove il genere comune ha una ragione grammaticale, sui "
        "pronomi che genere non hanno e sui nomi epiceni; qui il lemma è "
        "«{parola}». Non viene proposta nessuna correzione: scegliere fra "
        "maschile e femminile è un atto di analisi, e cancellerebbe la "
        "distinzione che l'annotatore ha voluto segnare.",
        "The seventh position (Gender) holds «c» for the common gender, a "
        "value the AGDT 2.0 inventory does not list: there the gender is only "
        "masculine, feminine or neuter. It is not an oversight, because the "
        "value recurs where the common gender has a grammatical ground, on the "
        "pronouns that have no gender and on the epicene nouns; here the lemma "
        "is «{parola}». No correction is proposed: choosing between masculine "
        "and feminine is an act of analysis, and would erase the distinction "
        "the annotator meant to record."),

    "degree-underscore": (
        "La nona posizione (Grado) contiene un trattino basso «_» al posto del "
        "trattino «-». I due segni dicono la stessa cosa, cioè che qui non c'è "
        "niente, ma per un programma sono simboli diversi, e la stessa parola "
        "finisce contata due volte.",
        "The ninth position (Degree) holds a low line «_» where the hyphen «-» "
        "belongs. The two signs say the same thing, namely that there is "
        "nothing here, but to a program they are different symbols, and the "
        "same word ends up counted twice."),

    "underscore-person-number": (
        "Il trattino basso «_» compare al posto del trattino «-» {dove}: "
        "{caselle}. I due segni dicono la stessa cosa, cioè che "
        "questa categoria non si applica, ma per un programma sono simboli "
        "diversi, e la stessa parola finisce contata due volte. Dove il "
        "trattino basso serviva a dire «indeclinabile» invece che «non "
        "applicabile», la distinzione non è prevista dallo schema e non si può "
        "conservare.",
        "The low line «_» appears where the hyphen «-» belongs, {dove}: "
        "{caselle}. The two signs say the same thing, namely that this "
        "category does not apply, but to a program they are different symbols, "
        "and the same word ends up counted twice. Where the low line was meant "
        "to say «indeclinable» rather than «not applicable», the scheme does "
        "not provide for the distinction and it cannot be preserved."),

    "mediopassive-d": (
        "La sesta posizione (Diatesi) contiene «d», che l'inventario AGDT non "
        "ha: le diatesi sono attiva (a), passiva (p), media (m) e "
        "medio-passiva (e). Nelle occorrenze osservate il verbo è deponente "
        "(ἥδομαι, ἔρχομαι), e «d» potrebbe valere «deponente» piuttosto che "
        "«medio-passivo»: nessuna fonte del progetto lo dichiara. "
        "Nessuna correzione proposta, perché scrivere «e» sarebbe una "
        "decisione e non una riscrittura senza perdita.",
        "The sixth position (Voice) holds «d», which the AGDT inventory does "
        "not have: the voices are active (a), passive (p), middle (m) and "
        "mediopassive (e). In the occurrences observed the verb is deponent "
        "(ἥδομαι, ἔρχομαι), and «d» may stand for «deponent» rather than "
        "«mediopassive»: no source of the project declares it. No correction "
        "is proposed, because writing «e» would be a decision and not a "
        "lossless rewriting."),

    "leading-t": (
        "La prima posizione (Parte del discorso) contiene «t», valore che "
        "l'inventario morfologico AGDT 2.0 non prevede. La parte del discorso "
        "corretta va determinata in base alla forma e al contesto: le "
        "occorrenze già controllate a mano ricevono la loro proposta dalla "
        "tabella delle riparazioni verificate.",
        "The first position (Part of speech) holds «t», a value the AGDT 2.0 "
        "morphological inventory does not provide for. The right part of "
        "speech has to be determined from the form and the context: the "
        "occurrences already checked by hand take their proposal from the "
        "table of verified repairs."),

    "punctuation-leading-e": (
        "La prima posizione (Parte del discorso) contiene «e», che lo schema "
        "non prevede: è il refuso tipico di un segno di punteggiatura "
        "etichettato a mano.",
        "The first position (Part of speech) holds «e», which the scheme does "
        "not provide for: it is the typical slip of a punctuation mark tagged "
        "by hand."),

    "leading-x-lexical": (
        "La prima posizione (Parte del discorso) contiene «x» (nodo ellittico "
        "/ non assegnato), valore che lo schema riserva ai nodi ellittici, ma "
        "il record porta una parola presente nel testo: «{form}». La parte del "
        "discorso corretta va stabilita nel contesto.",
        "The first position (Part of speech) holds «x» (elliptic node / "
        "unassigned), a value the scheme reserves for elliptic nodes, but the "
        "record carries a word that is present in the text: «{form}». The "
        "right part of speech has to be settled in context."),

    "dein-participle": (
        "L'etichetta analizza δεῖν come participio, ma δεῖν è l'infinito "
        "presente: il participio è δέον. Nei verbi in -έω contrae solo ε+ε → "
        "ει, e quindi δέ-ειν dà δεῖν, mentre ε+ο non contrae e il participio "
        "neutro resta δέον.",
        "The tag analyses δεῖν as a participle, but δεῖν is the present "
        "infinitive: the participle is δέον. In -έω verbs only ε+ε contracts "
        "to ει, so δέ-ειν gives δεῖν, while ε+ο does not contract and the "
        "neuter participle stays δέον."),

    "dein-participle-disputed": (
        "L'etichetta analizza δεῖν come participio, dove δεῖν è l'infinito "
        "presente. {spiegazione} Il programma non propone nessuna correzione: "
        "qui la scelta è editoriale, non morfologica, e va verificata sul "
        "passo e sulla tradizione testuale.",
        "The tag analyses δεῖν as a participle, where δεῖν is the present "
        "infinitive. {spiegazione} The program proposes no correction: here "
        "the choice is editorial, not morphological, and has to be checked "
        "against the passage and the textual tradition."),

    "personal-pronoun-person": (
        "La seconda posizione (Persona) è vuota, ma «{forma}» è un pronome "
        "personale di {persona_parola} persona. Le linee guida AGDT 2.0 non "
        "prescrivono la persona per il pronome, quindi il trattino non "
        "infrange lo schema: è una variante rispetto al profilo più ricco che "
        "GCP adotta, e l'informazione può servire a chi voglia un'annotazione "
        "completa o confrontabile fra risorse. Nessuna correzione proposta, e "
        "la persona non viene dedotta.",
        "The second position (Person) is empty, but «{forma}» is a "
        "{persona_parola}-person personal pronoun. The AGDT 2.0 guidelines do "
        "not prescribe the person for the pronoun, so the hyphen does not "
        "break the scheme: it is a variant with respect to the richer profile "
        "GCP adopts, and the information may serve whoever wants an annotation "
        "that is complete or comparable across resources. No correction is "
        "proposed, and the person is not inferred."),

    "verbal-adjective-g": (
        "La quinta posizione (Modo) contiene «g», che l'inventario AGDT non "
        "prevede, e la forma è un aggettivo verbale in -τέος: qui «g» non è un "
        "refuso per il participio, è il modo in cui il corpus scrive il "
        "gerundivo. Riclassificarlo come aggettivo è la prassi maggioritaria, "
        "ma richiede revisione manuale perché il neutro dell'aggettivo verbale "
        "è sincretico fra nominativo e accusativo, e quale dei due sia lo "
        "decide la costruzione. Nessuna correzione applicata.",
        "The fifth position (Mood) holds «g», which the AGDT inventory does "
        "not provide for, and the form is a verbal adjective in -τέος: here "
        "«g» is not a slip for the participle, it is how the corpus writes the "
        "gerundive. Reclassifying it as an adjective is the majority practice, "
        "but it requires manual review, because the neuter of a verbal "
        "adjective is syncretic between nominative and accusative, and which "
        "of the two it is depends on the construction. No correction is "
        "applied."),

    "participle-mood-g": (
        "La quinta posizione, quella del modo, contiene «g», che l'inventario "
        "AGDT non prevede: i modi sono indicativo (i), congiuntivo (s), "
        "ottativo (o), infinito (n), imperativo (m) e participio (p). "
        "L'etichetta porta però un genere e un caso, e di modi che li ammettano "
        "ce n'è uno solo. Gli aggettivi verbali in -τέος, dove «g» vale "
        "gerundivo e non participio, sono trattati a parte. Il valore corretto "
        "dipende dall'analisi della forma e non viene proposto d'ufficio: le "
        "occorrenze già controllate a mano ricevono la loro proposta dalla "
        "tabella delle riparazioni verificate.",
        "The fifth position, the one for mood, holds «g», which the AGDT "
        "inventory does not provide for: the moods are indicative (i), "
        "subjunctive (s), optative (o), infinitive (n), imperative (m) and "
        "participle (p). The tag does however carry a gender and a case, and "
        "there is only one mood that admits them. Verbal adjectives in -τέος, "
        "where «g» means gerundive and not participle, are handled separately. "
        "The right value depends on the analysis of the form and is not "
        "proposed by default: the occurrences already checked by hand take "
        "their proposal from the table of verified repairs."),

    "slot-forbidden": (
        "L'etichetta dice che questa parola è un {classe}, e una parola così "
        "non può avere {tratti}. Nello schema AGDT questa combinazione non "
        "esiste: o è sbagliata la prima posizione, cioè la parola non è quello "
        "che l'etichetta dice, oppure lo è la posizione valorizzata. Non viene "
        "proposta nessuna correzione, perché quale delle due sia sbagliata lo "
        "dice la parola, non l'etichetta.",
        "The tag says that this word is a {classe}, and a word of that kind "
        "cannot have {tratti}. In the AGDT scheme this combination does not "
        "exist: either the first position is wrong, that is, the word is not "
        "what the tag says it is, or the filled slot is. No correction is "
        "proposed, because which of the two is wrong is told by the word, not "
        "by the tag."),

    "slot-missing.uno": (
        "L'etichetta dice che questa parola è un {classe}, e una parola così "
        "porta questo tratto, che qui è vuoto: {tratti}. Gli altri tratti ci "
        "sono, quindi la parola è stata analizzata e questa casella è rimasta "
        "indietro.",
        "The tag says that this word is a {classe}, and a word of that kind "
        "carries this feature, which here is empty: {tratti}. The other "
        "features are there, so the word has been analysed and this slot was "
        "left behind."),

    "slot-missing.molti": (
        "L'etichetta dice che questa parola è un {classe}, e una parola così "
        "porta questi tratti, che qui sono tutti vuoti: {tratti}. Gli altri "
        "tratti ci sono, quindi la parola è stata analizzata e questa casella "
        "è rimasta indietro.",
        "The tag says that this word is a {classe}, and a word of that kind "
        "carries these features, which here are all empty: {tratti}. The other "
        "features are there, so the word has been analysed and this slot was "
        "left behind."),

    "slot-missing-bare.uno": (
        "L'etichetta dice che questa parola è un {classe}, e una parola così "
        "porta questo tratto, che qui è vuoto: {tratti}. Attenzione: "
        "l'etichetta non ha nessun tratto valorizzato. Può essere una parola "
        "che non si declina, per esempio un nome proprio straniero, e allora è "
        "scritta bene; oppure una parola flessa rimasta senza analisi. Solo la "
        "parola lo dice.",
        "The tag says that this word is a {classe}, and a word of that kind "
        "carries this feature, which here is empty: {tratti}. Note: the tag "
        "has no feature filled at all. It may be a word that does not decline, "
        "a foreign proper name for instance, and then it is written correctly; "
        "or an inflected word left unanalysed. Only the word says which."),

    "slot-missing-bare.molti": (
        "L'etichetta dice che questa parola è un {classe}, e una parola così "
        "porta questi tratti, che qui sono tutti vuoti: {tratti}. Attenzione: "
        "l'etichetta non ha nessun tratto valorizzato. Può essere una parola "
        "che non si declina, per esempio un nome proprio straniero, e allora è "
        "scritta bene; oppure una parola flessa rimasta senza analisi. Solo la "
        "parola lo dice.",
        "The tag says that this word is a {classe}, and a word of that kind "
        "carries these features, which here are all empty: {tratti}. Note: the "
        "tag has no feature filled at all. It may be a word that does not "
        "decline, a foreign proper name for instance, and then it is written "
        "correctly; or an inflected word left unanalysed. Only the word says "
        "which."),

    "uninflected-lemma": (
        "Il lemma «{voce}» {conteggio}. Quasi sempre è una parola che in greco "
        "non si declina, come un nome proprio semitico, un mese egiziano o una "
        "lettera usata come sigla, e allora l'etichetta è giusta così. Se "
        "invece la parola si declina, la casella non è rimasta vuota per "
        "distrazione: manca in tutte le occorrenze, e va riempita in tutte.",
        "The lemma «{voce}» {conteggio}. Nearly always it is a word that does "
        "not decline in Greek, a Semitic proper name, an Egyptian month or a "
        "letter used as an abbreviation, and then the tag is right as it "
        "stands. If instead the word does decline, the slot was not left empty "
        "by inattention: it is missing in every occurrence, and has to be "
        "filled in every one."),
})


# ── The derivations of the family ──────────────────────────────────────────

@_derivazione("invalid-character", extra=("postag",))
def _der_carattere(valori: dict, lingua: str) -> dict:
    # The character is not in the parameters: it is slot *n* of the tag, which the
    # finding already carries. The parameters hold which slot.
    slot = int(valori.get("slot", 0) or 0)
    tag = str(valori.get("postag", ""))
    return {"la_posizione": la_posizione(slot, lingua),
            "valore": tag[slot] if len(tag) > slot else ""}


@_derivazione("common-gender-c", extra=("lemma", "form"))
def _der_genere_comune(valori: dict, lingua: str) -> dict:
    return {"parola": valori.get("lemma") or valori.get("form") or ""}


@_derivazione("underscore-person-number")
def _der_trattino_basso(valori: dict, lingua: str) -> dict:
    slots = list(valori.get("slots", ()))
    caselle = [posizione(slot, lingua) for slot in slots]
    if lingua == "it":
        dove = "in questa casella" if len(slots) == 1 else "in queste caselle"
    else:
        dove = "in this slot" if len(slots) == 1 else "in these slots"
    return {"caselle": ", ".join(caselle), "dove": dove}


#: The three reasons why a participial δεῖν is not corrected. The parameter carries the
#: code, not the sentence.
_MOTIVI_DEIN: dict[str, tuple[str, str]] = {
    "identificato": (
        "Il luogo è fra le attestazioni che il LSJ, s.v. δεῖ, IV, marca "
        "dubbie: «δεῖν is dub. in Ar.Fr.220, Lys.14.7».",
        "The passage is among the attestations that LSJ, s.v. δεῖ, IV, marks "
        "as doubtful: «δεῖν is dub. in Ar.Fr.220, Lys.14.7»."),
    "non_escludibile": (
        "L'autore è quello di un'attestazione che il LSJ marca dubbia, ma il "
        "riferimento disponibile non ha la granularità per stabilire se "
        "l'occorrenza sia quella: il programma non dichiara che lo sia, "
        "dichiara di non poterlo escludere.",
        "The author is the author of an attestation LSJ marks as doubtful, but "
        "the available reference is not granular enough to establish whether "
        "this occurrence is that one: the program does not declare that it is, "
        "it declares that it cannot rule it out."),
    "senza_provenienza": (
        "Il record non identifica autore e opera, e senza quella informazione "
        "non si può escludere che l'occorrenza sia uno dei luoghi che il LSJ "
        "marca dubbi.",
        "The record does not identify author and work, and without that "
        "information one cannot rule out that the occurrence is one of the "
        "passages LSJ marks as doubtful."),
}


@_derivazione("dein-participle-disputed")
def _der_dein(valori: dict, lingua: str) -> dict:
    coppia = _MOTIVI_DEIN.get(str(valori.get("motivo", "")), ("", ""))
    return {"spiegazione": coppia[0] if lingua == "it" else coppia[1]}


_PERSONE: dict[int, tuple[str, str]] = {
    1: ("prima", "first"), 2: ("seconda", "second"), 3: ("terza", "third")}


@_derivazione("personal-pronoun-person", extra=("form",))
def _der_pronome(valori: dict, lingua: str) -> dict:
    coppia = _PERSONE.get(int(valori.get("persona", 0) or 0), ("", ""))
    return {"forma": unicodedata.normalize("NFC", str(valori.get("form", ""))),
            "persona_parola": coppia[0] if lingua == "it" else coppia[1]}


def _classe_della_parola(tag: object, lingua: str) -> str:
    """“verb in the participle mood”, “noun” — the class that the tag declares."""
    testo = str(tag or "")
    if len(testo) != 9:
        return describe_value(0, testo[:1], lingua) if testo else ""
    classe = describe_value(0, testo[0], lingua)
    if testo[0] != "v":
        return classe
    modo = testo[4]
    if modo == "-":
        return classe + (" di modo non indicato" if lingua == "it"
                         else " of unstated mood")
    nome = describe_value(4, modo, lingua)
    return classe + (f" di modo {nome}" if lingua == "it" else f" of {nome} mood")


#: The grammatical gender of the Italian name of each position: “una persona”, “un
#: numero”. It is needed only here, where the name follows an indefinite article, and it
#: lives here and not in the scheme because it is a property of the language in which the
#: sentence is written, not of the position.
_ARTICOLO_POSIZIONE: dict[int, str] = {
    0: "una", 1: "una", 2: "un", 3: "un", 4: "un",
    5: "una", 6: "un", 7: "un", 8: "un",
}


def _la_ordinale(slot: int) -> str:
    """``'la settima'``, but ``'l'ottava'``: elision before a vowel."""
    ordinale = _ORDINALI["it"][int(slot)]
    return ("l'" if ordinale[0] in "aeiou" else "la ") + ordinale


@_derivazione("slot-forbidden", extra=("postag",))
def _der_slot_vietato(valori: dict, lingua: str) -> dict:
    # The parameters carry the slots filled where they should not be; the character
    # found there is told by the tag.
    tag = str(valori.get("postag", ""))
    voci = []
    for slot in valori.get("slots", ()):
        slot = int(slot)
        carattere = tag[slot] if len(tag) > slot else ""
        nome = nome_posizione(slot, lingua).lower()
        ordinale = _ORDINALI[lingua][slot]
        glossa = describe_value(slot, carattere, lingua)
        if lingua == "it":
            articolo = _ARTICOLO_POSIZIONE.get(slot, "un")
            voci.append(f"{articolo} {nome} ({_la_ordinale(slot)} posizione "
                        f"porta «{carattere}», {glossa})")
        else:
            voci.append(f"a {nome} (the {ordinale} position holds "
                        f"«{carattere}», {glossa})")
    return {"classe": _classe_della_parola(tag, lingua), "tratti": ", ".join(voci)}


@_derivazione("slot-missing.uno", "slot-missing.molti",
              "slot-missing-bare.uno", "slot-missing-bare.molti",
              extra=("postag",))
def _der_slot_mancante(valori: dict, lingua: str) -> dict:
    tag = str(valori.get("postag", ""))
    voci = []
    for slot in valori.get("slots", ()):
        slot = int(slot)
        nome = nome_posizione(slot, lingua).lower()
        ordinale = _ORDINALI[lingua][slot]
        voci.append(f"{nome} ({ordinale} posizione)" if lingua == "it"
                    else f"{nome} ({ordinale} position)")
    return {"classe": _classe_della_parola(tag, lingua), "tratti": ", ".join(voci)}


@_derivazione("invalid-length-padding.piu-di-nove", "invalid-length-broken",
              extra=("postag",))
def _der_lunghezza(valori: dict, lingua: str) -> dict:
    # The length of the tag is the length of the tag: it is counted, not carried.
    lunghezza = len(str(valori.get("postag", "")))
    return {"lunghezza": lunghezza,
            "quanti_caratteri": quanti(
                lunghezza, "carattere" if lingua == "it" else "character",
                "caratteri" if lingua == "it" else "characters")}


@_derivazione("aux-governs-conjuncts")
def _der_congiunti(valori: dict, lingua: str) -> dict:
    return {"quanti_congiunti": quanti(
        valori.get("congiunti", 0),
        "congiunto marcato _CO" if lingua == "it" else "conjunct marked _CO",
        "congiunti marcati _CO" if lingua == "it" else "conjuncts marked _CO")}


@_derivazione("aux-finite-verb")
def _der_dipendenti(valori: dict, lingua: str) -> dict:
    return {"quanti_dipendenti": quanti(
        valori.get("dipendenti", 0),
        "dipendente proprio" if lingua == "it" else "dependent of its own",
        "dipendenti propri" if lingua == "it" else "dependents of its own")}


@_derivazione("uninflected-lemma", extra=("lemma",))
def _der_lemma_indeclinabile(valori: dict, lingua: str) -> dict:
    voce = unicodedata.normalize("NFC", str(valori.get("lemma", "")))
    tutte = numero(valori.get("totale", 0), lingua)
    viste = numero(valori.get("segnalate", 0), lingua)
    uguali = str(valori.get("totale", 0)) == str(valori.get("segnalate", 0))
    if lingua == "it":
        conteggio = (f"compare {tutte} volte in questo corpus, non porta mai "
                     "un caso e ogni volta ha l'etichetta incompleta"
                     if uguali else
                     f"compare {tutte} volte in questo corpus e non porta mai "
                     f"un caso; {viste} di quelle occorrenze hanno l'etichetta "
                     "incompleta")
    else:
        conteggio = (f"occurs {tutte} times in this corpus, never carries a "
                     "case, and every time has an incomplete tag"
                     if uguali else
                     f"occurs {tutte} times in this corpus and never carries a "
                     f"case; {viste} of those occurrences have an incomplete "
                     "tag")
    return {"voce": voce, "conteggio": conteggio}


# ── The lexical repairs ────────────────────────────────────────────────────
#
# Eight rules, two sentences. Each rule keeps its own identifier as its key — the
# identity between ``rule_id`` and ``issue_key`` holds here too — but the sentences are
# only two, and they are registered in a block because writing them eight times would
# mean maintaining them eight times.

_RIPARAZIONE_AUTOMATICA = (
    "La forma «{form}» porta l'etichetta «{postag}», che per questa parola è "
    "sbagliata. Lo spoglio manuale dei due corpora ha stabilito la lettura "
    "giusta di questa forma con questa etichetta.",
    "The form «{form}» carries the tag «{postag}», which for this word is "
    "wrong. The manual survey of the two corpora established the right reading "
    "of this form with this tag.")

_RIPARAZIONE_DA_VERIFICARE = (
    "La forma «{form}» porta l'etichetta «{postag}». Gli altri corpora la "
    "leggono in prevalenza in un altro modo, ma nessuna correzione viene "
    "proposta: richiede revisione manuale, perché quale delle due letture sia "
    "giusta lo decide la costruzione e non la stringa.",
    "The form «{form}» carries the tag «{postag}». The other corpora mostly "
    "read it another way, but no correction is proposed: it requires manual "
    "review, because which of the two readings is right is decided by the "
    "construction and not by the string.")


def _registra_riparazioni_lessicali() -> None:
    from .rule_catalog import LEXICAL_REPAIRS
    for regola in LEXICAL_REPAIRS:
        TESTI[str(regola["rule_id"])] = (
            _RIPARAZIONE_AUTOMATICA if regola.get("auto", True)
            else _RIPARAZIONE_DA_VERIFICARE)


_registra_riparazioni_lessicali()


# ===========================================================================
# Family: lemma
# ===========================================================================

TESTI.update({

    "missing-lemma": (
        "Il campo del lemma è vuoto: il token non è ricondotto a nessuna voce "
        "di dizionario, quindi non compare in nessun conteggio per lemma. Non "
        "viene proposta nessuna correzione: nei testi mutili il vuoto è spesso "
        "la risposta onesta.",
        "The lemma field is empty: the token is not referred to any dictionary "
        "entry, so it appears in no count by lemma. No correction is proposed: "
        "in mutilated texts the blank is often the honest answer."),

    "lemma-tool-numbering": (
        "Il lemma «{lemma}» finisce con una cifra, che non è una lettera "
        "greca: è il numero con cui il progetto di partenza distingue le voci "
        "omografe del lessico (λέγω1, λέγω2, λέγω3) o numera la classe della "
        "punteggiatura (punc1). Finché resta, la stessa parola si conta come "
        "voci diverse e non si allinea con gli altri corpora. Il programma non "
        "propone il lemma senza la cifra: togliendo la cifra le voci che il "
        "lessico teneva distinte si fondono in una, e quella perdita la deve "
        "accettare chi corregge.",
        "The lemma «{lemma}» ends with a digit, which is not a Greek letter: "
        "it is the number with which the source project distinguishes the "
        "homographic entries of its lexicon (λέγω1, λέγω2, λέγω3) or numbers "
        "the punctuation class (punc1). As long as it stays, the same word is "
        "counted as different entries and does not align with the other "
        "corpora. The program does not propose the lemma without the digit: "
        "removing it merges into one the entries the lexicon kept apart, and "
        "that loss has to be accepted by whoever corrects."),

    "lemma-graphic-variant": (
        "Il lemma «{lemma}» è una grafia diversa di una voce di dizionario che "
        "il corpus scrive anche in un altro modo. L'altra grafia è scelta come "
        "canonica in un elenco ricavato dallo spoglio manuale dei corpora "
        "annotati a mano, e il programma non la propone: qui non si corregge "
        "un errore, si sceglie quale delle due grafie contare, e la scelta è "
        "di chi legge.",
        "The lemma «{lemma}» is a different spelling of a dictionary entry the "
        "corpus also writes another way. The other spelling is the one chosen "
        "as canonical in a list drawn from the manual survey of the "
        "hand-annotated corpora, and the program does not propose it: here one "
        "does not correct a mistake, one chooses which of the two spellings to "
        "count, and that choice belongs to the reader."),

    "lemma-suspicious-characters": (
        "Il lemma «{lemma}» contiene trattini, parentesi o cifre in mezzo alla "
        "parola: non sono lettere greche, sono le convenzioni del progetto da "
        "cui il lemma proviene (Perseus scrive i composti con il trattino, "
        "διά-λέγω). Il conteggio per lemma non li riconosce come la stessa "
        "voce degli altri corpora. Non viene proposta nessuna correzione: la "
        "forma canonica dipende da quale convenzione si sceglie.",
        "The lemma «{lemma}» holds hyphens, brackets or digits in the middle "
        "of the word: they are not Greek letters, they are the conventions of "
        "the project the lemma comes from (Perseus writes compounds with a "
        "hyphen, διά-λέγω). The count by lemma does not recognise them as the "
        "same entry as in the other corpora. No correction is proposed: the "
        "canonical form depends on which convention one adopts."),

    "lemma-rare-for-form": (
        "La forma «{form}», con questa parte del discorso, è ricondotta qui al "
        "lemma «{lemma}», una volta sola, mentre nel resto del corpus è "
        "ricondotta a un altro lemma {maggioranza} volte su {totale}. "
        "Un'occorrenza isolata contro una maggioranza così larga è quasi "
        "sempre una svista. Il programma non propone il lemma della "
        "maggioranza: richiede revisione manuale, perché una forma greca può "
        "essere davvero omografa, e a deciderlo è il passo.",
        "The form «{form}», with this part of speech, is referred here to the "
        "lemma «{lemma}», once only, while in the rest of the corpus it is "
        "referred to another lemma {maggioranza} times out of {totale}. A "
        "single occurrence against so large a majority is nearly always a "
        "slip. The program does not propose the majority lemma: it requires "
        "manual review, because a Greek form can be genuinely homographic, and "
        "that is settled by the passage."),
})


# ===========================================================================
# Family: syntax
# ===========================================================================

TESTI.update({

    "head-dangling": (
        "La testa indicata ({testa}) non esiste in questa frase.",
        "The head given ({testa}) does not exist in this sentence."),

    "sentence-not-annotated": (
        "In questa frase nessun token dichiara una testa sintattica: l'albero "
        "non è stato costruito. Non è un buco da riempire token per token: è "
        "una porzione di testo rimasta fuori dal lavoro di annotazione.",
        "In this sentence no token declares a syntactic head: the tree was "
        "never built. It is not a hole to be filled token by token: it is a "
        "stretch of text that stayed outside the annotation work."),

    "head-missing": (
        "Il token non indica nessuna testa sintattica: qui l'annotazione "
        "dell'albero manca o è rimasta incompleta. Non c'è un valore da "
        "correggere, perché non c'è nessun valore. Il token resta fuori "
        "dall'albero, e con lui tutto quello che dipende da lui.",
        "The token gives no syntactic head: here the annotation of the tree is "
        "missing or was left incomplete. There is no value to correct, because "
        "there is no value at all. The token stays outside the tree, and with "
        "it everything that depends on it."),

    "token-id-duplicate": (
        "Due token della stessa frase hanno lo stesso identificatore.",
        "Two tokens of the same sentence have the same identifier."),

    "relation-greek-lookalike": (
        "L'etichetta scritta nel file è «{relation}». La differenza non si "
        "vede a schermo: l'etichetta contiene {differenza}. Per il programma è "
        "perciò un'etichetta nuova, assente dallo schema AGDT: finisce così "
        "com'è nei conteggi e nei dati di addestramento.",
        "The label written in the file is «{relation}». The difference is "
        "invisible on screen: the label holds {differenza}. To the program it "
        "is therefore a new label, absent from the AGDT scheme: it goes into "
        "the counts and into the training data exactly as it stands."),

    "relation-typo": (
        "L'etichetta scritta nel file è «{relation}»: non esiste nello schema "
        "AGDT. È un'etichetta dello schema con una lettera sbagliata"
        "{dettaglio}, e a differenza di una lettera greca l'errore si vede a "
        "occhio.",
        "The label written in the file is «{relation}»: it does not exist in "
        "the AGDT scheme. It is a label of the scheme with one wrong letter"
        "{dettaglio}, and unlike a Greek letter the mistake is visible to the "
        "eye."),

    "relation-truncated-or-foreign.suffisso-orfano": (
        "L'etichetta scritta nel file è «{relation}»: è una relazione AGDT "
        "incompleta, non una relazione dello schema. «_CO» è il suffisso che "
        "marca un membro di coordinazione, e qui compare da solo: manca la "
        "funzione sintattica che dovrebbe stargli davanti (SBJ_CO, OBJ_CO, "
        "ADV_CO…). Non viene proposta nessuna correzione: quale sia "
        "l'etichetta giusta si stabilisce solo leggendo la frase e guardando "
        "l'albero.",
        "The label written in the file is «{relation}»: it is an incomplete "
        "AGDT relation, not a relation of the scheme. «_CO» is the suffix that "
        "marks a member of a coordination, and here it stands alone: the "
        "syntactic function that should precede it is missing (SBJ_CO, OBJ_CO, "
        "ADV_CO…). No correction is proposed: which label is the right one can "
        "only be settled by reading the sentence and looking at the tree."),

    "relation-truncated-or-foreign.etichetta-tagliata": (
        "L'etichetta scritta nel file è «{relation}»: è una relazione AGDT "
        "incompleta, non una relazione dello schema. «Aux» è l'inizio delle "
        "etichette della famiglia Aux senza la lettera finale, e lo schema ne "
        "prevede nove: AuxP, AuxC, AuxR, AuxV, AuxX, AuxG, AuxK, AuxY, AuxZ. "
        "Non viene proposta nessuna correzione: quale sia l'etichetta giusta "
        "si stabilisce solo leggendo la frase e guardando l'albero.",
        "The label written in the file is «{relation}»: it is an incomplete "
        "AGDT relation, not a relation of the scheme. «Aux» is the beginning "
        "of the labels of the Aux family without the final letter, and the "
        "scheme has nine of them: AuxP, AuxC, AuxR, AuxV, AuxX, AuxG, AuxK, "
        "AuxY, AuxZ. No correction is proposed: which label is the right one "
        "can only be settled by reading the sentence and looking at the tree."),

    "relation-truncated-or-foreign.nome-di-altro-schema": (
        "L'etichetta scritta nel file è «{relation}»: è una relazione AGDT "
        "incompleta, non una relazione dello schema. «CONJ» è il nome che "
        "altri schemi di annotazione danno alla congiunzione; lo schema AGDT "
        "non lo prevede. Non viene proposta nessuna correzione: quale sia "
        "l'etichetta giusta si stabilisce solo leggendo la frase e guardando "
        "l'albero.",
        "The label written in the file is «{relation}»: it is an incomplete "
        "AGDT relation, not a relation of the scheme. «CONJ» is the name other "
        "annotation schemes give to the conjunction; the AGDT scheme does not "
        "provide for it. No correction is proposed: which label is the right "
        "one can only be settled by reading the sentence and looking at the "
        "tree."),

    "relation-truncated-or-foreign.fuori-inventario": (
        "L'etichetta scritta nel file è «{relation}»: è una relazione AGDT "
        "incompleta, non una relazione dello schema. L'etichetta non "
        "appartiene all'inventario AGDT. Non viene proposta nessuna "
        "correzione: quale sia l'etichetta giusta si stabilisce solo leggendo "
        "la frase e guardando l'albero.",
        "The label written in the file is «{relation}»: it is an incomplete "
        "AGDT relation, not a relation of the scheme. The label does not "
        "belong to the AGDT inventory. No correction is proposed: which label "
        "is the right one can only be settled by reading the sentence and "
        "looking at the tree."),

    "relation-bare-convention": (
        "L'etichetta scritta nel file è «{relation}», che lo schema AGDT non "
        "prevede da sola. In questo corpus però non è una svista: compare in "
        "quasi tutti i documenti e con una frequenza che la rende una "
        "convenzione della risorsa, non un guasto di singoli record. "
        "Nessuna correzione proposta: l'etichetta AGDT corrispondente non si "
        "ricava dalla stringa.",
        "The label written in the file is «{relation}», which the AGDT scheme "
        "does not provide for on its own. In this corpus, though, it is not a "
        "slip: it appears in nearly every document and with a frequency that "
        "makes it a convention of the resource, not a fault of individual "
        "records. No correction is proposed: the corresponding AGDT label "
        "cannot be derived from the string."),

    "relation-nil-placeholder": (
        "Nel campo della relazione c'è scritto «{relation}», cioè un "
        "segnaposto che dichiara «nessun valore»: il campo non è vuoto, ma non "
        "contiene nessuna analisi sintattica, e per il programma resta "
        "un'etichetta come le altre. Non viene proposta nessuna correzione: la "
        "relazione va scritta a mano leggendo la frase, mentre sostituirla con "
        "«UNDEFINED» cambierebbe solo il modo di dire che manca.",
        "The relation field holds «{relation}», that is, a placeholder "
        "declaring «no value»: the field is not empty, but it carries no "
        "syntactic analysis, and to the program it remains a label like any "
        "other. No correction is proposed: the relation has to be written by "
        "hand from the sentence, while replacing it with «UNDEFINED» would "
        "only change the way of saying that it is missing."),

    "relation-unknown": (
        "L'etichetta «{relation}» non è prevista dallo schema AGDT e non è "
        "riconducibile a nessuna delle etichette previste: di solito viene da "
        "un altro schema di annotazione. Non viene proposta nessuna "
        "correzione: se un equivalente AGDT esiste, va scelto leggendo la "
        "frase.",
        "The label «{relation}» is not provided for by the AGDT scheme and "
        "cannot be referred to any of the labels it provides: usually it comes "
        "from another annotation scheme. No correction is proposed: if an AGDT "
        "equivalent exists, it has to be chosen by reading the sentence."),

    "relation-missing": (
        "Il token non ha nessuna relazione sintattica.",
        "The token has no syntactic relation."),

    "head-cycle": (
        "Il token fa parte di un ciclo: seguendo le teste si torna al punto di "
        "partenza.",
        "The token is part of a cycle: following the heads brings you back to "
        "where you started."),

    "sentence-no-root": (
        "La frase non ha nessuna radice: nessun token con head = 0.",
        "The sentence has no root: no token with head = 0."),

    "sentence-many-roots": (
        "La frase ha {radici} radici indipendenti: nello schema AGDT ne è "
        "prevista una sola.",
        "The sentence has {radici} independent roots: the AGDT scheme provides "
        "for one only."),

    "coord-suffix-orphan": (
        "Il token è marcato come coordinato (_CO), ma risalendo dalla sua "
        "testa attraverso preposizioni, congiunzioni subordinanti, apposizioni "
        "e congiunzioni correlative non si arriva a un nodo COORD: si arriva a "
        "'{relazione_raggiunta}'. Nello schema AGDT ogni congiunto porta il "
        "suffisso _CO e dipende dal nodo COORD; qui il suffisso c'è e la "
        "coordinazione non si trova.",
        "The token is marked as coordinated (_CO), but climbing from its head "
        "through prepositions, subordinating conjunctions, appositions and "
        "correlative conjunctions one does not reach a COORD node: one reaches "
        "'{relazione_raggiunta}'. In the AGDT scheme every conjunct carries "
        "the _CO suffix and depends on the COORD node; here the suffix is "
        "there and the coordination is not to be found."),

    "apos-suffix-orphan": (
        "Il token è marcato come apposto (_AP), ma risalendo dalla sua testa "
        "attraverso preposizioni e congiunzioni non si arriva a un nodo APOS: "
        "si arriva a '{relazione_raggiunta}'.",
        "The token is marked as apposed (_AP), but climbing from its head "
        "through prepositions and conjunctions one does not reach an APOS "
        "node: one reaches '{relazione_raggiunta}'."),

    "coord-discordant-conjuncts": (
        "I congiunti di questo COORD hanno funzioni sintattiche diverse fra "
        "loro. Non è un errore: è una coordinazione asimmetrica, e in greco lo "
        "zeugma è una figura. La segnalazione serve solo a far vedere il "
        "punto, perché fra le coordinazioni asimmetriche si nascondono anche "
        "gli errori di attacco.",
        "The conjuncts of this COORD have different syntactic functions from "
        "one another. It is not a mistake: it is an asymmetric coordination, "
        "and in Greek zeugma is a figure. The finding only serves to show the "
        "place, because among the asymmetric coordinations the attachment "
        "errors hide as well."),

    "aux-governs-conjuncts": (
        "Il token ha relazione '{relation}' ma regge {quanti_congiunti}: nello "
        "schema AGDT chi regge dei congiunti è il nodo COORD, non una "
        "particella. Non viene proposta nessuna etichetta al posto di questa: "
        "può essere sbagliata l'etichetta del nodo, oppure il suffisso _CO dei "
        "figli, e la frase lo dice, il programma no.",
        "The token has relation '{relation}' but governs {quanti_congiunti}: "
        "in the AGDT scheme what governs conjuncts is the COORD node, not a "
        "particle. No label is proposed in its place: the label of the node "
        "may be wrong, or the _CO suffix of the children may be, and the "
        "sentence says which, the program does not."),

    "aux-finite-verb": (
        "Il token è un verbo di modo finito ma porta la relazione "
        "'{relation}', riservata alle particelle e agli avverbi di frase, e "
        "regge {quanti_dipendenti}: è una parentetica trattata come "
        "particella. Non è un errore: è una scelta del corpus, coerente e non "
        "vietata dalle linee guida. Il verbo però perde l'analisi verbale, e "
        "l'etichetta sintattica e la parte del discorso danno due letture "
        "incompatibili. Va deciso, non corretto.",
        "The token is a finite verb but carries the relation '{relation}', "
        "which is reserved for particles and sentence adverbs, and it governs "
        "{quanti_dipendenti}: it is a parenthetical treated as a particle. It "
        "is not a mistake: it is a choice of the corpus, "
        "consistent and not forbidden by the guidelines. The verb, however, "
        "loses its verbal analysis, and the syntactic label and the part of "
        "speech give two incompatible readings. It is to be decided, not "
        "corrected."),

    "aux-governor-without-child": (
        "Il token ha relazione '{relation}', ma non ha nessun dipendente. In "
        "un albero AGDT la preposizione e la congiunzione subordinante sono "
        "nodi di passaggio: il complemento della preposizione e il verbo della "
        "subordinata dipendono da loro. L'aspettativa non è però scritta a "
        "lettere nelle linee guida, ed è per questo che il controllo sta fra i "
        "casi da verificare e non fra le violazioni: viene dai corpora, dove "
        "nell'annotazione manuale un AuxP senza dipendenti è lo 0,20% dei casi "
        "in Gorman e lo 0,32% in Pedalion, e un AuxC lo 0,32% e l'1,34%. Può "
        "essere che il dipendente sia stato attaccato altrove, o che qui "
        "quella parola non sia una preposizione ma un avverbio.",
        "The token has relation '{relation}', but has no dependent at all. In "
        "an AGDT tree the preposition and the subordinating conjunction are "
        "transit nodes: the complement of the preposition and the verb of the "
        "subordinate clause depend on them. The expectation is not, however, "
        "written out in the guidelines, and that is why the check sits among "
        "the cases to be verified and not among the violations: it comes from "
        "the corpora, where in manual annotation an AuxP without dependents is "
        "0.20% of the cases in Gorman and 0.32% in Pedalion, and an AuxC 0.32% "
        "and 1.34%. It may be that the dependent was attached elsewhere, or "
        "that here the word is not a preposition but an adverb."),
})


# ── The derivations of the family ──────────────────────────────────────────

@_derivazione("head-dangling", extra=("head",))
def _der_testa_inesistente(valori: dict, lingua: str) -> dict:
    testa = str(valori.get("head", ""))
    try:
        testa = str(int(float(testa)))
    except (TypeError, ValueError):
        pass
    return {"testa": testa}


@_derivazione("relation-greek-lookalike")
def _der_sosia_greche(valori: dict, lingua: str) -> dict:
    coppie = valori.get("coppie", ())
    if not coppie:
        return {"differenza": ("una lettera greca al posto di quella latina"
                               if lingua == "it"
                               else "a Greek letter where the Latin one belongs")}
    voci = []
    for coppia in coppie:
        greco = str(coppia.get("greco", ""))
        latino = str(coppia.get("latino", ""))
        if lingua == "it":
            voci.append(f"«{carattere_di(greco)}» ({greco}, lettera greca) al "
                        f"posto di «{carattere_di(latino)}» ({latino}, lettera "
                        "latina)")
        else:
            voci.append(f"«{carattere_di(greco)}» ({greco}, Greek letter) where "
                        f"«{carattere_di(latino)}» ({latino}, Latin letter) "
                        "belongs")
    congiunzione = " e " if lingua == "it" else " and "
    return {"differenza": congiunzione.join(voci)}


@_derivazione("relation-typo")
def _der_refuso(valori: dict, lingua: str) -> dict:
    lettera = str(valori.get("lettera", "") or "")
    if not lettera:
        return {"dettaglio": ""}
    return {"dettaglio": (f" («{lettera}» al posto della lettera giusta)"
                          if lingua == "it"
                          else f" («{lettera}» where the right letter belongs)")}


# ===========================================================================
# Family: text and encoding
# ===========================================================================

TESTI.update({

    "corpus-not-nfc": (
        "Il corpus è distribuito in forma normale Unicode NFD: {decomposti} "
        "record su {totale} ({quota}) hanno la forma o il lemma in forma "
        "decomposta. Non è un guasto di singoli token ma la codifica scelta da "
        "chi pubblica la risorsa, e viene segnalata una volta sola. Conta lo "
        "stesso, e molto: due token identici a video non risultano uguali a "
        "nessun confronto che non normalizzi prima, e ogni elenco chiuso di "
        "forme o di lemmi, compresi quelli di questo programma, non trova "
        "niente finché il testo resta decomposto. La conversione in NFC cambia "
        "la codifica, non una lettera del testo, e si applica a tutto il "
        "corpus in una volta.",
        "The corpus is distributed in Unicode normal form NFD: {decomposti} "
        "records out of {totale} ({quota}) have the form or the lemma "
        "decomposed. It is not a fault of individual tokens but the encoding "
        "chosen by whoever publishes the resource, and it is reported once "
        "only. It counts all the same, and a great deal: two tokens identical "
        "on screen do not come out equal in any comparison that does not "
        "normalise first, and every closed list of forms or lemmas, this "
        "program's included, finds nothing as long as the text stays "
        "decomposed. Conversion to NFC changes the encoding, not a letter of "
        "the text, and applies to the whole corpus at once."),

    "unicode-not-nfc": (
        "Il campo «{campi}» non è in forma normale Unicode NFC: due token "
        "identici a video non vengono riconosciuti come uguali da nessun "
        "conteggio, ricerca o confronto. La conversione in NFC cambia la "
        "codifica, non una lettera del testo.",
        "The field «{campi}» is not in Unicode normal form NFC: two tokens "
        "identical on screen are not recognised as equal by any count, search "
        "or comparison. Conversion to NFC changes the encoding, not a letter "
        "of the text."),

    "apostrophe-mixed": (
        "Nel file convivono codifiche diverse dell'apostrofo. Qui: {caratteri}. "
        "Due token identici a video non risultano uguali a nessun confronto "
        "finché la codifica dell'apostrofo non è una sola.",
        "Several encodings of the apostrophe live together in this file. Here: "
        "{caratteri}. Two tokens identical on screen do not come out equal in "
        "any comparison as long as the apostrophe has more than one encoding."),

    "mixed-script": (
        "La parola mescola alfabeto greco e latino. Caratteri estranei: "
        "«{intrusi}». Ogni lettera latina ha qui una corrispondente greca "
        "identica a vedersi, e per questo la riscrittura è senza perdita.",
        "The word mixes the Greek and the Latin alphabet. Foreign characters: "
        "«{intrusi}». Every Latin letter here has a Greek counterpart "
        "identical to look at, and that is why rewriting it loses nothing."),

    "mixed-script-unrepairable": (
        "La parola mescola alfabeto greco e latino. Caratteri estranei: "
        "«{intrusi}». Non viene proposta nessuna correzione: queste lettere "
        "latine non hanno una corrispondente greca identica a vedersi, e di "
        "solito non sono lettere ma segni editoriali (nei papiri «G» segna una "
        "lacuna). Che cosa vada al loro posto si stabilisce solo sul testo.",
        "The word mixes the Greek and the Latin alphabet. Foreign characters: "
        "«{intrusi}». No correction is proposed: these Latin letters have no "
        "Greek counterpart identical to look at, and usually they are not "
        "letters but editorial signs (in the papyri «G» marks a lacuna). What "
        "belongs in their place can only be settled on the text."),

    "beta-code-form": (
        "Il campo «form» contiene simboli tipici del beta code (*, /, \\, |, "
        "+, =, parentesi): probabile conversione incompleta.",
        "The field «form» holds symbols typical of beta code (*, /, \\, |, +, "
        "=, brackets): an incomplete conversion is likely."),

    "beta-code-lemma": (
        "Il campo «lemma» contiene simboli tipici del beta code (*, /, \\, |, "
        "+, =, parentesi): probabile conversione incompleta.",
        "The field «lemma» holds symbols typical of beta code (*, /, \\, |, +, "
        "=, brackets): an incomplete conversion is likely."),

    "breathing-impossible": (
        "In fondo alla forma c'è uno spirito dolce appoggiato a una consonante: "
        "lì non può essere un diacritico, ed è quasi sempre l'apostrofo di "
        "elisione scritto con il carattere sbagliato. Il valore giusto va "
        "stabilito leggendo la parola.",
        "At the end of the form there is a smooth breathing resting on a "
        "consonant: there it cannot be a diacritic, and it is nearly always "
        "the apostrophe of elision written with the wrong character. The right "
        "value has to be settled by reading the word."),

    "breathing-impossible.delta-elisa": (
        "La forma è «δ̓» e il lemma è «δέ»: lo spirito dolce sta al posto "
        "dell'apostrofo di elisione. La firma è stata controllata a mano, e la "
        "riscrittura tocca soltanto la forma.",
        "The form is «δ̓» and the lemma is «δέ»: the smooth breathing stands in "
        "for the apostrophe of elision. The signature was checked by hand, and "
        "the rewriting touches the form only."),

    "isolated-breathing": (
        "La forma è costituita soltanto da un segno di spirito, che non è una "
        "parola del testo. Nei casi verificati il segno sta al posto di una "
        "parentesi, ma può anche essere il frammento di una parola spezzata "
        "fra due record: la proposta compare soltanto sulle occorrenze già "
        "controllate a mano.",
        "The form consists of a breathing sign and nothing else, which is not "
        "a word of the text. In the verified cases the sign stands in for a "
        "bracket, but it may also be the fragment of a word broken across two "
        "records: the proposal appears only on the occurrences already checked "
        "by hand."),

    "double-accent": (
        "La parola porta due accenti e non è seguita da un'enclitica.",
        "The word carries two accents and is not followed by an enclitic."),

    "final-sigma-inside": (
        "Il sigma finale «ς» compare in una posizione interna della parola, "
        "dove è atteso «σ».",
        "The final sigma «ς» appears in a word-internal position, where «σ» is "
        "expected."),

    "invisible-char-form": (
        "Il campo «form» contiene uno dei caratteri di formato Unicode che la "
        "pipeline riconosce (U+200B, U+200C, U+200D, U+2060, U+FEFF): "
        "categoria «Cf», nessuna resa a schermo, nessuna funzione ortografica "
        "nel greco del corpus, e un confronto fra stringhe graficamente uguali "
        "che si rompe.",
        "The field «form» holds one of the Unicode format characters the "
        "pipeline recognises (U+200B, U+200C, U+200D, U+2060, U+FEFF): "
        "category «Cf», no rendering on screen, no orthographic function in "
        "the Greek of the corpus, and a comparison between graphically equal "
        "strings that breaks."),

    "invisible-char-lemma": (
        "Il campo «lemma» contiene uno dei caratteri di formato Unicode che la "
        "pipeline riconosce (U+200B, U+200C, U+200D, U+2060, U+FEFF): "
        "categoria «Cf», nessuna resa a schermo, nessuna funzione ortografica "
        "nel greco del corpus, e un confronto fra stringhe graficamente uguali "
        "che si rompe.",
        "The field «lemma» holds one of the Unicode format characters the "
        "pipeline recognises (U+200B, U+200C, U+200D, U+2060, U+FEFF): "
        "category «Cf», no rendering on screen, no orthographic function in "
        "the Greek of the corpus, and a comparison between graphically equal "
        "strings that breaks."),

    "whitespace-in-form": (
        "Il campo «form» contiene uno spazio, uno spazio unificatore, una "
        "tabulazione o un a capo dentro il token. Nessuna correzione proposta: "
        "togliere il separatore nasconderebbe il caso in cui la tokenizzazione "
        "ha unito due parole, che è la spiegazione più probabile.",
        "The field «form» holds a space, a no-break space, a tab or a line "
        "break inside the token. No correction is proposed: removing the "
        "separator would hide the case in which the tokenisation joined two "
        "words, which is the likelier explanation."),

    "whitespace-in-lemma": (
        "Il campo «lemma» contiene uno spazio, uno spazio unificatore, una "
        "tabulazione o un a capo dentro il token. Nessuna correzione proposta: "
        "togliere il separatore nasconderebbe il caso in cui la tokenizzazione "
        "ha unito due parole, che è la spiegazione più probabile.",
        "The field «lemma» holds a space, a no-break space, a tab or a line "
        "break inside the token. No correction is proposed: removing the "
        "separator would hide the case in which the tokenisation joined two "
        "words, which is the likelier explanation."),

    "annotator-note-in-relation": (
        "Il campo relazione contiene un appunto di lavorazione lasciato "
        "dall'annotatore: «{appunto}». Non è un'etichetta sintattica, quindi "
        "non se ne propone la correzione: va deciso caso per caso se l'appunto "
        "è già stato evaso, e va scritta la relazione che manca.",
        "The relation field holds a working note left by the annotator: "
        "«{appunto}». It is not a syntactic label, so no correction is "
        "proposed for it: it has to be decided case by case whether the note "
        "has already been dealt with, and the missing relation has to be "
        "written."),
})


# ── The derivations of the family ──────────────────────────────────────────

def _migliaia(valore_grezzo: object, lingua: str) -> str:
    """An integer with the thousands separator: 27.847 / 27,847."""
    try:
        testo = f"{int(valore_grezzo):,}"
    except (TypeError, ValueError):
        return str(valore_grezzo)
    return testo.replace(",", ".") if lingua == "it" else testo


@_derivazione("corpus-not-nfc")
def _der_corpus_nfd(valori: dict, lingua: str) -> dict:
    decomposti = int(valori.get("decomposti", 0) or 0)
    totale = int(valori.get("totale", 0) or 0)
    quota = f"{decomposti / max(totale, 1):.1%}"
    return {"decomposti": _migliaia(decomposti, lingua),
            "totale": _migliaia(totale, lingua),
            "quota": quota.replace(".", ",") if lingua == "it" else quota}


_CAMPI_TOKEN: dict[str, tuple[str, str]] = {
    "form": ("forma", "form"), "lemma": ("lemma", "lemma")}


@_derivazione("unicode-not-nfc")
def _der_nfc(valori: dict, lingua: str) -> dict:
    nomi = [(_CAMPI_TOKEN.get(str(c), (str(c), str(c)))[0 if lingua == "it" else 1])
            for c in valori.get("campi", ())]
    congiunzione = " e " if lingua == "it" else " and "
    return {"campi": congiunzione.join(nomi)}


@_derivazione("apostrophe-mixed")
def _der_apostrofi(valori: dict, lingua: str) -> dict:
    # The names of the characters sit next to the rule that knows them: importing them
    # here, and not copying them, prevents the two tables from diverging.
    from .orthography import APOSTROPHES
    nomi = sorted({APOSTROPHES.get(carattere_di(punto), nome_unicode(punto))
                   for punto in valori.get("codepoints", ())})
    return {"caratteri": ", ".join(nomi)}


@_derivazione("annotator-note-in-relation", extra=("relation",))
def _der_appunto(valori: dict, lingua: str) -> dict:
    return {"appunto": str(valori.get("relation", ""))[:60]}


# ===========================================================================
# Family: agreement
# ===========================================================================

TESTI.update({

    "agreement-modifier": (
        "Il modificatore non concorda con la testa: {discordanze}. L'errore "
        "può stare da una parte o dall'altra: spesso è l'etichetta della testa "
        "a essere sbagliata, e il modificatore è solo il modo per accorgersene.",
        "The modifier does not agree with its head: {discordanze}. The mistake "
        "may lie on either side: often it is the tag of the head that is "
        "wrong, and the modifier is only the way of noticing it."),

    "case-subject.tre-costruzioni": (
        "Soggetto in {caso}: le linee guida AGDT 2.0 (§ 3.2) ammettono il "
        "soggetto in nominativo, in genitivo nel genitivo assoluto e in "
        "accusativo nell'infinitiva e col participio supplementare, e qui non "
        "ricorre nessuna delle tre costruzioni. Da verificare: può essere "
        "sbagliato il caso, può esserlo la testa.",
        "Subject in the {caso}: the AGDT 2.0 guidelines (§ 3.2) admit the "
        "subject in the nominative, in the genitive in the genitive absolute, "
        "and in the accusative in the infinitive clause and with the "
        "supplementary participle, and none of the three constructions occurs "
        "here. To be verified: the case may be wrong, or the head may be."),

    "case-subject.mai-previsto": (
        "Soggetto in {caso}: è un caso che le linee guida AGDT 2.0 (§ 3.2) non "
        "prevedono per SBJ in nessuna costruzione, dove ammettono nominativo, "
        "genitivo e accusativo. Da verificare: può essere sbagliata "
        "l'etichetta morfologica, può esserlo la relazione.",
        "Subject in the {caso}: it is a case the AGDT 2.0 guidelines (§ 3.2) do "
        "not provide for with SBJ in any construction, where they admit the "
        "nominative, the genitive and the accusative. To be verified: the "
        "morphological tag may be wrong, or the relation may be."),

    "case-object": (
        "Il token ha relazione OBJ e un'etichetta morfologica in {caso}. Per "
        "un argomento nominale e' una combinazione rara, ma lo schema non la "
        "vieta: nelle linee guida AGDT 2.0 (§ 3.3) OBJ marca «any dependent "
        "which is taken to be an argument of the verb, adjective, or adverb», "
        "e sotto OBJ stanno anche l'infinito, il participio, la completiva e "
        "la relativa sostantivata, che portano il caso che spetta a loro. Il "
        "programma esclude gia' gli aggettivi verbali in -τέον e i nodi che "
        "hanno un soggetto o un oggetto proprio fra i figli, cioe' le teste di "
        "proposizione riconoscibili dall'albero. Quel che resta va guardato: "
        "puo' essere una testa predicativa che il programma non ha "
        "riconosciuto, oppure un caso sbagliato.",
        "The token has relation OBJ and a morphological tag in the {caso}. For "
        "a nominal argument this is a rare combination, but the scheme does "
        "not forbid it: in the AGDT 2.0 guidelines (§ 3.3) OBJ marks «any "
        "dependent which is taken to be an argument of the verb, adjective, or "
        "adverb», and under OBJ stand also the infinitive, the participle, the "
        "complement clause and the substantivised relative, which carry the "
        "case that belongs to them. The program already excludes verbal "
        "adjectives in -τέον and the nodes that have a subject or an object of "
        "their own among their children, that is, the clause heads the tree "
        "makes recognisable. What is left is worth looking at: it may be a "
        "predicative head the program did not recognise, or a wrong case."),

    "rare-relation-for-lemma-and-pos": (
        "Questa coppia lemma e parte del discorso porta la relazione "
        "«{relazione_base}» in {occorrenze} delle {totale} occorrenze che ha "
        "in questo corpus ({quota}%). È una misura interna al corpus: una "
        "costruzione può essere rara e corretta, e il numero assoluto dice "
        "quanto pesa la percentuale. Non viene proposta nessuna correzione.",
        "This lemma and part-of-speech pair carries the relation "
        "«{relazione_base}» in {occorrenze} of the {totale} occurrences it has "
        "in this corpus ({quota}%). It is a measure internal to the corpus: a "
        "construction can be rare and correct, and the absolute number says "
        "how much the percentage weighs. No correction is proposed."),
})


# ── The derivations of the family ──────────────────────────────────────────

@_derivazione("agreement-modifier")
def _der_accordo(valori: dict, lingua: str) -> dict:
    voci = []
    for voce in valori.get("discordanze", ()):
        nome = nome_posizione(int(voce.get("slot", 0)), lingua).lower()
        voci.append(f"{nome} {voce.get('modificatore', '-')}"
                    f"≠{voce.get('testa', '-')}")
    return {"discordanze": "; ".join(voci)}


@_derivazione("case-subject.tre-costruzioni", "case-subject.mai-previsto",
              "case-object", extra=("postag",))
def _der_caso(valori: dict, lingua: str) -> dict:
    # The case is not in the parameters: it is the eighth slot of the tag, which the
    # finding already carries.
    tag = str(valori.get("postag", ""))
    carattere = tag[7] if len(tag) > 7 else ""
    return {"caso": describe_value(7, carattere, lingua)}


@_derivazione("rare-relation-for-lemma-and-pos")
def _der_relazione_rara(valori: dict, lingua: str) -> dict:
    return {"quota": percentuale(valori.get("percentuale", 0), lingua)}


# ---------------------------------------------------------------------------
# The findings in the language of the reader
# ---------------------------------------------------------------------------

#: The columns of the finding that are text and not data: they are rewritten in the
#: requested language, and what is in the saved file is only the cache of the language in
#: which the analysis was run.
COLONNE_TESTUALI: tuple[str, ...] = ("anomaly_name", "anomaly_description", "issue")


def localizza(findings: pd.DataFrame, lingua: str = "it") -> pd.DataFrame:
    """The same findings, with the text in the requested language.

    The name and description of the check are derived from the catalogue starting
    from ``rule_id``; the sentence of the single occurrence from ``issue_key`` and
    ``issue_params``. None of the three is read from the file: the file contains
    them because a CSV must be openable by itself, not because they are the
    source.

    A run saved without this key keeps the sentence it has, and reads in the
    language in which it was produced: re-deriving it is not possible and
    inventing it would be worse.
    """
    if findings is None or len(findings) == 0:
        return findings
    from .rule_catalog import rule_description, rule_name

    fuori = findings.copy()
    if "rule_id" in fuori.columns:
        regole = fuori["rule_id"].astype("string").fillna("")
        fuori["anomaly_name"] = map_unique(
            regole, lambda rule: rule_name(str(rule), lingua)).astype("string")
        fuori["anomaly_description"] = map_unique(
            regole, lambda rule: rule_description(str(rule), lingua)).astype("string")
    if "issue_key" in fuori.columns:
        vecchia = (fuori["issue"].astype("string").fillna("")
                   if "issue" in fuori.columns
                   else pd.Series("", index=fuori.index, dtype="string"))
        nuova = rendi_serie(fuori, lingua).fillna("")
        fuori["issue"] = nuova.where(nuova.str.len() > 0, vecchia)
    return fuori
