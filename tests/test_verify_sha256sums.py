# -*- coding: utf-8 -*-
"""The script that checks the files of the package against ``SHA256SUMS``
(``reproducibility/scripts/verify_sha256sums.py``).

It is the first thing a reader runs on a copy of the package, so it has to say "identical" when the copy is the
package and name the file when it is not. The tests build a small package of their own and change it in each of
the ways that matter: a file with other content (also a text file whose line endings were converted on the way),
a file that is missing, a file that is not in the list, and the files that the program, the tests and git leave in
the folder (the caches, the virtual environment, the workspace, the two log files, and the folder ``.git`` that a
clone of the repository carries), which must not count.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "verify_sha256sums.py"

FILES = {
    "README.md": b"A package\n",
    "src/module.py": b"VALUE = 1\n",
    "setup.bat": b"@echo off\r\necho hello\r\n",
}


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("verify_sha256sums_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def package(tmp_path) -> Path:
    """A package of three files and the list of their sums, in the format of the ``sha256sum`` program."""
    root = tmp_path / "package"
    for name, data in FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    lines = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(FILES.items()))
    (root / "SHA256SUMS").write_bytes(lines.encode("utf-8"))
    return root


def run(tool, root, capsys):
    status = tool.main([str(root)])
    return status, capsys.readouterr().out


def test_the_package_as_it_was_listed_is_identical(tool, package, capsys):
    status, said = run(tool, package, capsys)
    assert status == 0, said
    assert "3 files listed in SHA256SUMS" in said
    assert "RESULT: all files present and identical, nothing unlisted" in said


def test_a_file_with_other_content_is_named(tool, package, capsys):
    (package / "src" / "module.py").write_bytes(b"VALUE = 2\n")
    status, said = run(tool, package, capsys)
    assert status == 1
    assert "DIFFERENT content: src/module.py" in said and "1 different, 0 missing, 0 not listed" in said


def test_a_text_file_whose_line_endings_were_converted_is_different(tool, package, capsys):
    """What a version-control system does with ``core.autocrlf`` and no ``.gitattributes``: it is a difference."""
    (package / "README.md").write_bytes(b"A package\r\n")
    status, said = run(tool, package, capsys)
    assert status == 1 and "DIFFERENT content: README.md" in said


def test_a_file_that_is_missing_is_named(tool, package, capsys):
    (package / "src" / "module.py").unlink()
    status, said = run(tool, package, capsys)
    assert status == 1
    assert "MISSING: src/module.py" in said and "0 different, 1 missing, 0 not listed" in said


def test_a_file_that_is_not_in_the_list_is_named(tool, package, capsys):
    (package / "notes.txt").write_bytes(b"left by someone\n")
    status, said = run(tool, package, capsys)
    assert status == 1
    assert "NOT LISTED: notes.txt" in said and "0 different, 0 missing, 1 not listed" in said


def test_what_the_program_the_tests_and_git_leave_in_the_folder_is_not_counted(tool, package, capsys):
    leftovers = ["src/__pycache__/module.cpython-314.pyc", "src/module.pyc", ".pytest_cache/README.md",
                 ".venv/pyvenv.cfg", "workspace/runs/run-1/tokens.parquet", "pipeline_errors.log",
                 "CHECK_INSTALL_result.txt", ".git/HEAD", ".git/objects/ab/cdef", ".git/refs/heads/main"]
    for name in leftovers:
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not part of the package\n")
    status, said = run(tool, package, capsys)
    assert status == 0, said
    assert "nothing unlisted" in said


def test_a_log_file_that_is_not_at_the_root_is_counted(tool, package, capsys):
    """Only the two files that the program writes at the root of its folder are set aside."""
    (package / "docs").mkdir()
    (package / "docs" / "pipeline_errors.log").write_bytes(b"x\n")
    status, said = run(tool, package, capsys)
    assert status == 1 and "NOT LISTED: docs/pipeline_errors.log" in said


def test_a_malformed_line_stops_the_check_with_a_message(tool, package):
    (package / "SHA256SUMS").write_bytes(b"not a sum  README.md\n")
    with pytest.raises(SystemExit) as stopped:
        tool.main([str(package)])
    assert "line 1" in str(stopped.value)


def test_a_folder_without_the_list_is_said_and_help_is_not_an_error(tool, tmp_path, capsys):
    assert tool.main([str(tmp_path)]) == 2
    assert "SHA256SUMS" in capsys.readouterr().out
    assert tool.main(["--help"]) == 0
