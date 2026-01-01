#!/usr/bin/env python
"""Compare a re-run (``rerun_diagnosis.py``) with the reference values of the study.

For every stratum it compares, field by field, the numbers of Table S11.1 (imported
and active records, words, analysable links and sentences, findings, active checks,
nuclei, fingerprint of the findings), the nuclei of each of the five levels of the
n-gram variation (Table S8.1), the findings themselves (the four-field key of each one,
as a multiset), the number of findings of each of the 77 checks and the split of the
findings into violations, cases to verify and variants (Supplement S6).

usage:
    python compare_with_reference.py WORKSPACE [--strata gorman pedalion ...] [--skip-variation]

WORKSPACE is the folder given to ``rerun_diagnosis.py``. The report is printed and
written to ``WORKSPACE/reproduction/comparison.txt``.

**What the verdict means.** By default the comparison covers all six strata of the study,
and a stratum that is not in the re-run is a failure, not a stratum left out: a re-run
that has only one stratum does not confirm the study. The verdict "every compared value is
identical to the study" is given only when

* every stratum asked for has exactly one row in ``rerun_summary.csv`` (an empty summary,
  a missing stratum and a stratum that appears twice are failures);
* the input files of every one of those strata are those of the study, that is, the input
  fingerprint of the row is the one of ``reference/inputs.csv`` (on other input files a
  difference is expected, and identical values do not confirm the study either: the
  report says so and the verdict is "not confirmed");
* the four-field keys of the findings of every stratum are there to be compared;
* the n-gram variation family was run and its nuclei are compared (a re-run made with
  ``rerun_diagnosis.py --no-variation`` has none: say with ``--skip-variation`` that you
  compare without them, and the report then says that the nuclei were not compared);
* every compared value is identical.

``--strata`` restricts the comparison to the strata that you name (the others are then
reported as not compared, in the result line). The time taken is shown and not compared.

The exit status is 0 when the verdict is "identical to the study" and 1 in every other case
(a value that differs, or a comparison that could not be completed, or one made on other
input files); the result line says which.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import KEY, PLANE_EN, PLANES, REFERENCE, STRATA

import pyarrow.parquet as pq

from greek_corpus_pipeline import rule_catalog as rc

#: The numbers of Table S11.1 that are compared one by one (``nuclei`` is treated apart: it
#: is empty when the variation family was not run).
NUMERIC = ["imported_records", "active_records", "words", "analyzable_links",
           "analyzable_sentences", "findings", "active_checks", "nuclei"]

#: The columns that a row of ``rerun_summary.csv`` must have for the comparison to be made.
REQUIRED_COLUMNS = NUMERIC + ["stratum", "findings_fingerprint", "input_fingerprint",
                              "input_matches_study"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_keys(path: Path) -> Counter:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != KEY:
            raise SystemExit(f"{path}: unexpected header {header}")
        return Counter(tuple(row) for row in reader)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--strata", nargs="+", choices=STRATA,
                        help="compare only these strata (the default is all six: a stratum that is "
                             "missing from the re-run is then a failure)")
    parser.add_argument("--skip-variation", action="store_true",
                        help="compare without the nuclei of the n-gram variation (for a re-run made "
                             "with --no-variation); the result line says that they were not compared")
    arguments = parser.parse_args(argv)

    reproduction = arguments.workspace / "reproduction"
    wanted = list(arguments.strata) if arguments.strata else list(STRATA)
    explicit_subset = bool(arguments.strata) and set(wanted) != set(STRATA)

    lines: list[str] = []
    different: list[str] = []        # values that differ from the study
    problems: list[str] = []         # reasons why the comparison cannot confirm the study

    def line(text: str = "") -> None:
        lines.append(text)
        print(text)

    def compare(stratum: str, name: str, expected: str, got: str) -> None:
        same = expected == got
        if not same:
            different.append(f"{stratum}: {name}")
        line(f"  {name:<26} {expected:>14} {got:>14}   {'identical' if same else 'DIFFERENT'}")

    other_inputs: set[str] = set()   # strata whose input files are not those of the study

    def finish(coverage: list[str], compared: list[str] | None = None) -> int:
        for text in coverage:
            line(text)
        # on input files that are not the study's a difference is expected and contradicts nothing
        contradicting = [d for d in different if d.split(":")[0] not in other_inputs]
        expected = [d for d in different if d.split(":")[0] in other_inputs]
        if contradicting:
            result = (f"RESULT: {len(contradicting)} value(s) differ from the study: " + "; ".join(contradicting))
            if problems:
                result += " | and the comparison is not complete: " + "; ".join(problems)
        elif problems:
            result = "RESULT: NOT CONFIRMED, " + "; ".join(problems)
            if expected:
                result += (f" | {len(expected)} value(s) differ on the input files that are not the study's, "
                           "as expected")
        else:
            result = "RESULT: every compared value is identical to the study"
            if compared is not None and len(compared) < len(STRATA):
                result += (f" (only {len(compared)} of the {len(STRATA)} strata, chosen with --strata: "
                           + ", ".join(compared) + ")")
            if arguments.skip_variation:
                result += " (the nuclei were not compared: --skip-variation)"
        line(result)
        if reproduction.is_dir():
            (reproduction / "comparison.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0 if not (different or problems) else 1

    summary_file = reproduction / "rerun_summary.csv"
    if not summary_file.is_file():
        problems.append(f"{summary_file} does not exist: run rerun_diagnosis.py first")
        return finish(["COVERAGE: nothing was compared"])

    summary = read_rows(summary_file)
    columns = set(summary[0].keys()) if summary else set()
    if summary and not set(REQUIRED_COLUMNS) <= columns:
        problems.append("rerun_summary.csv lacks the column(s) " + ", ".join(sorted(set(REQUIRED_COLUMNS) - columns)))
        return finish(["COVERAGE: nothing was compared"])
    by_stratum: dict[str, list[dict[str, str]]] = {}
    for row in summary:
        by_stratum.setdefault(row["stratum"], []).append(row)
    for name in by_stratum:
        if name not in STRATA:
            problems.append(f"rerun_summary.csv has a row for '{name}', which is not a stratum of the study")
    if not summary:
        problems.append("rerun_summary.csv has no row at all")

    reference = {r["stratum"]: r for r in read_rows(REFERENCE / "table_S11_1_units_and_findings.csv")}
    study_inputs = {r["stratum"]: r["input_fingerprint"] for r in read_rows(REFERENCE / "inputs.csv")}
    overview = {r["rule_id"]: r for r in read_rows(REFERENCE / "checks_overview.csv")}
    nuclei_by_level = {r["stratum"]: r for r in read_rows(REFERENCE / "table_S8_1_nuclei_by_level.csv")}
    split_of_study = {r["stratum"]: r for r in read_rows(REFERENCE / "findings_by_class.csv")}

    compared: list[str] = []
    without_nuclei: list[str] = []
    for stratum in wanted:
        line(f"== {stratum} ==")
        rows = by_stratum.get(stratum, [])
        if not rows:
            problems.append(f"{stratum} is not in the re-run")
            line("  NOT COMPARED: no row of this stratum in rerun_summary.csv")
            line()
            continue
        if len(rows) > 1:
            problems.append(f"{stratum} has {len(rows)} rows in rerun_summary.csv")
            line(f"  NOT COMPARED: {len(rows)} rows of this stratum in rerun_summary.csv "
                 "(which one is the re-run?)")
            line()
            continue
        ref, got = reference[stratum], rows[0]
        compared.append(stratum)
        line(f"  {'':<26} {'study':>14} {'re-run':>14}")
        if got["input_matches_study"].strip().lower() != "true" or got["input_fingerprint"] != study_inputs[stratum]:
            other_inputs.add(stratum)
            problems.append(f"{stratum}: the input files are not those of the study (input fingerprint "
                            f"{got['input_fingerprint'] or '?'}, the study's is {study_inputs[stratum]})")
            line("  NOTE: the input files are not those of the study (input fingerprint "
                 f"{got['input_fingerprint'] or '?'}, the study's is {study_inputs[stratum]}): a difference "
                 "is expected here, and identical values would not confirm the study either.")
        for name in NUMERIC:
            if name == "nuclei":
                if arguments.skip_variation:
                    line(f"  {name:<26} {ref[name]:>14} {'not compared':>14}   (--skip-variation)")
                elif not got[name]:
                    without_nuclei.append(stratum)
                    line(f"  {name:<26} {ref[name]:>14} {'not run':>14}   NOT COMPARED: the variation family was "
                         "not run (--skip-variation compares without it)")
                else:
                    compare(stratum, name, ref[name], got[name])
                continue
            compare(stratum, name, ref[name], got[name])
        if not arguments.skip_variation and got["nuclei"]:
            for plane in PLANES:
                table = arguments.workspace / "runs" / f"rerun-{stratum}" / f"variation_{plane}.parquet"
                count = pq.ParquetFile(table).metadata.num_rows if table.is_file() else "absent"
                compare(stratum, f"nuclei, {PLANE_EN[plane]}", nuclei_by_level[stratum][PLANE_EN[plane]], str(count))
        compare(stratum, "findings fingerprint", ref["findings_fingerprint"], got["findings_fingerprint"])

        keys_file = reproduction / "finding_keys" / f"{stratum}.csv.gz"
        if not keys_file.is_file():
            problems.append(f"{stratum}: {keys_file.name} is missing from finding_keys/, so the findings "
                            "themselves cannot be compared")
            line(f"  NOT COMPARED: the findings themselves ({keys_file} does not exist)")
            line()
            continue
        expected_keys = read_keys(REFERENCE / "finding_keys" / f"{stratum}.csv.gz")
        got_keys = read_keys(keys_file)
        only_study = sum((expected_keys - got_keys).values())
        only_rerun = sum((got_keys - expected_keys).values())
        compare(stratum, "findings only in the study", "0", str(only_study))
        compare(stratum, "findings only in the re-run", "0", str(only_rerun))

        per_check_got = Counter(rule_id for rule_id, *_ in got_keys.elements())
        per_check_ref = {rid: int(row[stratum]) for rid, row in overview.items() if int(row[stratum])}
        wrong = sorted(rid for rid in set(per_check_ref) | set(per_check_got)
                       if per_check_ref.get(rid, 0) != per_check_got.get(rid, 0))
        compare(stratum, "checks with another count", "0", str(len(wrong)))
        for rid in wrong[:10]:
            line(f"      {rid}: study {per_check_ref.get(rid, 0)}, re-run {per_check_got.get(rid, 0)}")

        classes = Counter()
        for rid, n in per_check_got.items():
            classes[rc.rule_class(rid)] += n
        expected_split = split_of_study[stratum]
        compare(stratum, "violations", expected_split["violations"], str(classes["violazione"]))
        compare(stratum, "cases to verify", expected_split["to_verify"], str(classes["verifica"]))
        compare(stratum, "variants", expected_split["variants"], str(classes["variante"]))
        line(f"  (time taken: {got.get('seconds', '?')} s; not compared)")
        line()

    if without_nuclei:
        problems.append("the variation family was not run in " + ", ".join(without_nuclei)
                        + ", so the nuclei cannot be compared there (use --skip-variation to compare without them)")
    left_out = [s for s in STRATA if s not in compared]
    coverage = ["COVERAGE",
                f"  strata compared ({len(compared)} of {len(STRATA)}): {', '.join(compared) or 'none'}"]
    if left_out:
        reason = "chosen with --strata" if explicit_subset else "missing or unusable in the re-run"
        coverage.append(f"  strata not compared ({reason}): {', '.join(left_out)}")
    if arguments.skip_variation:
        coverage.append("  not compared (--skip-variation): the nuclei of Table S11.1 and of the five levels "
                        "of Table S8.1")
    elif without_nuclei:
        coverage.append("  not compared (the variation family was not run): the nuclei of Table S11.1 and of "
                        "the five levels of Table S8.1, in " + ", ".join(without_nuclei))
    with_nuclei = [] if arguments.skip_variation else [s for s in compared if s not in without_nuclei]
    coverage.append("  compared in each of the strata compared: the numbers of Table S11.1 other than the nuclei, "
                    "the findings fingerprint, the four-field key of every finding, the findings of each of the "
                    "77 checks, the split into violations, cases to verify and variants")
    if with_nuclei:
        coverage.append("  also compared, in " + ", ".join(with_nuclei) + ": the nuclei and their five levels")
    return finish(coverage, compared)


if __name__ == "__main__":
    sys.exit(main())
