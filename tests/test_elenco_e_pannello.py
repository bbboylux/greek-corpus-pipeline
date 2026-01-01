# -*- coding: utf-8 -*-
"""The list of findings and the right-hand panel, as they appear.

Two things together, because they are two halves of the same choice: the
table shows less and the panel shows everything.  If the table lost a column
without the panel recovering it, the finding would become unreadable; and if
the panel lost a section no test would notice, because the sections are
labels and not data.
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
    """The checks page with a real set of findings."""
    from greek_corpus_pipeline.postag import analyze_postags
    from gui_qt.pages.base import AppState
    from gui_qt.pages.errors_page import ErrorsPage

    stato = AppState(workspace=tmp_path)
    stato.run_id = "prova"
    stato.corpus_name = "prova"
    stato.tokens = tokens
    stato.findings = analyze_postags(tokens)
    assert not stato.findings.empty, "the test corpus produces no findings"
    vista = ErrorsPage(stato)
    vista.build()
    # The summary runs on a thread and the test has no event loop to wait for it:
    # it is computed here, with the same code, and applied.
    vista._apply_summary(
        vista._compute_summary(stato.findings, stato.tokens, "prova"))
    application.processEvents()
    yield vista
    vista.deleteLater()
    application.processEvents()


def _colonne_visibili(tabella) -> list[str]:
    frame = tabella.dataframe()
    vista = tabella._view
    return [str(nome) for indice, nome in enumerate(frame.columns)
            if not vista.isColumnHidden(indice)]


# ── 1. the table shows less ─────────────────────────────────────────────

def test_forma_e_lemma_non_sono_colonne_visibili(pagina):
    """The right-hand panel already shows them: in the table they took up width."""
    visibili = _colonne_visibili(pagina._table)
    assert "form" not in visibili
    assert "lemma" not in visibili


def test_la_tabella_resta_orientabile(pagina):
    """Without form and lemma two rows of the same rule must stay distinct."""
    visibili = _colonne_visibili(pagina._table)
    for atteso in ("controllo diagnostico", "classe diagnostica", "trattamento",
                   "document_id", "sentence_id"):
        assert atteso in visibili, f"column “{atteso}” is missing"


def test_forma_e_lemma_restano_nel_dato_e_nella_riga_scelta(pagina):
    """Hidden, not removed: the selected row must still carry them."""
    frame = pagina._table.dataframe()
    assert "form" in frame.columns and "lemma" in frame.columns
    pagina._table.select_first()
    riga = pagina._table.selected_row()
    assert riga is not None
    assert "form" in riga.index and "lemma" in riga.index


def test_forma_e_lemma_restano_nell_esportazione(pagina, tmp_path, monkeypatch):
    """An exported sheet is data, not a screen: the columns are there."""
    from gui_qt import widgets

    destinazione = tmp_path / "segnalazioni.csv"
    monkeypatch.setattr(widgets.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(destinazione), "")))
    scritto = pagina._table.export_csv()
    assert scritto
    intestazioni = pd.read_csv(destinazione, nrows=0).columns
    assert "forma" in intestazioni or "form" in intestazioni
    assert "lemma" in intestazioni


def test_la_ricerca_trova_per_forma(pagina):
    """Hiding a column must not remove it from the filter."""
    frame = pagina._table.dataframe()
    forma = str(frame["form"].dropna().iloc[0])
    pagina._table._search.setText(forma)
    pagina._table._apply_filter()
    assert not pagina._table.visible_dataframe().empty


# ── 2. the panel shows everything ───────────────────────────────────────

def test_il_pannello_ha_le_tre_sezioni(pagina, application):
    """“The whole sentence”, “What does not add up”, “The occurrences in the corpus”."""
    from gui_qt.i18n import tr

    pagina._table.select_first()
    application.processEvents()
    pannello = pagina._detail
    assert pannello._sentence_title.text() == tr("errors.context")
    assert pannello._what_title.text() == tr("errors.what")
    assert pannello._evidence_title.text() == tr("errors.evidence")
    for titolo in (pannello._sentence_title, pannello._what_title):
        assert titolo.isVisibleTo(pannello), "a section of the panel has disappeared"


def test_il_pannello_mostra_i_dati_grammaticali_del_token(pagina, application):
    """Form, PoS tag, lemma, relation and head: what the table does not say."""
    from gui_qt.i18n import tr

    pagina._table.select_first()
    application.processEvents()
    riga = pagina._table.selected_row()
    testo = pagina._detail._values.text()

    assert str(riga["form"]) in testo, "the form does not appear in the panel"
    for chiave in ("errors.field.postag", "errors.field.lemma",
                   "errors.field.relation", "errors.field.head"):
        assert tr(chiave) in testo, f"field “{tr(chiave)}” is missing"
    assert pagina._detail._sentence.text(), "the whole sentence is empty"
    assert pagina._detail._what.text(), "“what does not add up” is empty"


def test_il_pannello_segue_la_lingua(pagina, application):
    """The only change allowed in the panel is the change of language."""
    from gui_qt.i18n import T, tr

    lingua = T.language
    try:
        for scelta in ("it", "en"):
            T.set_language(scelta)
            pagina._detail.retranslate()
            assert pagina._detail._sentence_title.text() == tr("errors.context")
            assert pagina._detail._what_title.text() == tr("errors.what")
            assert pagina._detail._evidence_title.text() == tr("errors.evidence")
    finally:
        T.set_language(lingua)


# ── 3. the proposed correction is not on this page ──────────────────────

def test_il_pannello_non_mostra_la_correzione_proposta(pagina, application):
    """The proposal is read at “Correct”, where it is decided whether to apply it.

    This page says what is in the corpus and why it is flagged.  A value proposed
    here invites reading it as the right value, before anyone has decided
    anything.

    The proposal is put in the finding by hand, because the test corpus produces
    none: without it, the test would pass even with the page broken.
    """
    from gui_qt.i18n import tr

    segnalazioni = pagina.state.findings.copy()
    segnalazioni.loc[segnalazioni.index[0], "suggested_postag"] = "n-p---mn-"
    pagina.state.findings = segnalazioni
    pagina._apply_summary(
        pagina._compute_summary(segnalazioni, pagina.state.tokens, "prova"))
    application.processEvents()

    pagina._table.select_first()
    application.processEvents()
    riga = pagina._table.selected_row()
    assert riga is not None and str(riga.get("suggested_postag")) == "n-p---mn-", \
        "the proposal did not reach the selected row"

    pannello = pagina._detail
    testi = " ".join(filter(None, (
        pannello._values.text(), pannello._what.text(),
        pannello._sentence.text(), pannello._evidence.text())))
    assert "n-p---mn-" not in testi, "the proposed value appears in the panel"
    assert tr("errors.suggestion") not in testi
    assert not hasattr(pannello, "_suggestion"), \
        "the proposal box came back on the findings page"


def test_la_riga_della_forma_e_esplicita(pagina, application):
    """“Form ὀκτὼ”, with its label, like the other four."""
    from gui_qt.i18n import tr

    pagina._table.select_first()
    application.processEvents()
    testo = pagina._detail._values.text()
    assert tr("errors.field.form") in testo
    for chiave in ("errors.field.postag", "errors.field.lemma",
                   "errors.field.relation", "errors.field.head"):
        assert tr(chiave) in testo
