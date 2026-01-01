#!/usr/bin/env python
"""Check the files of this package against the list of SHA-256 sums that came with it.

``SHA256SUMS`` (in the folder of the package, next to ``README.md``) lists the SHA-256 of every
file of the package except itself, one per line, in the format of the ``sha256sum`` program:
64 hexadecimal characters, two spaces, the path with ``/`` as separator.  This script reads that
list and reports

* the files that are listed and whose content is different,
* the files that are listed and missing,
* the files that are in the folder and not in the list (what the program, the tests and git write in the
  folder is not counted: the caches ``__pycache__`` and ``.pytest_cache``, the virtual environment ``.venv``, the
  folder ``workspace``, the folder ``.git`` of a clone, and the two files ``pipeline_errors.log`` and
  ``CHECK_INSTALL_result.txt``, which ``.gitignore`` also names).

It uses the standard library only and does not need the program to be installed.  Line endings
are not normalised: the sums are those of the bytes of the files as they are in the archive, so
a text file that was converted on extraction (for instance by a tool that changes ``\\n`` into
``\\r\\n``) is reported as different, which is correct.

usage:
    python reproducibility/scripts/verify_sha256sums.py [PACKAGE_FOLDER]

The exit status is 0 when every listed file is present and identical and there is no unlisted
file, 1 otherwise.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

LIST_NAME = "SHA256SUMS"
SKIPPED_DIRECTORIES = {"__pycache__", ".pytest_cache", "workspace", ".venv", ".git"}
SKIPPED_FILES = {"pipeline_errors.log", "CHECK_INSTALL_result.txt"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_list(path: Path) -> dict[str, str]:
    """{relative path: sum}; a malformed line stops the check with a clear message."""
    listed: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if len(digest) != 64 or not separator or not name:
            raise SystemExit(f"{path}: line {number} is not '<64 hex characters>  <path>'")
        listed[name] = digest.lower()
    return listed


def files_present(root: Path) -> set[str]:
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIPPED_DIRECTORIES for part in relative.parts[:-1]):
            continue
        if relative.parts[-1].endswith(".pyc") or relative.as_posix() == LIST_NAME:
            continue
        if len(relative.parts) == 1 and relative.parts[0] in SKIPPED_FILES:
            continue
        found.add(relative.as_posix())
    return found


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) > 1 or (arguments and arguments[0] in {"-h", "--help"}):
        print(__doc__)
        return 0 if arguments and arguments[0] in {"-h", "--help"} else 2
    root = Path(arguments[0]) if arguments else Path(__file__).resolve().parents[2]
    list_path = root / LIST_NAME
    if not list_path.is_file():
        print(f"{list_path} not found: give the folder of the package as the argument")
        return 2

    listed = read_list(list_path)
    different, missing = [], []
    for name, expected in sorted(listed.items()):
        path = root / name
        if not path.is_file():
            missing.append(name)
        elif sha256_of(path) != expected:
            different.append(name)
    unlisted = sorted(files_present(root) - set(listed))

    print(f"{len(listed)} files listed in {LIST_NAME}")
    for title, names in (("DIFFERENT content", different), ("MISSING", missing), ("NOT LISTED", unlisted)):
        for name in names:
            print(f"  {title}: {name}")
    ok = not (different or missing or unlisted)
    print("RESULT: all files present and identical, nothing unlisted" if ok else
          f"RESULT: {len(different)} different, {len(missing)} missing, {len(unlisted)} not listed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
