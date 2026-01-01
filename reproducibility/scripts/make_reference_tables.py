#!/usr/bin/env python
"""Rebuild the machine-readable reference tables from the runs of the study.

Included for transparency. The runs of the study (tokens, findings, variation
tables) are NOT distributed with this package, so a reviewer normally does not
run this script: the files it writes are already in ``reproducibility/reference/``.
It documents how they were obtained, and lets anybody who has the runs of the study
(or a set of runs of their own, folder names adjusted in ``STUDY_RUNS``) rebuild the
tables and diff them against the distributed ones.

usage:
    python make_reference_tables.py RUNS_DIR OUTPUT_DIR

RUNS_DIR holds one run folder per stratum, named as in ``STUDY_RUNS`` of
``repro_common.py`` (the names of the folders of the study). OUTPUT_DIR receives the same files as
``reproducibility/reference/`` (except the three files about the input XML,
``inputs.csv``, ``inputs_files.csv``, and the two sensitivity tables).
"""
from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import (EN_CLASS, EN_FAMILY, EN_SEVERITY, EN_TREATMENT, KEY, LABELS, PACKAGE,
                          PLANE_EN, PLANES, STRATA, STUDY_RUNS, summarise_run)

import pandas as pd

from greek_corpus_pipeline import rule_catalog as rc

def write_keys(keys: pd.DataFrame, target: Path) -> None:
    """The findings as a sorted, compressed list of their four key fields."""
    with gzip.open(target, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(KEY)
        for row in sorted(keys.itertuples(index=False)):
            writer.writerow(row)


def main(runs_dir: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "finding_keys").mkdir(exist_ok=True)
    summary, nuclei, per_check, shares = [], [], {}, []
    for stratum in STRATA:
        result = summarise_run(runs_dir / STUDY_RUNS[stratum])
        summary.append({
            "stratum": stratum, "label": LABELS[stratum],
            **{k: result[k] for k in (
                "imported_records", "active_records", "words", "analyzable_links",
                "analyzable_sentences", "findings", "active_checks", "nuclei",
                "findings_fingerprint")},
        })
        nuclei.append({"stratum": stratum, "label": LABELS[stratum],
                       **{PLANE_EN[p]: result["planes"][p] for p in PLANES},
                       "total": result["nuclei"]})
        per_check[stratum] = result["per_check"]
        shares.append({"stratum": stratum, "findings": result["findings"],
                       "violations": result["violations"], "to_verify": result["to_verify"],
                       "variants": result["variants"]})
        write_keys(result["keys"], out / "finding_keys" / f"{stratum}.csv.gz")
        print(stratum, result["findings"], result["findings_fingerprint"], flush=True)

    pd.DataFrame(summary).to_csv(out / "table_S11_1_units_and_findings.csv", index=False)
    pd.DataFrame(nuclei).to_csv(out / "table_S8_1_nuclei_by_level.csv", index=False)
    pd.DataFrame(shares).assign(
        violation_share=lambda t: (t["violations"] / t["findings"]).round(4)
    ).to_csv(out / "findings_by_class.csv", index=False)

    rows = []
    with (PACKAGE / "data" / "catalogo_controlli.csv").open(encoding="utf-8-sig", newline="") as handle:
        for entry in csv.DictReader(handle, delimiter=";"):
            rid = entry["id"]
            rows.append({
                "rule_id": rid, "name_en": entry["name_en"],
                "family": EN_FAMILY[rc.rule_family(rid)],
                "class": EN_CLASS[rc.rule_class(rid)],
                "treatment": EN_TREATMENT[rc.rule_treatment(rid)],
                "severity": EN_SEVERITY[rc.rule_severity(rid)],
                **{s: int(per_check[s].get(rid, 0)) for s in STRATA},
            })
    pd.DataFrame(rows).to_csv(out / "checks_overview.csv", index=False)


if __name__ == "__main__":
    if sys.argv[1:] in (["-h"], ["--help"]):
        print(__doc__)
        raise SystemExit(0)
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
