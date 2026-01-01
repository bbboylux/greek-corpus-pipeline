# -*- coding: utf-8 -*-
"""UDPipe in a process of its own: it starts, it ends, and it leaves nothing.

``ufal.udpipe`` does not release the GIL — a test that measures it is in
``test_ciclo_di_vita_modelli`` — so in a thread it freezes the interface for
the whole duration of every call, model loading included.  The model is
therefore loaded and works in another process.

A separate process can hang on Windows, and these tests look at exactly the
things that can hang: that the child starts, that it says something, that it
ends, that it is closed in every case, and that nothing is left around
afterwards — after success, after an error, after a cancellation and after the
closing of the window.

The tests that need the real model are skipped if it is not there: it is
indicated with ``GCP_UDPIPE_MODEL``.
"""
from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from tests.test_model_eval import CORPUS  # noqa: E402

psutil = pytest.importorskip("psutil")


def _modello() -> Path:
    percorso = Path(os.environ.get("GCP_UDPIPE_MODEL", ""))
    if not percorso.is_file():
        pytest.skip("no UDPipe model available (GCP_UDPIPE_MODEL)")
    return percorso


def _corpus(frasi: int = 40, lunghezza: int = 8) -> pd.DataFrame:
    """A fake but well-formed corpus: the sentence is ``sentence_index``."""
    quante = frasi * lunghezza
    ripetuto = pd.concat([CORPUS] * (quante // len(CORPUS) + 1), ignore_index=True)
    tokens = ripetuto.head(quante).copy().reset_index(drop=True)
    tokens["sentence_index"] = tokens.index // lunghezza + 1
    tokens["token_index"] = tokens.index % lunghezza + 1
    tokens["sentence_id"] = tokens["sentence_index"]
    return tokens


def _figli() -> int:
    return len(psutil.Process().children(recursive=True))


# ── 1-2. the process starts, and the model is loaded inside the child ───────

def test_il_processo_figlio_parte_e_carica_il_modello():
    from greek_corpus_pipeline.udpipe_processo import analizza_frasi

    fasi: list[str] = []
    lotti, avvisi = analizza_frasi(["ὁ θεός λέγει ."] * 4, _modello(), lotto=2,
                                   fase=fasi.append)
    assert fasi[:2] == ["carico", "pronto"], (
        "the child must say when it loads the model and when it is ready")
    assert len(lotti) == 2 and avvisi == []


def test_il_modello_non_viene_mai_caricato_nel_processo_dell_interfaccia():
    """Loading is a single call of one or two seconds: if it were here, it would freeze the
    window for all that time."""
    import inspect

    from greek_corpus_pipeline import analyzers

    sorgente = inspect.getsource(analyzers.run_udpipe_analysis)
    assert "Model.load" not in sorgente, (
        "run_udpipe_analysis carica il modello nel processo dell'interfaccia")


# ── 3-4. same input, same predictions ──────────────────────────────────────

def test_l_ingresso_del_modello_e_lo_stesso_delle_due_strade():
    """The row that UDPipe receives has a single definition."""
    import numpy as np

    from greek_corpus_pipeline.analyzers import _horizontal_batch, _righe_di_frase

    forme = ["ὁ", "θεός", "λέγει", ".", "καὶ", "οὕτως"]
    starts = np.array([0, 4, 6])
    assert "\n".join(_righe_di_frase(forme, starts)) + "\n" == \
        _horizontal_batch(forme, starts, 0, 2)


def test_le_previsioni_sono_identiche_nelle_due_strade():
    """The proof that counts: same input, same table, row by row."""
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    tokens = _corpus(frasi=30)
    dentro = run_udpipe_analysis(tokens, model_path=_modello(), in_processo=True)
    fuori = run_udpipe_analysis(tokens, model_path=_modello(), in_processo=False)

    assert len(dentro) == len(fuori)
    assert list(dentro.columns) == list(fuori.columns)
    colonne = ["form", "lemma", "postag", "_sentenza", "_posizione"]
    impronta = lambda d: hashlib.sha256(
        d[colonne].to_csv(index=False).encode("utf-8")).hexdigest()
    assert impronta(dentro) == impronta(fuori), \
        "the separate process produces different predictions"
    assert dentro.equals(fuori), "the tables differ in some column"


# ── 5. the progress is real ────────────────────────────────────────────────

def test_il_progresso_arriva_dal_figlio_un_avviso_per_lotto():
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    passi: list[tuple[int, int]] = []
    run_udpipe_analysis(_corpus(frasi=20), model_path=_modello(), batch_size=5,
                        progress=lambda fatte, totale: passi.append((fatte, totale)),
                        in_processo=False)
    assert len(passi) == 4, f"four batches, four notices: {passi}"
    assert [f for f, _ in passi] == [5, 10, 15, 20]
    assert all(t == 20 for _, t in passi)


# ── 6-7. the calling thread stays free, even during loading ────────────────

def _battito_mentre(lavoro, intervallo=0.05):
    """Runs *work* in a thread and measures the delays of whoever waits for it."""
    ritardi: list[float] = []
    fermo = threading.Event()
    esito: dict = {}

    def dentro():
        try:
            esito["valore"] = lavoro()
        except BaseException as errore:                # noqa: BLE001
            esito["errore"] = errore
        finally:
            fermo.set()

    th = threading.Thread(target=dentro, daemon=True)
    ultimo = time.perf_counter()
    th.start()
    while not fermo.is_set():
        time.sleep(intervallo)
        ora = time.perf_counter()
        ritardi.append(ora - ultimo)
        ultimo = ora
    th.join(timeout=30)
    if "errore" in esito:
        raise esito["errore"]
    return esito.get("valore"), ritardi


def test_il_chiamante_resta_libero_durante_il_caricamento_e_l_analisi():
    """With UDPipe inside the process this delay would be the entire duration."""
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    modello = _modello()
    tokens = _corpus(frasi=60)
    _, ritardi = _battito_mentre(
        lambda: run_udpipe_analysis(tokens, model_path=modello, in_processo=False))
    assert len(ritardi) > 10, "the job finished too early to measure anything"
    assert max(ritardi) < 0.5, (
        f"the waiting thread stalled for {max(ritardi):.2f} s: the GIL does not pass")


# ── 8-9-10. success, error, cancellation ───────────────────────────────────

def test_successo():
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    fuori = run_udpipe_analysis(_corpus(frasi=10), model_path=_modello(),
                                in_processo=False)
    assert not fuori.empty
    assert fuori["lemma"].astype(str).str.strip().ne("").any()


def test_un_modello_che_non_si_carica_da_un_errore_leggibile(tmp_path):
    pytest.importorskip("ufal.udpipe")
    from greek_corpus_pipeline.udpipe_processo import ErroreUdpipe, analizza_frasi

    finto = tmp_path / "non-e-un-modello.udpipe"
    finto.write_bytes(b"questo non e' un modello UDPipe")
    with pytest.raises(ErroreUdpipe) as errore:
        analizza_frasi(["ὁ θεός ."], finto, lotto=1)
    assert "could not load the model" in str(errore.value).lower()


def test_un_modello_che_non_esiste_e_un_errore_di_file(tmp_path):
    from greek_corpus_pipeline.udpipe_processo import analizza_frasi

    with pytest.raises(FileNotFoundError):
        analizza_frasi(["ὁ θεός ."], tmp_path / "non-c-e.udpipe", lotto=1)


def test_annullamento():
    """A stop is requested, and it stops: between one batch and the next."""
    from greek_corpus_pipeline.udpipe_processo import AnnullatoUdpipe, analizza_frasi

    modello = _modello()
    figli_prima = _figli()
    visti: list[int] = []

    def annullato() -> bool:
        return len(visti) >= 1

    # Enough work for stopping to mean something: 3,000 long sentences in batches of ten
    # are three hundred calls, and the request arrives after the first.
    frasi = ["ὁ θεός λέγει τοῖς ἀνθρώποις τοῖς ἐν τῇ πόλει ταύτῃ ."] * 3000
    inizio = time.perf_counter()
    with pytest.raises(AnnullatoUdpipe):
        analizza_frasi(frasi, modello, lotto=10, annullato=annullato,
                       progresso=lambda fatte, totale: visti.append(fatte))
    durata = time.perf_counter() - inizio
    assert visti, "the cancellation arrived before the child said anything"
    assert visti[-1] < len(frasi), "the job ran to the end anyway"
    assert durata < 60, f"stopping took {durata:.1f} s"
    _senza_figli(figli_prima)


# ── 11-12. nothing is left around ──────────────────────────────────────────

def _senza_figli(baseline: int, limite: float = 15.0) -> None:
    scadenza = time.monotonic() + limite
    while time.monotonic() < scadenza:
        if _figli() <= baseline:
            return
        time.sleep(0.05)
    vivi = psutil.Process().children(recursive=True)
    raise AssertionError(f"processi figli rimasti: {[p.name() for p in vivi]}")


def test_nessun_processo_figlio_dopo_il_successo():
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    prima = _figli()
    run_udpipe_analysis(_corpus(frasi=10), model_path=_modello(), in_processo=False)
    _senza_figli(prima)


def test_nessun_processo_figlio_dopo_l_errore(tmp_path):
    from greek_corpus_pipeline.udpipe_processo import ErroreUdpipe, analizza_frasi

    finto = tmp_path / "rotto.udpipe"
    finto.write_bytes(b"x" * 100)
    prima = _figli()
    with pytest.raises(ErroreUdpipe):
        analizza_frasi(["ὁ θεός ."], finto, lotto=1)
    _senza_figli(prima)


def test_chiudere_la_finestra_durante_un_run_non_lascia_figli(tmp_path):
    """The case that made the process abort, with the child in the middle."""
    pytest.importorskip("PyQt6.QtWidgets")
    from PyQt6.QtGui import QCloseEvent
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from gui_qt.main_window import MainWindow
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    modello = _modello()
    app = QApplication.instance() or QApplication([])
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    finestra = MainWindow(workspace)
    finestra.show()
    prima = _figli()

    tokens = _corpus(frasi=400)

    def lavoro(progress, log, annullato=None):
        run_udpipe_analysis(tokens, model_path=modello, in_processo=False,
                            annullato=annullato)

    finestra._start_work(lavoro, (), {}, "udpipe")
    scadenza = time.monotonic() + 20
    while _figli() <= prima and time.monotonic() < scadenza:
        app.processEvents()
        time.sleep(0.05)
    assert _figli() > prima, "the child process never started"

    originale = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        evento = QCloseEvent()
        inizio = time.monotonic()
        finestra.closeEvent(evento)
        durata = time.monotonic() - inizio
    finally:
        QMessageBox.question = originale

    assert durata < 30, "closing must not wait forever"
    if finestra._worker is not None:
        finestra._worker.wait(30_000)
    _senza_figli(prima, limite=30)


# ── 13-14-15. runs one after the other, in both orders ─────────────────────

def _finto_stanza(superficie, risorse, tick):
    fuori = superficie.copy()
    fuori["lemma"] = "x"
    fuori["postag"] = "n-s---mn-"
    tick(1, 1)
    return fuori


def _giro(workspace, run_id, etichetta, esegui, versione="1.0", registro=None):
    from gui_qt.workers import _confronto_con_modello

    _confronto_con_modello(
        workspace, run_id, {}, etichetta=etichetta,
        prepara=lambda: "risorsa", esegui=esegui,
        identita=lambda risorse: (versione, "abc"),
        progress_cb=lambda *a: None,
        log_cb=(registro.append if registro is not None else (lambda *a: None)))


def _giro_pronto(tmp_path):
    from greek_corpus_pipeline.storage import run_dir, save_dataframe, save_metadata

    workspace = tmp_path / "workspace"
    run_id = "giro"
    run_dir(workspace, run_id).mkdir(parents=True, exist_ok=True)
    save_dataframe(workspace, run_id, "tokens", CORPUS.copy())
    save_metadata(workspace, run_id, {"run_id": run_id, "stages": {}})
    return workspace, run_id


def test_due_giri_di_udpipe_di_fila(tmp_path):
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    modello = _modello()
    prima = _figli()
    tokens = _corpus(frasi=10)
    uno = run_udpipe_analysis(tokens, model_path=modello, in_processo=False)
    due = run_udpipe_analysis(tokens, model_path=modello, in_processo=False)
    assert uno.equals(due), "two passes over the same input give two results"
    _senza_figli(prima)


def test_udpipe_dopo_stanza_e_stanza_dopo_udpipe(tmp_path):
    from greek_corpus_pipeline.storage import artifact_exists

    workspace, run_id = _giro_pronto(tmp_path)
    _giro(workspace, run_id, "stanza", _finto_stanza)
    _giro(workspace, run_id, "udpipe", _finto_stanza)
    assert artifact_exists(workspace, run_id, "stanza_comparison")
    assert artifact_exists(workspace, run_id, "udpipe_comparison")

    workspace2, run_id2 = _giro_pronto(tmp_path / "secondo")
    _giro(workspace2, run_id2, "udpipe", _finto_stanza)
    _giro(workspace2, run_id2, "stanza", _finto_stanza)
    assert artifact_exists(workspace2, run_id2, "stanza_comparison")
    assert artifact_exists(workspace2, run_id2, "udpipe_comparison")


# ── 16-17. what is already saved ───────────────────────────────────────────

def test_una_valutazione_gia_salvata_non_fa_rieseguire_niente(tmp_path):
    workspace, run_id = _giro_pronto(tmp_path)
    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(1)
        return _finto_stanza(superficie, risorse, tick)

    _giro(workspace, run_id, "udpipe", esegui)
    _giro(workspace, run_id, "udpipe", esegui)
    assert len(esecuzioni) == 1, "the second pass redid work already done"


def test_cambiata_la_definizione_si_riconta_senza_il_modello(tmp_path):
    from greek_corpus_pipeline import model_eval
    from greek_corpus_pipeline.storage import load_stats_if_present

    workspace, run_id = _giro_pronto(tmp_path)
    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(1)
        return _finto_stanza(superficie, risorse, tick)

    _giro(workspace, run_id, "udpipe", esegui)
    prima = load_stats_if_present(workspace, run_id, "udpipe_evaluation")

    vecchia = model_eval.EVALUATION_DEFINITION
    try:
        model_eval.EVALUATION_DEFINITION = vecchia + "-prova"
        _giro(workspace, run_id, "udpipe", esegui)
    finally:
        model_eval.EVALUATION_DEFINITION = vecchia

    assert len(esecuzioni) == 1, "the model was run again just to redo a sum"
    dopo = load_stats_if_present(workspace, run_id, "udpipe_evaluation")
    assert dopo["lemma"]["accordi"] == prima["lemma"]["accordi"]
    assert dopo["postag"]["accordi"] == prima["postag"]["accordi"]
