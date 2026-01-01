# -*- coding: utf-8 -*-
"""The reference texts of the checks are not rewritten by accident.

The scientific logic may evolve.  The titles and descriptions of the checks that
have *not* changed scientifically are to be left alone: a round of work on the
interface, a pass of stylistic uniformisation or a rewriting “for clarity” are not
sufficient reasons to change them.

The baseline is in ``data/canonical_check_texts.json``, versioned together with the
code.  If a check really changes definition, its text is changed in that file together
with the catalogue: that is the explicit gesture that this test forces one to make.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

RESOURCE = ROOT / "data" / "canonical_check_texts.json"


@pytest.fixture(scope="module")
def canonical() -> dict:
    return json.loads(RESOURCE.read_text(encoding="utf-8"))


def test_the_resource_exists_and_declares_its_count(canonical):
    assert canonical["_source"], "the resource does not declare what it is"
    assert canonical["_count"] == len(canonical["controlli"])


def test_every_frozen_check_still_exists_in_the_catalogue(canonical):
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    missing = [rid for rid in canonical["controlli"] if rid not in RULE_CATALOG]
    assert not missing, (
        "frozen checks that disappeared from the catalogue: " + ", ".join(missing)
        + " — if they were withdrawn, remove them from " + RESOURCE.name + " too")


def test_the_italian_titles_have_not_changed(canonical):
    from greek_corpus_pipeline.rule_catalog import rule_name
    culprits = []
    for rid, texts in canonical["controlli"].items():
        current = rule_name(rid, "it")
        if current != texts["titolo"]:
            culprits.append(f"\n  {rid}\n    expected: {texts['titolo']}\n"
                            f"    found   : {current}")
    assert not culprits, (
        "titles rewritten without an explicit decision:" + "".join(culprits))


def test_the_italian_descriptions_have_not_changed(canonical):
    from greek_corpus_pipeline.rule_catalog import rule_description
    culprits = []
    for rid, texts in canonical["controlli"].items():
        current = rule_description(rid, "it")
        if current != texts["descrizione"]:
            culprits.append(f"\n  {rid}\n    expected: {texts['descrizione'][:120]}…\n"
                            f"    found   : {current[:120]}…")
    assert not culprits, (
        "descriptions rewritten without an explicit decision:" + "".join(culprits))


def test_every_check_has_an_english_text_that_is_not_the_italian(canonical):
    """Italian is the source language of the canonical texts; English is a
    translation, and must be present."""
    from greek_corpus_pipeline.rule_catalog import rule_description, rule_name
    culprits = []
    for rid in canonical["controlli"]:
        if not rule_name(rid, "en") or rule_name(rid, "en") == rule_name(rid, "it"):
            culprits.append(f"{rid} (title)")
        if (not rule_description(rid, "en")
                or rule_description(rid, "en") == rule_description(rid, "it")):
            culprits.append(f"{rid} (description)")
    assert not culprits, "without an English text: " + ", ".join(culprits)


def test_the_csv_of_the_catalogue_carries_the_same_texts(canonical):
    """The exported sheet and the catalogue must not be able to diverge."""
    import csv
    path = ROOT / "data" / "catalogo_controlli.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = {r["id"]: r for r in csv.DictReader(f, delimiter=";")}
    culprits = []
    for rid, texts in canonical["controlli"].items():
        row = rows.get(rid)
        if row is None:
            culprits.append(f"{rid} is missing from the CSV")
            continue
        if row["nome"] != texts["titolo"]:
            culprits.append(f"{rid}: different title in the CSV")
        if row["descrizione"] != texts["descrizione"]:
            culprits.append(f"{rid}: different description in the CSV")
    assert not culprits, "\n".join(culprits)


def test_the_baseline_covers_every_check(canonical):
    """No check of the catalogue is left without a reference text.

    If the catalogue gained a check, this test would say so instead of letting it in
    without a text that somebody has read.
    """
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    outside = set(RULE_CATALOG) - set(canonical["controlli"])
    assert not outside, f"checks without a reference text: {sorted(outside)}"
    assert len(canonical["controlli"]) == len(RULE_CATALOG)
