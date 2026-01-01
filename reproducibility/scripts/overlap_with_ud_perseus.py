#!/usr/bin/env python
"""Redo the overlap analysis of Supplement S10.14 and compare it with Tables S10.12 and S10.13.

Gorman and Pedalion may contain texts on which Stanza and UDPipe were trained, because both
models are trained on UD_Ancient_Greek-Perseus, a conversion of passages of AGDT 2.1. S10.14
measures that overlap and its effect on the agreement rates. The program itself does not do
this; this script performs the method that S10.14 describes:

  * the forms of the corpus words and of the UD tokens whose UPOS is not PUNCT are normalised
    in the same way: NFC composition, one character for every sign used as an elision mark
    (U+2019, U+02BC, U+1FBD, U+1FBF, U+0313, U+2018 and the ASCII apostrophe), grave accent
    turned into acute, lower case;
  * a corpus word overlaps with one of the three UD sets when it lies inside a sequence of five
    consecutive words of its sentence that also occurs, in the same order, in a sentence of that
    set; a word that overlaps with more than one set is assigned to the training set first,
    then to the development set, then to the test set;
  * sentences that coincide as a whole after normalisation are counted separately, and on their
    words the corpus tag is compared with the XPOS of UD and the lemma, without the Perseus
    numbering, with the UD lemma;
  * the agreement measures of S10.3 are computed by overlap class from the comparison tables
    (``stanza_comparison.parquet`` and ``udpipe_comparison.parquet``) of the runs of Gorman and
    Pedalion, on the same words.

What you supply, besides a workspace in which ``rerun_diagnosis.py`` and
``rerun_model_comparison.py`` have run (or the study's own run folders):

    --ud UD_FOLDER     a folder holding grc_perseus-ud-train.conllu, grc_perseus-ud-dev.conllu and
                       grc_perseus-ud-test.conllu of release 2.4 of UD_Ancient_Greek-Perseus (the
                       release from which S10.14 took the forms; see ACQUISITION.md)

Every value is printed next to the one that the supplement states (``reference/s10_overlap.csv``:
Tables S10.12 and S10.13 and the figures of the text of S10.14). The exit status is 0 when every
stated value is reproduced. The number of sentences of the three UD files is checked first: if
it is not 11,476, 1,137 and 1,306 the files are not release 2.4.

usage:
    python overlap_with_ud_perseus.py --ud UD_FOLDER --workspace W
    python overlap_with_ud_perseus.py --ud UD_FOLDER --gorman RUN_FOLDER --pedalion RUN_FOLDER
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import REFERENCE

import numpy as np
import pandas as pd

KEY = ["source_file", "document_id", "sentence_index", "token_index"]
WINDOW = 5
SETS = ("train", "dev", "test")
ELISION_SIGNS = {"’": "'", "ʼ": "'", "᾽": "'", "᾿": "'", "̓": "'", "‘": "'"}
TABLES = ("stanza_comparison.parquet", "udpipe_comparison.parquet")
#: Gorman works of Table S10.12, identified by the beginning of the name of the file.
GORMAN_WORKS = ("hdt-1", "diodsic", "athen12", "athen13", "thuc-1", "plut-alcib", "plutarch-lycurgus")
CLASSES = {"training": "train", "development": "dev", "test": "test", "no_overlap": "none"}


def normalise(form: object) -> str:
    """The normalisation of S10.14, applied to corpus forms and UD forms alike."""
    if not isinstance(form, str):
        return ""
    text = "".join(ELISION_SIGNS.get(c, c) for c in unicodedata.normalize("NFC", form))
    text = unicodedata.normalize("NFD", text).replace("̀", "́")
    return unicodedata.normalize("NFC", text).lower()


def read_conllu(path: Path) -> list[tuple[str, list[list[str]]]]:
    """The sentences of a CoNLL-U file: (sentence identifier, the rows of the words)."""
    sentences, identifier, rows = [], None, []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("# sent_id"):
            identifier = line.split("=", 1)[1].strip()
        elif not line.strip():
            if identifier is not None:
                sentences.append((identifier, rows))
            identifier, rows = None, []
        elif not line.startswith("#"):
            cells = line.split("\t")
            if "-" in cells[0] or "." in cells[0]:      # multiword tokens and empty nodes
                continue
            rows.append(cells)
    if identifier is not None and rows:
        sentences.append((identifier, rows))
    return sentences


def ud_index(folder: Path):
    """Read the three UD sets; return the count of sentences and the two indexes."""
    sets = {}
    for name in SETS:
        path = folder / f"grc_perseus-ud-{name}.conllu"
        if not path.is_file():
            raise SystemExit(f"{path} does not exist (see ACQUISITION.md, section 7)")
        sets[name] = read_conllu(path)
    shingles: dict[tuple, set] = {}      # five consecutive forms -> the sets they occur in
    sentences: dict[tuple, dict] = {}    # the forms of a whole sentence -> {set: UD rows}
    for name, content in sets.items():
        for _, rows in content:
            words = [row for row in rows if row[3] != "PUNCT"]
            forms = tuple(normalise(row[1]) for row in words)
            sentences.setdefault(forms, {}).setdefault(name, words)
            for i in range(len(forms) - WINDOW + 1):
                shingles.setdefault(forms[i:i + WINDOW], set()).add(name)
    return {name: len(content) for name, content in sets.items()}, shingles, sentences


def classify(merged: pd.DataFrame, shingles: dict, sentences: dict) -> pd.DataFrame:
    """Add the overlap class and the whole-sentence comparison to the words of a corpus."""
    forms = merged["form"].map(normalise).to_numpy()
    tags = np.array([t if isinstance(t, str) else "" for t in merged["postag"]], dtype=object)
    lemmas = np.array([t if isinstance(t, str) else "" for t in merged["lemma"]], dtype=object)
    found = [set() for _ in range(len(merged))]
    whole = np.zeros(len(merged), dtype=bool)
    same_tag = np.zeros(len(merged), dtype=bool)
    same_lemma = np.zeros(len(merged), dtype=bool)
    strip = lambda text: re.sub(r"\d+$", "", unicodedata.normalize("NFC", text))
    for _, index in merged.groupby(["source_file", "document_id", "sentence_index"], sort=False).indices.items():
        sentence = tuple(forms[index])
        match = sentences.get(sentence)
        if match and "train" in match:
            ud_words = match["train"]
            for position, i in enumerate(index):
                whole[i] = True
                same_tag[i] = tags[i] == ud_words[position][4]
                same_lemma[i] = strip(lemmas[i]) == strip(ud_words[position][2])
        for start in range(len(sentence) - WINDOW + 1):
            sets_here = shingles.get(sentence[start:start + WINDOW])
            if sets_here:
                for i in index[start:start + WINDOW]:
                    found[i] |= sets_here
    merged = merged.copy()
    merged["overlap"] = ["train" if "train" in s else "dev" if "dev" in s else "test" if "test" in s else "none"
                         for s in found]
    merged["whole_sentence_train"] = whole
    merged["whole_same_tag"] = same_tag
    merged["whole_same_lemma"] = same_lemma
    return merged


def work_of(source_file: str) -> str:
    for prefix in GORMAN_WORKS:
        if source_file.startswith(prefix):
            return prefix
    return "other"


def compute(corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame, shingles, sentences):
    """All the values of S10.12, S10.13 and the text of S10.14 for one corpus."""
    columns = KEY + ["postag_modello", "accordo_lemma", "accordo_postag"]
    wanted = KEY + ["form", "lemma", "postag", "accordo_lemma", "accordo_postag", "postag_modello",
                    "eleggibile_lemma", "eleggibile_postag"]
    merged = stanza[wanted].merge(udpipe[columns], on=KEY, suffixes=("_s", "_u"), validate="one_to_one")
    merged = merged.sort_values(["source_file", "document_id", "sentence_index", "token_index"]).reset_index(drop=True)
    merged = classify(merged, shingles, sentences)
    values: dict[str, float | int] = {}
    words = len(merged)
    counts = merged["overlap"].value_counts()
    for name, label in CLASSES.items():
        values[f"S10.12.{corpus}.total.{name}"] = int(counts.get(label, 0))
    values[f"S10.12.{corpus}.total.words"] = words
    values[f"S10.14.{corpus}.train_pct"] = round(100 * counts.get("train", 0) / words, 1)
    values[f"S10.14.{corpus}.exact_train_words"] = int(merged["whole_sentence_train"].sum())
    if corpus == "gorman":
        whole = int(merged["whole_sentence_train"].sum())
        values["S10.14.gorman.exact_train_tag_identical"] = int(merged["whole_same_tag"].sum())
        values["S10.14.gorman.exact_train_tag_identical_pct"] = round(100 * merged["whole_same_tag"].sum() / whole, 1)
        values["S10.14.gorman.exact_train_lemma_identical_pct"] = round(100 * merged["whole_same_lemma"].sum() / whole, 1)
        values["S10.14.gorman.no_overlap_pct"] = round(100 * counts.get("none", 0) / words, 1)
        merged["work"] = merged["source_file"].astype(str).map(work_of)
        table = pd.crosstab(merged["work"], merged["overlap"])
        for work in (*GORMAN_WORKS, "other"):
            row = table.loc[work] if work in table.index else pd.Series(dtype=int)
            for name, label in CLASSES.items():
                values[f"S10.12.gorman.{work}.{name}"] = int(row.get(label, 0))
            values[f"S10.12.gorman.{work}.words"] = int(row.sum())

    eligible_lemma = merged["eleggibile_lemma"].astype(bool)
    eligible_tag = merged["eleggibile_postag"].astype(bool)
    both_against = (eligible_tag & ~merged["accordo_postag_s"].fillna(False).astype(bool)
                    & ~merged["accordo_postag_u"].fillna(False).astype(bool)
                    & (merged["postag_modello_s"].astype("string") == merged["postag_modello_u"].astype("string")).fillna(False))
    classes = {"training": merged["overlap"] == "train", "development": merged["overlap"] == "dev",
               "test": merged["overlap"] == "test", "no_overlap": merged["overlap"] == "none",
               "all_words": pd.Series(True, index=merged.index),
               "without_training_overlap": merged["overlap"] != "train"}
    measures = (("lemma_stanza", eligible_lemma, "accordo_lemma_s"), ("lemma_udpipe", eligible_lemma, "accordo_lemma_u"),
                ("tag_stanza", eligible_tag, "accordo_postag_s"), ("tag_udpipe", eligible_tag, "accordo_postag_u"),
                ("tag_both_against", eligible_tag, None))
    for measure, eligible, column in measures:
        for name, mask in classes.items():
            denominator = eligible & mask
            numerator = (both_against & denominator) if column is None else (merged[column].fillna(False).astype(bool) & denominator)
            base = f"S10.13.{corpus}.{measure}.{name}"
            values[base + ".agreements"] = int(numerator.sum())
            values[base + ".eligible"] = int(denominator.sum())
            values[base + ".rate"] = round(100 * numerator.sum() / denominator.sum(), 2) if denominator.sum() else float("nan")
    return values, merged


def reference() -> dict[str, tuple[str, str, str, float]]:
    with (REFERENCE / "s10_overlap.csv").open(encoding="utf-8", newline="") as handle:
        return {r["id"]: (r["section"], r["corpus"], r["quantity"], float(r["expected"]))
                for r in csv.DictReader(handle)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ud", type=Path, required=True)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--gorman", type=Path)
    parser.add_argument("--pedalion", type=Path)
    arguments = parser.parse_args(argv)
    folders = {"gorman": arguments.gorman, "pedalion": arguments.pedalion}
    if arguments.workspace:
        for corpus in folders:
            folders[corpus] = folders[corpus] or arguments.workspace / "runs" / f"rerun-{corpus}"
    folders = {k: v for k, v in folders.items() if v}
    if not folders:
        parser.error("give --workspace, or --gorman and/or --pedalion")

    sentence_counts, shingles, sentences = ud_index(arguments.ud)
    values: dict[str, float | int] = {f"S10.14.ud_sentences.{k}": v for k, v in sentence_counts.items()}
    detail: dict[str, pd.DataFrame] = {}
    for corpus, folder in folders.items():
        stanza, udpipe = (pd.read_parquet(folder / name) for name in TABLES)
        found, merged = compute(corpus, stanza, udpipe, shingles, sentences)
        values.update(found)
        detail[corpus] = merged

    expected = reference()
    compared = different = 0
    print(f"{'section':<8} {'quantity':<100} {'stated':>12} {'obtained':>12}")
    for key, (section, corpus, quantity, stated) in expected.items():
        if corpus not in folders and corpus != "ud":
            continue
        obtained = values.get(key)
        compared += 1
        same = obtained is not None and abs(float(obtained) - stated) < 1e-9
        different += not same
        shown = "not computed" if obtained is None else (f"{obtained:,}" if isinstance(obtained, int) else f"{obtained}")
        stated_text = f"{stated:,.0f}" if stated == int(stated) and not key.endswith(("rate", "_pct")) else f"{stated}"
        print(f"{section:<8} {quantity[:100]:<100} {stated_text:>12} {shown:>12}{'' if same else '   DIFFERENT'}")

    # Statements of the text that are derived from the tables: the drop in the rates when the
    # training overlap is left out (S10.14, "Effect on the agreement").
    for corpus in folders:
        drops = []
        for measure in ("lemma_stanza", "lemma_udpipe", "tag_stanza", "tag_udpipe"):
            drops.append(values[f"S10.13.{corpus}.{measure}.all_words.rate"]
                         - values[f"S10.13.{corpus}.{measure}.without_training_overlap.rate"])
        print(f"\n{corpus}: leaving out the training overlap lowers the four rates by "
              + ", ".join(f"{d:.2f}" for d in drops) + " points "
              + ("(S10.14: 0.6 to 1.4 for Gorman)" if corpus == "gorman" else "(S10.14: less than 0.1 for Pedalion)"))
    if "pedalion" in detail:
        top = (detail["pedalion"].query("overlap == 'train'")["source_file"].value_counts().head(5))
        print("\nPedalion, files with the most words overlapping the training set (S10.14: mostly the files of "
              "example sentences):")
        for name, count in top.items():
            print(f"  {count:>6}  {name}")
    print(f"\nRESULT: {compared} stated values compared, "
          + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
