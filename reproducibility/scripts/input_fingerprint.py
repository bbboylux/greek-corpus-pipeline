#!/usr/bin/env python
"""Fingerprint of the XML files that a run reads (Table S11.2 of the supplement).

The fingerprint is the first sixteen hexadecimal characters of the SHA-256 of the
text made of one line "file name:SHA-256 of the file" per XML file, sorted by
file name and joined by a line break (no final line break).

usage:
    python input_fingerprint.py FOLDER                     print files, bytes, fingerprint
    python input_fingerprint.py FOLDER --stratum gorman    ... and compare with reference/inputs.csv
    python input_fingerprint.py FOLDER --stratum gorman --diff
                                                           ... and, if it differs, list the files that
                                                           are missing, extra or different with respect
                                                           to reference/inputs_files.csv

The XML files are searched in FOLDER and its subfolders; two files with the same
name are an error. The strata are: gorman, pedalion, glaux_auto, glaux_man,
glaux_conf_auto, glaux_conf_man.

**Which files count.** The program reads a whole folder for Gorman and for Pedalion, so for
these two strata the fingerprint is that of *every* XML file under FOLDER: point it at the
folder of the XML files (``public/xml`` of the repository), and an XML file that does not
belong there makes the result DIFFERENT. For the four GLAUx strata the program reads only the
files that ``data/glaux_sample.csv`` names for the stratum, so FOLDER may hold more than that:
the files taken are those that ``reference/inputs_files.csv`` lists for the stratum, and the
other XML files under FOLDER are left out and counted. One folder with the forty files, or a
copy of the whole ``xml`` folder of GLAUx, therefore serves the four GLAUx strata, one after
the other. A file of the stratum that is not under FOLDER is reported as missing; two files of
the stratum with the same name are an error, wherever they are.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "reference"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_glaux(stratum: str) -> bool:
    """The four GLAUx strata are read by name from a list; Gorman and Pedalion as a whole folder."""
    return stratum.startswith("glaux_")


def scan(folder: Path, only: set[str] | None = None) -> tuple[dict[str, tuple[int, str]], list[str]]:
    """The XML files under *folder*: (name -> (bytes, SHA-256), the names that were left out).

    With *only*, just the files with those names are taken (and read); every other XML file is
    left out, and returned by name. Two taken files with the same name are an error.
    """
    found: dict[str, tuple[int, str]] = {}
    left_out: list[str] = []
    for path in sorted(folder.rglob("*.xml")):
        if not path.is_file():
            continue
        if only is not None and path.name not in only:
            left_out.append(path.name)
            continue
        if path.name in found:
            raise SystemExit(f"two files named {path.name} under {folder}")
        found[path.name] = (path.stat().st_size, sha256(path))
    return found, left_out


def fingerprint(files: dict[str, tuple[int, str]]) -> str:
    lines = [f"{name}:{digest}" for name, (_, digest) in sorted(files.items())]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def read_csv(name: str) -> list[dict[str, str]]:
    with (REFERENCE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--stratum")
    parser.add_argument("--diff", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.folder.is_dir():
        raise SystemExit(f"{arguments.folder} is not a folder")

    expected = None
    if arguments.stratum:
        strata = {r["stratum"]: r for r in read_csv("inputs.csv")}
        expected = strata.get(arguments.stratum)
        if expected is None:
            raise SystemExit(f"unknown stratum {arguments.stratum!r}; the strata are: {', '.join(strata)}")
    table = read_csv("inputs_files.csv") if arguments.stratum else []
    reference = {r["file"]: r for r in table if r["stratum"] == arguments.stratum}

    only = set(reference) if arguments.stratum and is_glaux(arguments.stratum) else None
    files, left_out = scan(arguments.folder, only)
    total = sum(size for size, _ in files.values())
    value = fingerprint(files)
    print(f"files: {len(files)}   bytes: {total:,}   fingerprint: {value}")
    if left_out:
        elsewhere = {r["file"] for r in table if is_glaux(r["stratum"]) and r["stratum"] != arguments.stratum}
        named = sum(1 for name in left_out if name in elsewhere)
        print(f"left out: {len(left_out)} other XML file(s), which {arguments.stratum} does not read "
              f"({named} named in another GLAUx stratum, {len(left_out) - named} in none)")
    if expected is None:
        return 0

    same = (value == expected["input_fingerprint"] and len(files) == int(expected["xml_files"])
            and total == int(expected["bytes"]))
    print(f"reference: files {expected['xml_files']}  bytes {int(expected['bytes']):,}  "
          f"fingerprint {expected['input_fingerprint']}")
    print("MATCH" if same else "DIFFERENT")
    if not same and arguments.diff:
        for name in sorted(set(reference) - set(files)):
            print(f"  missing : {name}")
        for name in sorted(set(files) - set(reference)):
            print(f"  extra   : {name}")
        for name in sorted(set(files) & set(reference)):
            if files[name][1] != reference[name]["sha256"]:
                print(f"  changed : {name}  (bytes {files[name][0]:,} against {int(reference[name]['bytes']):,})")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
