#!/usr/bin/env python
"""Redo what Table S4.2 of Supplement S4 states about the fixed limits of the code.

Besides the nine parameters of Table S4.1, a few numerical limits written in the code decide which strings or
structures a check considers at all (Table S4.2). The supplement states the effect of each on the six runs:
three of them change findings, one is "never reached", one "none in the six strata", one "not measured".
This script measures the effect of every limit that the table says has a measured effect, by taking the limit
away and running the checks again, one limit at a time:

    L1  postag.py       a numeral or a diagram label written in capitals has at most five letters
    L2  orthography.py  final-sigma-inside does not examine a core of two characters or fewer
    L3  orthography.py  an enclitic written together with its host is recognised if the host is longer
                        than the enclitic by more than two characters
    L4  syntax.py       the search for the effective head stops after twelve steps
    L5  agreement.py    a verbal adjective excluded from case-object is longer than four characters
    L6  postag.py, orthography.py, agdt_schema.py
                        the placeholder forms recognised by the checks are [0] to [20]

The program reads these values when it is imported, so each variant is run by a separate Python interpreter, on a
copy of the program (``src``, ``gui_qt``, ``data``) in which the one limit is changed; your own copy of the package
is not touched. In each interpreter the function that produced the runs of the study
(``gui_qt.workers.run_detection``) is called on the token table of each run with the four families of checks that
the limits touch (morphology, syntax, text, agreement) and the filters of the study. The unmodified program gives
the baseline, which is compared with Table S1.1 for every check of those families; the findings that a variant
adds or loses, check by check and stratum by stratum, are compared with what Table S4.2 and the text of S4 state.
The script also reads, in the token tables, the largest placeholder form ([n]) of the data, which Table S4.2 puts at [16].

Rows of Table S4.2 that this script does not measure: the annotator's note in the relation field (the table says
"not measured": only the wording of the pattern is checked against the code) and the tags that the padding can
repair (part of the definition of two checks; only the wording is checked against the code).

usage:
    python recompute_fixed_limits.py --workspace W        the runs written by rerun_diagnosis.py
    python recompute_fixed_limits.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>);
                                                          each needs tokens.parquet and metadata.json

The exit status is 0 when every stated value is reproduced.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]

#: The families that contain the checks the limits touch, and the filters of the study (those of rerun_diagnosis.py).
FAMILIES = {"morphology": True, "lemma": False, "syntax": True, "text": True, "agreement": True, "variation": False}
FILTERS = {"exclude_placeholders": True, "exclude_non_greek": False,
           "exclude_punctuation": False, "relation_expectation": "corpus"}
#: Table S1.1 gives the same families in these words.
CHECKED_FAMILIES = ("morphology", "syntax", "text", "agreement")

#: limit -> (description, [(file under src/greek_corpus_pipeline, text to replace, replacement, occurrences)])
OLD_PLACEHOLDER = "(?:[0-9]|1[0-9]|20)"
VARIANTS = {
    "L1": ("five capital letters",
           [("postag.py", "and len(letters) <= 5", "and len(letters) <= 1000000", 1)]),
    "L2": ("core of the final sigma",
           [("orthography.py", "if len(core) <= 2:", "if len(core) <= 0:", 1)]),
    "L3": ("length of the host of an enclitic",
           [("orthography.py", "len(bare) > len(suffix) + 2", "len(bare) > len(suffix)", 1)]),
    "L4": ("twelve steps to the effective head",
           [("syntax.py", "for _ in range(12):", "for _ in range(1000):", 1)]),
    "L5": ("verbal adjective longer than four characters",
           [("agreement.py", "return len(text) > 4 and text.endswith(", "return text.endswith(", 1)]),
    "L6": ("placeholders [0] to [20]",
           [("postag.py", OLD_PLACEHOLDER, "[0-9]+", 1), ("orthography.py", OLD_PLACEHOLDER, "[0-9]+", 1),
            ("agdt_schema.py", OLD_PLACEHOLDER, "[0-9]+", 1)]),
}

#: What Table S4.2 and the text of S4 state: variant -> {(check, stratum): findings added (+) or lost (-)}.
#: Every cell that is not named must not change.
STATED = {
    "L1": {("slot-missing", "glaux_auto"): -5},
    "L2": {("final-sigma-inside", "pedalion"): +1},
    "L3": {("double-accent", "gorman"): -1, ("double-accent", "pedalion"): -5},
    "L4": {},
    "L5": {},
    "L6": {},
}
#: The same effects as absolute numbers: (check, stratum) -> (with the limit, without it).
STATED_ABSOLUTE = {("slot-missing", "glaux_auto"): (356, 351),
                   ("double-accent", "gorman"): (55, 54),
                   ("double-accent", "pedalion"): (24, 19)}
#: The form that final-sigma-inside would also report in Pedalion without the limit of L2.
SIGMA_FORM = "ςΖ"
#: The largest placeholder form of the data (Table S4.2).
LARGEST_PLACEHOLDER = 16


# ---------------------------------------------------------------------------------------------
# the interpreter of one variant
# ---------------------------------------------------------------------------------------------

def child(tree: Path, output: Path, runs: list[str]) -> int:
    """Run the four families on each run with the program of *tree*; write the counts to *output*."""
    sys.path[:0] = [str(tree / "src"), str(tree)]
    import pandas as pd

    from gui_qt import workers

    assert Path(workers.__file__).resolve().is_relative_to(tree), workers.__file__
    answer: dict = {"strata": {}}
    for item in runs:
        stratum, folder = item.split("=", 1)
        scratch = Path(tempfile.mkdtemp(prefix="gcp-limits-run-"))
        run_id = f"rerun-{stratum}"
        run = scratch / "runs" / run_id
        run.mkdir(parents=True)
        shutil.copyfile(Path(folder) / "tokens.parquet", run / "tokens.parquet")
        shutil.copyfile(Path(folder) / "metadata.json", run / "metadata.json")
        workers.run_detection(scratch, run_id, dict(FAMILIES), dict(FILTERS), lambda *a: None, lambda *a: None)
        found = pd.read_parquet(run / "findings.parquet")
        counts = {k: int(v) for k, v in found["rule_id"].astype(str).value_counts().items()}
        sigma = found[found["rule_id"].astype(str) == "final-sigma-inside"]
        forms = sorted({str(v) for v in sigma["form"].astype(str)}) if len(sigma) else []
        answer["strata"][stratum] = {"counts": counts, "sigma_forms": forms}
        print(f"  {stratum}: {len(found):,} findings", flush=True)
        shutil.rmtree(scratch, ignore_errors=True)
    output.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------------------------
# the copy of the program in which one limit is changed
# ---------------------------------------------------------------------------------------------

def build_tree(destination: Path, edits: list[tuple[str, str, str, int]]) -> Path:
    """Copy src, gui_qt and data of the package and change the source text named by *edits*."""
    for name in ("src", "gui_qt", "data"):
        shutil.copytree(PACKAGE / name, destination / name, ignore=shutil.ignore_patterns("__pycache__"))
    for file_name, old, new, occurrences in edits:
        path = destination / "src" / "greek_corpus_pipeline" / file_name
        source = path.read_text(encoding="utf-8")
        if source.count(old) != occurrences:
            raise SystemExit(f"{file_name}: the text {old!r} occurs {source.count(old)} times, not {occurrences}: "
                             "the program is not the release that Table S4.2 describes")
        path.write_text(source.replace(old, new), encoding="utf-8")
    return destination


def literal(file_name: str, name: str) -> object:
    """The value of a module-level assignment ``name = <literal>`` in a source file of the program."""
    tree = ast.parse((PACKAGE / "src" / "greek_corpus_pipeline" / file_name).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"{name} is not assigned in {file_name}")


# ---------------------------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(HERE))
    import csv

    from repro_common import LABELS, REFERENCE, STRATA, stratum_of

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

    with (REFERENCE / "checks_overview.csv").open(encoding="utf-8", newline="") as handle:
        table_s1_1 = {r["rule_id"]: r for r in csv.DictReader(handle)}
    checked = sorted(rule for rule, row in table_s1_1.items() if row["family"] in CHECKED_FAMILIES)

    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="gcp-limits-") as temp:
        for variant, (description, edits) in {"B0": ("the program as released (baseline)", []), **VARIANTS}.items():
            print(f"== {variant}: {description}", flush=True)
            tree = build_tree(Path(temp) / variant, [(f, o, n, k) for f, o, n, k in edits])
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
        shown_stated, shown_obtained = str(stated), str(obtained)
        if max(len(shown_stated), len(shown_obtained)) <= 12:
            print(f"  {what:<84} {shown_stated:>12} {shown_obtained:>12}{'' if same else '   DIFFERENT'}")
        else:
            print(f"  {what:<84}{'' if same else '   DIFFERENT'}")
            print(f"      stated:   {shown_stated}")
            print(f"      obtained: {shown_obtained}")

    baseline = results["B0"]["strata"]
    print(f"\n{'The baseline against Table S1.1':<86} {'stated':>12} {'obtained':>12}")
    cells = bad = 0
    odd: list[str] = []
    for stratum in runs:
        for rule in checked:
            cells += 1
            stated_count = int(table_s1_1[rule][stratum])
            obtained_count = baseline[stratum]["counts"].get(rule, 0)
            if stated_count != obtained_count:
                bad += 1
                odd.append(f"{rule} / {LABELS[stratum]}: {stated_count} against {obtained_count}")
    show(f"cells (check × stratum) of the families {', '.join(CHECKED_FAMILIES)} that differ, of {cells}", 0, bad)
    for line in odd[:10]:
        print(f"      {line}")

    print(f"\n{'Table S4.2: findings added (+) or lost (-) when the limit is taken away':<86} {'stated':>12} {'obtained':>12}")
    for variant, (description, _) in VARIANTS.items():
        stated = {f"{c} / {LABELS[s]}": d for (c, s), d in STATED[variant].items() if s in runs}
        obtained = {}
        for stratum in runs:
            counts, base = results[variant]["strata"][stratum]["counts"], baseline[stratum]["counts"]
            for rule in set(counts) | set(base):
                if counts.get(rule, 0) != base.get(rule, 0):
                    obtained[f"{rule} / {LABELS[stratum]}"] = counts.get(rule, 0) - base.get(rule, 0)
        show(f"{variant} {description}: findings that change", stated, obtained)

    print(f"\n{'The same effects as absolute numbers (with the limit, without it)':<86} {'stated':>12} {'obtained':>12}")
    variant_of = {("slot-missing", "glaux_auto"): "L1", ("double-accent", "gorman"): "L3", ("double-accent", "pedalion"): "L3"}
    for (rule, stratum), stated in STATED_ABSOLUTE.items():
        if stratum not in runs:
            continue
        variant = variant_of[(rule, stratum)]
        obtained = (baseline[stratum]["counts"].get(rule, 0), results[variant]["strata"][stratum]["counts"].get(rule, 0))
        show(f"{rule}, {LABELS[stratum]}", stated, obtained)
    if "pedalion" in runs:
        before = set(baseline["pedalion"]["sigma_forms"])
        after = set(results["L2"]["strata"]["pedalion"]["sigma_forms"])
        show("final-sigma-inside, Pedalion: the form that is reported only without the limit", {SIGMA_FORM},
             after - before)

    print(f"\n{'The largest placeholder form [n] of the data (Table S4.2)':<86} {'stated':>12} {'obtained':>12}")
    import pandas as pd
    largest = 0
    for stratum, folder in runs.items():
        forms = pd.read_parquet(folder / "tokens.parquet", columns=["form"])["form"].astype("string").fillna("")
        numbers = forms.str.extract(r"^\[(\d+)\]$")[0].dropna().astype(int)
        largest = max(largest, int(numbers.max()) if len(numbers) else 0)
    show("largest n among the forms [n] of the tokens of the runs", LARGEST_PLACEHOLDER, largest)

    print(f"\n{'The wording of two rows against the code':<86} {'stated':>12} {'obtained':>12}")
    pattern = literal("orthography.py", "ANNOTATOR_NOTE_RE")
    examples = {"!!": True, "!": False, "?%": True, "%": False, "abcd ": True, "abc ": False, "abcd": False, "ABCD ": False}
    show("annotator's note: two or more of ! ? %, or four lower-case Latin letters and a space",
         examples, {text: bool(re.search(pattern, text)) for text in examples})
    padding = (PACKAGE / "src" / "greek_corpus_pipeline" / "postag.py").read_text(encoding="utf-8")
    show("padding: a tag of eight characters, or longer than nine, can be repaired",
         (1, 1), (padding.count("pad_ok = (lengths == 8)"), padding.count("trim_ok = (lengths > 9)")))

    print(f"\nRESULT: {compared} values compared, " + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        sys.exit(child(Path(sys.argv[2]).resolve(), Path(sys.argv[3]), sys.argv[4:]))
    sys.exit(main())
