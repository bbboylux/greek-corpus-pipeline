#!/usr/bin/env python
"""Recompute, from the comparison tables of Stanza and UDPipe, the counts of Supplement S10.

The comparison tables (``stanza_comparison.parquet`` and ``udpipe_comparison.parquet`` in the folder
of a run of Gorman or Pedalion) put the annotation of the corpus and the prediction of a model side
by side, word by word. From the two tables of a corpus this script recomputes, with the procedure
that S10.13 describes:

  * Table S10.3, the eight main measures (agreements, denominator, rate, predictions that have the AGDT
    form and malformed ones), and the same rates to one decimal as in Table 9 of the article;
  * Table S10.8, the five mutually exclusive outcomes of the three-way comparison on the lemma
    and on the tag (the agreement of corpus and model is the one recorded in the columns
    ``accordo_lemma`` and ``accordo_postag``; the agreement of the two models is the equality of
    the normalised lemmas, or of the tags when both are interpretable), and the different counts
    of the function ``three_way_agreement`` of ``modelcmp.py`` that S10.13 mentions;
  * the particle ``g`` (S10.9 and § 7.5 of the article): the words the models tag g, those on
    which they agree, and those among them that the corpus tags d--------; a block of information
    after each corpus shows how 2,735 (complete tag d-------- replaced by g--------) and 2,778
    (first position d replaced by g) of Gorman relate;
  * the substitutions of the complete tag and of the first position on which the two models agree
    against the corpus (S10.9): counts, forms and shares;
  * the ninth position, the degree (S10.6): which words fill it and where the models agree.

Before the counts, the provenance recorded in the evaluation file of each model run
(``stanza_evaluation.json``, ``udpipe_evaluation.json``: version of the model, corpus fingerprint, resource
fingerprint, tokens supplied to the model) is compared with Table S10.1
(``reference/table_S10_1_provenance.csv``). Every count is printed next to the one that the supplement
states, which ``reference/s10_model_counts.csv`` records with the section where it appears. Values that the
supplement does not state (for instance the Pedalion figures for a quantity that it gives only for
Gorman) are not compared. The exit status is 0 when every stated value is reproduced.

usage:
    python recompute_model_counts.py --workspace W        runs ``rerun-gorman`` and ``rerun-pedalion``
    python recompute_model_counts.py --gorman RUN_FOLDER --pedalion RUN_FOLDER
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import REFERENCE

import json

import pandas as pd

from greek_corpus_pipeline import modelcmp
from greek_corpus_pipeline.model_eval import _ha_forma_agdt

KEY = ["source_file", "document_id", "sentence_index", "token_index"]
TABLES = ("stanza_comparison.parquet", "udpipe_comparison.parquet")


def three_way(merged: pd.DataFrame, field: str) -> dict[str, int]:
    """The five outcomes of Table S10.8 for *field* (``lemma`` or ``postag``), as S10.13 defines them."""
    eligible = merged[f"eleggibile_{field}_s"].astype(bool) & merged[f"eleggibile_{field}_u"].astype(bool)
    corpus_stanza = merged[f"accordo_{field}_s"].astype(bool)
    corpus_udpipe = merged[f"accordo_{field}_u"].astype(bool)
    if field == "lemma":
        models = merged["lemma_modello_normalizzato_s"].astype(str) == merged["lemma_modello_normalizzato_u"].astype(str)
    else:
        stanza = merged["postag_modello_s"].fillna("").astype(str)
        udpipe = merged["postag_modello_u"].fillna("").astype(str)
        models = (stanza == udpipe) & _ha_forma_agdt(stanza) & _ha_forma_agdt(udpipe)
    return {
        "all_three_agree": int((eligible & corpus_stanza & corpus_udpipe).sum()),
        "corpus_and_stanza_against_udpipe": int((eligible & corpus_stanza & ~corpus_udpipe).sum()),
        "corpus_and_udpipe_against_stanza": int((eligible & ~corpus_stanza & corpus_udpipe).sum()),
        "two_models_against_corpus": int((eligible & ~corpus_stanza & ~corpus_udpipe & models).sum()),
        "no_pair_agrees": int((eligible & ~corpus_stanza & ~corpus_udpipe & ~models).sum()),
        "total": int(eligible.sum()),
    }


def headline(table: pd.DataFrame, model: str) -> dict[str, float | int]:
    """The eight main measures of Table S10.3 (and the rates of Table 9 of the article) for one model."""
    values: dict[str, float | int] = {}
    for field, name in (("lemma", "lemma"), ("postag", "tag")):
        eligible = table[f"eleggibile_{field}"].astype(bool)
        agree = table[f"accordo_{field}"].astype(bool) & eligible
        values[f"S10.3.{model}.{name}.agreements"] = int(agree.sum())
        values[f"S10.3.{model}.{name}.denominator"] = int(eligible.sum())
        rate = 100 * int(agree.sum()) / int(eligible.sum())
        values[f"S10.3.{model}.{name}.rate"] = round(rate, 2)
        values[f"S10.3.{model}.{name}.rate_1dp"] = round(rate, 1)
        if field == "postag":
            interpretable = int((eligible & _ha_forma_agdt(table["postag_modello"].fillna("").astype(str))).sum())
            values[f"S10.3.{model}.tag.interpretable"] = interpretable
            values[f"S10.3.{model}.tag.malformed"] = int(eligible.sum()) - interpretable
    return values


def compute(stanza: pd.DataFrame, udpipe: pd.DataFrame) -> dict[str, float | int]:
    values: dict[str, float | int] = {}
    values.update(headline(stanza, "stanza"))
    values.update(headline(udpipe, "udpipe"))
    merged = stanza.merge(udpipe, on=KEY, suffixes=("_s", "_u"), how="inner")
    for field, name in (("lemma", "lemma"), ("postag", "tag")):
        for outcome, count in three_way(merged, field).items():
            values[f"S10.8.{name}.{outcome}"] = count

    summary, _ = modelcmp.three_way_agreement(stanza, udpipe, field="postag")
    row = summary.set_index("esito")["token"]
    values["S10.13.modelcmp_tag_two_models_against_corpus"] = int(row["i due modelli contro il corpus"])
    values["S10.13.modelcmp_tag_words"] = int(row["TOTALE allineati"])

    corpus_tag = stanza["postag"].fillna("").astype(str)
    stanza_tag = stanza["postag_modello"].fillna("").astype(str)
    udpipe_tag = udpipe["postag_modello"].fillna("").astype(str)

    # The particle g.
    eligible = stanza["eleggibile_postag"].astype(bool) & udpipe["eleggibile_postag"].astype(bool)
    both_g = eligible & stanza_tag.str[:1].eq("g") & udpipe_tag.str[:1].eq("g")
    values["S10.9.g.corpus_words"] = int(corpus_tag.str[:1].eq("g").sum())
    values["S10.9.g.stanza_words"] = int(stanza_tag.str[:1].eq("g").sum())
    values["S10.9.g.udpipe_words"] = int(udpipe_tag.str[:1].eq("g").sum())
    values["S10.9.g.models_agree"] = int(both_g.sum())
    values["S10.9.g.models_agree_corpus_d"] = int((both_g & corpus_tag.eq("d--------")).sum())

    # The substitutions on which the two models agree against the corpus.
    agreed = eligible & (stanza_tag == udpipe_tag) & (stanza_tag != corpus_tag)
    n = int(agreed.sum())
    values["S10.9.agreed_substitutions"] = n
    for name, before, after in (("d_to_c", "d--------", "c--------"), ("d_to_g", "d--------", "g--------"),
                                ("b_to_c", "b--------", "c--------")):
        mask = agreed & corpus_tag.eq(before) & stanza_tag.eq(after)
        values[f"S10.9.fulltag.{name}.words"] = int(mask.sum())
        values[f"S10.9.fulltag.{name}.forms"] = int(stanza.loc[mask, "form"].nunique())
    complete = (corpus_tag + ">" + stanza_tag)[agreed].value_counts()
    big = complete[complete > 1000]
    values["S10.9.fulltag.over_1000.count"] = len(big)
    values["S10.9.fulltag.over_1000.share"] = round(100 * big.sum() / n, 1)
    first = (corpus_tag.str[:1] + ">" + stanza_tag.str[:1])[agreed].value_counts()
    frequent = first[first >= 1000]
    for pair, count in first.items():
        values[f"S10.9.pair.{pair}"] = int(count)
    values["S10.9.pair.count_at_least_1000"] = len(frequent)
    values["S10.9.pair.share"] = round(100 * frequent.sum() / n, 1)

    # The ninth position, the degree.
    nine = corpus_tag.str.len().eq(9)
    degree = corpus_tag.str[8:9]
    filled = nine & ~degree.isin(["-"])
    values["S10.6.degree.eligible"] = int(stanza["eleggibile_postag"].astype(bool).sum())
    values["S10.6.degree.corpus_fills"] = int(filled.sum())
    values["S10.6.degree.underscore"] = int((nine & degree.eq("_")).sum())
    values["S10.6.degree.p"] = int((nine & degree.eq("p")).sum())
    comparative = nine & degree.isin(["c", "s"])
    values["S10.6.degree.cs"] = int(comparative.sum())
    for model, tag in (("stanza", stanza_tag), ("udpipe", udpipe_tag)):
        position = tag.str[8:9]
        values[f"S10.6.degree.{model}_fills"] = int((nine & tag.str.len().eq(9) & ~position.isin(["-"])).sum())
        values[f"S10.6.degree.{model}_agrees_cs"] = int((comparative & position.eq(degree)).sum())
        disagree = filled & ~position.eq(degree)
        values[f"S10.6.degree.{model}_disagreements"] = int(disagree.sum())
        values[f"S10.6.degree.{model}_disagreements_model_hyphen"] = int(
            (disagree & degree.isin(["c", "s"]) & position.eq("-")).sum())
    return values


def explain_particle(stanza: pd.DataFrame, udpipe: pd.DataFrame) -> None:
    """Print how the numbers about the particle ``g`` of S10.9 and § 7.5 relate to one another.

    Two of them look alike and are not the same thing. The complete tag ``d--------`` replaced by
    ``g--------`` (Table S10.9) counts the words whose corpus tag is exactly ``d--------``; the pair
    d→g of the first position (list of the twelve pairs) counts every word whose corpus tag *begins*
    with d. The difference is made of the words whose corpus tag begins with d but is another tag.
    This block is information, not a comparison with a stated value.
    """
    corpus = stanza["postag"].fillna("").astype(str)
    stanza_tag = stanza["postag_modello"].fillna("").astype(str)
    udpipe_tag = udpipe["postag_modello"].fillna("").astype(str)
    eligible = stanza["eleggibile_postag"].astype(bool) & udpipe["eleggibile_postag"].astype(bool)
    both_g = eligible & stanza_tag.str[:1].eq("g") & udpipe_tag.str[:1].eq("g")
    agreed = eligible & (stanza_tag == udpipe_tag) & (stanza_tag != corpus)
    complete = agreed & corpus.eq("d--------") & stanza_tag.eq("g--------")
    first = agreed & corpus.str[:1].eq("d") & stanza_tag.str[:1].eq("g")
    print("  how the numbers about the particle g relate (information, not compared)")
    print(f"    words on which both models write a tag that begins with g:      {int(both_g.sum()):>9,}")
    print(f"      of which the two tags are identical:                          {int((both_g & (stanza_tag == udpipe_tag)).sum()):>9,}")
    print(f"      of which the corpus tag is exactly d-------- (complete tag):  {int((both_g & corpus.eq('d--------')).sum()):>9,}")
    print(f"      of which the corpus tag begins with d (first position):       {int((both_g & corpus.str[:1].eq('d')).sum()):>9,}")
    print(f"    substitutions on which the models agree against the corpus:")
    print(f"      d-------- replaced by g-------- (complete tag, Table S10.9):   {int(complete.sum()):>9,}")
    print(f"      d replaced by g at the first position (list of pairs):        {int(first.sum()):>9,}")
    rest = first & ~complete
    if rest.any():
        counts = (corpus + " -> " + stanza_tag)[rest].value_counts()
        print("      the difference is made of: "
              + "; ".join(f"{pair} ({int(n):,})" for pair, n in counts.items()))
    print()


def provenance_reference() -> dict[tuple[str, str], dict[str, str]]:
    with (REFERENCE / "table_S10_1_provenance.csv").open(encoding="utf-8", newline="") as handle:
        return {(r["corpus"], r["model"]): r for r in csv.DictReader(handle)}


def check_provenance(corpus: str, folder: Path) -> tuple[int, int]:
    """Compare the provenance of the two model runs of *folder* with Table S10.1.

    Returns the number of values compared and the number that differ. An evaluation file that is
    absent is reported and not counted.
    """
    compared = different = 0
    reference_rows = provenance_reference()
    print(f"  provenance of the model runs (Table S10.1)")
    print(f"  {'model':<8} {'value':<22} {'stated':>20} {'obtained':>20}")
    for model in ("stanza", "udpipe"):
        path = folder / f"{model}_evaluation.json"
        if not path.is_file():
            print(f"  {model:<8} {path.name} is absent: not compared")
            continue
        recorded = json.loads(path.read_text(encoding="utf-8"))["provenienza"]
        stated = reference_rows[(corpus, model)]
        for label, key, column in (("version", "modello_versione", "version"),
                                   ("corpus fingerprint", "impronta_corpus", "corpus_fingerprint"),
                                   ("resource fingerprint", "risorse_modello", "resource_fingerprint"),
                                   ("tokens supplied", "record_dati_al_modello", "tokens_supplied")):
            got, want = str(recorded.get(key)), stated[column]
            same = got == want
            compared += 1
            different += not same
            print(f"  {model:<8} {label:<22} {want:>20} {got:>20}   {'same' if same else 'DIFFERENT'}")
    print()
    return compared, different


def reference() -> dict[tuple[str, str], tuple[str, str, float]]:
    with (REFERENCE / "s10_model_counts.csv").open(encoding="utf-8", newline="") as handle:
        return {(r["corpus"], r["id"]): (r["section"], r["quantity"], float(r["expected"]))
                for r in csv.DictReader(handle)}


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

    expected = reference()
    compared = different = 0
    for corpus, folder in folders.items():
        stanza, udpipe = (pd.read_parquet(folder / name) for name in TABLES)
        values = compute(stanza, udpipe)
        print(f"== {corpus}  ({folder}) ==")
        seen, wrong = check_provenance(corpus, folder)
        compared += seen
        different += wrong
        print(f"  {'section':<8} {'quantity':<78} {'stated':>10} {'obtained':>10}")
        for (c, key), (section, quantity, stated) in expected.items():
            if c != corpus:
                continue
            got = values.get(key)
            compared += 1
            same = got is not None and abs(float(got) - stated) < 1e-9
            different += not same
            shown = "not computed" if got is None else (f"{got:,}" if isinstance(got, int) else f"{got}")
            stated_text = f"{stated:,.0f}" if stated == int(stated) and "share" not in key else f"{stated}"
            print(f"  {section:<8} {quantity[:78]:<78} {stated_text:>10} {shown:>10}   {'same' if same else 'DIFFERENT'}")
        print()
        explain_particle(stanza, udpipe)
    print(f"RESULT: {compared} stated values compared (provenance and counts), "
          + ("all reproduced" if not different else f"{different} not reproduced"))
    return 0 if compared and not different else 1


if __name__ == "__main__":
    sys.exit(main())
