# -*- coding: utf-8 -*-
"""What this computer is really running.

It is launched with a double click on CHECK_INSTALL.bat. It writes a text file
(CHECK_INSTALL_result.txt) next to itself, and opens it.

It serves to answer three questions that cannot be checked from outside: which copy of
the code is loaded, which version it is, and how long this machine really takes to do
the work.
"""
from __future__ import annotations

import io
import os
import platform
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE / "CHECK_INSTALL_result.txt"


def declared_version() -> str:
    """The version that this folder declares, read from pyproject.toml.

    No library: the file is at hand and the line sought is a single one. If the file is
    missing or the line is not there, an empty string is returned and the comparison is
    simply skipped.
    """
    path = HERE / "pyproject.toml"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def shipped_rules() -> int | None:
    """How many checks the table shipped in data/ contains.

    The file is separated by semicolons and the first line is the header. It returns
    ``None`` if the file is not there: in that case the comparison is not made, instead
    of declaring a fault that has not been measured.
    """
    path = HERE / "data" / "catalogo_controlli.csv"
    try:
        lines = [line for line in path.read_text(encoding="utf-8-sig").splitlines()
                 if line.strip()]
    except OSError:
        return None
    return max(len(lines) - 1, 0)


def shipped_rule_ids() -> set[str] | None:
    """The identifiers of the checks in the table shipped in data/ (column ``id``).

    It returns ``None`` if the file is not there or has no ``id`` column: in that case the
    comparison is not made.
    """
    import csv

    path = HERE / "data" / "catalogo_controlli.csv"
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter=";"))
    except OSError:
        return None
    if not rows or "id" not in rows[0]:
        return None
    return {row["id"].strip() for row in rows if row.get("id")}


buffer = io.StringIO()


def say(line: str = "") -> None:
    print(line)
    buffer.write(line + "\n")


def rule(title: str) -> None:
    say()
    say("=" * 66)
    say(title)
    say("=" * 66)


rule("1. THIS COMPUTER")
say(f"Python           {platform.python_version()}  ({platform.machine()})")
say(f"Executable       {sys.executable}")
say(f"Folder           {HERE}")
say(f"Processors       {os.cpu_count()}")

rule("2. WHICH CODE IS LOADED")
problems: list[str] = []
try:
    import greek_corpus_pipeline
except ImportError:
    # The editable install points Python at pkg_root/src through a .pth file.
    # When that is broken the program cannot start at all, so the check has to
    # keep going on its own and say so.
    sys.path.insert(0, str(HERE / "src"))
    problems.append(
        "The installation does not work: Python cannot find the package by itself. "
        "Run setup.bat again. (For this check the package was loaded by hand.)")
    try:
        import greek_corpus_pipeline
    except Exception:
        pass

try:
    import greek_corpus_pipeline

    source = Path(greek_corpus_pipeline.__file__).resolve()
    version = getattr(greek_corpus_pipeline, "__version__", "?")
    say(f"Version          {version}")
    say(f"Loaded from      {source.parent}")
    # No version number written in here: the code that is loaded is compared with what
    # this folder declares. A literal goes stale at every release and ends up accusing
    # the right installation of being faulty.
    declared = declared_version()
    if declared and version != declared:
        problems.append(
            f"The loaded version is {version}, but this folder declares "
            f"{declared}. The program is reading another copy of the "
            f"code, located in {source.parent}.")
    if str(HERE).lower() not in str(source).lower():
        problems.append(
            f"The code is NOT read from this folder but from {source.parent}. "
            f"This almost always means that a second copy of the program exists.")
except Exception:
    say("ERROR while importing the package:")
    say(traceback.format_exc())
    problems.append("The package greek_corpus_pipeline cannot be imported at all.")

for name in ("pandas", "numpy", "pyarrow", "PyQt6"):
    try:
        module = __import__(name)
        say(f"{name:<16} {getattr(module, '__version__', 'present')}")
    except Exception:
        say(f"{name:<16} MISSING")

rule("3. ARE THE EXPECTED FUNCTIONS THERE?")
checks = [
    ("CoNLL-U export", "greek_corpus_pipeline.conllu", "export_conllu"),
    ("One computation per distinct value", "greek_corpus_pipeline.fastmap", "map_unique"),
    ("Metadata read from the URNs", "greek_corpus_pipeline.corpus_metadata",
     "resolve_by_identifier"),
    ("Chronological ordering", "greek_corpus_pipeline.stats", "_order_groups"),
]
for label, module_name, attribute in checks:
    try:
        module = __import__(module_name, fromlist=[attribute])
        found = hasattr(module, attribute)
    except Exception as error:
        found = False
        say(f"  ({module_name}: {type(error).__name__})")
    say(f"{'YES' if found else 'NO '}  {label}")
    if not found:
        problems.append(f"Missing: {label}")

try:
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG, catalog_frame

    catalogue = catalog_frame("en")
    say(f"YES  Catalogue of the checks: {len(catalogue)} checks")
    # No hand-written number here either: the catalogue of the code is compared with the
    # table shipped in data/. If the two do not coincide, the program is reading a code
    # and a table that do not go together, and that is exactly the fault that this check
    # must find.
    shipped = shipped_rules()
    if shipped is not None and len(catalogue) != shipped:
        problems.append(
            f"The catalogue in the code has {len(catalogue)} checks, the table "
            f"data/catalogo_controlli.csv has {shipped}: the code and the data "
            "do not come from the same copy of the program.")

    # The identifiers, not only their number: the catalogue of the code and the table
    # shipped in data/ must name the same checks. If they do not, the program is running
    # a different copy of the code, whatever the version says.
    shipped_ids = shipped_rule_ids()
    if shipped_ids is not None:
        only_code = sorted(set(RULE_CATALOG) - shipped_ids)
        only_table = sorted(shipped_ids - set(RULE_CATALOG))
        if only_code or only_table:
            say("NO   The checks of the code are not those of data/catalogo_controlli.csv")
            problems.append(
                "The catalogue in the code and data/catalogo_controlli.csv name different "
                "checks: only in the code " + (", ".join(only_code) or "none")
                + "; only in the table " + (", ".join(only_table) or "none"))
        else:
            say("YES  The checks of the code are those of data/catalogo_controlli.csv")

    # The names of six checks, compared with the reference table of the catalogue
    # (English names; only the first word is compared).
    expected_names = {
        "aux-finite-verb": "Finite verb with the relation AuxY or AuxZ",
        "aux-governor-without-child": "AuxP or AuxC without a dependent",
        "aux-governs-conjuncts": "Non-COORD node governing several _CO conjuncts",
        "coord-discordant-conjuncts": "Different functions within the same coordination",
        "head-missing": "Syntactic head not declared",
        "agreement-modifier": "Possible failure of agreement in the modifier",
    }
    wrong = [name for name, expected in expected_names.items()
             if expected.split()[0] not in str(
                 RULE_CATALOG.get(name, {}).get("name_en", ""))]
    if wrong:
        say(f"NO   Checks whose name differs from the reference: {', '.join(wrong)}")
        problems.append("Their name differs from the reference table: " + ", ".join(wrong))
    else:
        say("YES  The six checks carry the names of the reference table")

    # No proposed correction on the ten polyfunctional particles.
    from greek_corpus_pipeline.rule_catalog import default_auto_apply

    particles = ["kai-relation", "mende-relation", "te-relation", "eta-relation",
                 "alla-relation", "oute-relation", "mede-relation",
                 "eite-relation", "kan-relation", "eper-relation"]
    auto = [name for name in particles if default_auto_apply(name)]
    if auto:
        say(f"NO   Particles that can still be corrected automatically: {', '.join(auto)}")
        problems.append("The particles must not have an automatic correction.")
    else:
        say("YES  No automatic correction on the particles")
except Exception as error:
    say(f"NO   Catalogue of the checks ({type(error).__name__}: {error})")

try:
    sys.path.insert(0, str(HERE))
    import gui_qt.pages.overview_page as overview

    has_button = "conllu" in Path(overview.__file__).read_text(encoding="utf-8")
    say(f"{'YES' if has_button else 'NO '}  CoNLL-U button on the Overview page")
    if not has_button:
        problems.append("The CoNLL-U button is not on the Overview page.")
except Exception as error:
    say(f"NO   Graphical interface ({type(error).__name__}: {error})")

rule("4. HOW LONG THIS MACHINE TAKES")
say("Looking for the latest saved analysis, to measure on your real data...")
try:
    import pandas as pd

    runs = sorted((HERE / "workspace" / "runs").glob("*/tokens.parquet"),
                  key=lambda path: path.stat().st_mtime, reverse=True)
    if not runs:
        say("No saved analysis: open the program, load a corpus, and run this again.")
    else:
        started = time.perf_counter()
        tokens = pd.read_parquet(runs[0])
        say(f"Test corpus      {runs[0].parent.name} — {len(tokens):,} tokens")
        say(f"  reading the table              {time.perf_counter() - started:6.1f} s")

        from greek_corpus_pipeline import agreement, orthography, syntax
        from greek_corpus_pipeline.postag import analyze_postags

        total = 0.0
        for label, function in (("morphological checks", analyze_postags),
                                ("tree checks", syntax.analyze_syntax),
                                ("text checks", orthography.analyze_orthography),
                                ("agreement checks", agreement.analyze_agreement)):
            started = time.perf_counter()
            function(tokens)
            elapsed = time.perf_counter() - started
            total += elapsed
            say(f"  {label:<30} {elapsed:6.1f} s")
        say(f"  {'TOTAL (without variation)':<30} {total:6.1f} s")

        rate = total / max(len(tokens), 1) * 100000
        say()
        say(f"Speed: {rate:.1f} seconds per hundred thousand tokens.")
        if rate > 12:
            say("This is slow. Send this file: it helps to find out why.")
        else:
            say("This is within the normal range for this code.")
except Exception:
    say("ERROR during the measurement:")
    say(traceback.format_exc())

rule("CONCLUSION")
if problems:
    say("PROBLEMS FOUND:")
    for number, problem in enumerate(problems, start=1):
        say(f"  {number}. {problem}")
else:
    say(f"No problem: the program is running the code of this "
        f"folder{f', version {declared_version()}' if declared_version() else ''}.")
    say("If it still seems slow, look at the times above and send them.")

say()
say(f"This text is saved in: {REPORT}")

REPORT.write_text(buffer.getvalue(), encoding="utf-8")
try:
    os.startfile(REPORT)                                  # noqa: S606 — Windows only
except Exception:
    pass
try:
    input("\nPress ENTER to close.")
except Exception:
    pass
