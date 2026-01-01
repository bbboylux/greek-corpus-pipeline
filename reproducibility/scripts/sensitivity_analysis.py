#!/usr/bin/env python
"""Redo the sensitivity analysis of Supplement S5 on the runs of the six strata.

Two checks are subjected to it (S5): ``rare-relation-for-lemma-and-pos`` (parameters
minimum support and maximum share of the relation) and ``lemma-rare-for-form``
(minimum number of occurrences of the form-and-part-of-speech pair, and minimum share of
the majority lemma; at most one occurrence of the rare lemma). Each is re-evaluated, with
the function of the program, on the records of the run at the configurations of the
supplement, 15 configurations on six strata, 90 evaluations in all:

    rare-relation-for-lemma-and-pos   support 100, 200   x   share 0.5%, 1%, 2%
    lemma-rare-for-form               support 15, 25, 50 x   majority 90%, 95%, 98%

For every evaluation it prints the number of findings, the findings of the run that the
configuration loses and the findings that it adds, and compares the three numbers with
``reference/table_S5_1_rare_relation.csv`` and ``reference/table_S5_2_rare_lemma.csv``.
A finding is identified by source file, document, sentence index and token index; the
baseline is the finding of that check in ``findings.parquet`` of the run (the adopted
configuration: support 200 and share 1%; support 25 and majority 95%).

usage:
    python sensitivity_analysis.py --workspace W        the runs written by rerun_diagnosis.py
    python sensitivity_analysis.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import REFERENCE, STRATA, stratum_of

import pandas as pd

from greek_corpus_pipeline import agreement, lemma, units

KEY = ["source_file", "document_id", "sentence_index", "token_index"]
RELATION = "rare-relation-for-lemma-and-pos"
LEMMA = "lemma-rare-for-form"
SHARES = {"0.5%": 0.005, "1%": 0.01, "2%": 0.02}
MAJORITIES = {"90%": 0.90, "95%": 0.95, "98%": 0.98}


def keys(frame: pd.DataFrame) -> set[tuple]:
    return set(map(tuple, frame[KEY].astype(str).to_numpy())) if len(frame) else set()


def evaluate(folder: Path) -> dict[tuple, tuple[int, int, int]]:
    """(check, first parameter, second parameter) -> (findings, lost, added) for one run."""
    tokens = pd.read_parquet(folder / "tokens.parquet")
    findings = pd.read_parquet(folder / "findings.parquet")
    active = tokens[~pd.Series(units.is_technical_record(tokens), index=tokens.index).astype(bool)]
    words = active[pd.Series(units.is_word(active), index=active.index).astype(bool)]
    base_relation = keys(findings[findings["rule_id"] == RELATION])
    base_lemma = keys(findings[findings["rule_id"] == LEMMA])
    result: dict[tuple, tuple[int, int, int]] = {}
    for support in (100, 200):
        for label, share in SHARES.items():
            got = keys(agreement.check_rare_relation(words, min_support=support, max_share=share))
            result[(RELATION, str(support), label)] = (len(got), len(base_relation - got), len(got - base_relation))
    for support in (15, 25, 50):
        for label, majority in MAJORITIES.items():
            got = keys(lemma.check_rare_lemma_for_form(
                active, min_form_total=support, max_rare=1, min_major_share=majority))
            result[(LEMMA, str(support), label)] = (len(got), len(base_lemma - got), len(got - base_lemma))
    return result


def reference_rows() -> list[dict[str, str]]:
    rows = []
    for name, second in (("table_S5_1_rare_relation.csv", "share"), ("table_S5_2_rare_lemma.csv", "majority")):
        with (REFERENCE / name).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["second"] = row[second]
                rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="*", type=Path)
    parser.add_argument("--workspace", type=Path)
    arguments = parser.parse_args(argv)
    folders = list(arguments.runs)
    if arguments.workspace:
        folders += [arguments.workspace / "runs" / f"rerun-{s}" for s in STRATA
                    if (arguments.workspace / "runs" / f"rerun-{s}" / "findings.parquet").is_file()]
    if not folders:
        parser.error("give run folders or --workspace")

    obtained: dict[tuple, tuple[int, int, int]] = {}
    for folder in folders:
        stratum = stratum_of(folder)
        if stratum is None:
            parser.error(f"cannot tell which stratum {folder.name} is")
        for key, value in evaluate(folder).items():
            obtained[(stratum,) + key] = value
        print(f"evaluated {stratum}", flush=True)

    compared = different = 0
    print(f"\n{'check':<34} {'support':>7} {'second':>7} {'stratum':<16} "
          f"{'findings':>16} {'lost':>12} {'added':>12}")
    for row in reference_rows():
        key = (row["stratum"], row["check"], row["support"], row["second"])
        if key not in obtained:
            continue
        expected = (int(row["findings"]), int(row["lost"]), int(row["added"]))
        got = obtained[key]
        compared += 1
        same = expected == got
        different += not same
        mark = " *" if row["adopted"] == "yes" else ""
        print(f"{row['check']:<34} {row['support']:>7} {row['second']:>7} {row['stratum']:<16} "
              f"{expected[0]:>7}/{got[0]:<7} {expected[1]:>5}/{got[1]:<5} {expected[2]:>5}/{got[2]:<5}"
              f"{'' if same else '   DIFFERENT'}{mark}")
    print("\n(each cell: reference/obtained; * = the configuration adopted in the study)")
    print(f"RESULT: {compared} evaluations compared, "
          + ("all identical to the supplement" if not different else f"{different} differ"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
