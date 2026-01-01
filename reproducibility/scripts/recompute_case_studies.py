#!/usr/bin/env python
"""Recompute the figures of the ten case studies of Supplement S7 (and the tokens touched by the findings, S1)
that are not simple counts per check.

The number of findings of each check in each stratum (for instance the 72,836 findings of
``lemma-tool-numbering`` in Gorman) is compared by ``compare_with_reference.py`` against Table S1.1.
The case studies also quote figures that need a question put to the token table: how many of the
findings fall on punctuation, how many tokens carry a value, in how many documents a label occurs,
how many tokens are not in NFC. This script puts those questions, with the code of the program
(``units.py``, ``agdt_schema.py``), to the runs of the six strata, and prints each answer next to
the figure that S7 states. The exit status is 0 when every stated figure is reproduced.

The figures are those of the running text of S7.1 to S7.10, and the figures of S1 and § 5.1 of the article
about the tokens that carry findings; the section is shown in the first column. A figure stated for a stratum whose run is not given is skipped.

usage:
    python recompute_case_studies.py --workspace W        the runs written by rerun_diagnosis.py
    python recompute_case_studies.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>)
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA, stratum_of

import pandas as pd

from greek_corpus_pipeline import agdt_schema, rule_catalog, units

#: (section, stratum, what is counted, stated value). A per cent is rounded to one decimal.
STATED = [
    ("S1", "gorman", "distinct tokens that carry at least one finding", 98440),
    ("S1", "gorman", "  per cent of the active tokens", 16.0),
    ("S1", "gorman", "  tokens that carry findings of more than one check", 2474),
    ("S1", "gorman", "  of the tokens touched, punctuation marks", 62296),
    ("S1", "gorman", "  of the tokens touched, words", 36144),
    ("S1", "gorman", "  per cent of the words", 6.6),
    ("S1", "pedalion", "distinct tokens that carry at least one finding", 27709),
    ("S1", "pedalion", "  per cent of the active tokens", 10.1),
    ("S1", "pedalion", "  tokens that carry findings of more than one check", 1684),
    ("S1", "pedalion", "  of the tokens touched, punctuation marks", 2397),
    ("S1", "pedalion", "  of the tokens touched, words", 25312),
    ("S1", "pedalion", "  per cent of the words", 10.6),
    ("S9", "glaux_auto", "active tokens of the text 0527-012", 20238),
    ("S7.1", "gorman", "findings of lemma-tool-numbering", 72836),
    ("S7.1", "gorman", "  of which on punctuation", 62238),
    ("S7.1", "gorman", "  of which on words", 10598),
    ("S7.1", "pedalion", "findings of lemma-tool-numbering", 311),
    ("S7.1", "glaux_auto", "findings of lemma-tool-numbering", 0),
    ("S7.1", "glaux_man", "findings of lemma-tool-numbering", 0),
    ("S7.1", "glaux_conf_auto", "findings of lemma-tool-numbering", 0),
    ("S7.1", "glaux_conf_man", "findings of lemma-tool-numbering", 0),
    ("S7.1", "gorman", "per cent of the findings of class variant that are lemma-tool-numbering", 79.2),
    ("S7.1", "gorman", "per cent of all the findings that are lemma-tool-numbering", 72.1),
    ("S7.2", "gorman", "findings of degree-underscore", 11187),
    ("S7.2", "pedalion", "findings of degree-underscore", 270),
    ("S7.2", "gorman", "degree-underscore findings whose tag also has underscores in positions 2-8", 1316),
    ("S7.2", "pedalion", "degree-underscore findings whose tag also has underscores in positions 2-8", 1),
    ("S7.3", "gorman", "findings of grade-p", 1218),
    ("S7.3", "pedalion", "findings of grade-p", 454),
    ("S7.4", "pedalion", "findings of pedalion-b-pos", 8555),
    ("S7.4", "glaux_man", "findings of pedalion-b-pos", 1405),
    ("S7.4", "glaux_conf_man", "findings of pedalion-b-pos", 2131),
    ("S7.4", "pedalion", "per cent of the findings of class variant that are pedalion-b-pos", 51.6),
    ("S7.5", "pedalion", "findings of common-gender-c", 8256),
    ("S7.5", "glaux_auto", "findings of common-gender-c", 5163),
    ("S7.5", "glaux_man", "findings of common-gender-c", 835),
    ("S7.5", "glaux_conf_auto", "findings of common-gender-c", 4267),
    ("S7.5", "glaux_conf_man", "findings of common-gender-c", 769),
    ("S7.5", "gorman", "findings of common-gender-c", 0),
    ("S7.5", "pedalion", "imported tokens with c in the seventh position of the tag", 8257),
    ("S7.5", "pedalion", "active tokens with c in the seventh position of the tag", 8256),
    ("S7.6", "gorman", "findings of personal-pronoun-person", 2372),
    ("S7.6", "pedalion", "findings of personal-pronoun-person", 176),
    ("S7.6", "glaux_auto", "findings of personal-pronoun-person", 1773),
    ("S7.6", "glaux_conf_auto", "findings of personal-pronoun-person", 1451),
    ("S7.6", "glaux_man", "findings of personal-pronoun-person", 1),
    ("S7.6", "glaux_conf_man", "findings of personal-pronoun-person", 1),
    ("S7.7", "glaux_auto", "imported tokens whose relation is the bare label CO", 2369),
    ("S7.7", "glaux_auto", "  documents in which it occurs", 18),
    ("S7.7", "glaux_conf_auto", "imported tokens whose relation is the bare label CO", 1887),
    ("S7.7", "glaux_conf_auto", "  documents in which it occurs", 17),
    ("S7.7", "glaux_auto", "findings of relation-bare-convention", 2239),
    ("S7.7", "glaux_auto", "  documents with relation-bare-convention findings", 18),
    ("S7.7", "glaux_conf_auto", "findings of relation-bare-convention", 1782),
    ("S7.7", "glaux_conf_auto", "  documents with relation-bare-convention findings", 17),
    ("S7.7", "gorman", "findings of relation-truncated-or-foreign on the label CO", 11),
    ("S7.7", "gorman", "  documents with such findings (label CO)", 4),
    ("S7.7", "gorman", "findings of relation-truncated-or-foreign on the label Aux", 8),
    ("S7.7", "gorman", "findings of relation-truncated-or-foreign on the label CONJ", 1),
    ("S7.7", "gorman", "findings of relation-truncated-or-foreign", 20),
    ("S7.7", "gorman", "  documents with relation-truncated-or-foreign findings", 11),
    ("S7.7", "pedalion", "findings of relation-truncated-or-foreign on the label CO", 11),
    ("S7.7", "pedalion", "  documents with such findings (label CO)", 5),
    ("S7.7", "gorman", "documents of the corpus", 158),
    ("S7.7", "pedalion", "documents of the corpus", 40),
    ("S7.7", "gorman", "imported tokens with the bare label CO (thresholds of S4)", 14),
    ("S7.7", "gorman", "  documents in which the label of the thresholds occurs", 6),
    ("S7.7", "pedalion", "imported tokens with the bare label CO (thresholds of S4)", 32),
    ("S7.7", "pedalion", "  documents in which the label of the thresholds occurs", 10),
    ("S7.8", "glaux_auto", "active tokens", 292567),
    ("S7.8", "glaux_auto", "active tokens whose form or lemma is not in NFC", 252406),
    ("S7.8", "glaux_auto", "per cent of the active tokens not in NFC", 86.3),
    ("S7.8", "pedalion", "active tokens", 274609),
    ("S7.8", "pedalion", "active tokens whose form or lemma is not in NFC", 4007),
    ("S7.8", "pedalion", "per cent of the active tokens not in NFC", 1.5),
    ("S7.9", "gorman", "words whose form is δεῖν", 165),
    ("S7.9", "gorman", "  of which with p in the mood position", 37),
    ("S7.9", "gorman", "findings of dein-participle", 36),
    ("S7.9", "gorman", "findings of dein-participle-disputed", 1),
    ("S7.10", "pedalion", "elision apostrophes U+2019 in achar.xml", 637),
    ("S7.10", "pedalion", "elision apostrophes U+02BC in achar.xml", 18),
    ("S7.10", "pedalion", "findings of apostrophe-mixed", 2394),
    ("S7.10", "gorman", "findings of apostrophe-mixed", 1655),
    ("S7.10", "pedalion", "files with a finding of apostrophe-mixed", 11),
    ("S7.10", "pedalion", "files of the corpus", 40),
    ("S7.10", "gorman", "files with a finding of apostrophe-mixed", 16),
    ("S7.10", "gorman", "files of the corpus", 158),
]


def text(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype("string").fillna("")


def not_nfc(frame: pd.DataFrame) -> pd.Series:
    def bad(value: object) -> bool:
        return isinstance(value, str) and bool(value) and unicodedata.normalize("NFC", value) != value
    return frame["form"].map(bad) | frame["lemma"].map(bad)


def measure(stratum: str, folder: Path) -> dict[tuple[str, str], float | int]:
    """The figures of S7 for one stratum, keyed by (section, what is counted)."""
    tokens = pd.read_parquet(folder / "tokens.parquet")
    findings = pd.read_parquet(folder / "findings.parquet")
    technical = pd.Series(units.is_technical_record(tokens), index=tokens.index).astype(bool)
    active = tokens[~technical]
    punctuation = pd.Series(units.is_punctuation(tokens), index=tokens.index).astype(bool)
    got: dict[tuple[str, str], float | int] = {}

    def put(section: str, what: str, value: float | int) -> None:
        got[(section, what)] = value

    def of(rule: str) -> pd.DataFrame:
        return findings[findings["rule_id"] == rule]

    # S1 (§ 5.1 of the article): the tokens that carry findings. A token is identified by its
    # file, the index of its sentence in the file and its index in the sentence.
    token_key = ["source_file", "sentence_index", "token_index"]
    touched = findings[token_key + ["rule_id"]].drop_duplicates()
    per_token = touched.groupby(token_key).size()
    put("S1", "distinct tokens that carry at least one finding", len(per_token))
    put("S1", "  per cent of the active tokens", round(100 * len(per_token) / len(active), 1))
    put("S1", "  tokens that carry findings of more than one check", int((per_token > 1).sum()))
    marked = per_token.index.to_frame(index=False).merge(
        tokens[token_key].assign(punct=punctuation.to_numpy(), word=units.is_word(tokens)),
        on=token_key, how="left")
    put("S1", "  of the tokens touched, punctuation marks", int(marked["punct"].fillna(False).astype(bool).sum()))
    touched_words = int(marked["word"].fillna(False).astype(bool).sum())
    put("S1", "  of the tokens touched, words", touched_words)
    put("S1", "  per cent of the words",
        round(100 * touched_words / int(pd.Series(units.is_word(tokens)).astype(bool).sum()), 1))
    # S9: the weight of one text, and the sizes of the texts of the samples (compared in main()).
    put("S9", "active tokens of the text 0527-012", int((active["document_id"].astype(str) == "0527-012").sum()))
    per_document = tokens.groupby("document_id").size()
    put("S9", "_smallest", int(per_document.min()))
    put("S9", "_largest", int(per_document.max()))
    # S7.1
    numbering = of("lemma-tool-numbering")
    put("S7.1", "findings of lemma-tool-numbering", len(numbering))
    keys = ["source_file", "sentence_index", "token_index"]
    joined = numbering[keys].merge(tokens[keys].assign(punct=punctuation.to_numpy()), on=keys, how="left")
    put("S7.1", "  of which on punctuation", int(joined["punct"].fillna(False).astype(bool).sum()))
    put("S7.1", "  of which on words", int((~joined["punct"].fillna(False).astype(bool)).sum()))
    variants = findings["rule_id"].map(rule_catalog.rule_class) == "variante"
    if variants.sum():
        put("S7.1", "per cent of the findings of class variant that are lemma-tool-numbering",
            round(100 * len(numbering) / variants.sum(), 1))
        put("S7.4", "per cent of the findings of class variant that are pedalion-b-pos",
            round(100 * len(of("pedalion-b-pos")) / variants.sum(), 1))
    put("S7.1", "per cent of all the findings that are lemma-tool-numbering",
        round(100 * len(numbering) / len(findings), 1))
    # S7.2 / S7.3 / S7.4 / S7.5 / S7.6
    degree = of("degree-underscore")
    put("S7.2", "findings of degree-underscore", len(degree))
    put("S7.2", "degree-underscore findings whose tag also has underscores in positions 2-8",
        int(text(degree, "postag").str[1:8].str.contains("_", regex=False).sum()))
    put("S7.3", "findings of grade-p", len(of("grade-p")))
    put("S7.4", "findings of pedalion-b-pos", len(of("pedalion-b-pos")))
    put("S7.5", "findings of common-gender-c", len(of("common-gender-c")))
    put("S7.5", "imported tokens with c in the seventh position of the tag", int((text(tokens, "postag").str[6:7] == "c").sum()))
    put("S7.5", "active tokens with c in the seventh position of the tag", int((text(active, "postag").str[6:7] == "c").sum()))
    put("S7.6", "findings of personal-pronoun-person", len(of("personal-pronoun-person")))
    # S7.7
    relation = text(tokens, "relation")
    bare = tokens[relation == "CO"]
    put("S7.7", "imported tokens whose relation is the bare label CO", len(bare))
    put("S7.7", "  documents in which it occurs", int(bare["document_id"].nunique()))
    convention = of("relation-bare-convention")
    put("S7.7", "findings of relation-bare-convention", len(convention))
    put("S7.7", "  documents with relation-bare-convention findings", int(convention["document_id"].nunique()))
    foreign = of("relation-truncated-or-foreign")
    for label in ("CO", "Aux", "CONJ"):
        part = foreign[text(foreign, "relation").str.strip() == label]
        put("S7.7", f"findings of relation-truncated-or-foreign on the label {label}", len(part))
        if label == "CO":
            put("S7.7", "  documents with such findings (label CO)", int(part["document_id"].nunique()))
    put("S7.7", "findings of relation-truncated-or-foreign", len(foreign))
    put("S7.7", "  documents with relation-truncated-or-foreign findings", int(foreign["document_id"].nunique()))
    damage = relation.map(lambda v: agdt_schema.classify_relation_damage(v) if v else "")
    folded = relation.map(lambda v: agdt_schema.fold_greek_lookalikes(v.strip()) if v else "")
    thresholds = tokens[(damage == agdt_schema.DAMAGE_TRUNCATED_OR_FOREIGN) & (folded == "CO")]
    put("S7.7", "imported tokens with the bare label CO (thresholds of S4)", len(thresholds))
    put("S7.7", "  documents in which the label of the thresholds occurs", int(thresholds["document_id"].nunique()))
    put("S7.7", "documents of the corpus", int(tokens["document_id"].nunique()))
    # S7.8
    put("S7.8", "active tokens", len(active))
    bad = not_nfc(active)
    put("S7.8", "active tokens whose form or lemma is not in NFC", int(bad.sum()))
    put("S7.8", "per cent of the active tokens not in NFC", round(100 * bad.sum() / len(active), 1))
    # S7.9
    words = tokens[pd.Series(units.is_word(tokens), index=tokens.index).astype(bool)]
    dein = words[text(words, "form") == "δεῖν"]
    put("S7.9", "words whose form is δεῖν", len(dein))
    put("S7.9", "  of which with p in the mood position", int((text(dein, "postag").str[4:5] == "p").sum()))
    put("S7.9", "findings of dein-participle", len(of("dein-participle")))
    put("S7.9", "findings of dein-participle-disputed", len(of("dein-participle-disputed")))
    # S7.10
    achar = text(tokens[tokens["source_file"].astype(str) == "achar.xml"], "form")
    put("S7.10", "elision apostrophes U+2019 in achar.xml", int(achar.str.count("’").sum()))
    put("S7.10", "elision apostrophes U+02BC in achar.xml", int(achar.str.count("ʼ").sum()))
    apostrophe = of("apostrophe-mixed")
    put("S7.10", "findings of apostrophe-mixed", len(apostrophe))
    put("S7.10", "files with a finding of apostrophe-mixed", int(apostrophe["source_file"].nunique()))
    put("S7.10", "files of the corpus", int(tokens["source_file"].nunique()))
    return got


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="*", type=Path)
    parser.add_argument("--workspace", type=Path)
    arguments = parser.parse_args(argv)
    folders = list(arguments.runs)
    if arguments.workspace:
        folders += [arguments.workspace / "runs" / f"rerun-{s}" for s in STRATA
                    if (arguments.workspace / "runs" / f"rerun-{s}" / "findings.parquet").is_file()]
    if not folders:
        parser.error("give run folders or --workspace")

    obtained: dict[tuple[str, str, str], float | int] = {}
    for folder in folders:
        stratum = stratum_of(folder)
        if stratum is None:
            parser.error(f"cannot tell which stratum {folder.name} is")
        for (section, what), value in measure(stratum, folder).items():
            obtained[(section, stratum, what)] = value
        print(f"measured {stratum}", flush=True)

    compared = different = 0
    print(f"\n{'section':<8} {'stratum':<16} {'what is counted':<78} {'stated':>9} {'obtained':>9}")
    for section, stratum, what, stated in STATED:
        key = (section, stratum, what)
        if not any(k[1] == stratum for k in obtained):
            continue
        value = obtained.get(key)
        compared += 1
        same = value is not None and abs(float(value) - stated) < 1e-9
        different += not same
        shown = "not computed" if value is None else (f"{value:,}" if isinstance(value, int) else f"{value}")
        stated_text = f"{stated:,}" if isinstance(stated, int) else f"{stated}"
        print(f"{section:<8} {stratum:<16} {what[:78]:<78} {stated_text:>9} {shown:>9}{'' if same else '   DIFFERENT'}")
    glaux = [s for s in STRATA if s.startswith("glaux")]
    if all(any(k[1] == s for k in obtained) for s in glaux):
        smallest = min(obtained[("S9", s, "_smallest")] for s in glaux)
        largest = max(obtained[("S9", s, "_largest")] for s in glaux)
        for what, stated, value in (("smallest of the forty texts (imported tokens)", 5109, smallest),
                                    ("largest of the forty texts (imported tokens)", 41942, largest)):
            compared += 1
            different += value != stated
            print(f"{'S9':<8} {'glaux (all)':<16} {what:<78} {stated:>9,} {value:>9,}{'' if value == stated else '   DIFFERENT'}")
    print(f"\nRESULT: {compared} stated figures compared, "
          + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
