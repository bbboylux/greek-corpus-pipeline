# -*- coding: utf-8 -*-
"""The “Lemma profile” card, really pressed.

Verifies what the card promises: the note speaks of logDice and the table must show it,
counted on the words and not on the records, with the spellings of the lemma that the
corpus uses.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_word_sketch import CHIAVI  # noqa: E402


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def scheda(application, tmp_path):
    from gui_qt.pages.base import AppState
    from gui_qt.pages.stats_page import StatsPage

    stato = AppState(workspace=tmp_path)
    stato.tokens = CHIAVI.copy()
    pagina = StatsPage(stato)
    pagina.build()
    pagina.refresh()
    yield pagina
    pagina.deleteLater()


def test_la_scheda_mostra_le_associazioni_con_logdice(scheda):
    scheda._par_campo.setText("λέγω")
    scheda._profilo_parola()

    tabella = scheda._par_tabelle["associazioni"].dataframe()
    assert not tabella.empty
    for colonna in ("relazione", "direzione", "lemma associato", "co-occorrenze", "logDice"):
        assert colonna in tabella.columns
    assert "λόγος" in set(tabella["lemma associato"])


def test_la_scheda_conta_sulle_parole_e_non_sui_record(scheda):
    """The lemma is worth 5 among the words of the text, and the card says 5."""
    scheda._par_campo.setText("λέγω")
    scheda._profilo_parola()
    tabella = scheda._par_tabelle["associazioni"].dataframe()
    assert set(tabella["occorrenze lemma"]) == {5}


def test_la_scheda_mostra_le_grafie_del_lemma(scheda):
    """λέγω3, λέγω and λέγω1 are a single lemma, and the card says so."""
    scheda._par_campo.setText("λέγω")
    scheda._profilo_parola()
    grafie = scheda._par_tabelle["grafie"].dataframe()
    assert set(grafie.columns) == {"grafia", "occorrenze"}
    assert "λέγω3" in set(grafie["grafia"])
    assert int(grafie["occorrenze"].sum()) == 5


def test_la_scheda_non_ha_tabelle_di_conteggi_grezzi(scheda):
    """“What it depends on” and “What it governs” carry a measure, not only the pairs."""
    assert "teste" not in scheda._par_tabelle
    assert "dipendenti" not in scheda._par_tabelle


def test_un_lemma_assente_lo_dice_e_non_lascia_tabelle_vecchie(scheda):
    scheda._par_campo.setText("λέγω")
    scheda._profilo_parola()
    assert not scheda._par_tabelle["associazioni"].dataframe().empty

    scheda._par_campo.setText("ἵππος")
    scheda._profilo_parola()
    assert scheda._par_tabelle["associazioni"].dataframe().empty
    assert scheda._par_tabelle["grafie"].dataframe().empty
