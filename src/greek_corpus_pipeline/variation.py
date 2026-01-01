"""Variation cores: five planes, and the attribution of each.

The principle is Dickinson and Meurers' (2003a: 107): *“It detects variation in the
pos-annotation of a corpus by searching for n-grams which occur more than once in
the corpus and include at least one difference in their annotation”*, on the basis
that “the more similar the context of a variation, the more likely the variation
is an error” (Dickinson and Meurers 2005: 323).

**Who wrote what.**  The five planes are not “the five planes of
Boyd/Dickinson/Meurers”: three come from that literature, in three different
ways, and two are GCP's own.  It is written here so that nobody has to deduce it.

======================================  =====================================
plane                                   attribution
======================================  =====================================
1 · form → label                        the principle is Dickinson and
                                        Meurers' (2003a); the unigram core is
                                        theirs, the true n-gram is plane 3
2 · form → single position              **GCP's own extension**: no source
                                        decomposes a positional label
                                        position by position
3 · trigram → central label             Dickinson and Meurers (2003a), with
                                        the ±1 window justified in Dickinson
                                        (2005: 46, 81)
4 · syntactic pair → relation           **adaptation** of the pair-based
    and direction                       representation of Boyd, Dickinson and
                                        Meurers (2008: 123); *not* the full
                                        method
5 · form and PoS → lemma                **GCP's own extension**
======================================  =====================================

On plane 4 the formulation to use, in the article too, is: *GCP adapts the
pair-based representation of Boyd et al. (2008) for variation in attested
dependency relations.*  Not “follows”, not “implements”: the NIL cores are
missing, so is the merging of overlapping type-identical dependencies (§ 4.1.3),
and so are all three context heuristics (§ 4.2).  See
:func:`dependency_variation_with_nil`.

**Two bibliographic cautions**, because both are easy to fall into.  The works
of Dickinson and Meurers from 2003 are *two*: 2003a is “Detecting Errors in
Part-of-Speech Annotation” (EACL, 107–114), from which the definition quoted
above comes, and 2003b is “Detecting Inconsistencies in Treebanks” (TLT, 45–56),
where the treatment of null elements is found.  And the page numbers given here
for Boyd, Dickinson and Meurers 2008 are those of the authors' preprint,
numbered 1–30, not those of the article published in *Research on Language and
Computation* 6(2): 113–137.

**What the total is not.**  The sum of the five planes is the sum of the cores
found in the five planes, and nothing else: it is not the number of errors, not
the number of distinct problems, not the number of unique points.  The same form
can take part in several planes at once.  A “unique core across planes” cannot
be defined, because the five cores have different forms.

**Two filters** apply to all the planes, and both are documented as necessary in
the sources: punctuation leaves before the comparison (Boyd et al. 2008,
preprint: 19) and the suffixes ``_CO`` and ``_AP`` are stripped so that
coordination does not fabricate false positives (Celano 2025: 50).

No filter downgrades a core from error to legitimate variation for the pairs
between which the AGDT scheme allows oscillation (Boyd et al. 2008, preprint:
20): a pair admitted *in the corpus* is not a pair admitted *at that point of
the text*, and marking the row as legitimate would invite the reader not to look
at it.  The pairs are declared in :data:`agdt_schema.LEGITIMATE_VARIATION`,
where they are a fact of the scheme and not a judgement on the single core.

Realistic expectations, from the same sources: precision ranges from 48% on
TigerDB to 93% on Talbanken.  It is a tool for *ranking*, not an oracle.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from .agdt_schema import (
    POSITION_NAMES,
    TAG_LENGTH,
    base_relation,
)
from .fastmap import grouped_join, map_unique
from .normalise import nfc
from .units import SENTENCE_ORDER, is_word, sentence_key

NUCLEUS_COLUMNS = [
    "tipo", "nucleo", "chiave", "n_etichette", "etichette", "occorrenze",
    "distribuzione", "esempi",
]


def _empty(columns: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(columns=columns or NUCLEUS_COLUMNS)


#: The pairs of functions between which the AGDT scheme allows oscillation.
#:
#: They are declared because they are a fact of the scheme, and they decide
#: nothing: the tables of the cores have no “legitimate variation” column. Such a
#: column would say, of each core, whether the whole set of its labels falls
#: inside one of these pairs, and would order the table by that judgement. But a
#: core that oscillates between two functions admitted **by the scheme** is not for
#: that reason a correct core **at that point of the text**: the pair says that the
#: two functions can coexist in a corpus, not that this sentence admits both.
#: Marking the row as legitimate would invite the reader not to look at it, and
#: would be a judgement that no evidence supports.
#:
#: The tables are ordered by occurrences and number of labels, that is, by how much
#: material there is to look at. The pairs are declared in
#: ``agdt_schema.LEGITIMATE_VARIATION``, where they are a fact of the scheme.


def comparison_keys(tokens: pd.DataFrame) -> pd.DataFrame:
    """The columns on which the five planes compare, normalised to NFC.

    Returns a **copy** with ``form`` and ``lemma`` in NFC.  The original data is not
    touched, and that is not a detail: four checks of the catalogue exist to report
    precisely what a normalisation applied to the data would erase — “Encoding not
    normalised to NFC” (4,007 records in Pedalion), “Corpus predominantly in NFD”
    (one per stratum in GLAUx), “Final number in the lemma” (72,836 in Gorman) and
    “Competing graphic variants of the same lemma” (477).  Normalising in order to
    compare and modifying the corpus are two different things, and this function
    does only the first.

    Only NFC: not the stripping of the numbering, not the map of variants, not the
    skeleton.  A variation core must see θεῖος1 and θεῖος as two different lemmas,
    because the difference is real and the fifth plane exists, in part, to find it.
    """
    if tokens is None or tokens.empty:
        return tokens
    lavoro = tokens.copy()
    for colonna in ("form", "lemma"):
        if colonna in lavoro.columns:
            lavoro[colonna] = map_unique(
                lavoro[colonna].astype("string").fillna(""), nfc)
    return lavoro


def _content_tokens(tokens: pd.DataFrame) -> pd.DataFrame:
    """The words of the text: the unit ``words``, called by name.

    The definition of “word” is not repeated here: this function calls the unit
    ``words`` defined in :mod:`units`, the same one used by the Overview and by the
    article.  Three separately written definitions could diverge at the first
    modification of any of them, so the five planes of the variation n-gram declare
    the unit they work on instead of rebuilding it.
    """
    return tokens[np.asarray(is_word(tokens), dtype=bool)]


def _nuclei_from_pairs(
    keys: pd.Series,
    labels: pd.Series,
    *,
    kind: str,
    min_occurrences: int,
    max_labels: int | None = None,
    display: pd.Series | None = None,
    examples: pd.Series | None = None,
) -> pd.DataFrame:
    """Build the nucleus table from a (key, label) pair column, vectorised.

    Grouping seventy thousand distinct forms with a Python loop that filters the
    whole token table each time is quadratic and unusable on a real corpus. Two
    ``value_counts`` and one ``groupby.agg`` produce the same table in a couple
    of seconds.
    """
    frame = pd.DataFrame({
        "_key": keys.astype("string").fillna(""),
        "_label": labels.astype("string").fillna(""),
    })
    frame = frame[(frame["_key"] != "") & (frame["_label"] != "")]
    if frame.empty:
        return _empty()
    if display is not None:
        frame["_display"] = display.astype("string").fillna("").to_numpy()[
            : len(frame)] if len(display) == len(frame) else frame["_key"]
    if examples is not None and len(examples) == len(keys):
        frame["_example"] = examples.astype("string").fillna("").reindex(frame.index)

    counts = (frame.groupby(["_key", "_label"], sort=False)
              .size().reset_index(name="_n"))
    per_key = counts.groupby("_key", sort=False)
    label_count = per_key.size()
    total = per_key["_n"].sum()

    keep = label_count[label_count > 1].index
    if max_labels is not None:
        keep = keep.intersection(label_count[label_count <= max_labels].index)
    keep = keep.intersection(total[total >= min_occurrences].index)
    if len(keep) == 0:
        return _empty()

    counts = counts[counts["_key"].isin(keep)]
    counts = counts.sort_values(["_key", "_n"], ascending=[True, False], kind="stable")
    detail = grouped_join(
        counts["_label"] + " (" + counts["_n"].astype(str) + ")", counts["_key"], " · ")
    alphabetical = counts.sort_values(["_key", "_label"], kind="stable")
    joined = grouped_join(alphabetical["_label"], alphabetical["_key"], " | ")

    example_text = pd.Series("", index=keep, dtype="string")
    if "_example" in frame.columns:
        example_text = (frame[frame["_key"].isin(keep)]
                        .drop_duplicates("_key")
                        .set_index("_key")["_example"].reindex(keep).fillna(""))

    result = pd.DataFrame({
        "tipo": kind,
        "nucleo": [key.split("␟")[0] for key in keep],
        "chiave": [key.replace("␟", " / ") for key in keep],
        "n_etichette": label_count.reindex(keep).to_numpy(),
        "etichette": joined.reindex(keep).to_numpy(),
        "occorrenze": total.reindex(keep).to_numpy().astype(int),
        "distribuzione": detail.reindex(keep).to_numpy(),
        "esempi": example_text.to_numpy(),
    })
    return (result.sort_values(["occorrenze", "n_etichette"], ascending=False)
            .reset_index(drop=True))


# ---------------------------------------------------------------------------
# 1. Morphological variation
# ---------------------------------------------------------------------------

def pos_variation(
    tokens: pd.DataFrame,
    *,
    key: str = "form",
    min_occurrences: int = 2,
    max_labels: int | None = None,
) -> pd.DataFrame:
    """Word types annotated with more than one tag.

    *key* selects the nucleus: ``form`` (the classic unigram nucleus) or
    ``form+pos`` (Boyd et al. 2008, preprint: 22 — disambiguating by part of speech kills
    the homograph false positives at some cost in recall).
    """
    work = _content_tokens(tokens)
    if work.empty or "postag" not in work.columns:
        return _empty()

    work = work[work["postag"].notna()].copy()
    if key == "form+pos":
        nucleus = (work["form"].astype("string").fillna("") + "␟"
                   + work["postag"].astype("string").str[0].fillna(""))
    else:
        nucleus = work["form"].astype("string").fillna("")

    examples = (work["document_id"].astype("string").fillna("") + ", fr. "
                + work.get("sentence_id", pd.Series("", index=work.index))
                .astype("string").fillna(""))
    return _nuclei_from_pairs(
        nucleus, work["postag"], kind="morfologia",
        min_occurrences=min_occurrences, max_labels=max_labels, examples=examples)


def _position_inputs(tokens: pd.DataFrame):
    """The rows and columns shared by all nine per-position passes.

    Dropping punctuation, keeping the well-formed tags and pasting together the
    example reference does not depend on which slot is being examined, but it
    was redone nine times: three quarters of the 5.4 s of
    :func:`all_position_variation` went on work that only needed doing once.
    """
    work = _content_tokens(tokens)
    if work.empty or "postag" not in work.columns:
        return None
    tags = work["postag"].astype("string")
    usable = tags.str.len() == TAG_LENGTH
    work = work[usable]
    if work.empty:
        return None
    examples = (work["document_id"].astype("string").fillna("") + ", fr. "
                + work.get("sentence_id", pd.Series("", index=work.index))
                .astype("string").fillna(""))
    return work, tags[usable], examples


def _position_nuclei(work, tags, examples, position: int) -> pd.DataFrame:
    characters = tags.str[position]
    stated = characters != "-"
    if not stated.any():
        return _empty()
    label_it = POSITION_NAMES[position][0]
    return _nuclei_from_pairs(
        work.loc[stated, "form"], characters[stated],
        kind=f"posizione {position + 1} — {label_it}",
        min_occurrences=2, examples=examples[stated])


def position_variation(tokens: pd.DataFrame, position: int) -> pd.DataFrame:
    """Variation restricted to one slot of the tag.

    Running the nucleus test nine times, once per position, is the move that
    makes the method usable on AGDT: ``a-s---mn-`` vs ``a-s---fn-`` is a gender
    disagreement, and saying so is far more actionable than reporting that the
    two nine-character strings differ.
    """
    prepared = _position_inputs(tokens)
    if prepared is None:
        return _empty()
    return _position_nuclei(*prepared, position)


def all_position_variation(tokens: pd.DataFrame) -> pd.DataFrame:
    """The nine per-position tables, concatenated."""
    prepared = _position_inputs(tokens)
    if prepared is None:
        return _empty()
    parts = [_position_nuclei(*prepared, index) for index in range(TAG_LENGTH)]
    live = [part for part in parts if not part.empty]
    if not live:
        return _empty()
    return pd.concat(live, ignore_index=True)


# ---------------------------------------------------------------------------
# 2. n-gram extension with the non-fringe filter
# ---------------------------------------------------------------------------

def ngram_variation(
    tokens: pd.DataFrame,
    *,
    window: int = 1,
    min_occurrences: int = 2,
) -> pd.DataFrame:
    """Variation nuclei whose *context* is identical for *window* words each side.

    This is the filter that turns a noisy list into a usable one.  A word that
    varies in isolation may simply be ambiguous; a word that varies while its
    neighbours stay word-for-word identical is almost always an inconsistency.

    Two things this plane shares with the other four, and used not to.

    The **empty label does not enter**.  The other four planes go through
    :func:`_nuclei_from_pairs`, which drops any row whose key or label is empty;
    this one had its own loop and kept them, so a token with no ``postag``
    became a label of its own and could open a nucleus by itself.  It did, twice
    in the whole material: ``ἐν σ᾽ Κωμῳδουμένων`` in Gorman and ``εὖ ἴσθι ὅτι``
    in Pedalion.  Setting "annotated ``v2srma---``" against "not annotated" is
    not variation in the annotation but the absence of one, which the catalogue
    already reports on its own account with ``missing-postag``.

    The **sentence is the canonical one**, :func:`units.sentence_key`, and so is
    the reading order, :data:`units.SENTENCE_ORDER`.  The local key built here
    left out ``document_id``: harmless on the six corpora measured, where no
    file holds more than one document, and wrong on a resource that packs
    several documents into one file, where it would have built trigrams across a
    document boundary.
    """
    work = _content_tokens(tokens)
    if work.empty or "postag" not in work.columns:
        return _empty()

    work = work.sort_values(list(SENTENCE_ORDER))
    # Python lists, not numpy object arrays: slicing a list to build the context
    # tuple is a memcpy, while slicing a numpy array allocates a view that
    # ``tuple`` then has to walk element by element, boxing as it goes.  The
    # sentence key only ever gets compared for equality, so integer codes say
    # the same thing as the concatenated strings and compare in one instruction.
    forms = work["form"].astype("string").fillna("").to_numpy().tolist()
    tags = work["postag"].astype("string").fillna("").to_numpy().tolist()
    sentences = pd.factorize(sentence_key(work), sort=False)[0].tolist()

    buckets: dict[tuple[str, ...], dict[str, int]] = {}
    places: dict[tuple[str, ...], list[int]] = {}

    total = len(forms)
    for index in range(window, total - window):
        left, right = index - window, index + window
        here = sentences[index]
        if sentences[left] != here or sentences[right] != here:
            continue
        tag = tags[index]
        # The same rule as the other four planes: an empty key and an empty label do not
        # enter.  A token without ``postag`` does not carry a competing analysis of the
        # context but the lack of the analysis, which the catalogue reports on its own
        # account with ``missing-postag``; counting it as a label would turn a missing
        # annotation into a variant.
        if not tag:
            continue
        context = tuple(forms[left : right + 1])
        if not any(context):
            continue
        counts = buckets.get(context)
        if counts is None:
            buckets[context] = {tag: 1}
            places[context] = [index]
        else:
            counts[tag] = counts.get(tag, 0) + 1
            seen = places[context]
            # Only the first three ever reach the output.
            if len(seen) < 3:
                seen.append(index)

    rows: list[dict[str, object]] = []
    document_ids = work["document_id"].astype("string").fillna("").to_numpy()
    sentence_ids = work.get("sentence_id", pd.Series([""] * total)).astype("string").fillna("").to_numpy()
    for context, tag_counts in buckets.items():
        if len(tag_counts) < 2 or sum(tag_counts.values()) < min_occurrences:
            continue
        sample = places[context][:3]
        ranked = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)
        rows.append({
            "tipo": f"contesto ±{window}",
            "nucleo": context[window],
            "chiave": " ".join(context),
            "n_etichette": len(tag_counts),
            "etichette": " | ".join(sorted(tag_counts)),
            "occorrenze": int(sum(tag_counts.values())),
            "distribuzione": " · ".join(f"{tag} ({count})" for tag, count in ranked),
                "esempi": " · ".join(f"{document_ids[i]}, fr. {sentence_ids[i]}" for i in sample),
        })
    if not rows:
        return _empty()
    return (pd.DataFrame(rows)
            .sort_values(["occorrenze", "n_etichette"], ascending=False)
            .reset_index(drop=True))


# ---------------------------------------------------------------------------
# 3. Dependency variation
# ---------------------------------------------------------------------------


def dependency_variation(
    tokens: pd.DataFrame,
    *,
    strip_suffixes: bool = True,
    min_occurrences: int = 2,
) -> pd.DataFrame:
    """Pairs of words annotated with a different relation and direction.

    **What it is, and what it is not.**  GCP *adapts* the pair-based representation
    of Boyd, Dickinson and Meurers (2008: 123) for the variation of the label of the
    arcs that are present; it does not implement the full method.  The difference is
    substantial and has to be stated, not left to be understood.

    What GCP takes from the work: the core is a *pair* of words and not a single
    word, and the label carries the direction of the head — ``OBJ-L`` against
    ``OBJ-R`` — so that a label error and an error in the choice of the head come
    out as different in the output.

    What GCP does not take, and which in the original work is the central
    contribution: the ``NIL`` cores, which capture the *missing* arc instead of the
    wrong label; the merging into a set of labels of the overlapping type-identical
    dependencies (§ 4.1.3, which on the corpora examined concerns 465 cases in
    Gorman, 130 in Pedalion and 102 in GLAUx); and all three context heuristics of
    § 4.2, without which on TigerDB the authors went from 3 cores to 1,060.

    The NIL path exists, isolated, in :func:`dependency_variation_with_nil`, and is
    not reachable from here.
    """
    work = _content_tokens(tokens)
    needed = {"form", "relation", "token_id", "head"}
    if work.empty or not needed <= set(work.columns):
        return _empty()

    work = work.sort_values(list(SENTENCE_ORDER))
    sentence_keys = sentence_key(work)
    token_ids = pd.to_numeric(work["token_id"], errors="coerce")
    head_ids = pd.to_numeric(work["head"], errors="coerce")
    relation_text = work["relation"].astype("string").fillna("")
    if strip_suffixes:
        relation_text = map_unique(relation_text, base_relation)

    # Everything the loop reads is pulled out of pandas once, as plain Python
    # lists, and a sentence becomes a slice of them.  Asking pandas for the six
    # columns of each of the 26,616 groups would spend most of the time inside
    # groupby's row slicing and in constructing one ArrowStringArray per column
    # per group, before any counting happened.  The
    # stable sort by sentence code reproduces ``groupby(sort=False)`` exactly:
    # groups in order of first appearance, rows inside a group in table order.
    codes = pd.factorize(sentence_keys, sort=False)[0]
    order = np.argsort(codes, kind="stable")
    bounds = np.zeros(int(codes.max()) + 2, dtype="int64")
    np.cumsum(np.bincount(codes), out=bounds[1:])

    def flat(values, absent: object = "") -> list:
        if values is None:
            return [absent] * len(work)
        return values.to_numpy()[order].tolist()

    all_ids = flat(token_ids)
    all_id_present = flat(token_ids.notna())
    all_heads = flat(head_ids)
    all_head_present = flat(head_ids.notna())
    all_forms = flat(work["form"].astype("string").fillna(""))
    all_documents = flat(work.get("document_id"))
    all_sentence_labels = flat(work.get("sentence_id"))
    # The label is the relation plus the direction marker.  Composing it with an
    # f-string built 536,451 one-off strings whose hash then had to be computed
    # from scratch for every dictionary operation; deriving the two variants once
    # per distinct relation makes each occurrence a list lookup that hands back
    # the same interned object.
    all_left = flat(map_unique(relation_text, lambda value: f"{value}-L"))
    all_right = flat(map_unique(relation_text, lambda value: f"{value}-R"))

    labels: dict[tuple[str, str], dict[str, int]] = {}
    places: dict[tuple[str, str], list[tuple[str, object]]] = {}

    for sentence in range(len(bounds) - 1):
        start, stop = bounds[sentence], bounds[sentence + 1]
        ids = all_ids[start:stop]
        present = all_id_present[start:stop]
        id_to_row = {value: position
                     for position, value in enumerate(ids) if present[position]}
        forms = all_forms[start:stop]
        left_labels = all_left[start:stop]
        right_labels = all_right[start:stop]
        heads = all_heads[start:stop]
        head_present = all_head_present[start:stop]
        document = all_documents[start]
        sentence_label = all_sentence_labels[start]

        for position, head in enumerate(heads):
            if not head_present[position] or float(head) == 0:
                continue
            head_row = id_to_row.get(float(head))
            if head_row is None:
                continue
            if head_row < position:
                low, high = head_row, position
                label = left_labels[position]
            else:
                low, high = position, head_row
                label = right_labels[position]
            key = (forms[low], forms[high])
            counts = labels.get(key)
            if counts is None:
                labels[key] = {label: 1}
                places[key] = [(document, sentence_label)]
            else:
                counts[label] = counts.get(label, 0) + 1
                seen = places[key]
                # Only the first three ever reach the output.
                if len(seen) < 3:
                    seen.append((document, sentence_label))

    rows: list[dict[str, object]] = []
    for key, label_counts in labels.items():
        if len(label_counts) < 2 or sum(label_counts.values()) < min_occurrences:
            continue
        ranked = sorted(label_counts.items(), key=lambda item: item[1], reverse=True)
        rows.append({
            "tipo": "dipendenza",
            "nucleo": f"{key[0]} … {key[1]}",
            "chiave": f"{key[0]}␟{key[1]}",
            "n_etichette": len(label_counts),
            "etichette": " | ".join(sorted(label_counts)),
            "occorrenze": int(sum(label_counts.values())),
            "distribuzione": " · ".join(f"{label} ({count})"
                                        for label, count in ranked),
            "esempi": " · ".join(f"{doc}, fr. {sent}" for doc, sent in places[key][:3]),
        })
    if not rows:
        return _empty()
    frame = pd.DataFrame(rows)
    return (frame.sort_values(["occorrenze", "n_etichette"], ascending=[False, False])
            .reset_index(drop=True))




# ---------------------------------------------------------------------------
# The NIL path: experimental, unused, unofficial
# ---------------------------------------------------------------------------

def dependency_variation_with_nil(*args, **kwargs) -> pd.DataFrame:
    """The NIL cores of Boyd et al. — **not implemented, and deliberately so**.

    In the original method the ``NIL`` core is the central contribution to the case
    of dependencies: a pair of words linked by an arc at one point of the corpus and
    merely co-present at another generates the label ``NIL``, and that captures the
    *missing* arc instead of the wrong label.  Boyd, Dickinson and Meurers motivate
    it well: a wrong NIL implies at least one *other* error in the same sentence,
    because the dependent has been attached elsewhere by mistake, and so it is worth
    rereading the whole sentence.

    GCP does not activate it, and the reason is not cost.  It is that the full
    method filters the candidates with three context heuristics (Boyd et al. 2008,
    § 4.2) and GCP implements none of them.  Without context, the authors' own
    numbers say what happens: on TigerDB they went from 3 cores with the non-fringe
    heuristic to 1,060 with none.  On Gorman the ratio is of the same order —
    switching the NILs on would multiply the dependency plane several times over —
    and none of those additional cores would be filtered.

    Activating them without first implementing and validating the heuristics would
    produce a large quantity of unfiltered candidates, and present them next to
    cores that have been filtered: two different things under the same name.

    The function exists to carry this reasoning next to the code it refers to, and
    to be the place where the work will have to be done.  It raises.
    """
    raise NotImplementedError(
        "NIL nuclei are not part of the official results of GCP: the "
        "program does not implement the context heuristics that the full "
        "method of Boyd et al. (2008, § 4.2) provides, and without them the "
        "candidates would not be filtered. See the docstring of this function."
    )


# ---------------------------------------------------------------------------
# 4. Lemma variation
# ---------------------------------------------------------------------------

def lemma_variation(tokens: pd.DataFrame, *, use_pos: bool = True) -> pd.DataFrame:
    """One surface form, one part of speech, several lemmas."""
    work = _content_tokens(tokens)
    if work.empty or "lemma" not in work.columns:
        return _empty()
    work = work[work["lemma"].notna()].copy()
    if use_pos and "postag" in work.columns:
        work["_key"] = (work["form"].astype("string").fillna("") + "␟"
                        + work["postag"].astype("string").str[0].fillna(""))
    else:
        work["_key"] = work["form"].astype("string").fillna("")

    examples = (work["document_id"].astype("string").fillna("") + ", fr. "
                + work.get("sentence_id", pd.Series("", index=work.index))
                .astype("string").fillna(""))
    return _nuclei_from_pairs(
        work["_key"], work["lemma"], kind="lemma",
        min_occurrences=2, examples=examples)


# ---------------------------------------------------------------------------
# 5. Label confusion matrix
# ---------------------------------------------------------------------------

def label_confusion(nuclei: pd.DataFrame, top: int = 40) -> pd.DataFrame:
    """Which label pairs get confused, and how often.

    Boyd et al. (2008, preprint: 18) argue that the *classes* of error matter more than
    the individual tokens: a human annotator who learns that ``ATR`` and ``ADV``
    are being swapped can fix a hundred cases, while a list of a hundred rows
    tells them nothing.  This aggregates the nuclei into exactly that view.
    """
    if nuclei is None or nuclei.empty or "etichette" not in nuclei.columns:
        return pd.DataFrame(columns=["etichetta A", "etichetta B", "nuclei", "occorrenze"])

    pairs: Counter = Counter()
    weights: Counter = Counter()
    for labels, occurrences in zip(nuclei["etichette"], nuclei.get("occorrenze", 0)):
        parts = sorted({part.strip() for part in str(labels).split("|") if part.strip()})
        for index, first in enumerate(parts):
            for second in parts[index + 1:]:
                pairs[(first, second)] += 1
                weights[(first, second)] += int(occurrences or 0)

    rows = [
        {"etichetta A": first, "etichetta B": second,
         "nuclei": count, "occorrenze": weights[(first, second)]}
        for (first, second), count in pairs.most_common(top)
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_variation_suite(
    tokens: pd.DataFrame,
    *,
    do_pos: bool = True,
    do_positions: bool = True,
    do_ngram: bool = True,
    do_dependency: bool = True,
    do_lemma: bool = True,
    ngram_window: int = 1,
) -> dict[str, pd.DataFrame]:
    """Runs the five requested planes and returns them by name.

    **The comparison keys are normalised to NFC; the data stays as it is.**  The
    normalisation serves to prevent the same string, written in NFC in one place and
    in NFD in another, from turning out as two different strings for a purely
    technical reason: GLAUx writes 47,840 of its 48,513 distinct forms in NFD, and
    in Pedalion 280 types are duplicates that without NFC the program would count
    twice.  The original text is not touched, and it is essential that it is not:
    four checks of the catalogue — “Encoding not normalised to NFC”, “Corpus
    predominantly in NFD”, “Final number in the lemma” and “Competing graphic
    variants of the same lemma” — exist to report exactly what a normalisation
    applied to the data would erase.

    There is no ``include_nil`` parameter: see :func:`dependency_variation_with_nil`.
    """
    tokens = comparison_keys(tokens)
    result: dict[str, pd.DataFrame] = {}
    if do_pos:
        result["morfologia"] = pos_variation(tokens, key="form")
    if do_positions:
        result["posizioni"] = all_position_variation(tokens)
    if do_ngram:
        result["contesto"] = ngram_variation(tokens, window=ngram_window)
    if do_dependency:
        result["dipendenze"] = dependency_variation(tokens)
    if do_lemma:
        result["lemmi"] = lemma_variation(tokens)
    return result
