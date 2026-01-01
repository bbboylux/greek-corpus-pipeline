# -*- coding: utf-8 -*-
"""UDPipe in a process of its own, because a thread is not enough.

``ufal.udpipe`` **does not release the GIL** while it works. This has been
measured: an observer thread that beats every 0.05 s receives exactly two beats
around a call of 500 sentences, and its maximum delay equals the whole duration
of the call — 0.90 s for 100 sentences, 4.06 s for 500, 17.18 s for 2,000. As
long as the call lasts, no other Python thread can run: not even that of the
interface, however much the work sits in a ``QThread``.

Small batches shorten the single block but do not remove the problem, and the
loading of the model remains a single call of one or two seconds. The only way
to take the GIL out of the way is to take the interpreter out of the way: the
model is loaded and works in **another process**, and the interface process
never touches the library.

A ``multiprocessing`` child is avoided because it can hang on Windows. The child
here is an ordinary subprocess launched with ``python -m``, and that choice
alone closes the three classic causes of that hang:

* **the child does not re-import the main module.**  ``multiprocessing`` with
  "spawn" makes the child re-run the ``__main__`` file to rebuild its state: on
  Windows, where "spawn" is the only mode, that file is ``app_qt.py``. Here the
  child imports a module that knows neither Qt nor pandas, and there is nothing
  to rebuild.
* **nothing large goes through the pipes.**  The sentences reach the child in a
  text file and the CoNLL-U comes back in another file; on a real corpus the
  output is tens of megabytes, and sending it through a pipe means filling the
  buffer — a child writing to a full pipe while the parent waits for it is the
  classic way of blocking both. Only short progress lines go through the pipe,
  and the parent always reads them.
* **nothing lasts forever.**  Every wait has a maximum time, there is a guard on
  silence, and in the end the child is closed anyway: first politely, then by
  force.

What does **not** change: the sentences, their order, the size of the batches,
the CoNLL-U text produced. The child makes the same calls as the in-process
route, in the same order, and returns the same texts. A test compares the two
routes line by line on the same input.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

__all__ = [
    "AnnullatoUdpipe",
    "ErroreUdpipe",
    "SEPARATORE_LOTTI",
    "analizza_frasi",
    "elabora",
]

#: Separates one batch from the next in the output file. It starts with ``#``
#: because the CoNLL-U reader discards comment lines: if for any reason it ended up
#: inside a batch, nothing of what is read would change.
SEPARATORE_LOTTI = "#␟GCP-LOTTO␟\n"

#: How long to wait at most for a line from the child before considering it lost. Loading
#: the model is the longest phase without notices.
SILENZIO_MASSIMO = 300.0

#: How long to wait for the child to leave by itself, before closing it.
ATTESA_CHIUSURA = 10.0

#: The lines that the child writes on its stdout. Short, one per batch.
_FASE = "FASE "
_PROGRESSO = "PROG "
_AVVISO = "AVVI "
_FINE = "FINE"
_ERRORE = "ERRO "


class ErroreUdpipe(RuntimeError):
    """UDPipe could not work, and the reason is in the message."""


class AnnullatoUdpipe(RuntimeError):
    """The work was interrupted on request."""


# ---------------------------------------------------------------------------
# The child
# ---------------------------------------------------------------------------

def elabora(percorso_modello: str, percorso_ingresso: str, percorso_uscita: str,
            lotto: int, percorso_stop: str = "", scrivi=None) -> int:
    """Loads the model, processes in batches, writes the CoNLL-U. Runs in the child.

    *scrivi* (write) receives the status lines; in the real child it is ``print``.
    Having it as an argument makes it possible to run the same function inside a
    test without launching a process.

    The interruption arrives through a file: the parent creates *percorso_stop* (the
    stop path), and the child looks for it between one batch and the next. A file is
    the only channel that works the same on Windows and elsewhere without pipes,
    signals or shared objects.
    """
    if scrivi is None:
        def scrivi(riga: str) -> None:
            sys.stdout.write(riga + "\n")
            sys.stdout.flush()

    try:
        try:
            from .cpu import limita_thread
            limita_thread()
        except Exception:                              # noqa: BLE001
            pass

        from ufal.udpipe import Model, Pipeline, ProcessingError

        scrivi(_FASE + "carico")
        modello = Model.load(percorso_modello)
        if modello is None:
            scrivi(_ERRORE + "UDPipe could not load the model: "
                   + percorso_modello)
            return 2
        tubo = Pipeline(modello, "horizontal", Pipeline.DEFAULT,
                        Pipeline.DEFAULT, "conllu")
        scrivi(_FASE + "pronto")

        testo = Path(percorso_ingresso).read_text(encoding="utf-8")
        frasi = testo.split("\n") if testo else []
        if frasi and frasi[-1] == "":
            frasi.pop()
        totale = len(frasi)
        stop = Path(percorso_stop) if percorso_stop else None

        with open(percorso_uscita, "w", encoding="utf-8", newline="") as fuori:
            for inizio in range(0, totale, lotto):
                if stop is not None and stop.exists():
                    scrivi(_ERRORE + "interrupted on request")
                    return 3
                fine = min(inizio + lotto, totale)
                errore = ProcessingError()
                # The final “\n” is present in the direct call too: the line that UDPipe
                # receives must be identical byte for byte.
                prodotto = tubo.process("\n".join(frasi[inizio:fine]) + "\n", errore)
                if errore.occurred():
                    scrivi(_AVVISO + f"lotto {inizio}-{fine}: {errore.message}")
                    prodotto = ""
                fuori.write(prodotto)
                if not prodotto.endswith("\n"):
                    fuori.write("\n")
                fuori.write(SEPARATORE_LOTTI)
                scrivi(f"{_PROGRESSO}{fine} {totale}")
        scrivi(_FINE)
        return 0
    except BaseException as errore:                    # noqa: BLE001
        import traceback
        scrivi(_ERRORE + f"{type(errore).__name__}: {errore} | "
               + traceback.format_exc().replace("\n", " ⏎ "))
        return 1


def _da_riga_di_comando(argomenti: list[str]) -> int:
    if len(argomenti) < 4:
        sys.stderr.write("uso: -m greek_corpus_pipeline.udpipe_processo "
                         "MODELLO INGRESSO USCITA LOTTO [STOP]\n")
        return 64
    modello, ingresso, uscita, lotto = argomenti[:4]
    stop = argomenti[4] if len(argomenti) > 4 else ""
    return elabora(modello, ingresso, uscita, int(lotto), stop)


# ---------------------------------------------------------------------------
# The parent
# ---------------------------------------------------------------------------

def _interprete() -> str:
    """The executable with which to launch the child.

    Under ``pythonw.exe`` — which is how ``run.bat`` starts the program on Windows,
    so as not to leave a black window open — the ``python.exe`` next to it is
    preferred: it has the same environment and a normal stdout. If it is not there,
    ``pythonw.exe`` will do all the same, because its stdout here is a pipe and not
    a console.
    """
    eseguibile = Path(sys.executable)
    if eseguibile.name.lower() == "pythonw.exe":
        accanto = eseguibile.with_name("python.exe")
        if accanto.exists():
            return str(accanto)
    return str(eseguibile)


def _ambiente() -> dict:
    """The environment of the child: the package must be importable.

    The program also runs from a folder without installation, with ``src`` added to the
    path by hand: in that case the child would not find the package, and must be told so
    through ``PYTHONPATH``.
    """
    ambiente = dict(os.environ)
    radice = Path(__file__).resolve().parent.parent      # …/src
    percorsi = [p for p in (str(radice), ambiente.get("PYTHONPATH", "")) if p]
    ambiente["PYTHONPATH"] = os.pathsep.join(percorsi)
    return ambiente


def _senza_finestra() -> dict:
    """On Windows the child must not make a black window flash."""
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def analizza_frasi(
    frasi: Iterable[str],
    percorso_modello: str | Path,
    *,
    lotto: int,
    progresso: Callable[[int, int], None] | None = None,
    fase: Callable[[str], None] | None = None,
    annullato: Callable[[], bool] | None = None,
) -> tuple[list[str], list[str]]:
    """The sentences go through UDPipe in another process. Returns (batches, warnings).

    *lotti* (batches) is the list of the CoNLL-U texts, one per batch, in the order
    in which they were produced: exactly what the direct call returns.

    *annullato* (cancelled) is queried while waiting: if it returns true, the child
    receives the request to stop and is closed.
    """
    frasi = list(frasi)
    percorso_modello = Path(percorso_modello)
    if not percorso_modello.exists():
        raise FileNotFoundError(f"UDPipe model not found: {percorso_modello}")
    if not frasi:
        return [], []

    cartella = Path(tempfile.mkdtemp(prefix="gcp-udpipe-"))
    ingresso = cartella / "frasi.txt"
    uscita = cartella / "conllu.txt"
    stop = cartella / "FERMATI"
    ingresso.write_text("\n".join(frasi) + "\n", encoding="utf-8")

    comando = [_interprete(), "-m", "greek_corpus_pipeline.udpipe_processo",
               str(percorso_modello), str(ingresso), str(uscita), str(int(lotto)),
               str(stop)]

    avvisi: list[str] = []
    errori: list[str] = []
    finito = [False]
    righe: "list[str]" = []
    processo = None
    lettore = None
    try:
        processo = subprocess.Popen(
            comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=_ambiente(), **_senza_finestra())

        # The lines are read in a thread: ``readline`` blocks, and the parent must be able
        # to look at the clock and at the request for interruption. The pipe is in any
        # case always drained, which is the condition for not blocking the child.
        def leggi() -> None:
            try:
                for riga in processo.stdout:
                    righe.append(riga.rstrip("\n"))
            except Exception:                          # noqa: BLE001
                pass
            finally:
                finito[0] = True

        lettore = threading.Thread(target=leggi, name="gcp-udpipe-lettore",
                                   daemon=True)
        lettore.start()

        letto = 0
        ultimo_segno = time.monotonic()
        fine_dichiarata = False
        while True:
            if annullato is not None and annullato():
                stop.write_text("stop", encoding="utf-8")
                raise AnnullatoUdpipe("interrupted on request")

            while letto < len(righe):
                riga = righe[letto]
                letto += 1
                ultimo_segno = time.monotonic()
                if riga.startswith(_PROGRESSO):
                    pezzi = riga[len(_PROGRESSO):].split()
                    if progresso is not None and len(pezzi) == 2:
                        progresso(int(pezzi[0]), int(pezzi[1]))
                elif riga.startswith(_FASE):
                    if fase is not None:
                        fase(riga[len(_FASE):])
                elif riga.startswith(_AVVISO):
                    avvisi.append(riga[len(_AVVISO):])
                elif riga.startswith(_ERRORE):
                    errori.append(riga[len(_ERRORE):])
                elif riga.strip() == _FINE:
                    fine_dichiarata = True

            if fine_dichiarata:
                break
            if errori:
                break
            if finito[0] and letto >= len(righe):
                break
            if time.monotonic() - ultimo_segno > SILENZIO_MASSIMO:
                stop.write_text("stop", encoding="utf-8")
                raise ErroreUdpipe("the UDPipe process has not answered for "
                                   f"{SILENZIO_MASSIMO:.0f} seconds.")
            time.sleep(0.02)

        if errori:
            if any("interrupted on request" in messaggio for messaggio in errori):
                raise AnnullatoUdpipe("interrupted on request")
            raise ErroreUdpipe(" · ".join(errori))
        if not fine_dichiarata:
            codice = processo.poll()
            scarto = ""
            try:
                scarto = (processo.stderr.read() or "").strip()[:2000]
            except Exception:                          # noqa: BLE001
                pass
            raise ErroreUdpipe(
                "the UDPipe process ended without finishing "
                f"(code {codice}). {scarto}")
    finally:
        _chiudi(processo, lettore)

    testo = uscita.read_text(encoding="utf-8") if uscita.exists() else ""
    pezzi = testo.split(SEPARATORE_LOTTI)
    if pezzi and pezzi[-1].strip() == "":
        pezzi.pop()
    _pulisci(cartella)
    return pezzi, avvisi


def _chiudi(processo, lettore) -> None:
    """The child leaves, in every case: first politely, then by force."""
    if processo is None:
        return
    if processo.poll() is None:
        try:
            processo.terminate()
        except Exception:                              # noqa: BLE001
            pass
    try:
        processo.wait(timeout=ATTESA_CHIUSURA)
    except Exception:                                  # noqa: BLE001
        try:
            processo.kill()
            processo.wait(timeout=ATTESA_CHIUSURA)
        except Exception:                              # noqa: BLE001
            pass
    for tubo in (processo.stdout, processo.stderr):
        try:
            if tubo is not None:
                tubo.close()
        except Exception:                              # noqa: BLE001
            pass
    if lettore is not None:
        lettore.join(timeout=2.0)


def _pulisci(cartella: Path) -> None:
    try:
        for figlio in cartella.iterdir():
            figlio.unlink(missing_ok=True)
        cartella.rmdir()
    except Exception:                                  # noqa: BLE001
        pass


if __name__ == "__main__":                             # pragma: no cover
    raise SystemExit(_da_riga_di_comando(sys.argv[1:]))
