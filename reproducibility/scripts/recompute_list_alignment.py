#!/usr/bin/env python
"""Redo Table S6.2 of Supplement S6: what changes when a closed list is aligned with Smyth (1920).

The program distributes ten closed lists (``data/liste``). Four of those that rest on the grammar do
not coincide entry by entry with Smyth (Table S6.1), and S6 measures the effect of each difference by
running the checks that read the lists again, with one list changed at a time:

    E   enclitiche                     remove ἄττα, μεν, μεο and σφεσι
    P   pronomi-personali              add μου, μοι, σου, σοι, οὑ, οἱ, σφώ and σφῷν
    Q   quantificatori-non-concordanti remove εἷς
    N1  numerali-indeclinabili         remove δύο
    N2  numerali-indeclinabili         remove τρεῖς καὶ δέκα

The program reads a list when its module is imported, so each variant is run by a separate Python
interpreter, on a copy of the program (``src``, ``gui_qt``, ``data``) in which only the file of that list is
changed; your own copy of the package is not touched. In each interpreter the function that produced the
runs of the study (``gui_qt.workers.run_detection``) is called on the token table of each run with the
three families of checks that read the four lists (morphology, text, agreement) and the filters of the
study. The unmodified lists give the baseline; the findings that a variant adds or loses, check by check, are
the cells of Table S6.2.

Besides the cells of the table the script compares: that no other check changes; that no finding of the
checks concerned carries a proposed correction (S6: "No proposed correction changes, because none of the
checks concerned proposes one"); the nine verifiable violations that all the changes together would add
(eight in Gorman, one in Pedalion); the rate of violations per 10,000 active tokens (31.0 to 31.2 in
Gorman, unchanged in the other five strata); and that the baseline gives, for the checks concerned, the
numbers of Table S1.1.

The person assigned to each pronoun form that is added (first, second, third) is not a datum of S6
and does not decide whether a finding is produced; σφώ and σφῷν are put with the second person.

usage:
    python recompute_list_alignment.py --workspace W        the runs written by rerun_diagnosis.py
    python recompute_list_alignment.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>);
                                                            each needs tokens.parquet and metadata.json

Time: a few minutes (six interpreters, each with up to six runs; the larger corpora take about a minute).
The exit status is 0 when every stated value is reproduced.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]

#: The families that read the four lists, and the filters of the study (those of rerun_diagnosis.py).
FAMILIES = {"morphology": True, "lemma": False, "syntax": False, "text": True, "agreement": True, "variation": False}
FILTERS = {"exclude_placeholders": True, "exclude_non_greek": False,
           "exclude_punctuation": False, "relation_expectation": "corpus"}

AFFECTED = ("double-accent", "personal-pronoun-person", "slot-missing", "slot-missing-bare",
            "uninflected-lemma", "agreement-modifier")
PRONOUN_PERSON = {"μου": "prima", "μοι": "prima", "σου": "seconda", "σοι": "seconda",
                  "οὑ": "terza", "οἱ": "terza", "σφώ": "seconda", "σφῷν": "seconda"}

#: variant -> (description, [(list, operation, entries)])
VARIANTS = {
    "E": ("enclitiche: remove ἄττα, μεν, μεο and σφεσι",
          [("enclitiche", "remove", ["ἄττα", "μεν", "μεο", "σφεσι"])]),
    "P": ("pronomi-personali: add μου, μοι, σου, σοι, οὑ, οἱ, σφώ and σφῷν",
          [("pronomi-personali", "add", list(PRONOUN_PERSON))]),
    "Q": ("quantificatori-non-concordanti: remove εἷς",
          [("quantificatori-non-concordanti", "remove", ["εἷς"])]),
    "N1": ("numerali-indeclinabili: remove δύο",
           [("numerali-indeclinabili", "remove", ["δύο"])]),
    "N2": ("numerali-indeclinabili: remove τρεῖς καὶ δέκα",
           [("numerali-indeclinabili", "remove", ["τρεῖς καὶ δέκα"])]),
}

#: Table S6.2: (variant, check, {stratum: findings added}). The two manual strata give no change.
TABLE_S6_2 = [
    ("E", "double-accent", {"gorman": 1, "pedalion": 0, "glaux_auto": 0, "glaux_conf_auto": 1}),
    ("P", "personal-pronoun-person", {"gorman": 397, "pedalion": 112, "glaux_auto": 1169, "glaux_conf_auto": 844}),
    ("Q", "agreement-modifier", {"gorman": 13, "pedalion": 9, "glaux_auto": 15, "glaux_conf_auto": 7}),
    ("N1", "slot-missing", {"gorman": 8, "pedalion": 1, "glaux_auto": 0, "glaux_conf_auto": 0}),
    ("N1", "slot-missing-bare", {"gorman": 77, "pedalion": 6, "glaux_auto": 0, "glaux_conf_auto": 0}),
    ("N1", "agreement-modifier", {"gorman": 166, "pedalion": 4, "glaux_auto": 0, "glaux_conf_auto": 0}),
    ("N2", None, {"gorman": 0, "pedalion": 0, "glaux_auto": 0, "glaux_conf_auto": 0}),
]
SHOWN = ("gorman", "pedalion", "glaux_auto", "glaux_conf_auto")
#: Violations per 10,000 active tokens before and after (Table 7 and the text of S6).
RATE_BEFORE = {"gorman": 31.0, "pedalion": 49.6, "glaux_auto": 12.9, "glaux_man": 19.4,
               "glaux_conf_auto": 6.4, "glaux_conf_man": 5.3}
RATE_AFTER = dict(RATE_BEFORE, gorman=31.2)


# ---------------------------------------------------------------------------------------------
# the interpreter of one variant
# ---------------------------------------------------------------------------------------------

def child(tree: Path, output: Path, runs: list[str]) -> int:
    """Run the three families on each run with the program of *tree*; write the counts to *output*."""
    sys.path[:0] = [str(tree / "src"), str(tree)]
    import pandas as pd

    from greek_corpus_pipeline import resources
    from gui_qt import workers

    for module in (resources, workers):
        assert Path(module.__file__).resolve().is_relative_to(tree), module.__file__

    def size(name: str) -> int:
        entries = resources.entries(name)
        return sum(len(forms) for forms in entries.values()) if isinstance(entries, dict) else len(entries)
    sizes = {name: size(name) for name in
             ("enclitiche", "pronomi-personali", "quantificatori-non-concordanti", "numerali-indeclinabili")}
    answer: dict = {"sizes": sizes, "strata": {}}
    proposal_columns = ["suggested_postag", "suggested_lemma", "suggested_form", "suggested_relation", "suggested_head"]
    for item in runs:
        stratum, folder = item.split("=", 1)
        scratch = Path(tempfile.mkdtemp(prefix="gcp-lists-run-"))
        run_id = f"rerun-{stratum}"
        run = scratch / "runs" / run_id
        run.mkdir(parents=True)
        shutil.copyfile(Path(folder) / "tokens.parquet", run / "tokens.parquet")
        shutil.copyfile(Path(folder) / "metadata.json", run / "metadata.json")
        workers.run_detection(scratch, run_id, dict(FAMILIES), dict(FILTERS),
                              lambda *a: None, lambda *a: None)
        found = pd.read_parquet(run / "findings.parquet")
        counts = {k: int(v) for k, v in found["rule_id"].astype(str).value_counts().items()}
        concerned = found[found["rule_id"].isin(AFFECTED)]
        with_proposal = pd.Series(False, index=concerned.index)
        for column in proposal_columns:
            if column in concerned.columns:
                with_proposal |= concerned[column].notna() & (concerned[column].astype(str).str.strip() != "")
        answer["strata"][stratum] = {"counts": counts, "affected_with_proposal": int(with_proposal.sum())}
        print(f"  {stratum}: {len(found):,} findings", flush=True)
        shutil.rmtree(scratch, ignore_errors=True)
    output.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------------------------
# the copy of the program in which one list is changed
# ---------------------------------------------------------------------------------------------

def build_tree(destination: Path, edits: list[tuple[str, str, list[str]]]) -> Path:
    """Copy src, gui_qt and data of the package and change the list files named by *edits*."""
    for name in ("src", "gui_qt", "data"):
        shutil.copytree(PACKAGE / name, destination / name, ignore=shutil.ignore_patterns("__pycache__"))
    for list_id, operation, entries in edits:
        path = destination / "data" / "liste" / f"{list_id}.json"
        resource = json.loads(path.read_text(encoding="utf-8"))
        entries_of_list = resource["voci"]
        if operation == "remove":
            for entry in entries:
                if entry not in entries_of_list:
                    raise SystemExit(f"{entry!r} is not in the list {list_id}: the list is not the one of the study")
                entries_of_list.remove(entry)
        elif operation == "add":
            for entry in entries:
                if any(entry in forms for forms in entries_of_list.values()):
                    raise SystemExit(f"{entry!r} is already in the list {list_id}")
                entries_of_list[PRONOUN_PERSON[entry]].append(entry)
        else:
            raise ValueError(operation)
        path.write_text(json.dumps(resource, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return destination


# ---------------------------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(HERE))
    from repro_common import LABELS, REFERENCE, STRATA, stratum_of
    import csv

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="*", type=Path)
    parser.add_argument("--workspace", type=Path)
    arguments = parser.parse_args(argv)
    folders = list(arguments.runs)
    if arguments.workspace:
        folders += [arguments.workspace / "runs" / f"rerun-{s}" for s in STRATA
                    if (arguments.workspace / "runs" / f"rerun-{s}" / "tokens.parquet").is_file()]
    if not folders:
        parser.error("give run folders or --workspace")
    runs: dict[str, Path] = {}
    for folder in folders:
        stratum = stratum_of(folder)
        if stratum is None:
            parser.error(f"cannot tell which stratum {folder.name} is")
        if not (folder / "metadata.json").is_file():
            parser.error(f"{folder} has no metadata.json")
        runs[stratum] = folder.resolve()

    with (PACKAGE / "data" / "catalogo_controlli.csv").open(encoding="utf-8-sig", newline="") as handle:
        classes = {r["id"]: r["classe"] for r in csv.DictReader(handle, delimiter=";")}
    with (REFERENCE / "checks_overview.csv").open(encoding="utf-8", newline="") as handle:
        table_s1_1 = {r["rule_id"]: r for r in csv.DictReader(handle)}

    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="gcp-lists-") as temp:
        for variant, (description, edits) in {"B0": ("unmodified lists (baseline)", []), **VARIANTS}.items():
            print(f"== {variant}: {description}", flush=True)
            tree = build_tree(Path(temp) / variant, edits)
            output = Path(temp) / f"{variant}.json"
            command = [sys.executable, str(Path(__file__).resolve()), "--child", str(tree), str(output)]
            command += [f"{stratum}={folder}" for stratum, folder in runs.items()]
            subprocess.run(command, check=True)
            results[variant] = json.loads(output.read_text(encoding="utf-8"))

    compared = different = 0

    def show(what: str, stated, obtained) -> None:
        nonlocal compared, different
        same = stated == obtained
        compared += 1
        different += not same
        print(f"  {what:<84} {stated!s:>9} {obtained!s:>9}{'' if same else '   DIFFERENT'}")

    baseline = results["B0"]["strata"]
    print(f"\n{'Table S6.2: findings added, by list change, check and stratum':<86} {'stated':>9} {'obtained':>9}")
    for variant, check, stated in TABLE_S6_2:
        description = VARIANTS[variant][0]
        for stratum in SHOWN:
            if stratum not in runs:
                continue
            counts, base = results[variant]["strata"][stratum]["counts"], baseline[stratum]["counts"]
            obtained = (counts.get(check, 0) - base.get(check, 0)) if check else 0
            show(f"{variant} ({description[:34]}…) {check or '—':<24} {LABELS[stratum][:14]}",
                 stated[stratum], obtained)

    print("\nNo other check changes, in any stratum (including the two manual strata of GLAUx):")
    for variant in VARIANTS:
        named = {c for v, c, _ in TABLE_S6_2 if v == variant and c}
        others = {}
        for stratum in runs:
            counts, base = results[variant]["strata"][stratum]["counts"], baseline[stratum]["counts"]
            for c in set(counts) | set(base):
                if counts.get(c, 0) != base.get(c, 0) and c not in named:
                    others[f"{c} / {LABELS[stratum]}"] = counts.get(c, 0) - base.get(c, 0)
        show(f"{variant}: checks that change besides those of the table", {}, others)
    for stratum in ("glaux_man", "glaux_conf_man"):
        if stratum in runs:
            moved = sum(abs(results[v]["strata"][stratum]["counts"].get(c, 0) - baseline[stratum]["counts"].get(c, 0))
                        for v in VARIANTS for c in AFFECTED)
            show(f"all variants, {LABELS[stratum]}: findings that change", 0, moved)

    print("\nProposed corrections (none of the checks concerned proposes one):")
    for variant in ["B0"] + list(VARIANTS):
        total = sum(results[variant]["strata"][s]["affected_with_proposal"] for s in runs)
        show(f"{variant}: findings of the six checks concerned that carry a proposal, all strata", 0, total)

    print("\nThe nine violations that all the changes together would add:")
    added = {s: 0 for s in runs}
    for variant in VARIANTS:
        for stratum in runs:
            counts, base = results[variant]["strata"][stratum]["counts"], baseline[stratum]["counts"]
            added[stratum] += sum(counts.get(c, 0) - base.get(c, 0) for c in set(counts) | set(base)
                                  if classes.get(c) == "violazione")
    show("verifiable violations added, in all", 9, sum(added.values()))
    show("  of them in Gorman (slot-missing)", 8, added.get("gorman", 0))
    show("  of them in Pedalion (slot-missing)", 1, added.get("pedalion", 0))
    show("  of them in the other strata", 0, sum(v for s, v in added.items() if s not in ("gorman", "pedalion")))

    print("\nViolations per 10,000 active tokens, before and after all the changes:")
    with (REFERENCE / "table_S11_1_units_and_findings.csv").open(encoding="utf-8", newline="") as handle:
        units_row = {r["stratum"]: r for r in csv.DictReader(handle)}
    with (REFERENCE / "findings_by_class.csv").open(encoding="utf-8", newline="") as handle:
        by_class = {r["stratum"]: r for r in csv.DictReader(handle)}
    from decimal import ROUND_HALF_UP, Decimal
    for stratum in runs:
        active = int(units_row[stratum]["active_records"])
        violations = int(by_class[stratum]["violations"])
        for label, extra, stated in (("before", 0, RATE_BEFORE[stratum]), ("after", added[stratum], RATE_AFTER[stratum])):
            rate = float((Decimal(10000 * (violations + extra)) / Decimal(active)).quantize(Decimal("0.1"), ROUND_HALF_UP))
            show(f"{LABELS[stratum]}: rate {label}", stated, rate)

    print("\nThe baseline against Table S1.1 (the checks concerned, every stratum):")
    for stratum in runs:
        for check in AFFECTED:
            show(f"{LABELS[stratum]}: {check}", int(table_s1_1[check][stratum]), baseline[stratum]["counts"].get(check, 0))

    print("\nSize of the lists in each variant (Table S6.1: enclitiche 82, pronomi-personali 36 forms, "
          "quantificatori-non-concordanti 4, numerali-indeclinabili 47):")
    for variant in ["B0"] + list(VARIANTS):
        sizes = results[variant]["sizes"]
        print(f"  {variant:<3} " + ", ".join(f"{k} {v}" for k, v in sizes.items()))
    for key, stated in (("enclitiche", 82), ("pronomi-personali", 36),
                        ("quantificatori-non-concordanti", 4), ("numerali-indeclinabili", 47)):
        show(f"baseline size of {key}", stated, results["B0"]["sizes"][key])

    print(f"\nRESULT: {compared} values compared, " + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        sys.exit(child(Path(sys.argv[2]).resolve(), Path(sys.argv[3]), sys.argv[4:]))
    sys.exit(main())
