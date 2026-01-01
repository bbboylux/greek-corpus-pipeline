#!/usr/bin/env python
"""Redo the two GLAUx draws of Supplement S9 and compare them with ``data/glaux_sample.csv``.

The program does not perform the draw: it reads its result, the list of forty texts in
``data/glaux_sample.csv``. This script performs the procedure of S9 with the standard
library only (no pandas, no installation needed) from the two files that the package
distributes:

  1. pool: the rows of ``data/glaux_metadata.csv`` whose TLG author number (the first
     four digits of ``document_id``) is not one of the 37 numbers of the authors of
     Gorman and Pedalion, and whose declared size is between 5,000 and 60,000 tokens;
  2. the 37 numbers are read from ``tests/test_pipeline_base.py`` (the test of the
     program on the absence of overlap), where S9 says they are listed;
  3. first sample: ``random.seed(20260814)``, ``random.sample(pool, 20)``, the pool
     in the order of the metadata table;
  4. confirmation sample: ``random.seed(20260815)``, ``random.sample(rest, 20)``, the
     318 texts that remain, sorted by identifier.

It prints each number next to the one that S9 gives, and whether the twenty texts of
each draw are those of ``data/glaux_sample.csv``. The exit status is 0 when everything is
as S9 states. Only the sequence of ``random()`` is guaranteed to be the same for the same
seed across versions of Python, not that of ``sample()``: the version of Python is printed.

usage:
    python glaux_sample_draw.py
"""
from __future__ import annotations

import ast
import csv
import random
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]
TEST_FILE = "test_nessun_autore_del_campione_sta_in_gorman_o_pedalion"


def read(name: str) -> list[dict[str, str]]:
    with (PACKAGE / "data" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def authors_in_the_test() -> set[str]:
    """The TLG author numbers written in the test of the program on the absence of overlap."""
    tree = ast.parse((PACKAGE / "tests" / "test_pipeline_base.py").read_text(encoding="utf-8"))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == TEST_FILE)
    return {m.group(1) for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            for m in [re.fullmatch(r"tlg(\d{4})", node.value)] if m}


def main() -> int:
    rows = read("glaux_metadata.csv")
    sample = read("glaux_sample.csv")
    forbidden = authors_in_the_test()
    ok = True

    def show(name: str, expected, got) -> None:
        nonlocal ok
        same = expected == got
        ok &= same
        print(f"  {name:<58} {str(expected):>12} {str(got):>12}   {'same' if same else 'DIFFERENT'}")

    print(f"Python {sys.version.split()[0]}")
    print(f"  {'':<58} {'S9':>12} {'obtained':>12}")
    show("rows of data/glaux_metadata.csv", 1421, len(rows))
    show("TLG author numbers of Gorman and Pedalion (test file)", 37, len(forbidden))
    show("rows whose work number carries a letter (0096-002a)", 23,
         sum(1 for r in rows if not re.fullmatch(r"\d{4}-\d{3}", r["document_id"])))
    show("first four digits of document_id = column tlg_author", True,
         all(r["tlg_author"] == "tlg" + r["document_id"][:4] for r in rows))

    cut = [r for r in rows if r["document_id"][:4] in forbidden]
    print(f"  (first cut: {len(cut)} texts, {sum(int(r['tokens_declared']) for r in cut):,} declared "
          "records, by the authors of Gorman and Pedalion)")
    pool = [r["document_id"] for r in rows
            if r["document_id"][:4] not in forbidden and 5000 <= int(r["tokens_declared"]) <= 60000]
    show("texts in the pool (5,000 to 60,000 tokens declared)", 338, len(pool))

    random.seed(20260814)
    first = random.sample(pool, 20)
    rest = sorted(d for d in pool if d not in set(first))
    show("texts left for the confirmation sample", 318, len(rest))
    random.seed(20260815)
    second = random.sample(rest, 20)

    for number, name, drawn in ((1, "principale", first), (2, "conferma", second)):
        listed = sorted(r["tlg"] for r in sample if r["campione"] == name)
        common = len(set(drawn) & set(listed))
        show(f"draw {number}: texts that are in data/glaux_sample.csv ({name})", 20, common)
        show(f"draw {number}: texts of the list that the draw does not give", 0, len(set(listed) - set(drawn)))

    manual = {name: sum(1 for r in sample if r["campione"] == name and r["strato"] == "manuale")
              for name in ("principale", "conferma")}
    show("texts annotated by hand: first sample", 2, manual["principale"])
    show("texts annotated by hand: confirmation sample", 3, manual["conferma"])

    # The statement of S9 about the metadata tables of Gorman and Pedalion.
    catalogue = {r["tlg_author_id"][3:] for name in ("gorman_metadata.csv", "pedalion_metadata.csv")
                 for r in read(name) if re.fullmatch(r"tlg\d{4}", r["tlg_author_id"])}
    other_pool = [r["document_id"] for r in rows
                  if r["document_id"][:4] not in catalogue and 5000 <= int(r["tokens_declared"]) <= 60000]
    random.seed(20260814)
    other = random.sample(other_pool, 20)
    show("author numbers in the two metadata tables of the corpora", 42, len(catalogue))
    show("pool if those numbers were used instead", 299, len(other_pool))
    show("first draw still reproduced with those numbers (S9: no)", "no",
         "yes" if sorted(other) == sorted(r["tlg"] for r in sample if r["campione"] == "principale") else "no")

    print("RESULT:", "everything is as S9 states" if ok else "something differs from S9")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
