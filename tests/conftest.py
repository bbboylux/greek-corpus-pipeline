# -*- coding: utf-8 -*-
"""A minimal but real AGDT corpus, and its tables, for the tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture(autouse=True, scope="module")
def lingua_di_partenza_per_ogni_modulo():
    """Every test module starts in the language in which the program starts, and leaves it so.

    The translator is shared by the whole interface. A module that switches to Italian and
    does not switch back would make the next one start in the wrong language, and the
    order in which the modules run would decide whether the tests pass.
    """
    try:
        from gui_qt.i18n import T
    except Exception:                                  # noqa: BLE001
        yield
        return
    T.set_language("en")
    yield
    T.set_language("en")


@pytest.fixture(autouse=True)
def senza_finestre_modali(monkeypatch):
    """No test stops on a dialogue window.

    A modal ``QMessageBox`` waits for a click that never arrives in a test: the
    process stays there until somebody kills it, and it is not a fault of the
    program — in front of a person that message is right — but of the way in which
    it is being run.  The answers are those that the user of the program would give:
    “I have read it” to the warnings, “yes” to the question on closing.  Whoever
    wants to test the dialogue itself redefines it on their own, and their
    redefinition wins because it comes later.
    """
    try:
        from PyQt6.QtWidgets import QMessageBox
    except Exception:                                  # noqa: BLE001
        yield
        return
    for nome, risposta in (("critical", QMessageBox.StandardButton.Ok),
                           ("information", QMessageBox.StandardButton.Ok),
                           ("warning", QMessageBox.StandardButton.Ok),
                           ("about", None),
                           ("question", QMessageBox.StandardButton.Yes)):
        if hasattr(QMessageBox, nome):
            monkeypatch.setattr(QMessageBox, nome,
                                staticmethod(lambda *a, _r=risposta, **k: _r))
    yield


XML = """<?xml version="1.0" encoding="UTF-8"?>
<treebank version="1.1">
  <sentence id="1" document_id="test-doc" subdoc="1">
    <word id="1" form="τὴν" lemma="ὁ" postag="l-s---fa-" relation="ATR" head="2"/>
    <word id="2" form="πόλιν" lemma="πόλις" postag="n-s---fa-" relation="OBJ" head="3"/>
    <word id="3" form="ἐφύλαττον" lemma="φυλάσσω" postag="v3piia---" relation="PRED" head="0"/>
    <word id="4" form="οἱ" lemma="ὁ" postag="l-p---mn-" relation="ATR" head="5"/>
    <word id="5" form="στρατιῶται" lemma="στρατιώτης1" postag="n-p---mn-" relation="SBJ" head="3"/>
  </sentence>
  <sentence id="2" document_id="test-doc" subdoc="1">
    <word id="1" form="καὶ" lemma="καί" postag="c--------" relation="AuxY" head="3"/>
    <word id="2" form="οἱ" lemma="ὁ" postag="l-p---mn-" relation="ATR" head="3"/>
    <word id="3" form="ἄνδρες" lemma="ἀνήρ" postag="n-p---mn" relation="SBJ" head="4"/>
    <word id="4" form="ἦλθον" lemma="ἔρχομαι" postag="v3plia---" relation="PRED" head="0"/>
  </sentence>
</treebank>
"""


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "xml"
    directory.mkdir()
    (directory / "test-doc.xml").write_text(XML, encoding="utf-8")
    return directory


@pytest.fixture
def tokens(corpus_dir: Path) -> pd.DataFrame:
    from greek_corpus_pipeline.xmlio import load_corpus_from_directory
    return load_corpus_from_directory(corpus_dir)


@pytest.fixture
def corrected(tokens: pd.DataFrame) -> pd.DataFrame:
    """The corpus with two corrections made by hand: a lemma and a label."""
    frame = tokens.copy()
    frame.loc[frame["form"] == "στρατιῶται", "lemma"] = "στρατιώτης"
    frame.loc[frame["form"] == "ἄνδρες", "postag"] = "n-p---mn-"
    return frame


@pytest.fixture
def manual() -> pd.DataFrame:
    from greek_corpus_pipeline.gold import MANUAL_COLUMNS
    return pd.DataFrame([
        {"document_id": "test-doc", "sentence_id": "1", "token_id": "5",
         "form": "στρατιῶται", "corrected_lemma": "στρατιώτης",
         "corrected_postag": "", "corrected_relation": ""},
        {"document_id": "test-doc", "sentence_id": "2", "token_id": "3",
         "form": "ἄνδρες", "corrected_lemma": "",
         "corrected_postag": "n-p---mn-", "corrected_relation": ""},
    ], columns=MANUAL_COLUMNS)


@pytest.fixture
def stanza_like(tokens: pd.DataFrame) -> pd.DataFrame:
    """A comparison table like the one that the program saves after Stanza.

    The fake model guesses everything except the lemma of στρατιῶται, where it writes
    the form without the trailing number — that is exactly what the user will correct.
    It is the case that makes the test interesting: the agreement with the original
    corpus is lower than the agreement with the gold.
    """
    frame = tokens[["document_id", "sentence_id", "token_id", "form",
                    "lemma", "postag"]].copy()
    frame = frame.rename(columns={"lemma": "lemma_reference",
                                  "postag": "postag_reference"})
    frame["lemma_stanza"] = frame["lemma_reference"]
    frame["postag_stanza"] = frame["postag_reference"]
    frame.loc[frame["form"] == "στρατιῶται", "lemma_stanza"] = "στρατιώτης"
    frame.loc[frame["form"] == "ἄνδρες", "postag_stanza"] = "n-p---mn-"
    return frame


# ---------------------------------------------------------------------------
# The real corpora: where they are, when they are there
# ---------------------------------------------------------------------------
#
# Some tests measure the program on the six frozen corpora — Gorman, Pedalion and
# the four GLAUx samples — which this repository does not contain and could not
# contain: they are third-party resources, each with its own licence, and weigh
# hundreds of megabytes.
#
# Where they are is stated by the environment variable ``GCP_CORPORA``; without it
# those tests are skipped, with a message that says why. The path is not written
# inside the tests, so that the tests make sense on any computer.

CORPORA_ENV = "GCP_CORPORA"


def corpora_dir() -> Path | None:
    """The folder of the frozen corpora, if whoever runs the tests has indicated it."""
    dichiarata = os.environ.get(CORPORA_ENV, "").strip()
    if not dichiarata:
        return None
    percorso = Path(dichiarata).expanduser()
    return percorso if percorso.is_dir() else None


def corpus_tokens(nome: str) -> Path | None:
    """``tokens.parquet`` of one of the six strata, or ``None`` if it is not there."""
    radice = corpora_dir()
    if radice is None:
        return None
    percorso = radice / "runs" / f"run-{nome}" / "tokens.parquet"
    return percorso if percorso.is_file() else None


def findings_dir() -> Path | None:
    """The folder with the frozen findings, if it has been indicated."""
    radice = corpora_dir()
    if radice is None:
        return None
    percorso = radice / "giro"
    return percorso if percorso.is_dir() else None
