"""Helpers shared by the reproducibility scripts. This module is not run on its own.

Importing it puts ``src/`` and the package root on ``sys.path`` (so that the scripts
work from a plain extraction, without installing the package) and defines the names
of the six strata of the study, the key of a finding, the fingerprint of a set of
findings and the function that summarises one run of the program.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]
REFERENCE = PACKAGE / "reproducibility" / "reference"
sys.path[:0] = [str(PACKAGE / "src"), str(PACKAGE)]

#: The six strata of the study, in the order of Table S11.1.
STRATA = ("gorman", "pedalion", "glaux_auto", "glaux_man", "glaux_conf_auto", "glaux_conf_man")

LABELS = {
    "gorman": "Gorman",
    "pedalion": "Pedalion",
    "glaux_auto": "GLAUx automatic",
    "glaux_man": "GLAUx manual",
    "glaux_conf_auto": "GLAUx confirmation automatic",
    "glaux_conf_man": "GLAUx confirmation manual",
}

#: stratum -> name of the folder of the study's run (in ``workspace/runs`` of the study).
STUDY_RUNS = {
    "gorman": "20260909-053400-gorman",
    "pedalion": "20260909-060742-pedalion",
    "glaux_auto": "20260909-064439-glaux-campione",
    "glaux_man": "20260909-070338-glaux-campione-manuale",
    "glaux_conf_auto": "20260909-065606-glaux-conferma",
    "glaux_conf_man": "20260909-070407-glaux-conferma-manuale",
}

#: stratum -> (sample, stratum) as ``data/glaux_sample.csv`` and ``glaux_sample.select`` name them.
GLAUX_SAMPLES = {
    "glaux_auto": ("principale", "automatico"),
    "glaux_man": ("principale", "manuale"),
    "glaux_conf_auto": ("conferma", "automatico"),
    "glaux_conf_man": ("conferma", "manuale"),
}

#: The name under which a stratum is loaded. It is only a label: it is written in the
#: ``corpus`` column of the token table and in the name of the run folder, and no
#: result depends on it.
CORPUS_NAMES = {
    "gorman": "gorman",
    "pedalion": "pedalion",
    "glaux_auto": "glaux_main_automatic",
    "glaux_man": "glaux_main_manual",
    "glaux_conf_auto": "glaux_confirmation_automatic",
    "glaux_conf_man": "glaux_confirmation_manual",
}

#: The five planes on which the n-gram variation family looks for nuclei, as the
#: tables of a run name them (``variation_<plane>.parquet``), and their English names.
PLANES = ("morfologia", "posizioni", "contesto", "dipendenze", "lemmi")
PLANE_EN = {"morfologia": "morphology", "posizioni": "tag_positions", "contesto": "context",
            "dipendenze": "dependencies", "lemmi": "lemmas"}

#: The program stores the family, the class, the treatment and the severity of a check under
#: Italian keys (``rule_catalog.py``); these are the English names used in the reference tables
#: (the names of Table S1.1: violation, variant, case to check; automatic, manual).
EN_FAMILY = {"morfologia": "morphology", "lemma": "lemma", "sintassi": "syntax",
             "testo": "text", "accordo": "agreement"}
EN_CLASS = {"violazione": "violation", "variante": "variant", "verifica": "case_to_check"}
EN_TREATMENT = {"automatica": "automatic", "manuale": "manual", "normalizzazione": "normalisation"}
EN_SEVERITY = {"errore": "error", "sospetto": "suspect"}

#: A finding is identified by these four columns (Supplement S11).
KEY = ["rule_id", "document_id", "sentence_id", "token_id"]
SEP = "␟"        # the separator of the four fields in the fingerprint


def stratum_of(folder: Path) -> str | None:
    """The stratum a run folder belongs to: a folder of the study or ``rerun-<stratum>``."""
    for stratum, name in STUDY_RUNS.items():
        if folder.name == name:
            return stratum
    for stratum in STRATA:
        if folder.name == f"rerun-{stratum}":
            return stratum
    return None


def key_lines(findings) -> list[str]:
    """One text line per finding: the four key fields joined by the separator."""
    text = findings[KEY[0]].astype("string")
    for column in KEY[1:]:
        text = text + SEP + findings[column].astype("string")
    return text.tolist()


def fingerprint(lines: list[str]) -> str:
    """First twelve hexadecimal characters of the MD5 of the sorted lines (Table S11.1)."""
    return hashlib.md5("\n".join(sorted(lines)).encode("utf-8")).hexdigest()[:12]


def summarise_run(run: Path) -> dict:
    """The numbers of Table S11.1 for the run stored in the folder *run*.

    ``nuclei`` is ``None`` when the run has no variation tables (the variation family
    was not run).
    """
    import pandas as pd

    from greek_corpus_pipeline import rule_catalog as rc
    from greek_corpus_pipeline import units

    tokens = pd.read_parquet(run / "tokens.parquet")
    findings = pd.read_parquet(run / "findings.parquet")
    built = units.build_units(tokens)
    lines = key_lines(findings)

    planes: dict[str, int] = {}
    for plane in PLANES:
        table = run / f"variation_{plane}.parquet"
        if table.is_file():
            planes[plane] = len(pd.read_parquet(table))
    nuclei = sum(planes.values()) if len(planes) == len(PLANES) else None

    rule_ids = findings["rule_id"].astype(str)
    classes = rule_ids.map(rc.rule_class)
    return {
        "imported_records": len(tokens),
        "active_records": len(built.active_records),
        "words": len(built.words),
        "analyzable_links": len(built.analyzable_links),
        "analyzable_sentences": len(built.analyzable_sentences),
        "findings": len(findings),
        "active_checks": int(rule_ids.nunique()),
        "nuclei": nuclei,
        "findings_fingerprint": fingerprint(lines),
        "planes": planes,
        "per_check": rule_ids.value_counts().to_dict(),
        "violations": int((classes == "violazione").sum()),
        "to_verify": int((classes == "verifica").sum()),
        "variants": int((classes == "variante").sum()),
        "keys": findings[KEY].astype("string").fillna(""),
    }
