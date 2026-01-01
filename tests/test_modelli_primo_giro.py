# -*- coding: utf-8 -*-
"""The first comparison on a new run, when nothing is saved yet.

These tests guard against a failure seen on Windows with Gorman loaded:
Stanza started and the program died on

    FileNotFoundError: ...\\runs\\<run>\\stanza_evaluation.json

The file was not there because it was the first comparison of that run, and
the program opened it to ask itself whether a result to reuse already existed.
The question “is anything saved?” cannot fail because the answer is no.

The other tests on the comparison with the models all save a
``stanza_evaluation.json`` before starting — they exist to verify the
provenance, and verifying it needs a file — so the case of the first run would
be covered by none of them, and it is the only one that the user always meets.
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

from tests.test_model_eval import CORPUS  # noqa: E402

PREVISIONI_VUOTE = ["document_id", "sentence_id", "token_id", "lemma", "postag"]


def _giro(radice: Path, *, crea_cartella: bool = True) -> tuple[Path, str]:
    """A run with its tokens saved, as the loading step leaves it."""
    from greek_corpus_pipeline.storage import run_dir, save_dataframe, save_metadata

    workspace = radice / "workspace"
    run_id = "20260907-114458-gorman"
    if crea_cartella:
        run_dir(workspace, run_id).mkdir(parents=True, exist_ok=True)
        save_dataframe(workspace, run_id, "tokens", CORPUS.copy())
        save_metadata(workspace, run_id, {"run_id": run_id, "stages": {}})
    return workspace, run_id


def _confronto(workspace: Path, run_id: str, *, esegui, prepara=None, registro=None):
    from gui_qt.workers import _confronto_con_modello

    return _confronto_con_modello(
        workspace, run_id, {}, etichetta="stanza",
        prepara=prepara or (lambda: "cartella-del-modello"),
        esegui=esegui,
        identita=lambda risorse: ("1.5.0", "abc123"),
        progress_cb=lambda fatto, totale, testo: None,
        log_cb=(registro.append if registro is not None else (lambda testo: None)))


def _previsioni_da(superficie: pd.DataFrame) -> pd.DataFrame:
    """Predictions aligned to the surface, that is the case in which the model works."""
    fuori = superficie.copy()
    fuori["lemma"] = "x"
    fuori["postag"] = "n-s---mn-"
    return fuori


# ── 1. the run folder is there, the evaluation file is not ───────────────────

def test_il_primo_confronto_di_un_giro_arriva_a_eseguire_il_modello(tmp_path):
    """The reported case: no ``stanza_evaluation.json``, and Stanza must start."""
    workspace, run_id = _giro(tmp_path)
    eseguito: list[int] = []

    def esegui(superficie, risorse, tick):
        eseguito.append(len(superficie))
        return _previsioni_da(superficie)

    _confronto(workspace, run_id, esegui=esegui)
    assert eseguito, "the model was not run"


def test_il_primo_confronto_scrive_la_valutazione_e_la_rilegge(tmp_path):
    """And afterwards the file is there, it opens, and it carries the provenance with it."""
    from greek_corpus_pipeline.storage import load_stats, stats_exist

    workspace, run_id = _giro(tmp_path)
    _confronto(workspace, run_id,
               esegui=lambda superficie, risorse, tick: _previsioni_da(superficie))

    assert stats_exist(workspace, run_id, "stanza_evaluation")
    salvato = load_stats(workspace, run_id, "stanza_evaluation")
    assert salvato["provenienza"]["modello"] == "stanza"
    assert salvato["provenienza"]["run_id"] == run_id


def test_la_valutazione_si_legge_solo_dopo_che_e_stata_scritta(tmp_path):
    """No race between whoever writes and whoever reads: it is the same call, in order.

    The second comparison finds the file of the first and reuses it without rerunning
    the model — which is also the proof that the first one wrote it in full.
    """
    workspace, run_id = _giro(tmp_path)
    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(1)
        return _previsioni_da(superficie)

    _confronto(workspace, run_id, esegui=esegui)
    _confronto(workspace, run_id, esegui=esegui)
    assert len(esecuzioni) == 1, "the second comparison ran the model again"


# ── 2. the run folder is not there ───────────────────────────────────────────

def test_senza_la_cartella_del_giro_l_errore_dice_dei_token_non_della_valutazione(tmp_path):
    """A run that does not exist must not look like a missing evaluation.

    Both cases would end in the same ``FileNotFoundError`` and whoever read the message
    could not know which of the two they were looking at.
    """
    workspace, run_id = _giro(tmp_path, crea_cartella=False)
    with pytest.raises(FileNotFoundError) as errore:
        _confronto(workspace, run_id,
                   esegui=lambda superficie, risorse, tick: _previsioni_da(superficie))
    assert "stanza_evaluation.json" not in str(errore.value)


def test_salvare_le_statistiche_crea_la_cartella_del_giro(tmp_path):
    """As ``save_metadata`` and ``save_dataframe`` already do."""
    from greek_corpus_pipeline.storage import load_stats, save_stats

    workspace = tmp_path / "workspace"
    save_stats(workspace, "giro-mai-visto", "stanza_evaluation", {"a": 1})
    assert load_stats(workspace, "giro-mai-visto", "stanza_evaluation") == {"a": 1}


# ── 3. the model fails before producing anything ─────────────────────────────

def test_un_modello_che_fallisce_mostra_la_sua_eccezione(tmp_path):
    """The real fault, not a ``FileNotFoundError`` that covers it."""
    workspace, run_id = _giro(tmp_path)

    def esegui(superficie, risorse, tick):
        raise RuntimeError("il modello grc non è stato scaricato")

    with pytest.raises(RuntimeError, match="grc"):
        _confronto(workspace, run_id, esegui=esegui)


def test_un_modello_che_fallisce_non_lascia_una_valutazione(tmp_path):
    """And it writes nothing: a comparison that did not take place has no results."""
    from greek_corpus_pipeline.storage import stats_exist

    workspace, run_id = _giro(tmp_path)

    def esegui(superficie, risorse, tick):
        raise RuntimeError("il modello grc non è stato scaricato")

    with pytest.raises(RuntimeError):
        _confronto(workspace, run_id, esegui=esegui)
    assert not stats_exist(workspace, run_id, "stanza_evaluation")


def test_un_modello_assente_mostra_l_errore_della_preparazione(tmp_path):
    """The failure can come even before the model: Stanza not installed."""
    workspace, run_id = _giro(tmp_path)

    def prepara():
        raise RuntimeError("Stanza non è installato")

    with pytest.raises(RuntimeError, match="Stanza"):
        _confronto(workspace, run_id, prepara=prepara,
                   esegui=lambda superficie, risorse, tick: _previsioni_da(superficie))


# ── 4. a saved evaluation is unreadable ─────────────────────────────────────

def test_una_valutazione_troncata_vale_come_assente_e_non_ferma_il_confronto(tmp_path):
    """A half-written JSON is not a result: it is redone, it does not crash."""
    from greek_corpus_pipeline.storage import stats_path

    workspace, run_id = _giro(tmp_path)
    rovinato = stats_path(workspace, run_id, "stanza_evaluation")
    rovinato.write_text('{"provenienza": {"modello": "sta', encoding="utf-8")

    eseguito: list[int] = []

    def esegui(superficie, risorse, tick):
        eseguito.append(1)
        return _previsioni_da(superficie)

    with pytest.warns(UserWarning, match="Unreadable statistics"):
        _confronto(workspace, run_id, esegui=esegui)
    assert eseguito, "an unreadable evaluation prevented the comparison"


def test_una_scrittura_interrotta_non_lascia_un_file_a_meta(tmp_path):
    """The evaluation is written in full or not written."""
    from unittest import mock

    from greek_corpus_pipeline.storage import save_stats, stats_path

    workspace, run_id = _giro(tmp_path)
    save_stats(workspace, run_id, "stanza_evaluation", {"buono": True})
    with mock.patch("json.dump", side_effect=OSError("disco pieno")):
        with pytest.raises(OSError):
            save_stats(workspace, run_id, "stanza_evaluation", {"nuovo": True})

    from greek_corpus_pipeline.storage import load_stats
    assert load_stats(workspace, run_id, "stanza_evaluation") == {"buono": True}
    cartella = stats_path(workspace, run_id, "stanza_evaluation").parent
    assert not list(cartella.glob("*.tmp")), "a temporary file was left behind"


# ── 5. Windows paths with spaces ─────────────────────────────────────────────

@pytest.mark.parametrize("cartella", [
    "Greek Corpus Pipeline",
    "Shared documents",
    "Cloud storage - Example University",
])
def test_il_confronto_funziona_in_una_cartella_con_gli_spazi(tmp_path, cartella):
    """The program may sit under a folder whose name contains spaces."""
    from greek_corpus_pipeline.storage import stats_exist

    radice = tmp_path / cartella
    radice.mkdir(parents=True, exist_ok=True)
    workspace, run_id = _giro(radice)

    eseguito: list[int] = []

    def esegui(superficie, risorse, tick):
        eseguito.append(1)
        return _previsioni_da(superficie)

    _confronto(workspace, run_id, esegui=esegui)
    assert eseguito
    assert stats_exist(workspace, run_id, "stanza_evaluation")


# ── 6. the centralised reading ───────────────────────────────────────────────

def test_nessuno_legge_le_statistiche_senza_dire_che_cosa_fare_se_mancano():
    """The defect is ``load_stats(...) or {}``: it must not appear anywhere.

    ``load_stats`` raises if the file is not there, and it is right that it does;
    whoever is instead asking *whether* something is there uses
    ``load_stats_if_present``.  This test keeps the distinction standing over
    time.
    """
    import re

    sorgenti = [ROOT / "gui_qt" / "workers.py",
                ROOT / "gui_qt" / "pages" / "base.py"]
    for sorgente in sorgenti:
        testo = sorgente.read_text(encoding="utf-8")
        for riga in testo.splitlines():
            codice = riga.split("#", 1)[0]
            if re.search(r"(?<!_)\bload_stats\s*\(", codice) and "load_stats_if_present" not in codice:
                raise AssertionError(
                    f"{sorgente.name}: usa load_stats senza dire che fare se manca:\n  {riga.strip()}")


# ── 7. the cache is valid only if the provenance matches in everything ───────

def _riesegue(workspace, run_id, **cambi) -> bool:
    """A second comparison on the same run: does it redo the work or reuse it?"""
    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(1)
        return _previsioni_da(superficie)

    _confronto(workspace, run_id, esegui=esegui, **cambi)
    return bool(esecuzioni)


def test_un_corpus_diverso_nella_stessa_cartella_fa_rifare_il_confronto(tmp_path):
    """The result is recovered by fingerprint, not by the name of the run."""
    from greek_corpus_pipeline.storage import save_dataframe

    workspace, run_id = _giro(tmp_path)
    assert _riesegue(workspace, run_id), "the first comparison did not run the model"
    assert not _riesegue(workspace, run_id), "the second did not reuse the result"

    # same folder, same name, another corpus
    save_dataframe(workspace, run_id, "tokens", CORPUS.iloc[:-2].copy())
    assert _riesegue(workspace, run_id), \
        "another corpus reused the comparison saved for the previous one"


def test_una_versione_diversa_del_modello_fa_rifare_il_confronto(tmp_path):
    from gui_qt.workers import _confronto_con_modello

    workspace, run_id = _giro(tmp_path)
    assert _riesegue(workspace, run_id)

    esecuzioni: list[int] = []
    _confronto_con_modello(
        workspace, run_id, {}, etichetta="stanza",
        prepara=lambda: "cartella-del-modello",
        esegui=lambda superficie, risorse, tick: (esecuzioni.append(1)
                                                  or _previsioni_da(superficie)),
        identita=lambda risorse: ("1.6.0", "abc123"),      # a different version
        progress_cb=lambda fatto, totale, testo: None,
        log_cb=lambda testo: None)
    assert esecuzioni, "a different version of the model reused the old comparison"


def test_i_campi_della_cache_sono_quelli_dichiarati():
    """Eight dimensions, and none fewer.

    Corpus fingerprint, program version, filters, units, model, its version, its
    resources and definition of the evaluation.  The ``run_id`` is not there on
    purpose: a comparison is valid for the text that it read, not for the folder
    in which it sits.
    """
    from greek_corpus_pipeline.model_eval import CACHE_FIELDS

    assert set(CACHE_FIELDS) == {
        "impronta_corpus", "gcp_version", "filtri", "unita",
        "modello", "modello_versione", "risorse_modello", "definizione_valutazione",
    }
    assert "run_id" not in CACHE_FIELDS
    assert "corpus" not in CACHE_FIELDS
