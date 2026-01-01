# -*- coding: utf-8 -*-
"""The Windows setup in front of an incomplete virtual environment.

A ``.venv`` folder left over from an interrupted installation may contain the
interpreter but not pip.  A ``setup.bat`` that considered it valid because it exists
would skip to the next step and call ``pip.exe``, which is not there: the message that
comes out would look like a defect of the program and would not be one.

Two tests, which answer two different questions.

The first looks at the text of ``setup.bat``: it is a static test because a batch file
runs on Windows and the suite may run elsewhere, but what it must guarantee — that the
check is there, that the recovery is there, that ``pip.exe`` is never called directly — can
be read in the source and cannot be removed without somebody noticing.

The second tests the strategy, not the text: it builds a virtual environment without
pip, which is exactly the situation to cover, and verifies that ``python -m pip`` fails,
that ``python -m ensurepip --upgrade`` puts it right and that after the recovery pip
answers.  If one day ``ensurepip`` stopped being the right way, this test would say so.
"""
from __future__ import annotations

import re
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.bat"


@pytest.fixture(scope="module")
def source() -> str:
    if not SETUP.exists():
        pytest.skip("setup.bat is not in this copy")
    return SETUP.read_text(encoding="utf-8")


def _code(source: str) -> str:
    """The batch code without the ``::`` comment lines."""
    return "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith("::"))


# ── the text of setup.bat ───────────────────────────────────────────────

def test_an_existing_venv_is_not_valid_just_because_it_exists(source):
    """First it looks whether the folder contains an interpreter, then whether that
    interpreter has pip."""
    assert "The environment already exists, it is reused." not in source, (
        "setup.bat trusts a .venv again just because the folder exists")
    assert r"if exist .venv\Scripts\python.exe" in source, (
        "the check that the .venv contains an interpreter is missing")


def test_pip_is_verified_before_it_is_used(source):
    assert re.search(r"python\.exe -m pip --version", source), (
        "setup.bat no longer verifies that pip answers before installing")


def test_if_pip_is_missing_ensurepip_is_tried(source):
    assert "-m ensurepip --upgrade" in source, (
        "the recovery attempt with ensurepip is missing")
    after = source.split("-m ensurepip --upgrade", 1)[1]
    assert "python.exe -m pip --version" in after, (
        "after ensurepip nobody checks again that pip answers: the recovery "
        "would be taken as successful without being verified")


def test_if_the_recovery_fails_it_stops_and_says_what_to_do(source):
    assert "delete the .venv folder" in source, (
        "the error message does not tell the user to recreate the environment")
    tail = source.split("delete the .venv folder", 1)[1]
    assert "exit /b 1" in tail.split("[3/3]")[0], (
        "after the message the setup goes on instead of stopping")


def test_pip_is_never_called_as_an_executable(source):
    assert "pip.exe" not in _code(source), (
        r"setup.bat calls pip.exe again: use .venv\Scripts\python.exe -m pip")


def test_the_setup_works_in_the_folder_of_the_file(source):
    """From a shortcut the launch folder is not that of the program."""
    assert 'cd /d "%~dp0"' in source


def test_no_labels_and_no_goto(source):
    """A .bat with a goto is a trap when the line endings are wrong: there are none."""
    assert "goto " not in source.lower()
    assert not re.search(r"(?m)^\s*:[A-Za-z]", source)


def test_the_step_markers_are_consistent(source):
    """The markers announce the same total: [1/3], [2/3], [3/3]."""
    markers = re.findall(r"\[(\d)/(\d)\]", _code(source))
    assert markers == [("1", "3"), ("2", "3"), ("3", "3")], (
        f"the step markers of setup.bat are not consistent: {markers}")


def test_the_launchers_are_written_in_ascii(source):
    """cmd reads the file with the console code page: a non-ASCII character in an
    ``echo`` line would come out garbled on most Windows installations."""
    for name in ("setup.bat", "run.bat", "CHECK_INSTALL.bat"):
        path = ROOT / name
        if path.exists():
            text = path.read_bytes()
            assert all(byte < 128 for byte in text), (
                f"{name} contains a character outside ASCII")


# ── the strategy, tried on a real environment ───────────────────────────

def test_ensurepip_recovers_an_environment_without_pip(tmp_path):
    """The case of an incomplete environment, reproduced and repaired.

    It does not test ``setup.bat`` — that is Windows — but the strategy that the file
    adopts: a virtual environment without pip exists, ``python -m pip`` fails on it,
    ``ensurepip`` repairs it.
    """
    environment = tmp_path / ".venv"
    venv.create(environment, with_pip=False)

    folder = "Scripts" if sys.platform == "win32" else "bin"
    executable = environment / folder / ("python.exe" if sys.platform == "win32"
                                         else "python")
    assert executable.exists(), "the environment was created but has no interpreter"

    def pip_answers() -> bool:
        return subprocess.run([str(executable), "-m", "pip", "--version"],
                              capture_output=True).returncode == 0

    assert not pip_answers(), (
        "the environment was supposed to have no pip: the case to reproduce is missing")

    recovery = subprocess.run([str(executable), "-m", "ensurepip", "--upgrade"],
                              capture_output=True)
    if recovery.returncode != 0:
        pytest.skip("ensurepip is not available in this Python: it is the case in "
                    "which setup.bat stops and asks to recreate the .venv, and it "
                    "is the intended behaviour")

    assert pip_answers(), (
        "after ensurepip pip still does not answer: the recovery strategy of "
        "setup.bat no longer works and the file has to be reviewed")


# ── the models: really optional, not just in words ──────────────────────

def test_the_models_are_not_installed_without_asking(source):
    """The setup does not install the models while calling them optional.

    README and INSTRUCTIONS declare Stanza and UDPipe optional, so the setup asks, and
    the empty answer counts as no.
    """
    code = _code(source)
    assert "set /p" in code, (
        "setup.bat no longer asks whether to install the models: either it always "
        "installs them or it never does, and in both cases the documentation does "
        "not match")
    question = code.split("set /p", 1)[1].split("\n", 1)[0]
    assert "enter = no" in question, (
        "the empty answer must mean no: a careless Enter must not download "
        "a few hundred megabytes")


def test_the_models_are_installed_with_the_declared_extra(source):
    """One place declares the versions: pyproject.toml.

    The setup must not install “stanza” and “ufal.udpipe>=1.3” by hand while
    pyproject.toml declares the “models” extra with “ufal.udpipe>=1.3.1.1”: two
    different constraints for the same dependency, neither wrong in itself — what is
    wrong is that there are two.
    """
    assert 'pip install -e ".[models]"' in source, (
        "the models are no longer installed through the declared extra")
    assert "install stanza" not in _code(source), (
        "setup.bat installs stanza outside the extra again, and with it the "
        "version constraint lives in two places")


def _answer_accepted(source: str, typed: str) -> bool:
    """What cmd would do with what the user has typed.

    The initial value and the condition are read from the file, and the semantics of
    ``set /p`` — which leaves the variable as it was if nothing is typed — and that of
    ``if /i "%VAR:~0,1%"=="y"`` are reproduced.
    """
    start = ""
    for line in source.splitlines():
        if line.strip().startswith('set "MODELS='):
            start = line.split("=", 1)[1].rstrip().rstrip('"')
    value = typed if typed else start          # set /p with enter
    tests = [line for line in source.splitlines()
             if line.lstrip().startswith("if /i") and "MODELS:~0,1" in line]
    assert tests, "the condition no longer looks at the first letter"
    letters = {line.split('=="')[1].split('"')[0].lower() for line in tests}
    return value[:1].lower() in letters


@pytest.mark.parametrize("typed, expected", [
    ("", False),        # enter: stays no, and it is the most important point
    ("y", True),
    ("Y", True),
    ("yes", True),
    ("YES", True),
    ("Yes", True),
    ("n", False),
    ("no", False),
    ("N", False),
])
def test_the_accepted_affirmative_answers(source, typed, expected):
    """“y” and “yes” are both accepted, and Enter keeps meaning no."""
    assert _answer_accepted(source, typed) is expected, (
        f"typing {typed!r} the setup "
        f"{'does not install' if expected else 'installs'} the models")


def test_enter_means_no_because_the_variable_starts_as_no(source):
    """``set /p`` leaves the variable alone on enter: the no is the initial value.

    With ``set "MODELS="`` the variable is removed, and ``%MODELS:~0,1%`` on a
    non-existent variable does not expand at all: the condition stays false for
    accidental reasons instead of declared ones.  Starting from “n” says the same
    thing in a way that can be read.
    """
    start = [line for line in source.splitlines()
             if line.strip().startswith('set "MODELS=')]
    assert start, "the starting value of the answer is missing"
    assert start[-1].strip() != 'set "MODELS="', (
        "the variable starts empty: Enter works by accident, not by choice")


def test_whoever_says_no_gets_the_command_to_do_it_later(source):
    branch = source.split("set /p", 1)[1]
    assert branch.count('pip install -e ".[models]"') >= 2, (
        "the command to install the models later must appear both when the "
        "installation fails and when the user answers no")


# ── the three .bat files work on their own folder ───────────────────────

@pytest.mark.parametrize("name", ["setup.bat", "run.bat", "CHECK_INSTALL.bat"])
def test_every_bat_moves_to_its_own_folder(name):
    """From a shortcut on the desktop the launch folder is another one.

    Without this line setup.bat would create the environment elsewhere, run.bat would
    look for a .venv that is not there and CHECK_INSTALL.bat would say that the program
    is not installed.  Three different symptoms of the same cause.
    """
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} is not in this copy")
    assert 'cd /d "%~dp0"' in path.read_text(encoding="utf-8"), (
        f"{name} works on the current directory instead of its own")


@pytest.mark.parametrize("name", ["setup.bat", "run.bat", "CHECK_INSTALL.bat"])
def test_every_bat_ends_its_lines_with_cr_lf(name):
    """The launchers are Windows batch files and end every line with CR LF.

    ``.gitattributes`` keeps them so, and ``SHA256SUMS`` lists their bytes: an editor or a
    tool that rewrote them with LF alone would change both the file and its checksum.
    """
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} is not in this copy")
    data = path.read_bytes()
    assert data.endswith(b"\r\n"), f"{name} does not end with CR LF"
    assert data.count(b"\n") == data.count(b"\r\n"), f"{name}: a line ends with LF alone"
