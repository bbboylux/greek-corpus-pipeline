"""The application shell: a numbered rail on the left, one page at a time.

The organising metaphor is a sequence of steps, because that is how the work
actually goes: load a corpus, look at it, check it, correct it, ask it
questions. Steps that cannot yet be taken are visibly disabled with a reason
attached ("load a corpus first"), rather than silently doing nothing — a
disabled control that explains itself teaches the workflow without a manual.

Only one long operation runs at a time. That is a deliberate restriction: the
operations write into the same run directory, and two of them at once would
produce results that depend on the order they happened to finish in.
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from .i18n import LANGUAGES, T, _STRINGS, counted, number, tr
from .pages.base import AppState
from .pages.charts_page import ChartsPage
from .pages.errors_page import ErrorsPage
from .pages.gold_page import GoldPage
from .pages.load_page import LoadPage
from .pages.models_page import ModelsPage
from .pages.overview_page import OverviewPage
from .pages.review_page import ReviewPage
from .pages.rules_page import RulesPage
from .pages.search_page import SearchPage
from .pages.stats_page import StatsPage
from .pages.variation_page import VariationPage
from .style import ACCENT, CARD, GOOD, LINE, LINE_STRONG, MUTED

#: The threads that at the moment of closing are still inside a call to a native
#: library and cannot be interrupted.  Keeping a reference to them here prevents
#: Python from destroying them — a ``QThread`` destroyed while running calls
#: ``qFatal()`` and the process aborts.  The list is never emptied: that is its
#: purpose.
_TRATTIENI: list = []
from .widgets import ghost_button
from .workers import PipelineWorker, RunLoader

#: The two spellings of “Ready”: the status line recognises itself at rest by comparing
#: with both, because at the moment of the change it is still written in the previous
#: language.
_STRINGS_READY = _STRINGS["app.ready"]

#: (key, page class, title key, hint key, what it needs): the shape of an entry of
#: ``STEPS`` below.
#:
#: The rail numbers the steps by their position in ``STEPS``, so removing a step
#: renumbers the ones after it and no gap is left behind: the numbers are never written
#: down anywhere else.
#:
#: ``RIFERIMENTO`` (“reference”) holds the pages that are not steps of a path but manuals
#: to be opened when needed. They stay at the bottom of the rail, under their own
#: heading, and do not take a number.
RIFERIMENTO = {"rules"}

STEPS = [
    ("load", LoadPage, "step.load", "step.load.hint", None),
    ("overview", OverviewPage, "step.overview", "step.overview.hint", "corpus"),
    ("errors", ErrorsPage, "step.errors", "step.errors.hint", "corpus"),
    ("variation", VariationPage, "step.variation", "step.variation.hint", "corpus"),
    ("review", ReviewPage, "step.review", "step.review.hint", "findings"),
    ("search", SearchPage, "step.search", "step.search.hint", "corpus"),
    ("stats", StatsPage, "step.stats", "step.stats.hint", "corpus"),
    ("charts", ChartsPage, "step.charts", "step.charts.hint", "corpus"),
    ("models", ModelsPage, "step.models", "step.models.hint", "corpus"),
    ("gold", GoldPage, "step.gold", "step.gold.hint", "corpus"),
    ("rules", RulesPage, "step.rules", "step.rules.hint", None),
]


from greek_corpus_pipeline import __version__


def _title() -> str:
    """Window title with version and the folder the code is really running from.

    A user with two copies of the program on disk — one in Downloads, one on the
    Desktop — has no way to tell which one just started, and will reasonably
    conclude that an update did not arrive when in fact they launched the other
    copy. Putting the version and the source folder in the title costs one line
    and removes a whole class of confusion.
    """
    from pathlib import Path

    try:
        import greek_corpus_pipeline
        root = Path(greek_corpus_pipeline.__file__).resolve().parents[2]
        location = str(root)
    except Exception:                                  # noqa: BLE001
        location = "?"
    return f"{tr('app.title')} — v{__version__} — {location}"


class StepButton(QPushButton):
    """One entry in the left rail: number, name, hint, status dot."""

    def __init__(self, number: int | None, title: str, hint: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("stepButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)
        politica = self.sizePolicy()
        politica.setHeightForWidth(True)
        self.setSizePolicy(politica)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 8, 12, 8)
        layout.setSpacing(11)

        # A reference-only page is not a step of the path, and numbering it would tell
        # whoever reads the bar that it has to be done last. The dot in place of the
        # number says that it is opened when needed.
        self._numerata = number is not None
        self._number = QLabel(str(number) if self._numerata else "·")
        self._number.setFixedSize(26, 26)
        self._number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_number_style(False)
        layout.addWidget(self._number)

        text = QVBoxLayout()
        text.setSpacing(3)
        self._title = QLabel(title)
        self._title.setStyleSheet("font-weight: 600; background: transparent;")
        self._hint = QLabel(hint)
        self._hint.setObjectName("stepHint")
        self._hint.setWordWrap(True)
        # A wrapping QLabel can say how tall it will be only if it is asked to compute
        # the height from the width. Without this the English subtitle, longer than the
        # Italian one, would be cut off halfway.
        politica = self._hint.sizePolicy()
        politica.setHeightForWidth(True)
        self._hint.setSizePolicy(politica)
        self._hint.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        text.addWidget(self._title)
        text.addWidget(self._hint)
        layout.addLayout(text, 1)

        # The state of the step. A green square of nine pixels cannot be read: a tick is
        # recognised even at a glance, and says “done” instead of saying “green”.
        self._dot = QLabel("")
        self._dot.setFixedSize(16, 16)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._dot)

    def sizeHint(self):
        """The height that is really needed, wrapped subtitle included.

        A ``QPushButton`` asks its own layout for its height, and a wrapping ``QLabel``
        cannot say how tall it will be until it knows the width: without this the
        English subtitle — longer than the Italian one — would be cut off halfway with
        nothing to signal it. Here the width is known, and the height is computed.
        """
        base = super().sizeHint()
        larghezza = self.width() or base.width()
        margini = self.layout().contentsMargins()
        disponibile = max(
            60, larghezza - margini.left() - margini.right()
            - self._number.width() - self._dot.width() - 2 * self.layout().spacing())
        alta = (self._title.sizeHint().height()
                + self._hint.heightForWidth(disponibile)
                + margini.top() + margini.bottom() + 3)
        base.setHeight(max(base.height(), alta))
        return base

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.updateGeometry()

    def _set_number_style(self, active: bool) -> None:
        """The number of the step: a filled burgundy circle when it is the open one.

        A reference-only page carries no number, and no circle either: a dot, because it
        is not a step of a path.
        """
        if not getattr(self, "_numerata", True):
            self._number.setStyleSheet(
                f"background: transparent; color: {ACCENT if active else MUTED};"
                f"font-size: 17px; font-weight: 700;")
            return
        if active:
            sfondo, testo, bordo = ACCENT, "white", ACCENT
        else:
            sfondo, testo, bordo = "transparent", MUTED, LINE_STRONG
        self._number.setStyleSheet(
            f"background: {sfondo}; color: {testo}; border: 1.5px solid {bordo};"
            f"border-radius: 13px; font-size: 12px; font-weight: 700;")

    def set_texts(self, title: str, hint: str) -> None:
        self._title.setText(title)
        self._hint.setText(hint)

    def set_active(self, active: bool) -> None:
        self._set_number_style(active)

    def set_done(self, done: bool) -> None:
        self._dot.setText("✓" if done else "")
        self._dot.setStyleSheet(
            f"color: {GOOD}; font-size: 14px; font-weight: 700; background: transparent;"
            if done else "background: transparent;")
        self._dot.setToolTip(tr("rail.done") if done else "")


class MainWindow(QMainWindow):

    def __init__(self, workspace: Path) -> None:
        super().__init__()
        self.state = AppState(workspace=workspace)
        self._worker: PipelineWorker | None = None
        self._loader: RunLoader | None = None

        self.setWindowTitle(_title())
        self.setMinimumSize(1280, 840)
        self.resize(1500, 940)
        self._apply_style()

        self._build()
        self._go_to("load")

    # ── Construction ───────────────────────────────────────────────────
    @staticmethod
    def _apply_style() -> None:
        """The style sheet, applied by the window and not only at start-up.

        If the style sheet were applied only by ``app_qt.py``, the entry point, whoever
        built a ``MainWindow`` on their own — a test, a bench that photographs the
        pages — would get the window with the default look of Qt, and would not notice:
        the window works all the same.  The photographs would show a program that does
        not exist.  The window therefore applies it itself, if the application does not
        already have one of its own.
        """
        from PyQt6.QtWidgets import QApplication
        from .style import APP_STYLE

        applicazione = QApplication.instance()
        if applicazione is not None and not applicazione.styleSheet():
            applicazione.setStyleSheet(APP_STYLE)

    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar())

        # The stack has to exist before the rail is built: building the rail
        # also builds every page and puts it into the stack.
        self._stack = QStackedWidget()

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        middle.addWidget(self._build_rail())
        middle.addWidget(self._stack, 1)
        holder = QWidget()
        holder.setLayout(middle)
        root.addWidget(holder, 1)

        root.addWidget(self._build_status_bar())

    def _build_title_bar(self) -> QWidget:
        """The header: light, with a burgundy line beneath instead of a band.

        A solid band sixty pixels tall takes the best place in the window to say the name
        of the program, which whoever works already knows.  Here the identity colour is
        a line two pixels thick, and the space goes to the loaded corpus, which is the
        only thing in the header that changes.
        """
        bar = QWidget()
        bar.setObjectName("titleBar")
        # Without this a bare QWidget does not draw the background or the border that
        # the style sheet assigns it: the burgundy line under the header would not
        # appear, and nobody would know why.
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(62)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(22, 0, 18, 0)
        layout.setSpacing(14)
        # Without vertical alignment the badge and the dropdown stretch to the height of
        # the bar and the pill becomes a rectangle.
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(1)
        riga = QHBoxLayout()
        riga.setSpacing(8)
        title = QLabel(tr("app.title"))
        title.setObjectName("appTitle")
        title.setToolTip(_title())
        versione = QLabel(f"v{__version__}")
        versione.setObjectName("appVersion")
        riga.addWidget(title)
        riga.addWidget(versione)
        riga.addStretch(1)
        text.addLayout(riga)
        self._subtitle = QLabel(tr("app.subtitle"))
        self._subtitle.setObjectName("appSubtitle")
        text.addWidget(self._subtitle)
        layout.addLayout(text)
        layout.addStretch(1)

        self._corpus_badge = QLabel(tr("app.no_corpus"))
        self._corpus_badge.setObjectName("corpusBadgeEmpty")
        self._corpus_badge.setFixedHeight(30)
        layout.addWidget(self._corpus_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self._language = QComboBox()
        for code, name in LANGUAGES.items():
            self._language.addItem(name, code)
        # The menu shows the language in which the interface is written at this moment, whatever it is.
        # If it showed another one, choosing the entry that is already on display would do nothing (Qt
        # sends no signal when the index does not change) and the first choice of the person would be lost.
        self._select_language(T.language)
        self._language.setFixedWidth(118)
        self._language.setFixedHeight(32)
        self._language.currentIndexChanged.connect(self._change_language)
        layout.addWidget(self._language, 0, Qt.AlignmentFlag.AlignVCenter)
        return bar

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("rail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setFixedWidth(314)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(10, 16, 10, 12)
        layout.setSpacing(3)

        self._step_buttons: dict[str, StepButton] = {}
        self._pages: dict[str, object] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        numero = 0
        for key, page_class, title_key, hint_key, _needs in STEPS:
            if key in RIFERIMENTO:
                intestazione = QLabel(tr("rail.reference"))
                intestazione.setObjectName("stepHint")
                intestazione.setStyleSheet(
                    f"color: {MUTED}; font-size: 10.5px; font-weight: 700;"
                    "letter-spacing: 1px; padding: 14px 12px 4px 12px;")
                layout.addWidget(intestazione)
                self._rail_reference_label = intestazione
                button = StepButton(None, tr(title_key), tr(hint_key))
            else:
                numero += 1
                button = StepButton(numero, tr(title_key), tr(hint_key))
            button.clicked.connect(lambda _checked=False, k=key: self._go_to(k))
            self._group.addButton(button)
            layout.addWidget(button)
            self._step_buttons[key] = button

            page = page_class(self.state)
            page.requestWork.connect(self._start_work)
            page.requestNavigate.connect(self._go_to)
            page.logMessage.connect(self._log)
            page.requestReload.connect(self._reload_run)
            self._pages[key] = page
            self._stack.addWidget(page)

            # A little breathing room after the correction: it separates the work on the
            # corpus from the queries.
            if key == "review":
                spacer = QFrame()
                spacer.setFixedHeight(10)
                layout.addWidget(spacer)

        layout.addStretch(1)
        return rail

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(f"background: {CARD}; border-top: 1px solid {LINE};")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(12)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedWidth(300)
        self._progress.setVisible(False)
        # The percentage in digits beside the bar. A bar says “more or less halfway”;
        # “41%” says how much is left, and it is what is needed to decide whether to
        # wait or go and get a coffee.
        self._percent = QLabel("")
        self._percent.setObjectName("progressText")
        self._percent.setFixedWidth(46)
        self._percent.setAlignment(Qt.AlignmentFlag.AlignRight
                                   | Qt.AlignmentFlag.AlignVCenter)
        self._percent.setVisible(False)
        self._status = QLabel(tr("app.ready"))
        self._status.setObjectName("hint")
        self._toggle_log = ghost_button(tr("app.show_log"))
        self._toggle_log.clicked.connect(self._toggle_log_view)
        top.addWidget(self._progress)
        top.addWidget(self._percent)
        top.addWidget(self._status, 1)
        top.addWidget(self._toggle_log)
        layout.addLayout(top)

        self._log_view = QTextEdit()
        self._log_view.setObjectName("logView")
        self._log_view.setReadOnly(True)
        self._log_view.setFixedHeight(150)
        self._log_view.setVisible(False)
        layout.addWidget(self._log_view)
        return bar

    # ── Navigation ─────────────────────────────────────────────────────
    def _go_to(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        if not self._step_available(key):
            self._log(tr("step.locked"))
            return
        for name, button in self._step_buttons.items():
            active = name == key
            button.setChecked(active)
            button.set_active(active)
        self._stack.setCurrentWidget(page)
        # The header is recomputed every time the page changes, and not only when a run
        # is loaded: so it cannot say “no corpus” while the page below shows data, which
        # is a contradiction that whoever looks has no way to resolve.
        self._update_badge()
        page.refresh()

    def _step_available(self, key: str) -> bool:
        needs = next((item[4] for item in STEPS if item[0] == key), None)
        if needs is None:
            return True
        if needs == "corpus":
            return self.state.has_corpus
        if needs == "findings":
            return self.state.has_findings
        return True

    def _update_rail(self) -> None:
        stages = (self.state.metadata or {}).get("stages", {}) or {}
        done = {
            "load": self.state.has_corpus,
            "overview": self.state.has_corpus,
            "errors": self.state.has_findings,
            "review": "corrections" in stages,
            "search": False,
            "stats": False,
            "charts": False,
            "models": self.state.has_models,
            "gold": not self.state.corrected_tokens.empty,
            "rules": False,
        }
        for key, button in self._step_buttons.items():
            button.setEnabled(self._step_available(key))
            button.set_done(bool(done.get(key)))
            if not self._step_available(key):
                needs = next((item[4] for item in STEPS if item[0] == key), None)
                button.setToolTip(tr("step.locked") if needs == "corpus"
                                  else tr("step.needs_analysis"))
            else:
                button.setToolTip("")

    # ── Language ───────────────────────────────────────────────────────
    def _select_language(self, code: str) -> None:
        """Shows *code* in the language menu without changing the language of the interface."""
        index = self._language.findData(code)
        if index < 0:
            return
        self._language.blockSignals(True)
        try:
            self._language.setCurrentIndex(index)
        finally:
            self._language.blockSignals(False)

    def _change_language(self) -> None:
        code = self._language.currentData()
        T.set_language(code)
        self.setWindowTitle(_title())
        self._subtitle.setText(tr("app.subtitle"))
        self._toggle_log.setText(
            tr("app.hide_log") if self._log_view.isVisible() else tr("app.show_log"))
        for key, _cls, title_key, hint_key, _needs in STEPS:
            self._step_buttons[key].set_texts(tr(title_key), tr(hint_key))
        etichetta = getattr(self, "_rail_reference_label", None)
        if etichetta is not None:
            etichetta.setText(tr("rail.reference"))
        for page in self._pages.values():
            try:
                page.retranslate()
            except Exception as exception:            # noqa: BLE001
                self._log(tr("app.retranslate_failed", exception))
        # Refresh only the visible page: retranslate() updates the static strings of all
        # the pages, but refresh() — which can cost seconds on the data pages — must be
        # called only on the one that is open at this moment. The pages that are not
        # visible will update when the user opens them.
        current = self._stack.currentWidget()
        if current is not None:
            try:
                current.refresh()
            except Exception as exception:            # noqa: BLE001
                self._log(tr("app.retranslate_failed", exception))
        # The status line says “Ready” at rest, and at rest it must be rewritten. If
        # instead it is announcing an operation in progress, that message is more
        # informative than its translation and stays where it is.
        if self._status.text() in _STRINGS_READY:
            self._status.setText(tr("app.ready"))
        self._update_badge()

    # ── Work ───────────────────────────────────────────────────────────
    @pyqtSlot(object, tuple, dict, str)
    def _start_work(self, function, args: tuple, kwargs: dict, label: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, tr("app.busy_title"), tr("app.busy_body"))
            return
        # Whoever asked for the work must be remembered: it is the only page that cares
        # to know how it ended.
        self._chi_ha_chiesto = self.sender()
        self._progress.setVisible(True)
        self._percent.setVisible(True)
        self._progress.setValue(0)
        self._percent.setText(tr('work.percent', '0'))
        self._status.setText(f"{label} — {tr('app.working')}" if label else tr("app.working"))
        # The step bar stays alive.  Switching it off entirely for the whole duration of a
        # long job — and a model on a real corpus takes minutes — makes the application
        # indistinguishable from a frozen one, and protects against nothing: a second job
        # is already refused above, and each page switches off its own buttons by itself.
        # Whoever is looking must be able to read the results that already exist while the
        # model works.
        self._set_rail_enabled(True)

        self._worker = PipelineWorker(function, *args, **kwargs)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log)
        self._worker.finished_ok.connect(self._on_work_done)
        self._worker.error.connect(self._on_work_error)
        self._worker.start()

    def _set_rail_enabled(self, enabled: bool) -> None:
        for key, button in self._step_buttons.items():
            button.setEnabled(enabled and self._step_available(key))

    @pyqtSlot(int, int, str)
    def _on_progress(self, step: int, total: int, message: str) -> None:
        quota = int(step / total * 100) if total else 0
        self._progress.setValue(quota)
        self._percent.setText(tr("work.percent", number(quota)))
        self._status.setText(message)
        self._log(message)

    @pyqtSlot()
    def _on_work_done(self) -> None:
        self._progress.setVisible(False)
        self._percent.setVisible(False)
        self._status.setText(tr("app.done"))
        self._log(tr("app.done"))
        self._avvisa_chi_ha_chiesto(True, "")
        self._reload_run()

    def _avvisa_chi_ha_chiesto(self, riuscito: bool, messaggio: str) -> None:
        pagina, self._chi_ha_chiesto = getattr(self, "_chi_ha_chiesto", None), None
        if pagina is None:
            return
        try:
            pagina.work_finished(riuscito, messaggio)
        except Exception:                                  # noqa: BLE001
            pass

    @pyqtSlot(str)
    def _on_work_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._percent.setVisible(False)
        self._status.setText(tr("app.error"))
        self._set_rail_enabled(True)
        first_line = message.splitlines()[0] if message else ""
        self._log(tr("app.error_prefix", first_line))
        self._avvisa_chi_ha_chiesto(False, first_line)
        QMessageBox.critical(
            self, tr("app.error"),
            f"{first_line}\n\n{tr('app.error_details')}")

    # ── Loading a run ──────────────────────────────────────────────────
    def _reload_run(self) -> None:
        if not self.state.run_id:
            self._set_rail_enabled(True)
            self._update_rail()
            self._pages["load"].refresh()
            return
        self._status.setText(tr("app.working"))
        # A loader that is still alive is not abandoned: detaching its signals and
        # losing the reference would leave a QThread running with nobody waiting for it,
        # and a QThread destroyed while working aborts the process — that is, the window
        # that disappears without a message.
        vecchio = self._loader
        if vecchio is not None:
            try:
                vecchio.done.disconnect(self._apply_run)
                vecchio.error.disconnect(self._on_work_error)
            except TypeError:
                pass
            if vecchio.isRunning():
                vecchio.wait(5000)
                if vecchio.isRunning():
                    _TRATTIENI.append(vecchio)
        self._loader = RunLoader(self.state.workspace, self.state.run_id, parent=self)
        self._loader.done.connect(self._apply_run)
        self._loader.error.connect(self._on_work_error)
        self._loader.start()

    @pyqtSlot(dict)
    def _apply_run(self, data: dict) -> None:
        if data.get("run_id") != self.state.run_id:
            return

        for name in ("tokens", "findings", "arcs", "corrected_tokens", "token_diff",
                     "lemma_inventory", "spelling_variation"):
            value = data.get(name)
            setattr(self.state, name, value if isinstance(value, pd.DataFrame)
                    else pd.DataFrame())

        self.state.variation = {
            key.replace("variation_", ""): value
            for key, value in data.items()
            if key.startswith("variation_") and isinstance(value, pd.DataFrame)
            and not value.empty
        }
        self.state.stats_before = data.get("stats_before", {}) or {}
        self.state.stats_after = data.get("stats_after", {}) or {}
        self.state.metadata = data.get("metadata", {}) or {}
        self.state.corpus_name = str(self.state.metadata.get("corpus_name", ""))
        self.state.invalidate()

        self._set_rail_enabled(True)
        self._update_rail()
        self._update_badge()
        self._status.setText(tr("app.ready"))

        current = self._stack.currentWidget()
        if current is not None:
            self._aggiorna_pagina(current)
        # After a first load the natural next step is to look at the corpus.
        if current is self._pages["load"] and self.state.has_corpus:
            self._go_to("overview")

    def _aggiorna_pagina(self, pagina) -> None:
        """``refresh()`` of a page, without a fault of its own killing the rest.

        An exception raised inside a Qt slot does not return to the caller: PyQt passes
        it to ``sys.excepthook`` and, with the default hook, calls ``qFatal()``.  A
        secondary view that does not know how to draw a table must not be able to close
        the application, nor leave the page halfway with the bar spinning and the
        buttons switched off.  The fault is recorded, reported, and everything else
        continues.
        """
        try:
            pagina.refresh()
        except Exception as errore:                    # noqa: BLE001
            logging.error("The view '%s' could not be refreshed:\n%s",
                          type(pagina).__name__, traceback.format_exc())
            self._log(tr("app.view_failed", f"{type(errore).__name__}: {errore}"))
            self._status.setText(tr("app.ready"))

    def _update_badge(self) -> None:
        def _stile(nome: str) -> None:
            if self._corpus_badge.objectName() != nome:
                self._corpus_badge.setObjectName(nome)
                self._corpus_badge.style().unpolish(self._corpus_badge)
                self._corpus_badge.style().polish(self._corpus_badge)

        if not self.state.has_corpus:
            _stile("corpusBadgeEmpty")
            self._corpus_badge.setText(tr("app.no_corpus"))
            return
        _stile("corpusBadge")
        # The unit must be named: “token” is none of the five with which the program
        # counts, and whoever reads would not know what they are looking at.
        name = self.state.corpus_name or self.state.run_id or ""
        self._corpus_badge.setText(
            f"{tr('app.corpus')}: {name} · "
            f"{counted('record_importato', len(self.state.tokens))}")

    # ── Log ────────────────────────────────────────────────────────────
    def _toggle_log_view(self) -> None:
        visible = not self._log_view.isVisible()
        self._log_view.setVisible(visible)
        self._toggle_log.setText(tr("app.hide_log") if visible else tr("app.show_log"))

    @pyqtSlot(str)
    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._log_view.append(f"[{stamp}] {message}")
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _thread_vivi(self) -> list:
        """The worker threads still running at this moment."""
        candidati = [self._worker, self._loader]
        for page in self._pages.values():
            candidati.extend(getattr(page, "_async_workers", {}).values())
        vivi = []
        for thread in candidati:
            if thread is None or not hasattr(thread, "isRunning"):
                continue
            try:
                if thread.isRunning():
                    vivi.append(thread)
            except RuntimeError:
                # Already destroyed on the C++ side: there is nothing left to wait for.
                pass
        return vivi

    def closeEvent(self, event) -> None:
        """Closing must never make the process abort.

        A ``QThread`` destroyed while it runs calls ``qFatal()``: the window disappears
        without a message, which is a sudden closure.  ``quit()`` stops the event loop
        of a ``QThread`` and **does nothing** to a ``QThread`` whose ``run()`` is a
        blocking function — such as the run of a model — so it is not enough.

        The procedure: confirmation is asked if a job is in progress; the interruption
        is requested, which the long functions check; the window waits patiently.  If
        after the wait a thread is still inside a call to a native library — UDPipe
        holds the GIL and does not release it — its object is **retained** in a
        module-level list, so that Python does not destroy it, and the window closes
        without aborting.
        """
        vivi = self._thread_vivi()
        # Confirmation is asked only for work that is really lost: a model run, or the
        # import of a corpus.  The computations that the pages perform to fill a table are
        # throwaway, and stopping whoever closes the window to ask them would be merely
        # annoying.
        lungo = self._worker is not None and self._worker in vivi
        if lungo and self.isVisible():
            risposta = QMessageBox.question(
                self, tr("app.closing_title"), tr("app.closing_body"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if risposta != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        for thread in vivi:
            try:
                thread.requestInterruption()
                thread.quit()
            except RuntimeError:
                pass
        self._status.setText(tr("app.closing"))
        for thread in vivi:
            try:
                if thread.isRunning():
                    thread.wait(8000)
                if thread.isRunning():
                    logging.error(
                        "Closing with a thread still inside a native call: "
                        "the object is retained instead of being destroyed "
                        "(%s)", type(thread).__name__)
                    _TRATTIENI.append(thread)
            except RuntimeError:
                pass
        logging.getLogger("gcp.ciclo").info(
            "WINDOW CLOSING · threads still alive: %d",
            len(self._thread_vivi()))
        super().closeEvent(event)
