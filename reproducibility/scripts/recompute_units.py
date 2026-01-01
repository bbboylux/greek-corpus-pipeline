#!/usr/bin/env python
"""Recompute the counting units of Supplement S11.1 and the figures quoted in its text.

For every run it reads ``tokens.parquet`` (and ``arcs.parquet``) and, with the code of
the program (``src/greek_corpus_pipeline/units.py``), recomputes: the five units of
Table S11.1; the punctuation among the imported and among the active records; the
tokens with head 0, their sentences and the roots left once structural punctuation
is excluded; the distinct values of ``sentence_id`` against the sentence keys; the
arcs of the projectivity structure and the sentences that have at least one arc whose
two ends are active; the arcs that the analysable links leave out because they point
to a technical node; and the analysable sentences in which some chain of heads does
not reach a token with head 0, or runs into a cycle (counted twice: among all the
records, and among the active ones, that is, without the technical tokens).

For Gorman and Pedalion the value stated by the supplement (or, for the arcs that
point to a technical node, by the documentation of ``units.py``) is printed next to
the obtained one: for Pedalion among them the 28 sentences with a chain that reaches
no head 0, the nine of them whose chain contains a cycle and the eight in which it does
so once the technical tokens are left out (S11.1). The exit status is 0 when everything
that has a stated value coincides with it.

usage:
    python recompute_units.py --workspace W              the runs written by rerun_diagnosis.py
    python recompute_units.py RUN_FOLDER [RUN_FOLDER ...] other run folders (the stratum is
                                                          known from the name of the folder: the
                                                          study's own, or rerun-<stratum>)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA, stratum_of

import numpy as np
import pandas as pd

from greek_corpus_pipeline import units as U

#: What the supplement (S11.1, Table 2 of the article) and the documentation of units.py state.
STATED = {
    "gorman": {
        "imported records": 625176, "active records": 616646, "words": 548912,
        "analysable links": 513369, "analysable sentences": 25994,
        "punctuation among the imported records": 67790, "punctuation among the active records": 67734,
        "tokens with head 0": 88692, "sentences": 26616,
        "roots once structural punctuation is left out": 27305,
        "distinct values of sentence_id": 564, "XML files": 158,
        "arcs of the projectivity structure": 513355, "arcs with both ends active": 513355,
        "sentences with at least one evaluated arc": 26377,
        "arcs left out because they point to a technical node": 16680,
        "analysable sentences with a chain that reaches no head 0": 16,
    },
    "pedalion": {
        "imported records": 281245, "active records": 274609, "words": 238413,
        "analysable links": 213144, "analysable sentences": 18235,
        "punctuation among the imported records": 37638, "punctuation among the active records": 36196,
        "arcs of the projectivity structure": 213549, "arcs with both ends active": 213113,
        "sentences with at least one evaluated arc": 17984,
        "arcs left out because they point to a technical node": 9470,
        "analysable sentences with a chain that reaches no head 0": 28,
        "analysable sentences with a cycle among all the records": 9,
        "analysable sentences with a cycle among the active records": 8,
    },
    "glaux_auto": {"arcs left out because they point to a technical node": 14879},
}


def chains(tokens: pd.DataFrame, analysable: set[str], only_active: bool) -> tuple[int, int]:
    """(sentences with a chain that reaches no head 0, sentences with a cycle).

    From every token that is not itself a head-0 node, the chain of heads is followed.
    It ends well when it reaches a token with head 0. It ends badly in two ways: it ends
    nowhere when it meets an empty or absent head, and it runs into a cycle when it comes
    back to a token already visited (a token that is its own head is a cycle of one). The
    first number counts the sentences with a chain that ends in either way; the second
    those with a cycle. With *only_active* the technical records are not part of the graph
    (then a chain that passes through one ends nowhere, so only the second number is of use).
    """
    frame = pd.DataFrame({
        "k": U.sentence_key(tokens).to_numpy(),
        "id": pd.to_numeric(tokens["token_id"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
        "head": pd.to_numeric(tokens["head"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
        "technical": np.asarray(U.is_technical_record(tokens), dtype=bool),
    })
    frame = frame[frame["k"].isin(analysable)]
    if only_active:
        frame = frame[~frame["technical"]]
    nowhere: set[str] = set()
    cyclic: set[str] = set()
    for key, group in frame.groupby("k", sort=False):
        heads = dict(zip(group["id"], group["head"]))
        for start, head in heads.items():
            if head == 0:
                continue
            seen: set[int] = set()
            current = start
            while True:
                if heads.get(current) == 0:
                    break                         # a token with head 0 has been reached
                if current in seen:
                    cyclic.add(key)               # back to a token already visited
                    break
                seen.add(current)
                if current not in heads:          # an empty head, or one that is not a token
                    nowhere.add(key)
                    break
                current = heads[current]
    return len(nowhere | cyclic), len(cyclic)


def measure(run: Path) -> dict[str, int]:
    tokens = pd.read_parquet(run / "tokens.parquet")
    built = U.build_units(tokens)
    active = built.active_records
    key = U.sentence_key(tokens)
    head = pd.to_numeric(tokens["head"], errors="coerce")
    structural = np.asarray(U.is_structural_punctuation(tokens), dtype=bool)
    analysable = U.analyzable_sentence_keys(tokens)
    result = {
        "imported records": len(tokens),
        "active records": len(active),
        "words": len(built.words),
        "analysable links": len(built.analyzable_links),
        "analysable sentences": len(built.analyzable_sentences),
        "punctuation among the imported records": int(np.asarray(U.is_punctuation(tokens), dtype=bool).sum()),
        "punctuation among the active records": int(np.asarray(U.is_punctuation(active), dtype=bool).sum()),
        "tokens with head 0": int((head == 0).sum()),
        "sentences": int(key.nunique()),
        "roots once structural punctuation is left out": int(((head == 0) & ~structural).sum()),
        "distinct values of sentence_id": int(tokens["sentence_id"].astype("string").nunique()),
        "XML files": int(tokens["source_file"].astype("string").nunique()),
        "arcs left out because they point to a technical node":
            int(U.analyzable_link_mask(active, within=tokens).sum()) - len(built.analyzable_links),
    }
    arcs_file = run / "arcs.parquet"
    if arcs_file.is_file():
        arcs = pd.read_parquet(arcs_file)
        active_ids = set(zip(U.sentence_key(active).to_numpy(),
                             pd.to_numeric(active["token_id"], errors="coerce").fillna(-1).astype("int64").to_numpy()))
        arc_key = U.sentence_key(arcs)
        dependent_ok = [(k, int(i)) in active_ids for k, i in zip(arc_key, arcs["token_id"])]
        head_ok = [(k, int(h)) in active_ids for k, h in zip(arc_key, arcs["head"].fillna(-1))]
        both = np.asarray(dependent_ok) & np.asarray(head_ok)
        result["arcs of the projectivity structure"] = len(arcs)
        result["arcs with both ends active"] = int(both.sum())
        result["sentences with at least one evaluated arc"] = int(arc_key[both].nunique())
    result["analysable sentences with a chain that reaches no head 0"], \
        result["analysable sentences with a cycle among all the records"] = chains(tokens, analysable, False)
    _, result["analysable sentences with a cycle among the active records"] = chains(tokens, analysable, True)
    return result


def main(argv: list[str] | None = None) -> int:
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

    ok = True
    for folder in folders:
        stated = STATED.get(stratum_of(folder) or "", {})
        print(f"== {folder.name} ==")
        print(f"  {'':<62} {'stated':>10} {'obtained':>10}")
        for name, value in measure(folder).items():
            expected = stated.get(name)
            verdict = "" if expected is None else ("same" if expected == value else "DIFFERENT")
            ok &= verdict != "DIFFERENT"
            print(f"  {name:<62} {'' if expected is None else f'{expected:,}':>10} {value:>10,}   {verdict}")
        print()
    print("RESULT:", "every stated value is reproduced" if ok else "some stated value is not reproduced")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
