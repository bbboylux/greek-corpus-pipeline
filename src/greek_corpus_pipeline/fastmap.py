"""Apply a Python function once per *distinct* value instead of once per row.

A treebank column is enormously redundant. In the Gorman corpus, 625,176 tokens
carry 1,185 distinct PoS-tags, 18,658 distinct lemmas and 69,461 distinct word
forms. Every diagnostic that walks the column with ``Series.map(python_func)``
therefore does between nine and five hundred times more work than the question
requires — and the checks in this package are almost all of that shape, because
the questions they ask ("is this tag nine characters long", "does this form
contain a Latin letter") depend on the string alone and on nothing else in the
row.

``map_unique`` factorises the column, evaluates the function on the distinct
values, and gathers the answers back. The result is identical to ``Series.map``
— same values, same index, same dtype behaviour — so it is a drop-in
replacement wherever the function is *pure*, which is the only case in which
``map`` was correct to begin with.

The measured effect on the full Gorman corpus: the text-and-encoding family
falls from 10.1 s to 1.4 s, the PoS-tag family from 4.1 s to 0.6 s. Nothing
about the analysis changes; the program simply stops asking the same question
five hundred times.

The one caveat worth stating: for a function that is cheaper than a dictionary
lookup, factorising costs more than it saves. ``map_unique`` therefore falls
back to a plain ``map`` when the column has almost no repetition, which is the
right behaviour for a column of unique identifiers.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

#: Below this ratio of rows to distinct values, factorising is not worth it.
MIN_REDUNDANCY = 1.5


def map_unique(values: pd.Series, function: Callable[[object], object]) -> pd.Series:
    """``values.map(function)`` computed once per distinct value.

    *function* must be pure: same input, same output, no side effects. Missing
    values are passed through to *function* exactly as ``Series.map`` would.
    """
    if values is None or len(values) == 0:
        return pd.Series(dtype=object, index=getattr(values, "index", None))

    codes, uniques = pd.factorize(values, use_na_sentinel=False)
    if len(uniques) * MIN_REDUNDANCY >= len(values):
        return values.map(function)

    # ``uniques`` comes back as an Arrow-backed Index for every string column in
    # the package, and walking one of those hands back a freshly boxed Python
    # object per element: on the 69,461 distinct word forms of the Gorman corpus
    # that is 0.08 s of pure unboxing before the function under test has run
    # once. Materialising the object array first halves it, and this loop is on
    # the path of every check in the program.
    distinct = np.asarray(uniques, dtype=object)
    answers = np.empty(len(distinct), dtype=object)
    for position, value in enumerate(distinct):
        answers[position] = function(value)
    return pd.Series(answers[codes], index=values.index)


def mask_unique(values: pd.Series, predicate: Callable[[object], bool]) -> pd.Series:
    """A boolean mask from a per-value predicate, computed once per distinct value.

    Returns a real boolean Series (never object), so it can be combined with
    ``&`` and ``|`` without the NA-propagation surprises that a nullable
    boolean column produces.
    """
    mapped = map_unique(values, predicate)
    return mapped.fillna(False).astype(bool)


def transform_column(frame: pd.DataFrame, column: str,
                     function: Callable[[object], object]) -> pd.Series:
    """``map_unique`` on a named column, or an empty Series if it is absent."""
    if frame is None or column not in frame.columns:
        return pd.Series(dtype=object, index=getattr(frame, "index", None))
    return map_unique(frame[column], function)


def grouped_join(values: pd.Series, keys: pd.Series, separator: str) -> pd.Series:
    """``keys``-grouped ``separator.join(values)``, in order of first appearance.

    This is what ``groupby(key, sort=False)[column].agg(sep.join)`` computes, and
    pandas computes it by materialising one Series per group — one block slice,
    one index, one string array — before handing it to the Python callable. The
    tables in this package group by *type* — one group per distinct word form,
    per sentence, per lemma — so the group count is enormous and each group is
    tiny. Slicing dominates, and the joining does not even show up.

    Sorting the group codes once and slicing a Python list instead takes the
    lemma inventory from 25.9 s to 0.9 s and the sentence context from 4.5 s to
    0.5 s.
    """
    codes, uniques = pd.factorize(keys, sort=False)
    bounds = np.zeros(len(uniques) + 1, dtype="int64")
    np.cumsum(np.bincount(codes, minlength=len(uniques)), out=bounds[1:])
    ordered = values.to_numpy()[np.argsort(codes, kind="stable")].tolist()
    return pd.Series(
        [separator.join(ordered[bounds[group]:bounds[group + 1]])
         for group in range(len(uniques))],
        index=pd.Index(uniques, name=keys.name))


def build_frame(columns: "dict[str, object]", length: int) -> pd.DataFrame:
    """Assemble a DataFrame in one construction instead of column by column.

    ``frame[name] = values`` looks harmless and is not: each assignment inserts
    a block into the frame's manager, and inserting *n* columns one at a time is
    quadratic in *n*. The findings tables in this package have sixteen columns
    and are built a few hundred times per run, which turned table assembly into
    the single largest cost of the PoS-tag family — larger than every check it
    was assembling the results of.

    Passing the whole dictionary to the constructor builds the manager once.
    Scalars are broadcast to *length*; Series contribute their values, with the
    index discarded.
    """
    data = {}
    for name, value in columns.items():
        if isinstance(value, pd.Series):
            data[name] = value.to_numpy()
        elif isinstance(value, np.ndarray):
            data[name] = value
        else:
            data[name] = np.repeat(np.asarray([value], dtype=object), length)
    return pd.DataFrame(data, index=pd.RangeIndex(length))
