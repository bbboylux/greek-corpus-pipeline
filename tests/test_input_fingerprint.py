# -*- coding: utf-8 -*-
"""The input-fingerprint script of the reproducibility folder.

A run of the program on Gorman or on Pedalion reads a whole folder, so for those two strata the
fingerprint is that of every XML file under the folder, and a stray file must be noticed. A run
on one of the four GLAUx strata reads only the files that the list of the forty texts names for
that stratum, so one folder that holds the forty files (or a whole copy of the ``xml`` folder of
GLAUx) has to serve the four strata one after the other: files of the other strata are not
"extra" files of this one.

The tests build small corpora of their own and a reference of their own; one test also checks that
the two reference tables of the package (``inputs.csv`` and ``inputs_files.csv``) agree.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "input_fingerprint.py"


def load_script():
    """A fresh copy of the script as a module (so that changing ``REFERENCE`` leaks nowhere)."""
    spec = importlib.util.spec_from_file_location("input_fingerprint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_fingerprint(files: dict[str, bytes]) -> str:
    """The fingerprint as the supplement defines it, computed here from the definition."""
    lines = "\n".join(f"{name}:{digest(data)}" for name, data in sorted(files.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()[:16]


GORMAN = {"g-1.xml": b"<treebank>gorman one</treebank>", "g-2.xml": b"<treebank>gorman two</treebank>"}
AUTO = {"0001-001.xml": b"<TEI>auto one</TEI>", "0002-001.xml": b"<TEI>auto two</TEI>"}
MANUAL = {"0003-001.xml": b"<TEI>manual one</TEI>"}
IN_NO_STRATUM = {"0099-001.xml": b"<TEI>a text of nobody's sample</TEI>"}


@pytest.fixture()
def tool(tmp_path, monkeypatch):
    """The script, reading a reference of three strata made for the test."""
    reference = tmp_path / "reference"
    reference.mkdir()
    strata = {"gorman": GORMAN, "glaux_auto": AUTO, "glaux_man": MANUAL}
    with (reference / "inputs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["stratum", "xml_files", "bytes", "input_fingerprint"])
        for stratum, files in strata.items():
            writer.writerow([stratum, len(files), sum(len(d) for d in files.values()), input_fingerprint(files)])
    with (reference / "inputs_files.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["stratum", "file", "bytes", "sha256"])
        for stratum, files in strata.items():
            for name, data in sorted(files.items()):
                writer.writerow([stratum, name, len(data), digest(data)])
    module = load_script()
    monkeypatch.setattr(module, "REFERENCE", reference)
    return module


def put(folder: Path, files: dict[str, bytes], where: str = "") -> None:
    target = folder / where if where else folder
    target.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (target / name).write_bytes(data)


def run(tool, capsys, *arguments) -> tuple[int, str]:
    status = tool.main([str(a) for a in arguments])
    return status, capsys.readouterr().out


def test_a_folder_with_the_files_of_every_glaux_stratum_serves_each_of_them(tool, tmp_path, capsys):
    """The reviewer's case: one folder of forty files, four strata checked in turn."""
    folder = tmp_path / "glaux"
    put(folder, AUTO, "xml")
    put(folder, MANUAL, "xml/more")
    put(folder, IN_NO_STRATUM, "xml")
    status, out = run(tool, capsys, folder, "--stratum", "glaux_auto", "--diff")
    assert status == 0, out
    assert "MATCH" in out and "DIFFERENT" not in out
    assert f"fingerprint: {input_fingerprint(AUTO)}" in out
    assert "left out: 2 other XML file(s)" in out
    assert "1 named in another GLAUx stratum, 1 in none" in out
    status, out = run(tool, capsys, folder, "--stratum", "glaux_man", "--diff")
    assert status == 0, out
    assert "MATCH" in out and "extra" not in out
    assert "left out: 3 other XML file(s)" in out


def test_without_a_stratum_the_whole_folder_is_fingerprinted(tool, tmp_path, capsys):
    folder = tmp_path / "glaux"
    put(folder, AUTO)
    put(folder, MANUAL)
    status, out = run(tool, capsys, folder)
    assert status == 0
    assert f"fingerprint: {input_fingerprint({**AUTO, **MANUAL})}" in out
    assert "left out" not in out


def test_a_changed_glaux_file_is_reported_by_name(tool, tmp_path, capsys):
    folder = tmp_path / "glaux"
    put(folder, {**AUTO, "0002-001.xml": b"<TEI>auto two, edited</TEI>"})
    put(folder, MANUAL)
    status, out = run(tool, capsys, folder, "--stratum", "glaux_auto", "--diff")
    assert status == 1
    assert "DIFFERENT" in out
    assert "changed : 0002-001.xml" in out and "changed : 0001-001.xml" not in out
    assert "missing" not in out and "extra" not in out


def test_a_missing_glaux_file_is_reported_by_name(tool, tmp_path, capsys):
    folder = tmp_path / "glaux"
    put(folder, {"0001-001.xml": AUTO["0001-001.xml"]})
    put(folder, MANUAL)
    status, out = run(tool, capsys, folder, "--stratum", "glaux_auto", "--diff")
    assert status == 1
    assert "missing : 0002-001.xml" in out
    assert "files: 1 " in out


def test_gorman_and_pedalion_stay_strict_about_files_that_do_not_belong(tool, tmp_path, capsys):
    """The program reads the whole folder of those two strata, so a stray XML file changes the input."""
    folder = tmp_path / "gorman"
    put(folder, GORMAN)
    status, out = run(tool, capsys, folder, "--stratum", "gorman", "--diff")
    assert status == 0 and "MATCH" in out
    put(folder, {"stray.xml": b"<x/>"}, "backup")
    status, out = run(tool, capsys, folder, "--stratum", "gorman", "--diff")
    assert status == 1
    assert "DIFFERENT" in out and "extra   : stray.xml" in out
    assert "left out" not in out


def test_two_files_of_the_same_name_are_an_error_only_when_they_are_read(tool, tmp_path, capsys):
    folder = tmp_path / "glaux"
    put(folder, AUTO, "xml")
    put(folder, MANUAL, "xml")
    put(folder, {"0001-001.xml": AUTO["0001-001.xml"]}, "copy")             # a second copy of a file of the stratum
    with pytest.raises(SystemExit) as error:
        tool.main([str(folder), "--stratum", "glaux_auto"])
    assert "two files named 0001-001.xml" in str(error.value)
    # the same duplicate does not matter to the stratum that does not read that file
    status, out = run(tool, capsys, folder, "--stratum", "glaux_man", "--diff")
    assert status == 0 and "MATCH" in out


def test_an_unknown_stratum_and_a_folder_that_is_not_there_are_errors(tool, tmp_path):
    put(tmp_path / "xml", GORMAN)
    with pytest.raises(SystemExit) as error:
        tool.main([str(tmp_path / "xml"), "--stratum", "no_such_stratum"])
    assert "unknown stratum" in str(error.value)
    with pytest.raises(SystemExit) as error:
        tool.main([str(tmp_path / "absent"), "--stratum", "gorman"])
    assert "is not a folder" in str(error.value)


def test_the_two_reference_tables_of_the_package_agree():
    """``inputs.csv`` (one row per stratum) must be what ``inputs_files.csv`` (one row per file) adds up to."""
    tool = load_script()
    summary = {row["stratum"]: row for row in tool.read_csv("inputs.csv")}
    per_file: dict[str, dict[str, tuple[int, str]]] = {}
    for row in tool.read_csv("inputs_files.csv"):
        per_file.setdefault(row["stratum"], {})[row["file"]] = (int(row["bytes"]), row["sha256"])
    assert set(summary) == set(per_file) == {"gorman", "pedalion", "glaux_auto", "glaux_man",
                                             "glaux_conf_auto", "glaux_conf_man"}
    for stratum, files in per_file.items():
        assert len(files) == int(summary[stratum]["xml_files"]), stratum
        assert sum(size for size, _ in files.values()) == int(summary[stratum]["bytes"]), stratum
        assert tool.fingerprint(files) == summary[stratum]["input_fingerprint"], stratum
    names = [name for files in per_file.values() for name in files]
    assert len(names) == len(set(names)) == 238, "a file name belongs to one stratum only"
