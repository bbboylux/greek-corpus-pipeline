# -*- coding: utf-8 -*-
"""The script that compares two run folders cell by cell (``reproducibility/scripts/compare_run_folders.py``).

Supplement S11.2 says that a repetition of the runs reproduces the tables "cell by cell"; the script is what
lets a reviewer test that statement, so it must not call two different tables identical and must not call
two identical ones different. These tests build small run folders of their own and pin the cases that a
comparison of this kind easily gets wrong:

* a missing value against the number 5 is a difference even when the column has a nullable type
  (``Int64``, ``string``), where ``NA == 5`` is itself missing and a count of differences would drop it;
* the two label columns (the direction of an arc, the name of the corpus) are accepted as different only
  in their wording: a left that became a right is a difference, and so is a corpus label that is missing,
  empty or blank against one that has a name;
* a table that is in only one of the two folders is a failure, not a table left out;
* the tables ``tokens`` and ``findings`` are required: folders without them are not run folders;
* the model tables that no run had are named as not compared, so that "all identical" is not read as a
  statement about the comparison with the models.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "compare_run_folders.py"

LEFT, RIGHT = "head to the left", "head to the right"

# pandas 2.2.0 (the lowest version the package admits) warns, when it reads a parquet file written with pyarrow 14, about a
# call that pyarrow itself makes ("Passing a BlockManager to DataFrame is deprecated"): it is the libraries' business, not
# the program's, and later versions of pandas do not say it. Only that message is ignored.
pytestmark = pytest.mark.filterwarnings("ignore:Passing a BlockManager to DataFrame:DeprecationWarning")

CORE = ("tokens", "arcs", "findings", "variation_morfologia", "variation_posizioni", "variation_contesto",
        "variation_dipendenze", "variation_lemmi", "spelling_variation")
MODELS = ("stanza_comparison", "udpipe_comparison")


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("compare_run_folders_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_run(folder: Path, *, directions=(LEFT, RIGHT, LEFT), corpus=("c", "c", "c"),
              head=(1, 2, 3), models=False, texts=("a", "b", "c")) -> Path:
    """A run folder with the tables a run writes, each as small as can be."""
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "token_id": pd.array([1, 2, 3], dtype="Int64"),
        "corpus": list(corpus),
        "head": pd.array(list(head), dtype="Int64"),
        "form": pd.array(list(texts), dtype="string"),
    }).to_parquet(folder / "tokens.parquet")
    pd.DataFrame({"arc_id": [1, 2, 3], "direction": list(directions)}).to_parquet(folder / "arcs.parquet")
    for name in CORE[2:]:
        pd.DataFrame({"id": [1, 2, 3], "value": [0.5, 1.5, 2.5]}).to_parquet(folder / f"{name}.parquet")
    if models:
        for name in MODELS:
            pd.DataFrame({"id": [1, 2], "model_value": [7, 8]}).to_parquet(folder / f"{name}.parquet")
    return folder


def run(tool, capsys, *arguments) -> tuple[int, str]:
    status = tool.main([str(a) for a in arguments])
    return status, capsys.readouterr().out


# -- the cells ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("first, second, expected", [
    (pd.array([1, None, 3], dtype="Int64"), pd.array([1, 5, 3], dtype="Int64"), [False, True, False]),
    (pd.array([1, None, 3], dtype="Int64"), pd.array([1, None, 3], dtype="Int64"), [False, False, False]),
    (pd.array(["a", None, "c"], dtype="string"), pd.array(["a", "", "c"], dtype="string"), [False, True, False]),
    (pd.array(["a", None], dtype="string"), pd.array([None, None], dtype="string"), [True, False]),
    (pd.array([True, None], dtype="boolean"), pd.array([True, False], dtype="boolean"), [False, True]),
    (np.array([1.0, np.nan, 3.0]), np.array([1.0, 2.0, 3.0]), [False, True, False]),
    (np.array([1.0, np.nan]), np.array([1.0, np.nan]), [False, False]),
    (np.array([1, 2, 3]), np.array([1, 5, 3]), [False, True, False]),
])
def test_a_missing_value_equals_a_missing_value_and_nothing_else(tool, first, second, expected):
    result = tool.differing_cells(pd.Series(first), pd.Series(second))
    assert list(result) == expected


# -- the verdict on two folders -----------------------------------------------------------------------

def test_two_identical_runs_are_identical(tool, tmp_path, capsys):
    a, b = write_run(tmp_path / "a", models=True), write_run(tmp_path / "b", models=True)
    status, out = run(tool, capsys, a, b)
    assert status == 0, out
    assert "RESULT: 11 tables compared, all identical" in out


@pytest.mark.parametrize("flags", [(), ("--exact",)])
def test_a_missing_value_against_a_number_is_a_difference_in_either_mode(tool, tmp_path, capsys, flags):
    a = write_run(tmp_path / "a", head=(1, None, 3))
    b = write_run(tmp_path / "b", head=(1, 5, 3))
    status, out = run(tool, capsys, a, b, *flags)
    assert status == 1, out
    assert "head: 1 cells" in out
    assert "RESULT: 9 tables compared; FAILED: 1 not identical" in out


def test_a_missing_text_against_an_empty_text_is_a_difference(tool, tmp_path, capsys):
    a = write_run(tmp_path / "a", texts=("a", None, "c"))
    b = write_run(tmp_path / "b", texts=("a", "", "c"))
    status, out = run(tool, capsys, a, b)
    assert status == 1 and "form: 1 cells" in out


def test_a_new_wording_of_the_direction_is_accepted_and_said(tool, tmp_path, capsys):
    study = write_run(tmp_path / "study", directions=("testa a sinistra", "testa a destra", "testa a sinistra"))
    package = write_run(tmp_path / "package", directions=(LEFT, RIGHT, LEFT))
    status, out = run(tool, capsys, study, package)
    assert status == 0, out
    assert "the wording of a label differs, accepted: direction" in out
    assert "RESULT: 9 tables compared, all identical" in out


def test_a_left_that_became_a_right_is_a_difference(tool, tmp_path, capsys):
    """A table in which every direction is the opposite one must not pass."""
    study = write_run(tmp_path / "study", directions=("testa a sinistra", "testa a destra", "testa a sinistra"))
    swapped = write_run(tmp_path / "swapped", directions=(RIGHT, LEFT, RIGHT))
    status, out = run(tool, capsys, study, swapped)
    assert status == 1, out
    assert "direction: 3 cells" in out
    # one cell only
    one = write_run(tmp_path / "one", directions=(LEFT, RIGHT, RIGHT))
    status, out = run(tool, capsys, study, one)
    assert status == 1 and "direction: 1 cells" in out


def test_a_wording_that_is_not_one_of_the_four_must_be_the_same(tool, tmp_path, capsys):
    a = write_run(tmp_path / "a", directions=(LEFT, RIGHT, "testa a sinistra"))
    b = write_run(tmp_path / "b", directions=(LEFT, RIGHT, "toward the left"))
    status, out = run(tool, capsys, a, b)
    assert status == 1 and "direction: 1 cells" in out
    c = write_run(tmp_path / "c", directions=(LEFT, RIGHT, "toward the left"))
    status, out = run(tool, capsys, b, c)
    assert status == 0, out


def test_exact_makes_the_wording_of_a_label_a_difference(tool, tmp_path, capsys):
    study = write_run(tmp_path / "study", directions=("testa a sinistra", "testa a destra", "testa a sinistra"))
    package = write_run(tmp_path / "package", directions=(LEFT, RIGHT, LEFT))
    status, out = run(tool, capsys, study, package, "--exact")
    assert status == 1 and "direction: 3 cells" in out


def test_the_name_of_the_corpus_may_differ_only_when_each_table_holds_one_name(tool, tmp_path, capsys):
    a = write_run(tmp_path / "a", corpus=("glaux_campione",) * 3)
    b = write_run(tmp_path / "b", corpus=("glaux_main_automatic",) * 3)
    status, out = run(tool, capsys, a, b)
    assert status == 0 and "corpus ('glaux_campione' = 'glaux_main_automatic')" in out
    status, out = run(tool, capsys, a, b, "--exact")
    assert status == 1 and "corpus: 3 cells" in out
    # several names in a table: they must be the same, and they are compared row by row
    c = write_run(tmp_path / "c", corpus=("x", "y", "x"))
    d = write_run(tmp_path / "d", corpus=("x", "z", "x"))
    status, out = run(tool, capsys, c, d)
    assert status == 1 and "corpus: 1 cells" in out
    # one name against several is not "a label": a table that has two corpora is not the same as one that has one
    status, out = run(tool, capsys, a, c)
    assert status == 1 and "corpus: " in out


def test_the_descriptive_texts_of_a_finding_are_not_labels(tool, tmp_path, capsys):
    a, b = write_run(tmp_path / "a"), write_run(tmp_path / "b")
    pd.DataFrame({"anomaly_name": ["tag mancante"] * 3}).to_parquet(a / "findings.parquet")
    pd.DataFrame({"anomaly_name": ["missing tag"] * 3}).to_parquet(b / "findings.parquet")
    status, out = run(tool, capsys, a, b)
    assert status == 1 and "anomaly_name: 3 cells" in out


def test_other_differences_in_shape_and_order_are_named(tool, tmp_path, capsys):
    a, b = write_run(tmp_path / "a"), write_run(tmp_path / "b")
    pd.DataFrame({"id": [1, 2, 3]}).to_parquet(a / "variation_lemmi.parquet")
    pd.DataFrame({"id": [1, 2]}).to_parquet(b / "variation_lemmi.parquet")
    pd.DataFrame({"id": [1, 2, 3], "x": [1, 2, 3]}).to_parquet(a / "variation_contesto.parquet")
    pd.DataFrame({"id": [1, 2, 3], "y": [1, 2, 3]}).to_parquet(b / "variation_contesto.parquet")
    pd.DataFrame({"id": [1, 2, 3]}).to_parquet(a / "spelling_variation.parquet")
    pd.DataFrame({"id": [3, 2, 1]}).to_parquet(b / "spelling_variation.parquet")
    status, out = run(tool, capsys, a, b)
    assert status == 1
    assert "DIFFERENT number of rows (3 against 2)" in out
    assert "DIFFERENT columns (only in the first: ['x']; only in the second: ['y'])" in out
    assert "DIFFERENT only in the order of the rows" in out
    assert "FAILED: 3 not identical" in out


# -- the tables that are not in both folders -----------------------------------------------------------

def test_a_model_table_in_only_one_folder_is_a_failure(tool, tmp_path, capsys):
    """Skipping it would leave the statement of S11.2 about the model tables untested, and the result would pass."""
    a, b = write_run(tmp_path / "a", models=True), write_run(tmp_path / "b", models=False)
    status, out = run(tool, capsys, a, b)
    assert status == 1, out
    assert "stanza_comparison" in out and "MISSING, only in the first folder" in out
    assert "FAILED: 2 table(s) in only one of the two folders" in out
    status, out = run(tool, capsys, b, a)
    assert status == 1 and "only in the second folder" in out


def test_runs_without_the_models_are_compared_on_the_core_tables(tool, tmp_path, capsys):
    a, b = write_run(tmp_path / "a"), write_run(tmp_path / "b")
    status, out = run(tool, capsys, a, b)
    assert status == 0, out
    assert "in neither folder: these runs did not include the models" in out
    assert "RESULT: 9 tables compared, all identical" in out
    # the result line names what stays uncovered
    assert "NOT COMPARED, the model tables stanza_comparison, udpipe_comparison are in neither folder" in out


def test_skip_models_says_that_the_models_were_not_looked_at(tool, tmp_path, capsys):
    a, b = write_run(tmp_path / "a", models=True), write_run(tmp_path / "b", models=False)
    status, out = run(tool, capsys, a, b, "--skip-models")
    assert status == 0, out
    assert "not looked at (--skip-models)" in out
    assert "RESULT: 9 tables compared, all identical; 2 model table(s) not looked at (--skip-models)" in out


def test_a_table_in_only_one_folder_is_a_failure_and_a_table_in_neither_is_said(tool, tmp_path, capsys):
    """A run writes no table when it would be empty, so two runs may agree that a table is not there."""
    a, b = write_run(tmp_path / "a"), write_run(tmp_path / "b")
    (a / "arcs.parquet").unlink()
    status, out = run(tool, capsys, a, b)
    assert status == 1 and "MISSING, only in the second folder" in out
    assert "FAILED: 1 table(s) in only one of the two folders" in out
    (b / "arcs.parquet").unlink()
    status, out = run(tool, capsys, a, b)
    assert status == 0, out
    assert "arcs" in out and "in neither folder: not compared" in out
    assert "RESULT: 8 tables compared, all identical; 1 table(s) in neither folder: arcs" in out


def test_folders_that_have_no_table_at_all_compare_nothing(tool, tmp_path, capsys):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    status, out = run(tool, capsys, tmp_path / "a", tmp_path / "b")
    assert status == 1
    assert "nothing was compared" in out


@pytest.mark.parametrize("table", ["tokens", "findings"])
def test_tokens_and_findings_are_required_in_both_folders(tool, tmp_path, capsys, table):
    """Every run writes them: two folders that have neither are not run folders, and "all identical" would be empty."""
    a, b = write_run(tmp_path / "a"), write_run(tmp_path / "b")
    (a / f"{table}.parquet").unlink()
    (b / f"{table}.parquet").unlink()
    status, out = run(tool, capsys, a, b)
    assert status == 1, out
    assert f"{table}" in out and "MISSING from both folders" in out
    assert f"required table(s) in neither folder: {table}" in out
    assert "all identical" not in out
    # in only one of the two it is the failure that every other table has
    c = write_run(tmp_path / "c")
    (c / f"{table}.parquet").unlink()
    status, out = run(tool, capsys, c, write_run(tmp_path / "d"))
    assert status == 1 and "MISSING, only in the second folder" in out


@pytest.mark.parametrize("blank", [None, "", "   ", "\t"])
def test_a_corpus_label_that_is_missing_empty_or_blank_is_not_a_label(tool, tmp_path, capsys, blank):
    """A table with no label is not "another label": it differs from one that has a name, in either order."""
    named = write_run(tmp_path / "named", corpus=("pedalion",) * 3)
    anonymous = write_run(tmp_path / "anonymous", corpus=(blank,) * 3)
    for first, second in ((named, anonymous), (anonymous, named)):
        status, out = run(tool, capsys, first, second)
        assert status == 1, out
        assert "corpus: 3 cells" in out
        assert "accepted: corpus" not in out
    # two tables that both have no label hold the same thing in that column
    other = write_run(tmp_path / "other", corpus=(blank,) * 3)
    status, out = run(tool, capsys, anonymous, other)
    assert status == 0, out


def test_a_label_that_has_a_name_is_accepted_against_another_name_in_either_direction(tool, tmp_path, capsys):
    a = write_run(tmp_path / "a", corpus=("gorman",) * 3)
    b = write_run(tmp_path / "b", corpus=("rerun gorman",) * 3)
    for first, second in ((a, b), (b, a)):
        status, out = run(tool, capsys, first, second)
        assert status == 0 and "accepted: corpus" in out, out


@pytest.mark.parametrize("values, label", [
    (["x", "x", "x"], "x"), (["x"], "x"), ([" x "] * 2, " x "),
    ([None, None], None), (["", ""], None), (["  ", "  "], None), (["x", "y"], None), (["x", None], None),
    ([], None),
])
def test_single_label_is_one_real_text(tool, values, label):
    assert tool.single_label(pd.Series(values, dtype="string")) == label


def test_the_models_are_expected_only_on_gorman_and_pedalion(tool, tmp_path, capsys):
    """The study compared the models on those two strata: for the GLAUx strata their absence is by design."""
    study, workspace = tmp_path / "study", tmp_path / "workspace"
    for stratum, folder in (("glaux_auto", "20260909-064439-glaux-campione"), ("gorman", "20260909-053400-gorman")):
        write_run(study / folder)
        write_run(workspace / "runs" / f"rerun-{stratum}")
    status, out = run(tool, capsys, "--study-runs", study, "--workspace", workspace, "--strata", "glaux_auto")
    assert status == 0, out
    assert "the study did not compare the models on this stratum" in out
    assert "NOT COMPARED, the model tables" not in out
    status, out = run(tool, capsys, "--study-runs", study, "--workspace", workspace, "--strata", "gorman")
    assert status == 0, out
    assert "NOT COMPARED, the model tables stanza_comparison, udpipe_comparison are in neither folder" in out
    # the four GLAUx strata and the two with models together: the note is there, because of Gorman
    status, out = run(tool, capsys, "--study-runs", study, "--workspace", workspace, "--strata", "glaux_auto", "gorman")
    assert "NOT COMPARED, the model tables" in out


# -- the folders themselves ----------------------------------------------------------------------------

def test_a_run_folder_that_is_not_there_is_a_failure(tool, tmp_path, capsys):
    a = write_run(tmp_path / "a")
    status, out = run(tool, capsys, a, tmp_path / "absent")
    assert status == 1
    assert "not a folder" in out and "nothing was compared" in out


def test_the_study_runs_are_paired_with_the_reruns_by_stratum(tool, tmp_path, capsys):
    study = tmp_path / "study"
    workspace = tmp_path / "workspace"
    write_run(study / "20260909-053400-gorman")
    write_run(workspace / "runs" / "rerun-gorman")
    status, out = run(tool, capsys, "--study-runs", study, "--workspace", workspace, "--strata", "gorman")
    assert status == 0, out
    assert "== gorman ==" in out and "RESULT: 9 tables compared, all identical" in out
    # a stratum that is asked for and whose folders are not there is a failure, not a silent skip
    status, out = run(tool, capsys, "--study-runs", study, "--workspace", workspace,
                      "--strata", "gorman", "pedalion")
    assert status == 1
    assert "pedalion: NOT COMPARED, study folder not found" in out
    assert "FAILED: 1 run folder(s) not found" in out
