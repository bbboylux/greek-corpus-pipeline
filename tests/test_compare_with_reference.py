# -*- coding: utf-8 -*-
"""The script that compares a re-run with the reference values of the study
(``reproducibility/scripts/compare_with_reference.py``).

The script is what lets a reviewer say "this re-run reproduces the study", so its verdict must not be
given on less than the study: an empty summary, a stratum missing from the re-run, a stratum that appears
twice, input files that are not those of the study, findings that cannot be compared and a re-run without
the n-gram variation must all prevent it. Here the re-runs are built from the reference tables that the
package itself distributes (so that the "identical" case is identical by construction), and then spoilt one
way at a time. The small strata are used wherever the case does not need all six, so that the module is fast.
"""
from __future__ import annotations

import csv
import gzip
import importlib.util
import shutil
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "compare_with_reference.py"
REFERENCE = ROOT / "reproducibility" / "reference"

STRATA = ("gorman", "pedalion", "glaux_auto", "glaux_man", "glaux_conf_auto", "glaux_conf_man")
SMALL = ("glaux_man", "glaux_conf_man")          # the two smallest strata
PLANES = ("morfologia", "posizioni", "contesto", "dipendenze", "lemmi")
PLANE_EN = ("morphology", "tag_positions", "context", "dependencies", "lemmas")
COLUMNS = ["stratum", "label", "imported_records", "active_records", "words", "analyzable_links",
           "analyzable_sentences", "findings", "active_checks", "nuclei", "findings_fingerprint",
           "input_files", "input_bytes", "input_fingerprint", "input_matches_study", "seconds"]

pytestmark = pytest.mark.filterwarnings("ignore:Passing a BlockManager to DataFrame:DeprecationWarning")


def rows_of(name: str) -> dict[str, dict[str, str]]:
    with (REFERENCE / name).open(encoding="utf-8", newline="") as handle:
        return {r["stratum"]: r for r in csv.DictReader(handle)}


@pytest.fixture(scope="module")
def tool():
    pytest.importorskip("pyarrow")
    spec = importlib.util.spec_from_file_location("compare_with_reference_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summary_rows(strata) -> list[dict[str, str]]:
    units, inputs = rows_of("table_S11_1_units_and_findings.csv"), rows_of("inputs.csv")
    rows = []
    for stratum in strata:
        row = {k: units[stratum][k] for k in units[stratum]}
        row.update(input_files=inputs[stratum]["xml_files"], input_bytes=inputs[stratum]["bytes"],
                   input_fingerprint=inputs[stratum]["input_fingerprint"],
                   input_matches_study="True", seconds="1")
        rows.append({c: row[c] for c in COLUMNS})
    return rows


def write_summary(workspace: Path, rows: list[dict[str, str]]) -> None:
    (workspace / "reproduction").mkdir(parents=True, exist_ok=True)
    with (workspace / "reproduction" / "rerun_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_rerun(tmp_path: Path, strata=STRATA) -> Path:
    """A re-run that reproduces the study exactly: the numbers, the keys and the nuclei of the reference."""
    workspace = tmp_path / "workspace"
    write_summary(workspace, summary_rows(strata))
    (workspace / "reproduction" / "finding_keys").mkdir(parents=True, exist_ok=True)
    levels = rows_of("table_S8_1_nuclei_by_level.csv")
    for stratum in strata:
        shutil.copy(REFERENCE / "finding_keys" / f"{stratum}.csv.gz",
                    workspace / "reproduction" / "finding_keys" / f"{stratum}.csv.gz")
        run = workspace / "runs" / f"rerun-{stratum}"
        run.mkdir(parents=True, exist_ok=True)
        for plane, english in zip(PLANES, PLANE_EN):
            pd.DataFrame({"id": range(int(levels[stratum][english]))}).to_parquet(run / f"variation_{plane}.parquet")
    return workspace


def run(tool, capsys, workspace: Path, *arguments) -> tuple[int, str]:
    status = tool.main([str(workspace), *[str(a) for a in arguments]])
    return status, capsys.readouterr().out


def result_line(out: str) -> str:
    return next(line for line in out.splitlines() if line.startswith("RESULT"))


# -- the case that must pass -------------------------------------------------------------------------------

def test_a_complete_rerun_that_reproduces_the_study_is_confirmed(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path)
    status, out = run(tool, capsys, workspace)
    assert status == 0, out
    assert result_line(out) == "RESULT: every compared value is identical to the study"
    assert "strata compared (6 of 6)" in out
    assert "DIFFERENT" not in out and "NOT COMPARED" not in out
    assert (workspace / "reproduction" / "comparison.txt").read_text(encoding="utf-8").count("identical") > 50


# -- the cases that must not pass --------------------------------------------------------------------------

def test_an_empty_summary_confirms_nothing(tool, tmp_path, capsys):
    workspace = tmp_path / "workspace"
    write_summary(workspace, [])
    status, out = run(tool, capsys, workspace)
    assert status == 1, out
    assert result_line(out).startswith("RESULT: NOT CONFIRMED")
    assert "no row at all" in out and "strata compared (0 of 6): none" in out
    assert "every compared value is identical" not in out


def test_no_summary_at_all_is_a_failure_not_a_crash(tool, tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    status, out = run(tool, capsys, workspace)
    assert status == 1
    assert "rerun_summary.csv" in out and "NOT CONFIRMED" in out


def test_a_stratum_that_is_not_in_the_rerun_is_a_failure_by_default(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    status, out = run(tool, capsys, workspace)
    assert status == 1, out
    for stratum in ("gorman", "pedalion", "glaux_auto", "glaux_conf_auto"):
        assert f"{stratum} is not in the re-run" in out
    assert "strata compared (2 of 6): glaux_man, glaux_conf_man" in out
    assert "missing or unusable in the re-run" in out
    assert "every compared value is identical" not in out


def test_a_subset_is_compared_only_when_it_is_asked_for_and_the_result_says_so(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 0, out
    assert result_line(out) == ("RESULT: every compared value is identical to the study "
                                "(only 2 of the 6 strata, chosen with --strata: glaux_man, glaux_conf_man)")
    assert "strata not compared (chosen with --strata): gorman, pedalion, glaux_auto, glaux_conf_auto" in out
    # a stratum that is asked for and is not there is still a failure
    status, out = run(tool, capsys, workspace, "--strata", "glaux_man", "glaux_auto")
    assert status == 1 and "glaux_auto is not in the re-run" in out


def test_two_rows_for_one_stratum_are_a_failure(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    rows = summary_rows(SMALL) + summary_rows(SMALL[:1])
    write_summary(workspace, rows)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "glaux_man has 2 rows in rerun_summary.csv" in out
    assert "strata compared (1 of 2)" not in out and "NOT CONFIRMED" in result_line(out)


@pytest.mark.parametrize("flag, fingerprint", [("False", None), ("True", "0123456789abcdef"), ("", None)])
def test_input_files_that_are_not_those_of_the_study_prevent_the_verdict(tool, tmp_path, capsys, flag, fingerprint):
    """Identical values on other input files do not confirm the study, and a hand-written flag is not trusted."""
    workspace = make_rerun(tmp_path, SMALL)
    rows = summary_rows(SMALL)
    rows[0]["input_matches_study"] = flag
    if fingerprint:
        rows[0]["input_fingerprint"] = fingerprint
    write_summary(workspace, rows)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "NOTE: the input files are not those of the study" in out
    assert result_line(out).startswith("RESULT: NOT CONFIRMED, glaux_man: the input files are not those of the study")


def test_a_value_that_differs_is_reported_and_fails(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    rows = summary_rows(SMALL)
    rows[1]["findings"] = str(int(rows[1]["findings"]) + 1)
    write_summary(workspace, rows)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "RESULT: 1 value(s) differ from the study: glaux_conf_man: findings" in out
    assert "DIFFERENT" in out


def test_a_finding_that_is_not_the_one_of_the_study_is_a_difference(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    keys = workspace / "reproduction" / "finding_keys" / "glaux_man.csv.gz"
    with gzip.open(keys, "rt", encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines()
    lines[1] = lines[1].replace(lines[1].split(",")[0], "slot-missing", 1)        # another check for the first finding
    with gzip.open(keys, "wt", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "findings only in the re-run" in out and "checks with another count" in out
    assert "differ from the study" in result_line(out)


def test_the_keys_of_the_findings_must_be_there_to_be_compared(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    (workspace / "reproduction" / "finding_keys" / "glaux_man.csv.gz").unlink()
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "glaux_man: glaux_man.csv.gz is missing from finding_keys/" in out
    assert "NOT COMPARED: the findings themselves" in out


def test_a_rerun_without_the_variation_family_is_compared_only_when_that_is_said(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    rows = summary_rows(SMALL)
    for row in rows:
        row["nuclei"] = ""                                   # what rerun_diagnosis.py --no-variation writes
    write_summary(workspace, rows)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1, out
    assert "the variation family was not run in glaux_man, glaux_conf_man" in out
    assert "--skip-variation" in result_line(out)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL, "--skip-variation")
    assert status == 0, out
    assert result_line(out).endswith("(the nuclei were not compared: --skip-variation)")
    assert "not compared (--skip-variation): the nuclei of Table S11.1 and of the five levels of Table S8.1" in out
    # the nuclei that are there are not compared either, and the report says that they were not
    workspace = make_rerun(tmp_path / "again", SMALL)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL, "--skip-variation")
    assert status == 0 and "nuclei                               " in out and "(--skip-variation)" in out
    assert "nuclei, morphology" not in out


def test_a_row_for_something_that_is_not_a_stratum_is_a_failure(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    rows = summary_rows(SMALL)
    rows.append(dict(rows[0], stratum="glaux_third"))
    write_summary(workspace, rows)
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1 and "'glaux_third', which is not a stratum of the study" in out


def test_a_summary_without_the_columns_that_the_comparison_needs_is_a_failure(tool, tmp_path, capsys):
    workspace = make_rerun(tmp_path, SMALL)
    path = workspace / "reproduction" / "rerun_summary.csv"
    frame = pd.read_csv(path, dtype=str, keep_default_na=False).drop(columns=["findings_fingerprint"])
    frame.to_csv(path, index=False, lineterminator="\n")
    status, out = run(tool, capsys, workspace, "--strata", *SMALL)
    assert status == 1 and "lacks the column(s) findings_fingerprint" in out
