# -*- coding: utf-8 -*-
"""The count of the nuclei comes from the backend, never from the cap on the rows shown.

The defect to prevent is this: a table that shows 300 and a summary that says 300
because it counted the rows on screen instead of the nuclei.  The scientific number
cannot depend on how tall the window is.
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
def pagina(application, tmp_path, tokens):
    from gui_qt.pages.base import AppState
    from gui_qt.pages.variation_page import VariationPage
    stato = AppState(workspace=tmp_path)
    stato.run_id = "prova"
    stato.tokens = tokens
    vista = VariationPage(stato)
    vista.build()
    yield vista
    vista.deleteLater()
    application.processEvents()


def _voci(pagina) -> dict[str, int]:
    """The cards of the numbers, read as whoever looks reads them: name -> value."""
    from PyQt6.QtWidgets import QLabel
    voci = {}
    griglia = pagina._conto._grid
    for indice in range(griglia.count()):
        scheda = griglia.itemAt(indice).widget()
        if scheda is None:
            continue
        etichette = scheda.findChildren(QLabel)
        if len(etichette) < 2:
            continue
        valore, nome = etichette[0].text(), etichette[1].text()
        testo = valore.replace(".", "").replace(",", "")
        voci[nome] = int(testo) if testo.isdigit() else testo
    return voci


def test_il_conto_per_piano_e_quello_del_backend(pagina, tokens):
    """Five planes, five totals, and they are those that the suite returns."""
    from greek_corpus_pipeline.variation import run_variation_suite
    from gui_qt.i18n import tr
    from gui_qt.pages.variation_page import PIANI

    pagina.refresh()
    pagina._calcola(forzato=True)
    unita = pagina.state.units()
    atteso = run_variation_suite(unita.active_records)

    voci = _voci(pagina)
    for piano in PIANI:
        etichetta = tr(f"variation.plane.{piano}")
        assert voci[etichetta] == len(atteso[piano]), \
            f"the plane “{piano}” says {voci[etichetta]} and the backend {len(atteso[piano])}"
    assert voci[tr("variation.total")] == sum(len(atteso[p]) for p in PIANI)


def test_il_conto_non_e_il_numero_di_righe_mostrate(pagina):
    """If the summary counted the rows on screen, a cap would change it.

    Here the cap is lowered to two rows and the summary does not move.
    """
    from gui_qt.i18n import tr
    from gui_qt.pages.variation_page import PIANI
    from gui_qt.widgets import DataTable

    pagina.refresh()
    pagina._calcola(forzato=True)
    prima = _voci(pagina)

    originale = DataTable.MAX_DISPLAY_ROWS
    try:
        DataTable.MAX_DISPLAY_ROWS = 2
        for tabella in pagina._tabelle.values():
            tabella.set_dataframe(tabella.dataframe())
        pagina._calcola(forzato=True)
        dopo = _voci(pagina)
    finally:
        DataTable.MAX_DISPLAY_ROWS = originale

    for piano in PIANI:
        etichetta = tr(f"variation.plane.{piano}")
        assert dopo[etichetta] == prima[etichetta]
    assert dopo[tr("variation.total")] == prima[tr("variation.total")]


def test_una_tabella_troncata_lo_dichiara(application, tmp_path):
    """“mostrate le prime 2 di 5” (“showing the first 2 of 5”): the cap is made visible,
    not silently imposed."""
    from gui_qt.i18n import tr
    from gui_qt.widgets import DataTable

    tabella = DataTable()
    originale = DataTable.MAX_DISPLAY_ROWS
    try:
        DataTable.MAX_DISPLAY_ROWS = 2
        tabella.set_dataframe(pd.DataFrame({"nucleo": list("abcde")}))
        testo = tabella._count.text()
    finally:
        DataTable.MAX_DISPLAY_ROWS = originale
    assert tr("table.capped") in testo
    assert "2" in testo and "5" in testo
    tabella.deleteLater()
    application.processEvents()


def test_i_piani_della_pagina_sono_quelli_del_backend():
    """No list of planes rewritten in the interface."""
    from greek_corpus_pipeline.variation import run_variation_suite
    from gui_qt.pages.variation_page import PIANI
    import inspect
    sorgente = inspect.getsource(run_variation_suite)
    for piano in PIANI:
        assert f'"{piano}"' in sorgente, f"the plane “{piano}” does not exist in the backend"
