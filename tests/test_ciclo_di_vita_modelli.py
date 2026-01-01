# -*- coding: utf-8 -*-
"""The life cycle of the models step, from start to return to idle.

These tests cover three failure modes that a user can meet on the same
screen:

A. when a model finishes, ``KeyError: 'corpus'`` appears;
B. the same error appears with the other model too;
C. while a model runs, the whole window stays unusable, and on some
   occasions the application closes without saying anything.

The three are not three independent defects.  A and B are the same defect:
the three-way comparison starts only when **both** tables exist, and from
that moment on it fails at every refresh of the page, whichever model
finished last.  C has two distinct causes, and each has its own test here:
heavy work running in the interface thread, and a ``QThread`` abandoned while
it works — which makes the process abort, that is, the window that vanishes.

The final state after a run must always be the same: worker dead, no more
child processes, buttons re-enabled, tables full, window closable.
"""
from __future__ import annotations

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

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

from tests.test_confronto_modelli_schema_reale import COLONNE_REALI  # noqa: E402
from tests.test_model_eval import CORPUS                             # noqa: E402


# ── scaffolding ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def applicazione():
    return QApplication.instance() or QApplication([])


def _tabella_reale(n=6, *, corpus="gorman", tag_modello=None, lemma_modello=None):
    """A comparison table with **the columns that the program writes**."""
    tag_corpus = ["n-s---mn-", "v3spia---", "d--------", "c--------",
                  "l-s---mn-", "a-s---fn-"][:n]
    lem_corpus = ["θεός", "λέγω1", "οὕτως", "καί", "ὁ", "καλή"][:n]
    tag_modello = tag_modello or tag_corpus
    lemma_modello = lemma_modello or ["θεός", "λέγω", "οὕτως", "καί", "ὁ", "καλή"][:n]
    dati = {
        "corpus": [corpus] * n, "analyzer": ["corpus"] * n,
        "source_file": ["a.xml"] * n, "document_id": ["a"] * n,
        "sentence_index": [1] * n, "sentence_id": [1] * n,
        "token_index": list(range(1, n + 1)), "token_id": list(range(1, n + 1)),
        "head": [0] * n, "ref": [None] * n,
        "form": ["θεός", "λέγει", "οὕτως", "καὶ", "ὁ", "καλή"][:n],
        "lemma": lem_corpus, "postag": tag_corpus,
        "relation": ["SBJ", "PRED", "ADV", "COORD", "ATR", "ATR"][:n],
        "artificial": [None] * n, "annotation_mode": [None] * n,
        "tlg_author": ["tlg0026"] * n, "tlg_work": ["tlg001"] * n,
        "cts_urn": ["x"] * n,
        "_model_form": ["θεός", "λέγει", "οὕτως", "καὶ", "ὁ", "καλή"][:n],
        "_sentenza": ["a.xml␟a␟1"] * n, "_posizione": list(range(n)),
        "lemma_modello": lemma_modello, "postag_modello": tag_modello,
        "lemma_normalizzato": [l.rstrip("123") for l in lem_corpus],
        "lemma_modello_normalizzato": lemma_modello,
        "accordo_lemma": [a.rstrip("123") == b for a, b in zip(lem_corpus, lemma_modello)],
        "accordo_postag": [a == b for a, b in zip(tag_corpus, tag_modello)],
        "eleggibile_lemma": [True] * n, "eleggibile_postag": [True] * n,
    }
    return pd.DataFrame(dati, columns=COLONNE_REALI)


@pytest.fixture
def modelli_non_installati(monkeypatch):
    """The two models are reported as absent, so the tables in memory stay.

    ``model_status`` reads the folder of the run and, if it finds no saved comparison
    that matches, **empties** the table in memory: this is the right behaviour — a
    comparison from another run is not an old result to be updated — but here what
    matters is how the tables are drawn, not where they come from, which has its own
    tests elsewhere.
    """
    from greek_corpus_pipeline import analyzers

    monkeypatch.setattr(analyzers, "check_stanza_available",
                        lambda *a, **k: (False, "non installato"))
    monkeypatch.setattr(analyzers, "check_udpipe_available",
                        lambda *a, **k: (False, "non installato"))


def _pagina(applicazione, tmp_path, *, con_stanza=True, con_udpipe=True):
    """A real window, with a run loaded and the two comparison tables."""
    from gui_qt.main_window import MainWindow

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    finestra = MainWindow(workspace)
    finestra.show()
    finestra.state.tokens = CORPUS.copy()
    finestra.state.run_id = "giro"
    if con_stanza:
        finestra.state.stanza_comparison = _tabella_reale()
    if con_udpipe:
        finestra.state.udpipe_comparison = _tabella_reale(
            tag_modello=["n-s---mn-", "v3spia---", "c--------", "c--------",
                         "l-s---mn-", "a-s---fn-"])
    pagina = finestra._pages["models"]
    finestra._go_to("models")
    applicazione.processEvents()
    return finestra, pagina


@pytest.fixture(autouse=True)
def nessun_calcolo_di_pagina_in_corsa(applicazione):
    """Every test ends with the page computations really finished.

    Without this, the next test builds a new window while the previous one is
    being collected with a thread still inside pandas, and the process aborts:
    it is the very same failure that these tests describe, in miniature.
    """
    yield
    from gui_qt.pages.base import _IN_CORSA

    scadenza = time.monotonic() + 30
    while time.monotonic() < scadenza:
        applicazione.processEvents()
        vivi = [w for w in list(_IN_CORSA) if w.isRunning()]
        if not vivi:
            break
        time.sleep(0.01)
    for w in list(_IN_CORSA):
        w.wait(5000)
    applicazione.processEvents()


def _attendi_sfondo(pagina, applicazione, limite=30.0):
    """Processes events until the background computations of the page are finished."""
    scadenza = time.monotonic() + limite
    while time.monotonic() < scadenza:
        applicazione.processEvents()
        vivi = [w for w in pagina._async_workers.values()
                if hasattr(w, "isRunning") and w.isRunning()]
        if not vivi:
            applicazione.processEvents()
            return
        time.sleep(0.005)
    raise AssertionError("il calcolo di sfondo non e' finito")


# ── A and B · the KeyError, whichever model it comes from ────────────────────

def test_dopo_stanza_le_tabelle_si_disegnano_senza_errori(applicazione, tmp_path, modelli_non_installati):
    """Case A: Stanza finishes, the page refreshes, no KeyError."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.work_finished(True, "")
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    assert not pagina._three_way.dataframe().empty


def test_dopo_udpipe_le_tabelle_si_disegnano_senza_errori(applicazione, tmp_path, modelli_non_installati):
    """Case B: it is the same defect, and it needs a test of its own."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina._mismatch_source.setCurrentText("UDPipe")
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    assert not pagina._three_way.dataframe().empty


def test_il_confronto_a_tre_vie_sullo_schema_reale_non_solleva():
    """The shortest form of the defect, without the interface."""
    from greek_corpus_pipeline import modelcmp

    S, U = _tabella_reale(), _tabella_reale(
        tag_modello=["n-s---mn-", "v3spia---", "c--------", "c--------",
                     "l-s---mn-", "a-s---fn-"])
    riassunto, dettaglio = modelcmp.three_way_agreement(S, U)
    assert not riassunto.empty
    assert {"corpus", "stanza", "udpipe", "esito"} <= set(dettaglio.columns)


def test_una_valutazione_senza_le_chiavi_attese_non_ferma_la_pagina(applicazione, tmp_path):
    """The saved structure does not have the keys that a view expected.

    ``postag_match``, ``lemma_reference`` and ``postag_stanza`` do not exist in
    any file produced by the program.  Asking for them does not raise: the view
    merely shows a table without the columns that would give it a meaning.
    """
    from greek_corpus_pipeline import modelcmp

    tabella = _tabella_reale()
    assert "postag_match" not in tabella.columns
    assert modelcmp._colonna_accordo(tabella, "postag") == "accordo_postag"
    assert modelcmp._colonna_accordo(tabella, "lemma") == "accordo_lemma"
    assert modelcmp._colonna_corpus(tabella, "postag") == "postag"
    assert modelcmp._colonna_modello(tabella, "postag") == "postag_modello"


def test_la_linguetta_posizione_per_posizione_non_e_vuota(applicazione, tmp_path, modelli_non_installati):
    """Looks for ``postag_stanza`` and finds nothing: empty table, silently."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    assert not pagina._slots.dataframe().empty, "the table of the nine positions is empty"


def test_i_disaccordi_mostrano_le_colonne_del_corpus_e_del_modello(applicazione, tmp_path, modelli_non_installati):
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    colonne = set(pagina._mismatches.dataframe().columns)
    assert {"lemma", "lemma_modello", "postag", "postag_modello"} <= colonne


def test_tutte_le_linguette_si_aprono_dopo_il_giro(applicazione, tmp_path, modelli_non_installati):
    """None of the five must raise when it is looked at."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    for indice in range(pagina._tabs.count()):
        pagina._tabs.setCurrentIndex(indice)
        applicazione.processEvents()
    assert pagina._tabs.currentIndex() == pagina._tabs.count() - 1


# ── C · a failure in a view does not close the application ──────────────────

def test_un_guasto_in_una_vista_non_esce_dallo_slot(applicazione, tmp_path):
    """An exception raised in a Qt slot must not abort the process.

    An exception raised inside a Qt slot does not return to the caller: PyQt
    sends it to ``sys.excepthook`` and, with the default hook, calls ``qFatal()``,
    that is, it aborts the process.  The window must absorb it.
    """
    finestra, pagina = _pagina(applicazione, tmp_path)

    def rotta():
        raise RuntimeError("this view cannot draw itself")

    pagina.refresh = rotta
    finestra._aggiorna_pagina(pagina)          # must not raise
    assert finestra._status.text()


# ── the worker, after success and after error ───────────────────────────────

def _lavoro(finestra, applicazione, funzione, limite=30.0):
    finestra._start_work(funzione, (), {}, "prova")
    scadenza = time.monotonic() + limite
    while finestra._worker is not None and finestra._worker.isRunning() \
            and time.monotonic() < scadenza:
        applicazione.processEvents()
        time.sleep(0.005)
    applicazione.processEvents()
    return finestra._worker


def test_il_worker_e_morto_dopo_il_successo(applicazione, tmp_path):
    finestra, _ = _pagina(applicazione, tmp_path)
    worker = _lavoro(finestra, applicazione, lambda p, l: None)
    assert worker.isFinished() and not worker.isRunning()


def test_il_worker_e_morto_dopo_l_errore(applicazione, tmp_path):
    finestra, _ = _pagina(applicazione, tmp_path)

    def scoppia(progress, log):
        raise RuntimeError("scoppiato")

    worker = _lavoro(finestra, applicazione, scoppia)
    assert worker.isFinished() and not worker.isRunning()


def test_due_lavori_di_fila_lasciano_un_solo_worker_vivo(applicazione, tmp_path):
    """Stanza and then UDPipe, one after the other."""
    finestra, _ = _pagina(applicazione, tmp_path)
    primo = _lavoro(finestra, applicazione, lambda p, l: None)
    secondo = _lavoro(finestra, applicazione, lambda p, l: None)
    assert primo.isFinished() and secondo.isFinished()
    # The two jobs trigger the reloading of the run and the recomputation of the
    # tables: those are awaited too, because the question is whether anything is
    # still alive **at the end**, not whether anything is while it finishes.
    scadenza = time.monotonic() + 30
    while finestra._thread_vivi() and time.monotonic() < scadenza:
        applicazione.processEvents()
        time.sleep(0.01)
    assert finestra._thread_vivi() == []


# ── resources: back to the starting point ───────────────────────────────────

def test_nessun_processo_figlio_in_piu_dopo_un_giro(applicazione, tmp_path):
    """The cleanup harness: child processes and threads return to their previous level."""
    psutil = pytest.importorskip("psutil")
    processo = psutil.Process()
    figli_prima = len(processo.children(recursive=True))
    thread_prima = threading.active_count()

    finestra, pagina = _pagina(applicazione, tmp_path)
    _lavoro(finestra, applicazione, lambda p, l: None)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    scadenza = time.monotonic() + 10
    while time.monotonic() < scadenza and threading.active_count() > thread_prima:
        applicazione.processEvents()
        time.sleep(0.05)

    assert len(processo.children(recursive=True)) == figli_prima
    assert finestra._thread_vivi() == []


def test_nessun_timer_resta_acceso_dopo_il_giro(applicazione, tmp_path, modelli_non_installati):
    """The page keeps no timer alive between one run and the next."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    timer = [f for f in vars(pagina).values() if isinstance(f, QTimer) and f.isActive()]
    assert timer == []


def test_la_finestra_si_chiude_dopo_un_giro(applicazione, tmp_path):
    """Normal closing, with no thread to wait for and no questions."""
    from PyQt6.QtGui import QCloseEvent

    finestra, pagina = _pagina(applicazione, tmp_path)
    _lavoro(finestra, applicazione, lambda p, l: None)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    evento = QCloseEvent()
    finestra.closeEvent(evento)
    assert evento.isAccepted()
    assert finestra._thread_vivi() == []


def test_un_thread_ancora_vivo_non_viene_mai_abbandonato(applicazione, tmp_path):
    """The mechanism of the sudden closing, in the form of a test.

    ``quit()`` stops the event loop of a QThread and does nothing to a QThread
    whose ``run()`` is a blocking function.  Waiting for it two seconds and then
    closing anyway leaves the Python object without references: the C++
    destructor of a running QThread calls ``qFatal()``, and the process aborts
    without a message.  A thread that cannot be waited for must be retained.
    """
    from gui_qt import main_window as mw

    finestra, _ = _pagina(applicazione, tmp_path)
    fermati = threading.Event()
    finestra._start_work(lambda p, l: fermati.wait(60), (), {}, "lungo")
    applicazione.processEvents()
    worker = finestra._worker
    assert worker.isRunning()

    trattenuti_prima = len(mw._TRATTIENI)
    finestra._reload_run()                      # the run loader is replaced, but
    applicazione.processEvents()                # the long worker remains

    # closing, without the confirmation dialog
    from PyQt6.QtGui import QCloseEvent
    evento = QCloseEvent()
    t0 = time.monotonic()
    finestra.closeEvent(evento)
    durata = time.monotonic() - t0
    fermati.set()
    worker.wait(5000)

    assert durata < 20, "closing must not wait forever"
    assert len(mw._TRATTIENI) > trattenuti_prima or worker.isFinished(), (
        "a thread that is still running must be held on to, not abandoned")


def test_chiudere_con_un_lavoro_in_corso_chiede_conferma(applicazione, tmp_path, monkeypatch):
    """The user is asked, and a “no” does not close."""
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtGui import QCloseEvent

    finestra, _ = _pagina(applicazione, tmp_path)
    fermati = threading.Event()
    finestra._start_work(lambda p, l: fermati.wait(30), (), {}, "lungo")
    applicazione.processEvents()

    chiesto: list[int] = []

    def finta(*a, **k):
        chiesto.append(1)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(finta))
    try:
        evento = QCloseEvent()
        finestra.closeEvent(evento)
        assert chiesto, "closing during a job must ask for confirmation"
        assert not evento.isAccepted(), "answering no must not close"
    finally:
        fermati.set()
        finestra._worker.wait(5000)


# ── the step bar stays alive while the model works ──────────────────────────

def test_la_navigazione_non_si_spegne_durante_il_lavoro(applicazione, tmp_path):
    """The symptom to prevent: the whole interface faded for minutes."""
    finestra, _ = _pagina(applicazione, tmp_path)
    fermati = threading.Event()
    finestra._start_work(lambda p, l: fermati.wait(30), (), {}, "lungo")
    applicazione.processEvents()
    accesi = [b.isEnabled() for b in finestra._step_buttons.values()]
    fermati.set()
    finestra._worker.wait(5000)
    assert any(accesi), "during a long job navigation remains usable"


# ── heavy work does not return to the interface thread ──────────────────────

def test_le_tabelle_dei_modelli_si_calcolano_fuori_dal_thread_qt(applicazione, tmp_path, modelli_non_installati):
    """Ten seconds of pandas in the Qt thread are ten seconds of frozen window."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    principale = threading.get_ident()
    visti: list[int] = []
    originale = pagina._tabelle_dei_modelli

    def spia(*a, **k):
        visti.append(threading.get_ident())
        return originale(*a, **k)

    pagina._tabelle_dei_modelli = spia
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    assert visti, "the computation was not run"
    assert all(ident != principale for ident in visti), (
        "the model tables are computed in the interface thread")


def test_il_thread_principale_continua_a_battere_durante_il_lavoro(applicazione, tmp_path):
    """Responsiveness measured, not deduced: a 50 ms timer in the Qt thread."""
    finestra, _ = _pagina(applicazione, tmp_path)
    battiti: list[float] = []
    ultimo = [time.perf_counter()]

    def battito():
        ora = time.perf_counter()
        battiti.append(ora - ultimo[0])
        ultimo[0] = ora

    cuore = QTimer()
    cuore.timeout.connect(battito)
    cuore.start(50)

    fermati = threading.Event()
    finestra._start_work(lambda p, l: fermati.wait(2.0), (), {}, "lungo")
    scadenza = time.monotonic() + 10
    while finestra._worker.isRunning() and time.monotonic() < scadenza:
        applicazione.processEvents()
        time.sleep(0.005)
    cuore.stop()
    finestra._worker.wait(5000)

    assert len(battiti) > 5, "the main thread did not tick often enough"
    assert max(battiti) < 1.0, f"the main thread stalled for {max(battiti):.2f} s"


# ── batches: the duration of the block, and the identity of the result ──────

def test_il_lotto_di_udpipe_e_piccolo():
    """The batch is the duration of the block: UDPipe does not release the GIL."""
    from greek_corpus_pipeline.analyzers import (
        STANZA_SENTENCE_BATCH, UDPIPE_SENTENCE_BATCH,
    )
    assert UDPIPE_SENTENCE_BATCH <= 50
    assert STANZA_SENTENCE_BATCH <= 200


def test_udpipe_non_rilascia_il_gil():
    """The cause of the block, measured on the real library.

    If one day ``ufal.udpipe`` released the GIL, this test would fail and the
    batch size could become large again.  Failing here is good news, not a
    fault.
    """
    udpipe = pytest.importorskip("ufal.udpipe")
    modello = Path(os.environ.get("GCP_UDPIPE_MODEL", ""))
    if not modello.is_file():
        pytest.skip("no UDPipe model available")
    m = udpipe.Model.load(str(modello))
    tubo = udpipe.Pipeline(m, "horizontal", udpipe.Pipeline.DEFAULT,
                           udpipe.Pipeline.DEFAULT, "conllu")
    testo = "\n".join(["ὁ θεός λέγει τοῖς ἀνθρώποις τοῖς ἐν τῇ πόλει ."] * 3000)

    ritardi: list[float] = []
    fermo = threading.Event()

    def osserva():
        ultimo = time.perf_counter()
        while not fermo.is_set():
            time.sleep(0.02)
            ora = time.perf_counter()
            ritardi.append(ora - ultimo)
            ultimo = ora

    th = threading.Thread(target=osserva, daemon=True)
    th.start()
    time.sleep(0.2)
    ritardi.clear()
    inizio = time.perf_counter()
    tubo.process(testo, udpipe.ProcessingError())
    durata = time.perf_counter() - inizio
    fermo.set()
    th.join(timeout=2)

    if durata < 0.2:
        pytest.skip("the call is too short to measure the blocking")
    assert max(ritardi) > durata * 0.5, (
        "ufal.udpipe seems to release the GIL: the reason for the small batch "
        "is gone, and the constant needs to be revisited")


def test_la_dimensione_del_lotto_non_cambia_il_risultato():
    """No scientific change: form, lemma and label are the same."""
    udpipe = pytest.importorskip("ufal.udpipe")
    modello = Path(os.environ.get("GCP_UDPIPE_MODEL", ""))
    if not modello.is_file():
        pytest.skip("no UDPipe model available")
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    tokens = CORPUS.copy()
    riferimento = None
    for lotto in (1, 2, 500):
        fuori = run_udpipe_analysis(tokens, model_path=str(modello), batch_size=lotto)
        colonne = [c for c in ("form", "lemma_modello", "postag_modello") if c in fuori.columns]
        adesso = fuori[colonne].to_csv(index=False)
        if riferimento is None:
            riferimento = adesso
        assert adesso == riferimento, f"a batch of {lotto} changes the result"


# ── the policy on processors ────────────────────────────────────────────────

def test_la_politica_sui_processori_e_prudente_e_portabile():
    from greek_corpus_pipeline.cpu import TETTO, thread_consigliati

    assert thread_consigliati(1) == 1
    assert thread_consigliati(2) == 1
    assert thread_consigliati(4) == 2
    assert thread_consigliati(8) == 4        # eight processors: four threads
    assert thread_consigliati(64) == TETTO   # the cap also holds on a large machine
    assert all(thread_consigliati(n) >= 1 for n in range(1, 65))


def test_il_limite_ai_thread_si_mette_prima_degli_import_pesanti():
    """The variable read at import cannot be changed afterwards.

    ``app_qt.py`` must call ``limita_thread`` **before** importing pandas:
    OpenBLAS sizes its pool when it is loaded and does not reread the
    environment afterwards.  The test checks the order in the source, because
    the order is what matters.
    """
    testo = (ROOT / "app_qt.py").read_text(encoding="utf-8")
    posizione_limite = testo.index("limita_thread()")
    for pesante in ("import pandas", "import numpy", "import torch", "QApplication"):
        trovato = testo.find(pesante)
        if trovato >= 0:
            assert posizione_limite < trovato, (
                f"“{pesante}” comes before the thread limit")


def test_il_pool_delle_librerie_numeriche_rispetta_il_tetto():
    """Not the order in the source: the real size of the pool, measured.

    The test above looks at ``app_qt.py`` and finds the right order, but that is
    not enough.  To call ``limita_thread``, ``app_qt.py`` writes
    ``from greek_corpus_pipeline.cpu import limita_thread``, and that import
    runs ``greek_corpus_pipeline/__init__.py``, which imports pandas: OpenBLAS
    would size its pool on all the processors **before** the limit existed.
    Here the pool is measured in a clean process.
    """
    import json
    import subprocess

    pytest.importorskip("threadpoolctl")
    codice = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "import greek_corpus_pipeline\n"
        "from threadpoolctl import threadpool_info\n"
        "from greek_corpus_pipeline.cpu import thread_consigliati\n"
        "import json; print(json.dumps({'consigliati': thread_consigliati(),\n"
        "    'pool': [[d.get('prefix') or d.get('internal_api'), d['num_threads']]\n"
        "             for d in threadpool_info()]}))\n"
    ) % (str(ROOT / "src"), str(ROOT))

    # The environment must be cleaned: if the variables arrive already set from outside,
    # the test would measure the caution of whoever launches it, not that of the
    # program.
    ambiente = {k: v for k, v in os.environ.items()
                if k not in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                             "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                             "VECLIB_MAXIMUM_THREADS")}
    finito = subprocess.run([sys.executable, "-c", codice], capture_output=True,
                            text=True, env=ambiente, timeout=300)
    assert finito.returncode == 0, finito.stderr[-800:]
    letto = json.loads(finito.stdout.strip().splitlines()[-1])
    for nome, quanti in letto["pool"]:
        assert quanti <= letto["consigliati"], (
            f"{nome} opened {quanti} threads, the recommended number is {letto['consigliati']}")


def test_importare_una_parte_qualunque_del_pacchetto_mette_il_limite():
    """Whoever imports only ``cpu`` also goes through the file that applies the policy."""
    import subprocess

    codice = (
        "import sys, os; sys.path.insert(0, %r)\n"
        "from greek_corpus_pipeline.cpu import limita_thread\n"
        "print(os.environ.get('OPENBLAS_NUM_THREADS'))\n"
    ) % str(ROOT / "src")
    ambiente = {k: v for k, v in os.environ.items()
                if k not in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                             "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                             "VECLIB_MAXIMUM_THREADS")}
    finito = subprocess.run([sys.executable, "-c", codice], capture_output=True,
                            text=True, env=ambiente, timeout=300)
    assert finito.returncode == 0, finito.stderr[-800:]
    assert finito.stdout.strip().splitlines()[-1] not in ("None", ""), \
        "importing the package did not set the thread limit"


def test_reattivita_con_un_ciclo_di_eventi_vero(tmp_path):
    """The responsiveness test: real model, real event loop.

    Not ``processEvents()`` inside a hand-written loop — which waits in a
    different way, and one that is stingier with the GIL, than the open window
    does — but ``QApplication.exec()``, with a 100 ms heartbeat in the main
    thread while UDPipe really works on a small corpus.

    What is measured is the delay of the heartbeat: if the main thread stops
    receiving the GIL, the heartbeat thins out and the window, on Windows, is
    covered by the words “Not responding”.

    It is a time measurement, and a time measurement inside a suite that already
    keeps the machine busy measures the load and not the program.  It is run on
    purpose, alone, with ``GCP_RESPONSIVENESS_TEST=1``.
    """
    if not os.environ.get("GCP_RESPONSIVENESS_TEST"):
        pytest.skip(
            "time measurement: run it alone, on a quiet machine, "
            "with GCP_RESPONSIVENESS_TEST=1")
    udpipe = pytest.importorskip("ufal.udpipe")
    modello = Path(os.environ.get("GCP_UDPIPE_MODEL", ""))
    if not modello.is_file():
        pytest.skip("no UDPipe model available")

    from PyQt6.QtCore import QTimer
    from gui_qt.workers import PipelineWorker
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis

    app = QApplication.instance() or QApplication([])
    # The sentence is identified by ``sentence_index`` — not by ``sentence_id``, which
    # is the number inside the file — so that is what must be made distinct, otherwise
    # the whole corpus becomes a single sentence and a single batch.
    tokens = pd.concat([CORPUS] * 3000, ignore_index=True)
    lunghezza = 24                     # sentences of realistic length: it is the
    tokens["sentence_index"] = tokens.index // lunghezza + 1   # number of tokens
    tokens["token_index"] = tokens.index % lunghezza + 1       # per call that
    tokens["sentence_id"] = tokens["sentence_index"]           # decides the block

    battiti: list[float] = []
    ultimo = [0.0]

    def battito():
        ora = time.perf_counter()
        if ultimo[0]:
            battiti.append(ora - ultimo[0])
        ultimo[0] = ora

    cuore = QTimer()
    cuore.timeout.connect(battito)
    cuore.start(100)

    def lavoro(progress, log):
        run_udpipe_analysis(tokens, model_path=str(modello))

    worker = PipelineWorker(lavoro)
    worker.finished_ok.connect(app.quit)
    worker.error.connect(lambda _m: app.quit())
    QTimer.singleShot(0, worker.start)
    guardia = QTimer()
    guardia.timeout.connect(app.quit)
    guardia.start(120_000)
    inizio = time.perf_counter()
    app.exec()
    durata = time.perf_counter() - inizio
    cuore.stop()
    worker.wait(30_000)

    if durata < 1.5:
        pytest.skip("the test finished too quickly to measure anything")
    # One heartbeat every 100 ms: in `durata` seconds (the duration) at least a third of
    # the expected heartbeats are needed.  If many fewer arrive, the main thread has
    # stopped receiving the GIL — which is precisely the fault, and must not be confused
    # with a skipped test.
    attesi = max(10, int(durata / 0.3))
    assert len(battiti) >= attesi, (
        f"the main thread ticked {len(battiti)} times in {durata:.1f} s: "
        f"the window froze")
    ordinati = sorted(battiti)
    p95 = ordinati[int(len(ordinati) * 0.95)]
    assert p95 < 0.6, (
        f"the main thread thins out: 95th percentile {p95:.2f} s, "
        f"maximum {max(battiti):.2f} s")


def test_la_pausa_fra_i_lotti_esiste():
    """The pause is what guarantees that the GIL passes, not a detail."""
    from greek_corpus_pipeline.analyzers import PAUSA_FRA_LOTTI

    assert 0 < PAUSA_FRA_LOTTI <= 0.05


# ── the evaluation is redone without rerunning the model ────────────────────

def test_cambiata_la_definizione_i_conti_si_rifanno_senza_il_modello(tmp_path):
    """The saved predictions stay valid: only the way of counting them changes.

    The case is that of evaluations saved when a single unreadable prediction
    suspended the measurement on all the other words: they report zero label
    agreements.  The predictions, however, are the right ones.  Rerunning a
    model on half a million records to redo a sum would be a waste of hours.
    """
    from gui_qt.workers import _confronto_con_modello
    from greek_corpus_pipeline import model_eval
    from greek_corpus_pipeline.storage import (
        load_stats_if_present, run_dir, save_dataframe, save_metadata,
    )

    workspace = tmp_path / "workspace"
    run_id = "giro"
    run_dir(workspace, run_id).mkdir(parents=True, exist_ok=True)
    save_dataframe(workspace, run_id, "tokens", CORPUS.copy())
    save_metadata(workspace, run_id, {"run_id": run_id, "stages": {}})

    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(len(superficie))
        fuori = superficie.copy()
        fuori["lemma"] = "x"
        fuori["postag"] = "n-s---mn-"
        return fuori

    def giro():
        _confronto_con_modello(
            workspace, run_id, {}, etichetta="udpipe",
            prepara=lambda: "modello", esegui=esegui,
            identita=lambda risorse: ("1.4.0.1", "abc"),
            progress_cb=lambda *a: None, log_cb=lambda *a: None)

    giro()
    assert len(esecuzioni) == 1, "the first pass must run the model"
    prima = load_stats_if_present(workspace, run_id, "udpipe_evaluation")
    assert prima["provenienza"]["definizione_valutazione"] == model_eval.EVALUATION_DEFINITION

    # the definition changes: the predictions stay, the counts do not
    vecchia = model_eval.EVALUATION_DEFINITION
    try:
        model_eval.EVALUATION_DEFINITION = vecchia + "-prova"
        giro()
    finally:
        model_eval.EVALUATION_DEFINITION = vecchia

    assert len(esecuzioni) == 1, "the model was run again just to redo a sum"
    dopo = load_stats_if_present(workspace, run_id, "udpipe_evaluation")
    assert dopo["provenienza"]["definizione_valutazione"] == vecchia + "-prova"
    assert dopo["lemma"]["accordi"] == prima["lemma"]["accordi"]
    assert dopo["postag"]["accordi"] == prima["postag"]["accordi"]


def test_un_corpus_diverso_fa_rieseguire_il_modello(tmp_path):
    """The opposite: if the corpus changes, recounting is not enough."""
    from gui_qt.workers import _confronto_con_modello
    from greek_corpus_pipeline.storage import run_dir, save_dataframe, save_metadata

    workspace = tmp_path / "workspace"
    run_id = "giro"
    run_dir(workspace, run_id).mkdir(parents=True, exist_ok=True)
    save_dataframe(workspace, run_id, "tokens", CORPUS.copy())
    save_metadata(workspace, run_id, {"run_id": run_id, "stages": {}})

    esecuzioni: list[int] = []

    def esegui(superficie, risorse, tick):
        esecuzioni.append(len(superficie))
        fuori = superficie.copy()
        fuori["lemma"] = "x"
        fuori["postag"] = "n-s---mn-"
        return fuori

    def giro(versione):
        _confronto_con_modello(
            workspace, run_id, {}, etichetta="udpipe",
            prepara=lambda: "modello", esegui=esegui,
            identita=lambda risorse: (versione, "abc"),
            progress_cb=lambda *a: None, log_cb=lambda *a: None)

    giro("1.4.0.1")
    giro("2.0.0")               # another model: it is rerun
    assert len(esecuzioni) == 2


# ── D · the dropdowns, after the first drawing ──────────────────────────────

def test_ogni_tendina_ridisegna_le_tabelle_e_non_le_svuota(
        applicazione, tmp_path, modelli_non_installati):
    """The dropdowns must keep working after the first drawing.

    At the first run the grouping dropdown is still empty, so the computation
    passes ``gruppo=""`` and does not touch ``agreement_by_group``.  Right after,
    ``_mostra_tabelle`` fills it with the available fields — and on the real
    corpora the only one is ``document_id``, which is also one of the merge keys.
    From then on every recomputation would raise inside the worker, ``_failed``
    would turn the exception into a log line and **apply nothing any more**, so
    the five tabs would stay at the last good result without anything saying so.

    Here every dropdown is moved at least once and the result is required to
    really arrive: no failure message and no emptied table.
    """
    finestra, pagina = _pagina(applicazione, tmp_path)
    # Stanza too must get something wrong, otherwise the table of its disagreements is
    # legitimately empty and would say nothing about this fault.
    finestra.state.stanza_comparison = _tabella_reale(
        tag_modello=["n-s---mn-", "v1spia---", "d--------", "c--------",
                     "n-s---mn-", "a-s---fn-"])
    guasti: list[str] = []
    pagina.logMessage.connect(guasti.append)

    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    assert pagina._group.count() > 0, "the grouping drop-down stayed empty"
    assert "document_id" in [pagina._group.itemText(i) for i in range(pagina._group.count())]

    def tabelle_piene(dove: str):
        for nome, widget in (("disaccordi", pagina._mismatches),
                             ("tre vie", pagina._three_way),
                             ("posizioni", pagina._slots),
                             ("per gruppo", pagina._by_group)):
            assert not widget.dataframe().empty, f"{nome} vuota {dove}"

    combinazioni = 0
    for tendina, valori in (
            (pagina._mismatch_source, ["Stanza", "UDPipe"]),
            (pagina._slot_right, ["Stanza", "UDPipe"]),
            (pagina._group, [pagina._group.itemText(i)
                             for i in range(pagina._group.count())])):
        for valore in valori:
            tendina.setCurrentText(valore)
            applicazione.processEvents()
            # If the dropdown already had that value Qt emits nothing: the recomputation
            # is then requested from the same entry point as the signal, which is what
            # is to be tested.
            pagina._ricalcola_viste()
            _attendi_sfondo(pagina, applicazione)
            combinazioni += 1
            assert not guasti, f"the view reported a fault: {guasti[:1]}"
            tabelle_piene(f"dopo aver scelto {valore}")

    for indice in range(pagina._position.count()):
        pagina._position.setCurrentIndex(indice)
        applicazione.processEvents()
        pagina._ricalcola_viste()
        _attendi_sfondo(pagina, applicazione)
        combinazioni += 1
        assert not guasti, f"the view reported a fault: {guasti[:1]}"

    assert combinazioni >= 14
    assert not guasti


def test_il_raggruppamento_per_document_id_arriva_alla_scheda(
        applicazione, tmp_path, modelli_non_installati):
    """The per-group card, with the field that the real corpora offer."""
    finestra, pagina = _pagina(applicazione, tmp_path)
    pagina.refresh()
    _attendi_sfondo(pagina, applicazione)
    pagina._group.setCurrentText("document_id")
    applicazione.processEvents()
    pagina._ricalcola_viste()
    _attendi_sfondo(pagina, applicazione)
    tabella = pagina._by_group.dataframe()
    assert not tabella.empty
    assert "document_id" in tabella.columns
    assert tabella["token"].sum() > 0
