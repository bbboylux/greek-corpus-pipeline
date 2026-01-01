from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .fastmap import grouped_join, map_unique
from .lemma import analyze_lemmas, build_lemma_inventory, normalize_lemma
from .postag import RULE_PRIORITY, analyze_postags
from .rule_catalog import auto_applicable_rule_ids, rule_name


PUNCTUATION_FORMS = {
    ".",
    ",",
    ";",
    ":",
    "·",
    "·",
    "—",
    "-",
    "…",
    "...",
    "“",
    "”",
    "‘",
    "’",
    "'",
    '"',
    "(",
    ")",
    "[",
    "]",
}


# Author names by TLG identifier.
#
# They are read from the catalogues in ``data/`` — ``tlg_authors.csv`` for the authors
# of Gorman and Pedalion, the GLAUx catalogue for another three hundred — so that there
# is a single place in which a pair can be wrong. Coverage is 311 identifiers.
@lru_cache(maxsize=1)
def _tlg_author_names() -> dict[str, str]:
    """Author name by TLG identifier, read from the catalogues."""
    from .corpus_metadata import load_glaux_catalogue, load_tlg_authors

    names: dict[str, str] = {}
    # GLAUx first, then the curated table: where both know an author, the curated one
    # decides.
    for table in (load_glaux_catalogue(), load_tlg_authors()):
        if table.empty or not {"tlg_author", "author_en"} <= set(table.columns):
            continue
        for identifier, name in zip(table["tlg_author"], table["author_en"]):
            key = str(identifier or "").strip().lower()
            value = str(name or "").strip()
            if key and value:
                names[key] = value
    return names


def infer_author_name(document_id: object, source_file: object) -> str:
    """Infer a human-readable author name from the document filename.

    Handles TLG-format filenames (e.g. tlg0006.tlg001.perseus-grc2.tb.xml)
    and plain human-readable filenames (e.g. apollodorus-library-1.xml).
    """
    candidate = source_file if isinstance(source_file, str) and source_file.strip() else document_id
    if not isinstance(candidate, str) or not candidate.strip():
        return "Unknown"

    stem = Path(candidate).stem.lower()

    # TLG identifier: match "tlgNNNN" at the start
    tlg_match = re.match(r"(tlg\d{4})", stem)
    if tlg_match:
        tlg_id = tlg_match.group(1)
        return _tlg_author_names().get(tlg_id, tlg_id.upper())

    # Human-readable: take the portion before the first dot, then split on hyphens
    base = stem.split(".")[0]
    parts = [p for p in base.replace("_", "-").split("-") if p.isalpha()]
    if parts:
        return parts[0].title()

    return "Unknown"


def infer_work_label(document_id: object, source_file: object) -> str:
    candidate = source_file if isinstance(source_file, str) and source_file.strip() else document_id
    if not isinstance(candidate, str) or not candidate.strip():
        return "Unknown"
    return Path(candidate).stem


@lru_cache(maxsize=8192)
def _infer_labels_cached(document_id: object, source_file: object) -> tuple[str, str]:
    """Author/work labels for one document, memoized.

    A corpus has a few hundred documents but hundreds of thousands of tokens,
    so resolving the labels once per distinct (document_id, source_file) pair
    instead of once per row turns the dominant cost of every by-author summary
    into a dict lookup.
    """
    return (infer_author_name(document_id, source_file),
            infer_work_label(document_id, source_file))


def add_corpus_labels(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    enriched = frame.copy()
    need_author = "author" not in enriched.columns
    need_work   = "work"   not in enriched.columns
    if not (need_author or need_work):
        return enriched

    missing = pd.Series([pd.NA] * len(enriched), index=enriched.index)
    document_ids = enriched["document_id"] if "document_id" in enriched.columns else missing
    source_files = enriched["source_file"] if "source_file" in enriched.columns else missing

    # The labels depend on the (document_id, source_file) pair and on nothing
    # else, and a corpus has a few dozen of those against 625,176 rows. A cache
    # would make the second visit to a pair cheap, but the walk itself would still
    # be 625,176 tuple lookups over two Arrow-backed columns, and every by-author
    # summary starts with it.
    document_codes, document_values = pd.factorize(document_ids, use_na_sentinel=False)
    source_codes, source_values = pd.factorize(source_files, use_na_sentinel=False)
    width = max(len(source_values), 1)
    pairs, back = np.unique(document_codes * width + source_codes, return_inverse=True)

    def _text(value: object) -> object:
        return value if isinstance(value, str) else None

    labels = [
        _infer_labels_cached(_text(document_values[pair // width]),
                             _text(source_values[pair % width]))
        for pair in pairs
    ]
    if need_author:
        enriched["author"] = np.array(
            [author for author, _ in labels], dtype=object)[back].tolist()
    if need_work:
        enriched["work"] = np.array(
            [work for _, work in labels], dtype=object)[back].tolist()
    return enriched


def summarize_corpus(tokens: pd.DataFrame) -> dict[str, int]:
    non_punct = tokens[~tokens["form"].isin(PUNCTUATION_FORMS)]
    return {
        "documents": int(tokens["document_id"].nunique()),
        "sentences": int(tokens[["document_id", "sentence_index"]].drop_duplicates().shape[0]),
        "tokens": int(len(tokens)),
        "tokens_without_punctuation": int(len(non_punct)),
        "unique_forms": int(tokens["form"].dropna().nunique()),
        "unique_lemmas": int(tokens["lemma"].dropna().nunique()),
        "missing_lemmas": int(tokens["lemma"].isna().sum()),
        "missing_postags": int(tokens["postag"].isna().sum()),
    }


def summarize_corpus_by_group(tokens: pd.DataFrame, group_column: str) -> pd.DataFrame:
    tokens = add_corpus_labels(tokens)
    if tokens.empty or group_column not in tokens.columns:
        return pd.DataFrame()

    grouped = (
        tokens.groupby(group_column, dropna=False)
        .agg(
            documents=("document_id", "nunique"),
            source_files=("source_file", "nunique"),
            sentences=("sentence_index", "nunique"),
            tokens=("form", "size"),
            unique_forms=("form", "nunique"),
            unique_lemmas=("lemma", "nunique"),
            missing_lemmas=("lemma", lambda values: int(values.isna().sum())),
            missing_postags=("postag", lambda values: int(values.isna().sum())),
        )
        .reset_index()
        .sort_values("tokens", ascending=False)
    )
    return grouped


def summarize_findings_by_rule(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return pd.DataFrame(
            columns=[
                "rule_id",
                "findings",
                "documents",
                "forms",
                "auto_correctable",
            ]
        )

    # The name of the check is always derived from the rule, even when the column is
    # present: that column is created at the time of the analysis and carries the
    # language of that moment, not that of whoever reads the summary now.
    findings = findings.copy()
    findings["anomaly_name"] = findings["rule_id"].map(rule_name)

    summary = (
        findings.groupby(["rule_id", "anomaly_name"], dropna=False)
        .agg(
            findings=("rule_id", "size"),
            documents=("document_id", "nunique"),
            forms=("form", "nunique"),
            auto_correctable=("auto_correctable", "sum"),
        )
        .reset_index()
        .sort_values(["findings", "rule_id"], ascending=[False, True])
    )
    return summary


def summarize_findings_by_group(findings: pd.DataFrame, group_column: str) -> pd.DataFrame:
    findings = add_corpus_labels(findings)
    if findings.empty or group_column not in findings.columns:
        return pd.DataFrame()

    summary = (
        findings.groupby(group_column, dropna=False)
        .agg(
            findings=("rule_id", "size"),
            unique_rules=("rule_id", "nunique"),
            documents=("document_id", "nunique"),
            forms=("form", "nunique"),
            auto_correctable=("auto_correctable", "sum"),
        )
        .reset_index()
        .sort_values("findings", ascending=False)
    )
    return summary


def _merge_postag_suggestions(original: object, suggestions: list[object]) -> object:
    valid_suggestions = [value for value in suggestions if isinstance(value, str)]
    if not isinstance(original, str) or not valid_suggestions:
        return valid_suggestions[-1] if valid_suggestions else original

    if len(original) == 9 and all(len(value) == 9 for value in valid_suggestions):
        merged = list(original)
        for suggestion in valid_suggestions:
            for index, char in enumerate(suggestion):
                if char != original[index]:
                    merged[index] = char
        return "".join(merged)

    return valid_suggestions[-1]


#: The rules that change the encoding and not a character of the text: they must be
#: applied last, on the result of the others.
_REGOLE_DI_CODIFICA = frozenset({"unicode-not-nfc", "corpus-not-nfc"})


def apply_suggested_corrections(
    tokens: pd.DataFrame,
    postag_findings: pd.DataFrame,
    lemma_findings: pd.DataFrame,
    enabled_rule_ids: set[str] | None = None,
    form_findings: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Apply the program's proposals: tag, lemma and form.

    The form correction covers six of the eight automatic checks: the elision apostrophe
    written with a breathing mark, the final sigma inside a word, Latin letters inside a
    Greek word, the different encodings of the apostrophe, Unicode decomposition. All of
    them propose a new form, and the correction reads that column too, so that the
    proposal shown on screen reaches the exported corpus.
    """
    corrected = tokens.copy()
    corrected["correction_log"] = ""
    corrected["lemma_corrected"] = False
    corrected["postag_corrected"] = False
    corrected["form_corrected"] = False

    if enabled_rule_ids is None:
        enabled_rule_ids = set(auto_applicable_rule_ids())

    # Build postag corrections map: key → [suggestion, ...]
    # Sort by RULE_PRIORITY so that higher-priority suggestions appear first.
    # _merge_postag_suggestions() overlays changes left-to-right, so the
    # first suggestion (highest priority) sets the dominant shape.
    if postag_findings is None:
        postag_findings = pd.DataFrame()
    if lemma_findings is None:
        lemma_findings = pd.DataFrame()

    def _utilizzabile(frame: pd.DataFrame, colonna: str) -> bool:
        """A table of proposals is useful if it has rows and the columns that are needed.

        The caller does not have to build an empty table with the right headers in order
        to say “no proposal”: an empty table says so by itself.
        """
        richieste = {"auto_correctable", "rule_id", colonna,
                     "document_id", "sentence_id", "token_id"}
        return not frame.empty and richieste.issubset(frame.columns)

    eligible_postag = postag_findings[
        postag_findings["auto_correctable"]
        & postag_findings["suggested_postag"].notna()
        & postag_findings["rule_id"].isin(enabled_rule_ids)
    ].copy() if _utilizzabile(postag_findings, "suggested_postag") else pd.DataFrame()
    if not eligible_postag.empty:
        eligible_postag["_priority"] = eligible_postag["rule_id"].map(
            lambda rid: RULE_PRIORITY.get(rid, 99)
        )
        eligible_postag = eligible_postag.sort_values("_priority")
    postag_map: dict[tuple[object, object, object], list[object]] = {}
    for finding in eligible_postag.itertuples(index=False):
        key = (finding.document_id, finding.sentence_id, finding.token_id)
        postag_map.setdefault(key, []).append(finding.suggested_postag)

    # Build lemma corrections map: key → suggested_lemma
    lemma_map: dict[tuple[object, object, object], object] = {}
    if _utilizzabile(lemma_findings, "suggested_lemma"):
        lemma_map = (
            lemma_findings[
                lemma_findings["auto_correctable"]
                & lemma_findings["suggested_lemma"].notna()
                & lemma_findings["rule_id"].isin(enabled_rule_ids)
            ]
            .drop_duplicates(subset=["document_id", "sentence_id", "token_id"], keep="last")
            .set_index(["document_id", "sentence_id", "token_id"])["suggested_lemma"]
            .to_dict()
        )

    # Build form corrections map: key → suggested_form
    if form_findings is None:
        form_findings = pd.DataFrame()
    form_map: dict[tuple[object, object, object], object] = {}
    ricomporre = False
    if _utilizzabile(form_findings, "suggested_form"):
        ammesse = form_findings[
            form_findings["auto_correctable"]
            & form_findings["suggested_form"].notna()
            & form_findings["rule_id"].isin(enabled_rule_ids)
        ].copy()
        # Two rules may propose a form for the same token: δεξιώματ’ has the apostrophe
        # to be made uniform *and* the encoding to be composed. Keeping the last row to
        # arrive would make the result depend on the order in which the families had
        # run, which is not a criterion. The character rules win over the encoding rule,
        # and the encoding is settled afterwards, in a single pass over the result: so
        # the two compose instead of excluding each other.
        ammesse["_priorita"] = ammesse["rule_id"].map(
            lambda rid: 90 if rid in _REGOLE_DI_CODIFICA else RULE_PRIORITY.get(rid, 50))
        ammesse = ammesse.sort_values(["_priorita", "rule_id"], kind="stable")
        form_map = (ammesse
                    .drop_duplicates(subset=["document_id", "sentence_id", "token_id"],
                                     keep="first")
                    .set_index(["document_id", "sentence_id", "token_id"])["suggested_form"]
                    .to_dict())
        ricomporre = bool(set(ammesse["rule_id"]) & _REGOLE_DI_CODIFICA)

    if not postag_map and not lemma_map and not form_map:
        return corrected

    # Vectorized lookup via tuple key column.
    #
    # The three columns are converted with ``tolist`` before being zipped:
    # iterating an Arrow-backed column yields one freshly boxed object per row,
    # and three of those over 625,176 rows would be most of the cost. The tuples
    # themselves are the same, and so are the dictionary lookups.
    key_tuples = list(zip(corrected["document_id"].tolist(),
                          corrected["sentence_id"].tolist(),
                          corrected["token_id"].tolist()))
    keys = pd.Series(key_tuples, index=corrected.index)

    # ── Postag corrections ──
    postag_mask = pd.Series(
        np.fromiter((key in postag_map for key in key_tuples), bool, len(key_tuples)),
        index=corrected.index)
    if postag_mask.any():
        corrected.loc[postag_mask, "postag"] = corrected.loc[postag_mask].apply(
            lambda row: _merge_postag_suggestions(
                row["postag"],
                postag_map[(row["document_id"], row["sentence_id"], row["token_id"])],
            ),
            axis=1,
        )
        corrected.loc[postag_mask, "postag_corrected"] = True
        corrected.loc[postag_mask, "correction_log"] = corrected.loc[postag_mask, "postag"].map(
            lambda p: f"postag->{p}"
        )

    # ── Lemma corrections ──
    lemma_mask = pd.Series(
        np.fromiter((key in lemma_map for key in key_tuples), bool, len(key_tuples)),
        index=corrected.index)
    if lemma_mask.any():
        corrected.loc[lemma_mask, "lemma"] = keys[lemma_mask].map(lemma_map)
        corrected.loc[lemma_mask, "lemma_corrected"] = True
        both_mask = postag_mask & lemma_mask
        corrected.loc[lemma_mask & ~postag_mask, "correction_log"] = (
            corrected.loc[lemma_mask & ~postag_mask, "lemma"].map(lambda l: f"lemma->{l}")
        )
        if both_mask.any():
            corrected.loc[both_mask, "correction_log"] = corrected.loc[both_mask].apply(
                lambda row: f"postag->{row['postag']}; lemma->{row['lemma']}", axis=1
            )

    # ── Form corrections ───
    #
    # The form is corrected last, and without touching the lemma: the rules that propose
    # a form change the spelling of a word, not the word.
    form_mask = pd.Series(
        np.fromiter((key in form_map for key in key_tuples), bool, len(key_tuples)),
        index=corrected.index)
    if form_mask.any():
        corrected.loc[form_mask, "form"] = keys[form_mask].map(form_map)
        corrected.loc[form_mask, "form_corrected"] = True
        coda = corrected.loc[form_mask, "form"].map(lambda f: f"form->{f}")
        precedente = corrected.loc[form_mask, "correction_log"].fillna("")
        corrected.loc[form_mask, "correction_log"] = [
            f"{p}; {c}" if p else c for p, c in zip(precedente, coda)]

    # The encoding is settled last, on the records just corrected: a form whose
    # apostrophe has been made uniform must be composed too, and the composition
    # proposal, computed on the original form, could not know it. The pass stays within
    # the tokens touched: converting the whole corpus is the action of a different
    # check, and must not start as a side effect of this one.
    if ricomporre and form_mask.any():
        corrected.loc[form_mask, "form"] = corrected.loc[form_mask, "form"].map(
            lambda v: unicodedata.normalize("NFC", v) if isinstance(v, str) else v)

    return corrected


def apply_manual_corrections(tokens: pd.DataFrame, corrections: pd.DataFrame) -> pd.DataFrame:
    corrected = tokens.copy()
    if corrections.empty:
        return corrected

    required = {"document_id", "sentence_id", "token_id"}
    if not required.issubset(corrections.columns):
        raise ValueError(
            "Manual corrections must include document_id, sentence_id, and token_id columns. "
            "Optional columns are corrected_lemma and corrected_postag."
        )

    # Deduplicate keeping last correction per token
    deduped = corrections.drop_duplicates(
        subset=["document_id", "sentence_id", "token_id"], keep="last"
    )

    # The three key columns must be compared as text on both sides. The
    # corrections file is written and read back as CSV — every value comes back
    # a string — while the corpus keeps token_id as a whole number. Merging the
    # two directly raises "You are trying to merge on int64 and str columns",
    # which meant that a user who had saved corrections and pressed «Apply» got
    # an error instead of a corrected corpus. Casting both sides here, once,
    # costs a copy of three columns and removes the whole class of failure.
    KEYS = ["document_id", "sentence_id", "token_id"]
    corrected["_key_join"] = _join_key(corrected, KEYS)
    deduped = deduped.copy()
    deduped["_key_join"] = _join_key(deduped, KEYS)

    def _blank(series: pd.Series) -> pd.Series:
        """True where a correction carries no value: NaN, empty, whitespace."""
        text = series.astype("string").fillna("")
        return text.str.strip().eq("")

    for column, target in (("corrected_lemma", "lemma"),
                           ("corrected_postag", "postag"),
                           ("corrected_relation", "relation")):
        if column not in deduped.columns or target not in corrected.columns:
            continue
        changes = deduped.loc[~_blank(deduped[column]), ["_key_join", column]]
        if changes.empty:
            continue
        corrected = corrected.merge(changes, on="_key_join", how="left")
        mask = ~_blank(corrected[column])
        corrected.loc[mask, target] = corrected.loc[mask, column]
        corrected = corrected.drop(columns=[column])

    return corrected.drop(columns=["_key_join"])


def _join_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """One text key out of several columns, immune to int/str mismatches.

    ``token_id`` arrives as 5 from the corpus and as "5" from the corrections
    file, and 5.0 from a CSV that pandas decided was float. All three have to
    land on the same key.
    """
    pieces = []
    for column in columns:
        values = frame[column]
        if pd.api.types.is_float_dtype(values):
            text = values.map(
                lambda value: "" if pd.isna(value)
                else (str(int(value)) if float(value).is_integer() else str(value)))
        else:
            text = values.astype("string").fillna("")
        pieces.append(text.astype(str).str.strip())
    return pd.Series(["\x00".join(row) for row in zip(*pieces)], index=frame.index)


def compare_annotation_sets(reference: pd.DataFrame, candidate: pd.DataFrame, label: str) -> tuple[pd.DataFrame, dict[str, int]]:
    import warnings
    key_columns = ["source_file", "document_id", "sentence_index", "sentence_id", "token_index", "token_id", "form"]
    merged = reference[key_columns + ["lemma", "postag", "corpus"]].merge(
        candidate[key_columns + ["lemma", "postag"]],
        on=key_columns,
        suffixes=("_reference", f"_{label}"),
        how="inner",
    )
    dropped = len(reference) - len(merged)
    if dropped > 0:
        warnings.warn(
            f"compare_annotation_sets: {dropped} token(s) could not be aligned with {label} "
            f"(inner join dropped {dropped}/{len(reference)} reference rows). "
            "This is usually caused by tokenization differences between the corpus and the model."
        )
    merged["lemma_match"] = merged["lemma_reference"] == merged[f"lemma_{label}"]
    merged["postag_match"] = merged["postag_reference"] == merged[f"postag_{label}"]

    summary = {
        "aligned_tokens": int(len(merged)),
        "reference_tokens": int(len(reference)),
        "unaligned_tokens": int(dropped),
        "lemma_matches": int(merged["lemma_match"].sum()),
        "lemma_mismatches": int((~merged["lemma_match"]).sum()),
        "postag_matches": int(merged["postag_match"].sum()),
        "postag_mismatches": int((~merged["postag_match"]).sum()),
        "lemma_match_rate": round(float(merged["lemma_match"].mean()) * 100, 2) if len(merged) else 0.0,
        "postag_match_rate": round(float(merged["postag_match"].mean()) * 100, 2) if len(merged) else 0.0,
    }
    return merged, summary


def summarize_comparison_by_group(comparison: pd.DataFrame, group_column: str, label: str) -> pd.DataFrame:
    comparison = add_corpus_labels(comparison)
    if comparison.empty or group_column not in comparison.columns:
        return pd.DataFrame()

    summary = (
        comparison.groupby(group_column, dropna=False)
        .agg(
            aligned_tokens=("form", "size"),
            lemma_mismatches=("lemma_match", lambda values: int((~values).sum())),
            postag_mismatches=("postag_match", lambda values: int((~values).sum())),
        )
        .reset_index()
    )
    summary[f"{label}_lemma_mismatch_rate"] = (
        (summary["lemma_mismatches"] / summary["aligned_tokens"]) * 100
    ).round(2)
    summary[f"{label}_postag_mismatch_rate"] = (
        (summary["postag_mismatches"] / summary["aligned_tokens"]) * 100
    ).round(2)
    return summary.sort_values("aligned_tokens", ascending=False)


def build_sentence_context(tokens: pd.DataFrame) -> pd.DataFrame:
    if tokens.empty:
        return pd.DataFrame(
            columns=["source_file", "document_id", "sentence_index", "sentence_id", "sentence_text"]
        )

    # The error page shows the Greek sentence next to every finding, so the user
    # waits for this on every click. Visiting the 26,616 sentence groups one at a
    # time would spend almost all of it in pandas building a Series per group
    # before any text is joined; stripping the forms once per distinct spelling
    # and joining the sorted runs does the same far faster.
    key_columns = ["source_file", "document_id", "sentence_index", "sentence_id"]
    ordered = tokens.sort_values(["source_file", "sentence_index", "token_index"])
    grouped = ordered.groupby(key_columns, sort=True)
    index = grouped.size().index
    codes = grouped.ngroup().to_numpy()

    spellings = map_unique(ordered["form"].fillna(""),
                           lambda value: str(value).strip()).to_numpy()
    spoken = spellings != ""
    joined = grouped_join(pd.Series(spellings[spoken]), pd.Series(codes[spoken]), " ")

    frame = pd.DataFrame(
        {name: index.get_level_values(position).to_numpy()
         for position, name in enumerate(key_columns)})
    # A sentence whose forms are all blank keeps the empty string the loop gave it.
    frame["sentence_text"] = joined.reindex(range(len(index))).fillna("").to_numpy()
    return frame


def attach_sentence_context(frame: pd.DataFrame, tokens: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    sentence_context = build_sentence_context(tokens)
    enriched = frame.copy()
    missing_location_columns = [column for column in ["source_file", "sentence_index", "token_index"] if column not in enriched.columns]
    if missing_location_columns:
        token_columns = ["document_id", "sentence_id", "token_id", "source_file", "sentence_index", "token_index", "form"]
        token_lookup = tokens[token_columns].drop_duplicates(subset=["document_id", "sentence_id", "token_id"])
        enriched = enriched.merge(
            token_lookup,
            on=["document_id", "sentence_id", "token_id"],
            how="left",
            suffixes=("", "_token"),
        )
        for column in ["source_file", "sentence_index", "token_index", "form"]:
            token_column = f"{column}_token"
            if token_column in enriched.columns:
                if column not in enriched.columns:
                    enriched[column] = enriched[token_column]
                else:
                    enriched[column] = enriched[column].fillna(enriched[token_column])
                enriched = enriched.drop(columns=[token_column])

    return enriched.merge(
        sentence_context,
        on=["source_file", "document_id", "sentence_index", "sentence_id"],
        how="left",
    )


def summarize_annotation_inventory(tokens: pd.DataFrame) -> dict[str, object]:
    if tokens.empty:
        return {
            "unique_forms": 0,
            "unique_lemmas": 0,
            "unique_postags": 0,
            "average_lemmas_per_form": 0.0,
            "average_postags_per_form": 0.0,
            "max_lemmas_for_one_form": 0,
            "max_postags_for_one_form": 0,
        }

    grouped = tokens.groupby("form", dropna=False)
    lemmas_per_form = grouped["lemma"].nunique(dropna=True)
    postags_per_form = grouped["postag"].nunique(dropna=True)
    return {
        "unique_forms": int(tokens["form"].dropna().nunique()),
        "unique_lemmas": int(tokens["lemma"].dropna().nunique()),
        "unique_postags": int(tokens["postag"].dropna().nunique()),
        "average_lemmas_per_form": round(float(lemmas_per_form.mean()), 3) if len(lemmas_per_form) else 0.0,
        "average_postags_per_form": round(float(postags_per_form.mean()), 3) if len(postags_per_form) else 0.0,
        "max_lemmas_for_one_form": int(lemmas_per_form.max()) if len(lemmas_per_form) else 0,
        "max_postags_for_one_form": int(postags_per_form.max()) if len(postags_per_form) else 0,
    }


def build_unified_lemma_dictionary(tokens: pd.DataFrame) -> pd.DataFrame:
    if tokens.empty:
        return pd.DataFrame(
            columns=[
                "normalized_lemma",
                "occurrences",
                "corpora_count",
                "corpora",
                "author_count",
                "authors",
                "work_count",
                "works",
                "document_count",
                "form_count",
                "forms",
                "raw_lemma_count",
                "raw_lemmas",
                "postags",
            ]
        )

    working = add_corpus_labels(tokens)
    working = working[working["lemma"].notna() & working["form"].notna()].copy()
    if working.empty:
        return pd.DataFrame(
            columns=[
                "normalized_lemma",
                "occurrences",
                "corpora_count",
                "corpora",
                "author_count",
                "authors",
                "work_count",
                "works",
                "document_count",
                "form_count",
                "forms",
                "raw_lemma_count",
                "raw_lemmas",
                "postags",
            ]
        )

    if "corpus" not in working.columns:
        working["corpus"] = "Unknown"

    # The regular expression for the trailing digit is asked once per distinct
    # lemma rather than once per token: the distinct values are a small fraction
    # of the occurrences, and the answer is the same for all of them.
    working["normalized_lemma"] = map_unique(working["lemma"], normalize_lemma)

    # Aggregate with vectorized group operations rather than a per-group Python
    # loop.
    grouped = working.groupby("normalized_lemma", sort=True, dropna=False)
    result = pd.DataFrame({"occurrences": grouped.size()})
    result["document_count"] = grouped["document_id"].nunique()

    def _unique_joined(column: str) -> tuple[pd.Series, pd.Series]:
        """(count, ' | '-joined sorted unique values) per normalized lemma."""
        sub = working.loc[working[column].notna(), ["normalized_lemma", column]].copy()
        sub[column] = sub[column].astype(str)
        sub = sub[sub[column] != ""]
        if sub.empty:
            zero  = pd.Series(0,  index=result.index, dtype=int)
            blank = pd.Series("", index=result.index, dtype=object)
            return zero, blank
        sub = sub.drop_duplicates()
        sub = sub.sort_values(["normalized_lemma", column], kind="stable")
        by_lemma = sub.groupby("normalized_lemma", sort=True, dropna=False)[column]
        counts = by_lemma.size().reindex(result.index, fill_value=0).astype(int)
        # Six of these, each over as many groups as there are distinct lemmas:
        # ``agg`` with a Python callable makes pandas build a Series per group,
        # and that slicing dominated the cost of the whole function.
        joined = (grouped_join(sub[column], sub["normalized_lemma"], " | ")
                  .reindex(result.index).fillna("").astype(object))
        return counts, joined

    for column, count_name, join_name in (
        ("corpus", "corpora_count",    "corpora"),
        ("author", "author_count",     "authors"),
        ("work",   "work_count",       "works"),
        ("form",   "form_count",       "forms"),
        ("lemma",  "raw_lemma_count",  "raw_lemmas"),
        ("postag", None,               "postags"),
    ):
        counts, joined = _unique_joined(column)
        if count_name:
            result[count_name] = counts
        result[join_name] = joined

    result = result.reset_index()
    ordered = [
        "normalized_lemma", "occurrences",
        "corpora_count", "corpora",
        "author_count", "authors",
        "work_count", "works",
        "document_count",
        "form_count", "forms",
        "raw_lemma_count", "raw_lemmas",
        "postags",
    ]
    result["occurrences"] = result["occurrences"].astype(int)
    result["document_count"] = result["document_count"].astype(int)
    return (result[ordered]
            .sort_values("occurrences", ascending=False, kind="stable")
            .reset_index(drop=True))



def compute_token_diff(
    original: pd.DataFrame,
    corrected: pd.DataFrame,
) -> pd.DataFrame:
    """Return rows where lemma or postag changed between original and corrected tokens.

    Matches rows by (document_id, sentence_id, token_id) and produces a flat
    DataFrame with both the original and corrected values side by side.
    """
    key_cols = ["document_id", "sentence_id", "token_id"]
    left_cols = key_cols + ["form", "lemma", "postag"]
    right_cols = key_cols + ["form", "lemma", "postag"]

    left = original[[c for c in left_cols if c in original.columns]].copy()
    right = corrected[[c for c in right_cols if c in corrected.columns]].copy()

    merged = left.merge(right, on=key_cols, suffixes=("_original", "_corrected"), how="inner")

    # Two empty cells are not a change. Compared as they were, NaN != NaN would report
    # “changed” for every record without a lemma, and the before-and-after comparison
    # would contain rows in which nothing had changed.
    def _cambiata(nome: str) -> pd.Series:
        prima = merged.get(f"{nome}_original", pd.Series(dtype=object))
        dopo = merged.get(f"{nome}_corrected", pd.Series(dtype=object))
        if prima.empty or dopo.empty:
            return pd.Series(False, index=merged.index)
        return prima.fillna("") != dopo.fillna("")

    lemma_changed = _cambiata("lemma")
    postag_changed = _cambiata("postag")
    form_changed = _cambiata("form")
    changed = merged[lemma_changed | postag_changed | form_changed].copy()
    return changed.reset_index(drop=True)


def normalise_corpus_to_nfc(tokens: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Bring the whole corpus to Unicode normal form NFC.

    This is the action of the check “Corpus predominantly in NFD”, and it is not a
    token-by-token correction: either everything is converted or nothing is. A resource
    published in NFD is not wrong, but two tokens that look identical on screen are not
    equal under any comparison that does not normalise first, and every closed list of
    forms or lemmas, including those of this program, stays blind as long as the text is
    decomposed.

    The conversion changes the encoding and not a letter of the text. It returns the
    converted table and the number of records it touched.
    """
    if tokens is None or tokens.empty:
        return tokens, 0
    convertito = tokens.copy()
    toccati = pd.Series(False, index=convertito.index)
    for colonna in ("form", "lemma"):
        if colonna not in convertito.columns:
            continue
        originale = convertito[colonna]
        nuovo = originale.map(
            lambda v: unicodedata.normalize("NFC", v) if isinstance(v, str) else v)
        toccati |= (originale != nuovo) & originale.notna()
        convertito[colonna] = nuovo
    numero = int(toccati.sum())
    if numero:
        if "form_corrected" not in convertito.columns:
            convertito["form_corrected"] = False
        convertito.loc[toccati, "form_corrected"] = True
        if "correction_log" not in convertito.columns:
            convertito["correction_log"] = ""
        precedente = convertito.loc[toccati, "correction_log"].fillna("")
        convertito.loc[toccati, "correction_log"] = [
            f"{p}; nfc" if p else "nfc" for p in precedente]
    return convertito, numero


def apply_form_corrections(
    tokens: pd.DataFrame,
    form_corrections: pd.DataFrame,
) -> pd.DataFrame:
    """Apply a form-level lexicon — lemma, tag, or both — to the token table.

    *form_corrections* is the user's own dictionary, and it is read here exactly
    as :mod:`greek_corpus_pipeline.corrections` declares it, which is also what
    the interface prints on the screen next to the field:

      - ``form``   — required: the surface form as it appears in the corpus;
      - ``postag`` — optional: the morphological tag to assign;
      - ``lemma``  — optional: the lemma to assign;
      - at least one of ``postag`` and ``lemma`` must be there.

    A two-column ``form,lemma`` file is the special case in which ``postag`` is
    absent, and it is accepted as it is. Empty
    cells assign nothing, entries that match no form in the corpus do nothing,
    and ``lemma_corrected`` / ``postag_corrected`` mark what actually moved.

    This is applied AFTER automatic rule corrections and BEFORE token-level manual
    corrections, so that token-level overrides always take final precedence.
    """
    from .corrections import apply_form_dictionary, normalise_form_dictionary

    if form_corrections is None or form_corrections.empty:
        return tokens.copy()
    entries, _report = normalise_form_dictionary(form_corrections)
    return apply_form_dictionary(tokens, entries)


def run_pipeline(
    tokens: pd.DataFrame,
    manual_corrections: pd.DataFrame | None = None,
    form_corrections: pd.DataFrame | None = None,
    enabled_auto_rules: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run the full annotation analysis pipeline on an already-loaded token table.

    Correction order (each layer can override the previous):
    1. Automatic rule-based corrections (postag + lemma analysis findings)
    2. Form-level lemma corrections  (form → lemma lexicon, applies to all occurrences)
    3. Token-level manual corrections (document_id + sentence_id + token_id, most specific)

    Returns a dict with keys: tokens, postag_findings, lemma_findings,
    corrected_tokens, lemma_inventory.
    """
    if manual_corrections is None:
        manual_corrections = pd.DataFrame()
    if form_corrections is None:
        form_corrections = pd.DataFrame()

    postag_findings = analyze_postags(tokens)
    lemma_findings = analyze_lemmas(tokens)
    corrected_tokens = apply_suggested_corrections(
        tokens,
        postag_findings,
        lemma_findings,
        enabled_rule_ids=enabled_auto_rules,
    )
    if not form_corrections.empty:
        corrected_tokens = apply_form_corrections(corrected_tokens, form_corrections)
    if not manual_corrections.empty:
        corrected_tokens = apply_manual_corrections(corrected_tokens, manual_corrections)
    lemma_inventory = build_lemma_inventory(corrected_tokens)

    return {
        "tokens": tokens,
        "postag_findings": postag_findings,
        "lemma_findings": lemma_findings,
        "corrected_tokens": corrected_tokens,
        "lemma_inventory": lemma_inventory,
    }



#: From which column of the alignment the label of each source comes.
#: ``build_confusion_matrix`` depends on it; the interface uses
#: ``modelcmp.slot_confusion``, and this function is called only by the library.
CONFUSION_SOURCES = {
    "corpus": "postag_reference",
    "reference": "postag_reference",
    "stanza": "postag_stanza",
    "udpipe": "postag_udpipe",
}


def build_confusion_matrix(
    per_token: pd.DataFrame,
    position: int,
    source: str = "stanza",
) -> pd.DataFrame:
    """Confusion matrix for one AGDT postag position (1–9).

    Rows are the gold character for that position, columns the character
    predicted by *source* (``corpus`` / ``corrected`` / ``stanza`` / ``udpipe``),
    values are token counts.  A ``TOT`` row and column give the margins.

    Tokens whose gold character is missing or ``-`` (feature not applicable for
    that part of speech) are excluded.  Returns an empty DataFrame when the
    requested source or the gold column is unavailable.
    """
    if per_token is None or per_token.empty:
        return pd.DataFrame()
    if not isinstance(position, int) or not 1 <= position <= 9:
        return pd.DataFrame()

    postag_col = CONFUSION_SOURCES.get(source)
    if postag_col is None:
        return pd.DataFrame()
    if postag_col not in per_token.columns or "postag_gold" not in per_token.columns:
        return pd.DataFrame()

    idx = position - 1
    gold_char = (per_token["postag_gold"].astype("string")
                 .str.split("|").str[0].str[idx:idx + 1])
    pred_char = per_token[postag_col].astype("string").str[idx:idx + 1]

    mask = gold_char.notna() & (gold_char != "") & (gold_char != "-")
    gold_char = gold_char[mask]
    pred_char = pred_char[mask].fillna("∅").replace("", "∅")

    if gold_char.empty:
        return pd.DataFrame()

    matrix = pd.crosstab(
        gold_char.rename("gold \\ predetto"),
        pred_char.rename(""),
        margins=True,
        margins_name="TOT",
    )
    return matrix.reset_index()


# ---------------------------------------------------------------------------
# 3-way comparison: does the model replicate the noise or converge on the fix?
# ---------------------------------------------------------------------------

_THREEWAY_CATEGORIES = [
    ("Agrees with the original", True,  False),
    ("Agrees with the corrected", False, True),
    ("Neither",                  False, False),
]


def build_threeway_table(
    tokens: pd.DataFrame,
    corrected: pd.DataFrame,
    stanza_cmp: "pd.DataFrame | None" = None,
    udpipe_cmp: "pd.DataFrame | None" = None,
) -> "tuple[pd.DataFrame, pd.DataFrame]":
    """Classify each model's output on the tokens the pipeline changed.

    Restricted to tokens where ``original postag != corrected postag`` (i.e.
    where an automatic rule actually fired), each model output falls into one
    of three classes:

    * *Agrees with the original* — the model reproduces the corpus annotation,
      i.e. it replicates the same noise the pipeline set out to remove;
    * *Agrees with the corrected* — the model independently converges on the
      pipeline's correction;
    * *Neither*                 — the model proposes a third value.

    This analysis treats **neither model as a gold standard**: it records what
    the model says about a record the pipeline changed, and nothing that follows
    licenses reading the model's answer as the correct one.  Pass the *full*
    (unfiltered) comparison frames: restricting them to corpus/model mismatches
    would systematically delete the "Agrees with the original" class.

    Returns ``(stanza_table, udpipe_table)``, each with columns
    ``Outcome | N | %``.  Empty DataFrames are returned when the inputs are
    insufficient.
    """
    empty = (pd.DataFrame(), pd.DataFrame())
    if (corrected is None or corrected.empty
            or tokens is None or tokens.empty
            or "postag" not in tokens.columns or "postag" not in corrected.columns):
        return empty

    id_cols = [c for c in ("document_id", "sentence_id", "token_id")
               if c in tokens.columns and c in corrected.columns]
    if not id_cols:
        return empty

    base_cols = id_cols + (["form"] if "form" in tokens.columns else []) + ["postag"]
    base = tokens[base_cols].rename(columns={"postag": "postag_orig"})
    corr = corrected[id_cols + ["postag"]].rename(columns={"postag": "postag_corr"})
    merged = base.merge(corr, on=id_cols, how="inner")

    # Only tokens the pipeline actually rewrote
    changed = merged[
        merged["postag_orig"].astype("string").fillna("")
        != merged["postag_corr"].astype("string").fillna("")
    ].copy()
    if changed.empty:
        return empty

    def _model_column(cmp_df: "pd.DataFrame | None", *candidates: str) -> "str | None":
        if cmp_df is None or cmp_df.empty:
            return None
        return next((c for c in candidates if c in cmp_df.columns), None)

    def _table(cmp_df: "pd.DataFrame | None", postag_cmp_col: "str | None") -> pd.DataFrame:
        if cmp_df is None or cmp_df.empty or not postag_cmp_col:
            return pd.DataFrame()
        if not all(c in cmp_df.columns for c in id_cols):
            return pd.DataFrame()
        model = (cmp_df[id_cols + [postag_cmp_col]]
                 .rename(columns={postag_cmp_col: "postag_model"}))
        m = changed.merge(model, on=id_cols, how="inner")
        m = m[m["postag_model"].notna()]
        if m.empty:
            return pd.DataFrame()

        model_s = m["postag_model"].astype("string")
        is_orig = model_s == m["postag_orig"].astype("string")
        is_corr = model_s == m["postag_corr"].astype("string")
        total = len(m)
        rows = [{
            "Outcome": label,
            "N": int(((is_orig == want_orig) & (is_corr == want_corr)).sum()),
            "%": 0.0,
        } for label, want_orig, want_corr in _THREEWAY_CATEGORIES]
        for row in rows:
            row["%"] = round(row["N"] / total * 100, 1) if total else 0.0
        rows.append({"Outcome": "TOTAL modified tokens", "N": total, "%": 100.0})
        return pd.DataFrame(rows)

    return (
        _table(stanza_cmp, _model_column(stanza_cmp, "postag_stanza", "postag")),
        _table(udpipe_cmp, _model_column(udpipe_cmp, "postag_udpipe", "postag")),
    )


# ---------------------------------------------------------------------------
# Stanza vs UDPipe divergences (neither model as a reference)
# ---------------------------------------------------------------------------

def find_model_divergences(
    stanza_cmp: pd.DataFrame,
    udpipe_cmp: pd.DataFrame,
) -> pd.DataFrame:
    """Tokens where Stanza and UDPipe disagree with each other.

    Independent of the corpus annotation: the comparison is Stanza output vs
    UDPipe output.  Pass the *full* comparison frames — frames pre-filtered to
    corpus mismatches drop every token where one model agrees with the corpus
    and the other does not, which is precisely the most interesting case.

    Returns a DataFrame with the shared id columns plus
    ``postag_stanza`` / ``postag_udpipe`` (and the lemma pair when available),
    with a ``divergenza`` column flagging what differs.
    """
    if (stanza_cmp is None or udpipe_cmp is None
            or stanza_cmp.empty or udpipe_cmp.empty):
        return pd.DataFrame()

    id_cols = [c for c in ("document_id", "sentence_id", "token_id", "form")
               if c in stanza_cmp.columns and c in udpipe_cmp.columns]
    if not id_cols:
        return pd.DataFrame()

    def _pick(df: pd.DataFrame, *candidates: str) -> "str | None":
        return next((c for c in candidates if c in df.columns), None)

    s_postag = _pick(stanza_cmp, "postag_stanza", "postag")
    u_postag = _pick(udpipe_cmp, "postag_udpipe", "postag")
    if not s_postag or not u_postag:
        return pd.DataFrame()
    s_lemma = _pick(stanza_cmp, "lemma_stanza", "lemma")
    u_lemma = _pick(udpipe_cmp, "lemma_udpipe", "lemma")

    # Select only the columns we need before merging: avoids suffix collisions
    # between the two comparison frames (both carry lemma_reference etc.).
    left_cols  = id_cols + [s_postag] + ([s_lemma] if s_lemma else [])
    right_cols = id_cols + [u_postag] + ([u_lemma] if u_lemma else [])
    left  = stanza_cmp[left_cols].rename(
        columns={s_postag: "postag_stanza", **({s_lemma: "lemma_stanza"} if s_lemma else {})})
    right = udpipe_cmp[right_cols].rename(
        columns={u_postag: "postag_udpipe", **({u_lemma: "lemma_udpipe"} if u_lemma else {})})

    merged = left.merge(right, on=id_cols, how="inner")
    if merged.empty:
        return pd.DataFrame()

    postag_diff = (merged["postag_stanza"].astype("string").fillna("")
                   != merged["postag_udpipe"].astype("string").fillna(""))
    if s_lemma and u_lemma:
        lemma_diff = (merged["lemma_stanza"].astype("string").fillna("")
                      != merged["lemma_udpipe"].astype("string").fillna(""))
    else:
        lemma_diff = pd.Series(False, index=merged.index)

    div = merged[postag_diff | lemma_diff].copy()
    if div.empty:
        return pd.DataFrame()

    div["divergenza"] = [
        "postag + lemma" if p and l else "postag" if p else "lemma"
        for p, l in zip(postag_diff[postag_diff | lemma_diff],
                        lemma_diff[postag_diff | lemma_diff])
    ]

    ordered = (id_cols + ["divergenza", "postag_stanza", "postag_udpipe"]
               + (["lemma_stanza", "lemma_udpipe"] if s_lemma and u_lemma else []))
    return div[ordered].reset_index(drop=True)
