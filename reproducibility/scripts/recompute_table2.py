#!/usr/bin/env python
"""Recompute Table 2 of the article (the size and the shape of Gorman and Pedalion).

Table 2 of the article ("Indicator, Unit / basis of calculation, Gorman, Pedalion") is made of
twenty indicators. This script recomputes each of them from the token table (``tokens.parquet``)
and the arc table (``arcs.parquet``) of a run, with the counting units of the program
(``units.py``) and, for projectivity, the function of the program that the Overview of the
interface uses (``stats.syntax_summary``), and prints it next to the value of the article:

    imported tokens, active tokens, technical tokens excluded, tokens classified as punctuation,
    words, documents, sentences, sentences with at least one word, distinct forms and lemmas
    (among the words), distinct morphological tags and distinct relations (among the imported
    tokens), tags that do not have nine characters, average and longest sentence (in words),
    analysable links, links covered by the projectivity structure, sentences with at least one
    evaluated arc, non-projective links and sentences with a non-projective link (with their
    percentages).

Only the two corpora of the table are compared (Gorman and Pedalion); the other strata are
measured and shown without a stated value. The exit status is 0 when every stated value is
reproduced.

The basis of each indicator is the one the table declares. In particular the distinct relations
are counted among the *imported* tokens, as the table says (72 and 63); the Overview of the
interface counts them among the active tokens and shows 62 for Pedalion, because one relation
occurs only on a technical token.

usage:
    python recompute_table2.py --workspace W        the runs written by rerun_diagnosis.py
    python recompute_table2.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA, stratum_of

import pandas as pd

from greek_corpus_pipeline import stats, units

#: Table 2 of the article, in the order of the table: (indicator, Gorman, Pedalion).
TABLE_2 = [
    ("imported tokens", 625176, 281245),
    ("active tokens", 616646, 274609),
    ("technical tokens excluded", 8530, 6636),
    ("tokens classified as punctuation", 67790, 37638),
    ("words", 548912, 238413),
    ("documents", 158, 40),
    ("sentences", 26616, 18791),
    ("sentences with at least one word", 26616, 18639),
    ("distinct forms", 69329, 45410),
    ("distinct lemmas", 18630, 14318),
    ("distinct morphological tags", 1185, 1043),
    ("  of which not of nine characters", 91, 14),
    ("distinct relations", 72, 63),
    ("average sentence length", 20.62, 12.79),
    ("longest sentence", 185, 131),
    ("analysable links", 513369, 213144),
    ("links covered by the projectivity structure", 513355, 213113),
    ("sentences with at least one evaluated arc", 26377, 17984),
    ("non-projective links", 66918, 21316),
    ("  per cent of the analysable links", 13.0, 10.0),
    ("sentences with at least one non-projective link", 20949, 8959),
    ("  per cent of the sentences with at least one evaluated arc", 79.4, 49.8),
]
STATED = {"gorman": {name: g for name, g, _ in TABLE_2}, "pedalion": {name: p for name, _, p in TABLE_2}}


def measure(folder: Path) -> dict[str, float | int]:
    tokens = pd.read_parquet(folder / "tokens.parquet")
    arcs = pd.read_parquet(folder / "arcs.parquet")
    built = units.build_units(tokens)
    words, active = built.words, built.active_records

    in_sentence = units.sentence_key(words).value_counts()
    tags = tokens["postag"].dropna().astype(str)
    relations = tokens["relation"].dropna().astype(str)
    relations = relations[relations.str.strip() != ""]
    syntax = stats.syntax_summary(active, arcs)

    return {
        "imported tokens": len(tokens),
        "active tokens": len(active),
        "technical tokens excluded": len(tokens) - len(active),
        "tokens classified as punctuation": int(pd.Series(units.is_punctuation(tokens)).astype(bool).sum()),
        "words": len(words),
        "documents": int(tokens["document_id"].nunique()),
        "sentences": built.n_sentences,
        "sentences with at least one word": len(in_sentence),
        "distinct forms": int(words["form"].dropna().nunique()),
        "distinct lemmas": int(words["lemma"].dropna().nunique()),
        "distinct morphological tags": int(tags.nunique()),
        "  of which not of nine characters": int(tags[tags.str.len() != 9].nunique()),
        "distinct relations": int(relations.nunique()),
        "average sentence length": round(len(words) / len(in_sentence), 2),
        "longest sentence": int(in_sentence.max()),
        "analysable links": int(syntax["legami utilizzabili"]),
        "links covered by the projectivity structure": int(syntax["legami misurati"]),
        "sentences with at least one evaluated arc": int(syntax["frasi con archi"]),
        "non-projective links": int(syntax["legami non proiettivi"]),
        "  per cent of the analysable links": float(syntax["% legami non proiettivi"]),
        "sentences with at least one non-projective link": int(syntax["frasi con almeno un legame non proiettivo"]),
        "  per cent of the sentences with at least one evaluated arc":
            float(syntax["% frasi con almeno un legame non proiettivo"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="*", type=Path)
    parser.add_argument("--workspace", type=Path)
    arguments = parser.parse_args(argv)
    folders = list(arguments.runs)
    if arguments.workspace:
        folders += [arguments.workspace / "runs" / f"rerun-{s}" for s in STRATA
                    if (arguments.workspace / "runs" / f"rerun-{s}" / "arcs.parquet").is_file()]
    if not folders:
        parser.error("give run folders or --workspace")

    compared = different = 0
    for folder in folders:
        stratum = stratum_of(folder)
        stated = STATED.get(stratum or "", {})
        print(f"== {folder.name} ==")
        print(f"  {'indicator':<62} {'Table 2':>12} {'obtained':>12}")
        for name, value in measure(folder).items():
            expected = stated.get(name)
            shown = f"{value:,}" if isinstance(value, int) else f"{value}"
            if expected is None:
                print(f"  {name:<62} {'':>12} {shown:>12}")
                continue
            same = abs(float(value) - float(expected)) < 1e-9
            compared += 1
            different += not same
            wanted = f"{expected:,}" if isinstance(expected, int) else f"{expected}"
            print(f"  {name:<62} {wanted:>12} {shown:>12}   {'same' if same else 'DIFFERENT'}")
        print()
    print(f"RESULT: {compared} values of Table 2 compared, "
          + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
