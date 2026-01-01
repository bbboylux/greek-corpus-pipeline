#!/usr/bin/env python
"""Re-run the diagnosis of the six strata of the study with the program of this package.

It calls the two functions that the graphical interface and the command line share
(``gui_qt.workers.prepare_corpus`` and ``gui_qt.workers.run_detection``), with the
five diagnostic families and the n-gram variation family switched on and the
default filters of the study (placeholders of elliptical nodes left out; punctuation
and non-Greek records kept), and then summarises every run in the form of Table S11.1.

The corpora are not distributed with the package (see ``ACQUISITION.md``). You
supply them:

    --gorman DIR     the folder holding the Gorman XML files (``.../public/xml``)
    --pedalion DIR   the folder holding the Pedalion XML files
    --glaux DIR      a folder (searched recursively) holding the GLAUx XML files of the
                     four samples, ``0011-004.xml`` and so on; without it the files are
                     downloaded from the GLAUx repository, whose branch moves
    --workspace DIR  where the runs are written (created if absent; use an empty one)

Before anything is run the script computes the input fingerprint of each stratum
(Table S11.2, ``input_fingerprint.py``) and says whether it is the one of the study. If it
is not, the numbers may legitimately differ, and the report says so.

usage:
    python rerun_diagnosis.py --gorman G --pedalion P --glaux X --workspace W
    python rerun_diagnosis.py ... --strata gorman pedalion        (a subset)
    python rerun_diagnosis.py ... --no-variation                   (skip the n-gram family)

A re-run of a subset, or one made with ``--no-variation``, is compared with ``compare_with_reference.py`` only
if you say so there (``--strata`` and ``--skip-variation``): by default the comparison asks for the six strata
and for the nuclei of the variation, and a re-run that lacks them is "not confirmed", not "identical".

Output, in ``W/reproduction/``: ``rerun_summary.csv`` (one row per stratum, the columns of
Table S11.1 plus the input fingerprint), ``finding_keys/<stratum>.csv.gz`` (the four-field
key of every finding) and ``log-<stratum>.txt``. Then run ``compare_with_reference.py W``.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import (CORPUS_NAMES, GLAUX_SAMPLES, KEY, LABELS, REFERENCE, STRATA,
                          summarise_run)
from input_fingerprint import fingerprint, read_csv, scan, sha256

#: The families the study switched on, and the filters it used (the defaults of the
#: graphical interface and of the command line).
FAMILIES = {"morphology": True, "lemma": True, "syntax": True,
            "text": True, "agreement": True, "variation": True}
FILTERS = {"exclude_placeholders": True, "exclude_non_greek": False,
           "exclude_punctuation": False, "relation_expectation": "corpus"}

COLUMNS = ["stratum", "label", "imported_records", "active_records", "words",
           "analyzable_links", "analyzable_sentences", "findings", "active_checks",
           "nuclei", "findings_fingerprint", "input_files", "input_bytes",
           "input_fingerprint", "input_matches_study", "seconds"]


def find_glaux_files(root: Path, stratum: str, workspace: Path) -> tuple[str, str]:
    """Put the GLAUx files of one sample where the program looks for them.

    The program, in ``glaux-sample`` mode, reads (and downloads into) the folder
    ``<workspace>/downloads/glaux-<sample>-<stratum>/``. The files found under *root*
    are copied there after their SHA-256 has been compared with the one of the study.
    Returns the pair (sample, stratum) the program wants as ``source_value``.
    """
    from greek_corpus_pipeline import glaux_sample

    sample, kind = GLAUX_SAMPLES[stratum]
    wanted = [Path(t.percorso).name for t in glaux_sample.select(sample, kind)]
    expected = {r["file"]: r["sha256"] for r in read_csv("inputs_files.csv") if r["stratum"] == stratum}
    available: dict[str, Path] = {}
    for path in root.rglob("*.xml"):
        available.setdefault(path.name, path)
    target = workspace / "downloads" / f"glaux-{sample}-{kind}"
    target.mkdir(parents=True, exist_ok=True)
    for name in wanted:
        if name not in available:
            print(f"  [{stratum}] {name} is not under {root}: the program will download it")
            continue
        digest = sha256(available[name])
        if name in expected and digest != expected[name]:
            print(f"  [{stratum}] {name}: SHA-256 differs from the study "
                  f"({digest[:12]}… against {expected[name][:12]}…); copied all the same")
        shutil.copy2(available[name], target / name)
    return sample, kind


def run_stratum(stratum: str, folder: Path | None, glaux_root: Path | None,
                workspace: Path, families: dict[str, bool]) -> dict:
    """Prepare and diagnose one stratum; return its summary."""
    from gui_qt.workers import prepare_corpus, run_detection
    from greek_corpus_pipeline.storage import save_metadata

    corpus = CORPUS_NAMES[stratum]
    if stratum in GLAUX_SAMPLES:
        mode = "glaux-sample"
        if glaux_root is not None:
            sample, kind = find_glaux_files(glaux_root, stratum, workspace)
        else:
            sample, kind = GLAUX_SAMPLES[stratum]
        value = f"{sample}/{kind}"
        input_dir = workspace / "downloads" / f"glaux-{sample}-{kind}"
    else:
        mode, value, input_dir = "folder", str(folder), folder

    run_id = f"rerun-{stratum}"
    run = workspace / "runs" / run_id
    if run.exists():
        shutil.rmtree(run)
    save_metadata(workspace, run_id, {"run_id": run_id, "corpus_name": corpus,
                                      "source_mode": mode, "source_value": value, "stages": {}})
    log_lines: list[str] = []

    started = time.time()
    prepare_corpus(workspace, run_id, mode, value, corpus,
                   lambda step, total, message: None, log_lines.append)
    run_detection(workspace, run_id, families, FILTERS,
                  lambda step, total, message: None, log_lines.append)
    seconds = round(time.time() - started)

    reproduction = workspace / "reproduction"
    (reproduction / "finding_keys").mkdir(parents=True, exist_ok=True)
    (reproduction / f"log-{stratum}.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    result = summarise_run(run)
    with gzip.open(reproduction / "finding_keys" / f"{stratum}.csv.gz", "wt",
                   encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(KEY)
        for row in sorted(result["keys"].itertuples(index=False)):
            writer.writerow(row)

    files, _ = scan(input_dir)           # the folder of a stratum holds exactly the files of that stratum
    reference = next(r for r in read_csv("inputs.csv") if r["stratum"] == stratum)
    value_fp = fingerprint(files)
    return {
        "stratum": stratum, "label": LABELS[stratum],
        **{k: result[k] for k in COLUMNS[2:11]},
        "input_files": len(files), "input_bytes": sum(s for s, _ in files.values()),
        "input_fingerprint": value_fp,
        "input_matches_study": value_fp == reference["input_fingerprint"],
        "seconds": seconds,
    }


def check_inputs(strata, gorman, pedalion) -> None:
    """Report the input fingerprints of Gorman and Pedalion before the long computation starts."""
    folders = {"gorman": gorman, "pedalion": pedalion}
    for stratum in strata:
        folder = folders.get(stratum)
        if folder is None:
            continue
        files, _ = scan(folder)          # Gorman and Pedalion: every XML file under the folder
        reference = next(r for r in read_csv("inputs.csv") if r["stratum"] == stratum)
        value = fingerprint(files)
        state = "same as the study" if value == reference["input_fingerprint"] else (
            f"DIFFERENT from the study ({reference['input_fingerprint']}): "
            "see input_fingerprint.py --diff")
        print(f"input {stratum}: {len(files)} XML files, fingerprint {value}, {state}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gorman", type=Path)
    parser.add_argument("--pedalion", type=Path)
    parser.add_argument("--glaux", type=Path)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--strata", nargs="+", choices=STRATA, default=list(STRATA))
    parser.add_argument("--no-variation", action="store_true",
                        help="do not run the n-gram variation family (compare_with_reference.py then needs "
                             "--skip-variation, and says that the nuclei were not compared)")
    arguments = parser.parse_args(argv)

    for stratum in arguments.strata:
        if stratum == "gorman" and not arguments.gorman:
            parser.error("--gorman is needed for the stratum gorman")
        if stratum == "pedalion" and not arguments.pedalion:
            parser.error("--pedalion is needed for the stratum pedalion")
    workspace = arguments.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    families = dict(FAMILIES, variation=not arguments.no_variation)

    check_inputs(arguments.strata, arguments.gorman, arguments.pedalion)
    rows = []
    for stratum in arguments.strata:
        folder = {"gorman": arguments.gorman, "pedalion": arguments.pedalion}.get(stratum)
        row = run_stratum(stratum, folder.resolve() if folder else None,
                          arguments.glaux.resolve() if arguments.glaux else None,
                          workspace, families)
        rows.append(row)
        print(f"{stratum}: {row['findings']} findings, {row['active_checks']} checks, "
              f"fingerprint {row['findings_fingerprint']}, {row['seconds']} s", flush=True)
        reproduction = workspace / "reproduction"
        with (reproduction / "rerun_summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    options = ""
    if set(arguments.strata) != set(STRATA):
        options += " --strata " + " ".join(arguments.strata)
    if arguments.no_variation:
        options += " --skip-variation"
    print(f"\nsummary written to {workspace / 'reproduction' / 'rerun_summary.csv'}\n"
          f"next: python compare_with_reference.py {workspace}{options}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
