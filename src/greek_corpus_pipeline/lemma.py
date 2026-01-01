from __future__ import annotations

import re
import unicodedata

import pandas as pd

from . import issue_testi, resources
from .normalise import nfc, without_lemma_numbering
from .fastmap import build_frame, grouped_join, map_unique, mask_unique
from .rule_catalog import default_auto_apply, rule_description, rule_name


#: The spellings that different corpora use for the same lemma, and the form on
#: which they align when compared. A versioned data resource: it applies only
#: to the comparison between resources, because applying it to the counts of a
#: single corpus would rewrite its lexicon according to the convention of
#: another.
NOTEBOOK_LEMMA_NORMALIZATIONS = resources.entries("varianti-canoniche-di-lemma")

# A trailing digit is not always the same thing, and the corpus says so: of the
# 72,836 active Gorman records whose lemma carries one, 62,236 are ``punc1``, the
# corpus's own lemma for punctuation, while the rest are the homograph numbers of
# the source lexicon (λέγω1, λέγω2 and λέγω3 are three different verbs in LSJ).  Stripping
# the digit is kept — it is what every count in this program assumes — but it
# merges entries the source project deliberately kept apart, so the rule that
# proposes it says so instead of calling the digit meaningless.
_TRAILING_DIGIT_RE = re.compile(r"\d+$")


#: Characters that have no business in a dictionary headword and that mark the
#: convention of the project the lemma came from: Perseus writes compounds with
#: a hyphen (διά-λέγω), PROIEL brackets optional letters, and a digit inside the
#: string is never part of a Greek word.  Gorman has 335 such lemmas over 804
#: tokens, Pedalion 14 over 17.
_SUSPICIOUS_LEMMA_RE = re.compile(r"[-\u2010\u2011\u2012\u2013\u2014()\[\]{}]|\d(?!$)")


def normalize_lemma(lemma: object) -> object:
    if not isinstance(lemma, str):
        return lemma
    normalized = unicodedata.normalize("NFC", lemma.strip())
    normalized = _TRAILING_DIGIT_RE.sub("", normalized)
    return NOTEBOOK_LEMMA_NORMALIZATIONS.get(normalized, normalized)


def lemma_normalisation_step(lemma: object) -> str:
    """Which of the three normalisations a lemma needs (``""`` if none).

    The three are reported as separate checks, because they have nothing in
    common: most of those findings are a digit an annotation tool appended, a
    few hundred are the hand-made list of graphic variants, and in Pedalion the
    rest are a Unicode encoding difference that ``unicode-not-nfc`` already
    reports by name.
    """
    if not isinstance(lemma, str):
        return ""
    composed = unicodedata.normalize("NFC", lemma.strip())
    without_digits = _TRAILING_DIGIT_RE.sub("", composed)
    if NOTEBOOK_LEMMA_NORMALIZATIONS.get(without_digits, without_digits) != without_digits:
        return "variant"
    if without_digits != composed:
        return "numbering"
    if composed != lemma:
        return "nfc"
    return ""


def build_lemma_inventory(tokens: pd.DataFrame) -> pd.DataFrame:
    """One row per word form: its lemmas, its tags, how ambiguous it is.

    The three "which distinct values does this form take" columns are not built
    with Python aggregators handed to ``groupby.agg``, which would make pandas
    build a Series for each of the 69,461 groups three times over: about 26 s on
    Gorman, and a wait the user would meet every time the lemma dictionary
    opens.  Deduplicating and sorting the (form, value) pairs once and joining
    the sorted runs gives the same strings in about 1.4 s.
    """
    valid = tokens[tokens["form"].notna()].copy()
    valid["normalized_lemma"] = map_unique(valid["lemma"], normalize_lemma)

    grouped = valid.groupby("form", sort=True)
    counts = grouped.size().rename("occurrences")

    def _join_unique(column: str) -> pd.Series:
        """``' | '.join(sorted({str(v) for v in values}))`` per form."""
        present = valid[valid[column].notna()]
        # The columns go in as they are: converting them to object arrays first
        # would make pandas re-infer the string dtype on the way back in, for a
        # frame that is thrown away three lines later.
        pairs = pd.DataFrame({"_form": present["form"],
                              "_text": map_unique(present[column], str)})
        # Deduplicate on the rendered text, as the set comprehension did, and
        # sort inside each form with Python's own string ordering.
        pairs = pairs.drop_duplicates().sort_values(["_form", "_text"], kind="stable")
        return (grouped_join(pairs["_text"], pairs["_form"], " | ")
                .reindex(counts.index).fillna(""))

    info = pd.DataFrame({
        "lemmas": _join_unique("lemma"),
        "normalized_lemmas": _join_unique("normalized_lemma"),
        "postags": _join_unique("postag"),
        "lemma_count": grouped["lemma"].nunique(),
    })
    result = counts.to_frame().join(info).reset_index()
    return result.sort_values(
        ["lemma_count", "occurrences", "form"], ascending=[False, False, True]
    ).reset_index(drop=True)


def _make_lemma_findings(
    subset: pd.DataFrame,
    rule_id: str,
    issue_params: "object | pd.Series" = None,
    suggested_lemma: object | pd.Series = pd.NA,
    auto_correctable: bool = False,
    issue_key: "str | pd.Series | None" = None,
) -> pd.DataFrame:
    """Build a findings DataFrame from a filtered token subset (no Python loop)."""
    if subset.empty:
        return pd.DataFrame()
    base_cols = [c for c in [
        "source_file", "document_id", "sentence_index", "sentence_id",
        "token_index", "token_id", "form", "lemma", "postag",
    ] if c in subset.columns]
    columns = {
        "rule_id": rule_id,
        "anomaly_name": rule_name(rule_id),
        "anomaly_description": rule_description(rule_id),
    }
    for col in base_cols:
        columns[col] = subset[col]
    columns["issue_key"] = rule_id if issue_key is None else issue_key
    columns["issue_params"] = "" if issue_params is None else issue_params
    columns["suggested_lemma"] = suggested_lemma
    columns["auto_correctable"] = auto_correctable and default_auto_apply(rule_id)
    frame = build_frame(columns, len(subset))
    frame["issue"] = issue_testi.rendi_serie(frame, "it")
    return frame[[c for c in _EMPTY_LEMMA_COLUMNS if c in frame.columns]]


_EMPTY_LEMMA_COLUMNS = [
    "rule_id", "anomaly_name", "anomaly_description",
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "form", "lemma", "postag",
    "issue", "issue_key", "issue_params", "suggested_lemma", "auto_correctable",
]


def analyze_lemmas(tokens: pd.DataFrame) -> pd.DataFrame:
    """Detect lemma anomalies.

    Returns one row per anomalous *token* for missing/normalizable rules,
    and one row per ambiguous *form* for the multiple-lemmas rule.
    """
    if tokens.empty:
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)

    working = tokens.copy()
    # Normalisation and the "is this lemma usable" test both read the lemma and
    # nothing else, so both are asked once per distinct value instead of once
    # per token: the distinct lemmas are a small fraction of the occurrences,
    # and most of what is saved is the regular expression for the trailing digit.
    working["normalized_lemma"] = map_unique(working["lemma"], normalize_lemma)

    # 1. Missing lemma (vectorized)
    missing_mask = working["lemma"].isna() | mask_unique(
        working["lemma"], lambda x: not isinstance(x, str) or not x.strip())
    findings_parts: list[pd.DataFrame] = []
    if missing_mask.any():
        findings_parts.append(_make_lemma_findings(
            working[missing_mask],
            "missing-lemma",
            suggested_lemma=pd.NA,
            auto_correctable=default_auto_apply("missing-lemma"),
        ))

    # 2. Normalisable lemma, split by the reason it needs normalising.
    #
    # A lemma can need more than one step; the label names the step that decides
    # the final form, and the proposal is always the fully canonical lemma, so
    # nothing is silently left half-normalised.  Pure NFC cases are left to
    # unicode-not-nfc: that rule names the cause (two encodings of one
    # word), belongs to the text-and-encoding family where the rest of the
    # Unicode work is done, and proposes the same string.  Reporting them here
    # too meant 532 Pedalion tokens counted twice in the same table.
    step = map_unique(working["lemma"], lemma_normalisation_step)

    numbering = (~missing_mask) & (step == "numbering")
    if numbering.any():
        findings_parts.append(_make_lemma_findings(
            working[numbering],
            "lemma-tool-numbering",
            suggested_lemma=working.loc[numbering, "normalized_lemma"],
            auto_correctable=default_auto_apply("lemma-tool-numbering"),
        ))

    # The pair must exist in this corpus.
    #
    # The list comes from the survey of Gorman and Pedalion, and applied to a third
    # corpus it would say false things: GLAUx writes ἀείρω 56 times and αἴρω never, ποτέ
    # 183 times and ποτε never, and the program would propose rewriting all the
    # occurrences in the spelling that that corpus does not use. This is not normalising
    # an internal variant: it is exporting the choice of another corpus. The finding
    # makes sense only where the two spellings really coexist, and that is where the
    # question “which of the two to count” arises.
    attested = set(working["lemma"].astype("string").fillna("")
                   .map(lambda value: unicodedata.normalize("NFC", value)))
    both_present = map_unique(
        working["normalized_lemma"],
        lambda value: isinstance(value, str) and value in attested)
    variant = (~missing_mask) & (step == "variant") & both_present.fillna(False)
    if variant.any():
        findings_parts.append(_make_lemma_findings(
            working[variant],
            "lemma-graphic-variant",
            suggested_lemma=working.loc[variant, "normalized_lemma"],
            auto_correctable=default_auto_apply("lemma-graphic-variant"),
        ))

    # 3. Multiple lemmas per form — one finding per form, not per token.
    #
    # Written with grouped aggregations rather than a per-form loop. The
    # readable version does `working[working["form"] == form]` inside a loop
    # over seventy thousand distinct forms, which is a full scan of six hundred
    # thousand rows each time: quadratic, and it turned this single rule into a
    # minute of the analysis on the Gorman corpus. The output is identical.
    #
    # The check “A form associated with several lemmas” is deliberately not among
    # the diagnostic checks: in Greek homography is the norm, and the condition
    # “same form, several lemmas” describes the language, not a defect of the
    # corpus. In Gorman there are about 2,500 such forms, and with the part of
    # speech in the key about 2,100 remain: it is not a defect that shrinks by
    # adding information, it is ὅς that really has several dictionary entries.
    #
    # The information is not lost. The statistics count it, the “Profile of a
    # lemma” card shows it, and the fifth level of the variation n-gram looks for
    # the same thing at equal part of speech. It does not enter the
    # totals of the diagnostic findings.
    #
    # The function that computes it is :func:`ambiguous_forms`, below.

    # 4. Suspicious characters, and 5. a rare lemma against a dominant one.
    findings_parts.append(check_suspicious_lemma_characters(working))
    findings_parts.append(check_rare_lemma_for_form(working))

    findings_parts = [part for part in findings_parts if part is not None and not part.empty]
    if not findings_parts:
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)
    return pd.concat(findings_parts, ignore_index=True)


def ambiguous_forms(working: pd.DataFrame) -> pd.DataFrame:
    """The forms that receive more than one dictionary entry in the corpus.

    It is a statistic and not a diagnostic check, because that is what it is: in
    Greek homography is normal, and a form with several lemmas is not in itself a
    defect. The table serves the “Profile of a lemma” card and the lexical
    statistics, where the right question is not “how many anomalies” but “how
    ambiguous is this lexicon”.

    It returns one row per form, sorted by number of occurrences: the form, the
    lemmas it receives, how many they are and how many times it appears.
    """
    colonne = ["forma", "lemmi", "n_lemmi", "occorrenze"]
    if working is None or working.empty:
        return pd.DataFrame(columns=colonne)
    needed = {"form", "normalized_lemma"}
    if not needed <= set(working.columns):
        return pd.DataFrame(columns=colonne)

    present = working[working["form"].notna() & working["normalized_lemma"].notna()]
    if present.empty:
        return pd.DataFrame(columns=colonne)

    pairs = (present[["form", "normalized_lemma"]]
             .astype({"form": "string", "normalized_lemma": "string"})
             .drop_duplicates()
             .sort_values(["form", "normalized_lemma"], kind="stable"))
    per_form = pairs.groupby("form", sort=False)["normalized_lemma"]
    counts = per_form.size()
    ambiguous = counts[counts > 1]
    if ambiguous.empty:
        return pd.DataFrame(columns=colonne)

    wanted = pairs[pairs["form"].isin(ambiguous.index)]
    joined = (wanted.groupby("form", sort=False)["normalized_lemma"]
              .agg(", ".join).reindex(ambiguous.index))
    occurrences = (present["form"].astype("string")
                   .value_counts().reindex(ambiguous.index).fillna(0))
    table = pd.DataFrame({
        "forma": ambiguous.index.to_numpy(),
        "lemmi": joined.to_numpy(),
        "n_lemmi": ambiguous.to_numpy().astype(int),
        "occorrenze": occurrences.to_numpy().astype(int),
    })
    return table.sort_values(["occorrenze", "n_lemmi"],
                             ascending=False).reset_index(drop=True)


def check_suspicious_lemma_characters(working: pd.DataFrame) -> pd.DataFrame:
    """Lemmas carrying hyphens, brackets or internal digits.

    Declared in the catalogue since the beginning and never implemented, which
    is worse than not declaring it.  Punctuation tokens are excluded: a comma
    lemmatised as "," is not an anomaly, and including them would have turned a
    real signal (817 Gorman tokens spelled the Perseus way, διά-λέγω) into noise.
    """
    if "lemma" not in working.columns:
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)
    lemmas = working["lemma"].astype("string").fillna("")
    postags = working["postag"].astype("string").fillna("") if "postag" in working.columns \
        else pd.Series("", index=working.index, dtype="string")
    mask = mask_unique(lemmas, lambda value: bool(_SUSPICIOUS_LEMMA_RE.search(value)))
    mask &= ~postags.str.startswith("u")
    if not mask.any():
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)
    return _make_lemma_findings(
        working[mask], "lemma-suspicious-characters", suggested_lemma=pd.NA)


def _chiave_lemma_intracorpus(lemma: object) -> str:
    """The key with which the rare-lemma check compares lemmas.

    Two normalisations and not three, and the third is excluded for a precise
    reason.

    **NFC**, because it is Unicode identity: two writings of the same string are
    the same string, and there is no lexical interpretation in between.

    **Cutting of the Perseus numbering**, because that numbering is an artefact of
    the tool that annotated, not a choice of lemma: without the cut, ``Ζεύς1``
    and ``Ζεύς2`` would produce a distribution of lemmas that is not the one the
    check wants to measure. The phenomenon already has its own check, “Trailing
    number in the lemma”, and this one must not chase it.

    **The map of canonical variants, no.** That map exists to make the lexical
    conventions of different resources comparable, and this check measures the
    *internal* consistency of a single resource. Applying it here would transform,
    before the comparison, precisely the difference that the check must be able
    to observe.

    This is not an abstraction: the map hid two true findings. In Gorman the form
    ``τ᾽`` is lemmatised ``τέ`` once only against ``τε`` in all the others, and
    the map collapsed the two spellings before the check saw them. In Pedalion
    the same thing happens with ``νοῦν`` lemmatised ``νοῦς`` against ``νόος``.
    These are two inconsistencies of lemmatisation internal to the corpus, and
    they are exactly the phenomenon for which the check was built.
    """
    return without_lemma_numbering(nfc(lemma))


def check_rare_lemma_for_form(
    working: pd.DataFrame,
    *,
    min_form_total: int = 25,
    max_rare: int = 1,
    min_major_share: float = 0.95,
) -> pd.DataFrame:
    """A form and part of speech lemmatised once against all the others.

    The group is the pair **(form, part of speech)**, not the form alone. With the
    form alone, two homographs of different category would end up in the same
    group and the lemma of one would appear “rare” for the other. That in
    automatic GLAUx the count falls to zero is the right result: that corpus is
    automatic and consistent, and it did not have that inconsistency.

    With the adopted parameters (25 · 1 · 0.95) the check reports 102 findings in
    Gorman, 41 in Pedalion and 0 in the first automatic GLAUx sample.

    The key of the lemma is :func:`_chiave_lemma_intracorpus`: NFC and cutting of
    the numbering, without the map of canonical variants.

    The thresholds are the declared ones, and are deliberately strict: the pair
    must appear at least twenty-five times, the anomalous lemma exactly once, and
    the dominant lemma must cover at least 95% of the occurrences. Greek is
    homographic by nature and the rule must not start arguing with ὅς. What
    survives is clear-cut: δὲ lemmatised οὐδέ once against 13,539 times δέ, a
    comma lemmatised Ζεύς.
    """
    colonna_lemma = "lemma" if "lemma" in working.columns else "normalized_lemma"
    needed = {"form", colonna_lemma}
    if working.empty or not needed <= set(working.columns):
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)
    present = working[working["form"].notna() & working[colonna_lemma].notna()]
    if present.empty:
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)

    forma = present["form"].astype("string")
    pos = (present["postag"].astype("string").fillna("").str[0].fillna("")
           if "postag" in present.columns
           else pd.Series("", index=present.index, dtype="string"))
    lemma = map_unique(present[colonna_lemma].astype("string").fillna(""),
                       _chiave_lemma_intracorpus)

    pairs = (pd.DataFrame({"form": forma.to_numpy(), "pos": pos.to_numpy(),
                           "lemma": lemma.to_numpy()})
             .groupby(["form", "pos", "lemma"], sort=False).size()
             .rename("n").reset_index())
    pairs["total"] = pairs.groupby(["form", "pos"])["n"].transform("sum")
    major = (pairs.sort_values("n", ascending=False)
             .drop_duplicates(["form", "pos"])
             .set_index(["form", "pos"])[["lemma", "n"]])
    gruppo = pd.MultiIndex.from_arrays([pairs["form"], pairs["pos"]])
    pairs["major"] = major["lemma"].reindex(gruppo).to_numpy()
    pairs["major_n"] = major["n"].reindex(gruppo).to_numpy()

    rare = pairs[(pairs["total"] >= min_form_total)
                 & (pairs["n"] <= max_rare)
                 & (pairs["lemma"] != pairs["major"])
                 & (pairs["major_n"] / pairs["total"] >= min_major_share)]
    if rare.empty:
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)

    keys = dict(zip(zip(rare["form"], rare["pos"], rare["lemma"]),
                    zip(rare["major"], rare["major_n"], rare["total"])))
    token_keys = list(zip(forma, pos, lemma))
    mask = pd.Series([key in keys for key in token_keys], index=present.index)
    if not mask.any():
        return pd.DataFrame(columns=_EMPTY_LEMMA_COLUMNS)
    subset = present[mask]
    chosen = [keys[key] for key in token_keys if key in keys]
    suggested = pd.Series([value[0] for value in chosen], index=subset.index, dtype="object")
    # The two counts are an aggregate on the pair form and part of speech: they are not
    # in any column of the finding. The majority lemma, instead, is in
    # ``suggested_lemma``, and is read from there at the “Correct” step.
    maggioranza = pd.Series([int(value[1]) for value in chosen],
                            index=subset.index).astype("Int64")
    totale = pd.Series([int(value[2]) for value in chosen],
                       index=subset.index).astype("Int64")
    return _make_lemma_findings(
        subset, "lemma-rare-for-form",
        issue_testi.parametri(maggioranza=maggioranza, totale=totale),
        suggested_lemma=suggested)
