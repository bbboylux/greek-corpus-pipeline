#!/usr/bin/env python
"""Recompute the concentration test of Supplement S8.1 (Tables S8.2 and S8.3, and § 6.1 of the article).

S8.1 asks whether the forms involved in a variation (a nucleus of the n-gram variation) are reported
by the checks more often than the forms of the corpus taken all together. The unit is the distinct form,
among the words, in NFC. From the files of a run this script computes, for each stratum:

    N   distinct forms among the words (``tokens.parquet``; the words are those of ``units.py``, S11.1)
    K   the forms of N that coincide with the form of at least one token carrying a finding
        (``findings.parquet``; findings on punctuation tokens count, as the note to Table S8.2 says)
    n   the forms of N involved in at least one variation: the nucleus of the four levels
        morphology, tag positions, context and lemmas, and both forms of the pair of the level
        dependencies (``variation_<level>.parquet``, columns ``nucleo`` and ``chiave``)
    k   the forms that are both

then the expected number n*K/N, the share of reported forms inside the nucleus (k/n) and in the corpus
(K/N), their ratio, the upper tail of the hypergeometric distribution, P(X >= k) with X drawn
without replacement (n forms from an urn of N forms of which K are reported), and the Holm correction
over the six strata (one family of six comparisons). The tail is computed exactly, with integers
(``math.comb``) and the ``decimal`` module, so that the very small values (10^-820 in Gorman) are
not lost to double precision; nothing but pandas is needed besides the program.

Every value is printed next to the one that Tables S8.2 and S8.3 state. The corrected values are compared
only when the six strata are given, because the family of S8.1 comprises the six. The exit status is
0 when every stated value is reproduced.

usage:
    python recompute_variation_concentration.py --workspace W        the runs written by rerun_diagnosis.py
    python recompute_variation_concentration.py RUN_FOLDER ...       other run folders (the study's own, or rerun-<stratum>)
"""
from __future__ import annotations

import argparse
import math
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import LABELS, SEP, STRATA, stratum_of

import pandas as pd

from greek_corpus_pipeline import units

getcontext().prec = 60
getcontext().Emin = -9_999_999
getcontext().Emax = 9_999_999

LEVELS = ("morfologia", "posizioni", "contesto", "dipendenze", "lemmi")
SMALLEST_SUBNORMAL = Decimal("4.9406564584124654E-324")     # the smallest positive double
SMALLEST_NORMAL = Decimal("2.2250738585072014E-308")

#: Table S8.2: N, K, n, k, expected, share in the nucleus (%), share in the corpus (%), ratio.
TABLE_S8_2 = {
    "gorman":          (69329, 5928, 12021, 2973, 1028, 24.7, 8.6, 2.89),
    "pedalion":        (45132, 4186, 5593, 1451, 519, 25.9, 9.3, 2.80),
    "glaux_auto":      (48502, 2999, 5074, 1091, 314, 21.5, 6.2, 3.48),
    "glaux_man":       (7219, 240, 461, 70, 15, 15.2, 3.3, 4.57),
    "glaux_conf_auto": (38234, 2453, 4580, 999, 294, 21.8, 6.4, 3.40),
    "glaux_conf_man":  (7159, 252, 587, 65, 21, 11.1, 3.5, 3.15),
}
#: Table S8.3: nominal p, corrected p (Holm), as mantissa and exponent of ten (two significant digits).
TABLE_S8_3 = {
    "gorman":          ("6.6", -820, "4.0", -819),
    "pedalion":        ("3.7", -347, "1.9", -346),
    "glaux_auto":      ("3.7", -342, "1.5", -341),
    "glaux_man":       ("4.4", -29, "8.8", -29),
    "glaux_conf_auto": ("9.9", -314, "3.0", -313),
    "glaux_conf_man":  ("9.6", -18, "9.6", -18),
}
#: Other figures of the text of S8.1.
PEDALION_FORMS_WITHOUT_NFC = 45410         # Table 2 of the article counts the strings as they stand
GLAUX_MAN_K_WORDS_ONLY = 239               # the note to Table S8.2


def nfc(text: object) -> str:
    return unicodedata.normalize("NFC", text) if isinstance(text, str) else ""


def measure(folder: Path) -> dict:
    tokens = pd.read_parquet(folder / "tokens.parquet")
    findings = pd.read_parquet(folder / "findings.parquet")
    words = units.build_units(tokens).words
    word_forms = {f for f in words["form"].map(nfc) if f}

    finding_forms = {f for f in findings["form"].map(nfc) if f} & word_forms
    # the same, counting only the findings that fall on a word of the table of the words
    on_words = findings.merge(words[["source_file", "document_id", "sentence_index", "token_index"]],
                              on=["source_file", "document_id", "sentence_index", "token_index"], how="inner")
    finding_forms_on_words = {f for f in on_words["form"].map(nfc) if f} & word_forms

    nucleus: set[str] = set()
    for level in LEVELS:
        table = pd.read_parquet(folder / f"variation_{level}.parquet", columns=["nucleo", "chiave"])
        if level == "dipendenze":
            for key in table["chiave"]:
                nucleus.update(nfc(part) for part in str(key).split(SEP))
        else:
            nucleus.update(nfc(form) for form in table["nucleo"])
    nucleus &= word_forms

    N, K, n = len(word_forms), len(finding_forms), len(nucleus)
    k = len(nucleus & finding_forms)
    return {
        "N": N, "K": K, "n": n, "k": k,
        "K_words_only": len(finding_forms_on_words),
        "expected": n * K / N,
        "share_nucleus": 100 * k / n, "share_corpus": 100 * K / N,
        "ratio": (k / n) / (K / N),
        "forms_raw": int(words["form"].dropna().nunique()),
    }


def upper_tail(N: int, K: int, n: int, k: int) -> Decimal:
    """P(X >= k) for X hypergeometric: n forms drawn without replacement from N, K of them reported."""
    top = min(n, K)
    numerator = sum(math.comb(K, x) * math.comb(N - K, n - x) for x in range(k, top + 1))
    return Decimal(numerator) / Decimal(math.comb(N, n))


def holm(p_values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Holm's step-down correction in exact decimal arithmetic."""
    m = len(p_values)
    corrected: dict[str, Decimal] = {}
    running = Decimal(0)
    for rank, name in enumerate(sorted(p_values, key=lambda s: p_values[s]), start=1):
        running = max(running, min(Decimal(1), (m - rank + 1) * p_values[name]))
        corrected[name] = running
    return corrected


def mantissa_exponent(value: Decimal) -> tuple[str, int]:
    """Two significant digits (rounded half up) and the exponent of ten: 6.6E-820 -> ('6.6', -820)."""
    if value == 0:
        return "0.0", 0
    exponent = value.adjusted()
    mantissa = (value.scaleb(-exponent)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if mantissa >= 10:
        mantissa, exponent = (mantissa / 10).quantize(Decimal("0.1")), exponent + 1
    return str(mantissa), exponent


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

    compared = different = 0

    def show(label: str, stated, obtained, text_stated: str, text_obtained: str) -> None:
        nonlocal compared, different
        same = stated == obtained
        compared += 1
        different += not same
        print(f"  {label:<54} {text_stated:>12} {text_obtained:>12}   {'same' if same else 'DIFFERENT'}")

    results: dict[str, dict] = {}
    for folder in folders:
        stratum = stratum_of(folder)
        if stratum is None:
            print(f"== {folder.name}: not a run folder of a known stratum; skipped")
            continue
        print(f"== {LABELS[stratum]}  ({folder.name}) ==")
        print(f"  {'quantity':<54} {'stated':>12} {'obtained':>12}")
        m = measure(folder)
        N, K, n, k, expected, nucleus_share, corpus_share, ratio = TABLE_S8_2[stratum]
        show("N  distinct forms among the words (NFC)", N, m["N"], f"{N:,}", f"{m['N']:,}")
        show("K  forms that carry a finding", K, m["K"], f"{K:,}", f"{m['K']:,}")
        show("n  forms involved in a variation", n, m["n"], f"{n:,}", f"{m['n']:,}")
        show("k  forms that are both", k, m["k"], f"{k:,}", f"{m['k']:,}")
        show("expected k if independent (n*K/N)", expected, round(m["expected"]),
             f"{expected:,}", f"{round(m['expected']):,}")
        show("share of reported forms in the nucleus (%)", nucleus_share, round(m["share_nucleus"], 1),
             f"{nucleus_share}", f"{round(m['share_nucleus'], 1)}")
        show("share of reported forms in the corpus (%)", corpus_share, round(m["share_corpus"], 1),
             f"{corpus_share}", f"{round(m['share_corpus'], 1)}")
        show("ratio of the two shares", ratio, round(m["ratio"], 2), f"{ratio:.2f}", f"{m['ratio']:.2f}")
        if stratum == "pedalion":
            print(f"  {'distinct forms without NFC (Table 2)':<54} {PEDALION_FORMS_WITHOUT_NFC:>12,} {m['forms_raw']:>12,}"
                  + ("   same" if m["forms_raw"] == PEDALION_FORMS_WITHOUT_NFC else "   DIFFERENT"))
            compared += 1
            different += m["forms_raw"] != PEDALION_FORMS_WITHOUT_NFC
        if stratum == "glaux_man":
            show("K counting only the findings on words", GLAUX_MAN_K_WORDS_ONLY, m["K_words_only"],
                 f"{GLAUX_MAN_K_WORDS_ONLY}", f"{m['K_words_only']}")
        results[stratum] = m
        results[stratum]["p"] = upper_tail(m["N"], m["K"], m["n"], m["k"])
        mantissa, exponent = mantissa_exponent(results[stratum]["p"])
        s_mant, s_exp, _, _ = TABLE_S8_3[stratum]
        show("nominal p (upper tail, exact)", (s_mant, s_exp), (mantissa, exponent),
             f"{s_mant}E{s_exp}", f"{mantissa}E{exponent}")
        print()

    if set(results) == set(STRATA):
        corrected = holm({s: results[s]["p"] for s in STRATA})
        print("== Holm correction over the six strata ==")
        print(f"  {'quantity':<54} {'stated':>12} {'obtained':>12}")
        for stratum in STRATA:
            _, _, c_mant, c_exp = TABLE_S8_3[stratum]
            mantissa, exponent = mantissa_exponent(corrected[stratum])
            show(f"corrected p, {LABELS[stratum]}", (c_mant, c_exp), (mantissa, exponent),
                 f"{c_mant}E{c_exp}", f"{mantissa}E{exponent}")
            significant = corrected[stratum] < Decimal("0.05")
            show(f"  significant at 0.05, {LABELS[stratum]}", True, significant, "yes", "yes" if significant else "no")
        # the statements of S8.1 on double precision
        below = [s for s in STRATA if results[s]["p"] < SMALLEST_SUBNORMAL]
        subnormal = [s for s in STRATA if SMALLEST_SUBNORMAL <= results[s]["p"] < SMALLEST_NORMAL]
        show("strata with p below the smallest double", ["gorman", "pedalion", "glaux_auto"], below,
             "3", str(len(below)))
        show("strata with p representable only as subnormal", ["glaux_conf_auto"], subnormal,
             "1", str(len(subnormal)))
    else:
        print("The six strata were not all given: the Holm correction (one family of six comparisons) was not computed.")
    print()
    print(f"RESULT: {compared} values compared, " + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
