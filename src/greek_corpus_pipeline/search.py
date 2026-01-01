"""Searching a treebank the way a philologist actually searches.

The TLG separates three engines — a word index, a lemma search, a full text
scan — and makes you choose. On an annotated treebank that separation is
unnecessary: the lemma is *already* on every token, so a lemma search is exact
and complete by construction rather than dependent on a morphological
analyser's coverage. This module therefore offers one query object with several
independent filters, all combinable:

* **form** — exact, prefix, contains, or regular expression, with an option to
  ignore accents and breathings (the single most requested behaviour, because
  nobody wants to type ᾧτινι correctly to find it);
* **lemma** — same matching modes;
* **postag** — a nine-character pattern where ``.`` means "anything", so
  ``v...p....`` reads "any participle" and ``n......g.`` "any noun in the
  genitive"; or, more humanely, the individual drop-down slots;
* **relation** — the syntactic function, with or without its ``_CO`` suffix;
* **head lemma / head relation** — "every object of λέγω", "every genitive
  under a preposition";
* **metadata** — author, work, genre, dialect, period, century.

Every result comes back with its KWIC line, so a search is never a bare count:
Perseus, Scaife and every concordance since Cruden's have taught readers to
expect the context, and a number without a passage is not an answer.

The design constraint that shaped everything here: *every search must be able
to become a frequency table*. That is the clause PML-TQ calls ``give`` and it
is exactly what GLAUx (which exports rows but does not aggregate) and the TLG
(which has statistics and search, in two separate worlds) do not offer.

Beside that combined query sits the search the interface offers, and it is
narrower on purpose. :class:`WordQuery` names *one* field — the form or the
lemma, never both — and :func:`find_occurrences` answers with one row per
occurrence and the sentence around it; :func:`detail_of` then says what a
chosen occurrence is, in five lines. "Which of the two did I ask for" is a
question a reader can answer about their own search. "Why does form X *and*
lemma Y find nothing" is not, and it was the commonest way of finding nothing.

Either way in, the word may be typed in polytonic Greek, in Greek without
accents or breathings, or in Latin letters: ἄνθρωπος, ανθρωπος and anthropos
are one search. :func:`search_key` is where that is made true, and it carries
the transliteration table.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from .agdt_schema import (
    CASE_SLOT,
    POSITION_NAMES,
    POSITION_VALUES,
    TAG_LENGTH,
    base_relation,
    describe_postag,
    describe_relation,
)
from .fastmap import map_unique
from .normalise import without_lemma_numbering
from .orthography import APOSTROPHES, strip_diacritics
from .syntax import build_head_index

MATCH_MODES = ("esatto", "inizia con", "contiene", "espressione regolare")

#: The three modes a word search offers. The fourth of ``MATCH_MODES`` — a raw
#: regular expression — belongs to the combined query below, not to the word
#: search: nobody looking for ἄνθρωπος wants to be told their brackets are
#: unbalanced.
WORD_MATCH_MODES = ("esatto", "inizia con", "contiene")

# ---------------------------------------------------------------------------
# The words a search says back to the reader
# ---------------------------------------------------------------------------

def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text, in the language of the interface, with English as the fallback.

    The same reason as in ``figures`` applies: the line that summarises a search is read
    in the window, and the strings all live in ``gui_qt.i18n``. The fallback exists
    because this module must keep working when imported without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:
        return fallback.format(*args) if args else fallback
    return text


def _pair(pair) -> str:
    """Italian or English, from a pair declared in the scheme."""
    if not isinstance(pair, (tuple, list)) or len(pair) < 2:
        return str(pair)
    try:
        from gui_qt.i18n import pick                   # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return str(pair[0])
    return pick(pair)


def _mode_name(mode: str) -> str:
    """“esatto” or “exact”: the value stays Italian, the word does not."""
    return _t(f"search.mode.{mode}", str(mode))


# ---------------------------------------------------------------------------
# One word, three ways of typing it
# ---------------------------------------------------------------------------
#
# ἄνθρωπος, ανθρωπος, anthropos are the same word, and a search box that
# answers only the first of the three answers almost nobody: the polytonic
# keyboard is not installed, the accent is half-remembered, the word was copied
# out of a Latin-script bibliography. Every comparison in this section
# therefore happens between *keys* rather than between what is written:
#
#     NFD  →  drop every combining mark  →  lowercase  →  transliterate
#
# applied to both sides. The corpus is never touched: the keys live in a table
# built beside it, one entry per distinct value, and thrown away when the
# search is over. The transliteration table itself is written out in the
# docstring of :func:`search_key`, which is the function that applies it.
#
# Three points are the whole design.
#
# *Final sigma is not a letter of its own.* ς and σ both fold to ``s``, so
# ἄνθρωπος is found by ανθρωποσ and λόγος by logos.
#
# *e and o are ambiguous on purpose.* Latin ``e`` stands for ε and for η, ``o``
# for ο and for ω, because someone typing ``anthropos`` does not know — and
# should not have to know — that the fifth vowel of ἄνθρωπος is an omega. The
# ambiguity is resolved only if the user resolves it: writing the Greek letter
# (ανθρωπος), or writing the Latin vowel long (anthrōpos, anthrôpos, and
# beta-code ``w`` for ω), restricts the search to that vowel. This is why the
# fold produces a *pattern* and not simply a string: an undecided vowel becomes
# a two-way character class, everything else a literal.
#
# *Digraphs win over single letters.* ``th`` is θ before it is τ+h, ``ps`` is ψ
# before it is π+σ. There is no bare ``h`` in the key alphabet — it can only be
# the rough breathing, which the fold has already removed from the Greek — so
# hodos finds ὁδός.

#: η and ω in the key alphabet: e and o with a macron (U+0113, U+014D). They
#: are one character each, so a key stays as long as the word it came from.
LONG_E = "ē"
LONG_O = "ō"

#: "an e whose length the user did not state" and its omicron/omega twin. They
#: never leave this module: :func:`search_key` resolves them, :func:`key_pattern`
#: turns them into a character class.
ANY_E = "\x01"
ANY_O = "\x02"

#: Marks that say "this Latin vowel is long", i.e. "eta, not epsilon": the
#: combining macron and the combining circumflex. The Greek circumflex is
#: U+0342 and is not one of them, so nothing on the Greek side is affected.
_LONG_MARKS = frozenset({"̄", "̂"})

#: Elision apostrophes, in every codepoint the corpora use for them. They are
#: dropped from the key: δ᾽ and δ' and δ’ are one word typed three ways.
_APOSTROPHE_CHARS = frozenset(APOSTROPHES)

#: Greek letter -> key. Diacritics are gone by the time this is consulted.
GREEK_TO_KEY: dict[str, str] = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": LONG_E,
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u",
    "φ": "ph", "χ": "ch", "ψ": "ps", "ω": LONG_O,
}

#: Latin letter or digraph -> key. Digraphs are tried first; an empty value
#: means "write nothing", which is what a rough breathing contributes.
LATIN_TO_KEY: dict[str, str] = {
    # digraphs
    "th": "th", "ph": "ph", "ch": "ch", "ps": "ps", "rh": "r",
    # single letters
    "a": "a", "b": "b", "c": "k", "d": "d", "e": ANY_E, "f": "ph",
    "g": "g", "h": "", "i": "i", "j": "i", "k": "k", "l": "l", "m": "m",
    "n": "n", "o": ANY_O, "p": "p", "r": "r", "s": "s", "t": "t",
    "u": "u", "v": "u", "w": LONG_O, "x": "x", "y": "u", "z": "z",
    # the two vowels the user has already disambiguated
    LONG_E: LONG_E, LONG_O: LONG_O,
}

_RESOLVE_AMBIGUOUS = {ANY_E: "e", ANY_O: "o"}
_AMBIGUOUS_CLASS = {ANY_E: f"[e{LONG_E}]", ANY_O: f"[o{LONG_O}]"}


def _fold_atoms(text: object) -> list[str]:
    """Fold a written word into key atoms, one per letter of the original.

    An atom is a piece of the key: usually a letter or two (``th``, ``ps``),
    sometimes one of the two ambiguity markers, sometimes a character the table
    does not know, which passes through untouched so that it can still match
    itself.
    """
    if not isinstance(text, str) or not text:
        return []

    # Marks come off — with one exception. A macron or circumflex on a Latin
    # e or o is not decoration, it is the user saying "eta", "omega", and it
    # has to be read before the mark is thrown away.
    letters: list[str] = []
    for char in unicodedata.normalize("NFD", text.lower()):
        if unicodedata.combining(char):
            if char in _LONG_MARKS and letters:
                if letters[-1] == "e":
                    letters[-1] = LONG_E
                elif letters[-1] == "o":
                    letters[-1] = LONG_O
            continue
        if char in _APOSTROPHE_CHARS:
            continue
        letters.append(char)

    atoms: list[str] = []
    index = 0
    total = len(letters)
    while index < total:
        char = letters[index]
        greek = GREEK_TO_KEY.get(char)
        if greek is not None:
            atoms.append(greek)
            index += 1
            continue
        pair = char + letters[index + 1] if index + 1 < total else ""
        mapped = LATIN_TO_KEY.get(pair) if pair else None
        if mapped is not None:
            if mapped:
                atoms.append(mapped)
            index += 2
            continue
        mapped = LATIN_TO_KEY.get(char)
        if mapped is not None:
            if mapped:
                atoms.append(mapped)
            index += 1
            continue
        atoms.append(char)
        index += 1
    return atoms


@lru_cache(maxsize=1 << 18)
def _key_of(text: str) -> str:
    return "".join(_RESOLVE_AMBIGUOUS.get(atom, atom) for atom in _fold_atoms(text))


def search_key(text: object) -> str:
    """The normalised key of a written word: NFD, marks off, lowercase, transliterated.

    ``ἄνθρωπος``, ``ανθρωπος`` and ``ΑΝΘΡΩΠΟΣ`` all give ``anthrōpos``; so does
    ``anthrōpos`` typed in Latin letters. ``anthropos``, which leaves the vowel
    undecided, gives ``anthropos`` — the same string an omicron would give,
    which is why a query is matched through :func:`key_pattern` and not by
    comparing keys.

    **The transliteration table.** From the Greek, one letter at a time::

        α a    β b    γ g    δ d    ε e    ζ z    η ē    θ th   ι i
        κ k    λ l    μ m    ν n    ξ x    ο o    π p    ρ r    σ s   ς s
        τ t    υ u    φ ph   χ ch   ψ ps   ω ō

    and from what may be typed in Latin letters, digraphs first::

        th θ   ph φ   ch χ   ps ψ   rh ῥ
        a α    b β    c κ    d δ    e ε or η      f φ    g γ    h  (nothing)
        i ι    j ι    k κ    l λ    m μ    n ν    o ο or ω      p π
        r ρ    s σ/ς  t τ    u υ    v υ    w ω    x ξ    y υ    z ζ
        ē η    ō ω           (a macron or a circumflex: "the long one")

    Diacritics, iota subscripts and elision apostrophes are removed before the
    table is consulted, final sigma is not a letter of its own, and a bare
    ``h`` can only be the rough breathing, which the Greek side has already
    lost: ``hodos`` finds ὁδός.

    Memoised: a corpus is folded once per distinct value, and the second search
    over the same corpus pays nothing at all.
    """
    if not isinstance(text, str) or not text:
        return ""
    return _key_of(text)


def key_pattern(text: object) -> str:
    """What was typed, as a regular expression over keys.

    ``anthropos`` becomes ``anthr[oō]p[oō]s``: the two undecided vowels match
    either quantity, every other letter matches itself.
    """
    return "".join(_AMBIGUOUS_CLASS.get(atom, re.escape(atom))
                   for atom in _fold_atoms(text))


def key_column(series: pd.Series) -> pd.Series:
    """The key of every value of a column, computed once per distinct value.

    This is the indexed copy the search reads: the corpus itself is never
    modified, and the copy is aligned with it row by row. A treebank of six
    hundred thousand tokens holds some seventy thousand distinct forms, so
    folding per value rather than per row is the difference between a search
    that answers instantly and one that does not.
    """
    values = series.astype("string").fillna("")
    distinct = pd.Index(values.unique())
    mapping = pd.Series([search_key(value) for value in distinct],
                        index=distinct, dtype="object")
    return values.map(mapping)


def lemma_key(text: object) -> str:
    """The search key of a **lemma**: like that of a form, minus the digit.

    ``λέγω1``, ``λέγω2``, ``λέγω3`` and ``λέγω`` are the same lemma: the digit is
    Perseus metadata embedded in the string, not a lexical distinction. In Gorman
    11.7% of the records carry it: without the cut, typing ``λέγω`` in the lemma box
    would find 52 occurrences instead of 1,958 — the 1,906 missing ones are written
    ``λέγω3`` (1,785), ``λέγω2`` (98) and ``λέγω1`` (23).

    The digit is removed **only** on the side of the lemma, and with
    :func:`~greek_corpus_pipeline.normalise.without_lemma_numbering`, which is the
    same function with which the statistical key removes it: the two pages thus
    start from the very same gesture. On the side of the form nothing is touched,
    because there a final digit is not metadata — in Pedalion 34 forms end in a
    digit and are lacuna markers (``G2``, ``G15``): removing the number would make
    them collapse onto one another.

    It holds for matching and for nothing else: the raw lemma stays what it is,
    and the counts continue to distinguish the spellings.
    """
    return search_key(without_lemma_numbering(text))


def key_test(text: object, mode: str = "esatto",
             *, campo: str = "") -> "Callable[[str], bool] | None":
    """The criterion with which one decides whether a key is the one being sought.

    A single function, because the answer must not depend on which page asked the
    question. Whoever searches a whole column comes through here by way of
    :func:`key_mask`; whoever has to resolve what the user has written to *one*
    key — the profile of a lemma in the statistics — calls this directly. Having
    two copies is how two pages begin to answer two different things about the
    same word.

    It returns ``None`` if nothing usable has been written: this is not a criterion
    that finds nothing, it is the absence of a criterion, and whoever calls must be
    able to tell the two cases apart.

    The regex is compiled **once** and the test is applied to many keys: this is the
    reason why this function returns a function instead of also taking the value to
    compare.

    *campo* says what is being searched. With ``"lemma"`` the Perseus numbering is
    removed from what has been written, exactly as :func:`key_column_for` removes
    it from the values of the corpus: the two parts of the comparison must undergo
    the same gesture, otherwise a typed ``λέγω1`` would not find ``λέγω`` written
    without a digit.
    """
    pattern = key_pattern(without_lemma_numbering(text) if campo == "lemma" else text)
    if not pattern:
        return None
    try:
        regex = re.compile(pattern)
    except re.error:                                   # pragma: no cover
        return None

    if mode == "inizia con":
        return lambda key: regex.match(key) is not None
    if mode == "contiene":
        return lambda key: regex.search(key) is not None
    return lambda key: regex.fullmatch(key) is not None  # "esatto", and every other


def key_column_for(series: pd.Series, campo: str = "") -> pd.Series:
    """Like :func:`key_column`, but knowing whether the column is that of the lemmas."""
    if campo != "lemma":
        return key_column(series)
    values = series.astype("string").fillna("")
    distinct = pd.Index(values.unique())
    mapping = pd.Series([lemma_key(value) for value in distinct],
                        index=distinct, dtype="object")
    return values.map(mapping)


def key_mask(series: pd.Series, text: str, mode: str = "esatto",
             *, campo: str = "") -> pd.Series:
    """Which rows of a column match *text*, read forgivingly.

    The test is applied to the distinct values and gathered back onto the rows,
    for the same reason :func:`key_column` folds per value.

    *campo* says which column is being read, because the key of a lemma is not that
    of a form: see :func:`lemma_key`. Whoever does not say gets the key of the
    forms, which is the default behaviour.
    """
    index = getattr(series, "index", None)
    test = key_test(text, mode, campo=campo)
    if test is None:
        return pd.Series(False, index=index)

    piega = lemma_key if campo == "lemma" else search_key
    values = series.astype("string").fillna("")
    codes, uniques = pd.factorize(values, use_na_sentinel=False)
    distinct = np.asarray(uniques, dtype=object)
    matched = np.fromiter((test(piega(value)) for value in distinct),
                          dtype=bool, count=len(distinct))
    if not len(distinct):
        return pd.Series(False, index=index)
    return pd.Series(matched[codes], index=index)


RESULT_COLUMNS = [
    "sinistra", "parola", "destra", "forma", "lemma", "postag", "analisi",
    "relazione", "funzione", "testa", "autore", "opera", "locus",
    "periodo", "dialetto", "genere", "documento", "frase", "token",
]


@dataclass
class Query:
    """One search. Every field is optional; empty fields impose no constraint."""

    form: str = ""
    form_mode: str = "esatto"
    lemma: str = ""
    lemma_mode: str = "esatto"
    ignore_diacritics: bool = True
    case_sensitive: bool = False

    postag_pattern: str = ""            # e.g. "v...p....", dots are wildcards
    slots: dict[int, str] = field(default_factory=dict)  # {slot: char}

    relation: str = ""
    relation_exact: bool = False        # False = compare the base label

    head_lemma: str = ""
    head_relation: str = ""

    author: str = ""
    work: str = ""
    genre: str = ""
    dialect: str = ""
    period: str = ""
    century: str = ""

    context: int = 6
    limit: int = 20_000

    def is_empty(self) -> bool:
        return not any([
            self.form, self.lemma, self.postag_pattern, self.slots,
            self.relation, self.head_lemma, self.head_relation,
            self.author, self.work, self.genre, self.dialect,
            self.period, self.century,
        ])

    def describe(self) -> str:
        """A one-line, human-readable statement of what was asked.

        In the language of the interface: this line ends up under the search bar.
        """
        parts: list[str] = []
        if self.form:
            parts.append(_t("query.form", "form {0} “{1}”",
                            _mode_name(self.form_mode), self.form))
        if self.lemma:
            parts.append(_t("query.lemma", "lemma {0} “{1}”",
                            _mode_name(self.lemma_mode), self.lemma))
        if self.postag_pattern:
            parts.append(_t("query.postag", "tag {0}", self.postag_pattern))
        for slot_index, char in sorted(self.slots.items()):
            label = _pair(POSITION_NAMES[slot_index]).lower()
            value = _pair(POSITION_VALUES.get(slot_index, {}).get(char, (char, char)))
            parts.append(f"{label} = {value}")
        if self.relation:
            parts.append(_t("query.relation", "relation {0}", self.relation))
        if self.head_lemma:
            parts.append(_t("query.head_lemma", "head with lemma “{0}”",
                            self.head_lemma))
        if self.head_relation:
            parts.append(_t("query.head_relation", "head with relation {0}",
                            self.head_relation))
        # ``name``, not ``field``: the field name of a dataclass is already imported in
        # this module, and giving the two the same name here would shadow it.
        for name, value in (("autore", self.author), ("opera", self.work),
                            ("genere", self.genre), ("dialetto", self.dialect),
                            ("periodo", self.period), ("secolo", self.century)):
            if value:
                parts.append(f"{_t('group.' + name, name)} = {value}")
        return " · ".join(parts) if parts else _t("query.none", "no filter")


# ---------------------------------------------------------------------------
# Matching primitives
# ---------------------------------------------------------------------------

def _bool(mask) -> pd.Series:
    """Force a mask to plain numpy booleans.

    Pandas' nullable string dtype propagates ``<NA>`` through comparisons, and
    an ``<NA>`` inside a boolean mask raises the moment two masks are combined.
    Every filter therefore passes through here: a missing value simply does not
    match.
    """
    return pd.Series(mask, copy=False).fillna(False).astype(bool)


def fold_column(series: pd.Series) -> pd.Series:
    """Diacritic-free version of a text column, computed per distinct value.

    A corpus of six hundred thousand tokens holds perhaps seventy thousand
    distinct forms. Stripping diacritics once per *value* instead of once per
    *row* is the difference between a search that answers while the user's
    finger is still on the key and one that takes three seconds — and a search
    box that lags is a search box nobody uses twice.
    """
    values = series.astype("string").fillna("")
    distinct = pd.Index(values.unique())
    mapping = pd.Series([strip_diacritics(value) for value in distinct], index=distinct)
    return values.map(mapping)


def _text_mask(series: pd.Series, needle: str, mode: str,
               *, ignore_diacritics: bool, case_sensitive: bool,
               campo: str = "") -> pd.Series:
    """Apply one textual filter to a column, honouring the matching mode."""
    if not needle:
        return pd.Series(True, index=series.index)

    # Ignoring the diacritics is what the reader means by "find me this word",
    # and the normalised key does that and more: it also accepts the word typed
    # in Latin letters. The literal paths below stay for the two cases where
    # the user has asked for something else — a regular expression, or an
    # accent-sensitive comparison.
    if ignore_diacritics and mode in WORD_MATCH_MODES:
        return key_mask(series, needle, mode, campo=campo)

    values = series.astype("string").fillna("")
    target = needle
    if ignore_diacritics:
        values = fold_column(values)
        target = strip_diacritics(needle)
    elif not case_sensitive:
        values = values.str.lower()
        target = needle.lower()

    if mode == "esatto":
        return _bool(values == target)
    if mode == "inizia con":
        return _bool(values.str.startswith(target))
    if mode == "contiene":
        return _bool(values.str.contains(re.escape(target), regex=True))
    if mode == "espressione regolare":
        try:
            return _bool(values.str.contains(target, regex=True))
        except re.error:
            # A half-typed regular expression should return nothing, not crash
            # the interface while the user is still typing.
            return pd.Series(False, index=series.index)
    return pd.Series(True, index=series.index)


def _postag_mask(tags: pd.Series, pattern: str) -> pd.Series:
    """Match a nine-slot pattern where ``.`` and ``-`` mean 'any'.

    Written by hand rather than delegated to a regular expression because the
    user types ``v...p`` and means "a participle", stopping when they have said
    enough; padding the pattern here is friendlier than demanding nine
    characters.
    """
    if not pattern:
        return pd.Series(True, index=tags.index)
    cleaned = pattern.strip()
    if not cleaned:
        return pd.Series(True, index=tags.index)
    cleaned = (cleaned + "." * TAG_LENGTH)[:TAG_LENGTH]
    regex = "".join("." if char in "._?*" else re.escape(char) for char in cleaned)
    values = tags.astype("string").fillna("")
    return _bool(values.str.fullmatch(regex))


def _slot_mask(tags: pd.Series, slots: dict[int, str]) -> pd.Series:
    mask = pd.Series(True, index=tags.index)
    if not slots:
        return mask
    values = tags.astype("string").fillna("")
    long_enough = _bool(values.str.len() == TAG_LENGTH)
    for slot_index, char in slots.items():
        if not char:
            continue
        mask &= long_enough & _bool(values.str[slot_index] == char)
    return mask


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

def _sentence_index(tokens: pd.DataFrame) -> pd.Series:
    return (tokens["source_file"].astype("string").fillna("") + "␟"
            + tokens["document_id"].astype("string").fillna("") + "␟"
            + tokens["sentence_index"].astype("string").fillna(""))


def run_query(tokens: pd.DataFrame, query: Query) -> pd.DataFrame:
    """Return the matching tokens, each with its KWIC context."""
    if tokens is None or tokens.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    work = tokens.reset_index(drop=True)
    mask = pd.Series(True, index=work.index)

    if query.form:
        mask &= _text_mask(work["form"], query.form, query.form_mode,
                           ignore_diacritics=query.ignore_diacritics,
                           case_sensitive=query.case_sensitive)
    if query.lemma and "lemma" in work.columns:
        mask &= _text_mask(work["lemma"], query.lemma, query.lemma_mode, campo="lemma",
                           ignore_diacritics=query.ignore_diacritics,
                           case_sensitive=query.case_sensitive)
    if "postag" in work.columns:
        if query.postag_pattern:
            mask &= _postag_mask(work["postag"], query.postag_pattern)
        if query.slots:
            mask &= _slot_mask(work["postag"], query.slots)

    if query.relation and "relation" in work.columns:
        relations = work["relation"].astype("string").fillna("")
        if query.relation_exact:
            mask &= _bool(relations == query.relation)
        else:
            # A few dozen distinct labels behind 625,176 tokens: the suffixes are
            # stripped once per distinct label, not once per token.
            mask &= _bool(map_unique(relations, base_relation) == base_relation(query.relation))

    for column, value in (("autore", query.author), ("opera", query.work),
                          ("genere", query.genre), ("dialetto", query.dialect),
                          ("periodo", query.period), ("secolo", query.century)):
        if value and column in work.columns:
            mask &= _bool(work[column].astype("string").fillna("") == value)

    # Head-based filters need the tree, so they are resolved only if asked for.
    if (query.head_lemma or query.head_relation) and {"token_id", "head"} <= set(work.columns):
        prepared = work.copy()
        prepared["_sent"] = _sentence_index(prepared)
        prepared["_tid"] = pd.to_numeric(prepared["token_id"], errors="coerce")
        prepared["_head"] = pd.to_numeric(prepared["head"], errors="coerce")
        head_index = build_head_index(prepared)
        # Reading the head's value one row at a time would be slow; the gather
        # is a single numpy fancy index.
        positions = head_index.to_numpy()
        linked = positions >= 0
        if query.head_lemma and "lemma" in work.columns:
            lemmas = work["lemma"].astype("string").fillna("").to_numpy()
            head_lemma = pd.Series(
                np.where(linked, lemmas[positions], ""), index=work.index, dtype="string")
            mask &= _text_mask(head_lemma, query.head_lemma, "esatto", campo="lemma",
                               ignore_diacritics=query.ignore_diacritics,
                               case_sensitive=query.case_sensitive)
        if query.head_relation and "relation" in work.columns:
            relations = work["relation"].astype("string").fillna("").to_numpy()
            head_relation = pd.Series(
                np.where(linked, relations[positions], ""), index=work.index, dtype="string")
            mask &= _bool(map_unique(head_relation, base_relation)
                          == base_relation(query.head_relation))

    hits = work[mask]
    if hits.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    if len(hits) > query.limit:
        hits = hits.head(query.limit)

    return build_kwic(work, hits, context=query.context)


def build_kwic(tokens: pd.DataFrame, hits: pd.DataFrame, context: int = 6) -> pd.DataFrame:
    """Attach left and right context to every hit, without leaving the sentence."""
    if hits.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    forms = tokens["form"].astype("string").fillna("").to_numpy()
    sentences = _sentence_index(tokens).to_numpy()
    total = len(forms)

    # Columns are pulled out as arrays once. Reading them through ``.iloc[i]``
    # inside the loop builds a fresh Series per hit, which on a twenty-thousand
    # hit result set costs more than the whole rest of the search.
    #
    # They are also taken at the hit positions rather than converted whole:
    # converting nineteen output columns of an Arrow-backed table whole means
    # boxing 625,176 rows each, to keep the twenty thousand that were asked for.
    # Only the two the loop reads by row number stay full length.
    selection = hits.index

    def _column(name: str, default: object = ""):
        if name in tokens.columns:
            return tokens[name].take(selection).to_numpy()
        return [default] * len(selection)

    columns = {name: _column(name) for name in
               ("form", "lemma", "postag", "relation", "head", "autore", "opera",
                "locus", "periodo", "dialetto", "genere", "document_id",
                "sentence_id", "token_id")}
    scanned_tags = tokens["postag"].take(selection).to_numpy() if "postag" in tokens.columns else [""] * len(selection)
    scanned_relations = tokens["relation"].take(selection).to_numpy() if "relation" in tokens.columns else [""] * len(selection)

    # Glosses are expensive and highly repetitive: memoise per distinct value.
    tag_gloss: dict[object, str] = {}
    relation_gloss: dict[object, str] = {}

    left: list[str] = []
    centre: list[str] = []
    right: list[str] = []
    analyses: list[str] = []
    functions: list[str] = []

    for hit, position in enumerate(selection):
        sentence = sentences[position]
        low = position
        while low > 0 and position - low < context and sentences[low - 1] == sentence:
            low -= 1
        high = position
        while high < total - 1 and high - position < context and sentences[high + 1] == sentence:
            high += 1
        left.append(" ".join(forms[low:position]))
        centre.append(forms[position])
        right.append(" ".join(forms[position + 1 : high + 1]))

        tag = scanned_tags[hit]
        if tag not in tag_gloss:
            tag_gloss[tag] = describe_postag(tag)
        analyses.append(tag_gloss[tag])

        relation = scanned_relations[hit]
        if relation not in relation_gloss:
            relation_gloss[relation] = describe_relation(relation)
        functions.append(relation_gloss[relation])

    return pd.DataFrame({
        "sinistra": left,
        "parola": centre,
        "destra": right,
        "forma": columns["form"],
        "lemma": columns["lemma"],
        "postag": columns["postag"],
        "analisi": analyses,
        "relazione": columns["relation"],
        "funzione": functions,
        "testa": columns["head"],
        "autore": columns["autore"],
        "opera": columns["opera"],
        "locus": columns["locus"],
        "periodo": columns["periodo"],
        "dialetto": columns["dialetto"],
        "genere": columns["genere"],
        "documento": columns["document_id"],
        "frase": columns["sentence_id"],
        "token": columns["token_id"],
    }, columns=RESULT_COLUMNS).reset_index(drop=True)


# ---------------------------------------------------------------------------
# A form, or a lemma: the occurrences first, what the word is afterwards
# ---------------------------------------------------------------------------
#
# This is the search the interface offers, and it is deliberately narrower than
# :func:`run_query` above. Two decisions shape it, and both come from watching
# a philologist at work.
#
# *One field at a time.* A form search and a lemma search are two different
# questions — "where does this written word occur" and "where does this word
# occur, in any of its forms" — and joining them with an implicit AND answers
# neither. A query here therefore names exactly one field; there is no way to
# express "form X and lemma Y", because nobody meant it.
#
# *The occurrences first.* What comes back is one row per occurrence with the
# sentence around it, which is the list a reader chooses from. Everything the
# annotation says about a single chosen occurrence — its morphology, its
# syntactic function, its lemma, the lemma of its head, its author — is a
# second step, and :func:`detail_of` is the whole of it.

#: Query field -> the column of the treebank it reads. The keys are the values
#: the interface stores, not the words it shows: those are translated.
FIELD_COLUMNS = {"forma": "form", "form": "form", "lemma": "lemma"}

#: What one occurrence carries. The first three are the list the reader picks
#: from; the rest are what :func:`detail_of` needs and are not meant to be
#: shown as a table.
OCCURRENCE_COLUMNS = [
    "n.", "forma", "contesto",
    "lemma", "postag", "relazione", "lemma_testa", "autore",
]

#: The list, as it is shown: the occurrence, the word, the sentence it is in.
LIST_COLUMNS = ["n.", "forma", "contesto"]

#: The five things the detail shows, in order. There is no sixth on purpose.
DETAIL_FIELDS = (
    "morfologia",
    "funzione sintattica",
    "lemma",
    "lemma della testa",
    "autore",
)


@dataclass
class WordQuery:
    """One word search: one field, one way of matching it.

    *field* is ``"forma"`` or ``"lemma"`` and never both — that is the whole
    point of the class. *mode* is one of :data:`WORD_MATCH_MODES`. *text* may
    be written in Greek with or without diacritics, or in Latin letters.
    """

    text: str = ""
    field: str = "forma"
    mode: str = "esatto"
    context_words: int = 25
    limit: int = 20_000

    def is_empty(self) -> bool:
        return not self.text.strip()

    def describe(self) -> str:
        """A one-line statement of what was asked, in the interface's language."""
        if self.is_empty():
            return _t("search.query.none", "no search")
        field = _t(f"search.field.{self.column_name}",
                   "lemma" if self.column_name == "lemma" else "forma")
        return _t("search.query.one", "{0} {1} “{2}”",
                  field, _mode_name(self.mode), self.text.strip())

    @property
    def column_name(self) -> str:
        """``"form"`` or ``"lemma"``: the column this query reads, and only it."""
        return FIELD_COLUMNS.get(self.field, "form")


def _sentence_key(tokens: pd.DataFrame) -> pd.Series:
    """A value that changes exactly when the sentence changes.

    Written to work on whatever identifying columns the table happens to carry:
    the corrected corpus, a slice, a table assembled by hand for a test. A
    context that ran past the end of its sentence would be a quotation of
    something the author did not write.
    """
    parts = [tokens[name].astype("string").fillna("")
             for name in ("source_file", "document_id", "sentence_index",
                          "sentence_id")
             if name in tokens.columns]
    if not parts:
        return pd.Series([""] * len(tokens), index=tokens.index, dtype="string")
    joined = parts[0]
    for part in parts[1:]:
        joined = joined + "␟" + part
    return joined


def _context_of(forms, sentences, position: int, window: int) -> str:
    """The sentence around one token, with the token itself marked.

    Bounded by the sentence on both sides, and by *window* words, so that a
    badly segmented document cannot put a page of prose into one table cell.
    The cut, when there is one, is shown: a silently shortened quotation is a
    misquotation.
    """
    total = len(forms)
    sentence = sentences[position]
    low = position
    while low > 0 and sentences[low - 1] == sentence and position - low < window:
        low -= 1
    high = position
    while high < total - 1 and sentences[high + 1] == sentence and high - position < window:
        high += 1
    pieces: list[str] = []
    if low > 0 and sentences[low - 1] == sentence:
        pieces.append("…")
    pieces.extend(str(form) for form in forms[low:position])
    pieces.append(f"«{forms[position]}»")
    pieces.extend(str(form) for form in forms[position + 1: high + 1])
    if high < total - 1 and sentences[high + 1] == sentence:
        pieces.append("…")
    return " ".join(piece for piece in pieces if piece)


def _head_lemmas(work: pd.DataFrame, sentences: pd.Series, positions) -> list[str]:
    """The lemma of each token's head, looked up inside its own sentence.

    A head is an identifier, not a row number: ``head=3`` means "the token whose
    id is 3 *in this sentence*", and the same id occurs once per sentence in the
    corpus. Resolving it therefore has to be done per sentence, which is exactly
    what :func:`syntax.build_head_index` does.
    """
    if "lemma" not in work.columns or not {"token_id", "head"} <= set(work.columns):
        return [""] * len(positions)
    helper = pd.DataFrame({
        "_sent": sentences,
        "_tid": pd.to_numeric(work["token_id"], errors="coerce"),
        "_head": pd.to_numeric(work["head"], errors="coerce"),
    })
    parents = build_head_index(helper).to_numpy()
    lemmas = work["lemma"].astype("string").fillna("").to_numpy()
    return [str(lemmas[parents[position]]) if parents[position] >= 0 else ""
            for position in positions]


def find_occurrences(tokens: pd.DataFrame, query: WordQuery) -> pd.DataFrame:
    """Every occurrence of one word, each with the sentence it appears in.

    Reads exactly one column of the corpus — the one *query* names — and never
    modifies the corpus: the folded keys the matching needs are built beside it
    and thrown away.
    """
    empty = pd.DataFrame(columns=OCCURRENCE_COLUMNS)
    if tokens is None or tokens.empty or query is None or query.is_empty():
        return empty
    column = query.column_name
    if column not in tokens.columns:
        return empty

    work = tokens.reset_index(drop=True)
    mask = key_mask(work[column], query.text.strip(), query.mode,
                    campo="lemma" if column == "lemma" else "")
    positions = np.flatnonzero(np.asarray(mask, dtype=bool))
    if positions.size == 0:
        return empty
    if query.limit and positions.size > query.limit:
        positions = positions[: query.limit]

    # Two columns are read at every row, because the context of a hit is made
    # of its neighbours: the forms and the sentence each token belongs to.
    # Everything else is read only where the hits are, and is therefore taken
    # first and converted afterwards — converting an Arrow-backed column whole
    # in order to keep twenty of its rows is most of what a search costs.
    def _taken(name: str) -> list[str]:
        if name not in work.columns:
            return [""] * positions.size
        values = work[name].take(positions).astype("string").fillna("")
        return [str(value) for value in values]

    forms = (work["form"].astype("string").fillna("").to_numpy()
             if "form" in work.columns else np.full(len(work), "", dtype=object))
    sentences = _sentence_key(work)
    sentence_values = sentences.to_numpy()

    return pd.DataFrame({
        "n.": np.arange(1, positions.size + 1),
        "forma": [str(forms[position]) for position in positions],
        "contesto": [_context_of(forms, sentence_values, position,
                                 query.context_words) for position in positions],
        "lemma": _taken("lemma"),
        "postag": _taken("postag"),
        "relazione": _taken("relation"),
        "lemma_testa": _head_lemmas(work, sentences, positions),
        "autore": _taken("autore"),
    }, columns=OCCURRENCE_COLUMNS)


def find_forms(tokens: pd.DataFrame, text: str, mode: str = "esatto",
               **options) -> pd.DataFrame:
    """Every occurrence of a written form. Never looks at the lemma column."""
    return find_occurrences(tokens, WordQuery(text=text, field="forma",
                                              mode=mode, **options))


def find_lemmas(tokens: pd.DataFrame, text: str, mode: str = "esatto",
                **options) -> pd.DataFrame:
    """Every occurrence of a lemma. Never looks at the form column."""
    return find_occurrences(tokens, WordQuery(text=text, field="lemma",
                                              mode=mode, **options))


def _cell(row: object, name: str) -> str:
    """One field of an occurrence, as text, whatever shape the row arrives in."""
    try:
        value = row[name]
    except (KeyError, IndexError, TypeError):
        return ""
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def detail_of(row: object, lang: str = "it") -> dict[str, str]:
    """What the chosen occurrence is: five things, and nothing else.

    Morphology — the nine-character tag read out as the categories it stands
    for, with the tag itself in brackets so that the two can be checked against
    each other. Syntactic function — the relation, likewise. The lemma. The
    lemma of the head, which is what makes a dependency readable: ἀνθρώπου is
    not "a genitive", it is "a genitive under φύσις". And the author.

    Nothing else, and that is a decision rather than an omission: everything
    else the row carries — document, sentence number, token number, work,
    period — answers a question about the *file*, and the question here is
    about the word.
    """
    postag = _cell(row, "postag")
    morphology = describe_postag(postag, lang)
    if len(postag) == TAG_LENGTH:
        # A well-formed tag is shown twice, read out and as it is written. A
        # malformed one is not: ``describe_postag`` has already said so, in
        # words, and repeating the string would bury the sentence that matters.
        morphology = f"{morphology}  ({postag})"

    relation = _cell(row, "relazione") or _cell(row, "relation")
    function = describe_relation(relation, lang) if relation else ""
    if relation and function != relation:
        function = f"{function}  ({relation})"

    dash = "—"
    return {
        "morfologia": morphology or dash,
        "funzione sintattica": function or dash,
        "lemma": _cell(row, "lemma") or dash,
        "lemma della testa": _cell(row, "lemma_testa") or dash,
        "autore": _cell(row, "autore") or dash,
    }


# ---------------------------------------------------------------------------
# Every search can become a table
# ---------------------------------------------------------------------------

GROUPABLE_FIELDS = {
    "forma": "forma",
    "lemma": "lemma",
    "postag": "postag",
    "analisi morfologica": "analisi",
    "relazione": "relazione",
    "funzione sintattica": "funzione",
    "autore": "autore",
    "opera": "opera",
    "genere": "genere",
    "dialetto": "dialetto",
    "periodo": "periodo",
    "documento": "documento",
}


def aggregate_results(
    results: pd.DataFrame,
    by: str | list[str],
    *,
    total_tokens: int | None = None,
) -> pd.DataFrame:
    """Turn a result set into a frequency table.

    When *total_tokens* is given, a normalised column is added: occurrences per
    ten thousand tokens, which is the only figure that can be honestly compared
    between an author represented by 100 000 tokens and one represented by 3 000.
    """
    if results is None or results.empty:
        return pd.DataFrame()
    fields = [by] if isinstance(by, str) else list(by)
    columns = [GROUPABLE_FIELDS.get(field, field) for field in fields]
    columns = [column for column in columns if column in results.columns]
    if not columns:
        return pd.DataFrame()

    table = (results.groupby(columns, dropna=False, sort=False)
             .size().reset_index(name="occorrenze")
             .sort_values("occorrenze", ascending=False))
    table["%"] = (table["occorrenze"] / table["occorrenze"].sum() * 100).round(2)
    if total_tokens:
        table["per 10.000 token"] = (
            table["occorrenze"] / total_tokens * 10_000).round(2)
    return table.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Convenience: things a philologist asks often enough to deserve a button
# ---------------------------------------------------------------------------

def who_uses_it_most(
    tokens: pd.DataFrame,
    *,
    lemma: str = "",
    form: str = "",
    group_by: str = "autore",
) -> pd.DataFrame:
    """Which author (or work, or genre) uses this word most — honestly.

    "Most" is ambiguous and the ambiguity matters: Polybius uses everything most,
    because there is more Polybius. The table therefore gives both the raw count
    and the rate per ten thousand tokens, and sorts by the rate.
    """
    if tokens is None or tokens.empty:
        return pd.DataFrame()
    if group_by not in tokens.columns:
        return pd.DataFrame()

    if lemma:
        matches = tokens["lemma"].astype("string").fillna("") == lemma
    elif form:
        matches = tokens["form"].astype("string").fillna("") == form
    else:
        return pd.DataFrame()

    sizes = tokens.groupby(group_by, dropna=False).size().rename("token_totali")
    counts = (tokens[matches].groupby(group_by, dropna=False)
              .size().rename("occorrenze"))
    table = pd.concat([counts, sizes], axis=1).fillna(0)
    table = table[table["token_totali"] > 0].reset_index()
    table["occorrenze"] = table["occorrenze"].astype(int)
    table["token_totali"] = table["token_totali"].astype(int)
    table["per 10.000 token"] = (
        table["occorrenze"] / table["token_totali"] * 10_000).round(2)
    return table.sort_values("per 10.000 token", ascending=False).reset_index(drop=True)


def concordance_of_lemma(tokens: pd.DataFrame, lemma: str, context: int = 8) -> pd.DataFrame:
    return run_query(tokens, Query(lemma=lemma, lemma_mode="esatto", context=context))


def find_construction(tokens: pd.DataFrame, name: str) -> pd.DataFrame:
    """Named Greek constructions, expressed as tree queries.

    These are the patterns a Greek syntax course spends a term on, and each is
    a handful of conditions on ``(postag, relation, head)``.
    """
    if tokens is None or tokens.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    needed = {"postag", "relation", "token_id", "head"}
    if not needed <= set(tokens.columns):
        return pd.DataFrame(columns=RESULT_COLUMNS)

    work = tokens.reset_index(drop=True).copy()
    work["_sent"] = _sentence_index(work)
    work["_tid"] = pd.to_numeric(work["token_id"], errors="coerce")
    work["_head"] = pd.to_numeric(work["head"], errors="coerce")
    head_index = build_head_index(work)

    # Every slot of the tag is a property of the tag, and Gorman spells 625,176
    # records with 1,185 distinct tags: each slot is read once per distinct tag,
    # not once per record.
    tags = work["postag"].astype("string").fillna("")
    codes, uniques = pd.factorize(tags, use_na_sentinel=False)
    distinct = np.asarray(uniques, dtype=object)

    def _slot(index: int) -> pd.Series:
        characters = [tag[index] if len(tag) == TAG_LENGTH else "" for tag in distinct]
        return pd.Series(pd.array(characters, dtype="string").take(codes), index=work.index)

    pos = _slot(0)
    mood = _slot(4)
    case = _slot(CASE_SLOT)
    gender = _slot(6)
    number = _slot(2)
    relations = map_unique(work["relation"].astype("string").fillna(""), base_relation)

    pos_of = pos.to_numpy()
    case_of = case.to_numpy()
    gender_of = gender.to_numpy()
    number_of = number.to_numpy()
    relation_of = relations.to_numpy()
    parent_of = head_index.to_numpy()
    linked = parent_of >= 0

    def _has_child(child_matches) -> pd.Series:
        """Rows with at least one child the array marks.

        The readable version built a dict of child lists and then called a Python
        predicate once per (parent, child) pair, reading each value out of an
        Arrow-backed column with ``.iat``: 4.2 s for a table the interface offers
        as a button.  Marking the children first and scattering onto the parents
        answers the same question in one pass.
        """
        matched = np.zeros(len(work), dtype=bool)
        matched[parent_of[linked & child_matches]] = True
        return pd.Series(matched, index=work.index)

    participle = (pos == "v") & (mood == "p")
    infinitive = (pos == "v") & (mood == "n")

    if name == "genitivo assoluto":
        mask = (participle & (case == "g") & (relations == "ADV")
                & _has_child((relation_of == "SBJ") & (case_of == "g")))
    elif name == "accusativo assoluto":
        mask = (participle & (case == "a") & (gender == "n") & (relations == "ADV"))
    elif name == "accusativo con infinito":
        mask = infinitive & _has_child((relation_of == "SBJ") & (case_of == "a"))
    elif name == "infinito articolare":
        mask = infinitive & _has_child(pos_of == "l")
    elif name == "participio sostantivato":
        mask = participle & _has_child(pos_of == "l")
    elif name == "participio predicativo":
        mask = participle & work["relation"].astype("string").fillna("").isin(
            {"ATV", "AtvV", "ATV_CO", "AtvV_CO"})
    elif name == "perifrastica con εἰμί":
        finite_eimi = (pos == "v") & (mood.isin(list("isom"))) & (
            work["lemma"].astype("string").fillna("") == "εἰμί")
        mask = finite_eimi & _has_child(np.asarray(participle, dtype=bool))
    elif name == "schema attico":
        # Neuter plural subject with a singular verb: the classic figure.
        mask = ((pos == "v") & mood.isin(list("isom")) & (number == "s")
                & _has_child((relation_of == "SBJ") & (gender_of == "n")
                                       & (number_of == "p")))
    elif name == "ἄν + modo":
        mask = work["lemma"].astype("string").fillna("").isin({"ἄν", "ἅν", "κέ", "κέν"})
    elif name == "soggetto sottinteso":
        finite = (pos == "v") & mood.isin(list("isom"))
        has_subject = _has_child(relation_of == "SBJ")
        mask = finite & ~has_subject
    else:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    return build_kwic(work, work[mask.fillna(False)], context=8)


CONSTRUCTIONS = [
    "genitivo assoluto",
    "accusativo assoluto",
    "accusativo con infinito",
    "infinito articolare",
    "participio sostantivato",
    "participio predicativo",
    "perifrastica con εἰμί",
    "schema attico",
    "ἄν + modo",
    "soggetto sottinteso",
]

CONSTRUCTION_HELP: dict[str, str] = {
    "genitivo assoluto":
        "Participio al genitivo con relazione avverbiale che regge un soggetto "
        "anch'esso al genitivo: la costruzione assoluta per eccellenza.",
    "accusativo assoluto":
        "Participio neutro all'accusativo in funzione avverbiale, tipico dei "
        "verbi impersonali (δέον, ἐξόν).",
    "accusativo con infinito":
        "Infinito che regge un soggetto all'accusativo: la proposizione "
        "infinitiva del greco.",
    "infinito articolare":
        "Infinito preceduto dall'articolo, sostantivato.",
    "participio sostantivato":
        "Participio preceduto dall'articolo: «coloro che…».",
    "participio predicativo":
        "Participio in relazione ATV o AtvV, predicativo del soggetto o "
        "dell'oggetto.",
    "perifrastica con εἰμί":
        "Forma finita di εἰμί che regge un participio: perifrastica.",
    "schema attico":
        "Soggetto neutro plurale con verbo al singolare: il σχῆμα Ἀττικόν. "
        "Utile due volte, come figura e come controllo dell'annotazione.",
    "ἄν + modo":
        "Tutte le occorrenze della particella modale: incrociandole con il modo "
        "del verbo reggente si ottiene la tabella dei periodi ipotetici.",
    "soggetto sottinteso":
        "Verbi finiti privi di un soggetto espresso: la misura del pro-drop, "
        "che varia molto per genere e per persona.",
}
