"""Statistics a classicist recognises.

Everything here is computed from the five columns a treebank already has —
``form``, ``lemma``, ``postag``, ``relation``, ``head`` — plus the author and
date metadata. No external resource, no model, no training.

The organising idea is that a corpus tool should answer the questions a
philologist actually asks, in the units they already think in. "How much
Herodotus is there" is a token count; "does this author write nominally or
verbally" is a noun-to-verb ratio; "is this Atticism" is an optative index;
"how convoluted is this period" is tree depth and mean dependency distance;
"what is hyperbaton, measured" is the non-projectivity rate.

Three principles run through the module, each a response to a limitation of the
tools it means to complement:

*Nothing is reported raw when raw is misleading.* Every frequency comes with a
rate per ten thousand tokens, because Polybius leads every raw count in the
Gorman corpus for the sole reason that there is more Polybius.

*Concentration is reported next to frequency.* A word can be frequent because
Greek uses it or because one passage repeats it; Gries's DP and the range tell
the two apart, and raw counts cannot.

*Length-sensitive measures are labelled as such.* Type/token ratio is offered
because everyone expects it, next to Yule's K, MATTR and Maas's a², which can
honestly compare a fragment of Sappho with the whole of Polybius.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Iterable

import numpy as np
import pandas as pd

from .agdt_schema import (
    CASE_SLOT,
    DEGREE_SLOT,
    FINITE_MOODS,
    MOOD_SLOT,
    NUMBER_SLOT,
    POS_SLOT,
    TAG_LENGTH,
    base_relation,
    describe_value,
)
from . import resources
from .fastmap import map_unique
from .syntax import build_head_index
from .normalise import disambiguate_spellings, nfc, without_lemma_numbering
from .units import sentence_key

PUNCTUATION_POS = "u"


#: Groupings whose natural order is not "biggest first" but chronological.
#: Sorting a diachronic index by sub-corpus size is not a cosmetic mistake: it
#: puts the Hellenistic column after the Imperial one whenever there happens to
#: be more Imperial text, and a reader who scans left to right then reads a
#: sequence of numbers as a trend when it is not one.  Two lines here prevent a
#: whole class of misreadings downstream, in every table and every chart.
_ORDERED_GROUPS = {"periodo", "secolo"}


def _order_groups(table: pd.DataFrame, group: str) -> pd.DataFrame:
    """Chronological order for period/century groupings, size order otherwise."""
    if table is None or table.empty or group not in _ORDERED_GROUPS \
            or group not in table.columns:
        return table
    if group == "periodo":
        from .corpus_metadata import period_sort_key
        key = table[group].map(period_sort_key)
    else:
        key = table[group].map(_century_sort_key)
    return (table.assign(_order=key)
            .sort_values("_order", kind="stable")
            .drop(columns="_order")
            .reset_index(drop=True))


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
          "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
_CENTURY_RE = re.compile(r"\b([IVX]+)\b")


def _century_sort_key(century: object) -> float:
    """'V a.C.' before 'I a.C.' before 'I d.C.'; unknown values last.

    Straddling labels ('V-IV a.C.', 'I-II d.C.') are placed by the midpoint of
    the two centuries they name, so a range sits between its neighbours instead
    of being dumped at the end — which is where a naive parse puts it, and where
    a reader would never look for it.
    """
    text = str(century).strip()
    if not text or text.lower() in {"nan", "none", "sconosciuto", "unknown"}:
        return float("inf")
    numbers = [_ROMAN[m] for m in _CENTURY_RE.findall(text.upper()) if m in _ROMAN]
    if not numbers:
        digits = re.findall(r"\d+", text)
        if not digits:
            return float("inf")
        numbers = [int(d) for d in digits]
    value = sum(numbers) / len(numbers)
    before_christ = any(marker in text for marker in ("a.C", "a. C", "BC", "BCE"))
    return -value if before_christ else value


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _slot(tokens: pd.DataFrame, index: int) -> pd.Series:
    """One position of the tag, as a column, blank where the tag is malformed.

    Answered once per distinct tag and gathered back: the corpus spells 625,176
    tokens with 1,185 distinct tags, and this is called some thirty times in a
    full statistics report — six times in ``slot_distribution`` alone — so
    slicing and masking the whole column each time was the single most repeated
    piece of work in the module, 0.10 s a call against 0.01 s.
    """
    tags = tokens["postag"].astype("string").fillna("")
    codes, uniques = pd.factorize(tags, use_na_sentinel=False)
    characters = [tag[index] if len(tag) == TAG_LENGTH else ""
                  for tag in np.asarray(uniques, dtype=object)]
    return pd.Series(pd.array(characters, dtype="string").take(codes),
                     index=tokens.index, name=tags.name)


def _content(tokens: pd.DataFrame) -> pd.DataFrame:
    """The words of the text, according to the one definition the program has.

    Delegates to :func:`units.is_word`. A looser rule (dropping only the label ``u``
    and the forms ``[n]``) would let through 58 punctuation marks in Gorman and 26
    in Pedalion: the full stops, colons, commas and dashes that carry an empty or
    malformed label but a punctuation relation. They would end up in the lexical
    counts and in the frequency lists as if they were words.

    Two definitions of the same thing always diverge sooner or later, so there is
    only one.
    """
    if tokens.empty:
        return tokens
    from .units import is_word
    return tokens[is_word(tokens).to_numpy()]


# ---------------------------------------------------------------------------
# Stopword profiles
# ---------------------------------------------------------------------------

#: POS to exclude in the “function words” profile: article (l), particle (g), conjunction
#: (c), preposition (r), punctuation (u), elliptic node (x), plus the two local
#: extensions that the KU Leuven corpora use instead of the AGDT categories: “b”, with
#: which Pedalion writes coordinators, and “z”, which marks non-lexical records. Without
#: these two, on Pedalion the filter would leave καί at the top of the list.
FUNCTIONAL_POS: frozenset[str] = frozenset("lgcruxbz")

#: POS to keep in the “content words only” profile: noun (n), adjective (a), verb (v),
#: adverb (d), numeral (m).
CONTENT_POS: frozenset[str] = frozenset("navdm")

#: The grammatical lemmas of Greek, in a single list.
#:
#: It is the only place in the program where a word is declared grammatical, and
#: it exists because the filter by part of speech is not enough on its own: none
#: of the corpora examined uses the “g” that the scheme reserves for particles,
#: Gorman marks δέ, μέν, γάρ and οὐ as adverbs, and Pedalion marks them “b”. A
#: filter that looked only at the tag would leave καί at the top of every
#: frequency list, which is the defect the filter exists to remove.
#:
#: The list is open: lemmas can be added and removed from the Statistics page, and
#: exported and re-imported. It holds the lemmas that the “Lexical words only”
#: view excludes, in addition to the morphological categories. The list itself is
#: not in this file: it lives in ``data/liste``, versioned and with its rationale
#: beside it, because it decides the lexical density, which is a number that the
#: article publishes. Whoever reads it must be able to inspect it and dispute it
#: entry by entry, and a ``frozenset`` inside a Python file does not allow that.
GRAMMATICAL_LEMMAS = resources.entries("lemmi-grammaticali")


#: The list's original name, kept because the tests import it.
CORE_STOP_LEMMAS: frozenset[str] = GRAMMATICAL_LEMMAS

#: The four profiles, under the name that appears in the menu of the Statistics page. The
#: strings are also the keys under which a profile travels in the cache: they are
#: identifiers, and the interface translates them for display.
STOPWORD_PROFILES: tuple[str, ...] = (
    "nessun filtro",
    "senza parole funzionali",
    "solo parole di contenuto",
    "lista personalizzata",
)


def _normalize_lemma(value: str) -> str:
    """NFC + casefold, for comparisons with the stop lists."""
    return unicodedata.normalize("NFC", value.casefold()).strip()


#: A lemma that is not a word: only hyphens, underscores, digits or punctuation. These
#: are placeholders and conversion leftovers, and they must not sit at the top of a
#: frequency list however the filter is set.
_LEMMA_NON_PAROLA = re.compile(r"^[\W\d_]+$", re.UNICODE)


def _lemma_non_e_una_parola(tokens: pd.DataFrame) -> pd.Series:
    """The check is made once per distinct lemma, not once per token.

    The distinct lemmas of a treebank are an order of magnitude fewer than the records
    that carry them, and the answer is the same for all the occurrences of the same
    lemma: asking once per value instead of once per row gives the same answer with a
    fraction of the work.
    """
    if "lemma" not in tokens.columns:
        return pd.Series(False, index=tokens.index)
    valori = tokens["lemma"].astype("string").fillna("")
    esito = map_unique(valori, lambda v: bool(_LEMMA_NON_PAROLA.match(v)) if v else True)
    return pd.Series(esito.to_numpy(dtype=bool), index=tokens.index)


def _lemma_in(tokens: pd.DataFrame, elenco: frozenset[str]) -> pd.Series:
    """Which tokens carry one of the lemmas of the list, ignoring accents and capitals.

    It serves as a safety net under the filter by part of speech, and it is not a
    luxury: the two corpora do not write the particle with the “g” that the scheme
    provides for. Gorman marks δέ, μέν, γάρ and οὐ as adverbs, Pedalion marks them “b”.
    A filter that looked only at the tag would leave them at the top of the frequency
    list, which is exactly the defect the filter exists to remove.
    """
    if "lemma" not in tokens.columns:
        return pd.Series(False, index=tokens.index)
    riferimento = frozenset(_normalize_lemma(v) for v in elenco)
    valori = tokens["lemma"].astype("string").fillna("")
    esito = map_unique(valori, lambda v: _normalize_lemma(v) in riferimento)
    return pd.Series(esito.to_numpy(dtype=bool), index=tokens.index)


def apply_stopword_profile(
    tokens: pd.DataFrame,
    profile: str,
    *,
    extra: "Iterable[str] | None" = None,
    remove: "Iterable[str] | None" = None,
) -> pd.DataFrame:
    """The subset of tokens that the declared profile lets through.

    The four profiles are those of :data:`STOPWORD_PROFILES`:

    * ``"no filter"`` — no exclusion beyond those of ``_content``;
    * ``"without function words"`` — articles, prepositions, conjunctions,
      particles, pronouns, punctuation, elliptic nodes, lacuna markers and every
      other non-lexical record are removed, by part of speech and by lemma;
    * ``"content words only"`` — nouns, adjectives, verbs and lexical adverbs
      remain, minus the grammatical lemmas;
    * ``"custom list"`` — the grammatical list with the additions and removals of
      the user, without a filter by part of speech.

    ``extra`` and ``remove`` modify the list without touching the constant: they
    are the lemmas that the user has added and those that the user has removed.
    """
    if tokens.empty or profile == "nessun filtro":
        return tokens

    elenco = stopword_list(extra=extra, remove=remove)
    funzionali = _lemma_in(tokens, elenco)
    non_parole = _lemma_non_e_una_parola(tokens)

    if profile == "senza parole funzionali":
        pos = _slot(tokens, POS_SLOT)
        return tokens[~(pos.isin(FUNCTIONAL_POS) | funzionali | non_parole)].copy()

    if profile == "solo parole di contenuto":
        pos = _slot(tokens, POS_SLOT)
        return tokens[pos.isin(CONTENT_POS) & ~funzionali & ~non_parole].copy()

    if profile == "lista personalizzata":
        return tokens[~(funzionali | non_parole)].copy()

    return tokens                      # unknown profile: no filter


def stopword_list(
    *,
    extra: "Iterable[str] | None" = None,
    remove: "Iterable[str] | None" = None,
) -> frozenset[str]:
    """The grammatical list with the user's additions and removals."""
    elenco = set(GRAMMATICAL_LEMMAS)
    elenco |= {v.strip() for v in (extra or []) if v and v.strip()}
    togliere = {_normalize_lemma(v) for v in (remove or []) if v and v.strip()}
    if togliere:
        elenco = {v for v in elenco if _normalize_lemma(v) not in togliere}
    return frozenset(elenco)


def stopword_profile_report(
    tokens: pd.DataFrame,
    profile: str,
    *,
    extra: "Iterable[str] | None" = None,
    remove: "Iterable[str] | None" = None,
    top: int = 60,
    rimasti: pd.DataFrame | None = None,
) -> dict[str, object]:
    """How many lemmas the profile removed, which ones, and for what reason.

    ``rimasti`` (the remaining tokens) is the result of :func:`apply_stopword_profile`
    when the caller has already computed it: redoing it here would mean filtering the
    same corpus twice to write the same number.

    A filtered frequency list is not “the actual frequency”: it is the frequency of the
    words that the profile lets through, and the reader must be able to see what was
    left out and why. There are three reasons, and they exclude one another in the order
    in which they are tested: the part of speech, the list of grammatical lemmas, the
    fact that the lemma is not a word.
    """
    vuoto = {"profilo": profile, "token_prima": 0, "token_dopo": 0,
             "token_esclusi": 0, "percentuale_esclusa": 0.0,
             "lemmi_esclusi": pd.DataFrame()}
    if tokens is None or tokens.empty:
        return vuoto

    prima = len(tokens)
    restano = (rimasti if rimasti is not None
               else apply_stopword_profile(tokens, profile, extra=extra, remove=remove))
    dopo = len(restano)
    if profile == "nessun filtro" or dopo == prima:
        vuoto.update({"token_prima": prima, "token_dopo": dopo})
        return vuoto

    elenco = stopword_list(extra=extra, remove=remove)
    fuori = tokens.loc[~tokens.index.isin(restano.index)].copy()
    pos = _slot(fuori, POS_SLOT)
    per_lemma = _lemma_in(fuori, elenco)
    non_parola = _lemma_non_e_una_parola(fuori)
    if profile == "solo parole di contenuto":
        per_pos = ~pos.isin(CONTENT_POS)
    else:
        per_pos = pos.isin(FUNCTIONAL_POS)
    ragione = pd.Series("non è una parola", index=fuori.index)
    ragione[per_lemma] = "elenco dei lemmi grammaticali"
    ragione[per_pos & ~per_lemma] = "parte del discorso"
    ragione[non_parola & ~per_pos & ~per_lemma] = "non è una parola"
    fuori["ragione"] = ragione

    tabella = (fuori.groupby([fuori["lemma"].astype("string").fillna(""), "ragione"],
                             dropna=False, sort=False)
               .size().reset_index(name="occorrenze"))
    tabella.columns = ["lemma", "ragione", "occorrenze"]
    tabella = tabella.sort_values("occorrenze", ascending=False).head(top).reset_index(drop=True)
    return {"profilo": profile, "token_prima": prima, "token_dopo": dopo,
            "token_esclusi": prima - dopo,
            "percentuale_esclusa": round(100.0 * (prima - dopo) / prima, 1) if prima else 0.0,
            "lemmi_esclusi": tabella}


def _nfc(values: pd.Series) -> pd.Series:
    """Composed copy of a text column.

    GLAUx distributes its XML in Unicode NFD: the accent is a separate
    character after the vowel. Every closed list in this program is written
    NFC, so a plain ``isin`` against those lists finds nothing at all in a
    decomposed corpus and the counts come out zero, silently. Comparisons go
    through here; what is stored and later written back is untouched.
    """
    text = values.astype("string").fillna("")
    return map_unique(text, lambda value: unicodedata.normalize("NFC", value)
                      if isinstance(value, str) else value).astype("string").fillna("")
#: The lemmas counted as particles in the morphological statistic. This list too
#: is a data resource. No diagnostic check uses it: the relation-rarity check that
#: restricts the profile to particles covers all the parts of speech.
PARTICLE_LEMMAS = resources.entries("lemmi-particella")



def _safe_ratio(numerator: float, denominator: float, digits: int = 3) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), digits)


# ---------------------------------------------------------------------------
# 1. Basic counts
# ---------------------------------------------------------------------------

def basic_counts(tokens: pd.DataFrame) -> dict[str, object]:
    """The header figures: what is in this corpus, in one glance.

    A note on what "sentence length" means here, because the figure is one a
    reader will want to quote. A sentence is a group of records sharing
    ``(source_file, document_id, sentence_index)``, and its length is the
    number of records in it that :func:`_content` lets through — that is, all
    of them except punctuation (tag position 1 = ``u``) and the empty ``[0]``
    placeholders. So the unit is *tokens per sentence, punctuation and empty
    placeholders excluded*, and the interface says so in as many words.
    """
    if tokens is None or tokens.empty:
        return {}
    words = _content(tokens)
    sentence_sizes = words.groupby(
        ["source_file", "document_id", "sentence_index"], sort=False).size()
    return {
        "documenti": int(tokens["document_id"].nunique()),
        "frasi": int(tokens[["document_id", "sentence_index"]].drop_duplicates().shape[0]),
        "token (tutto)": int(len(tokens)),
        "token (parole)": int(len(words)),
        "forme distinte": int(words["form"].dropna().nunique()),
        "lemmi distinti": int(words["lemma"].dropna().nunique()),
        "lemmi mancanti": int(words["lemma"].isna().sum()),
        "postag mancanti": int(words["postag"].isna().sum()),
        "lunghezza media frase": round(float(sentence_sizes.mean()), 2) if len(sentence_sizes) else 0.0,
        "lunghezza mediana frase": float(sentence_sizes.median()) if len(sentence_sizes) else 0.0,
        "frase più lunga": int(sentence_sizes.max()) if len(sentence_sizes) else 0,
    }


def counts_by_group(tokens: pd.DataFrame, group: str) -> pd.DataFrame:
    """Basic counts broken down by author, work, genre, dialect or period."""
    if tokens is None or tokens.empty or group not in tokens.columns:
        return pd.DataFrame()
    words = _content(tokens)
    if words.empty:
        return pd.DataFrame()

    grouped = words.groupby(group, dropna=False, sort=False)
    table = grouped.agg(
        documenti=("document_id", "nunique"),
        frasi=("sentence_index", "nunique"),
        token=("form", "size"),
        forme=("form", "nunique"),
        lemmi=("lemma", "nunique"),
    ).reset_index()

    # The two columns below are named for what they compute, because a name that
    # meant one thing here and another thing one table away is the sort of
    # collision a reader has no way of seeing.  «lunghezza media frase (parole)»
    # counts words — punctuation already dropped by ``_content`` — whereas the
    # per-sentence table that ``tree_metrics`` builds counts *all* tokens and
    # filters nothing.  «token per lemma» is token ÷ lemmi, that is the average
    # number of occurrences per lemma, and has nothing to do with the lexical
    # density of ``morphological_profile`` (content words ÷ all words).
    sentence_sizes = words.groupby(
        [group, "document_id", "sentence_index"], dropna=False, sort=False).size()
    mean_length = (sentence_sizes.groupby(level=0).mean().round(2)
                   .rename("lunghezza media frase (parole)"))
    table = table.merge(mean_length.reset_index(), on=group, how="left")

    table["TTR (lemmi)"] = (table["lemmi"] / table["token"]).round(4)
    table["token per lemma"] = (table["token"] / table["lemmi"]).round(2)
    return _order_groups(
        table.sort_values("token", ascending=False).reset_index(drop=True), group)


# ---------------------------------------------------------------------------
# 2. Frequency lists
# ---------------------------------------------------------------------------

def frequency_list(
    tokens: pd.DataFrame,
    field: str = "lemma",
    *,
    top: int | None = None,
    min_count: int = 1,
    group: str | None = None,
) -> pd.DataFrame:
    """Frequency list, normalised per ten thousand tokens.

    The normalised column is not decoration. Without it, "the most frequent
    lemma in Herodotus" and "the most frequent lemma in the corpus" cannot be
    put on the same page.
    """
    if tokens is None or tokens.empty or field not in tokens.columns:
        return pd.DataFrame()
    words = _content(tokens)
    words = words[words[field].notna()]
    if words.empty:
        return pd.DataFrame()

    if group and group in words.columns:
        table = (words.groupby([group, field], sort=False).size()
                 .reset_index(name="occorrenze"))
        totals = words.groupby(group, sort=False).size().rename("token_gruppo")
        table = table.merge(totals.reset_index(), on=group, how="left")
        table["per 10.000"] = (table["occorrenze"] / table["token_gruppo"] * 10_000).round(2)
        table = table.sort_values(["occorrenze"], ascending=False)
    else:
        counts = words[field].value_counts()
        table = counts.reset_index()
        table.columns = [field, "occorrenze"]
        total = int(counts.sum())
        table["per 10.000"] = (table["occorrenze"] / total * 10_000).round(2)
        table["%"] = (table["occorrenze"] / total * 100).round(3)
        table["% cumulativa"] = table["%"].cumsum().round(2)
        table["rango"] = np.arange(1, len(table) + 1)

    table = table[table["occorrenze"] >= min_count]
    if top:
        table = table.head(top)
    return table.reset_index(drop=True)


# 3. Lexical richness
# ---------------------------------------------------------------------------

# 4. Morphological profile
# ---------------------------------------------------------------------------

def slot_distribution(
    tokens: pd.DataFrame,
    slot_index: int,
    *,
    restrict_pos: set[str] | None = None,
    group: str | None = None,
) -> pd.DataFrame:
    """Distribution of one tag slot — cases, tenses, moods, voices, persons."""
    words = _content(tokens)
    if words.empty:
        return pd.DataFrame()
    pos = _slot(words, POS_SLOT)
    values = _slot(words, slot_index)
    mask = (values != "") & (values != "-")
    if restrict_pos:
        mask &= pos.isin(restrict_pos)
    subset = words[mask]
    if subset.empty:
        return pd.DataFrame()

    # Ten distinct characters answer for the whole column: the per-token map
    # called ``describe_value`` 1,226,435 times across the six slot tables of a
    # full report, for a dictionary lookup it could have done ten times.
    labels = map_unique(values[mask], lambda char: describe_value(slot_index, char))
    frame = pd.DataFrame({"valore": values[mask].values, "categoria": labels.values})
    if group and group in subset.columns:
        frame[group] = subset[group].values
        table = frame.groupby([group, "valore", "categoria"], sort=False).size().reset_index(name="occorrenze")
        totals = table.groupby(group)["occorrenze"].transform("sum")
        table["%"] = (table["occorrenze"] / totals * 100).round(2)
        return table.sort_values([group, "occorrenze"], ascending=[True, False]).reset_index(drop=True)

    table = frame.groupby(["valore", "categoria"], sort=False).size().reset_index(name="occorrenze")
    table["%"] = (table["occorrenze"] / table["occorrenze"].sum() * 100).round(2)
    return table.sort_values("occorrenze", ascending=False).reset_index(drop=True)


def morphological_profile(tokens: pd.DataFrame) -> dict[str, object]:
    """The handful of ratios a classicist reads first.

    Each is one number that a reader of Greek immediately understands, and each
    is chosen because it is known to move with period, genre or dialect:

    * genitive/dative — the dative recedes after the classical period, so this
      ratio climbs through time;
    * optative index — the optative disappears in the koiné and is deliberately
      revived by the atticists: on its own it separates Lucian from a papyrus;
    * participles per finite verb — the most characteristic feature of Greek
      prose, and the numerical face of the "subordinating" style;
    * article density — Homer has almost no article, Attic prose is saturated
      with it.
    """
    return _profile_of_words(_content(tokens))


def _profile_of_words(words: pd.DataFrame) -> dict[str, object]:
    """The body of :func:`morphological_profile`, for callers that have already
    dropped punctuation — ``profile_by_group`` slices one chunk per author out of
    a filtered table and then had every chunk filtered a second time."""
    if words.empty:
        return {}

    pos = _slot(words, POS_SLOT)
    case = _slot(words, CASE_SLOT)
    mood = _slot(words, MOOD_SLOT)
    number = _slot(words, NUMBER_SLOT)
    degree = _slot(words, DEGREE_SLOT)

    total = len(words)
    finite = int(mood.isin(FINITE_MOODS).sum())
    participles = int((mood == "p").sum())
    infinitives = int((mood == "n").sum())
    optatives = int((mood == "o").sum())
    subjunctives = int((mood == "s").sum())

    nouns = int((pos == "n").sum())
    verbs = int((pos == "v").sum())
    adjectives = int((pos == "a").sum())
    articles = int((pos == "l").sum())
    particles = int((pos == "g").sum())
    adverbs = int((pos == "d").sum())

    # Particles: lemma-based (see PARTICLE_LEMMAS) with the tag as a fallback
    # for corpora that do use the 'g' slot.
    lemmas = words["lemma"].astype("string").fillna("") if "lemma" in words.columns else pd.Series(dtype="string")
    particle_tokens = int(_nfc(lemmas).isin(PARTICLE_LEMMAS).sum()) if len(lemmas) else particles

    return {
        "genitivi / dativi": _safe_ratio((case == "g").sum(), (case == "d").sum()),
        "indice di ottativo": _safe_ratio(optatives, finite, 4),
        "ottativi / congiuntivi": _safe_ratio(optatives, subjunctives),
        "participi / verbi finiti": _safe_ratio(participles, finite),
        "infiniti / verbi finiti": _safe_ratio(infinitives, finite),
        "densità dell'articolo (art./sost.)": _safe_ratio(articles, nouns),
        "aggettivi / sostantivi": _safe_ratio(adjectives, nouns),
        "sostantivi / verbi": _safe_ratio(nouns, verbs),
        "densità lessicale": _safe_ratio(nouns + verbs + adjectives + adverbs, total, 4),
        "particelle per 1.000 token": _safe_ratio(particle_tokens * 1000, total, 2),
        "duali per 10.000 token": _safe_ratio((number == "d").sum() * 10_000, total, 2),
        "comparativi e superlativi / agg.+avv.":
            _safe_ratio(degree.isin({"c", "s"}).sum(), adjectives + adverbs, 4),
    }


def profile_by_group(tokens: pd.DataFrame, group: str) -> pd.DataFrame:
    """The morphological profile, one row per author (or genre, or period)."""
    words = _content(tokens)
    if words.empty or group not in words.columns:
        return pd.DataFrame()
    rows = []
    for name, chunk in words.groupby(group, dropna=False, sort=False):
        if len(chunk) < 200:      # too little text for a stable ratio
            continue
        profile = _profile_of_words(chunk)
        rows.append({group: name, "token": int(len(chunk)), **profile})
    if not rows:
        return pd.DataFrame()
    return _order_groups(
        pd.DataFrame(rows).sort_values("token", ascending=False)
        .reset_index(drop=True), group)


# 5. Syntactic profile
# ---------------------------------------------------------------------------

def relation_distribution(tokens: pd.DataFrame, group: str | None = None) -> pd.DataFrame:
    """Frequency of each syntactic function: the syntactic fingerprint."""
    if tokens is None or tokens.empty or "relation" not in tokens.columns:
        return pd.DataFrame()
    words = tokens[tokens["relation"].notna()].copy()
    # 72 distinct labels for 625,176 tokens; ``astype`` keeps the column dtype
    # the per-token map produced.
    words["_rel"] = map_unique(
        words["relation"].astype("string"), base_relation).astype("str")
    if group and group in words.columns:
        table = words.groupby([group, "_rel"], sort=False).size().reset_index(name="occorrenze")
        totals = table.groupby(group)["occorrenze"].transform("sum")
        table["%"] = (table["occorrenze"] / totals * 100).round(2)
        return table.rename(columns={"_rel": "relazione"}).sort_values(
            [group, "occorrenze"], ascending=[True, False]).reset_index(drop=True)
    table = words["_rel"].value_counts().reset_index()
    table.columns = ["relazione", "occorrenze"]
    table["%"] = (table["occorrenze"] / table["occorrenze"].sum() * 100).round(2)
    return table


def tree_metrics(tokens: pd.DataFrame, arcs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-sentence complexity: length, depth, dependency distance, hyperbaton.

    Mean dependency distance is the standard measure of processing load for a
    free-word-order language, and tree depth separates the built period of
    Isocrates from Herodotean parataxis. Both come almost free once the head
    index exists.
    """
    if tokens is None or tokens.empty:
        return pd.DataFrame()
    needed = {"token_id", "head", "sentence_index"}
    if not needed <= set(tokens.columns):
        return pd.DataFrame()

    work = tokens.reset_index(drop=True).copy()
    work["_sent"] = (work["source_file"].astype("string").fillna("") + "␟"
                     + work["document_id"].astype("string").fillna("") + "␟"
                     + work["sentence_index"].astype("string").fillna(""))
    work["_tid"] = pd.to_numeric(work["token_id"], errors="coerce")
    work["_head"] = pd.to_numeric(work["head"], errors="coerce")
    head_index = build_head_index(work).to_numpy()

    positions = pd.to_numeric(work.get("token_index"), errors="coerce").to_numpy()
    sentences = work["_sent"].to_numpy()

    # Depth level by level: the roots are at 0, and every pass settles the
    # tokens whose head already has a depth.  Dependency trees are shallow (the
    # deepest chain in the Gorman corpus is 22 links), so a couple of dozen
    # numpy passes replace 625,176 Python walks.
    #
    # A head cycle has no depth under this definition, and the memoised walk
    # below gave it whatever its guard happened to stop at.  That is not a
    # number worth reproducing in numpy, so a corpus that still has cycles —
    # check_cycles reports them as errors — takes the original scalar path.
    depth = np.full(len(work), -1, dtype="int64")
    depth[head_index < 0] = 0
    pending = np.flatnonzero(head_index >= 0)
    while pending.size:
        settled = depth[head_index[pending]] >= 0
        if not settled.any():
            break
        depth[pending[settled]] = depth[head_index[pending[settled]]] + 1
        pending = pending[~settled]

    if pending.size:
        depth = np.full(len(work), -1, dtype="int64")
        for row in range(len(work)):
            if depth[row] >= 0:
                continue
            chain: list[int] = []
            node = row
            guard = 0
            while node >= 0 and depth[node] < 0 and guard < 500:
                chain.append(node)
                node = head_index[node]
                guard += 1
            base = 0 if node < 0 else depth[node] + 1
            for offset, member in enumerate(reversed(chain)):
                depth[member] = base + offset

    distance = np.where(
        head_index >= 0,
        np.abs(positions - np.where(head_index >= 0, positions[head_index], positions)),
        np.nan,
    )

    frame = pd.DataFrame({
        "_sent": sentences,
        "document_id": work["document_id"].values,
        "sentence_index": work["sentence_index"].values,
        "sentence_id": work.get("sentence_id", pd.Series("", index=work.index)).values,
        "depth": depth,
        "distance": distance,
    })
    for column in ("autore", "opera", "genere", "periodo", "dialetto"):
        if column in work.columns:
            frame[column] = work[column].values

    aggregations = {
        "token": ("depth", "size"),
        "profondità massima": ("depth", "max"),
        "profondità media": ("depth", "mean"),
        "distanza media testa-dipendente": ("distance", "mean"),
        "distanza massima": ("distance", "max"),
    }
    grouped = frame.groupby(["_sent", "document_id", "sentence_index", "sentence_id"],
                            sort=False).agg(**aggregations).reset_index()

    if arcs is not None and not arcs.empty and "non_projective" in arcs.columns:
        projectivity = (arcs.groupby(["document_id", "sentence_index"], sort=False)["non_projective"]
                        .agg(["sum", "size"]).reset_index())
        projectivity.columns = ["document_id", "sentence_index", "archi non proiettivi", "archi"]
        grouped = grouped.merge(projectivity, on=["document_id", "sentence_index"], how="left")
        grouped["% archi non proiettivi"] = (
            grouped["archi non proiettivi"] / grouped["archi"] * 100).round(1)

    for column in ("autore", "opera", "genere", "periodo", "dialetto"):
        if column in frame.columns:
            first = frame.groupby("_sent", sort=False)[column].first().rename(column)
            grouped = grouped.merge(first.reset_index(), on="_sent", how="left")

    grouped["profondità media"] = grouped["profondità media"].round(2)
    grouped["distanza media testa-dipendente"] = grouped["distanza media testa-dipendente"].round(2)
    return grouped.drop(columns=["_sent"])


# 6. The syntactic summary
# ---------------------------------------------------------------------------

def syntax_summary(tokens: pd.DataFrame, arcs: pd.DataFrame | None = None) -> dict[str, object]:
    """The figures of syntax, on the one syntactic universe the program has.

    **Numerator and denominator come from the same set.**  The share of
    non-projective links is computed on ``analyzable_links``, the canonical unit:
    the active records whose declared head exists as a record of the same sentence.
    The rows of the arc table would be a wrong denominator, because
    :func:`syntax.analyze_syntax` builds that table with a procedure of its own on
    the whole corpus, and it is a second population of the same thing: on Pedalion
    it contains 436 arcs that are not usable links — ``G?`` lacunae and other
    records that the filters remove — and lacks 31 that are.

    *tokens* must be the **active records** of the chosen group.

    **Coverage is declared.**  Projectivity is read in the arc table, and that table
    does not cover every usable link: the sentences that the builder skips are not
    in it. They are 14 out of 513,369 in Gorman and 31 out of 213,144 in Pedalion.
    They stay in the denominator, as the definition requires, and ``legami
    misurati`` (links measured) says how many were actually looked at.

    The distinct relations are counted with the suffix removed: ``ATR_CO`` and
    ``ATR`` are the same function, coordinated or not.
    """
    from .units import analyzable_link_mask, sentence_key

    vuoto = {"legami utilizzabili": 0, "legami misurati": 0,
             "relazioni distinte": 0,
             "funzioni distinte (suffisso tolto)": 0,
             "legami non proiettivi": 0, "% legami non proiettivi": 0.0,
             "frasi con almeno un legame non proiettivo": 0,
             "% frasi con almeno un legame non proiettivo": 0.0,
             "frasi nel gruppo": 0, "frasi con archi": 0, "frasi senza archi": 0,
             "ragione dell'esclusione": "senza_archi"}
    if tokens is None or tokens.empty:
        return vuoto

    frasi_totali = int(tokens[["document_id", "sentence_index"]].drop_duplicates().shape[0])
    vuoto["frasi nel gruppo"] = frasi_totali

    if "relation" in tokens.columns:
        # The labels as they stand in the file, suffixes included: this is the number
        # that the Overview calls “distinct relations”, and the one that counts if the
        # question is how many different labels a model would have to learn.
        etichette = tokens.loc[tokens["relation"].notna(), "relation"].astype("string")
        etichette = etichette[etichette.str.strip() != ""]
        vuoto["relazioni distinte"] = int(etichette.nunique())
        funzioni = map_unique(etichette, base_relation)
        vuoto["funzioni distinte (suffisso tolto)"] = int(pd.Series(funzioni).nunique())

    # The universe: the usable links, as asked of the canonical function.
    utilizzabili = tokens[np.asarray(
        analyzable_link_mask(tokens, within=tokens), dtype=bool)]
    legami = int(len(utilizzabili))
    vuoto["legami utilizzabili"] = legami

    if arcs is None or arcs.empty or not legami:
        vuoto["frasi senza archi"] = frasi_totali
        vuoto["ragione dell'esclusione"] = "corpus_senza_archi"
        return vuoto

    def _chiavi(frame: pd.DataFrame) -> pd.Series:
        return (sentence_key(frame).astype(str) + "\x00"
                + pd.to_numeric(frame["token_id"], errors="coerce")
                .fillna(-1).astype("int64").astype(str))

    dentro = set(_chiavi(utilizzabili))
    misurati = arcs[_chiavi(arcs).isin(dentro).to_numpy()]
    if misurati.empty:
        vuoto["frasi senza archi"] = frasi_totali
        vuoto["ragione dell'esclusione"] = "corpus_senza_archi"
        return vuoto

    storti = (misurati["non_projective"].fillna(False).astype(bool)
              if "non_projective" in misurati.columns
              else pd.Series(False, index=misurati.index))
    non_proiettivi = int(storti.sum())
    per_frase = (misurati.assign(_np=storti.to_numpy())
                 .groupby(["document_id", "sentence_index"], sort=False)["_np"].any())
    frasi_con_archi = int(len(per_frase))
    frasi_storte = int(per_frase.sum())

    return {
        # The canonical unit: it is the denominator of the share below.
        "legami utilizzabili": legami,
        # How many of those the arc table actually looked at.
        "legami misurati": int(len(misurati)),
        "relazioni distinte": vuoto["relazioni distinte"],
        "funzioni distinte (suffisso tolto)": vuoto.get("funzioni distinte (suffisso tolto)", 0),
        "legami non proiettivi": non_proiettivi,
        "% legami non proiettivi": round(non_proiettivi / legami * 100, 1) if legami else 0.0,
        "frasi con almeno un legame non proiettivo": frasi_storte,
        "% frasi con almeno un legame non proiettivo":
            round(frasi_storte / frasi_con_archi * 100, 1) if frasi_con_archi else 0.0,
        "frasi nel gruppo": frasi_totali,
        "frasi con archi": frasi_con_archi,
        "frasi senza archi": frasi_totali - frasi_con_archi,
        # A code and not a sentence: the sentence is written by the interface, in the
        # language chosen by the reader. The three values are “senza_archi” (no arcs),
        # “corpus_senza_archi” (corpus without arcs) and “frasi_non_utilizzabili”
        # (no usable sentences).
        "ragione dell'esclusione": "frasi_non_utilizzabili",
    }


def content_words_ranked(
    tokens: pd.DataFrame,
    *,
    profile: str = "solo parole di contenuto",
    extra: "Iterable[str] | None" = None,
    remove: "Iterable[str] | None" = None,
    top: int = 300,
) -> tuple[pd.DataFrame, bool]:
    """The content words ordered by TF-IDF, not by raw frequency.

    The defect that this function removes: εἰμί, λέγω, ἔχω, γίγνομαι, ποιέω and φημί
    are verbs to all intents and purposes, and they sit at the top of any list of
    content words without saying anything about the text, because they sit at the
    top everywhere. Document frequency recognises them: a lemma present in almost
    all the documents weighs little, a frequent lemma concentrated in a few
    documents weighs a lot. No word is removed for this, only moved lower down.

    It returns the table and a boolean that says whether the TF-IDF weight was
    applied: with a single document the document frequency distinguishes nothing,
    and then the table is ordered by frequency, and says so.
    """
    if tokens is None or tokens.empty or "lemma" not in tokens.columns:
        return pd.DataFrame(), False
    parole = (tokens if profile == "nessun filtro"
              else apply_stopword_profile(_content(tokens), profile,
                                          extra=extra, remove=remove))
    parole = parole[parole["lemma"].notna()]
    if parole.empty:
        return pd.DataFrame(), False

    conteggi = parole["lemma"].value_counts()
    totale = int(conteggi.sum())
    documenti = int(parole["document_id"].nunique()) if "document_id" in parole.columns else 1
    tabella = conteggi.reset_index()
    tabella.columns = ["lemma", "occorrenze"]
    tabella["per 10.000"] = (tabella["occorrenze"] / totale * 10_000).round(2)

    if documenti < 2:
        tabella["documenti"] = documenti
        tabella["rango"] = range(1, len(tabella) + 1)
        return tabella.head(top).reset_index(drop=True), False

    df = parole.groupby("lemma", sort=False)["document_id"].nunique().rename("documenti")
    tabella = tabella.merge(df.reset_index(), on="lemma", how="left")
    # Smoothed idf: log(1 + N/df). A lemma in all the documents is worth log 2, one in a
    # single document out of a hundred is worth log 101, and none is worth zero.
    tabella["TF-IDF"] = (tabella["occorrenze"]
                         * np.log1p(documenti / tabella["documenti"].clip(lower=1))).round(1)
    tabella = tabella.sort_values("TF-IDF", ascending=False).reset_index(drop=True)
    tabella["rango"] = range(1, len(tabella) + 1)
    return tabella.head(top).reset_index(drop=True), True


def lemma_profile(
    tokens: pd.DataFrame,
    lemma: str,
    *,
    top: int = 25,
    esempi: int = 8,
) -> dict[str, object]:
    """Everything the corpus says about a lemma, and nothing else.

    It is computed on request, for one lemma at a time: precomputing it for all the
    lemmas would mean doing eighteen thousand times the work that is needed once.
    """
    vuoto = {"lemma": lemma, "chiave": statistical_lemma_key(lemma),
             "occorrenze": 0, "forme": pd.DataFrame(), "grafie": pd.DataFrame(),
             "postag": pd.DataFrame(), "relazioni": pd.DataFrame(),
             "teste": pd.DataFrame(), "dipendenti": pd.DataFrame(),
             "documenti": pd.DataFrame(), "esempi": pd.DataFrame()}
    if tokens is None or tokens.empty or "lemma" not in tokens.columns or not lemma:
        return vuoto

    # The same key as the syntactic profile, and for the same reason: ``λέγω1``,
    # ``λέγω2``, ``λέγω3`` and ``λέγω`` are a single lemma, and searching for one
    # must find them all. The numbering is Perseus metadata inside the string.
    colonna = tokens["lemma"].astype("string").fillna("")
    chiavi = map_unique(colonna, statistical_lemma_key)
    # The occurrences travel with the keys, not the bare set: ``resolve_lemma_key``
    # needs them to tell a spelling from its corruption.
    cercato = resolve_lemma_key(lemma, Counter(chiavi.tolist()))
    e_questo = pd.Series(chiavi.to_numpy() == cercato, index=tokens.index)
    mio = tokens[e_questo]
    if mio.empty:
        return vuoto

    def conta(colonna, frame=None, nome=None):
        base = mio if frame is None else frame
        if colonna not in base.columns:
            return pd.DataFrame()
        valori = base[colonna].astype("string").fillna("")
        valori = valori[valori.str.strip() != ""]
        if valori.empty:
            return pd.DataFrame()
        tabella = valori.value_counts().head(top).reset_index()
        tabella.columns = [nome or colonna, "occorrenze"]
        return tabella

    fuori = dict(vuoto)
    fuori["occorrenze"] = int(len(mio))
    fuori["chiave"] = cercato
    fuori["grafie"] = (mio["lemma"].astype("string").fillna("")
                       .value_counts().rename_axis("grafia")
                       .reset_index(name="occorrenze"))
    fuori["forme"] = conta("form", nome="forma")
    fuori["postag"] = conta("postag", nome="etichetta")
    fuori["documenti"] = conta("document_id", nome="documento")

    if "relation" in mio.columns:
        rel = map_unique(mio["relation"].astype("string"), base_relation)
        rel = pd.Series(rel).astype("string").fillna("")
        rel = rel[rel.str.strip() != ""]
        if not rel.empty:
            tabella = rel.value_counts().head(top).reset_index()
            tabella.columns = ["relazione", "occorrenze"]
            fuori["relazioni"] = tabella

    # Heads and dependents: a single climb per sentence, with the index of the heads.
    if {"token_id", "head", "sentence_index"} <= set(tokens.columns):
        lavoro = tokens.reset_index(drop=True).copy()
        lavoro["_sent"] = (lavoro.get("source_file", "").astype("string").fillna("") + "␟"
                           + lavoro["document_id"].astype("string").fillna("") + "␟"
                           + lavoro["sentence_index"].astype("string").fillna(""))
        lavoro["_tid"] = pd.to_numeric(lavoro["token_id"], errors="coerce")
        lavoro["_head"] = pd.to_numeric(lavoro["head"], errors="coerce")
        indice = build_head_index(lavoro).to_numpy()
        lemmi_tutti = lavoro["lemma"].astype("string").fillna("")
        e_mio = e_questo.to_numpy(dtype=bool)

        posizioni = np.flatnonzero(e_mio)
        teste = indice[posizioni]
        teste = teste[teste >= 0]
        if teste.size:
            tabella = lemmi_tutti.iloc[teste].value_counts().head(top).reset_index()
            tabella.columns = ["testa", "occorrenze"]
            fuori["teste"] = tabella

        figli = np.flatnonzero((indice >= 0) & e_mio[np.clip(indice, 0, None)])
        if figli.size:
            tabella = lemmi_tutti.iloc[figli].value_counts().head(top).reset_index()
            tabella.columns = ["dipendente", "occorrenze"]
            fuori["dipendenti"] = tabella

    # The examples: the whole sentence, recomposed from the forms.
    if {"document_id", "sentence_index", "form"} <= set(tokens.columns):
        chiavi = mio[["document_id", "sentence_index"]].drop_duplicates().head(esempi)
        righe = []
        for _, chiave in chiavi.iterrows():
            frase = tokens[(tokens["document_id"] == chiave["document_id"])
                           & (tokens["sentence_index"] == chiave["sentence_index"])]
            testo = " ".join(frase["form"].astype("string").fillna("").tolist()).strip()
            righe.append({"documento": chiave["document_id"],
                          "frase": chiave["sentence_index"],
                          "testo": testo[:300]})
        if righe:
            fuori["esempi"] = pd.DataFrame(righe)
    return fuori


# 7. Syntactic word sketch
# ---------------------------------------------------------------------------

#: The key with which the profile counts lemmas.
#:
#: NFC and removal of the tool's numbering, and nothing else.  ``λέγω1``,
#: ``λέγω2``, ``λέγω3`` and ``λέγω`` are the same statistical lemma: the digit is
#: Perseus metadata embedded in the string, not a lexical distinction, and leaving
#: it in fragments the frequencies. In Gorman, among the words, ``λέγω`` written
#: without a digit occurs 51 times and the statistical lemma 1,908 in all, and
#: since logDice rewards rarity a profile built on the 51 would inflate every
#: score.
#:
#: **The map of canonical variants is not applied here.**  Merging ``νοῦς`` with
#: ``νόος`` or ``ἀείρω`` with ``αἴρω`` harmonises different lexical conventions,
#: which is an operation between resources; this is a statistic internal to a
#: single resource, and the difference between two spellings of a lemma is a datum
#: of the corpus that must not be erased.
def statistical_lemma_key(lemma: object) -> str:
    """The statistical key of a lemma: NFC, without the tool's numbering."""
    return without_lemma_numbering(nfc(lemma))


def resolve_lemma_key(scritto: object, presenti) -> str:
    """The key to use for what the user has typed in the box.

    Two things that could easily end up on the same line are separated here.
    **Finding** a lemma and **counting** it are not the same operation and do not
    want the same key: counting uses :func:`statistical_lemma_key`, which is exact
    and forgives nothing because it is the unit of a statistic; finding uses the
    search key, which is generous because it must reach whoever types without a
    polytonic keyboard. This function does **only** the second: it takes what has
    been written and returns a statistical key; from there on the count is the usual
    one, on the usual string.

    Why the search key is needed here: “Search the corpus” goes through
    :func:`~greek_corpus_pipeline.search.key_test` and finds ἄνθρωπος for whoever
    writes ``ανθρωπος``; a box that stopped at capitals would answer that the lemma
    does not occur in the corpus. Two pages with two criteria would let the second
    deny what the first has just shown.

    There are four steps, and one goes down only if the previous one has not
    answered:

    1. the exact statistical key, if there is one;
    2. capitals, which in Greek distinguish the proper name and therefore count for
       the lexicon but not for whoever types;
    3. **the search key**, the same as on the “Search the corpus” page: accents,
       breathings, iota subscript, final sigma, NFC/NFD and the Latin alphabet;
    4. if several candidates remain, no guess is made.

    The third step takes nothing away from anyone: it is reached only when
    otherwise the answer would have been “does not occur in the corpus”.
    """
    from .search import key_test, search_key

    chiave = statistical_lemma_key(scritto)
    if chiave in presenti:
        return chiave

    piegata = chiave.casefold()
    candidati = [k for k in presenti if k.casefold() == piegata]
    if candidati:
        return candidati[0] if len(candidati) == 1 else chiave

    verifica = key_test(scritto, "esatto")
    if verifica is None:
        return chiave
    # The statistical keys are already free of numbering: the search compares those, not
    # the spellings of the corpus, so ``λέγω`` and ``λέγω3`` remain a single lemma even
    # for whoever types without accents.
    candidati = [k for k in presenti if verifica(search_key(k))]
    if len(candidati) == 1:
        return candidati[0]
    if len(candidati) < 2:
        return chiave

    # More than one statistical lemma under the same search key. They are almost
    # never two words: they are a word and a wrong spelling of it — in Gorman
    # ``λέγω`` 1,957 times and ``λἐγω`` once, ``ἄνθρωπος`` 809 times and
    # ``̓́Ανθρωπος`` once. Whoever types without accents cannot tell them apart, and
    # answering that the lemma does not occur in the corpus would be false.
    #
    # The one that the corpus writes most often is taken, and the page shows
    # **which** was taken: the choice is visible and the count remains that of the
    # chosen spelling, not a sum of different spellings. If the occurrences are not
    # known — the set of keys does not carry them — or if two spellings are equally
    # frequent, no guess is made.
    occorrenze = getattr(presenti, "get", None)
    if occorrenze is None:
        return chiave
    classifica = sorted(candidati, key=lambda k: (-int(occorrenze(k, 0) or 0), k))
    if int(occorrenze(classifica[0], 0) or 0) <= int(occorrenze(classifica[1], 0) or 0):
        return chiave
    return classifica[0]


def word_sketch(
    words: pd.DataFrame,
    lemma: str,
    *,
    min_count: int = 1,
    top: int = 40,
) -> dict[str, object]:
    """What this word combines with, by syntactic relation rather than by window.

    A collocation window asks "what appears near λέγω". A treebank can ask the
    better question: "what is the *subject* of λέγω, what is its *object*, in
    which case". The association measure is logDice, in its canonical form
    ``14 + log2(2·f_joint / (f_target + f_partner))``, which does not depend on
    corpus size and is therefore comparable between Herodotus and the whole
    corpus.

    **The three terms do not share one denominator, and they must not.**  A
    dependency association measure counts two different things, and forcing them
    onto one universe would be a false uniformity rather than a correction:

    ``f_target``   how many times the lemma occurs among the **words**
    ``f_partner``  the same, for the other lemma
    ``f_joint``    how many **links between two words** join them, under that
                   relation and in that direction

    So *words* must be :attr:`units.Units.words`.  Passing the active records
    would count punctuation and technical nodes as lexical occurrences, and
    passing the imported records would add the nodes that carry no text at all.
    The links counted here are the analyzable links of :func:`units.analyzable_link_mask`
    restricted to those whose two ends are both words: an arc whose head is a
    punctuation mark has no lemma to associate, and an arc to a missing head is
    not an arc.  That count is reported in the returned ``unita`` so a reader
    knows what the joint frequency was drawn from.

    Lemmas are counted on :func:`statistical_lemma_key`; the spellings the key
    was built from are returned in ``grafie`` and are never thrown away.

    **An empty relation contributes to the lexical frequencies and to nothing
    else.**  A word whose ``relation`` field is empty is a real occurrence of its
    lemma, so it counts in ``f_target`` and ``f_partner``; but the absence of a
    relation is not a syntactic relation, and it must not become a row of the
    profile.  That absence is already diagnosed on its own account by
    ``relation-missing``.

    There is **no minimum on the joint frequency**: a pair seen once is shown
    with ``co-occorrenze = 1`` next to its score, because logDice rewards rarity and a
    high score on one observation has to be visible as such.  *top* caps how
    many rows each relation shows, and the number of rows dropped by that cap is
    reported.
    """
    vuoto = {
        "lemma": lemma,
        "chiave": statistical_lemma_key(lemma),
        "associazioni": pd.DataFrame(),
        "f_target": 0,
        "grafie": pd.DataFrame(),
        "unita": {},
        "troncate": 0,
    }
    needed = {"token_id", "head", "relation", "lemma"}
    if words is None or words.empty or not needed <= set(words.columns):
        return vuoto

    work = words.reset_index(drop=True).copy()
    work["_sent"] = sentence_key(work)
    work["_tid"] = pd.to_numeric(work["token_id"], errors="coerce")
    work["_head"] = pd.to_numeric(work["head"], errors="coerce")
    head_index = build_head_index(work).to_numpy()

    scritti = work["lemma"].astype("string").fillna("")
    lemmas = map_unique(scritti, statistical_lemma_key).to_numpy()
    relations = map_unique(
        work["relation"].astype("string").fillna(""), base_relation).to_numpy()
    case = _slot(work, CASE_SLOT).to_numpy()

    lemma_counts = Counter(lemmas)
    cercato = resolve_lemma_key(lemma, lemma_counts)
    target_count = lemma_counts.get(cercato, 0)
    if not target_count:
        return vuoto

    # The spellings that the key comes from: they are merged in the count but kept in
    # the profile, because knowing that λέγω occurs in the corpus as λέγω3 is a datum.
    e_il_bersaglio = lemmas == cercato
    grafie = (scritti[e_il_bersaglio].value_counts().rename_axis("grafia")
              .reset_index(name="occorrenze"))
    if not grafie.empty:
        etichette = disambiguate_spellings(grafie["grafia"].astype(str).tolist())
        grafie["grafia"] = etichette

    # Only the arcs that touch the target lemma can contribute anything, and on
    # a corpus of 625,176 tokens that is a few thousand rows: selecting them
    # first, in table order so the counters fill in the same sequence, leaves
    # the loop with a thousandth of the iterations.
    linked = head_index >= 0
    governed = np.zeros(len(work), dtype=bool)
    governed[linked] = lemmas[head_index[linked]] == cercato
    touching = np.flatnonzero(linked & (governed | e_il_bersaglio))

    dependents: Counter = Counter()
    heads: Counter = Counter()
    senza_relazione = 0
    for row in touching:
        if not relations[row]:
            senza_relazione += 1
            continue
        head_position = head_index[row]
        if lemmas[head_position] == cercato:
            label = relations[row]
            if case[row] not in ("", "-"):
                label = f"{label} ({describe_value(CASE_SLOT, case[row])})"
            dependents[(label, lemmas[row])] += 1
        if lemmas[row] == cercato:
            heads[(relations[row], lemmas[head_position])] += 1

    # The spellings of each key, for the column that shows them when there is more than
    # one.
    per_chiave: dict[str, list[str]] = {}
    for chiave, grafia in zip(lemmas, scritti.to_numpy()):
        elenco = per_chiave.setdefault(chiave, [])
        if grafia not in elenco:
            elenco.append(grafia)
    per_chiave = {chiave: disambiguate_spellings(elenco)
                  for chiave, elenco in per_chiave.items()}

    troncate = 0
    pezzi = []
    for direzione, counter in (("dipendente", dependents), ("testa", heads)):
        righe = []
        for (relation, partner), joint in counter.items():
            if joint < min_count:
                continue
            partner_total = lemma_counts.get(partner, 0)
            if not partner_total:
                continue
            varianti = per_chiave.get(partner, [])
            righe.append({
                "relazione": relation,
                "direzione": direzione,
                "lemma associato": partner,
                "co-occorrenze": int(joint),
                "occorrenze del lemma associato": int(partner_total),
                "occorrenze lemma": int(target_count),
                "logDice": round(
                    14 + math.log2(2 * joint / (target_count + partner_total)), 2),
                "grafie": " · ".join(sorted(varianti)) if len(varianti) > 1 else "",
            })
        if not righe:
            continue
        tabella = (pd.DataFrame(righe)
                   .sort_values(["relazione", "logDice"], ascending=[True, False],
                                kind="stable"))
        tenute = tabella.groupby("relazione", sort=False).head(top)
        troncate += len(tabella) - len(tenute)
        pezzi.append(tenute)

    associazioni = (pd.concat(pezzi, ignore_index=True) if pezzi
                    else pd.DataFrame())
    return {
        "lemma": lemma,
        "chiave": cercato,
        "associazioni": associazioni,
        "f_target": int(target_count),
        "grafie": grafie,
        "unita": {
            "f_target": "occorrenze del lemma fra le words",
            "f_partner": "occorrenze dell'altro lemma fra le words",
            "f_joint": "archi fra due words che uniscono i due lemmi",
            "chiave_lemma": "NFC e taglio della numerazione dello strumento",
            "words": int(len(work)),
            "links": int(linked.sum()),
            "archi_senza_relazione": int(senza_relazione),
        },
        "troncate": int(troncate),
    }


# ---------------------------------------------------------------------------
# 7b. Co-occurrence tables and clusters
# ---------------------------------------------------------------------------

# 8. Growth curves
# ---------------------------------------------------------------------------
