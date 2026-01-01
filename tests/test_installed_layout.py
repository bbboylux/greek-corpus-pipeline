# -*- coding: utf-8 -*-
"""The program in the layout of an installed wheel, not in that of the source tree.

In the source tree the data folder is at the root of the project, two levels above the package
(``src/greek_corpus_pipeline``). In an installed copy ``data`` is *inside* the package
(``greek_corpus_pipeline/data``, by the ``force-include`` of ``pyproject.toml``) and the interface
package ``gui_qt``, whose worker functions the command line shares, sits beside it in
``site-packages``. A package that looked for its lists of lemmas only in the first of
the two places would stop, once installed, at import time with "the list
'numerali-indeclinabili' does not exist".

The tests run the code from a copy laid out as a wheel lays it out, from a folder that is not the
project's: first a copy made by the test, then the wheel itself, which is built when the tool that builds
it (``hatchling``, in the ``dev`` extra) is there. They check where the lists and the data are found, that
the command line runs, that it gives the same tables as in the source tree, and that the error log of
the program is written in the folder where the program is run and not inside ``site-packages``.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "reproducibility" / "scripts"

# pandas 2.2.0 (the lowest version the package admits) warns, when it reads a parquet file written with pyarrow 14, about a
# call that pyarrow itself makes ("Passing a BlockManager to DataFrame is deprecated"): it is the libraries' business, not
# the program's, and later versions of pandas do not say it. Only that message is ignored.
pytestmark = pytest.mark.filterwarnings("ignore:Passing a BlockManager to DataFrame:DeprecationWarning")


XML = """<?xml version="1.0" encoding="UTF-8"?>
<treebank version="1.1">
  <sentence id="1" document_id="test-doc" subdoc="1">
    <word id="1" form="τὴν" lemma="ὁ" postag="l-s---fa-" relation="ATR" head="2"/>
    <word id="2" form="πόλιν" lemma="πόλις" postag="n-s---fa-" relation="OBJ" head="3"/>
    <word id="3" form="ἐφύλαττον" lemma="φυλάσσω" postag="v3piia---" relation="PRED" head="0"/>
    <word id="4" form="οἱ" lemma="ὁ" postag="l-p---mn-" relation="ATR" head="5"/>
    <word id="5" form="στρατιῶται" lemma="στρατιώτης1" postag="n-p---mn-" relation="SBJ" head="3"/>
  </sentence>
  <sentence id="2" document_id="test-doc" subdoc="1">
    <word id="1" form="καὶ" lemma="καί" postag="c--------" relation="AuxY" head="3"/>
    <word id="2" form="οἱ" lemma="ὁ" postag="l-p---mn-" relation="ATR" head="3"/>
    <word id="3" form="ἄνδρες" lemma="ἀνήρ" postag="n-p---mn" relation="SBJ" head="4"/>
    <word id="4" form="ἦλθον" lemma="ἔρχομαι" postag="v3plia---" relation="PRED" head="0"/>
  </sentence>
</treebank>
"""

#: What the subprocess reports about the copy of the program it has imported.
PROBE = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import greek_corpus_pipeline
from greek_corpus_pipeline import corpus_metadata, resources
import gui_qt.workers as workers
print(json.dumps({
    "package": str(Path(greek_corpus_pipeline.__file__).resolve()),
    "lists": str(resources.DIRECTORY.resolve()),
    "data": str(Path(corpus_metadata.data_dir()).resolve()),
    "available": resources.available(),
    "workers": str(Path(workers.__file__).resolve()),
    "numerals": sorted(resources.entries("numerali-indeclinabili"))[:3],
}))
"""

#: The command line, run as the installed command would run it.
CLI = r"""
import sys
sys.path.insert(0, sys.argv[1])
from greek_corpus_pipeline.cli import main
sys.exit(main(sys.argv[2:]))
"""


def clean_environment() -> dict[str, str]:
    """The environment of a person who has installed the program: no PYTHONPATH pointing at the source."""
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    environment["QT_QPA_PLATFORM"] = "offscreen"
    return environment


def python(code: str, *arguments: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code, *arguments], cwd=cwd, env=clean_environment(),
                          capture_output=True, text=True, timeout=600)


def lay_out_like_a_wheel(target: Path) -> Path:
    """What ``pip install`` leaves in ``site-packages``: the package with its data inside, and ``gui_qt``."""
    site = target / "site-packages"
    shutil.copytree(ROOT / "src" / "greek_corpus_pipeline", site / "greek_corpus_pipeline",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data", site / "greek_corpus_pipeline" / "data")
    shutil.copytree(ROOT / "gui_qt", site / "gui_qt", ignore=shutil.ignore_patterns("__pycache__"))
    return site


def built_wheel(target: Path) -> Path:
    pytest.importorskip("hatchling", reason="the wheel is built with hatchling (the dev extra installs it)")
    done = subprocess.run([sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(target / "dist")],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    (wheel,) = (target / "dist").glob("*.whl")
    return wheel


@pytest.fixture(scope="module", params=["a copy laid out as a wheel", "the wheel built from pyproject.toml"])
def site(request, tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("installed")
    if request.param.startswith("a copy"):
        return lay_out_like_a_wheel(target)
    wheel = built_wheel(target)
    unpacked = target / "site-packages"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(unpacked)
    return unpacked


@pytest.fixture()
def elsewhere(tmp_path) -> Path:
    """A folder that is not the project's, where the program is run from."""
    folder = tmp_path / "somewhere_else"
    folder.mkdir()
    return folder


def test_the_lists_and_the_data_are_found_inside_the_installed_package(site, elsewhere):
    done = python(PROBE, str(site), cwd=elsewhere)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout.strip().splitlines()[-1])
    package = site / "greek_corpus_pipeline"
    assert Path(report["package"]).is_relative_to(site.resolve())
    assert Path(report["lists"]) == (package / "data" / "liste").resolve()
    assert Path(report["data"]) == (package / "data").resolve()
    assert "numerali-indeclinabili" in report["available"] and len(report["available"]) >= 10
    assert report["numerals"], "the list of the indeclinable numerals must not be empty"
    assert Path(report["workers"]) == (site / "gui_qt" / "workers.py").resolve()


def test_the_error_log_is_written_where_the_program_is_run_not_inside_site_packages(site, elsewhere):
    done = python(PROBE, str(site), cwd=elsewhere)
    assert done.returncode == 0, done.stderr
    assert (elsewhere / "pipeline_errors.log").is_file()
    assert not (site / "pipeline_errors.log").exists() and not (site.parent / "pipeline_errors.log").exists()


def test_the_command_line_runs_from_the_installed_layout_and_gives_the_tables_of_the_source_tree(
        site, elsewhere, tmp_path):
    source = tmp_path / "xml"
    source.mkdir()
    (source / "doc.xml").write_text(XML, encoding="utf-8")
    runs = {}
    # the installed copy; and the source tree, whose root (for ``gui_qt``) ``cli.py`` puts on the path itself
    for label, path in (("installed", site), ("source", ROOT / "src")):
        workspace = tmp_path / f"workspace-{label}"
        done = python(CLI, str(path), "--source", str(source), "--corpus-name", "check", "--workspace",
                      str(workspace), "--detect", "--variation", "--quiet", cwd=elsewhere)
        assert done.returncode == 0, f"{label}: {done.stdout[-800:]}\n{done.stderr[-800:]}"
        (run,) = (workspace / "runs").iterdir()
        assert (run / "tokens.parquet").is_file() and (run / "arcs.parquet").is_file(), label
        runs[label] = run
    spec = importlib.util.spec_from_file_location("compare_run_folders_installed", SCRIPTS / "compare_run_folders.py")
    compare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compare)
    tally = compare.compare_folders(runs["installed"], runs["source"], exact=True)
    assert tally.compared >= 2 and tally.different == 0 and tally.missing == 0
    assert not tally.required_absent


def test_the_wheel_declares_the_command_and_carries_what_the_program_reads(tmp_path):
    wheel = built_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        entry_points = next(archive.read(n).decode("utf-8") for n in names if n.endswith("entry_points.txt"))
    assert "greek-corpus-cli = greek_corpus_pipeline.cli:main" in entry_points
    for needed in ("greek_corpus_pipeline/cli.py", "greek_corpus_pipeline/data/catalogo_controlli.csv",
                   "greek_corpus_pipeline/data/liste/numerali-indeclinabili.json",
                   "gui_qt/workers.py", "gui_qt/__init__.py"):
        assert needed in names, needed
    assert not any(n.startswith(("tests/", "workspace/", "reproducibility/")) for n in names)
