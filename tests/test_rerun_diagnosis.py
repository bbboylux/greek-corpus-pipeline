# -*- coding: utf-8 -*-
"""The script that repeats the diagnosis of a stratum (``reproducibility/scripts/rerun_diagnosis.py``).

The script reads the folder of the corpus, fingerprints its XML files with ``input_fingerprint.py``, runs
the preparation and the diagnosis of the program and writes the summary that ``compare_with_reference.py``
reads. The script calls the ``scan`` function of the fingerprint script and relies on what it returns; the real
run needs the corpora, which the suite does not have. The test below runs the script from the beginning to the
end on a corpus of two sentences, which has no reason to match the study, and checks that it says so.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from conftest import XML

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "rerun_diagnosis.py"

# pandas 2.2.0 (the lowest version the package admits) warns, when it reads a parquet file written with pyarrow 14, about a
# call that pyarrow itself makes ("Passing a BlockManager to DataFrame is deprecated"): it is the libraries' business, not
# the program's, and later versions of pandas do not say it. Only that message is ignored.
pytestmark = pytest.mark.filterwarnings("ignore:Passing a BlockManager to DataFrame:DeprecationWarning")


def load_script():
    spec = importlib.util.spec_from_file_location("rerun_diagnosis_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_diagnosis_runs_on_a_small_corpus_and_says_that_it_is_not_the_study(tmp_path, capsys):
    corpus = tmp_path / "xml"
    corpus.mkdir()
    (corpus / "doc.xml").write_text(XML, encoding="utf-8")
    workspace = tmp_path / "workspace"
    script = load_script()

    status = script.main(["--gorman", str(corpus), "--workspace", str(workspace), "--strata", "gorman", "--no-variation"])

    assert status == 0
    said = capsys.readouterr().out
    assert "input gorman: 1 XML files" in said and "DIFFERENT from the study" in said, said
    with (workspace / "reproduction" / "rerun_summary.csv").open(encoding="utf-8", newline="") as handle:
        (row,) = list(csv.DictReader(handle))
    assert row["stratum"] == "gorman"
    assert row["input_files"] == "1" and row["input_matches_study"] == "False"
    assert int(row["imported_records"]) == 9 and int(row["findings"]) > 0
    assert (workspace / "reproduction" / "finding_keys" / "gorman.csv.gz").is_file()
    # the message says how to compare a re-run that has one stratum and no variation
    assert "compare_with_reference.py" in said and "--strata gorman --skip-variation" in said, said


def test_the_summary_that_it_writes_is_the_one_that_the_comparison_reads(tmp_path, capsys):
    """Producer and consumer agree on the columns, and a corpus that is not the study's is "not confirmed"."""
    corpus = tmp_path / "xml"
    corpus.mkdir()
    (corpus / "doc.xml").write_text(XML, encoding="utf-8")
    workspace = tmp_path / "workspace"
    load_script().main(["--gorman", str(corpus), "--workspace", str(workspace), "--strata", "gorman", "--no-variation"])
    capsys.readouterr()

    spec = importlib.util.spec_from_file_location("compare_with_reference_for_the_chain",
                                                  ROOT / "reproducibility" / "scripts" / "compare_with_reference.py")
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    status = comparison.main([str(workspace), "--strata", "gorman", "--skip-variation"])
    out = capsys.readouterr().out

    assert status == 1, out
    assert "lacks the column" not in out
    assert "RESULT: NOT CONFIRMED, gorman: the input files are not those of the study" in out
