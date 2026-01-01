"""Structural diagnostics on the dependency layer of an AGDT treebank.

The postag engine (``postag.py``) looks at one token at a time.  This module
looks at the *tree*: it walks the ``head`` pointers and reports the things that
cannot be seen from a single row — cycles, dangling heads, sentences with no
root or with several, coordination whose ``_CO`` suffixes contradict the tree,
particles that govern conjuncts, a full stop with words after it.  It also
*measures* projectivity and reports nothing about it: hyperbaton is Greek, not
a mistake, and no rule flags the longest non-projective arcs, for the reasons
set out in :func:`analyze_syntax`.

One principle runs through the whole file and is worth stating once.  A
Prague-school tree routes a dependency through nodes that carry no function of
their own — the coordinator, the apposition node, the preposition, the
subordinating conjunction — so the parent written in the table is very often
not the governor in the sentence.  Every comparison here is therefore made
against the *functional* head, obtained with
:func:`build_effective_head_index`: comparing against the structural one
produces false positives by the hundred (Boyd et al. 2008, authors' preprint:
19–20), and on these two corpora it produced some six thousand.

Why these matter, concretely.  Celano (2025: 49) reports that the aggregated
AGDT + Gorman + Pedalion dataset had to be repaired before training because
"syntactic trees also had to be modified if cycles were detected", and the
official CoNLL-2018 evaluation script rejects both cycles and multiple roots
(Celano 2025: 49 n. 5).  And coordination is worth getting right: reformatting
it raises the LAS of the whole corpus by 3.2 points and the LAS of the nodes
inside a coordination from 0.684 to 0.833 (Keersmaekers and Van Hal 2024:
1050–1051).  The larger figures of the preliminary report — "5-6% points
overall (and 25-30% points for the nodes involved in these structures)"
(Keersmaekers et al. 2019: 111) — were revised downwards by the same authors,
and this file cites the revised ones.

A note on the pagination of Boyd, Dickinson and Meurers 2008.  The published
article is *Research on Language and Computation* 6(2): 113–137; the copy in
general circulation, and the one whose page numbers appear in this package, is
the authors' preprint, self-numbered 1–30.  Every reference to it here is
marked as such rather than silently mixed with the journal pagination.

Every function returns a findings table with the same columns as the postag
engine, so the interface can show structural and morphological anomalies side
by side in one list.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .agdt_schema import (
    DAMAGE_GREEK_LOOKALIKE,
    DAMAGE_NIL_PLACEHOLDER,
    DAMAGE_TRUNCATED_OR_FOREIGN,
    DAMAGE_TYPO,
    FINITE_MOODS,
    LEAF_RELATIONS,
    MOOD_SLOT,
    PUNCTUATION_RELATIONS,
    base_relation,
    classify_relation_damage,
    elliptic_token_mask,
    fold_greek_lookalikes,
    greek_lookalike_pairs,
    is_known_relation,
    normalize_relation_text,
)
from . import issue_testi
from .fastmap import build_frame, map_unique, mask_unique
from .orthography import relation_is_annotator_note
from .rule_catalog import default_auto_apply, rule_description, rule_name, rule_severity

SENTENCE_KEY = ["source_file", "document_id", "sentence_index"]

FINDINGS_COLUMNS = [
    "rule_id", "anomaly_name", "anomaly_description",
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "head", "form", "lemma", "postag", "relation",
    "issue", "issue_key", "issue_params",
    "suggested_postag", "suggested_relation", "suggested_head",
    "auto_correctable", "severity",
]

_BASE_COLS = [
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "head", "form", "lemma", "postag", "relation",
]


def empty_findings() -> pd.DataFrame:
    return pd.DataFrame(columns=FINDINGS_COLUMNS)


def _make(
    subset: pd.DataFrame,
    rule_id: str,
    issue_params: "object | pd.Series" = None,
    *,
    issue_key: "str | pd.Series | None" = None,
    suggested_relation: object = pd.NA,
    suggested_head: object = pd.NA,
    severity: str = "errore",
    auto_correctable: bool = False,
) -> pd.DataFrame:
    """Build a findings frame from a filtered token subset (no Python loop)."""
    if subset is None or subset.empty:
        return empty_findings()
    columns = {
        "rule_id": rule_id,
        "anomaly_name": rule_name(rule_id),
        "anomaly_description": rule_description(rule_id),
    }
    for column in _BASE_COLS:
        columns[column] = subset[column] if column in subset.columns else pd.NA
    columns["issue_key"] = rule_id if issue_key is None else issue_key
    columns["issue_params"] = "" if issue_params is None else issue_params
    columns["suggested_postag"] = pd.NA
    columns["suggested_relation"] = suggested_relation
    columns["suggested_head"] = suggested_head
    columns["auto_correctable"] = bool(auto_correctable) and default_auto_apply(rule_id)
    # Severity comes from the class of the check. The parameter is kept so that existing
    # calls do not break, but it has no effect: a column that contradicts the class of
    # its own rule is exactly the defect to avoid.
    columns["severity"] = rule_severity(rule_id)
    frame = build_frame(columns, len(subset))
    frame["issue"] = issue_testi.rendi_serie(frame, "it")
    return frame[FINDINGS_COLUMNS]


def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
    live = [part for part in parts if part is not None and not part.empty]
    if not live:
        return empty_findings()
    return pd.concat(live, ignore_index=True)


# ---------------------------------------------------------------------------
# Sentence-level index
# ---------------------------------------------------------------------------

def _prepare(tokens: pd.DataFrame) -> pd.DataFrame:
    """Return a working copy with a stable sentence key and numeric head/id."""
    work = tokens.copy()
    for column in SENTENCE_KEY:
        if column not in work.columns:
            work[column] = ""
    work["_sent"] = (
        work["source_file"].astype("string").fillna("")
        + "␟" + work["document_id"].astype("string").fillna("")
        + "␟" + work["sentence_index"].astype("string").fillna("")
    )
    work["_tid"] = pd.to_numeric(work.get("token_id"), errors="coerce")
    work["_head"] = pd.to_numeric(work.get("head"), errors="coerce")
    if "token_index" in work.columns:
        work["_pos"] = pd.to_numeric(work["token_index"], errors="coerce")
    else:
        work["_pos"] = work.groupby("_sent").cumcount() + 1
    return work


def build_head_index(work: pd.DataFrame) -> pd.Series:
    """Map ``(sentence, head_id)`` to the row position of the head token.

    Returned as a Series aligned with *work*, holding the positional index of
    each token's head (``-1`` when the head is the artificial root or cannot be
    resolved).

    Every structural check in the program starts by calling this, on tables of
    six hundred thousand rows, so it is written as an index reindex rather than
    a Python dictionary walk: the loop version costs about a second per call
    and there are a dozen calls in a full analysis.
    """
    import numpy as np

    if work.empty:
        return pd.Series([], dtype="int64", index=work.index)

    sentence_codes = pd.factorize(work["_sent"], sort=False)[0]
    token_ids = pd.to_numeric(work["_tid"], errors="coerce")
    head_ids = pd.to_numeric(work["_head"], errors="coerce")

    positions = pd.Series(
        np.arange(len(work), dtype="int64"),
        index=pd.MultiIndex.from_arrays([sentence_codes, token_ids]),
    )
    # A duplicated token id inside one sentence is itself an error (reported by
    # check_head_integrity); here we simply keep the first occurrence so the
    # lookup stays well defined.
    positions = positions[~positions.index.duplicated(keep="first")]

    target = pd.MultiIndex.from_arrays([sentence_codes, head_ids])
    # ``copy=True`` guarantees a writable array: recent pandas releases return
    # a read-only view here, and the next line assigns into it.
    resolved = positions.reindex(target).to_numpy(
        dtype="float64", na_value=-1.0, copy=True
    )
    resolved[np.asarray(head_ids.fillna(0)) == 0] = -1.0
    return pd.Series(resolved.astype("int64"), index=work.index)


#: Nodes that stand between a word and its real governor. Prague-school
#: annotation routes a dependency through them, so the label of the token is
#: determined not by its structural parent but by whatever lies above it.
#: A bare AGDT fragment («CO», «Aux», «CONJ») is a defect when it is sporadic
#: and a house convention when it is everywhere. These two numbers draw the
#: line: at least this many occurrences, present in at least this share of the
#: corpus's documents.
BARE_RELATION_MINIMUM = 20
BARE_RELATION_SPREAD = 0.90

TRANSPARENT_RELATIONS = {"COORD", "APOS", "AuxP", "AuxC"}

#: The same set, plus the technical label of a correlative conjunction, for the
#: one question that needs it: "does this conjunct hang from a coordination?"
#:
#: The AGDT guidelines are explicit about coordinations written with more than
#: one conjunction — τε … καί, οὔτε … οὔτε — : "the last one by rule takes the
#: function COORD, while the preceding ones take the technical label AuxY and
#: are attached to the last one" (AGDT 2.0 guidelines, § 3.17). A conjunct
#: attached to one of those AuxY nodes therefore *is* inside a coordination:
#: the COORD is one step further up, and the walk has to take that step.
#:
#: Stopping at AuxY produced 301 findings on the GLAUx sample and 436 on the
#: confirmation sample — every single one of that rule's output on that corpus
#: — 166 on Pedalion and 45 on Gorman. They were the guideline's own
#: construction reported as a defect.
TRANSPARENT_FOR_COORDINATION = TRANSPARENT_RELATIONS | {"AuxY"}


def build_effective_head_index(
    work: pd.DataFrame,
    head_index: pd.Series,
    through: "set[str] | None" = None,
) -> pd.Series:
    """Like :func:`build_head_index`, but seeing through coordination.

    A conjunct's structural parent is the ``COORD`` node; its *functional*
    parent is whatever the coordination as a whole depends on. Testing
    agreement or case against the coordinator instead of the real governor
    produces false positives by the hundred — Boyd, Dickinson and Meurers
    (2008, authors' preprint: 20) measure that "49.0% (73)" of their residual
    false positives "are due to indirect annotation scheme decisions other than
    AuxP or AuxC, namely the annotation of coordination", and prescribe exactly
    this kind of local swap before any comparison. The same applies to
    prepositions and subordinating conjunctions, whose label is decided
    elsewhere in the graph.

    *through* names the labels to climb past, and defaults to all four.  A
    caller looking *for* one of them — "does this ``_CO`` hang from a COORD?" —
    passes the other three, so that the node it is asking about stays visible.
    """
    if through is None:
        through = TRANSPARENT_RELATIONS
    relations = map_unique(
        work["relation"].astype("string").fillna(""), base_relation)
    transparent = np.asarray(relations.isin(set(through)), dtype=bool)
    parent = head_index.to_numpy()

    # The walk is capped at twelve steps, so twelve numpy passes cover it: each
    # pass lifts every token that still sits under a transparent node one level
    # up, instead of walking token by token.
    current = parent.copy()
    for _ in range(12):
        climbing = (current >= 0) & transparent[current]
        if not climbing.any():
            break
        current[climbing] = parent[current[climbing]]
    return pd.Series(current, index=work.index, dtype="int64")


# ---------------------------------------------------------------------------
# 1. Well-formedness of the pointers
# ---------------------------------------------------------------------------

#: The unrepairable labels recognised by their spelling in the file, and the
#: diagnosis each falls under: a suffix left without its function, a family
#: prefix left without its last letter, or a label borrowed from another
#: inventory.  The sentences that tell the reader why each cannot be repaired
#: are in ``issue_testi``: here there is only the recognition.
_DIAGNOSI_TRONCATE: dict[str, str] = {
    "CO": "suffisso-orfano",
    "Aux": "etichetta-tagliata",
    "CONJ": "nome-di-altro-schema",
}


def _coppie_sosia(relation: object) -> tuple:
    """The Greek letters of a label, as code points.

    Code points are the point of the message: on screen ``AuxΖ`` and ``AuxZ`` are the
    same image, and a message that quoted only the label would leave the reader facing
    something that looks perfectly correct. Here the codes come out; the sentence that
    tells them is written by ``issue_testi``, in the requested language.
    """
    return tuple(
        {"greco": f"U+{ord(greek):04X}", "latino": f"U+{ord(latin):04X}"}
        for greek, latin in greek_lookalike_pairs(relation))


def _lettera_sbagliata(relation: object) -> str:
    """The wrong letter, when exactly one is wrong (``AucZ``)."""
    written = fold_greek_lookalikes(relation)
    intended = normalize_relation_text(relation)
    if len(written) == len(intended):
        wrong = [pair for pair in zip(written, intended) if pair[0] != pair[1]]
        if len(wrong) == 1:
            return wrong[0][0]
    return ""


def _chiave_troncata(relation: object) -> str:
    """Which of the four diagnoses applies to this label."""
    return "relation-truncated-or-foreign." + _DIAGNOSI_TRONCATE.get(
        fold_greek_lookalikes(relation), "fuori-inventario")


def check_head_integrity(work: pd.DataFrame) -> pd.DataFrame:
    """Dangling heads, self-loops, duplicate ids, unusable relation labels."""
    parts: list[pd.DataFrame] = []

    head_present = work["_head"].notna()
    is_root = head_present & (work["_head"] == 0)

    # "Is (sentence, head id) one of the (sentence, token id) pairs?" — asked
    # once for the whole column instead of once per token.  Building 625,176
    # tuples and hashing them against a set of the same size would cost 1.5 s of
    # the 3.0 s this check takes, and half of that would be iterating an
    # Arrow-backed string column element by element.  Factorising both id
    # columns together gives them a common integer code (missing ids share the
    # -1 sentinel, so a missing head still matches a missing id in the same
    # sentence, as the tuple test did), and the sentence code becomes a stride.
    sentence_codes = pd.factorize(work["_sent"], sort=False)[0].astype("int64")
    total = len(work)
    id_codes = pd.factorize(np.concatenate([
        work["_tid"].astype("float64").to_numpy(),
        work["_head"].astype("float64").to_numpy(),
    ]))[0]
    stride = int(id_codes.max()) + 2 if total else 2
    resolvable = pd.Series(
        np.isin(sentence_codes * stride + id_codes[total:],
                sentence_codes * stride + id_codes[:total]),
        index=work.index,
    )
    dangling = head_present & ~is_root & ~resolvable
    if dangling.any():
        # The number of the head is already the ``head`` column of the finding: the text
        # reads it from there.
        parts.append(_make(work[dangling], "head-dangling"))

    # "Missing" and "incomplete" are not the same defect and must not be
    # counted together. A single headless token inside an otherwise annotated
    # sentence is a hole in the tree — an annotator's slip, repairable by
    # reading one sentence. A sentence in which *no* token declares a head is
    # not a hole: it is a stretch of text that never entered the annotation
    # work at all, and no amount of reading will repair it one token at a time.
    # The two are separate checks, so that a corpus with fifty unannotated
    # sentences does not look like a corpus with nine hundred careless slips.
    missing_head = ~head_present & ~work["relation"].isin(PUNCTUATION_RELATIONS)
    if missing_head.any():
        annotated_somewhere = head_present.groupby(work["_sent"]).transform("any")
        never_annotated = missing_head & ~annotated_somewhere
        isolated = missing_head & annotated_somewhere
        if never_annotated.any():
            parts.append(_make(work[never_annotated], "sentence-not-annotated"))
        missing_head = isolated
    if missing_head.any():
        parts.append(_make(work[missing_head], "head-missing"))

    # A token that is its own head has no rule of its own: it is already covered by the
    # cycle rule, because following the head of a token that points to itself returns at
    # once to the starting point. Two rules would flag the same tokens under two names,
    # and the count would carry them twice.

    duplicated = work.duplicated(subset=["_sent", "_tid"], keep=False) & work["_tid"].notna()
    if duplicated.any():
        parts.append(_make(work[duplicated], "token-id-duplicate"))

    # "Label not in the inventory" is not one rule, because it covers four
    # accidents with four different causes, four different repairs and four
    # different consequences.  In Gorman: a Greek capital keyed instead of the
    # Latin one (AuxΖ, AuxΚ: 10 tokens), a typing slip (AucZ: 1), a label that
    # is a fragment of AGDT notation or comes from another inventory (CO, Aux,
    # CONJ: 20), and an explicit "no value" marker (nil: 3).  Only the first two
    # have one possible intended value, so only those two propose a correction;
    # merged into one rule, the twenty-three unrepairable ones would drag the
    # eleven repairable ones down with them, and the rule would be auto-applicable.
    raw_relations = work["relation"].astype("string")
    damage = map_unique(raw_relations, classify_relation_damage)
    repaired = map_unique(raw_relations, normalize_relation_text)

    lookalike = damage == DAMAGE_GREEK_LOOKALIKE
    if lookalike.any():
        subset = work[lookalike]
        # The code points, not their names: the name of the letter is written by whoever
        # displays the sentence, and the correct label is in ``suggested_relation``.
        coppie = map_unique(raw_relations[lookalike], _coppie_sosia)
        parts.append(_make(subset, "relation-greek-lookalike",
                           issue_testi.parametri(coppie=coppie),
                           suggested_relation=repaired[lookalike], auto_correctable=True))

    typo = damage == DAMAGE_TYPO
    if typo.any():
        subset = work[typo]
        parts.append(_make(subset, "relation-typo",
                           issue_testi.parametri(
                               lettera=map_unique(raw_relations[typo],
                                                  _lettera_sbagliata)),
                           suggested_relation=repaired[typo], auto_correctable=True))

    truncated = damage == DAMAGE_TRUNCATED_OR_FOREIGN
    if truncated.any():
        # Corpus-relative, for the same reason the relation-family expectation
        # is. A bare «CO» written fourteen times in a corpus of 158 documents
        # (Gorman) is a label that lost its function; the same «CO» written
        # 2,369 times across 18 documents out of 18 (the automatic GLAUx sample)
        # is how that corpus writes coordination, and GLAUx says of itself that
        # it follows the AGDT guidelines only «roughly». Calling the second a
        # violation of the scheme would report a house style as an error, which
        # is the mistake the catalogue also avoids for Pedalion's «b». The
        # threshold is spread across the corpus, not raw frequency: a
        # convention shows up nearly everywhere.
        subset = work[truncated]
        documents = work["document_id"] if "document_id" in work.columns else None
        total_documents = int(documents.nunique()) if documents is not None else 0
        systematic = pd.Series(False, index=subset.index)
        if total_documents:
            for label, rows in subset.groupby(raw_relations[truncated], dropna=False):
                spread = rows["document_id"].nunique() / max(total_documents, 1)
                if len(rows) >= BARE_RELATION_MINIMUM and spread >= BARE_RELATION_SPREAD:
                    systematic.loc[rows.index] = True
        sporadic = ~systematic
        if sporadic.any():
            rows = subset[sporadic]
            # Four different diagnoses of the same symptom, four keys.
            chiave = map_unique(raw_relations[truncated][sporadic], _chiave_troncata)
            parts.append(_make(rows, "relation-truncated-or-foreign",
                               issue_key=chiave))
        if systematic.any():
            parts.append(_make(subset[systematic], "relation-bare-convention"))

    nil_placeholder = damage == DAMAGE_NIL_PLACEHOLDER
    if nil_placeholder.any():
        parts.append(_make(work[nil_placeholder], "relation-nil-placeholder"))

    # Working notes belong to annotator-note-in-relation, which names the cause
    # and is the only one of the two that can say what to do with them.  A
    # relation written like a note — "!!!!!!ATR", "!!!congruentiefout
    # geslacht?!!!ADV", "%%%SBJ" — is not an unknown label: nobody meant
    # "!!!!!!ATR" to be a label.  Without this exclusion the same tokens would
    # be reported twice, once as a note and once as an unknown label.
    note = relation_is_annotator_note(work["relation"])
    known = mask_unique(work["relation"], is_known_relation)
    unknown = work["relation"].notna() & ~known & (damage == "") & ~note
    if unknown.any():
        parts.append(_make(work[unknown], "relation-unknown"))

    blank_relation = work["relation"].isna() | (
        work["relation"].astype("string").fillna("").str.strip() == ""
    )
    if blank_relation.any():
        parts.append(_make(work[blank_relation], "relation-missing"))

    return _concat(parts)


# ---------------------------------------------------------------------------
# 2. Cycles and roots
# ---------------------------------------------------------------------------

def check_cycles(work: pd.DataFrame, head_index: pd.Series) -> pd.DataFrame:
    """Tokens caught in a head cycle (A governs B governs … governs A).

    Uses iterative colouring — WHITE / GREY / BLACK — so each node is visited
    once regardless of how deep the tree is.  A recursive walk would blow the
    Python stack on the long periods of Thucydides.
    """
    parent = head_index.to_numpy()
    total = len(parent)
    colour = [0] * total          # 0 = unvisited, 1 = on stack, 2 = settled
    in_cycle = [False] * total

    for start in range(total):
        if colour[start]:
            continue
        path: list[int] = []
        node = start
        while node != -1 and colour[node] == 0:
            colour[node] = 1
            path.append(node)
            node = parent[node]
        if node != -1 and colour[node] == 1:
            # Found a back-edge: everything from `node` onwards is in the cycle.
            cut = path.index(node)
            for member in path[cut:]:
                in_cycle[member] = True
        for member in path:
            colour[member] = 2

    mask = pd.Series(in_cycle, index=work.index)
    if not mask.any():
        return empty_findings()
    return _make(work[mask], "head-cycle")


def check_roots(work: pd.DataFrame) -> pd.DataFrame:
    """Sentences with no root, or with more than one non-punctuation root."""
    parts: list[pd.DataFrame] = []
    is_root = work["_head"].notna() & (work["_head"] == 0)
    is_punct = work["relation"].isin(PUNCTUATION_RELATIONS)

    real_roots = is_root & ~is_punct
    per_sentence = real_roots.groupby(work["_sent"]).sum()

    no_root = set(per_sentence[per_sentence == 0].index)
    if no_root:
        mask = work["_sent"].isin(no_root) & (work["_pos"] == work.groupby("_sent")["_pos"].transform("min"))
        if mask.any():
            parts.append(_make(work[mask], "sentence-no-root"))

    many_roots = set(per_sentence[per_sentence > 1].index)
    if many_roots:
        mask = real_roots & work["_sent"].isin(many_roots)
        if mask.any():
            counts = work.loc[mask, "_sent"].map(per_sentence).astype("Int64")
            parts.append(_make(work[mask], "sentence-many-roots",
                               issue_testi.parametri(radici=counts),
                               severity="sospetto"))

    return _concat(parts)


# ---------------------------------------------------------------------------
# 3. Coordination and apposition
# ---------------------------------------------------------------------------

def check_coordination(work: pd.DataFrame, head_index: pd.Series) -> pd.DataFrame:
    """The ``_CO`` / ``_AP`` suffixes must agree with the shape of the tree.

    Every test below reads the *functional* head, not the structural one.  A
    preposition, a subordinating conjunction and an apposition node carry no
    function of their own — they inherit it from above — so a conjunct hanging
    from one of them is a conjunct of whatever governs it: in ``καὶ ἄνευ ὅρκου
    καὶ μεθ' ὅρκου`` the chain runs καί (COORD) → ἄνευ (AuxP) → ὅρκου (ADV_CO),
    and the ``_CO`` is exactly where it belongs.  Comparing with the structural
    parent instead is the mistake Boyd et al. (2008, preprint: 19–20) measure and warn
    about: it reports as errors conjuncts that hang from a preposition, a
    subordinating conjunction or an apposition node, all of them correct annotation.
    """
    parts: list[pd.DataFrame] = []
    relations = work["relation"].astype("string").fillna("")
    # Reading the head's label with ``.iat`` once per token goes through pandas'
    # scalar indexing and, on an Arrow-backed string column, costs roughly five
    # times a numpy lookup: 3.2 s of the 3.4 s this check would take are spent
    # inside ``ArrowExtensionArray.__getitem__``.  One gather over an object
    # array answers the same 625,176 questions.
    labels = relations.to_numpy()

    def _head_labels(index: pd.Series) -> pd.Series:
        rows = index.to_numpy()
        return pd.Series(np.where(rows >= 0, labels[rows], ""),
                         index=work.index, dtype="string")

    # Climb past everything transparent except the node being looked for, so
    # that a COORD directly above a ``_CO`` still stops the walk.
    coord_head = build_effective_head_index(
        work, head_index, through=TRANSPARENT_FOR_COORDINATION - {"COORD"})
    apos_head = build_effective_head_index(
        work, head_index, through=TRANSPARENT_RELATIONS - {"APOS"})

    # A _CO child must hang from a COORD (or from another _CO in nested
    # coordination); a _AP child from an APOS.
    co_head_relations = _head_labels(coord_head)
    co_mask = relations.str.endswith("_CO")
    bad_co = co_mask & ~(
        co_head_relations.str.startswith("COORD")
        | co_head_relations.str.endswith("_CO")
        | co_head_relations.str.endswith("_AP")
    )
    if bad_co.any():
        # The relation reached by climbing is not the relation of the token: it is the
        # result of a walk in the tree, and it lives in the parameters.
        parts.append(_make(
            work[bad_co], "coord-suffix-orphan",
            issue_testi.parametri(
                relazione_raggiunta=co_head_relations[bad_co].fillna(""))))

    ap_head_relations = _head_labels(apos_head)
    ap_mask = relations.str.endswith("_AP")
    bad_ap = ap_mask & ~(
        ap_head_relations.str.startswith("APOS")
        | ap_head_relations.str.endswith("_AP")
        | ap_head_relations.str.endswith("_CO")
    )
    if bad_ap.any():
        parts.append(_make(
            work[bad_ap], "apos-suffix-orphan",
            issue_testi.parametri(
                relazione_raggiunta=ap_head_relations[bad_ap].fillna(""))))

    # Children of a COORD: do the conjuncts carry the same function?
    #
    # There is no check for "COORD with fewer than two conjuncts".  Counting
    # only the ``_CO`` children flags thousands of Gorman coordinations, almost
    # all of which have two members as soon as one looks a step further down;
    # counting the nested nodes as well leaves a few hundred, and those are the
    # places where AGDT legitimately annotates a coordination with one expressed
    # member — elliptic conjuncts, correlatives whose first term is a particle, a
    # coordinator resumed across a full stop.  A rule that has to keep growing
    # exceptions to stay honest is measuring the annotation style, not the
    # annotation, and it does not belong among the anomalies.
    coord_rows = np.flatnonzero(
        relations.str.startswith("COORD").to_numpy(dtype=bool))
    if coord_rows.size:
        # ``base_relation`` is derived once per distinct label — the column
        # holds 72 of them — and the result indexed, instead of being called
        # once per (COORD, conjunct) pair, which would be over a million calls
        # on this corpus.  Counting the distinct functions among the
        # conjuncts then reduces to one ``bincount`` pass over the head array.
        bases = map_unique(relations, base_relation)
        functional = coord_head.to_numpy()
        conjunct = np.asarray(relations.str.endswith("_CO"), dtype=bool) & (functional >= 0)

        base_codes = pd.factorize(bases, sort=False)[0]
        span = int(base_codes.max()) + 1
        distinct = np.unique(functional[conjunct] * span + base_codes[conjunct])
        base_count = np.bincount(distinct // span, minlength=len(work))
        discordant_rows = coord_rows[base_count[coord_rows] > 1]

        if discordant_rows.size:
            subset = work.iloc[discordant_rows]
            parts.append(_make(subset, "coord-discordant-conjuncts",
                               severity="sospetto"))

    return _concat(parts)


# ---------------------------------------------------------------------------
# 4. Auxiliary labels
# ---------------------------------------------------------------------------

def check_auxiliaries(work: pd.DataFrame, head_index: pd.Series) -> pd.DataFrame:
    """What the auxiliary labels really promise about the shape of the tree.

    The check does not report every AuxY/AuxZ/AuxX/AuxG/AuxK node with a child,
    on the premise that those labels mark leaves.  The guidelines do not say
    that, and the corpora contradict it: of the 1,636 Gorman tokens with one of
    these labels and a child, most are particle chains — ``οὐ μόνον``,
    ``οὐ μὴν ἀλλ᾽``, ``τοῦτο μέν`` — whose internal structure is the annotation,
    286 (17%) are parenthetical finite verbs (``ὡς ἔγωγέ φημι``), and only 42
    (2.6%) govern ``_CO`` conjuncts, which is a coordinator wearing the wrong
    label.  In Pedalion that last group is 126 of 314 (40%).  So the shape is not
    reported; the two things that can be named are.
    """
    parts: list[pd.DataFrame] = []
    relations = work["relation"].astype("string").fillna("")

    # How many children each token has. The readable version walks the head
    # index and does ``child_count.iat[position] += 1`` six hundred thousand
    # times; every one of those goes through pandas' indexing machinery, and
    # together they were two thirds of the whole structural family. bincount
    # answers the same question in one pass over a numpy array.
    positions = head_index.to_numpy()
    counts = np.bincount(positions[positions >= 0], minlength=len(work))
    child_count = pd.Series(counts[: len(work)], index=work.index, dtype="int64")

    # ── An Aux node that governs conjuncts is a COORD ─────────────────────
    linked = positions >= 0
    conjunct = np.asarray(relations.str.endswith("_CO"), dtype=bool) & linked
    conjunct_children = pd.Series(
        np.bincount(positions[conjunct], minlength=len(work))[: len(work)],
        index=work.index, dtype="int64")
    disguised = relations.isin(LEAF_RELATIONS) & (conjunct_children > 0)
    if disguised.any():
        parts.append(_make(
            work[disguised], "aux-governs-conjuncts",
            issue_testi.parametri(
                congiunti=conjunct_children[disguised].astype("Int64")),
            severity="sospetto"))

    # ── A finite verb labelled as a particle ──────────────────────────────
    # ὡς ἔγωγέ φημι, ὥς φασιν, ὡς ἱστορεῖ Κλέαρχος: a parenthetical verb with
    # its own subject and objects, filed under the label for sentence adverbs.
    # 286 tokens in Gorman, 168 of them φημί.  Not a slip and not a coordinator:
    # a deliberate way of treating a formula as a particle, which costs the verb
    # its verbal analysis and teaches a model that φημί is a particle.
    tags = work["postag"].astype("string").fillna("")
    finite_verb = np.asarray(
        tags.str.slice(0, 1).eq("v") & tags.str.slice(MOOD_SLOT, MOOD_SLOT + 1).isin(FINITE_MOODS),
        dtype=bool)
    parenthetical = (relations.isin({"AuxY", "AuxZ"}) & (child_count > 0)
                     & pd.Series(finite_verb, index=work.index) & ~disguised)
    if parenthetical.any():
        parts.append(_make(
            work[parenthetical], "aux-finite-verb",
            issue_testi.parametri(
                dipendenti=child_count[parenthetical].astype("Int64")),
            severity="sospetto"))

    governing = relations.isin({"AuxP", "AuxC"}) & (child_count == 0)
    if governing.any():
        parts.append(_make(work[governing], "aux-governor-without-child",
                           severity="sospetto"))

    # ── AuxK: why there is no rule for real words after it ────────────────
    # A rule reporting "AuxK with real words after it" as terminal punctuation
    # out of place would be wrong, because AuxK is not the label of the full
    # stop: it is the label of *sentence-boundary punctuation*, and the AGDT
    # guidelines put under it the colon, the raised dot and the question mark as
    # well.  A colon in Greek is regularly followed by the clause it introduces,
    # inside the same annotated sentence, so a rule that does not read which
    # character the token actually is cannot tell a segmentation error from
    # ordinary punctuation — and around nine findings in ten would be the
    # latter.  Excluding the elliptic nodes parked after the stop does not change
    # that ratio, because what remains is mostly colons.  A detector with that
    # error rate does not belong among the anomalies, and no amount of tolerance
    # fixes it: what it would take is a rule keyed on the punctuation mark
    # itself, which is a different rule and is not part of the program.

    return _concat(parts)


# ---------------------------------------------------------------------------
# 5. Projectivity
# ---------------------------------------------------------------------------

def _children_blocks(
    nodes: np.ndarray,
    counts: np.ndarray,
    starts: np.ndarray,
    child_list: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Gather the children of a whole level of the forest in one numpy pass.

    Returns the parents that actually have children, how many each has, where
    each parent's block begins inside the gathered array, and the children.
    """
    sizes = counts[nodes]
    keep = sizes > 0
    parents = nodes[keep]
    sizes = sizes[keep]
    block_start = np.cumsum(sizes) - sizes
    total = int(sizes.sum())
    within = np.arange(total, dtype="int64") - np.repeat(block_start, sizes)
    kids = child_list[np.repeat(starts[parents], sizes) + within]
    return parents, sizes, block_start, kids


def _euler_tour(parent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Entry/exit stamps of a depth-first walk over the head forest.

    ``k`` is a descendant of ``h`` — or is ``h`` itself — exactly when
    ``tin[h] <= tin[k] < tout[h]``: one integer comparison instead of a lookup
    in a set of dominated positions.  Nodes unreachable from any root, i.e. the
    ones caught in a head cycle, keep ``tin == tout == -1``, so the test is
    false for them in either role, which is what leaving them out of the map
    did before.

    The walk is done a level at a time in numpy rather than node by node in
    Python: a per-node stack walk costs about 1.0 s on 625,176 tokens, this
    costs 0.08 s, and dependency trees are shallow enough (deepest chain in the
    Gorman corpus: 22 links) that the number of numpy passes stays tiny.
    """
    total = len(parent)
    tin = np.full(total, -1, dtype="int64")
    size = np.zeros(total, dtype="int64")
    roots = np.flatnonzero(parent < 0)
    if roots.size == 0:
        return tin, tin.copy()

    linked = np.flatnonzero(parent >= 0)
    child_list = linked[np.argsort(parent[linked], kind="stable")]
    counts = np.bincount(parent[linked], minlength=total)
    starts = np.zeros(total + 1, dtype="int64")
    np.cumsum(counts, out=starts[1:])

    levels = [roots]
    while True:
        kids = _children_blocks(levels[-1], counts, starts, child_list)[3]
        if kids.size == 0:
            break
        levels.append(kids)

    for level in levels:
        size[level] = 1
    for level in reversed(levels[1:]):
        size += np.bincount(
            parent[level], weights=size[level], minlength=total).astype("int64")

    # A node's stamp is its parent's, plus one, plus the whole weight of the
    # siblings that come before it — the numbering a stack walk would produce.
    tin[roots] = np.cumsum(size[roots]) - size[roots]
    for level in levels[:-1]:
        parents, sizes, block_start, kids = _children_blocks(
            level, counts, starts, child_list)
        if kids.size == 0:
            continue
        weights = size[kids]
        before = np.cumsum(weights) - weights
        tin[kids] = (np.repeat(tin[parents] + 1, sizes)
                     + before - np.repeat(before[block_start], sizes))
    return tin, tin + size


def _projectivity_flags_exact(
    linear: np.ndarray,
    parent: np.ndarray,
    sentence_codes: np.ndarray,
    punctuation: np.ndarray,
    tin: np.ndarray,
    tout: np.ndarray,
) -> np.ndarray:
    """The scalar reading of the test, for token tables with an irregular layout.

    Only reached when two tokens of one sentence claim the same linear position
    — itself an error, and absent from every corpus this ships against — or
    when the positions are so sparse that the flat layout below would cost more
    memory than the table itself.  Kept because in that case a position counts
    as dominated when *any* of the tokens sitting on it is dominated, which the
    minimum/maximum test cannot express.
    """
    at_position: dict[tuple[int, int], list[int]] = {}
    skip: set[tuple[int, int]] = set()
    for row in range(len(parent)):
        key = (int(sentence_codes[row]), int(linear[row]))
        at_position.setdefault(key, []).append(row)
        if punctuation[row]:
            skip.add(key)

    flags = np.zeros(len(parent), dtype=bool)
    for row in range(len(parent)):
        head_row = parent[row]
        if head_row < 0:
            continue
        low, high = sorted((int(linear[head_row]), int(linear[row])))
        if high - low <= 1:
            continue
        first, last = tin[head_row], tout[head_row]
        sentence = int(sentence_codes[row])
        for between in range(low + 1, high):
            key = (sentence, between)
            if key in skip:
                continue
            if any(first <= tin[node] < last for node in at_position.get(key, ())):
                continue
            flags[row] = True
            break
    return flags


def compute_projectivity(work: pd.DataFrame, head_index: pd.Series) -> pd.DataFrame:
    """Per-arc table with a ``non_projective`` flag and the arc length.

    An arc (head, dependent) is non-projective when another arc crosses it.
    In Ancient Greek this is *hyperbaton*, a stylistic fact rather than an
    error — Gorman (2020: 2) lists "frequent discontinuous syntactic
    structures" as a property of her corpus.  So the output is a measurement
    and nothing else: the statistics tab plots it, and no rule fires on it.

    Arcs that touch an elided-word placeholder are left out of the table.  Both
    corpora park those nodes after the terminal punctuation, so an arc reaching
    one of them measures the parking convention and not the word order.
    """
    columns = ["source_file", "document_id", "sentence_index", "sentence_id",
               "token_id", "head", "form", "relation", "dep_pos", "head_pos",
               "arc_length", "direction", "non_projective"]
    if work.empty:
        return pd.DataFrame(columns=columns)

    positions = work["_pos"].to_numpy()
    parent = head_index.to_numpy()
    linear = positions.astype("int64")
    tin, tout = _euler_tour(parent)

    # Punctuation is excluded from the "between" test.  In AGDT a comma is
    # routinely attached far from the words it sits between, so counting it
    # would attribute to Greek word order a discontinuity that belongs to the
    # punctuation convention — the same reason UD validators ignore it.
    punctuation = (
        work["relation"].isin(PUNCTUATION_RELATIONS)
        | (work["postag"].astype("string").fillna("").str[:1] == "u")
    ).to_numpy()

    sentence_codes = pd.factorize(work["_sent"], sort=False)[0]
    sentences = int(sentence_codes.max()) + 1
    first = np.full(sentences, np.iinfo("int64").max, dtype="int64")
    np.minimum.at(first, sentence_codes, linear)
    last = np.full(sentences, np.iinfo("int64").min, dtype="int64")
    np.maximum.at(last, sentence_codes, linear)
    width = last - first + 1
    block = np.zeros(sentences, dtype="int64")
    np.cumsum(width[:-1], out=block[1:])
    slot = block[sentence_codes] + (linear - first[sentence_codes])
    span = int(width.sum())

    regular = span <= 4 * len(work)
    if regular:
        regular = not (np.bincount(slot[~punctuation], minlength=span) > 1).any()

    if not regular:
        flags = _projectivity_flags_exact(
            linear, parent, sentence_codes, punctuation, tin, tout)
    else:
        # Every sentence occupies one contiguous stretch of `board`, so "the
        # positions strictly between a head and its dependent" is a slice, and
        # "all of them are dominated by the head" is a range minimum and a range
        # maximum against the head's own interval: the descendants of a node are
        # exactly the nodes whose stamp falls inside it.  A position nobody
        # occupies keeps the sentinels and so always breaks projectivity, which
        # is what the set version did by not finding it in `covered`.
        far = np.int64(2 ** 40)
        board_min = np.full(span, -1, dtype="int64")
        board_max = np.full(span, far, dtype="int64")
        board_min[slot] = tin
        board_max[slot] = tin
        board_min[slot[punctuation]] = far
        board_max[slot[punctuation]] = -far

        head_slot = np.where(parent >= 0, linear[parent], 0)
        low = np.minimum(head_slot, linear)
        high = np.maximum(head_slot, linear)
        between = high - low - 1
        arcs = (parent >= 0) & (between > 0)
        flags = np.zeros(len(work), dtype=bool)
        rows = np.flatnonzero(arcs)
        if rows.size:
            # Sparse table over `board`: one pass per power of two, then every
            # arc answered by two lookups regardless of how far it reaches.
            widths = between[rows]
            table_min, table_max = [board_min], [board_max]
            step = 1
            while step * 2 <= int(widths.max()):
                previous_min, previous_max = table_min[-1], table_max[-1]
                keep = span - step * 2 + 1
                table_min.append(np.minimum(previous_min[:keep],
                                            previous_min[step:step + keep]))
                table_max.append(np.maximum(previous_max[:keep],
                                            previous_max[step:step + keep]))
                step *= 2
            level = np.frexp(widths.astype("float64"))[1] - 1
            left = block[sentence_codes[rows]] + (low[rows] + 1 - first[sentence_codes[rows]])
            reach_min = np.empty(rows.size, dtype="int64")
            reach_max = np.empty(rows.size, dtype="int64")
            for index in range(len(table_min)):
                here = level == index
                if not here.any():
                    continue
                start = left[here]
                tail = start + widths[here] - (1 << index)
                reach_min[here] = np.minimum(table_min[index][start],
                                             table_min[index][tail])
                reach_max[here] = np.maximum(table_max[index][start],
                                             table_max[index][tail])
            heads = parent[rows]
            flags[rows] = ~((reach_min >= tin[heads]) & (reach_max < tout[heads]))

    # Handing the constructor the columns themselves, rather than `.values`,
    # keeps the Arrow-backed strings as they are: a round trip through an object
    # array and back would cost time for no change in dtype.
    flat = pd.RangeIndex(len(work))

    def column(name: str) -> pd.Series:
        source = work[name] if name in work.columns else pd.Series(pd.NA, index=work.index)
        return source.set_axis(flat)

    # An arc is dropped when either end is an elided-word placeholder: the
    # measurement is about the order of the words an author wrote.
    parked = elliptic_token_mask(work, sentence_codes, linear)
    keep = (parent < 0) | ~(parked | parked[np.where(parent >= 0, parent, 0)])

    result = pd.DataFrame({
        "source_file": column("source_file"),
        "document_id": column("document_id"),
        "sentence_index": column("sentence_index"),
        "sentence_id": column("sentence_id"),
        "token_id": column("_tid"),
        "head": column("_head"),
        "form": column("form"),
        "relation": column("relation"),
        "dep_pos": positions,
        "head_pos": np.where(parent >= 0, linear[parent], -1),
        "non_projective": flags,
    }, index=flat)
    result = result[(result["head_pos"] >= 0) & keep].copy()
    result["arc_length"] = (result["head_pos"] - result["dep_pos"]).abs()
    result["direction"] = np.where(
        result["head_pos"].to_numpy() < result["dep_pos"].to_numpy(),
        "head to the left", "head to the right")
    return result[columns].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

def analyze_syntax(
    tokens: pd.DataFrame,
    *,
    include_projectivity: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every structural check.

    Returns ``(findings, arcs)`` where *arcs* is the per-arc projectivity table
    (empty when *include_projectivity* is False).  Keeping the arcs is worth
    the memory: the statistics tab reuses them for dependency distance,
    branching direction and hyperbaton without a second tree walk.

    Projectivity produces no findings.  Reporting the longest 0.5% of the
    non-projective arcs as "very wide hyperbaton, or a wrong head" would not be
    defensible, for two reasons.  Most of those arcs reach an elided-word
    placeholder parked after the full stop, and those are kept out of the table
    altogether; and the length distribution of what remains has no outlier
    regime to speak of — a smooth tail — so a quantile threshold reports a fixed
    share of the corpus whatever its quality, and many *projective* arcs are
    longer than the cut without being reported.  Reading a sample of the
    survivors finds correct annotation (a δέ attached to the main verb of a long
    period, a genitive absolute, coordinators spanning a Thucydidean sentence)
    and further placeholders.  The number stays, in the statistics; the
    accusation does not.
    """
    if tokens is None or tokens.empty:
        return empty_findings(), pd.DataFrame()

    work = _prepare(tokens)
    head_index = build_head_index(work)

    parts = [
        check_head_integrity(work),
        check_cycles(work, head_index),
        check_roots(work),
        check_coordination(work, head_index),
        check_auxiliaries(work, head_index),
    ]

    arcs = pd.DataFrame()
    if include_projectivity:
        arcs = compute_projectivity(work, head_index)

    return _concat(parts), arcs
