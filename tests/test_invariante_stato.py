# -*- coding: utf-8 -*-
"""No corpus loaded, no corpus data visible.

The two things must be tied together: if the heading says that there is no corpus, there
cannot be a full table below; and if there is a full table below, the heading must say
which corpus it is.
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
from PyQt6.QtWidgets import QApplication, QTabWidget  # noqa: E402


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def finestra(application, tmp_path):
    from gui_qt.main_window import MainWindow
    workspace = tmp_path / "workspace"; workspace.mkdir()
    finestra = MainWindow(workspace)
    yield finestra
    finestra.close()
    # Deferred destructions are processed here, inside the module that created them:
    # left in the queue they would kill the next module while it builds its own window.
    application.processEvents()


def _carica(finestra, tokens: pd.DataFrame) -> None:
    from greek_corpus_pipeline.storage import run_dir
    stato = finestra.state
    stato.run_id = "prova"; stato.corpus_name = "corpus di prova"
    stato.tokens = tokens
    directory = run_dir(stato.workspace, stato.run_id)
    directory.mkdir(parents=True, exist_ok=True)
    tokens.to_parquet(directory / "tokens.parquet", index=False)
    stato.invalidate()


def _tabelle_piene(pagina) -> list[str]:
    from gui_qt.widgets import DataTable
    piene = []
    for tabella in pagina.findChildren(DataTable):
        frame = tabella.dataframe()
        if frame is not None and not getattr(frame, "empty", True):
            piene.append(f"{type(pagina).__name__}: {list(frame.columns)[:4]}")
    return piene


def test_senza_corpus_nessuna_tabella_mostra_dati(finestra, application, tokens):
    """First load, then unload: the pages must keep nothing."""
    from gui_qt.main_window import STEPS

    _carica(finestra, tokens)
    for chiave, *_ in STEPS:
        if finestra._pages.get(chiave) is None:
            continue
        finestra._go_to(chiave)
        pagina = finestra._pages[chiave]
        for schede in pagina.findChildren(QTabWidget):
            for i in range(schede.count()):
                schede.setCurrentIndex(i)
        application.processEvents()

    stato = finestra.state
    stato.run_id = None
    stato.tokens = pd.DataFrame(); stato.findings = pd.DataFrame()
    stato.arcs = pd.DataFrame(); stato.variation = {}
    stato.invalidate()

    # The reference pages show the AGDT scheme, which does not come from the corpus and
    # is there even with nothing loaded: the invariant concerns the data of the corpus.
    from gui_qt.main_window import RIFERIMENTO

    piene = []
    for chiave, *_ in STEPS:
        pagina = finestra._pages.get(chiave)
        if pagina is None or chiave in RIFERIMENTO:
            continue
        finestra._go_to(chiave)
        application.processEvents()
        piene += _tabelle_piene(pagina)
    assert not piene, "full tables with no corpus:\n" + "\n".join(piene[:10])


def test_senza_corpus_l_intestazione_lo_dice(finestra):
    from gui_qt.i18n import tr
    stato = finestra.state
    stato.run_id = None
    stato.tokens = pd.DataFrame()
    stato.invalidate()
    finestra._update_badge()
    assert finestra._corpus_badge.text() == tr("app.no_corpus")


def test_con_dati_visibili_l_intestazione_nomina_il_corpus(finestra, tokens):
    """The contradiction to prevent: data below, “no corpus” above."""
    _carica(finestra, tokens)
    finestra._go_to("overview")
    testo = finestra._corpus_badge.text()
    assert "corpus di prova" in testo
    assert str(len(tokens)) in testo.replace(".", "").replace(",", "")


def test_l_intestazione_si_aggiorna_a_ogni_cambio_di_pagina(finestra, tokens):
    """The defect to prevent: a heading that is not recomputed."""
    from gui_qt.i18n import tr
    assert finestra._corpus_badge.text() == tr("app.no_corpus")
    _carica(finestra, tokens)
    finestra._go_to("stats")
    assert finestra._corpus_badge.text() != tr("app.no_corpus")


def test_l_intestazione_dice_l_unita_e_non_token(finestra, tokens):
    """“token” is none of the five units with which the program counts."""
    from gui_qt.i18n import T
    _carica(finestra, tokens)
    for lingua, atteso in (("it", "record importati"), ("en", "imported records")):
        T.set_language(lingua)
        finestra._update_badge()
        assert atteso in finestra._corpus_badge.text()
    T.set_language("it")


def test_i_numeri_seguono_la_lingua(finestra):
    from gui_qt.i18n import T, counted, number
    T.set_language("it")
    assert number(16191) == "16.191"
    assert counted("documento", 2) == "2 documenti"
    assert counted("documento", 1) == "1 documento"
    T.set_language("en")
    assert number(16191) == "16,191"
    assert counted("documento", 2) == "2 documents"
    assert counted("documento", 1) == "1 document"
    T.set_language("it")


def test_nessun_numero_e_formattato_a_mano_nell_interfaccia():
    """No number is formatted by hand: the separator follows the language."""
    colpevoli = []
    for percorso in (ROOT / "gui_qt").rglob("*.py"):
        if "__pycache__" in str(percorso) or percorso.name == "i18n.py":
            continue
        for numero, riga in enumerate(percorso.read_text(encoding="utf-8").splitlines(), 1):
            if ':,}' in riga and "number(" not in riga:
                colpevoli.append(f"{percorso.name}:{numero} {riga.strip()[:80]}")
    assert not colpevoli, "hand-formatted numbers:\n" + "\n".join(colpevoli[:10])
