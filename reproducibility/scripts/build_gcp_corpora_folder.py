#!/usr/bin/env python
"""Build the folder that the test suite reads from ``GCP_CORPORA``, from a re-run.

Some tests of the suite measure the program on the six corpora of the study. The corpora are
third-party resources and are not distributed with the package, so those tests are skipped
unless the environment variable ``GCP_CORPORA`` names a folder with this layout:

    <GCP_CORPORA>/runs/run-<stratum>/tokens.parquet     the prepared token table of the stratum
    <GCP_CORPORA>/giro/findings-<stratum>.parquet       the findings of the detection step

with ``<stratum>`` one of gorman, pedalion, glaux_auto, glaux_man, glaux_conf_auto, glaux_conf_man.

The token tables are those that ``rerun_diagnosis.py`` has prepared. The findings in ``giro/``
are the raw output of the detection step, *before* the last step of ``run_detection`` (the
function ``proposte.allinea_proposte``), which removes the suggested corrections of the checks
whose treatment is manual and restores only the verified repairs. The tests that look at what
the checks themselves produce (for instance that ``lemma-rare-for-form`` names the majority
lemma) need that raw output; the file ``findings.parquet`` of a run is the aligned one. The
family of n-gram variation is not run here: it does not enter these tests.

usage:
    python build_gcp_corpora_folder.py --workspace W --output C [--strata gorman pedalion ...]

W is the workspace given to ``rerun_diagnosis.py``; C is the folder to create. Then:

    set GCP_CORPORA=C            (Windows)       export GCP_CORPORA=C        (Linux, macOS)
    python -m pytest
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA

import pandas as pd

FAMILIES = {"morphology": True, "lemma": True, "syntax": True,
            "text": True, "agreement": True, "variation": False}
FILTERS = {"exclude_placeholders": True, "exclude_non_greek": False,
           "exclude_punctuation": False, "relation_expectation": "corpus"}


def raw_findings(tokens_file: Path, stratum: str) -> pd.DataFrame:
    """The findings of the detection step for a prepared token table, without the alignment."""
    import greek_corpus_pipeline.proposte as proposte
    from gui_qt.workers import run_detection
    from greek_corpus_pipeline.storage import save_metadata

    original = proposte.allinea_proposte
    proposte.allinea_proposte = lambda findings, tokens=None, corpus="": findings
    try:
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            run_id = f"raw-{stratum}"
            (workspace / "runs" / run_id).mkdir(parents=True)
            shutil.copy2(tokens_file, workspace / "runs" / run_id / "tokens.parquet")
            save_metadata(workspace, run_id, {"run_id": run_id, "corpus_name": stratum,
                                              "source_mode": "folder", "source_value": "-", "stages": {}})
            run_detection(workspace, run_id, FAMILIES, FILTERS, lambda *a: None, lambda m: None)
            return pd.read_parquet(workspace / "runs" / run_id / "findings.parquet")
    finally:
        proposte.allinea_proposte = original


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strata", nargs="+", choices=STRATA, default=list(STRATA))
    arguments = parser.parse_args(argv)

    for stratum in arguments.strata:
        tokens_file = arguments.workspace / "runs" / f"rerun-{stratum}" / "tokens.parquet"
        if not tokens_file.is_file():
            parser.error(f"{tokens_file} does not exist: run rerun_diagnosis.py first")
        target = arguments.output / "runs" / f"run-{stratum}"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tokens_file, target / "tokens.parquet")
        (arguments.output / "giro").mkdir(parents=True, exist_ok=True)
        found = raw_findings(tokens_file, stratum)
        found.to_parquet(arguments.output / "giro" / f"findings-{stratum}.parquet", index=False)
        print(f"{stratum}: {len(found)} raw findings", flush=True)
    print(f"\nGCP_CORPORA={arguments.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
