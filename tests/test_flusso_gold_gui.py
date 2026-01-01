# -*- coding: utf-8 -*-
"""The gold flow really walked through, inside the application.

It is not a unit test: it opens the real window, with the same code that starts from
run.bat, and retraces the six steps that the user takes.  It runs without a screen
(``QT_QPA_PLATFORM=offscreen``) because what is to be verified is not how the buttons
are drawn, but that pressing them produces the corrected corpus.
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
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def finestra(application, tmp_path, corpus_dir):
    """The real window, on a clean workspace."""
    from gui_qt.main_window import MainWindow
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    window = MainWindow(workspace)
    yield window
    window.close()


def _passi(finestra) -> dict:
    return {chiave: pagina for chiave, pagina in finestra._pages.items()} \
        if hasattr(finestra, "_pages") else {}


def test_il_passo_del_gold_esiste_nella_barra(finestra):
    from gui_qt.main_window import STEPS
    chiavi = [passo[0] for passo in STEPS]
    assert "gold" in chiavi, "the gold step is not registered"
    assert chiavi.index("gold") > chiavi.index("review"), \
        "the gold must come after the correction"


def test_la_pagina_del_gold_si_costruisce(finestra):
    pagine = _passi(finestra)
    assert "gold" in pagine
    pagina = pagine["gold"]
    for attributo in ("_export_xml", "_export_csv", "_export_conllu",
                      "_save_bundle", "_load_bundle", "_compare"):
        assert hasattr(pagina, attributo), f"manca {attributo}"


def test_i_tre_pulsanti_di_esportazione_sono_distinti_dal_confronto(finestra):
    pagina = _passi(finestra)["gold"]
    etichette = {pagina._export_xml.text(), pagina._export_csv.text(),
                 pagina._export_conllu.text()}
    assert len(etichette) == 3, "two export buttons have the same name"
    assert pagina._compare.text() not in etichette, \
        "the comparison command is confused with the exports"
    from gui_qt.i18n import tr
    attese = {tr("gold.export.xml"), tr("gold.export.csv"),
              tr("gold.export.conllu")}
    assert etichette == attese, "the labels do not come from the string catalogue"
    for testo in etichette:
        assert testo.startswith("Export"), f"“{testo}” does not name an export"


def test_senza_corpus_tutto_e_bloccato(finestra):
    pagina = _passi(finestra)["gold"]
    pagina.refresh()
    assert not pagina._export_xml.isEnabled()
    assert not pagina._compare.isEnabled()


def _carica(finestra, tokens: pd.DataFrame, corrected: pd.DataFrame | None = None,
            manual: pd.DataFrame | None = None,
            stanza: pd.DataFrame | None = None) -> None:
    """Puts the window in the state it would be in after a real load."""
    from greek_corpus_pipeline.analysis import compute_token_diff
    from greek_corpus_pipeline.storage import run_dir

    stato = finestra.state
    stato.run_id = "run-di-prova"
    stato.corpus_name = "prova"
    stato.tokens = tokens
    directory = run_dir(stato.workspace, stato.run_id)
    directory.mkdir(parents=True, exist_ok=True)
    tokens.to_parquet(directory / "tokens.parquet", index=False)
    if corrected is not None:
        stato.corrected_tokens = corrected
        stato.token_diff = compute_token_diff(tokens, corrected)
        corrected.to_parquet(directory / "corrected_tokens.parquet", index=False)
    if manual is not None:
        manual.to_csv(directory / "correzioni_manuali.csv", index=False,
                      encoding="utf-8-sig")
    if stanza is not None:
        stato.stanza_comparison = stanza


def test_con_corpus_ma_senza_correzioni_lo_dice(finestra, tokens):
    pagina = _passi(finestra)["gold"]
    _carica(finestra, tokens)
    pagina.refresh()
    assert pagina._export_xml.isEnabled()
    assert not pagina._state_notice.isHidden()
    assert "have not been applied" in pagina._state_notice.text()


def test_esporta_davvero_la_versione_corretta(finestra, tokens, corrected,
                                              manual, tmp_path, monkeypatch):
    """The heart of the matter: the three buttons produce the gold, not the original."""
    from gui_qt.pages import gold_page as modulo
    pagina = _passi(finestra)["gold"]
    _carica(finestra, tokens, corrected, manual)
    pagina.refresh()

    uscita = tmp_path / "uscita"
    uscita.mkdir()
    monkeypatch.setattr(modulo.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(uscita)))
    pagina._do_export_xml()
    scritti = list(uscita.glob("*.xml"))
    assert scritti, "no XML written"
    testo = scritti[0].read_text(encoding="utf-8")
    assert 'lemma="στρατιώτης"' in testo
    assert 'lemma="στρατιώτης1"' not in testo, "the original was exported"

    csv_path = tmp_path / "gold.csv"
    monkeypatch.setattr(modulo.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(csv_path), "")))
    pagina._do_export_csv()
    frame = pd.read_csv(csv_path)
    assert frame.loc[frame["form"] == "ἄνδρες", "postag"].iloc[0] == "n-p---mn-"

    conllu_path = tmp_path / "gold.conllu"
    monkeypatch.setattr(modulo.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(conllu_path), "")))
    pagina._do_export_conllu()
    assert "στρατιώτης1" not in conllu_path.read_text(encoding="utf-8")


def test_senza_correzioni_chiede_conferma_prima_di_esportare(
        finestra, tokens, tmp_path, monkeypatch):
    from gui_qt.pages import gold_page as modulo
    from PyQt6.QtWidgets import QMessageBox
    pagina = _passi(finestra)["gold"]
    _carica(finestra, tokens, tokens.copy())   # corrected identical to the original
    pagina.refresh()

    domande: list[str] = []

    def finta_domanda(parent, titolo, testo, *args, **kwargs):
        domande.append(testo)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(modulo.QMessageBox, "question", staticmethod(finta_domanda))
    chiamato: list[str] = []
    monkeypatch.setattr(modulo.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: chiamato.append("aperto") or ""))
    pagina._do_export_xml()

    assert domande, "it did not ask for confirmation"
    assert "identical to the original corpus" in domande[0]
    assert not chiamato, "it opened the save dialogue despite the No"


def test_senza_correzioni_applicate_non_esporta_l_originale(
        finestra, tokens, monkeypatch):
    """If the corrections have not been applied, the gold does not exist: it stops."""
    from gui_qt.pages import gold_page as modulo
    pagina = _passi(finestra)["gold"]
    _carica(finestra, tokens)                  # no corrected_tokens
    pagina.refresh()

    messaggi: list[str] = []
    monkeypatch.setattr(modulo.QMessageBox, "information",
                        staticmethod(lambda p, t, m, *a, **k: messaggi.append(m)))
    aperto: list[str] = []
    monkeypatch.setattr(modulo.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: aperto.append("x") or ""))
    pagina._do_export_xml()

    from gui_qt.i18n import tr
    assert messaggi and messaggi[0] == tr("gold.msg.not_applied")
    assert not aperto


def test_salva_e_ricarica_dalla_finestra(finestra, tokens, corrected, manual,
                                         tmp_path, monkeypatch):
    from gui_qt.pages import gold_page as modulo
    from PyQt6.QtWidgets import QMessageBox
    pagina = _passi(finestra)["gold"]
    _carica(finestra, tokens, corrected, manual)
    pagina.refresh()

    bundle = tmp_path / "mio.gcpgold"
    monkeypatch.setattr(modulo.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(bundle), "")))
    pagina._do_save_bundle()
    assert bundle.exists(), "the gold was not saved"

    from greek_corpus_pipeline.storage import run_dir
    directory = run_dir(finestra.state.workspace, finestra.state.run_id)
    (directory / "corrected_tokens.parquet").unlink()

    monkeypatch.setattr(modulo.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(bundle), "")))
    monkeypatch.setattr(modulo.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pagina._do_load_bundle()

    ripreso = pd.read_parquet(directory / "corrected_tokens.parquet")
    riga = ripreso.loc[ripreso["form"] == "στρατιῶται"].iloc[0]
    assert riga["lemma"] == "στρατιώτης", "the reloaded gold lost the corrections"


def test_il_confronto_mette_a_fianco_i_due_riferimenti(finestra, tokens, corrected,
                                                       manual, stanza_like):
    from greek_corpus_pipeline.gold import model_reference_table
    _carica(finestra, tokens, corrected, manual, stanza_like)
    tabella = model_reference_table(tokens, corrected, stanza_like, None)
    assert not tabella.empty
    for colonna in ("accordo con l'originale %", "accordo con il gold %", "differenza"):
        assert colonna in tabella.columns
    assert (tabella["differenza"] > 0).all(), \
        "against the corrected corpus the model must agree more"


def test_la_sezione_del_gold_compare_solo_dopo_una_correzione(
        finestra, tokens, corrected, manual):
    pagina = _passi(finestra)["review"]
    finestra.state.findings = pd.DataFrame([{"rule_id": "x", "form": "y"}])

    # ``isVisible`` is false for any child of a window that is not shown: what matters
    # here is whether the page hid it on purpose.
    _carica(finestra, tokens)
    pagina.refresh()
    assert pagina._gold_ready.isHidden()

    _carica(finestra, tokens, corrected, manual)
    pagina.refresh()
    assert not pagina._gold_ready.isHidden(), \
        "after a correction the gold section must appear"
    assert "corrections" in pagina._gold_ready_body.text()


# ── The “Correct” card ──────────────────────────────────────────────────
#
# The design is clear-cut: no automatic corrections, no rules applied in bulk, and every
# proposal looked at one at a time with the current value next to the proposed one.
# These tests fix that boundary, and the boundary between the card that decides and the
# card that shows the result.

def _segnalazioni() -> pd.DataFrame:
    """Two findings with one proposal each: one of lemma, one of label."""
    return pd.DataFrame([
        {"rule_id": "lemma-tool-numbering", "document_id": "test-doc",
         "sentence_id": "1", "token_id": "5", "form": "στρατιῶται",
         "lemma": "στρατιώτης1", "postag": "n-p---mn-", "relation": "SBJ",
         "issue": "numero in coda al lemma",
         "suggested_lemma": "στρατιώτης", "suggested_postag": None},
        {"rule_id": "invalid-length-padding", "document_id": "test-doc",
         "sentence_id": "2", "token_id": "3", "form": "ἄνδρες",
         "lemma": "ἀνήρ", "postag": "n-p---mn", "relation": "SBJ",
         "issue": "etichetta di lunghezza sbagliata",
         "suggested_lemma": None, "suggested_postag": "n-p---mn-"},
    ])


def _con_segnalazioni(finestra, tokens):
    pagina = _passi(finestra)["review"]
    _carica(finestra, tokens)
    finestra.state.findings = _segnalazioni()
    pagina.refresh()
    return pagina


def test_nessuna_regola_si_applica_in_blocco(finestra):
    """A correction is decided case by case: no list of rules with ticks, no “apply all”."""
    pagina = _passi(finestra)["review"]
    for attributo in ("_rules", "_select_all", "_select_none", "_rule_count",
                      "enabled_rules"):
        assert not hasattr(pagina, attributo), \
            f"«{attributo}» is there: a whole rule would be applied in bulk"


def test_la_scheda_correggi_non_esporta_e_il_gold_non_decide(finestra):
    """The two cards must not be copies of one another."""
    correggi = _passi(finestra)["review"]
    gold = _passi(finestra)["gold"]
    for attributo in ("_export_xml", "_export_csv", "_export_conllu",
                      "_gold_button", "_diff_table", "_result_metrics"):
        assert not hasattr(correggi, attributo), \
            f"«{attributo}» duplicates a command that lives in step 10"
    for attributo in ("_accept", "_reject", "_dict_path", "_apply",
                      "_cases_table", "_decisions_table"):
        assert not hasattr(gold, attributo), \
            f"«{attributo}» duplicates a command that lives in step 5"


def test_la_riga_mostra_il_valore_di_adesso_e_quello_proposto(finestra, tokens):
    from gui_qt.pages.review_page import ARROW
    pagina = _con_segnalazioni(finestra, tokens)
    vista = pagina._cases_view
    assert len(vista) == 2, "the two proposals must appear, and only those"

    lemma = vista.loc[vista["forma"] == "στρατιῶται"].iloc[0]
    assert lemma["lemma_proposto"] == f"στρατιώτης1{ARROW}στρατιώτης"
    assert lemma["etichetta_proposta"] == "", \
        "a column with no proposal must stay empty"

    etichetta = vista.loc[vista["forma"] == "ἄνδρες"].iloc[0]
    assert etichetta["etichetta_proposta"] == f"n-p---mn{ARROW}n-p---mn-"


def test_accettare_scrive_una_sola_decisione(finestra, tokens):
    pagina = _con_segnalazioni(finestra, tokens)
    riga = pagina._cases_view.loc[pagina._cases_view["forma"] == "ἄνδρες"].iloc[0]
    pagina._select_case(riga)
    assert pagina._accept.isEnabled()
    assert "n-p---mn-" in pagina._proposal.text()

    pagina._accept_proposal()
    registro = pagina._load_manual()
    assert len(registro) == 1, "one decision at a time, not a whole rule"
    decisione = registro.iloc[0]
    assert decisione["corrected_postag"] == "n-p---mn-"
    assert decisione["previous_postag"] == "n-p---mn"
    assert decisione["status"] == "accettata"


def test_rifiutare_resta_scritto_e_non_corregge_niente(finestra, tokens):
    pagina = _con_segnalazioni(finestra, tokens)
    riga = pagina._cases_view.iloc[0]
    pagina._select_case(riga)
    pagina._reject_proposal()

    registro = pagina._load_manual()
    assert len(registro) == 1
    assert registro.iloc[0]["status"] == "respinta"
    assert registro.iloc[0]["corrected_lemma"] == ""
    assert pagina._accepted_decisions().empty, \
        "a rejected proposal must not end up in the corrected corpus"


def test_applicare_non_attiva_nessuna_regola_in_blocco(finestra, tokens, monkeypatch):
    """The engine always receives an empty set of rules."""
    pagina = _con_segnalazioni(finestra, tokens)
    pagina._select_case(pagina._cases_view.iloc[0])
    pagina._accept_proposal()

    chiamate = []
    monkeypatch.setattr(pagina, "run_work",
                        lambda *args, **kwargs: chiamate.append((args, kwargs)))
    pagina._apply_now()
    assert chiamate, "the button started nothing"
    argomenti = chiamate[0][0]
    assert argomenti[3] == set(), \
        "rules to apply automatically were passed"


# ── The dictionary of forms: which file it wants ───────────────────────

def test_il_dizionario_accetta_form_postag_lemma(tmp_path):
    from greek_corpus_pipeline.corrections import read_form_dictionary
    percorso = tmp_path / "mio.csv"
    percorso.write_text(
        "form,postag,lemma\n"
        "στρατιῶται,n-p---mn-,στρατιώτης\n"
        "ἄνδρες,,ἀνήρ\n"
        "καὶ,c--------,\n"
        ",x,y\n"
        "vuota,,\n", encoding="utf-8")
    voci, resoconto = read_form_dictionary(percorso)
    assert list(voci.columns) == ["form", "postag", "lemma"]
    assert resoconto.entries == 3
    assert resoconto.with_lemma == 2 and resoconto.with_postag == 2
    assert resoconto.skipped_rows == 2, "the row with no form and the empty one"


def test_il_dizionario_a_due_colonne_si_legge(tmp_path):
    from greek_corpus_pipeline.corrections import read_form_dictionary
    percorso = tmp_path / "due_colonne.csv"
    percorso.write_text("form,lemma\nστρατιῶται,στρατιώτης\n", encoding="utf-8-sig")
    voci, resoconto = read_form_dictionary(percorso)
    assert resoconto.entries == 1 and resoconto.with_postag == 0
    assert voci.iloc[0]["lemma"] == "στρατιώτης"


def test_un_dizionario_senza_niente_da_assegnare_e_rifiutato(tmp_path):
    from greek_corpus_pipeline.corrections import read_form_dictionary
    percorso = tmp_path / "solo_forme.csv"
    percorso.write_text("form\nστρατιῶται\n", encoding="utf-8")
    with pytest.raises(ValueError) as errore:
        read_form_dictionary(percorso)
    assert "postag" in str(errore.value) and "lemma" in str(errore.value)


def test_il_modello_scaricabile_si_rilegge_e_non_corregge_niente(tmp_path):
    """Whoever downloads the model and applies it without touching it changes nothing."""
    from greek_corpus_pipeline.corrections import (
        read_form_dictionary, write_form_dictionary_template,
    )
    scritto = write_form_dictionary_template(tmp_path / "modello.csv")
    testo = scritto.read_text(encoding="utf-8-sig")
    assert "form,postag,lemma" in testo
    voci, resoconto = read_form_dictionary(scritto)
    assert resoconto.entries == 0 and voci.empty


def test_il_dizionario_corregge_lemma_ed_etichetta_e_non_tocca_l_originale(tokens):
    from greek_corpus_pipeline.analysis import apply_form_corrections
    dizionario = pd.DataFrame([
        {"form": "στρατιῶται", "postag": "", "lemma": "στρατιώτης"},
        {"form": "ἄνδρες", "postag": "n-p---mn-", "lemma": ""},
        {"form": "νon-esiste", "postag": "", "lemma": "niente"},
    ])
    corretti = apply_form_corrections(tokens, dizionario)
    assert corretti.loc[corretti["form"] == "στρατιῶται", "lemma"].iloc[0] == "στρατιώτης"
    assert corretti.loc[corretti["form"] == "ἄνδρες", "postag"].iloc[0] == "n-p---mn-"
    # An empty cell deletes nothing, and the original stays as it was.
    assert corretti.loc[corretti["form"] == "ἄνδρες", "lemma"].iloc[0] == "ἀνήρ"
    assert tokens.loc[tokens["form"] == "στρατιῶται", "lemma"].iloc[0] == "στρατιώτης1"


def test_il_confronto_del_dizionario_e_esatto_sugli_accenti(tokens):
    from greek_corpus_pipeline.analysis import apply_form_corrections
    dizionario = pd.DataFrame([{"form": "ανδρες", "lemma": "sbagliato"}])
    corretti = apply_form_corrections(tokens, dizionario)
    assert corretti.loc[corretti["form"] == "ἄνδρες", "lemma"].iloc[0] == "ἀνήρ", \
        "an unaccented form must not match an accented one"
