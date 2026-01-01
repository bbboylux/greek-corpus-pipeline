#!/usr/bin/env python
"""Recompute the tables of Supplement S10 that ``recompute_model_counts.py`` does not cover.

``recompute_model_counts.py`` reproduces Table S10.1 (provenance), Table S10.3 (the eight main
measures), the degree paragraph of S10.6, Table S10.8 (the three-way comparison) and S10.9 (the
recurrent substitutions). This script reproduces the rest of S10.2–S10.11 from the same comparison
tables (``stanza_comparison.parquet`` and ``udpipe_comparison.parquet`` of the runs of Gorman and
Pedalion), with the definitions of S10.3:

  * Table S10.2, the denominators: the tokens supplied to the models, the words with a reference lemma
    and with a nine-character tag, the words without a lemma, without a tag and with a tag whose length
    is not nine, and (section S10.11) the elliptic nodes;
  * Table S10.4 and section S10.5, the predictions of UDPipe that do not have the AGDT positional form,
    one by one, with the tag of the corpus at the same point;
  * Table S10.5, the agreement position by position, with the explicit denominator (the eligible words
    in which the corpus fills the position), and the paragraph on person of section S10.6;
  * Tables S10.6 and S10.7 (section S10.7), the agreement by part of speech of the corpus, for the classes
    of at least two hundred words;
  * the comparison key of section S10.8: what the fourth row of Table S10.8 would be with raw strings, and
    what makes the difference (the numeral appended to the lemma, the Unicode composition);
  * Table S10.10, the formal classification of the cases in which the two models agree against the
    corpus on the lemma (four criteria, in order, mutually exclusive), Table S10.11, the ten most
    frequent lemma substitutions of each corpus with their categories, and the figures of the text of
    section S10.10 that comment them.

Every value is printed next to the one that the supplement states. The exit status is 0 when every
stated value is reproduced.

usage:
    python recompute_model_tables.py --workspace W        runs ``rerun-gorman`` and ``rerun-pedalion``
    python recompute_model_tables.py --gorman RUN_FOLDER --pedalion RUN_FOLDER
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repro_common  # noqa: F401  (puts the program on the path)

import numpy as np
import pandas as pd

from greek_corpus_pipeline import units
from greek_corpus_pipeline.agdt_schema import TAG_LENGTH, VALID_CHARACTERS
from greek_corpus_pipeline.model_eval import _ha_forma_agdt, prepare_model_input

KEY = ["source_file", "document_id", "sentence_index", "token_index"]
CORPORA = ("gorman", "pedalion")
TITLE = {"gorman": "Gorman", "pedalion": "Pedalion"}
#: The marks of elision: U+1FBD (koronis), U+02BC (modifier letter apostrophe), U+2019 (right quotation mark).
ELISION = ("\u1fbd", "\u02bc", "\u2019")

# ---------------------------------------------------------------------------------------------
# what the supplement states
# ---------------------------------------------------------------------------------------------

#: Table S10.2 and, for the elliptic nodes, section S10.11: (tokens supplied to the models, words with a
#: reference lemma, words with a nine-character tag, words without a lemma, words without a tag, words
#: with a tag whose length is not nine, elliptic nodes).
DENOMINATORS = {"gorman": (616646, 548803, 548593, 109, 22, 297, 8530),
                "pedalion": (274608, 238389, 238311, 24, 12, 90, 4914)}

#: Table S10.4: corpus -> prediction -> (occurrences, {corpus tag: occurrences}, {forms}).
MALFORMED = {
    "gorman": {"v-sagamn-": (2, {"v-sapamn-": 1, "v-sagamn-": 1}, {"ἐξελκύσας", "ἀκούσας"}),
               "v--pnd---": (1, {"v--pnd---": 1}, {"συνέχεσθαι"})},
    "pedalion": {"SYM": (6, {"n-_---__-": 3, "n--------": 1, "n-s---nn-": 1, "a--------": 1}, {"∠"}),
                 "v-sagamn-": (1, {"v-sapamn-": 1}, {"ἀκούσας"})},
}

#: Table S10.5: position -> (words, Stanza agreements, UDPipe agreements), per corpus.
POSITIONS = {
    "gorman": {1: (548583, 503965, 429540), 2: (54241, 49335, 46596), 3: (366966, 359667, 351260),
               4: (107642, 101562, 88976), 5: (107647, 104264, 98992), 6: (107610, 102868, 95985),
               7: (316327, 291854, 278582), 8: (316706, 302321, 289842), 9: (16476, 2993, 1506)},
    "pedalion": {1: (238298, 197668, 173578), 2: (35794, 27790, 25653), 3: (158248, 153776, 149400),
                 4: (50508, 46463, 39957), 5: (50555, 47809, 44490), 6: (50503, 47688, 44306),
                 7: (128610, 108957, 101791), 8: (128933, 119247, 112121), 9: (3354, 1319, 619)},
}
#: The paragraph on person (section S10.6): (corpus, model) -> (words in which the corpus marks person,
#: agreements, disagreements, disagreements with the hyphen in the prediction, their share of the
#: disagreements %, of them on words with p in the first position, share of the hyphen cases %,
#: disagreements on pronouns, share of all the disagreements %). The text gives all of these for Pedalion x
#: UDPipe; for the other three combinations it gives the disagreements and the two shares of the hyphen cases.
PERSON = {
    ("pedalion", "udpipe"): (35794, 25653, 10141, 8086, 79.7, 6146, 76.0, 6393, 63.0),
    ("gorman", "stanza"): (None, None, 4906, None, 82.6, None, 83.1, None, None),
    ("gorman", "udpipe"): (None, None, 7645, None, 76.6, None, 63.8, None, None),
    ("pedalion", "stanza"): (None, None, 8004, None, 87.1, None, 89.1, None, None),
}

#: Tables S10.6 and S10.7: part of speech -> (words lemma, Stanza %, UDPipe %, words tag, Stanza %, UDPipe %).
BY_POS = {
    "gorman": {"n": (110780, 82.2, 76.5, 110806, 86.3, 79.6), "v": (107782, 84.0, 63.4, 107642, 87.8, 75.8),
               "d": (79506, 92.6, 87.6, 79476, 76.7, 33.9), "l": (76363, 99.5, 97.8, 76355, 92.1, 79.8),
               "a": (54784, 87.0, 79.2, 54717, 60.0, 54.1), "c": (42328, 91.2, 87.4, 42327, 88.1, 71.8),
               "r": (38741, 93.4, 88.2, 38741, 96.6, 88.4), "p": (37488, 93.7, 92.1, 37488, 71.7, 36.0),
               "i": (922, 98.9, 98.8, 922, 98.5, 98.5)},
    "pedalion": {"v": (50556, 78.1, 58.5, 50555, 85.4, 71.9), "n": (43887, 78.4, 72.8, 43887, 79.3, 70.8),
                 "d": (32125, 88.9, 85.5, 32063, 65.2, 37.7), "l": (27094, 98.8, 96.5, 27094, 88.6, 73.6),
                 "p": (24400, 93.4, 90.1, 24400, 38.5, 18.4), "a": (20596, 81.2, 73.8, 20596, 65.8, 54.6),
                 "c": (15224, 92.2, 91.3, 15221, 71.9, 69.8), "r": (13655, 91.9, 87.9, 13655, 90.8, 85.3),
                 "b": (8556, 89.5, 85.8, 8555, 0.0, 0.0), "m": (1293, 84.1, 81.0, 1282, 6.3, 22.6),
                 "i": (990, 91.6, 91.1, 990, 80.4, 81.0)},
}

#: The comparison key (S10.8): corpus -> (fourth row with raw strings, difference from the normalised row,
#: cases that the raw comparison adds, of them due to the numbering, due to the Unicode composition,
#: cases that only the normalised comparison recognises).
COMPARISON_KEY = {"gorman": (27566, 8985, 8985, 8985, 0, 0),
                  "pedalion": (9803, 371, 372, 229, 143, 1)}

#: Table S10.10: corpus -> counts of the four categories (percentages are computed from them).
LEMMA_CATEGORIES = {"gorman": (3872, 2092, 1334, 11283), "pedalion": (1169, 1574, 584, 6105)}
LEMMA_CATEGORY_SHARES = {"gorman": (20.8, 11.3, 7.2, 60.7), "pedalion": (12.4, 16.7, 6.2, 64.7)}
#: Text of S10.10: citation forms of the fourth category that end / begin with an elision mark.
ELIDED_IN_RESIDUAL = {"gorman": (2862, 7), "pedalion": (1139, 12)}
#: Table S10.11: corpus -> [(substitution, words, {category: words})].
TOP_SUBSTITUTIONS = {
    "gorman": [("ἀλλά → ἀλλ\u1fbd", 651, {4: 651}), ("ἢ → ἤ", 611, {1: 611}), ("ὅς → ὁ", 513, {2: 80, 3: 433}),
               ("ἀλλά → ἀλλ\u02bc", 395, {4: 395}), ("δέ → -δέ", 386, {2: 79, 4: 307}),
               ("εἰς → ἐν", 374, {2: 1, 4: 373}), ("τις → τίς", 361, {1: 361}), ("διά → δι\u1fbd", 293, {4: 293}),
               ("ἐάν → ἄν", 240, {2: 42, 4: 198}), ("μη → μή", 167, {1: 167})],
    "pedalion": [("λέγω → εἶπον", 633, {4: 633}), ("δέω → δεῖ", 311, {4: 311}), ("ἀλλά → ἀλλ\u2019", 293, {4: 293}),
                 ("ὁράω → εἶδον", 227, {4: 227}), ("ὅς → ὁ", 202, {2: 11, 3: 191}),
                 ("μάλα → μάλιστα", 159, {4: 159}), ("μάλα → μᾶλλον", 153, {4: 153}),
                 ("μόνον → μόνος", 152, {2: 148, 4: 4}), ("ἀλλά → ἀλλ\u02bc", 125, {4: 125}),
                 ("λέγω → ἐρῶ", 106, {4: 106})],
}
#: The examples printed under Table S10.10: corpus -> {description: words}.
EXAMPLES = {
    "gorman": {"ἢ → ἤ": 611, "ἄρχων → ἄρχω": 108, "ὅς → ὁ": 513, "ὅς → ὁ, category 2": 80,
               "ὅς → ὁ, category 3, the models differ on the part of speech": 261,
               "ὅς → ὁ, category 3, both write p": 172, "ἄρχων → ἄρχω, category 2": 104,
               "ἀλλά → an elided citation form": 1100},
    "pedalion": {"ἄρχων → ἄρχω": 90, "ὅς → ὁ": 202, "ὅς → ὁ, category 2": 11,
                 "ὅς → ὁ, category 3, the models differ on the part of speech": 81,
                 "ὅς → ὁ, category 3, both write p": 110, "ἄρχων → ἄρχω, category 2": 82,
                 "ἀλλά → an elided citation form": 419, "λέγω → εἶπον": 633},
}


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def percent(part: int, whole: int) -> float:
    """One decimal, rounded half up, as a table written by hand would."""
    if not whole:
        return 0.0
    return float((Decimal(100 * part) / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("")


def split_tags(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """For each row, the nine characters of the tag (empty if it has not nine) and whether each is admitted."""
    codes, uniques = pd.factorize(text(series), sort=False)
    chars = np.full((len(uniques), TAG_LENGTH), "", dtype=object)
    valid = np.zeros((len(uniques), TAG_LENGTH), dtype=bool)
    for row, tag in enumerate(uniques):
        if len(tag) == TAG_LENGTH:
            for position, character in enumerate(tag):
                chars[row, position] = character
                valid[row, position] = character in (VALID_CHARACTERS.get(position, set()) | {"-"})
    return chars[codes], valid[codes]


def reduced(form: str) -> str:
    """Criterion (1) of S10.10: NFD, no combining marks, lower case, final sigma reduced to sigma."""
    decomposed = unicodedata.normalize("NFD", form)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().replace("ς", "σ")


class Report:
    def __init__(self) -> None:
        self.compared = 0
        self.different = 0

    def group(self, title: str) -> None:
        print(f"\n== {title} ==")
        print(f"  {'what':<84} {'stated':>14} {'obtained':>14}")

    def line(self, what: str, stated, obtained) -> None:
        same = stated == obtained
        self.compared += 1
        self.different += not same

        def show(value) -> str:
            if isinstance(value, bool):
                return str(value)
            if isinstance(value, int):
                return f"{value:,}"
            return str(value)
        stated_text, obtained_text = show(stated), show(obtained)
        if max(len(stated_text), len(obtained_text)) <= 14:
            print(f"  {what[:84]:<84} {stated_text:>14} {obtained_text:>14}{'' if same else '   DIFFERENT'}")
        elif same:
            # a long value (a list, a set, a dictionary): printed once, under the line
            print(f"  {what[:84]:<84} {'identical':>14} {'identical':>14}")
            print(f"      = {stated_text}")
        else:
            print(f"  {what[:84]:<84} {'':>14} {'':>14}   DIFFERENT")
            print(f"      stated:   {stated_text}")
            print(f"      obtained: {obtained_text}")


# ---------------------------------------------------------------------------------------------
# the blocks
# ---------------------------------------------------------------------------------------------

def denominators(report: Report, corpus: str, tokens: pd.DataFrame, stanza: pd.DataFrame) -> None:
    supplied, with_lemma, with_tag, no_lemma, no_tag, odd_tag, elliptic = DENOMINATORS[corpus]
    built = units.build_units(tokens)
    report.group(f"{TITLE[corpus]}: the denominators (Table S10.2) and the elliptic nodes (S10.11)")
    report.line("tokens supplied to the models (active, with a non-empty form)",
                supplied, len(prepare_model_input(built.active_records)))
    report.line("words with a reference lemma", with_lemma, int(stanza["eleggibile_lemma"].astype(bool).sum()))
    report.line("words with a nine-character tag", with_tag, int(stanza["eleggibile_postag"].astype(bool).sum()))
    lemma, tag = text(stanza["lemma"]).str.strip(), text(stanza["postag"]).str.strip()
    report.line("words without a lemma", no_lemma, int((lemma == "").sum()))
    report.line("words without a tag", no_tag, int((tag == "").sum()))
    report.line("words with a tag whose length is not nine", odd_tag, int(((tag != "") & (tag.str.len() != 9)).sum()))
    report.line("words, in the comparison table", len(built.words), len(stanza))
    artificial = text(tokens["artificial"]).str.strip().ne("") if "artificial" in tokens else pd.Series(False, index=tokens.index)
    placeholder = text(tokens["form"]).str.strip().str.fullmatch(r"\[\d+\]")
    report.line("elliptic nodes (attribute artificial, or a placeholder form [n])", elliptic,
                int((artificial | placeholder).sum()))


def malformed(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    report.group(f"{TITLE[corpus]}: the predictions without the AGDT positional form (Table S10.4, section S10.5)")
    for name, table in (("Stanza", stanza), ("UDPipe", udpipe)):
        eligible = table["eleggibile_postag"].astype(bool)
        bad = eligible & ~_ha_forma_agdt(table["postag_modello"])
        if name == "Stanza":
            report.line("predictions of Stanza without the positional form", 0, int(bad.sum()))
            continue
        found = table.loc[bad]
        stated = MALFORMED[corpus]
        report.line("predictions of UDPipe without the positional form", sum(v[0] for v in stated.values()), len(found))
        for prediction, (count, corpus_tags, forms) in stated.items():
            rows = found[text(found["postag_modello"]) == prediction]
            report.line(f"  {prediction}: occurrences", count, len(rows))
            report.line(f"  {prediction}: corpus tags at the same point",
                        dict(sorted(corpus_tags.items())),
                        dict(sorted(text(rows["postag"]).value_counts().items())))
            report.line(f"  {prediction}: forms", {nfc(f) for f in forms}, {nfc(f) for f in text(rows["form"])})
        coincide = int((text(found["postag_modello"]) == text(found["postag"])).sum())
        if corpus == "gorman":
            report.line("  of the three, prediction identical to the corpus tag (S10.5)", 2, coincide)
        report.line("words eligible for the tag", 548593 if corpus == "gorman" else 238311,
                    int(eligible.sum()))


def positions(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    report.group(f"{TITLE[corpus]}: agreement position by position (Table S10.5, section S10.6)")
    c_chars, _ = split_tags(stanza["postag"])
    eligible = stanza["eleggibile_postag"].astype(bool).to_numpy()
    models = {}
    for name, table in (("Stanza", stanza), ("UDPipe", udpipe)):
        models[name] = split_tags(table["postag_modello"])
    for position, (words, stanza_stated, udpipe_stated) in POSITIONS[corpus].items():
        k = position - 1
        filled = eligible & (c_chars[:, k] != "-") & (c_chars[:, k] != "")
        report.line(f"position {position}: words in which the corpus fills the position", words, int(filled.sum()))
        for (name, (m_chars, m_valid)), stated in zip(models.items(), (stanza_stated, udpipe_stated)):
            agree = filled & m_valid[:, k] & (m_chars[:, k] == c_chars[:, k])
            report.line(f"position {position}: agreements, {name}", stated, int(agree.sum()))


def person(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    report.group(f"{TITLE[corpus]}: person (paragraph \"Person\" of section S10.6)")
    c_chars, _ = split_tags(stanza["postag"])
    eligible = stanza["eleggibile_postag"].astype(bool).to_numpy()
    for name, table in (("stanza", stanza), ("udpipe", udpipe)):
        stated = PERSON.get((corpus, name))
        if stated is None:
            continue
        words, agree_stated, disagree_stated, hyphen_stated, hyphen_pct, pronoun_hyphen, pronoun_pct, pronoun_all, pronoun_all_pct = stated
        m_chars, m_valid = split_tags(table["postag_modello"])
        filled = eligible & (c_chars[:, 1] != "-") & (c_chars[:, 1] != "")
        agree = filled & m_valid[:, 1] & (m_chars[:, 1] == c_chars[:, 1])
        disagree = filled & ~agree
        hyphen = disagree & (m_chars[:, 1] == "-")
        pronoun = c_chars[:, 0] == "p"
        label = f"{name}"
        if words is not None:
            report.line(f"{label}: words in which the corpus marks person", words, int(filled.sum()))
            report.line(f"{label}: agreements", agree_stated, int(agree.sum()))
        report.line(f"{label}: disagreements", disagree_stated, int(disagree.sum()))
        if hyphen_stated is not None:
            report.line(f"{label}: disagreements with the hyphen in the prediction", hyphen_stated, int(hyphen.sum()))
        report.line(f"{label}: share of the disagreements with the hyphen (%)", hyphen_pct,
                    percent(int(hyphen.sum()), int(disagree.sum())))
        if pronoun_hyphen is not None:
            report.line(f"{label}: of those, on words with p in the first position", pronoun_hyphen,
                        int((hyphen & pronoun).sum()))
        report.line(f"{label}: share of pronouns among the predictions with the hyphen (%)", pronoun_pct,
                    percent(int((hyphen & pronoun).sum()), int(hyphen.sum())))
        if pronoun_all is not None:
            report.line(f"{label}: disagreements on pronouns", pronoun_all, int((disagree & pronoun).sum()))
            report.line(f"{label}: share of pronouns among all the disagreements (%)", pronoun_all_pct,
                        percent(int((disagree & pronoun).sum()), int(disagree.sum())))


def by_part_of_speech(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    table = "S10.6" if corpus == "gorman" else "S10.7"
    report.group(f"{TITLE[corpus]}: agreement by part of speech of the corpus (Table {table}, section S10.7, classes of at least 200 words)")
    first = text(stanza["postag"]).str[:1]
    obtained: dict[str, list] = {}
    for field in ("lemma", "postag"):
        eligible = stanza[f"eleggibile_{field}"].astype(bool)
        for name, model in (("stanza", stanza), ("udpipe", udpipe)):
            agree = model[f"accordo_{field}"].astype(bool) & eligible
            frame = pd.DataFrame({"pos": first[eligible].to_numpy(), "agree": agree[eligible].to_numpy()})
            grouped = frame.groupby("pos")["agree"].agg(["size", "sum"])
            for pos, row in grouped.iterrows():
                entry = obtained.setdefault(pos, [None] * 6)
                base = 0 if field == "lemma" else 3
                entry[base] = int(row["size"])
                entry[base + (1 if name == "stanza" else 2)] = percent(int(row["sum"]), int(row["size"]))
    shown = {p for p, v in obtained.items() if p and ((v[0] or 0) >= 200 or (v[3] or 0) >= 200)}
    report.line("parts of speech with at least 200 words (lemma or tag)", "".join(sorted(BY_POS[corpus])),
                "".join(sorted(shown)))
    labels = ("words (lemma)", "Stanza, lemma (%)", "UDPipe, lemma (%)", "words (tag)", "Stanza, tag (%)", "UDPipe, tag (%)")
    for pos, stated in BY_POS[corpus].items():
        for label, want, got in zip(labels, stated, obtained.get(pos, [None] * 6)):
            report.line(f"{pos}: {label}", want, got)


def comparison_key(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    report.group(f"{TITLE[corpus]}: the comparison key of the three-way comparison on the lemma (section S10.8)")
    merged = stanza.merge(udpipe[KEY + ["lemma", "lemma_modello", "lemma_modello_normalizzato"]], on=KEY,
                          suffixes=("_s", "_u"), validate="one_to_one")
    eligible = merged["eleggibile_lemma"].astype(bool).to_numpy()
    corpus_raw = text(merged["lemma_s"]).to_numpy()
    stanza_raw, udpipe_raw = text(merged["lemma_modello_s"]).to_numpy(), text(merged["lemma_modello_u"]).to_numpy()
    corpus_key = text(merged["lemma_normalizzato"]).to_numpy()
    stanza_key = text(merged["lemma_modello_normalizzato_s"]).to_numpy()
    udpipe_key = text(merged["lemma_modello_normalizzato_u"]).to_numpy()
    raw = eligible & (stanza_raw == udpipe_raw) & (stanza_raw != corpus_raw)
    normalised = eligible & (stanza_key == udpipe_key) & (stanza_key != corpus_key)
    added = raw & ~normalised
    gone = normalised & ~raw
    stated = COMPARISON_KEY[corpus]
    numbering = np.array([bool(re.fullmatch(r".*\d+", a)) and re.sub(r"\d+$", "", a) == b
                          for a, b in zip(corpus_raw[added], stanza_raw[added])])
    composition = np.array([nfc(a) == nfc(b) and a != b for a, b in zip(corpus_raw[added], stanza_raw[added])])
    report.line("the two models against the corpus, normalised key (Table S10.8)",
                18581 if corpus == "gorman" else 9432, int(normalised.sum()))
    report.line("the same with raw strings", stated[0], int(raw.sum()))
    report.line("difference between the raw and the normalised row", stated[1], int(raw.sum() - normalised.sum()))
    report.line("cases that the raw comparison adds", stated[2], int(added.sum()))
    report.line("  of them, the numeral appended to the lemma", stated[3], int(numbering.sum()))
    report.line("  of them, a different Unicode composition", stated[4], int(composition.sum()))
    report.line("cases that only the normalised comparison recognises", stated[5], int(gone.sum()))


def lemma_tables(report: Report, corpus: str, stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    report.group(f"{TITLE[corpus]}: the lemma, inside the cases of agreement against the corpus (Tables S10.10 and S10.11, section S10.10)")
    merged = stanza.merge(udpipe[KEY + ["lemma_modello_normalizzato", "postag_modello"]], on=KEY,
                          suffixes=("_s", "_u"), validate="one_to_one")
    eligible = merged["eleggibile_lemma"].astype(bool).to_numpy()
    corpus_key = text(merged["lemma_normalizzato"])
    stanza_key = text(merged["lemma_modello_normalizzato_s"])
    udpipe_key = text(merged["lemma_modello_normalizzato_u"])
    cases = merged[eligible & (stanza_key == udpipe_key).to_numpy() & (stanza_key != corpus_key).to_numpy()].copy()
    c_key, m_key = text(cases["lemma_normalizzato"]), text(cases["lemma_modello_normalizzato_s"])
    c_red, m_red = c_key.map(reduced), m_key.map(reduced)
    first = (c_red == m_red).to_numpy()
    c_pos = text(cases["postag"]).str[:1]
    s_pos, u_pos = text(cases["postag_modello_s"]).str[:1], text(cases["postag_modello_u"]).str[:1]
    second = ((s_pos == u_pos) & (s_pos != c_pos)).to_numpy()
    third = np.array([a.startswith(b) or b.startswith(a) for a, b in zip(c_red, m_red)])
    cases["category"] = np.select([first, ~first & second, ~first & ~second & third], [1, 2, 3], 4)
    n = len(cases)
    names = ("different spelling of the citation form", "different part of speech in the corpus and the models",
             "one citation form a prefix of the other", "residual")
    report.line("cases in which the two models agree against the corpus (Table S10.8)",
                18581 if corpus == "gorman" else 9432, n)
    for category, name in enumerate(names, start=1):
        count = int((cases["category"] == category).sum())
        report.line(f"category {category}: {name}", LEMMA_CATEGORIES[corpus][category - 1], count)
        report.line(f"category {category}: per cent", LEMMA_CATEGORY_SHARES[corpus][category - 1], percent(count, n))

    residual = m_key[cases["category"] == 4]
    ends = int(residual.map(lambda x: x[-1:] in ELISION).sum())
    begins = int(residual.map(lambda x: x[:1] in ELISION and x[-1:] not in ELISION).sum())
    report.line("category 4: model citation form ending with an elision mark", ELIDED_IN_RESIDUAL[corpus][0], ends)
    report.line("category 4: model citation form beginning with an elision mark", ELIDED_IN_RESIDUAL[corpus][1], begins)

    cases["pair"] = c_key + " → " + m_key
    observed = [(pair, int(count)) for pair, count in cases["pair"].value_counts().head(10).items()]
    stated_top = TOP_SUBSTITUTIONS[corpus]
    report.line("the ten most frequent substitutions, in order (Table S10.11)",
                [(nfc(p), w) for p, w, _ in stated_top], [(nfc(p), w) for p, w in observed])
    for pair, words, split in stated_top:
        inside = cases[cases["pair"].map(nfc) == nfc(pair)]
        counts = {int(k): int(v) for k, v in inside["category"].value_counts().items()}
        report.line(f"  {pair}: words by category", dict(sorted(split.items())), dict(sorted(counts.items())))

    def pair_cases(corpus_form: str, model_form: str) -> pd.DataFrame:
        return cases[(c_key.map(nfc) == nfc(corpus_form)) & (m_key.map(nfc) == nfc(model_form))]

    stated = EXAMPLES[corpus]
    for pair in ("ἢ → ἤ", "ἄρχων → ἄρχω", "ὅς → ὁ", "λέγω → εἶπον"):
        if pair in stated:
            a, b = pair.split(" → ")
            report.line(f"example {pair}", stated[pair], len(pair_cases(a, b)))
    if "ἄρχων → ἄρχω, category 2" in stated:
        inside = pair_cases("ἄρχων", "ἄρχω")
        report.line("example ἄρχων → ἄρχω, category 2", stated["ἄρχων → ἄρχω, category 2"],
                    int((inside["category"] == 2).sum()))
    inside = pair_cases("ὅς", "ὁ")
    report.line("example ὅς → ὁ, category 2", stated["ὅς → ὁ, category 2"], int((inside["category"] == 2).sum()))
    three = inside[inside["category"] == 3]
    report.line("example ὅς → ὁ, category 3, the models differ on the part of speech",
                stated["ὅς → ὁ, category 3, the models differ on the part of speech"],
                int((text(three["postag_modello_s"]).str[:1] != text(three["postag_modello_u"]).str[:1]).sum()))
    report.line("example ὅς → ὁ, category 3, both write p", stated["ὅς → ὁ, category 3, both write p"],
                int(((text(three["postag_modello_s"]).str[:1] == "p") & (text(three["postag_modello_u"]).str[:1] == "p")).sum()))
    if "ἢ → ἤ" in stated:
        report.line("example ἢ → ἤ, all in category 1", stated["ἢ → ἤ"], int((pair_cases("ἢ", "ἤ")["category"] == 1).sum()))
    elided = cases[(c_key.map(nfc) == nfc("ἀλλά")) & m_key.map(lambda x: x[:3] in ("ἀλλ", "ἁλλ") and x[-1:] in ELISION)]
    report.line("example ἀλλά → an elided citation form", stated["ἀλλά → an elided citation form"], len(elided))


# ---------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
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

    report = Report()
    for corpus, folder in folders.items():
        print(f"\n######## {TITLE[corpus]}  ({folder})")
        stanza = pd.read_parquet(folder / "stanza_comparison.parquet")
        udpipe = pd.read_parquet(folder / "udpipe_comparison.parquet")
        tokens = pd.read_parquet(folder / "tokens.parquet")
        denominators(report, corpus, tokens, stanza)
        malformed(report, corpus, stanza, udpipe)
        positions(report, corpus, stanza, udpipe)
        person(report, corpus, stanza, udpipe)
        by_part_of_speech(report, corpus, stanza, udpipe)
        comparison_key(report, corpus, stanza, udpipe)
        lemma_tables(report, corpus, stanza, udpipe)
    if set(folders) == set(CORPORA):
        report.group("Both corpora")
        report.line("words eligible for the tag, Gorman and Pedalion together (S10.5)", 786904,
                    DENOMINATORS["gorman"][2] + DENOMINATORS["pedalion"][2])
    print(f"\nRESULT: {report.compared} values compared, "
          + ("all reproduced" if not report.different else f"{report.different} not reproduced"))
    return 0 if report.compared and not report.different else 1


if __name__ == "__main__":
    sys.exit(main())
