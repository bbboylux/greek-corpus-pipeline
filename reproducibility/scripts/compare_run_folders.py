#!/usr/bin/env python
"""Compare two run folders cell by cell (the repetition that Supplement S11.2 describes).

S11.2 states that a repetition of the six runs on a second machine reproduces "cell by cell" the
imported tokens, the findings with their proposals, the arcs and the tables of the variation
nuclei, and, for Gorman and Pedalion, the four comparison tables of the models. This script makes
that statement testable: it reads the same table in two run folders and compares every cell.

The tables are those a run writes: the nine *core* tables (``tokens``, ``arcs``, ``findings``,
the five ``variation_<plane>`` tables and ``spelling_variation``) and the two *model* tables
(``stanza_comparison`` and ``udpipe_comparison``, which exist only in the runs on Gorman and on
Pedalion that included the comparison with the models).

**What "identical" means.** Two tables are identical when they have the same columns in the same
order, the same number of rows and the same value in every cell, rows being compared in the order
in which they are stored. A missing value is equal to a missing value and to nothing else: a
missing value against the number 5 (or against an empty text) is a difference, whatever the type
of the column. If the order of the rows is the only difference this is said.

**What can be missing.** A table that is in only one of the two folders is a failure, whichever
table it is: the comparison does not cover it, and the statement of S11.2 about it would be left
untested. The tables ``tokens`` (the imported records) and ``findings`` are required in both
folders: every run writes them, and a folder that has no ``tokens.parquet`` or no
``findings.parquet`` is not a run folder, so their absence from both is a failure too. Any other
core table that is in neither folder is not a failure: a run writes no file for a table that would
be empty (on a small corpus a plane of the variation may find no nuclei and have none), and two runs
that agree on its absence agree. It is said on its own line and in the result line, and it is not
counted among the tables compared. The two model tables are written only by the runs that compared
the models; when only one of the two runs did, the failure is the right verdict, unless you say with
``--skip-models`` that the models are not what you are comparing (the result of
``rerun_diagnosis.py`` alone, for instance): the model tables are then not looked at, and the result
line says that they were not compared. When the model tables are in neither folder and you did not
say ``--skip-models``, the result line names them as not compared: the statement of S11.2 about the
four comparison tables of the models is then not tested by this run, and nothing is claimed about it.

**Two labels.** In two columns the value is a label, not a result of the diagnosis, and a run of
another version or language of the program may word it differently:

* ``arcs.direction``, the word with which the program says "head to the left / to the right".
  The study's tables carry the Italian wording (``testa a sinistra``, ``testa a destra``), this
  package the English one (``head to the left``, ``head to the right``). The four wordings are
  known: they are read as *left* and *right* and the two columns are compared on that, row by
  row, so that a left that became a right is a difference. A wording that is not one of the four
  must be the same in both tables.
* ``tokens.corpus``, the name that the person gave when loading the corpus. It may differ when
  each of the two tables holds a single name, and a real one: a text that is not empty and not
  made of spaces only (the label of that load). A table whose label is missing, empty or blank
  is not "another label": it is a table that has none, and it is a difference against a table
  that has one. If a table holds several names they must be the same.

With ``--exact`` these two columns are compared like any other. The three descriptive texts of a
finding (``anomaly_name``, ``anomaly_description``, ``issue``) are not labels in this sense: the
program writes them in Italian whatever the language of the interface, and they must be identical.

What the comparison does not cover: the run folders of the study are not distributed with this
package (S11.4), so a reviewer has them only if the authors supply them. Two runs of your own
(for instance the same inputs on Windows and on Linux) can be compared in the same way.

usage:
    python compare_run_folders.py RUN_A RUN_B [--exact] [--skip-models]
    python compare_run_folders.py --study-runs DIR --workspace W [--strata gorman pedalion ...]
                                  [--exact] [--skip-models]

``DIR`` holds the run folders of the study under the names of ``STUDY_RUNS`` in ``repro_common.py``
(for instance ``20260909-053400-gorman``); ``W`` is the workspace given to ``rerun_diagnosis.py``
(the runs ``W/runs/rerun-<stratum>``). A study folder or a re-run folder that is not there is a
failure. The exit status is 0 only when the tables ``tokens`` and ``findings`` and at least one other
were compared, no table is in only one of the two folders, and all the tables compared are identical;
it is 1 otherwise. What was not compared (the tables that are in neither folder, the model tables that
were left out or that no run had) is named in the result line.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA, STUDY_RUNS

import numpy as np
import pandas as pd

CORE_TABLES = (
    "tokens", "arcs", "findings",
    "variation_morfologia", "variation_posizioni", "variation_contesto",
    "variation_dipendenze", "variation_lemmi",
    "spelling_variation",
)
MODEL_TABLES = ("stanza_comparison", "udpipe_comparison")
TABLES = CORE_TABLES + MODEL_TABLES
#: Every run writes these two: the imported records and the findings. A folder without them is not a run folder.
REQUIRED_TABLES = ("tokens", "findings")

#: The known wordings of the direction of an arc, by the direction they name.
DIRECTION_WORDING = {
    "testa a sinistra": "left", "head to the left": "left",
    "testa a destra": "right", "head to the right": "right",
}


def differing_cells(first: pd.Series, second: pd.Series) -> np.ndarray:
    """True where two columns differ.

    A missing value equals a missing value and nothing else. The test does not depend on the type
    of the columns: with the nullable types of pandas (``Int64``, ``string``, ``boolean``) the
    expression ``a == b`` is itself missing when one side is missing, and a missing result would
    be dropped from a count of differences.
    """
    first_missing = first.isna().to_numpy(dtype=bool)
    second_missing = second.isna().to_numpy(dtype=bool)
    if (first.dtype.kind in "biuf" and second.dtype.kind in "biuf"
            and not first_missing.any() and not second_missing.any()):
        return first.to_numpy() != second.to_numpy()          # plain numeric columns, nothing missing
    differ = first_missing != second_missing
    both = ~first_missing & ~second_missing
    if both.any():
        a = first.to_numpy(dtype=object)[both]
        b = second.to_numpy(dtype=object)[both]
        differ[both] = ~np.asarray(a == b, dtype=bool)
    return differ


def direction_reading(series: pd.Series) -> pd.Series:
    """The direction named by each cell (left, right), or the cell itself when it is not a known wording."""
    return series.map(lambda value: DIRECTION_WORDING.get(value, value) if isinstance(value, str) else value)


def single_label(series: pd.Series) -> str | None:
    """The one real label that a column holds, or None.

    A label is a text that is not empty and not made of spaces only; a column that holds one such
    text in every row has that label. A column of missing values, of empty texts or of blanks, and a
    column that holds several values, has none.
    """
    values = series.drop_duplicates()
    if len(values) != 1:
        return None
    value = values.iloc[0]
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def describe(pairs: list[tuple[object, object]], limit: int = 3) -> str:
    shown = [f"{str(a)[:40]!r} = {str(b)[:40]!r}" for a, b in pairs[:limit]]
    more = f", and {len(pairs) - limit} more" if len(pairs) > limit else ""
    return "; ".join(shown) + more


def same_rows_in_another_order(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Do the two tables hold the same rows, only in a different order?

    Used to say *why* two tables differ, never to excuse the difference. A missing value is a value of
    its own: each column is looked at twice, as "is it missing" and as its text, so that a missing value
    and an empty text are not taken for each other.
    """
    def signature(frame: pd.DataFrame) -> pd.DataFrame:
        columns: dict[str, np.ndarray] = {}
        for column in frame.columns:
            columns[f"{column}\x00missing"] = frame[column].isna().to_numpy(dtype=bool)
            columns[f"{column}\x00text"] = frame[column].astype("string").fillna("").to_numpy(dtype=object)
        keyed = pd.DataFrame(columns)
        return keyed.sort_values(list(keyed.columns), kind="mergesort").reset_index(drop=True)

    return signature(left).equals(signature(right))


def compare_table(name: str, a: Path, b: Path, exact: bool = False) -> tuple[str, bool]:
    """The verdict on one table: (text, identical)."""
    left, right = pd.read_parquet(a), pd.read_parquet(b)
    if list(left.columns) != list(right.columns):
        only_a = [c for c in left.columns if c not in right.columns]
        only_b = [c for c in right.columns if c not in left.columns]
        return (f"DIFFERENT columns (only in the first: {only_a}; only in the second: {only_b})", False)
    if len(left) != len(right):
        return (f"DIFFERENT number of rows ({len(left):,} against {len(right):,})", False)

    accepted: list[str] = []              # label columns that differ only in their wording
    decisive: dict[str, int] = {}         # columns that differ, and by how many cells
    first_row: dict[str, int] = {}
    for column in left.columns:
        first, second = left[column], right[column]
        wrong = differing_cells(first, second)
        total = int(wrong.sum())
        if not total:
            continue
        if not exact and name == "arcs" and column == "direction":
            reading = differing_cells(direction_reading(first), direction_reading(second))
            if not reading.any():
                pairs = sorted({(x, y) for x, y in zip(first[wrong], second[wrong])})
                accepted.append(f"direction ({describe(pairs)})")
                continue
            wrong, total = reading, int(reading.sum())
        elif not exact and name == "tokens" and column == "corpus":
            label_first, label_second = single_label(first), single_label(second)
            if label_first is not None and label_second is not None:
                accepted.append(f"corpus ({label_first[:40]!r} = {label_second[:40]!r})")
                continue
        decisive[column] = total
        first_row[column] = int(wrong.nonzero()[0][0])

    shape = f"{len(left):,} rows x {len(left.columns)} columns"
    if not decisive:
        note = "; the wording of a label differs, accepted: " + " | ".join(accepted) if accepted else ""
        return (f"identical, {shape}{note}", True)

    if same_rows_in_another_order(left, right):
        return (f"DIFFERENT only in the order of the rows, {shape}", False)
    detail = "; ".join(
        f"{c}: {n:,} cells (first at row {first_row[c]}: {str(left[c].iloc[first_row[c]])[:40]!r} "
        f"against {str(right[c].iloc[first_row[c]])[:40]!r})" for c, n in decisive.items())
    return (f"DIFFERENT, {shape}: {detail}", False)


class Tally:
    """What the comparison of two run folders found: counts, and the names of what was not covered."""

    def __init__(self) -> None:
        self.compared = 0                          # tables compared
        self.different = 0                         # of these, the ones that are not identical
        self.missing = 0                           # tables that are in only one of the two folders
        self.skipped = 0                           # model tables left out by request
        self.in_neither: list[str] = []            # core tables that are in neither folder
        self.models_in_neither: list[str] = []     # model tables that are in neither folder (not asked to skip)
        self.required_absent: list[str] = []       # required tables that are in neither folder

    def add(self, other: "Tally") -> None:
        self.compared += other.compared
        self.different += other.different
        self.missing += other.missing
        self.skipped += other.skipped
        self.in_neither += other.in_neither
        self.models_in_neither += other.models_in_neither
        self.required_absent += other.required_absent


def compare_folders(first: Path, second: Path, exact: bool = False,
                    skip_models: bool = False, models_expected: bool = True) -> Tally:
    """Compare the tables of two run folders; print one line each.

    The result says how many tables were compared and how many of them differ, how many tables are in
    only one of the two folders, which required tables (``tokens``, ``findings``) are in neither, which
    other core tables are in neither, which model tables are in neither (when they were not left out by
    request), and how many model tables were left out by request. The study compared the models on Gorman
    and on Pedalion only: for a stratum on which no run of the study had them (``models_expected`` false) the
    model tables are in neither folder by design, which is said on their line and is not a gap.
    """
    tally = Tally()
    for name in TABLES:
        a, b = first / f"{name}.parquet", second / f"{name}.parquet"
        if name in MODEL_TABLES and skip_models:
            tally.skipped += 1
            print(f"  {name:<24} not looked at (--skip-models)")
            continue
        if not a.is_file() and not b.is_file():
            if name in REQUIRED_TABLES:
                tally.required_absent.append(name)
                print(f"  {name:<24} MISSING from both folders: every run writes it, so these are not run "
                      "folders; not compared")
            elif name in MODEL_TABLES and not models_expected:
                print(f"  {name:<24} in neither folder: the study did not compare the models on this stratum")
            elif name in MODEL_TABLES:
                tally.models_in_neither.append(name)
                print(f"  {name:<24} in neither folder: these runs did not include the models; not compared")
            else:
                tally.in_neither.append(name)
                print(f"  {name:<24} in neither folder: not compared (a run writes no table when it would be empty)")
            continue
        if not (a.is_file() and b.is_file()):
            where = "only in the first folder" if a.is_file() else "only in the second folder"
            print(f"  {name:<24} MISSING, {where}: not compared")
            tally.missing += 1
            continue
        verdict, same = compare_table(name, a, b, exact)
        tally.compared += 1
        tally.different += not same
        print(f"  {name:<24} {verdict}")
    return tally


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="*", type=Path, help="two run folders")
    parser.add_argument("--study-runs", type=Path, help="folder with the run folders of the study")
    parser.add_argument("--workspace", type=Path, help="workspace of rerun_diagnosis.py")
    parser.add_argument("--strata", nargs="*", choices=STRATA, default=list(STRATA))
    parser.add_argument("--exact", action="store_true",
                        help="a different wording of a label (the direction of an arc, the name of the "
                             "corpus) is a difference like any other")
    parser.add_argument("--skip-models", action="store_true",
                        help="do not look at the two model tables (for runs without the models); the "
                             "result line says that they were not compared")
    arguments = parser.parse_args(argv)

    pairs: list[tuple[str, Path, Path]] = []
    absent = 0                      # run folders that were asked for and are not there
    if arguments.runs:
        if len(arguments.runs) != 2:
            parser.error("give exactly two run folders")
        for folder in arguments.runs:
            if not folder.is_dir():
                print(f"== {folder}: not a folder")
                absent += 1
        if not absent:
            pairs.append((arguments.runs[0].name + " / " + arguments.runs[1].name, *arguments.runs))
    elif arguments.study_runs and arguments.workspace:
        for stratum in arguments.strata:
            study = arguments.study_runs / STUDY_RUNS[stratum]
            rerun = arguments.workspace / "runs" / f"rerun-{stratum}"
            if study.is_dir() and rerun.is_dir():
                pairs.append((stratum, study, rerun))
            else:
                absent += 1
                print(f"== {stratum}: NOT COMPARED, {'study folder' if not study.is_dir() else 're-run folder'}"
                      f" not found ({study if not study.is_dir() else rerun})")
    else:
        parser.error("give two run folders, or --study-runs and --workspace")

    total = Tally()
    for label, first, second in pairs:
        print(f"== {label} ==")
        # the study compared the models on Gorman and on Pedalion only
        models_expected = label in ("gorman", "pedalion") or label not in STRATA
        total.add(compare_folders(first, second, arguments.exact, arguments.skip_models, models_expected))

    problems = []
    if total.different:
        problems.append(f"{total.different} not identical")
    if total.missing:
        problems.append(f"{total.missing} table(s) in only one of the two folders")
    if total.required_absent:
        problems.append("required table(s) in neither folder: " + ", ".join(sorted(set(total.required_absent))))
    if absent:
        problems.append(f"{absent} run folder(s) not found")
    if not total.compared:
        problems.append("nothing was compared")
    notes = ""
    if total.in_neither:
        notes += (f"; {len(total.in_neither)} table(s) in neither folder: "
                  f"{', '.join(sorted(set(total.in_neither)))}")
    if total.models_in_neither:
        notes += ("; NOT COMPARED, the model tables " + ", ".join(sorted(set(total.models_in_neither)))
                  + " are in neither folder (these runs did not include the models, so the statement of S11.2 "
                    "about the four comparison tables of the models is not tested)")
    if total.skipped:
        notes += f"; {total.skipped} model table(s) not looked at (--skip-models)"
    if problems:
        print(f"RESULT: {total.compared} tables compared; FAILED: " + "; ".join(problems) + notes)
        return 1
    print(f"RESULT: {total.compared} tables compared, all identical{notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
