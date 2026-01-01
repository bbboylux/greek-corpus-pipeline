"""Entry point.

Everything this file does is defensive. The application itself is started in
four lines; the rest exists because the two ways this program most often fails
for a non-technical user are (a) a missing dependency, and (b) an unhandled
exception that closes the window with no message at all. Both are turned into
something readable.
"""
from __future__ import annotations

import atexit
import logging
import sys
import threading
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LOG_PATH = _HERE / "pipeline_errors.log"

# The package lives in src/. It must be put in sys.path **here**, before everything
# else, because the first thing to do is to fix the number of threads: the numerical
# libraries read the environment when they are imported, and do not read it again
# afterwards.
_SRC = _HERE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from greek_corpus_pipeline.cpu import limita_thread
    _THREAD = limita_thread()
except Exception:                                      # noqa: BLE001
    _THREAD = None

# pythonw.exe — used on Windows to launch without a console window — sets
# sys.stdout and sys.stderr to None. Several libraries, including Stanza's
# downloader, write to stdout and die with AttributeError. Pointing both at the
# log file makes those writes succeed silently.
if sys.stdout is None:
    sys.stdout = open(str(_LOG_PATH), "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = sys.stdout

logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.ERROR,
    format="%(asctime)s  %(levelname)s  %(message)s",
    encoding="utf-8",
)

# The life-cycle log — start, close, threads — lives under a name of its own with its
# own threshold: the root stays at ERROR, so third-party information does not fill the
# file, and these few lines get there all the same.
_CICLO = logging.getLogger("gcp.ciclo")
_CICLO.setLevel(logging.INFO)

# A shutdown that does not go through Python — a segmentation fault inside a native
# library, the abort of Qt when a QThread is destroyed while it works — leaves no
# traceback. faulthandler writes the stack of all the threads to the log file all the
# same: it is the only thing left to read afterwards.
_FAULT_FILE = open(str(_LOG_PATH), "a", encoding="utf-8", buffering=1)
try:
    import faulthandler
    faulthandler.enable(file=_FAULT_FILE, all_threads=True)
except Exception:                                      # noqa: BLE001
    pass


def _hook_thread(args) -> None:
    """An exception inside a thread does not end up in sys.excepthook."""
    testo = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback))
    nome = getattr(args.thread, "name", "?")
    logging.error(f"UNHANDLED EXCEPTION in thread {nome}:\n{testo}")


try:
    threading.excepthook = _hook_thread
except Exception:                                      # noqa: BLE001
    pass



def _check_dependencies() -> list[str]:
    """Names of the required packages that are missing."""
    missing: list[str] = []
    # The four that are really needed. ``xmltodict`` is not in this list: the XML is
    # read with ``xml.parsers.expat``, which is in the standard library, and a user
    # without xmltodict would be refused at start-up because of a library that the
    # program never opens.
    for module, package in (("PyQt6", "PyQt6"), ("pandas", "pandas"),
                            ("pyarrow", "pyarrow"), ("matplotlib", "matplotlib")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def default_workspace() -> Path:
    """Where runs, downloads and models are kept: next to this file."""
    base = _HERE / "workspace"
    base.mkdir(parents=True, exist_ok=True)
    return base


def main() -> None:
    # If the program were ever frozen into an executable, the child that is born from
    # it must be able to return to its own work instead of reopening a window.  It
    # costs nothing and removes a class of faults.
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:                                  # noqa: BLE001
        pass

    missing = _check_dependencies()
    if missing:
        message = (
            "Some required libraries are missing:\n\n  "
            + "\n  ".join(missing)
            + "\n\nRun setup.bat again to install them."
        )
        print(message)
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            application = QApplication(sys.argv)
            QMessageBox.critical(None, "Incomplete installation", message)
        except Exception:
            pass
        sys.exit(1)

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from gui_qt.style import APP_STYLE

    def _hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.error("UNHANDLED EXCEPTION:\n" + text)
        try:
            QMessageBox.critical(
                None, "Unexpected error",
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"The details were written to:\n{_LOG_PATH}")
        except Exception:
            pass

    sys.excepthook = _hook

    _CICLO.info("START · threads per library: %s · processors: %s",
                _THREAD, __import__("os").cpu_count())
    atexit.register(lambda: _CICLO.info("ORDERLY SHUTDOWN of the application"))

    # torch has two pools and not just one: the limit must be set on both.
    try:
        from greek_corpus_pipeline.cpu import limita_torch
        limita_torch()
    except Exception:                                  # noqa: BLE001
        pass

    application = QApplication(sys.argv)
    application.setApplicationName("Greek Corpus Pipeline")
    application.setOrganizationName("Greek Corpus Pipeline")
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI", 10))
    application.setStyleSheet(APP_STYLE)

    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_workspace()
    workspace.mkdir(parents=True, exist_ok=True)

    from gui_qt.main_window import MainWindow

    window = MainWindow(workspace)
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
