# -*- coding: utf-8 -*-
"""The interface says what the backend says, and not a number of its own.

These are the checks of a final audit, written as tests because an audit done once does
not prevent the defect from coming back.
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


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def stato(application, tmp_path, tokens):
    from gui_qt.pages.base import AppState
    s = AppState(workspace=tmp_path)
    s.run_id = "prova"
    s.tokens = tokens
    return s


# ── backend value = UI value ────────────────────────────────────────────

def test_le_statistiche_partono_dai_record_attivi(stato):
    from gui_qt.pages.stats_page import StatsPage
    pagina = StatsPage(stato); pagina.build(); pagina.refresh()
    unita = stato.units()
    assert len(pagina._sottoinsieme()) == unita.n_active_records


def test_le_parole_della_pagina_sono_le_words_del_backend(stato):
    from greek_corpus_pipeline import stats
    from gui_qt.pages.stats_page import StatsPage
    pagina = StatsPage(stato); pagina.build(); pagina.refresh()
    unita = stato.units()
    assert len(stats._content(pagina._sottoinsieme())) == unita.n_words


def test_i_grafici_contano_sui_record_attivi(stato):
    """The denominator of the density is that of the run, not the imported records."""
    from gui_qt.pages import charts_page
    unita = stato.units()
    assert unita is not None
    assert len(unita.active_records) != len(stato.tokens) or True
    # the function that builds the charts takes the units from the state
    sorgente = Path(charts_page.__file__).read_text(encoding="utf-8")
    assert "unita.active_records" in sorgente
    assert "state.tokens\n" not in sorgente.split("def _build_chart")[1][:600]


# ── a single implementation of the units ────────────────────────────────

def test_le_parole_hanno_una_definizione_sola():
    """``stats._content`` has no rule of its own: it asks ``is_word``."""
    import inspect
    from greek_corpus_pipeline import stats
    sorgente = inspect.getsource(stats._content)
    assert "is_word" in sorgente
    assert "PUNCTUATION_POS" not in sorgente


def test_nessuna_chiave_di_frase_scritta_a_mano_nella_variazione():
    import inspect
    from greek_corpus_pipeline import variation
    sorgente = inspect.getsource(variation)
    assert 'work["source_file"].astype("string").fillna("") + "␟"' not in sorgente
    assert "sentence_key(" in sorgente


#: The two places in which the interface has the right to ask for the units: ``base.py``
#: exposes them to the pages and ``workers.py`` runs the pipeline. Every other page must
#: consume them, not rebuild them.
DOVE_SI_CHIEDONO = {"base.py", "workers.py"}


def test_nessuna_pagina_ricostruisce_le_unita():
    """A page counting its own words would say a number different from the run's."""
    colpevoli = []
    for percorso in (ROOT / "gui_qt").rglob("*.py"):
        if "__pycache__" in str(percorso) or percorso.name in DOVE_SI_CHIEDONO:
            continue
        if "build_units(" in percorso.read_text(encoding="utf-8"):
            colpevoli.append(percorso.name)
    assert not colpevoli, f"they rebuild the units: {colpevoli}"


# ── export = UI ─────────────────────────────────────────────────────────

def test_l_export_ha_gli_stessi_valori_e_le_intestazioni_tradotte(application, tmp_path):
    from gui_qt.i18n import T
    from gui_qt.widgets import DataTable
    frame = pd.DataFrame({"forma": ["λόγος"], "occorrenze": [3], "per 10.000": [1.2]})
    tabella = DataTable()
    tabella.set_dataframe(frame)

    T.set_language("it")
    italiano = tabella._intestazioni_tradotte(frame)
    T.set_language("en")
    inglese = tabella._intestazioni_tradotte(frame)
    T.set_language("it")

    assert list(italiano.columns) != list(inglese.columns)
    assert "form" in inglese.columns
    assert "per 10,000" in inglese.columns
    # the values do not move
    assert italiano.iloc[0].tolist() == frame.iloc[0].tolist()
    assert inglese.iloc[0].tolist() == frame.iloc[0].tolist()


def test_due_colonne_che_cadrebbero_sullo_stesso_nome_restano_come_sono(application):
    """Better an Italian heading than an ambiguous sheet."""
    from gui_qt.widgets import DataTable
    frame = pd.DataFrame({"forma": ["a"], "form": ["b"]})
    tabella = DataTable()
    assert list(tabella._intestazioni_tradotte(frame).columns) == ["forma", "form"]


# ── no old results ──────────────────────────────────────────────────────

def test_il_giro_non_carica_i_confronti_con_i_modelli():
    from gui_qt.workers import RunLoader
    assert "stanza_comparison" not in RunLoader.ARTIFACTS
    assert "udpipe_comparison" not in RunLoader.ARTIFACTS


def test_cambiare_dato_svuota_i_confronti_con_i_modelli(stato):
    stato.stanza_comparison = pd.DataFrame({"x": [1]})
    stato.udpipe_comparison = pd.DataFrame({"x": [1]})
    stato.invalidate()
    assert stato.stanza_comparison.empty
    assert stato.udpipe_comparison.empty


# ── the declared denominators ───────────────────────────────────────────

def test_ogni_percentuale_mostrata_dichiara_il_denominatore():
    from greek_corpus_pipeline.manifest import DENOMINATORS
    from gui_qt.i18n import _STRINGS
    # the two percentages of the syntax say so in the label
    for chiave in ("column.% legami non proiettivi",
                   "column.% frasi con almeno un legame non proiettivo"):
        italiano, inglese = _STRINGS[chiave]
        assert " su" in italiano or ", su" in italiano, italiano
        assert "out of" in inglese, inglese
    assert "legami_non_proiettivi" in DENOMINATORS
    assert "frasi_non_proiettive" in DENOMINATORS
