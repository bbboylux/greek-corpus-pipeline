"""The counting units, defined once for the whole program.

Without a single definition the same word would mean different things depending
on who pronounced it. “Word” in the Overview would mean *imported record minus
punctuation and written placeholders* ``[n]``; inside :mod:`variation` it would
mean something else, computed by :func:`variation._content_tokens`; and the
article would use a third. Three definitions would give three numbers, and none
would be written beside the number it produced.

Five units, one definition each, and three elementary predicates from which all
of them descend.

**The hierarchy**

.. code-block:: text

    imported_records
      → general filters of the user
    active_records
      → lexical eligibility
    words

The delicate point is the second step, and it must be stated precisely because
it is the error that this module exists to prevent. The ``active_records``
depend on the filters: if the user switches off the exclusion of technical
records, the elliptic nodes *come back* among the active records, and rightly
so, because the user wants to see them in the structural diagnosis. The
``words`` do not. Being a word of the text is a property of the record, not a
display preference: an elliptic node does not become a word because someone has
unticked a box. :func:`is_word` always excludes it, and the lexical statistics
are therefore invariant with respect to that filter.

**The two syntactic units** — ``analyzable_links`` and
``analyzable_sentences`` — follow the same logic: an arc is analyzable when its
head really exists in the same sentence and is not a technical record, because
an arc that points to an elliptic node parked after the full stop does not
measure word order.

**The sentence key** is not ``sentence_id``.  In Gorman ``sentence_id`` takes
564 distinct values over 26,616 sentences, because it is the number of the
sentence *inside its file*: using it alone as a grouping key merges sentences of
different documents. The key is :func:`sentence_key`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .agdt_schema import PUNCTUATION_RELATIONS, TAG_LENGTH
from .postag import SPECIALISED_CHARACTERS as _SPECIALISED
from .postag import VALID_CHARACTERS as _VALID

_VALID_POS = _VALID.get(0, set())
_LOCAL_POS = _SPECIALISED.get(0, set())

__all__ = [
    "INTERPRETABLE_POS",
    "PUNCTUATION_POS",
    "PUNCTUATION_RELATIONS",
    "SENTENCE_KEY_COLUMNS",
    "SENTENCE_ORDER",
    "Measure",
    "Units",
    "is_punctuation",
    "is_structural_punctuation",
    "is_technical_record",
    "is_word",
    "sentence_key",
    "sentence_positions",
    "build_units",
    "analyzable_link_mask",
    "analyzable_sentence_keys",
]


#: The value that AGDT writes in the first position of the label for punctuation.
PUNCTUATION_POS = "u"

#: The three relations with which AGDT attaches a punctuation mark to the tree,
#: imported from :mod:`agdt_schema`, which is where the scheme is declared as data.
#: They are needed because punctuation is not recognised only from the label: in
#: the six strata studied, 58 marks in Gorman and 21 in Pedalion (none in GLAUx)
#: have an empty or malformed tag and would escape a test on the first position
#: alone. Redeclaring them here would create the second definition that this
#: module exists to remove.

#: The values of the first position of the label that make it possible to classify
#: the record as a word of a linguistic category. It serves a single question:
#: *does this label say anything?*
#:
#: Inside there are the twelve values of the AGDT inventory and the local
#: extensions that a resource declares and documents. Today the only one is
#: Pedalion's ``b``, which marks 8,555 active records there and 1,405 and 2,131 in the
#: two manual samples of GLAUx: it does not belong to the standard inventory, but it is
#: a category of words that the project documents, and treating it as an empty
#: field would be false.
#:
#: Two values that look like candidates are left out, and are not. ``z`` marks a
#: record that *is not* a word of the text — lacunae, unannotated passages — and
#: :func:`is_technical_record` intercepts it first: putting it here would say that
#: it is a linguistic category, which it is not. ``x`` is the value with which AGDT
#: declares that it cannot classify the record, and a label that says “I do not
#: know” does not stop the relation from speaking.
INTERPRETABLE_POS = (frozenset(_VALID_POS) | frozenset(_LOCAL_POS)) - {"z"}

#: The columns that identify a sentence. In this order, and all three.
SENTENCE_KEY_COLUMNS = ("source_file", "document_id", "sentence_index")

#: The sort order that puts the tokens of the corpus in reading order: the
#: sentences in the order in which they stand in the files, and within each
#: sentence the tokens in the order in which they stand in the sentence. It serves
#: whoever looks at the neighbours of a token, and must be used **with**
#: :data:`SENTENCE_KEY_COLUMNS`: sorting without ``document_id`` interleaves the
#: sentences of two documents that live in the same file, and then two tokens that
#: the text never placed next to each other turn out to be adjacent.
SENTENCE_ORDER = SENTENCE_KEY_COLUMNS + ("token_index",)

#: The separator of composite keys: a character that does not occur in the data.
_SEP = "␟"

#: The written placeholder of an elliptic node, from ``[0]`` to ``[20]``.
_PLACEHOLDER_FORM = re.compile(r"^\[\d+\]$")

#: The Leuven lacuna marker, written ``G`` or ``G?`` by both GLAUx and Pedalion, with the
#: label ``z--------``.
_GAP_FORM = re.compile(r"^[Gg]\??$")


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    """The column as a string, never null, with the index of the frame."""
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].astype("string").fillna("")


def _bool(values) -> np.ndarray:
    """A true boolean array, without null values.

    The columns of the corpus come from Arrow and carry ``pd.NA``: an ``&`` between
    two nullable masks raises “boolean value of NA is ambiguous” three calls away
    from the point where the null entered. All the masks of this module pass through
    here.
    """
    return np.asarray(pd.Series(values).fillna(False), dtype=bool)


# ---------------------------------------------------------------------------
# The three elementary predicates
# ---------------------------------------------------------------------------

def is_technical_record(tokens: pd.DataFrame) -> pd.Series:
    """The records that the file declares not to be words of the text.

    Five ways of saying so, and the predicate must honour them all because the three
    corpora use three different ones:

    * the ``artificial`` attribute filled in — the authoritative route, and often on
      a node that carries a real word, because where the annotator supplied the
      understood verb the form is ἐστιν and not ``[0]``. Gorman does this 5,691
      times;
    * the written form ``[0]``, ``[1]``… ``[20]``;
    * the lacuna marker ``G`` or ``G?``;
    * form and label both empty — GLAUx writes the passages left out of the
      annotation this way, keeping the word between braces in ``form_original``;
    * the label that begins with ``z``, which the catalogue declares a marker of a
      non-lexical record.

    None of these is a defect, and none produces a diagnostic finding: recognising
    them is preprocessing, not diagnosis.
    """
    if tokens.empty:
        return pd.Series(False, index=tokens.index, dtype=bool)

    mask = np.zeros(len(tokens), dtype=bool)
    if "artificial" in tokens.columns:
        mask |= _bool(_text(tokens, "artificial").str.strip() != "")

    form = _text(tokens, "form").str.strip()
    postag = _text(tokens, "postag").str.strip()
    if "form" in tokens.columns:
        mask |= _bool(form.str.match(_PLACEHOLDER_FORM.pattern))
        mask |= _bool(form.str.match(_GAP_FORM.pattern))
        mask |= _bool((form == "") & (postag == ""))
    if "postag" in tokens.columns:
        mask |= _bool(postag.str.startswith("z"))
    return pd.Series(mask, index=tokens.index, dtype=bool)


def is_punctuation(tokens: pd.DataFrame) -> pd.Series:
    """The records that are a punctuation mark and not a word of the text.

    Two tests, in *or*.  The label that begins with ``u`` is the prescribed one; the
    relation ``AuxG``/``AuxK``/``AuxX`` recovers the marks whose tag is malformed —
    71 records in Gorman, 48 in Pedalion — which with the first test alone would end
    up counted among the words.

    A single principle, not a ladder of cases: **the label decides whenever it says
    something; the relation speaks only in the silence of the label.**

    Two directions descend from it.  A label that says ``u`` closes the question:
    the record is a mark, whatever relation it carries.  A label that says a
    linguistic category — including the documented local extensions such as ``b`` —
    closes the question from the other side: the record is a word, whatever relation
    it carries.  Only where the label says nothing does the relation have a voice.

    Why the fallback is conditional: applied unconditionally, it would remove from
    the words 71 records of Gorman and 48 of Pedalion, and among them there are
    ``δὲ``, ``οὔ``, ``οὖν`` with relation ``AuxK`` and, in Pedalion, ``καὶ``,
    ``ὥσπερ``, ``δʼ`` with ``AuxG``.  They are Greek words that have been assigned a
    punctuation relation: that is an anomaly of the syntactic annotation, which the
    catalogue reports on its own account, and it does not retroactively change the
    lexical nature of the record.

    Why the test is on the inventory and not on being just any letter: ``e`` is a
    letter and is not a part of speech, and in Gorman 17 full stops and semicolons
    carry ``e--------``.  They are the same 17 records that the check “PoS e on a
    punctuation mark” reports.

    What the first direction costs, measured: over a million and a half records of
    the six corpora, the ``u`` labels on a form that is not a mark are four — ``ἢ``,
    ``Εἰ``, ``ΘΑ``, ``πολύχουν``.  The thousands of ``u`` on Greek forms are the ano
    teleia ``·`` and the question mark ``;``, which are in the Greek Unicode block
    and are punctuation to all intents and purposes.

    It answers the question “is this record a word of the text?”, and for that
    question a punctuation mark never is one, whatever it does in the tree.  For the
    different question “is this record the root of the sentence?”
    :func:`is_structural_punctuation` is needed, and the two must not be exchanged.
    """
    if tokens.empty:
        return pd.Series(False, index=tokens.index, dtype=bool)
    postag = _text(tokens, "postag")
    by_tag = _bool(postag.str[0] == PUNCTUATION_POS)
    # A label speaks when it has the prescribed length and the first position carries
    # a value of the inventory: it then already says which part of speech it is, and
    # the relation has no say. The test is on the inventory and not on being just any
    # letter, because ``e`` is a letter and is not a part of speech: in Gorman 17 full
    # stops and semicolons carry ``e--------``, and with the alphabetic test alone
    # they would re-enter among the words. They are the same 17 records that the
    # check “PoS e on a punctuation mark” reports.
    speaks = _bool(postag.str.len() == TAG_LENGTH) & _bool(
        postag.str[0].isin(INTERPRETABLE_POS))
    by_relation = _bool(_text(tokens, "relation").isin(PUNCTUATION_RELATIONS))
    return pd.Series(by_tag | (by_relation & ~speaks),
                     index=tokens.index, dtype=bool)


def is_structural_punctuation(tokens: pd.DataFrame) -> pd.Series:
    """The marks that do nothing but punctuation in the tree.

    Only the relation, not the label.  The difference from :func:`is_punctuation` is
    not a nuance: in AGDT asyndetic coordination is annotated by making the mark
    itself the coordinating node — “ἄνδρες, γυναῖκες, παῖδες”, where the comma
    carries ``COORD`` and governs the conjuncts — and that comma, if it sits at
    ``head = 0``, **is** the root of the sentence.

    Counting it among the punctuation because of its tag would remove the root from
    197 sentences of Gorman, 233 of Pedalion, 24 and 28 of the two manual samples of
    GLAUx: 144 of the 197 carry ``COORD`` and 41 ``APOS``.  They are nodes that do
    syntactic work, and for the structure of the tree they must be read as such.
    """
    if tokens.empty:
        return pd.Series(False, index=tokens.index, dtype=bool)
    return pd.Series(_bool(_text(tokens, "relation").isin(PUNCTUATION_RELATIONS)),
                     index=tokens.index, dtype=bool)


def is_word(tokens: pd.DataFrame) -> pd.Series:
    """The records that are a word of the text.

    Neither technical nor punctuation.  Note that this predicate **does not look at
    the filters of the user**: it is the intrinsic lexical definition, and its
    invariance with respect to the ticks of the interface is the reason why it
    exists.
    """
    if tokens.empty:
        return pd.Series(False, index=tokens.index, dtype=bool)
    technical = np.asarray(is_technical_record(tokens), dtype=bool)
    punctuation = np.asarray(is_punctuation(tokens), dtype=bool)
    return pd.Series(~(technical | punctuation), index=tokens.index, dtype=bool)


# ---------------------------------------------------------------------------
# The sentence key
# ---------------------------------------------------------------------------

def sentence_key(tokens: pd.DataFrame) -> pd.Series:
    """The key that identifies a sentence, to be used everywhere.

    ``source_file``, ``document_id`` and ``sentence_index`` concatenated.  The field
    ``sentence_id``, by itself, does **not** identify a sentence: it is the number of
    the sentence inside its file, and in Gorman it takes 564 distinct values for
    26,616 sentences.  Grouping on it merges the homonymous sentences of 158
    documents.
    """
    if tokens.empty:
        return pd.Series([], index=tokens.index, dtype="string")
    parts = [_text(tokens, column) for column in SENTENCE_KEY_COLUMNS]
    key = parts[0]
    for part in parts[1:]:
        key = key + _SEP + part
    return key


def sentence_positions(tokens: pd.DataFrame) -> pd.Series:
    """The position of each token inside its sentence, counted from zero.

    In reading order, that is by increasing ``token_index`` inside the canonical
    sentence.  It serves whoever has to bring back to the record an analysis
    produced outside the program: the position in the sentence is a stable key,
    whereas the form is not, because a difference of encoding or a cleaned-up space
    changes it without the token having changed.
    """
    if tokens.empty:
        return pd.Series([], index=tokens.index, dtype="int64")
    ordine = pd.to_numeric(
        tokens.get("token_index", pd.Series(range(len(tokens)), index=tokens.index)),
        errors="coerce").fillna(0)
    frame = pd.DataFrame({"_k": sentence_key(tokens), "_o": ordine},
                         index=tokens.index)
    ordinato = frame.sort_values(["_k", "_o"], kind="stable")
    posizioni = ordinato.groupby("_k", sort=False).cumcount()
    return posizioni.reindex(tokens.index).astype("int64")


# ---------------------------------------------------------------------------
# Analyzable arcs and sentences
# ---------------------------------------------------------------------------

def analyzable_link_mask(
    active: pd.DataFrame,
    *,
    within: pd.DataFrame | None = None,
) -> pd.Series:
    """Which active records carry a usable arc to their head.

    An arc is analyzable when the declared head exists as a record of the same
    sentence **inside the reference set**.  The value ``head = 0`` produces no arc:
    zero is the root, which is a fictitious attachment point and not another record.

    *within* is the set in which the head must be found; absent, it is ``active``
    itself.  Passing the active records means discarding the arcs that point to a
    technical node: they are 16,680 in Gorman, 9,470 in Pedalion and 14,879 in
    the automatic GLAUx sample, and almost all point to an elliptic node parked
    after the full stop,
    whose position in the file is not that of the understood element in the text.
    """
    if active.empty or not {"head", "token_id"} <= set(active.columns):
        return pd.Series(False, index=active.index, dtype=bool)

    target = active if within is None else within
    keys = sentence_key(active)
    heads = pd.to_numeric(active["head"], errors="coerce")

    present = set(zip(
        sentence_key(target).to_numpy(),
        pd.to_numeric(target["token_id"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
    ))
    wanted = zip(keys.to_numpy(), heads.fillna(-1).astype("int64").to_numpy())
    usable = [head > 0 and (key, head) in present for key, head in wanted]
    return pd.Series(usable, index=active.index, dtype=bool)


def analyzable_sentence_keys(tokens: pd.DataFrame) -> set[str]:
    """The sentences that have a usable structure.

    Two requirements, and they are the two that make the tree readable: a single
    root that is not punctuation — the AGDT scheme prescribes one — and no arc that
    points to an identifier absent from the sentence.  The first requirement must be
    measured excluding punctuation because in AGDT a mark can be attached to ``0``
    without thereby being a second root: without that exclusion Gorman would appear
    to have 88,692 roots over 26,616 sentences.

    The punctuation to exclude here is that of :func:`is_structural_punctuation`,
    not that of :func:`is_word`: a comma that coordinates is a node of the tree and
    can be its root.
    """
    if tokens.empty or "head" not in tokens.columns:
        return set()

    keys = sentence_key(tokens)
    heads = pd.to_numeric(tokens["head"], errors="coerce")
    punctuation = np.asarray(is_structural_punctuation(tokens), dtype=bool)

    roots = pd.Series(_bool(heads.notna()) & _bool(heads == 0) & ~punctuation,
                      index=tokens.index)
    per_sentence = roots.groupby(keys, sort=False).sum()

    present = set(zip(
        keys.to_numpy(),
        pd.to_numeric(tokens["token_id"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
    )) if "token_id" in tokens.columns else set()
    dangling = pd.Series(
        [1 if (head > 0 and (key, head) not in present) else 0
         for key, head in zip(keys.to_numpy(), heads.fillna(-1).astype("int64").to_numpy())],
        index=tokens.index,
    ).groupby(keys, sort=False).sum()

    single_root = set(per_sentence[per_sentence == 1].index)
    intact = set(dangling[dangling == 0].index)
    return single_root & intact


# ---------------------------------------------------------------------------
# The container of the five units
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Units:
    """The five canonical units of a corpus, computed once.

    Every analysis receives this object and takes the unit that concerns it, instead
    of rebuilding the universe with its own filter lines.  The names of the
    attributes are those that appear in ``denominator_name``, so that the number
    shown and the unit declared cannot diverge.
    """

    imported_records: pd.DataFrame
    active_records: pd.DataFrame
    words: pd.DataFrame
    analyzable_links: pd.DataFrame
    analyzable_sentences: frozenset
    filters: Mapping[str, Any] = field(default_factory=dict)

    # ── counts, which are what ends up in the denominators ────────────────
    @property
    def n_imported_records(self) -> int:
        return int(len(self.imported_records))

    @property
    def n_active_records(self) -> int:
        return int(len(self.active_records))

    @property
    def n_words(self) -> int:
        return int(len(self.words))

    @property
    def n_analyzable_links(self) -> int:
        return int(len(self.analyzable_links))

    @property
    def n_analyzable_sentences(self) -> int:
        return int(len(self.analyzable_sentences))

    @property
    def n_sentences(self) -> int:
        """All the imported sentences, analyzable or not."""
        return int(sentence_key(self.imported_records).nunique())

    def size_of(self, name: str) -> int:
        """The count of a unit from its name, for whoever builds measures."""
        try:
            return int(getattr(self, f"n_{name}"))
        except AttributeError as error:
            raise KeyError(
                f"'{name}' is not one of the five units: "
                "imported_records, active_records, words, analyzable_links, "
                "analyzable_sentences"
            ) from error

    def frame_of(self, name: str) -> pd.DataFrame:
        """The table of a unit from its name."""
        if name == "analyzable_sentences":
            raise KeyError(
                "'analyzable_sentences' is a set of keys, not a table: "
                "use units.analyzable_sentences"
            )
        try:
            frame = getattr(self, name)
        except AttributeError as error:
            raise KeyError(f"'{name}' is not one of the five units") from error
        if not isinstance(frame, pd.DataFrame):
            raise KeyError(f"'{name}' is not a table")
        return frame

    def measure(
        self,
        name: str,
        numerator: int,
        *,
        denominator_name: str,
        denominator: int | None = None,
        universe: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        per: int = 100,
    ) -> "Measure":
        """A measure that carries its own denominator.

        *denominator* can be passed when the denominator is a relevant subset — only the
        words with a valid label, say — and then *denominator_name* names it and
        *universe* declares from which of the five units that subset is derived.
        """
        if denominator is None:
            denominator = self.size_of(denominator_name)
            universe = universe or denominator_name
        return Measure(
            name=name,
            numerator=int(numerator),
            denominator=int(denominator),
            denominator_name=denominator_name,
            universe=universe or denominator_name,
            filters=dict(self.filters),
            parameters=dict(parameters or {}),
            per=per,
        )


def build_units(
    imported: pd.DataFrame,
    *,
    filters: Mapping[str, Any] | None = None,
    active: pd.DataFrame | None = None,
) -> Units:
    """Builds the five units from an imported corpus.

    *active* is passed when the general filters of the user have already been
    applied elsewhere — as on the loading page, which applies them to build the
    active corpus — and then this function does not reapply them: it takes that set
    as given and derives the other units from it.  If ``None`` is passed, the active
    records coincide with the imported ones minus the technical records, which is the
    default behaviour.

    The ``words`` are not obtained from the active records by subtracting
    punctuation: they are obtained by applying :func:`is_word` to the active
    records.  The difference matters exactly in the case that this module exists to
    cover, that is when the user has switched off the exclusion of technical
    records: the active records contain them, the words do not.
    """
    if imported is None:
        imported = pd.DataFrame()
    if active is None:
        keep = ~np.asarray(is_technical_record(imported), dtype=bool)
        active = imported[keep]

    words = active[np.asarray(is_word(active), dtype=bool)]
    links = active[np.asarray(analyzable_link_mask(active, within=active), dtype=bool)]
    sentences = frozenset(analyzable_sentence_keys(imported))

    return Units(
        imported_records=imported,
        active_records=active,
        words=words,
        analyzable_links=links,
        analyzable_sentences=sentences,
        filters=dict(filters or {}),
    )


# ---------------------------------------------------------------------------
# The structure of a measure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Measure:
    """A number that knows where it comes from.

    Interface, charts and exports read this object and recompute nothing: it is the
    only thing that keeps three views of the same number from diverging, and the
    reason why the denominator travels together with the value instead of being
    reconstructed downstream.

    *per* is the base of the percentage: 100 for a percentage, 10,000 for the “per
    ten thousand records” rates of the article.
    """

    name: str
    numerator: int
    denominator: int
    denominator_name: str
    universe: str
    filters: Mapping[str, Any] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    per: int = 100

    @property
    def value(self) -> float:
        """The ratio, rounded once and here."""
        if not self.denominator:
            return 0.0
        return round(self.per * self.numerator / self.denominator, 4)

    def as_dict(self) -> dict[str, Any]:
        """The serialisable form, with the six mandatory fields."""
        return {
            "name": self.name,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "denominator_name": self.denominator_name,
            "universe": self.universe,
            "filters": dict(self.filters),
            "parameters": dict(self.parameters),
            "per": self.per,
            "value": self.value,
        }

    def __str__(self) -> str:
        unit = "%" if self.per == 100 else "‰₀" if self.per == 10000 else f"/{self.per}"
        return (f"{self.name}: {self.value}{unit} "
                f"({self.numerator} su {self.denominator} {self.denominator_name})")
