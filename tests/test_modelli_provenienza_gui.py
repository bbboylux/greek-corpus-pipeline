# -*- coding: utf-8 -*-
"""A saved comparison does not belong to whoever finds it, but to whoever produced it.

The folder of a run may contain a ``stanza_comparison`` table produced weeks earlier,
with other units, other filters or another version of the model. Loading it next to the
current numbers would make it read as if it were theirs.  These tests verify that this
does not happen.
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

from tests.test_model_eval import CORPUS  # noqa: E402


@pytest.fixture
def stato(tmp_path):
    from greek_corpus_pipeline.storage import run_dir
    from gui_qt.pages.base import AppState

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    stato = AppState(workspace=workspace)
    stato.run_id = "prova"
    stato.tokens = CORPUS.copy()
    run_dir(workspace, "prova").mkdir(parents=True, exist_ok=True)
    return stato


def _salva_confronto(stato, *, provenienza: dict) -> None:
    from greek_corpus_pipeline.storage import save_dataframe, save_stats
    save_dataframe(stato.workspace, stato.run_id, "stanza_comparison",
                   pd.DataFrame({"form": ["θεός"], "accordo_lemma": [True]}))
    save_stats(stato.workspace, stato.run_id, "stanza_evaluation",
               {"provenienza": provenienza, "modello": "stanza", "parole": 5,
                "lemma": {"eleggibili": 5, "accordi": 5, "quota": 100.0,
                          "copertura": 100.0, "denominatore": "parole"},
                "postag": {"eleggibili": 5, "accordi": 5, "quota": 100.0,
                           "denominatore": "parole", "sospesa": ""}})


def _provenienza_corrente(stato, **cambi):
    from greek_corpus_pipeline import __version__
    from greek_corpus_pipeline.model_eval import provenance
    base = dict(surface=stato.model_surface(), gcp_version=__version__,
                filtri=stato.filter_options, modello="stanza",
                modello_versione="1.5.0", risorse_modello="abc123",
                run_id=stato.run_id)
    base.update(cambi)
    return provenance(**base)


def test_senza_confronto_salvato_lo_stato_e_assente(stato):
    esito = stato.model_status("stanza", versione="1.5.0", risorse="abc123")
    assert esito["stato"] == "assente"
    assert stato.stanza_comparison.empty


def test_un_confronto_dello_stesso_corpus_e_valido_e_viene_caricato(stato):
    _salva_confronto(stato, provenienza=_provenienza_corrente(stato))
    esito = stato.model_status("stanza", versione="1.5.0", risorse="abc123")
    assert esito["stato"] == "valido"
    assert not stato.stanza_comparison.empty


def test_un_confronto_di_un_altro_modello_non_viene_caricato(stato):
    _salva_confronto(stato, provenienza=_provenienza_corrente(stato))
    esito = stato.model_status("stanza", versione="1.6.0", risorse="abc123")
    assert esito["stato"] == "inapplicabile"
    assert "modello_versione" in esito["motivo"]
    assert stato.stanza_comparison.empty


def test_un_confronto_di_un_altro_corpus_non_viene_caricato(stato):
    """The real case: an older table next to the run of today."""
    altro = CORPUS.iloc[:-2]
    stato_altro = type(stato)(workspace=stato.workspace)
    stato_altro.run_id = stato.run_id
    stato_altro.tokens = altro
    _salva_confronto(stato, provenienza=_provenienza_corrente(stato_altro))

    esito = stato.model_status("stanza", versione="1.5.0", risorse="abc123")
    assert esito["stato"] == "inapplicabile"
    assert "impronta_corpus" in esito["motivo"]
    assert stato.stanza_comparison.empty


def test_cambiare_i_filtri_rende_inapplicabile_il_confronto(stato):
    _salva_confronto(stato, provenienza=_provenienza_corrente(stato))
    stato.filter_options = dict(stato.filter_options, exclude_punctuation=True)
    stato.invalidate()
    esito = stato.model_status("stanza", versione="1.5.0", risorse="abc123")
    assert esito["stato"] == "inapplicabile"
    assert stato.stanza_comparison.empty


def test_il_confronto_inapplicabile_non_viene_cancellato(stato):
    from greek_corpus_pipeline.storage import artifact_exists
    _salva_confronto(stato, provenienza=_provenienza_corrente(stato))
    stato.model_status("stanza", versione="9.9.9", risorse="abc123")
    assert artifact_exists(stato.workspace, stato.run_id, "stanza_comparison")


def test_il_caricamento_di_un_giro_non_porta_dentro_le_tabelle_dei_modelli():
    """The two tables are not among those that load by themselves."""
    from gui_qt.workers import RunLoader
    assert "stanza_comparison" not in RunLoader.ARTIFACTS
    assert "udpipe_comparison" not in RunLoader.ARTIFACTS
    assert "stanza_evaluation" not in RunLoader.STATISTICHE
