"""The comparison between the annotation of the corpus and that of a model.

The module keeps two things apart that tend to be taken for the same one, and
are not:

**What is given to the model** is the text. A tagger and a parser also read
punctuation, because punctuation is linguistic context and removing it changes
the analysis of the words around it. So the input is the active records minus
the technical ones, that is, the words plus the real signs.

**What is measured on** is the words. The rate of agreement on lemmas cannot
have punctuation marks in the denominator, which have no lemma in the sense
in which a word has one, nor elliptic nodes, which correspond to nothing in
the text.

    input to the model ≠ universe of the evaluation

The rest follows from this separation.

**Alignment does not go through the form.** The model receives the corpus
already tokenised and returns one analysis per token; the alignment is
therefore between the canonical sentence and the position of the token inside
that sentence. Comparing forms as the key would mean that a difference of
encoding or a cleaned character made a token disappear from the comparison
without anybody noticing.

**A missing prediction is a disagreement, not a disappearance.** If a token is
in the denominator and the model produces nothing for it, the count keeps it
and counts it as a disagreement. The share of tokens for which a prediction
exists is called coverage and is reported separately: a model must not improve
its own rate by making disappear the cases it cannot align.

**Keys are normalised before being compared**, each in its own way. The lemma
in NFC and without the numbering of the tool, on both sides: GLAUx publishes
252,047 lemmas out of 300,292 in decomposed form, and comparing them with raw
equality would give an agreement close to zero for a typographical reason. The
map of canonical variants is **not** applied: the aim is to compare the lexical
choice of the model with that of the corpus, not to harmonise two different
lemmas.

**The morphological tag is compared only if it is the same kind of thing.** A
nine-character AGDT positional tag and a Universal Dependencies UPOS cannot be
compared with a string equality, and the result would be zero by construction.
The guard in :func:`postag_comparability` looks at the shape of the labels
returned by the model, and the metric stops **only** when none of them is
interpretable: then there is no object to measure. No conversion is built.

**A malformed prediction is a disagreement, not a suspension.** A model that
returns AGDT labels on the whole corpus and gets the shape wrong on three
tokens has got three tokens wrong: those three predictions stay in the
denominator, end up among the disagreements and are counted separately in
``previsioni_malformate``. Suppressing the whole measure would answer a defect
of a single token with a decision taken on the corpus.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .agdt_schema import TAG_LENGTH, VALID_CHARACTERS
from .fastmap import map_unique
from .normalise import nfc, without_lemma_numbering
from .units import (
    SENTENCE_ORDER,
    is_technical_record,
    sentence_key,
    sentence_positions,
)

__all__ = [
    "EVALUATION_DEFINITION",
    "ALIGNMENT_COLUMNS",
    "Evaluation",
    "align_predictions",
    "corpus_fingerprint",
    "evaluate_predictions",
    "lemma_comparison_key",
    "evaluation_universe",
    "model_input_records",
    "prepare_model_input",
    "sanitize_model_form",
    "postag_comparability",
    "provenance",
    "provenance_matches",
]


#: The version of the **definition** of the evaluation: universe, denominators,
#: normalisation of the keys, rule on missing predictions.
#:
#: It is not the version of the program and not the version of the model. It serves one
#: purpose only: a comparison saved with a definition different from the current one
#: cannot be reused, however well the corpus and the model match. Whoever changes one of
#: those rules must raise this number, otherwise the cache will return numbers computed
#: with another definition.
EVALUATION_DEFINITION = "1.1"
#: Definition 1.1: a tag prediction that cannot be read in the scheme counts as a
#: disagreement and stays in the denominator, instead of suspending the measure on
#: all the other words. An evaluation saved with definition 1.0 carries numbers
#: that the current code would not produce — on the tag, zero agreements on half
#: a million words — and cannot be reused.

#: The two columns that identify a token in the comparison: the canonical sentence and
#: the position inside the pre-tokenised sentence.
ALIGNMENT_COLUMNS = ("_sentenza", "_posizione")


# ---------------------------------------------------------------------------
# 1. What is given to the model
# ---------------------------------------------------------------------------

def model_input_records(active: pd.DataFrame) -> pd.DataFrame:
    """The surface tokens of the current corpus: words plus real punctuation.

    The technical records stay out, that is, those that do not correspond to a
    token present in the text: elliptic nodes, lacunae, unannotated passages,
    placeholders. Giving them to the model would mean asking it to analyse
    something that is not there.

    The punctuation marks stay in, since they are in the text and a tagger reads
    them as context. They will not enter the denominator of the lexical rates:
    that is decided by :func:`evaluate_predictions`.
    """
    if active is None or active.empty:
        return active if active is not None else pd.DataFrame()
    tecnici = is_technical_record(active)
    return active.loc[~tecnici.to_numpy()]


def sanitize_model_form(value: object) -> str:
    """The form as the model receives it: without tabs, line breaks, double spaces.

    It does not touch the letters. A model receives one line per sentence and the
    tokens separated by spaces, so a space inside a form would split it into two
    tokens and break the positional correspondence.
    """
    if value is None or (isinstance(value, float) and value != value):
        return ""
    testo = str(value).replace("\t", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(testo.split())


def prepare_model_input(active: pd.DataFrame) -> pd.DataFrame:
    """The input of the model, in reading order and with the alignment keys.

    It does three things and does them once only, because doing them twice in two
    places is how two counts of the same thing come to diverge:

    1. removes the technical records, with :func:`model_input_records`;
    2. removes the records whose form is empty after cleaning, which are not a
       token to give to a model;
    3. puts them in canonical reading order and adds ``_sentenza`` and
       ``_posizione``, which are the two columns with which the prediction will
       return to its own record.
    """
    superficie = model_input_records(active)
    if superficie is None or superficie.empty:
        return pd.DataFrame()
    forme = superficie["form"].map(sanitize_model_form)
    superficie = superficie.loc[forme.ne("")].sort_values(list(SENTENCE_ORDER))
    superficie = superficie.reset_index(drop=True)
    superficie["_model_form"] = superficie["form"].map(sanitize_model_form)
    superficie["_sentenza"] = sentence_key(superficie)
    superficie["_posizione"] = sentence_positions(superficie)
    return superficie


def evaluation_universe(words: pd.DataFrame, surface: pd.DataFrame) -> pd.DataFrame:
    """The words on which the measure is made, with the alignment keys of the surface.

    The universe of the evaluation is the ``words``; the alignment keys, however,
    count the positions **in the sentence given to the model**, punctuation
    included, because that is the sentence the model has seen. The two meet here:
    the rows of the surface that are also words are taken.
    """
    if surface is None or surface.empty or words is None or words.empty:
        return pd.DataFrame()
    chiavi = set(zip(sentence_key(words).to_numpy(),
                     pd.to_numeric(words["token_index"], errors="coerce")
                     .fillna(-1).astype("int64").to_numpy()))
    ordine = pd.to_numeric(surface["token_index"], errors="coerce").fillna(-1).astype("int64")
    e_parola = [(k, o) in chiavi for k, o in zip(surface["_sentenza"].to_numpy(),
                                                 ordine.to_numpy())]
    return surface.loc[pd.Series(e_parola, index=surface.index)]


def corpus_fingerprint(surface: pd.DataFrame) -> str:
    """The fingerprint of what the model actually received.

    Canonical sentence, position and form in NFC: it changes if a token changes, if
    their order changes or if the filter that decided which records pass changes. Two
    comparisons with the same fingerprint have read the same text.
    """
    if surface is None or surface.empty:
        return "0" * 16
    ordinato = surface.sort_values(list(SENTENCE_ORDER))
    chiavi = sentence_key(ordinato).to_numpy()
    forme = ordinato["form"].astype("string").fillna("").map(nfc).to_numpy()
    digest = hashlib.sha256()
    for chiave, forma in zip(chiavi, forme):
        digest.update(f"{chiave}\x00{forma}\n".encode("utf-8"))
    return digest.hexdigest()[:16]


# ---------------------------------------------------------------------------
# 2. The alignment
# ---------------------------------------------------------------------------

def align_predictions(
    reference: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the predictions to the reference records, by sentence and position.

    It does not go through the form. The model receives the sentence already tokenised
    and returns one analysis per token, so the correspondence is positional by
    construction; using the form as key means silently losing the tokens in which a
    difference of encoding breaks equality.

    The records without a prediction stay, with lemma and tag absent: it is
    :func:`evaluate_predictions` that decides what to do with them, and the decision is
    that they count as disagreements.
    """
    colonne = list(ALIGNMENT_COLUMNS)
    if reference is None or reference.empty:
        return pd.DataFrame()
    base = reference.copy()
    if predictions is None or predictions.empty:
        base["lemma_modello"] = pd.NA
        base["postag_modello"] = pd.NA
        return base
    mancanti = [c for c in colonne if c not in predictions.columns]
    if mancanti:
        raise ValueError(
            "the predictions do not carry the alignment columns "
            f"{mancanti}: without them the comparison would go back to matching "
            "on the form, which is the defect this module exists to remove")
    magre = predictions[colonne + ["lemma", "postag"]].rename(
        columns={"lemma": "lemma_modello", "postag": "postag_modello"})
    return base.merge(magre, on=colonne, how="left", validate="one_to_one")


# ---------------------------------------------------------------------------
# 3. The comparison keys
# ---------------------------------------------------------------------------

def lemma_comparison_key(value: object) -> str:
    """The key with which two lemmas are compared: NFC, without the numbering.

    The two normalisations apply to both sides. ``λέγω3`` in the corpus and ``λέγω`` in
    the model are the same lexical choice, and the digit is metadata of the tool inside
    the string.

    The map of canonical variants is not applied: ``νοῦς`` and ``νόος`` are two
    different lemmas, and if the model chooses one where the corpus chooses the other,
    that is a real disagreement, which one wants to see.
    """
    return without_lemma_numbering(nfc(value))


# ---------------------------------------------------------------------------
# 4. The guard on the morphological tag
# ---------------------------------------------------------------------------

def _tag_ha_forma_agdt(tag: str) -> bool:
    """The tag has the AGDT positional form: nine characters, each from its own inventory.

    A single function, because the same question is asked at two points — the verdict of
    comparability and the comparison proper — and two copies of the same test are two
    tests that sooner or later diverge.
    """
    if not isinstance(tag, str) or len(tag) != TAG_LENGTH:
        return False
    return all(carattere in VALID_CHARACTERS.get(posizione, set()) | {"-"}
               for posizione, carattere in enumerate(tag))


def _ha_forma_agdt(tags: pd.Series) -> pd.Series:
    """:func:`_tag_ha_forma_agdt` on a column, once per distinct value."""
    valori = pd.Series(tags).astype("string").fillna("")
    return pd.Series(map_unique(valori, _tag_ha_forma_agdt).to_numpy(dtype=bool),
                     index=valori.index)


def postag_comparability(tags: pd.Series) -> dict[str, Any]:
    """Are the labels of the model comparable with the AGDT ones?

    An AGDT positional tag has nine characters, each taken from an inventory
    declared for its position. A Universal Dependencies UPOS is a word such as
    ``NOUN``. Comparing them with ``==`` would give zero agreement by
    construction, and that would be a worse number than no number.

    It returns a verdict and the profile on which it was given:

    ``compatibile``    every non-empty label has the AGDT shape
    ``misto``          some do and some do not
    ``incompatibile``  none does

    **Only ``incompatibile`` stops the metric**, and it stops it because there is
    nothing to measure: if no label is interpretable, the field returned belongs
    to another tagset and comparing it with ``==`` would give zero agreement by
    construction — a worse number than no number. No conversion is built, which
    would be a methodological choice disguised as a technical detail.

    ``misto`` **does not** stop anything. A stricter rule would let a few labels
    cancel the whole measure: UDPipe returns AGDT positional labels on all of
    Gorman except three — ``v-sagamn-`` twice and ``v--pnd---`` once — and those
    three would be enough to annul the measure on the other 548,909. That would be
    a decision taken on the corpus for a defect of a single token. A prediction
    that cannot be read is a wrong prediction, and must be counted as such: the
    place where it ends up is the disagreement, not the suppression of the whole
    measure.
    """
    valori = pd.Series(tags).astype("string").fillna("")
    valori = valori[valori.str.strip() != ""]
    if valori.empty:
        return {"verdetto": "incompatibile", "motivo": "no tag returned",
                "totale": 0, "forma_agdt": 0, "forme_frequenti": []}

    ha_la_forma = _tag_ha_forma_agdt
    distinte = valori.unique()
    buone = {tag for tag in distinte if ha_la_forma(tag)}
    malformate_distinte = sorted(set(distinte) - buone)
    quante = int(valori.isin(list(buone)).sum())
    profilo = Counter(len(tag) for tag in valori).most_common(4)

    if quante == len(valori):
        verdetto, motivo = "compatibile", ""
    elif quante == 0:
        verdetto = "incompatibile"
        motivo = ("no tag has the nine-character positional AGDT form; the "
                  "returned field belongs to another tagset")
    else:
        verdetto = "misto"
        motivo = (f"{len(valori) - quante} tags out of {len(valori)} do not have "
                  "the positional AGDT form")
    return {"verdetto": verdetto, "motivo": motivo, "totale": int(len(valori)),
            "forma_agdt": quante,
            "malformate": int(len(valori)) - quante,
            # The malformed labels are listed: they are few by definition — if they were
            # many the verdict would be “incompatibile” — and whoever reads a report
            # must be able to go and see which they are.
            "malformate_distinte": [
                {"etichetta": tag, "occorrenze": int((valori == tag).sum())}
                for tag in malformate_distinte[:20]],
            "forme_frequenti": [{"lunghezza": l, "occorrenze": n} for l, n in profilo]}


# ---------------------------------------------------------------------------
# 5. The evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Metrica:
    """A rate of agreement, with everything that is needed to read it."""

    nome: str
    denominatore: str
    eleggibili: int
    con_previsione: int
    accordi: int
    disaccordi: int
    esclusi: dict[str, int] = field(default_factory=dict)
    sospesa: str = ""
    #: Predictions produced by the model that cannot be read. They stay in the
    #: denominator and among the disagreements, and are counted separately so that
    #: whoever reads the metric can know how many they are.
    previsioni_malformate: int = 0

    @property
    def copertura(self) -> float:
        return 100.0 * self.con_previsione / self.eleggibili if self.eleggibili else 0.0

    @property
    def quota(self) -> float:
        return 100.0 * self.accordi / self.eleggibili if self.eleggibili else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome,
            "denominatore": self.denominatore,
            "eleggibili": self.eleggibili,
            "con_previsione": self.con_previsione,
            "accordi": self.accordi,
            "disaccordi": self.disaccordi,
            "copertura": round(self.copertura, 2),
            "quota": round(self.quota, 2),
            "esclusi": dict(self.esclusi),
            "sospesa": self.sospesa,
            "previsioni_malformate": self.previsioni_malformate,
            "previsioni_valide": self.con_previsione - self.previsioni_malformate,
        }


@dataclass(frozen=True)
class Evaluation:
    """The comparison made, with its denominators and its provenance."""

    modello: str
    lemma: Metrica
    postag: Metrica
    comparabilita_postag: dict[str, Any]
    universo: str
    parole: int
    tabella: pd.DataFrame

    def as_dict(self) -> dict[str, Any]:
        return {
            "modello": self.modello,
            "universo": self.universo,
            "parole": self.parole,
            "lemma": self.lemma.as_dict(),
            "postag": self.postag.as_dict(),
            "comparabilita_postag": dict(self.comparabilita_postag),
        }


def evaluate_predictions(
    words: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    modello: str,
) -> Evaluation:
    """Compare the annotation of the corpus with that of the model, on the words.

    *words* is :attr:`units.Units.words`: punctuation served the model as context
    and is not here, because a rate of agreement on lemmas cannot have a
    punctuation mark in the denominator.

    Every metric declares its own denominator by name and reports separately how
    many tokens left it and for what reason. An eligible token for which the model
    produced nothing stays in the denominator and counts as a disagreement; how
    many they are can be read in the coverage.
    """
    allineato = align_predictions(words, predictions)
    if allineato.empty:
        vuota = Metrica("", "", 0, 0, 0, 0)
        return Evaluation(modello, vuota, vuota, {"verdetto": "incompatibile"},
                          "words", 0, pd.DataFrame())

    # ── lemma ──────────────────────────────────────────────────────────────
    lemma_corpus = allineato["lemma"].astype("string").fillna("").map(lemma_comparison_key)
    lemma_modello = allineato["lemma_modello"].astype("string")
    ha_previsione_lemma = lemma_modello.notna() & (lemma_modello.fillna("").str.strip() != "")
    lemma_previsto = lemma_modello.fillna("").map(lemma_comparison_key)

    eleggibile_lemma = lemma_corpus.str.strip() != ""
    esclusi_lemma = {"reference lemma missing": int((~eleggibile_lemma).sum())}
    accordo_lemma = eleggibile_lemma & ha_previsione_lemma & (lemma_corpus == lemma_previsto)

    metrica_lemma = Metrica(
        nome="lemma",
        denominatore="words with a reference lemma present",
        eleggibili=int(eleggibile_lemma.sum()),
        con_previsione=int((eleggibile_lemma & ha_previsione_lemma).sum()),
        accordi=int(accordo_lemma.sum()),
        disaccordi=int((eleggibile_lemma & ~accordo_lemma).sum()),
        esclusi={k: v for k, v in esclusi_lemma.items() if v},
    )

    # ── morphological label ────────────────────────────────────────────────
    tag_corpus = allineato["postag"].astype("string").fillna("")
    tag_modello = allineato["postag_modello"].astype("string")
    ha_previsione_tag = tag_modello.notna() & (tag_modello.fillna("").str.strip() != "")

    presente = tag_corpus.str.strip() != ""
    giusta_lunghezza = tag_corpus.str.len() == TAG_LENGTH
    eleggibile_tag = presente & giusta_lunghezza
    esclusi_tag = {
        "reference tag missing": int((~presente).sum()),
        f"reference tag of a length other than {TAG_LENGTH}":
            int((presente & ~giusta_lunghezza).sum()),
    }

    comparabilita = postag_comparability(tag_modello.fillna(""))
    if comparabilita["verdetto"] == "incompatibile":
        # No prediction is interpretable: the field returned belongs to another tagset
        # and there is nothing to compare. It is the only case in which the measure
        # stops, and it stops for lack of an object, not because of a threshold.
        metrica_tag = Metrica(
            nome="morphological tag",
            denominatore=f"words with a reference tag of {TAG_LENGTH} characters",
            eleggibili=int(eleggibile_tag.sum()),
            con_previsione=0, accordi=0, disaccordi=0,
            esclusi={k: v for k, v in esclusi_tag.items() if v},
            sospesa=comparabilita["motivo"],
        )
        accordo_tag = pd.Series(False, index=allineato.index)
    else:
        # A prediction that cannot be read is a wrong prediction. It does not enter
        # among the agreements, it stays in the denominator, and it is counted
        # separately so that whoever reads can see it: suppressing the measure because
        # of it would answer a defect of the token with a decision on the corpus.
        ben_formata = _ha_forma_agdt(tag_modello.fillna(""))
        accordo_tag = (eleggibile_tag & ha_previsione_tag & ben_formata
                       & (tag_corpus == tag_modello.fillna("")))
        malformate = int((eleggibile_tag & ha_previsione_tag & ~ben_formata).sum())
        esclusi_tag_finale = {k: v for k, v in esclusi_tag.items() if v}
        metrica_tag = Metrica(
            nome="morphological tag",
            denominatore=f"words with a reference tag of {TAG_LENGTH} characters",
            eleggibili=int(eleggibile_tag.sum()),
            con_previsione=int((eleggibile_tag & ha_previsione_tag).sum()),
            accordi=int(accordo_tag.sum()),
            disaccordi=int((eleggibile_tag & ~accordo_tag).sum()),
            esclusi=esclusi_tag_finale,
            previsioni_malformate=malformate,
        )

    tabella = allineato.copy()
    tabella["lemma_normalizzato"] = lemma_corpus
    tabella["lemma_modello_normalizzato"] = lemma_previsto
    tabella["accordo_lemma"] = accordo_lemma
    tabella["accordo_postag"] = accordo_tag
    tabella["eleggibile_lemma"] = eleggibile_lemma
    tabella["eleggibile_postag"] = eleggibile_tag

    return Evaluation(
        modello=modello,
        lemma=metrica_lemma,
        postag=metrica_tag,
        comparabilita_postag=comparabilita,
        universo="words",
        parole=int(len(allineato)),
        tabella=tabella,
    )


# ---------------------------------------------------------------------------
# 6. Provenance and reuse
# ---------------------------------------------------------------------------

#: The fields that must match for a saved comparison to apply to the current run. The
#: date is not among them: a result does not expire, it becomes inapplicable.
CACHE_FIELDS = (
    "impronta_corpus", "gcp_version", "filtri", "unita",
    "modello", "modello_versione", "risorse_modello", "definizione_valutazione",
)


def provenance(
    *,
    surface: pd.DataFrame,
    gcp_version: str,
    filtri: dict,
    modello: str,
    modello_versione: str,
    risorse_modello: str,
    run_id: str = "",
    corpus: str = "",
) -> dict[str, Any]:
    """Everything that is needed to know what a comparison refers to."""
    return {
        "impronta_corpus": corpus_fingerprint(surface),
        "record_dati_al_modello": int(len(surface)) if surface is not None else 0,
        "gcp_version": gcp_version,
        "filtri": dict(sorted(filtri.items())),
        "unita": "input: active records minus the technical ones; evaluation: words",
        "modello": modello,
        "modello_versione": modello_versione,
        "risorse_modello": risorse_modello,
        "definizione_valutazione": EVALUATION_DEFINITION,
        "run_id": run_id,
        "corpus": corpus,
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def provenance_matches(salvata: dict | None, corrente: dict) -> tuple[bool, str]:
    """Does the saved comparison apply to the current run?

    It does if corpus, program version, filters, units, model, model version, its
    resources and definition of the evaluation all match. If even one changes, the saved
    result was computed on something else and must be redone.
    """
    if not salvata:
        return False, "no comparison saved for this run"
    for campo in CACHE_FIELDS:
        if salvata.get(campo) != corrente.get(campo):
            return False, (f"“{campo}” has changed: it was {salvata.get(campo)!r}, "
                           f"it is now {corrente.get(campo)!r}")
    return True, ""
