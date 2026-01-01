# -*- coding: utf-8 -*-
"""The long work stays outside the interface thread, and it shows.

Running a model on Gorman takes minutes, not seconds.  A window that stops
redrawing for minutes on Windows is covered by the words “Not responding”, and
whoever sees them closes it: the work has not gone wrong, it has been killed.

It is therefore not enough that the code *looks* asynchronous.  These tests
verify three separate things, because they are three different ways of getting
it wrong:

1. the long function really runs in another thread — the identity of the
   thread is looked at from inside the function, not the form of the code that
   calls it;
2. while it runs, the main thread keeps processing events — which is what
   “does not freeze” means for whoever looks at the screen;
3. the progress is determinate and grows, and is not a ``processEvents()``
   called inside a loop to fake a thread that is not there.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def _attendi(worker, applicazione, limite: float = 20.0) -> None:
    """Processes events until the worker has finished, as the window does."""
    scadenza = time.monotonic() + limite
    while worker.isRunning() and time.monotonic() < scadenza:
        applicazione.processEvents()
        time.sleep(0.005)
    worker.wait(2000)
    applicazione.processEvents()


# ── 1. the long function does not run in the main thread ────────────────────

def test_la_funzione_lunga_gira_in_un_altro_thread(application):
    from gui_qt.workers import PipelineWorker

    principale = threading.get_ident()
    visto: dict[str, int] = {}

    def lavoro(progress_cb, log_cb):
        visto["thread"] = threading.get_ident()
        time.sleep(0.05)

    worker = PipelineWorker(lavoro)
    worker.start()
    _attendi(worker, application)

    assert "thread" in visto, "the function was not run"
    assert visto["thread"] != principale, \
        "the long function ran in the interface thread"


def test_il_thread_principale_continua_a_smaltire_eventi(application):
    """The proof of “does not freeze”, measured instead of declared."""
    from gui_qt.workers import PipelineWorker

    battiti: list[int] = []
    orologio = QTimer()
    orologio.setInterval(10)
    orologio.timeout.connect(lambda: battiti.append(1))
    orologio.start()

    def lavoro(progress_cb, log_cb):
        time.sleep(0.4)

    worker = PipelineWorker(lavoro)
    worker.start()
    _attendi(worker, application)
    orologio.stop()

    assert len(battiti) >= 5, (
        f"the main thread received only {len(battiti)} events "
        "while the job was running: the window was frozen")


def test_l_errore_di_un_modello_arriva_intero_alla_finestra(application):
    """The real type and message, not a secondary error."""
    from gui_qt.workers import PipelineWorker

    def lavoro(progress_cb, log_cb):
        raise RuntimeError("il modello grc non è stato scaricato")

    ricevuti: list[str] = []
    worker = PipelineWorker(lavoro)
    worker.error.connect(ricevuti.append)
    worker.start()
    _attendi(worker, application)

    assert ricevuti, "the error did not reach the window"
    assert "RuntimeError" in ricevuti[0]
    assert "grc" in ricevuti[0]
    assert "FileNotFoundError" not in ricevuti[0]


# ── 2. the two models go through there, and not through a direct call ───────

@pytest.mark.parametrize("gestore", ["_run_stanza", "_run_udpipe"])
def test_i_modelli_si_avviano_con_run_work(gestore):
    """The page asks the window for the work, it does not execute it itself.

    ``run_work`` emits a signal and returns immediately; the window collects it in
    a ``PipelineWorker``.  Calling ``run_stanza(...)`` directly from the handler of
    the button would block the interface thread for the whole time of the model,
    and it is the error that this test keeps closed.
    """
    import inspect

    from gui_qt.pages.models_page import ModelsPage

    sorgente = inspect.getsource(getattr(ModelsPage, gestore))
    nome = gestore.lstrip("_")
    # The function travels as an argument — ``run_work(run_udpipe, ...)`` — and is not
    # called: if the handler invoked it, the parenthesis would follow the name instead
    # of the comma, and the interface thread would stay inside the model for the whole
    # duration of the comparison.
    assert f"self.run_work({nome}," in sorgente, \
        f"{gestore} does not pass {nome} to run_work"
    corpo = sorgente.split("\n", 1)[1]          # without the signature line
    assert f"{nome}(" not in corpo, f"{gestore} seems to call {nome} directly"


def test_la_finestra_esegue_il_lavoro_in_un_pipeline_worker():
    import inspect

    from gui_qt.main_window import MainWindow

    sorgente = inspect.getsource(MainWindow._start_work)
    assert "PipelineWorker(" in sorgente
    assert ".start()" in sorgente


def test_nessun_processevents_nel_codice_dell_applicazione():
    """``processEvents()`` inside a loop is a fake thread, and must be looked for.

    In the tests it is legitimate — it is the way to run the event loop without opening
    a window — so only the code that is delivered is looked at.
    """
    sospette: list[str] = []
    for cartella in ("gui_qt", "src"):
        for sorgente in (ROOT / cartella).rglob("*.py"):
            if "__pycache__" in sorgente.parts:
                continue
            for numero, riga in enumerate(sorgente.read_text(encoding="utf-8").splitlines(), 1):
                if "processEvents" in riga.split("#", 1)[0]:
                    sospette.append(f"{sorgente.relative_to(ROOT)}:{numero}")
    assert not sospette, "processEvents in the application code: " + ", ".join(sospette)


# ── 3. the progress is determinate and grows ────────────────────────────────

def test_il_progresso_dei_modelli_e_determinato_e_cresce(tmp_path):
    """The progress is determinate, grows, starts at zero and reaches one.

    A bar that does not say where it stands is not a progress, it is an animation.  The
    check is on the **fraction** and not on the number of steps: the scale is an
    implementation detail, and the model step needs to move inside itself instead of
    standing still for its whole duration.
    """
    import pandas as pd

    from gui_qt.workers import _confronto_con_modello
    from greek_corpus_pipeline.storage import run_dir, save_dataframe, save_metadata
    from tests.test_model_eval import CORPUS

    workspace = tmp_path / "workspace"
    run_id = "giro"
    run_dir(workspace, run_id).mkdir(parents=True, exist_ok=True)
    save_dataframe(workspace, run_id, "tokens", CORPUS.copy())
    save_metadata(workspace, run_id, {"run_id": run_id, "stages": {}})

    passi: list[tuple[int, int]] = []

    def esegui(superficie, risorse, tick):
        # the model reports its own progress sentence by sentence.  More than the 150 ms
        # throttle passes between one notice and the next, so it is visible that the
        # model step really moves.
        for fatte in (1, 2, 3, 4):
            tick(fatte, 4)
            time.sleep(0.2)
        fuori = superficie.copy()
        fuori["lemma"] = "x"
        fuori["postag"] = "n-s---mn-"
        return fuori

    _confronto_con_modello(
        workspace, run_id, {}, etichetta="udpipe",
        prepara=lambda: "modello", esegui=esegui,
        identita=lambda risorse: ("1.3.1", "abc"),
        progress_cb=lambda fatto, totale, testo: passi.append((fatto, totale)),
        log_cb=lambda testo: None)

    assert passi, "no progress reported"
    assert all(totale > 0 for _, totale in passi), "the total is not declared"
    assert len({totale for _, totale in passi}) == 1, "the total changes along the way"
    quote = [fatto / totale for fatto, totale in passi]
    assert quote == sorted(quote), f"the progress went backwards: {quote}"
    assert 0 < quote[0] < 1, "the progress does not start at the beginning"
    assert quote[-1] == 1.0, "the progress does not reach the end"
    # inside the model phase the bar moves: more than one distinct value between 50% and
    # 90%, which is the band in which that phase lives.
    dentro = {q for q in quote if 0.5 < q < 0.95}
    assert len(dentro) >= 2, (
        f"the bar stays still for the whole model phase: {sorted(quote)}")


def test_udpipe_riporta_l_avanzamento_una_volta_per_lotto():
    """Progress costs little: it is reported per batch, not per token.

    Verified on behaviour and not on the text of the source: a test that reads the code
    instead of executing it breaks at every rewrite without anything having got worse.
    """
    import numpy as np

    from greek_corpus_pipeline.analyzers import _leggi_lotti

    # ten sentences of two tokens, batches of three: four batches
    starts = np.array([2 * i for i in range(11)])
    lotti = [""] * 4
    passi: list[tuple[int, int]] = []
    _leggi_lotti(lotti, starts, 3, 10, lambda fatte, totale: passi.append((fatte, totale)))

    assert len(passi) == 4, "one notice per batch, no more and no fewer"
    assert [fatte for fatte, _ in passi] == [3, 6, 9, 10], \
        "the progress does not say which sentence it has reached"
    assert all(totale == 10 for _, totale in passi)


# ── 4. after an error the page becomes usable again ─────────────────────────

def test_dopo_un_errore_i_bottoni_dei_modelli_tornano_attivi(application, tmp_path):
    """Once the popup is closed it must be possible to retry, without leaving the
    page.

    When the comparison succeeds, the run is reloaded and the page refreshes by
    itself.  When it fails nothing is reloaded: the page would stay with the bar
    spinning and the two buttons off — the look of a job in progress on top of a
    dead job — until one changed step and came back.
    """
    import pandas as pd

    from gui_qt.pages.base import AppState
    from gui_qt.pages.models_page import ModelsPage
    from tests.test_model_eval import CORPUS

    stato = AppState(workspace=tmp_path)
    stato.run_id = "giro"
    stato.tokens = CORPUS.copy()
    pagina = ModelsPage(stato)
    pagina.build()
    try:
        pagina._running = True
        pagina._busy_bar.setVisible(True)
        pagina._stanza_button.setEnabled(False)
        pagina._udpipe_button.setEnabled(False)

        pagina.work_finished(False, "RuntimeError: il modello grc non è stato scaricato")

        assert not pagina._running
        assert not pagina._busy_bar.isVisibleTo(pagina)
        # The buttons again depend only on the corpus and on the installed model, which
        # is the right condition: if Stanza is not there they stay off because Stanza is
        # not there, not because an error left them so.
        from greek_corpus_pipeline.analyzers import check_stanza_available
        disponibile, _ = check_stanza_available()
        assert pagina._stanza_button.isEnabled() == disponibile
    finally:
        pagina.deleteLater()
        application.processEvents()
