# -*- coding: utf-8 -*-
"""Every command that looks pressable must really do something.

A visible, enabled button that does not respond is worse than an absent
button: whoever works tries twice, nothing happens, and from that moment does
not trust the rest of the page.  A list of charts that at the second entry
leaves the first chart on the screen is the same thing, only worse, because
the screen keeps showing something and that something is wrong.

These tests look at no number: they look at whether the program responds.
None of them touches a count, a denominator or a definition.
"""
from __future__ import annotations

import hashlib
import io
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
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QTabWidget,
)


#: The only exception allowed: a command that no signal listens to, but whose
#: position is *read* by another command when it starts — the boxes of the
#: check families, which “Diagnostic findings” reads, and the second of the two
#: source buttons, which “Load” reads.  Those commands carry in the code of the
#: page the property ``letto_al_via`` (“read at start”), written next to the
#: line that builds them: that is where the documentation of the exception is,
#: not in a list of labels here, which would change with the language.
PROPRIETA_ECCEZIONE = "letto_al_via"


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def finestra(application, tmp_path, tokens):
    """The real window, with a real corpus and a real set of findings."""
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.storage import run_dir
    from gui_qt.main_window import MainWindow

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    vista = MainWindow(workspace)
    stato = vista.state
    stato.run_id = "prova"
    stato.corpus_name = "prova"
    stato.tokens = tokens
    cartella = run_dir(workspace, "prova")
    cartella.mkdir(parents=True, exist_ok=True)
    tokens.to_parquet(cartella / "tokens.parquet", index=False)
    stato.findings = analyze_postags(tokens)
    assert not stato.findings.empty
    stato.invalidate()
    vista._update_badge()
    vista._update_rail()
    # The window must really be shown: a box opened inside a window that was never shown
    # stays ``isVisible() == False``, and the test could not tell “it opened” from “it
    # did not open”.
    vista.resize(1500, 940)
    vista.show()
    application.processEvents()
    yield vista
    vista.deleteLater()
    application.processEvents()


def _impronta_figura(vista) -> str:
    """What is drawn now: the figure, or the fact that there is none."""
    figura = getattr(vista, "_figure", None)
    if figura is None:
        return "vuoto"
    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=36)
    return hashlib.md5(buffer.getvalue()).hexdigest()[:16]


def _stato_vuoto(vista) -> bool:
    """The box that says in words why there is nothing to draw."""
    return (not vista._empty.isHidden()
            and bool(vista._empty_title.text().strip()))


def _attendi(application, prova, secondi: float = 25.0) -> bool:
    """Waits for a background job, running the event loop as Qt would."""
    import time
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        application.processEvents()
        try:
            if prova():
                application.processEvents()
                return True
        except Exception:                                  # noqa: BLE001
            pass
        time.sleep(0.03)
    return False


def _pagina_grafici(finestra, application):
    finestra._go_to("charts")
    application.processEvents()
    return finestra._pages["charts"]


# ── 1. every entry of the chart list responds ────────────────────────────
def test_ogni_voce_dei_grafici_disegna_o_dice_perche_no(finestra, application):
    """No entry can stay mute: either a figure comes out, or an explanation."""
    pagina = _pagina_grafici(finestra, application)
    assert pagina._list.count() > 0, "the list of charts is empty"
    muti = []
    for indice in range(pagina._list.count()):
        pagina._list.setCurrentRow(indice)
        application.processEvents()
        chiave = pagina._list.item(indice).data(256)
        disegnata = getattr(pagina._view, "_figure", None) is not None
        spiegata = _stato_vuoto(pagina._view)
        if not (disegnata or spiegata):
            muti.append(chiave)
    assert not muti, f"entries that neither draw nor explain: {muti}"


def test_le_voci_non_disponibili_dicono_che_cosa_manca(finestra, application):
    """Without the models the chart does not exist, and the page says so in writing."""
    from gui_qt.i18n import tr
    pagina = _pagina_grafici(finestra, application)
    assert not finestra.state.has_both_models, "this test applies without models"
    trovata = False
    for indice in range(pagina._list.count()):
        voce = pagina._list.item(indice)
        if not voce.data(257):        # UserRole + 1: what is missing
            continue
        trovata = True
        pagina._list.setCurrentRow(indice)
        application.processEvents()
        assert _stato_vuoto(pagina._view), (
            f"the entry “{voce.text()}” does not explain why it cannot be drawn")
        assert pagina._view._empty_title.text() == tr("chart.unavailable")
        assert pagina._view._empty_body.text().strip()
        assert not pagina._view._save.isEnabled()
        assert not pagina._view._copy.isEnabled()
    assert trovata, "no entry turns out to be unavailable: the test proves nothing"


def test_una_figura_assente_cancella_quella_di_prima(application):
    """``set_figure(None)`` must empty the view, not return silently.

    If it returned silently the view would keep the previous figure, and whoever had
    asked for another chart would read the numbers of the one before.
    """
    from matplotlib.figure import Figure
    from gui_qt.chart_view import ChartView
    vista = ChartView()
    figura = Figure(figsize=(3, 2))
    figura.add_subplot(111).plot([0, 1], [0, 1])
    vista.set_figure(figura, "una didascalia", "un'unita'")
    assert vista._figure is figura
    assert vista._save.isEnabled() and vista._copy.isEnabled()
    vista.set_figure(None, "niente da disegnare")
    assert vista._figure is None, "the previous figure stayed"
    assert vista._canvas.isHidden(), "the previous canvas stayed on screen"
    assert not vista._empty.isHidden()
    assert vista._empty_title.text() == "niente da disegnare"
    assert vista._caption.text() == "", "the previous caption stayed"
    assert vista._unit.text() == "", "the previous unit stayed"
    assert not vista._save.isEnabled(), "a figure that does not exist can be saved"
    assert not vista._copy.isEnabled(), "a figure that does not exist can be copied"
    vista.deleteLater()
    application.processEvents()


# ── 2. switching from one chart to another really replaces it ────────────
def test_cambiare_grafico_sostituisce_il_precedente(finestra, application):
    """A then B: B must stay on the screen, never A."""
    pagina = _pagina_grafici(finestra, application)
    disegnabili = [indice for indice in range(pagina._list.count())
                   if not pagina._list.item(indice).data(257)]
    assert len(disegnabili) >= 2, "at least two drawable charts are needed"
    viste = []
    for indice in disegnabili:
        pagina._list.setCurrentRow(indice)
        application.processEvents()
        viste.append((pagina._list.item(indice).data(256),
                      _impronta_figura(pagina._view),
                      pagina._view._caption.text()))
    for (chiave_a, figura_a, _), (chiave_b, figura_b, _) in zip(viste, viste[1:]):
        assert figura_a != figura_b, (
            f"going from “{chiave_a}” to “{chiave_b}” the figure did not change")
    didascalie = {didascalia for _, _, didascalia in viste}
    assert len(didascalie) > 1, "the caption does not follow the chart"


def test_dal_grafico_al_riquadro_vuoto_e_ritorno(finestra, application):
    """An unavailable entry must erase the chart that was there before."""
    pagina = _pagina_grafici(finestra, application)
    disegnabile = next(indice for indice in range(pagina._list.count())
                       if not pagina._list.item(indice).data(257))
    mancante = next((indice for indice in range(pagina._list.count())
                     if pagina._list.item(indice).data(257)), None)
    if mancante is None:
        pytest.skip("in this state all the charts are available")
    pagina._list.setCurrentRow(disegnabile)
    application.processEvents()
    assert getattr(pagina._view, "_figure", None) is not None
    pagina._list.setCurrentRow(mancante)
    application.processEvents()
    assert getattr(pagina._view, "_figure", None) is None, (
        "the previous chart stayed on the screen")
    assert pagina._view._canvas.isHidden(), (
        "the canvas of the previous chart is still on screen")
    pagina._list.setCurrentRow(disegnabile)
    application.processEvents()
    assert getattr(pagina._view, "_figure", None) is not None, (
        "going back, the chart is not redrawn")


# ── 3. clicking the entry already chosen ─────────────────────────────────
def test_riclic_sulla_voce_gia_scelta_ridisegna(finestra, application):
    """Pressing the same entry twice redraws, and redraws the same thing."""
    pagina = _pagina_grafici(finestra, application)
    indice = next(i for i in range(pagina._list.count())
                  if not pagina._list.item(i).data(257))
    pagina._list.setCurrentRow(indice)
    application.processEvents()
    prima = getattr(pagina._view, "_figure", None)
    impronta_prima = _impronta_figura(pagina._view)
    pagina._list.itemClicked.emit(pagina._list.item(indice))
    application.processEvents()
    dopo = getattr(pagina._view, "_figure", None)
    assert dopo is not None, "clicking again left the view without a figure"
    assert dopo is not prima, "clicking again did not redraw"
    assert _impronta_figura(pagina._view) == impronta_prima, (
        "the same chart, redrawn, came out different")


# ── 4. the toolbar of the tables ─────────────────────────────────────────
def test_la_barra_delle_tabelle_risponde(finestra, application, tmp_path):
    """Filter, columns, copy and export: four commands, four effects."""
    finestra._go_to("errors")
    application.processEvents()
    tabella = finestra._pages["errors"]._table
    # The list is filled by a background job: without waiting for it the test would
    # measure a table that is still empty.
    _attendi(application, lambda: tabella._model.rowCount() > 0)
    assert tabella._model.rowCount() > 0, "the table is empty"

    intere = tabella._model.rowCount()
    tabella._search.setText("zzzzz-che-non-esiste-zzzzz")
    tabella._apply_filter()
    application.processEvents()
    assert tabella._model.rowCount() < intere, "the filter does not filter"
    tabella._search.setText("")
    tabella._apply_filter()
    application.processEvents()
    assert tabella._model.rowCount() == intere, "the filter does not reset"

    # The choice of columns opens a menu: the menu is the effect, and must be seen.
    from PyQt6.QtWidgets import QMenu
    aperti = []
    originale = QMenu.exec
    QMenu.exec = lambda self, *a, **k: (aperti.append(len(self.actions())), None)[1]
    try:
        tabella._columns_button.click()
        application.processEvents()
    finally:
        QMenu.exec = originale
    assert aperti and aperti[0] > 0, "the columns button opens nothing"

    QApplication.clipboard().clear()
    tabella._copy_button.click()
    application.processEvents()
    assert QApplication.clipboard().text().strip(), "the copy copied nothing"
    assert tabella._esito.text().strip(), "the copy does not say whether it succeeded"

    destinazione = tmp_path / "tabella.csv"
    from PyQt6.QtWidgets import QFileDialog
    salva = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: (str(destinazione), "CSV (*.csv)"))
    try:
        tabella._export_button.click()
        application.processEvents()
    finally:
        QFileDialog.getSaveFileName = salva
    assert destinazione.exists() and destinazione.stat().st_size > 0, (
        "the export did not write the file")
    assert destinazione.name in tabella._esito.text(), (
        "the export does not say where it wrote")


def test_i_comandi_di_una_tabella_vuota_sono_spenti(application):
    """On a table without rows the three commands switch off and say why."""
    from gui_qt.widgets import DataTable
    tabella = DataTable()
    for bottone in (tabella._copy_button, tabella._export_button,
                    tabella._columns_button):
        assert not bottone.isEnabled(), (
            f"“{bottone.text()}” stays enabled on an empty table")
        assert bottone.toolTip().strip(), (
            f"“{bottone.text()}” is disabled and does not say why")
    tabella.set_dataframe(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}))
    application.processEvents()
    for bottone in (tabella._copy_button, tabella._export_button,
                    tabella._columns_button):
        assert bottone.isEnabled(), (
            f"“{bottone.text()}” stays disabled on a full table")
    # A filter that lets nothing through switches off the copy, not the saving:
    # the latter writes the whole table.
    tabella._search.setText("zzzzz-che-non-esiste-zzzzz")
    tabella._apply_filter()
    application.processEvents()
    assert not tabella._copy_button.isEnabled()
    assert tabella._export_button.isEnabled()
    tabella.deleteLater()
    application.processEvents()


# ── 5. the “How to read this page” panels ────────────────────────────────
def test_i_riquadri_come_si_legge_si_aprono_e_si_chiudono(finestra, application):
    """The button opens the text, and the text is there."""
    from gui_qt.widgets import HowToBox
    from gui_qt.main_window import STEPS
    aperti = 0
    for chiave, *_ in STEPS:
        finestra._go_to(chiave)
        application.processEvents()
        for riquadro in finestra._pages[chiave].findChildren(HowToBox):
            assert riquadro._box.isHidden(), (
                f"“{chiave}”: the box starts already open")
            riquadro._button.click()
            application.processEvents()
            assert not riquadro._box.isHidden(), (
                f"“{chiave}”: the button does not open the box")
            assert riquadro._body.text().strip(), (
                f"“{chiave}”: the box opens empty")
            riquadro._button.click()
            application.processEvents()
            assert riquadro._box.isHidden(), (
                f"“{chiave}”: the button does not close the box again")
            aperti += 1
    assert aperti > 0, "no “How to read this” box found"


# ── 6. the tabs ──────────────────────────────────────────────────────────
def test_le_linguette_cambiano_contenuto(finestra, application):
    """Each tab leads to a box of its own, and none is empty."""
    from gui_qt.main_window import STEPS
    provate = 0
    for chiave, *_ in STEPS:
        finestra._go_to(chiave)
        application.processEvents()
        for gruppo in finestra._pages[chiave].findChildren(QTabWidget):
            if gruppo.count() < 2:
                continue
            visti = set()
            for indice in range(gruppo.count()):
                gruppo.setCurrentIndex(indice)
                application.processEvents()
                assert gruppo.currentIndex() == indice, (
                    f"“{chiave}”: tab {indice} does not open")
                assert gruppo.tabText(indice).strip(), (
                    f"“{chiave}”: tab {indice} has no name")
                corrente = gruppo.currentWidget()
                assert corrente is not None
                visti.add(id(corrente))
                provate += 1
            assert len(visti) == gruppo.count(), (
                f"“{chiave}”: two tabs show the same box")
    assert provate > 0, "no group of tabs found"


# ── 7. no command enabled and mute ───────────────────────────────────────
def _ha_azione(bottone) -> bool:
    for segnale in ("clicked", "toggled", "stateChanged", "triggered"):
        emesso = getattr(bottone, segnale, None)
        if emesso is None:
            continue
        try:
            if bottone.receivers(emesso) > 0:
                return True
        except (TypeError, AttributeError):
            continue
    gruppo = bottone.group() if hasattr(bottone, "group") else None
    if gruppo is not None:
        for segnale in (gruppo.buttonClicked, gruppo.idClicked):
            try:
                if gruppo.receivers(segnale) > 0:
                    return True
            except (TypeError, AttributeError):
                continue
    return False


def test_nessun_comando_visibile_e_acceso_senza_azione(finestra, application):
    """If it is visible and can be pressed, it must be connected to something."""
    from gui_qt.main_window import STEPS
    application.processEvents()
    muti = []
    for chiave, *_ in STEPS:
        finestra._go_to(chiave)
        application.processEvents()
        for bottone in finestra._pages[chiave].findChildren(QAbstractButton):
            if not (bottone.isVisible() and bottone.isEnabled()):
                continue
            if bottone.property(PROPRIETA_ECCEZIONE):
                continue
            nome = (bottone.text() or bottone.objectName()
                    or bottone.__class__.__name__).replace("\n", " ").strip()
            if not _ha_azione(bottone):
                muti.append(f"{chiave}: {nome} ({bottone.__class__.__name__})")
    assert not muti, "enabled commands with no action attached:\n  " + "\n  ".join(muti)


def test_anche_la_barra_dei_passi_e_collegata(finestra, application):
    """The steps in the left column really lead to their page."""
    from gui_qt.main_window import STEPS
    for chiave, *_ in STEPS:
        bottone = finestra._step_buttons[chiave]
        if not bottone.isEnabled():
            continue
        bottone.click()
        application.processEvents()
        assert finestra._stack.currentWidget() is finestra._pages[chiave], (
            f"the step “{chiave}” does not open its page")
