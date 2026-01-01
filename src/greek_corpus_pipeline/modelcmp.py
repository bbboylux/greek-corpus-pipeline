"""Comparing annotations — corpus against models, and models against each other.

The important design decision here is that **the comparison does not treat
either automatic model as a gold standard**. Neither Stanza nor UDPipe is a
validated reference: both are trained systems whose output is one more opinion
about the text, and the comparison is arranged so that no figure on this page
can be read as a model correcting the corpus. What it buys is that a user who
has just loaded a treebank can run the two models on it and learn something
straight away, without first spending three weeks building a reference
dictionary.

What can be learned this way turns out to be a great deal:

*Where two independent models disagree with each other* is the best unsupervised
predictor of a hard or wrongly annotated record there is. When Stanza and UDPipe
both diverge from the corpus and agree with each other on what it should be,
that is **a stronger review signal** than either model alone — stronger, not
conclusive: two systems trained on overlapping data can be wrong together, and
Ancient Greek is exactly the setting where they are. When they disagree with
each other, the record is genuinely hard.

*Whether a model reproduces the corpus's own noise* answers the question that
motivates the whole enterprise. Take the records an automatic rule changed, and
ask what the model says about them: if it echoes the original annotation, it has
learned the noise; if it converges on the correction, the correction was right
and the model confirms it independently.

*A per-slot agreement matrix* localises the disagreement. Two annotations that
match 82 % of the time can be matching almost perfectly on part of speech and
falling apart on case, and the average hides exactly the thing worth knowing.

Everything below therefore works on the comparison frames produced by
``compare_annotation_sets``, needing nothing else.
"""
from __future__ import annotations

import pandas as pd

from .agdt_schema import POSITION_NAMES, TAG_LENGTH, describe_value

KEY_COLUMNS = ["document_id", "sentence_id", "token_id"]

#: The two columns of a comparison table, per source. The corpus sits under the
#: bare name of the field, the model under the same name with the suffix
#: ``_modello``: this is the schema that ``model_eval.evaluate_predictions`` writes.
SOURCE_COLUMNS: dict[str, tuple[str, str]] = {
    "corpus": ("lemma", "postag"),
    "modello": ("lemma_modello", "postag_modello"),
}

SOURCE_LABELS = {
    "corpus": "Corpus", "corrected": "Corpus corretto",
    "stanza": "Stanza", "udpipe": "UDPipe",
}


def _pick(frame: pd.DataFrame, *candidates: str) -> str | None:
    if frame is None or frame.empty:
        return None
    return next((name for name in candidates if name in frame.columns), None)


# ---------------------------------------------------------------------------
# What the columns of a comparison table are really called
# ---------------------------------------------------------------------------
#
# The table that ``model_eval.evaluate_predictions`` saves carries the value of
# the corpus under the bare name of the field — ``lemma``, ``postag`` — and the
# prediction of the model under the same name with the suffix ``_modello``. The
# names ``postag_reference``, ``postag_stanza`` and ``postag_udpipe`` are not
# used: they never occur in a file produced by the program.
#
# A wrong name would not raise a visible error: ``_pick`` would fall back on the
# bare name and the three columns — corpus, Stanza, UDPipe — would become the
# same one. The three-way comparison would die with ``KeyError: 'corpus'``
# because the rename would collapse two columns of the same name into one; and
# ``divergence_hotspots``, which does not die, would compare the ``postag``
# column of Stanza with the ``postag`` column of UDPipe — that is, the corpus
# with itself — and would never find a divergence.
#
# The two names are kept here, once only.

def _colonna_corpus(frame: pd.DataFrame, campo: str) -> str | None:
    """The column that carries the value **of the corpus** for *field*."""
    return _pick(frame, campo, f"{campo}_reference")


def _colonna_modello(frame: pd.DataFrame, campo: str) -> str | None:
    """The column that carries the prediction **of the model** for *field*."""
    return _pick(frame, f"{campo}_modello", f"{campo}_stanza", f"{campo}_udpipe")


def _colonna_accordo(frame: pd.DataFrame, campo: str) -> str | None:
    """The boolean column “corpus and model say the same thing” for *field*.

    As for the other two: the real name is the one that
    ``model_eval.evaluate_predictions`` writes, and the search starts from there.
    Asking for the wrong name raises nothing — it returns ``None`` — and a view
    that does not notice shows an empty table without saying why.
    """
    return _pick(frame, f"accordo_{campo}", f"{campo}_match")


def _slot_series(values: pd.Series, index: int) -> pd.Series:
    text = values.astype("string").fillna("")
    usable = text.str.len() == TAG_LENGTH
    return text.str[index].where(usable, "")


# ---------------------------------------------------------------------------
# 1. Two annotations, slot by slot
# ---------------------------------------------------------------------------

def per_slot_agreement(
    left: pd.Series,
    right: pd.Series,
    *,
    left_label: str = "A",
    right_label: str = "B",
) -> pd.DataFrame:
    """Agreement on each of the nine tag positions, separately.

    Reported over the tokens where *both* sides mark the feature, because
    counting "both wrote a dash" as agreement inflates every figure: the person
    slot is a dash on eighty per cent of tokens, and an accuracy that includes
    those dashes says nothing about persons.
    """
    if left is None or right is None or len(left) == 0:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for index, (name_it, _name_en) in POSITION_NAMES.items():
        a = _slot_series(left, index)
        b = _slot_series(right, index)
        relevant = ((a != "") & (b != "")) & ((a != "-") | (b != "-"))
        total = int(relevant.sum())
        matches = int((a[relevant] == b[relevant]).sum())
        rows.append({
            "posizione": index + 1,
            "tratto": name_it,
            "token confrontati": total,
            "accordo": matches,
            "% accordo": round(matches / total * 100, 2) if total else None,
        })
    frame = pd.DataFrame(rows)
    frame.attrs["left"] = left_label
    frame.attrs["right"] = right_label
    return frame


def slot_confusion(
    left: pd.Series,
    right: pd.Series,
    index: int,
    *,
    readable: bool = True,
) -> pd.DataFrame:
    """Confusion matrix for one tag position between two annotation sources."""
    if left is None or right is None or len(left) == 0:
        return pd.DataFrame()
    a = _slot_series(left, index)
    b = _slot_series(right, index)
    relevant = (a != "") & (b != "") & (a != "-")
    if not relevant.any():
        return pd.DataFrame()
    a, b = a[relevant], b[relevant]
    if readable:
        a = a.map(lambda char: describe_value(index, char))
        b = b.map(lambda char: describe_value(index, char))
    matrix = pd.crosstab(a.rename("riga = A"), b.rename(""), margins=True, margins_name="TOT")
    return matrix.reset_index()


# ---------------------------------------------------------------------------
# 2. Three-way agreement, with neither model as a reference
# ---------------------------------------------------------------------------

def three_way_agreement(
    stanza_comparison: pd.DataFrame,
    udpipe_comparison: pd.DataFrame,
    *,
    field: str = "postag",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corpus, Stanza and UDPipe on the same tokens: who agrees with whom.

    Returns ``(summary, per_token)``. The summary has four mutually exclusive
    categories, and the fourth is the interesting one:

    * all three agree — nothing to see;
    * corpus with one model — the other model is probably wrong;
    * **both models against the corpus** — the strongest unsupervised signal
      that the corpus annotation deserves a second look, because two
      independently trained systems converged on a different answer;
    * all three differ — a genuinely hard token.
    """
    empty = (pd.DataFrame(), pd.DataFrame())
    if (stanza_comparison is None or udpipe_comparison is None
            or stanza_comparison.empty or udpipe_comparison.empty):
        return empty

    keys = [key for key in KEY_COLUMNS if key in stanza_comparison.columns
            and key in udpipe_comparison.columns]
    if not keys:
        return empty

    stanza_column = _colonna_modello(stanza_comparison, field)
    udpipe_column = _colonna_modello(udpipe_comparison, field)
    reference_column = _colonna_corpus(stanza_comparison, field)
    if not (stanza_column and udpipe_column and reference_column):
        return empty

    # The real table already has a column called ``corpus`` — it carries the name of the
    # corpus, not the annotated value — so it must be removed before renaming the
    # reference column, otherwise the two overlap.
    extra = [name for name in ("form", "lemma", "autore", "opera")
             if name in stanza_comparison.columns
             and name not in (reference_column, stanza_column)]
    left = stanza_comparison[keys + extra + [reference_column, stanza_column]].rename(
        columns={reference_column: "corpus", stanza_column: "stanza"})
    right = udpipe_comparison[keys + [udpipe_column]].rename(
        columns={udpipe_column: "udpipe"})
    merged = left.merge(right, on=keys, how="inner")
    if merged.empty:
        return empty

    corpus = merged["corpus"].astype("string").fillna("")
    stanza = merged["stanza"].astype("string").fillna("")
    udpipe = merged["udpipe"].astype("string").fillna("")

    corpus_stanza = corpus == stanza
    corpus_udpipe = corpus == udpipe
    stanza_udpipe = stanza == udpipe

    category = pd.Series("tutti e tre diversi", index=merged.index, dtype=object)
    category[corpus_stanza & corpus_udpipe] = "tutti e tre d'accordo"
    category[corpus_stanza & ~corpus_udpipe] = "corpus e Stanza contro UDPipe"
    category[~corpus_stanza & corpus_udpipe] = "corpus e UDPipe contro Stanza"
    category[~corpus_stanza & ~corpus_udpipe & stanza_udpipe] = "i due modelli contro il corpus"
    merged["esito"] = category

    order = [
        "tutti e tre d'accordo",
        "corpus e Stanza contro UDPipe",
        "corpus e UDPipe contro Stanza",
        "i due modelli contro il corpus",
        "tutti e tre diversi",
    ]
    counts = merged["esito"].value_counts().reindex(order, fill_value=0)
    summary = pd.DataFrame({
        "esito": counts.index,
        "token": counts.to_numpy(),
        "%": (counts / len(merged) * 100).round(2).to_numpy(),
    })
    summary.loc[len(summary)] = ["TOTALE allineati", len(merged), 100.0]

    interesting = merged[merged["esito"].isin(
        {"i due modelli contro il corpus", "tutti e tre diversi"})]
    return summary, interesting.reset_index(drop=True)


def models_against_corpus(
    stanza_comparison: pd.DataFrame,
    udpipe_comparison: pd.DataFrame,
    *,
    field: str = "postag",
    top: int = 400,
) -> pd.DataFrame:
    """The tokens where both models agree with each other and not with the corpus.

    Deliberately ordered by how often the same (corpus value → model value)
    substitution recurs. A single token is an anecdote; the same substitution
    two hundred times is a systematic divergence between the corpus's
    conventions and what the models learned, and that is a finding.
    """
    _summary, per_token = three_way_agreement(
        stanza_comparison, udpipe_comparison, field=field)
    if per_token.empty:
        return pd.DataFrame()
    both = per_token[per_token["esito"] == "i due modelli contro il corpus"]
    if both.empty:
        return pd.DataFrame()

    grouped = (both.groupby(["corpus", "stanza"], sort=False)
               .agg(token=("esito", "size"),
                    forme=("form", "nunique") if "form" in both.columns else ("esito", "size"),
                    esempio=("form", "first") if "form" in both.columns else ("esito", "first"))
               .reset_index()
               .rename(columns={"corpus": "valore nel corpus", "stanza": "valore dei modelli"}))
    return grouped.sort_values("token", ascending=False).head(top).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Does the model reproduce the noise, or fix it?
# ---------------------------------------------------------------------------

def noise_replication(
    tokens: pd.DataFrame,
    corrected: pd.DataFrame,
    comparison: pd.DataFrame,
    *,
    label: str = "stanza",
) -> pd.DataFrame:
    """On the tokens a rule rewrote, does the model echo the corpus or the fix?

    This is the experiment that makes the diagnosis falsifiable. Restricted to
    tokens where the pipeline changed the tag, each model output falls into one
    of three classes: it reproduces the original annotation (the model learned
    the noise), it independently arrives at the correction (the correction was
    right and a second, independent system says so), or it proposes a third
    value (the token is hard).

    The comparison frame must be the *full* one. Filtering it to corpus/model
    mismatches beforehand deletes the entire "agrees with the original" class
    and turns the result into an artefact.
    """
    if (tokens is None or corrected is None or comparison is None
            or tokens.empty or corrected.empty or comparison.empty):
        return pd.DataFrame()
    keys = [key for key in KEY_COLUMNS if key in tokens.columns and key in corrected.columns]
    if not keys:
        return pd.DataFrame()

    original = tokens[keys + ["form", "postag"]].rename(columns={"postag": "originale"})
    fixed = corrected[keys + ["postag"]].rename(columns={"postag": "corretto"})
    changed = original.merge(fixed, on=keys, how="inner")
    changed = changed[changed["originale"].astype("string").fillna("")
                      != changed["corretto"].astype("string").fillna("")]
    if changed.empty:
        return pd.DataFrame()

    model_column = _colonna_modello(comparison, "postag")
    if not model_column or not all(key in comparison.columns for key in keys):
        return pd.DataFrame()
    model = comparison[keys + [model_column]].rename(columns={model_column: "modello"})
    merged = changed.merge(model, on=keys, how="inner")
    merged = merged[merged["modello"].notna()]
    if merged.empty:
        return pd.DataFrame()

    same_as_original = (merged["modello"].astype("string")
                        == merged["originale"].astype("string"))
    same_as_corrected = (merged["modello"].astype("string")
                         == merged["corretto"].astype("string"))

    rows = [
        {"esito": "riproduce l'annotazione originale",
         "token": int((same_as_original & ~same_as_corrected).sum())},
        {"esito": "converge sulla correzione",
         "token": int((~same_as_original & same_as_corrected).sum())},
        {"esito": "propone un terzo valore",
         "token": int((~same_as_original & ~same_as_corrected).sum())},
    ]
    total = len(merged)
    for row in rows:
        row["%"] = round(row["token"] / total * 100, 1) if total else 0.0
    rows.append({"esito": "TOTALE token modificati", "token": total, "%": 100.0})
    frame = pd.DataFrame(rows)
    frame.attrs["modello"] = SOURCE_LABELS.get(label, label)
    return frame


# ---------------------------------------------------------------------------
# 4. Model-vs-model, by author and by feature
# ---------------------------------------------------------------------------

def agreement_by_group(
    stanza_comparison: pd.DataFrame,
    udpipe_comparison: pd.DataFrame,
    tokens: pd.DataFrame,
    *,
    group: str = "autore",
) -> pd.DataFrame:
    """Corpus↔model and model↔model agreement, per author (or genre, or period).

    The point of the breakdown: an aggregate agreement rate is an average over
    a corpus that is not homogeneous. Models trained mostly on classical Attic
    behave differently on Polybius' koiné, and the only way to see that is to
    stop averaging.
    """
    if (stanza_comparison is None or udpipe_comparison is None
            or stanza_comparison.empty or udpipe_comparison.empty
            or tokens is None or tokens.empty or group not in tokens.columns):
        return pd.DataFrame()

    keys = [key for key in KEY_COLUMNS if key in stanza_comparison.columns
            and key in udpipe_comparison.columns and key in tokens.columns]
    if not keys:
        return pd.DataFrame()

    stanza_column = _colonna_modello(stanza_comparison, "postag")
    udpipe_column = _colonna_modello(udpipe_comparison, "postag")
    reference_column = _colonna_corpus(stanza_comparison, "postag")
    if not (stanza_column and udpipe_column and reference_column):
        return pd.DataFrame()

    # The two tables call the prediction the same way — ``postag_modello`` in both — so
    # the names must be decided before the merge: afterwards, pandas would have told
    # them apart by itself with suffixes, and the code below would have looked for a
    # column that no longer exists.
    left = stanza_comparison[keys + [reference_column, stanza_column]].rename(
        columns={reference_column: "_rif", stanza_column: "_stanza"})
    right = udpipe_comparison[keys + [udpipe_column]].rename(
        columns={udpipe_column: "_udpipe"})
    merged = left.merge(right, on=keys, how="inner")
    # The grouping field may be one of the keys — ``document_id`` is, and it is the
    # only one that these corpora offer — and in that case it is already inside
    # ``merged``, carried by the merge. Taking it again from ``tokens`` would
    # produce two columns with the same name, and ``drop_duplicates`` would stop
    # there: “The column label 'document_id' is not unique”.
    if group not in merged.columns:
        merged = merged.merge(tokens[keys + [group]].drop_duplicates(subset=keys),
                              on=keys, how="left")
    if merged.empty:
        return pd.DataFrame()

    corpus = merged["_rif"].astype("string").fillna("")
    stanza = merged["_stanza"].astype("string").fillna("")
    udpipe = merged["_udpipe"].astype("string").fillna("")
    merged["_cs"] = corpus == stanza
    merged["_cu"] = corpus == udpipe
    merged["_su"] = stanza == udpipe

    table = merged.groupby(group, dropna=False, sort=False).agg(
        token=("_cs", "size"),
        accordo_corpus_stanza=("_cs", "mean"),
        accordo_corpus_udpipe=("_cu", "mean"),
        accordo_stanza_udpipe=("_su", "mean"),
    ).reset_index()
    for column in ("accordo_corpus_stanza", "accordo_corpus_udpipe", "accordo_stanza_udpipe"):
        table[column] = (table[column] * 100).round(2)
    table = table.rename(columns={
        "accordo_corpus_stanza": "% corpus ↔ Stanza",
        "accordo_corpus_udpipe": "% corpus ↔ UDPipe",
        "accordo_stanza_udpipe": "% Stanza ↔ UDPipe",
    })
    return table.sort_values("token", ascending=False).reset_index(drop=True)


def divergence_hotspots(
    stanza_comparison: pd.DataFrame,
    udpipe_comparison: pd.DataFrame,
    *,
    top: int = 60,
) -> pd.DataFrame:
    """The word forms on which the two models most often disagree.

    A ranked list of where automatic annotation of Greek is currently weakest —
    useful to the corpus builder (these are the tokens to check first) and to
    the model builder (these are the constructions to work on).
    """
    if (stanza_comparison is None or udpipe_comparison is None
            or stanza_comparison.empty or udpipe_comparison.empty):
        return pd.DataFrame()
    keys = [key for key in KEY_COLUMNS if key in stanza_comparison.columns
            and key in udpipe_comparison.columns]
    if not keys or "form" not in stanza_comparison.columns:
        return pd.DataFrame()

    stanza_column = _colonna_modello(stanza_comparison, "postag")
    udpipe_column = _colonna_modello(udpipe_comparison, "postag")
    if not (stanza_column and udpipe_column):
        return pd.DataFrame()

    # As above: the two names coincide, and must be separated before the merge.
    left = stanza_comparison[keys + ["form", stanza_column]].rename(
        columns={stanza_column: "_stanza"})
    right = udpipe_comparison[keys + [udpipe_column]].rename(
        columns={udpipe_column: "_udpipe"})
    merged = left.merge(right, on=keys, how="inner")
    if merged.empty:
        return pd.DataFrame()

    disagree = (merged["_stanza"].astype("string").fillna("")
                != merged["_udpipe"].astype("string").fillna(""))
    merged["_diverge"] = disagree

    table = merged.groupby("form", sort=False).agg(
        occorrenze=("_diverge", "size"),
        divergenze=("_diverge", "sum"),
    ).reset_index()
    table = table[table["occorrenze"] >= 5]
    if table.empty:
        return pd.DataFrame()
    table["% divergenza"] = (table["divergenze"] / table["occorrenze"] * 100).round(1)
    return (table.sort_values(["divergenze", "% divergenza"], ascending=False)
            .head(top).reset_index(drop=True))


def summarise_comparison(comparison: pd.DataFrame, label: str) -> dict[str, object]:
    """Headline agreement figures for one model against the corpus."""
    if comparison is None or comparison.empty:
        return {}
    lemma_match = comparison.get("lemma_match")
    postag_match = comparison.get("postag_match")
    result: dict[str, object] = {"token allineati": int(len(comparison))}
    if lemma_match is not None:
        result["% lemmi uguali"] = round(float(lemma_match.mean()) * 100, 2)
        result["lemmi diversi"] = int((~lemma_match).sum())
    if postag_match is not None:
        result["% postag uguali"] = round(float(postag_match.mean()) * 100, 2)
        result["postag diversi"] = int((~postag_match).sum())
    result["modello"] = SOURCE_LABELS.get(label, label)
    return result
