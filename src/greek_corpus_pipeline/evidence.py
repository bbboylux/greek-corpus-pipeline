# -*- coding: utf-8 -*-
"""The occurrences behind a type-level finding.

Some checks do not speak of a record but of a *type*: “this form appears in the corpus
with two different lemmas”, “this lemma never carries a case”, “this particle carries
this relation in one per cent of the cases”. For a finding of that kind the selected row
is only a representative, and by itself it is not enough to correct anything: the reader
must see which are the competing readings, how many times each occurs and where to go
and read them.

This module computes that table. It decides nothing and flags nothing: it collects and
counts.
"""
from __future__ import annotations

import pandas as pd

#: How many distinct rows to show at most. Beyond that, the table says how many it has
#: cut: a list truncated in silence reads as a complete list.
MAX_ROWS = 40

#: On which field to group, per check. An absent key means “group on the form”, which is
#: the most common case.
_BY_LEMMA = {
    "uninflected-lemma", "lemma-graphic-variant", "lemma-tool-numbering",
    "lemma-suspicious-characters", "lemma-rare-for-form",
}


def grouping_field(rule_id: object) -> str:
    return "lemma" if str(rule_id or "") in _BY_LEMMA else "form"


def readings(
    tokens: pd.DataFrame,
    value: object,
    field: str = "form",
    *,
    max_rows: int = MAX_ROWS,
    lingua: str = "it",
) -> tuple[pd.DataFrame, int]:
    """The distinct readings of a form (or of a lemma) in the corpus.

    Return a table with lemma, tag, relation, number of occurrences and an example
    location, sorted by decreasing frequency, and the number of distinct rows left out.
    """
    empty = pd.DataFrame(columns=["lemma", "postag", "relation", "occorrenze",
                                  "esempio", "document_id", "sentence_id",
                                  "token_id"])
    if tokens is None or tokens.empty or field not in tokens.columns:
        return empty, 0
    text = tokens[field].astype("string").fillna("")
    wanted = "" if value is None or pd.isna(value) else str(value)
    subset = tokens[text == wanted]
    if subset.empty:
        return empty, 0

    columns = [c for c in ("lemma", "postag", "relation") if c in subset.columns]
    if not columns:
        return empty, 0
    work = subset.copy()
    for column in columns:
        work[column] = work[column].astype("string").fillna("")

    grouped = work.groupby(columns, dropna=False, sort=False)
    counts = grouped.size().reset_index(name="occorrenze")
    first = grouped.head(1).set_index(columns)
    counts = counts.sort_values("occorrenze", ascending=False)
    resto = max(0, len(counts) - max_rows)
    counts = counts.head(max_rows)

    for column in ("document_id", "sentence_id", "token_id"):
        if column in first.columns:
            counts[column] = [
                first.loc[tuple(row[c] for c in columns) if len(columns) > 1
                          else row[columns[0]], column]
                for _, row in counts.iterrows()]
        else:
            counts[column] = ""
    # The example location is a sentence, and the word “sentence” is text: the caller
    # says in which language it wants it. Written here in Italian only, it would come
    # back in Italian inside an English interface.
    parola = " · frase " if str(lingua) != "en" else " · sentence "
    counts["esempio"] = (counts["document_id"].astype("string").fillna("")
                         + parola + counts["sentence_id"].astype("string").fillna(""))
    for column in ("lemma", "postag", "relation"):
        if column not in counts.columns:
            counts[column] = ""
    return counts.reset_index(drop=True), resto
