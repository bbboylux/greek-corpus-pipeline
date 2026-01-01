"""The shared shape of a page, and the state every page reads from.

``AppState`` is the single object holding what the program currently knows: the
workspace, the selected corpus, its tokens, its findings, its model comparisons.
Pages never load anything themselves — the main window loads once, on a worker
thread, and hands the result round. That is what keeps a page switch instant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ..i18n import tr
from ..widgets import HowToBox, Scrollable, heading, paragraph


@dataclass
class AppState:
    """Everything currently loaded. Empty frames rather than ``None``.

    Using an empty DataFrame for "not loaded" instead of ``None`` removes a
    whole class of guard clause from every page: ``if frame.empty`` reads the
    same whether nothing was loaded or nothing was found, and both cases want
    the same message.
    """

    workspace: Path
    run_id: str | None = None
    corpus_name: str = ""
    metadata: dict = field(default_factory=dict)

    tokens: pd.DataFrame = field(default_factory=pd.DataFrame)
    findings: pd.DataFrame = field(default_factory=pd.DataFrame)
    arcs: pd.DataFrame = field(default_factory=pd.DataFrame)
    corrected_tokens: pd.DataFrame = field(default_factory=pd.DataFrame)
    token_diff: pd.DataFrame = field(default_factory=pd.DataFrame)
    lemma_inventory: pd.DataFrame = field(default_factory=pd.DataFrame)
    stanza_comparison: pd.DataFrame = field(default_factory=pd.DataFrame)
    udpipe_comparison: pd.DataFrame = field(default_factory=pd.DataFrame)
    spelling_variation: pd.DataFrame = field(default_factory=pd.DataFrame)
    variation: dict[str, pd.DataFrame] = field(default_factory=dict)

    stats_before: dict = field(default_factory=dict)
    stats_after: dict = field(default_factory=dict)


    filter_options: dict = field(default_factory=lambda: {
        "exclude_placeholders": True,
        "exclude_non_greek": False,
        "exclude_punctuation": False,
        "relation_expectation": "corpus",
    })

    # Cached derived tables, computed on demand and reused across page switches.
    cache: dict = field(default_factory=dict)

    @property
    def has_corpus(self) -> bool:
        return not self.tokens.empty

    @property
    def has_findings(self) -> bool:
        return not self.findings.empty

    @property
    def has_models(self) -> bool:
        return not self.stanza_comparison.empty or not self.udpipe_comparison.empty

    def model_surface(self):
        """The text that would be given to a model now: words plus punctuation.

        It is also the text of which the fingerprint is taken, to know whether a saved
        comparison concerns this corpus or another one.
        """
        if self.tokens.empty:
            return self.tokens

        def calcola():
            from greek_corpus_pipeline.model_eval import prepare_model_input
            from ..workers import filter_tokens
            attivi, _ = filter_tokens(self.tokens, self.filter_options)
            return prepare_model_input(attivi)

        return self.cached("model_surface", calcola, self.tokens)

    def model_status(self, label: str, *, versione: str, risorse: str) -> dict:
        """The state of the comparison with a model, for the corpus loaded now.

        Four states and nothing else:

        ``assente``       (absent) no comparison saved for this run
        ``inapplicabile`` (not applicable) there is one, but it was computed on
                          another corpus, another configuration or another model
        ``valido``        (valid) everything matches, and the table is loaded
        ``senza_corpus``  (no corpus) there is no corpus loaded

        An inapplicable comparison is not loaded and is not deleted: it is the
        result of another question, and it stays where it is.
        """
        from greek_corpus_pipeline import __version__
        from greek_corpus_pipeline.model_eval import provenance, provenance_matches
        from greek_corpus_pipeline.storage import (
            artifact_exists, load_dataframe, load_stats_if_present,
        )

        campo = f"{label}_comparison"
        if self.tokens.empty or not self.run_id:
            setattr(self, campo, pd.DataFrame())
            return {"stato": "senza_corpus", "motivo": "", "valutazione": {}}

        # The provenance is read from the folder of the run and not from a copy in
        # memory: the folder is the only thing that really knows what is inside it.
        salvata = load_stats_if_present(
            self.workspace, self.run_id, f"{label}_evaluation")
        if not salvata or not artifact_exists(self.workspace, self.run_id, campo):
            setattr(self, campo, pd.DataFrame())
            return {"stato": "assente", "motivo": "", "valutazione": {}}

        corrente = provenance(
            surface=self.model_surface(), gcp_version=__version__,
            filtri=self.filter_options, modello=label,
            modello_versione=versione, risorse_modello=risorse,
            run_id=self.run_id)
        valido, motivo = provenance_matches(salvata.get("provenienza"), corrente)
        if not valido:
            setattr(self, campo, pd.DataFrame())
            return {"stato": "inapplicabile", "motivo": motivo, "valutazione": salvata}

        setattr(self, campo, load_dataframe(self.workspace, self.run_id, campo))
        return {"stato": "valido", "motivo": "", "valutazione": salvata}

    @property
    def has_both_models(self) -> bool:
        return not self.stanza_comparison.empty and not self.udpipe_comparison.empty

    def group_fields(self) -> list[str]:
        """Metadata columns available for grouping, in the order users expect."""
        preferred = ["autore", "opera", "genere", "periodo", "dialetto",
                     "secolo", "document_id"]
        return [name for name in preferred if name in self.tokens.columns]

    def units(self, frame: pd.DataFrame | None = None):
        """The five canonical units of the loaded corpus, computed once.

        The interface redefines nothing: it asks ``build_units``, which is the only
        definition of the units, and asks it once per corpus.  A page that counted
        its own words would end up saying a different number from that of the run,
        which is exactly the defect that the canonical units exist to remove.

        *frame* is for the pages that work on a subset chosen by the user, for
        example a single author: the units are built on that subset and remain the
        same five.
        """
        base = self.tokens if frame is None else frame
        if base is None or base.empty:
            return None

        def calcola():
            from greek_corpus_pipeline.units import build_units
            from ..workers import filter_tokens
            attivi, _ = filter_tokens(base, self.filter_options)
            return build_units(base, filters=self.filter_options, active=attivi)

        return self.cached(f"units|{len(base)}", calcola, self.tokens)

    def invalidate(self) -> None:
        self.cache.clear()
        # The comparisons with the models hold for a precise corpus and a precise
        # configuration. As soon as either changes they become the result of another
        # question, and what brings them back into play is ``model_status``.
        self.stanza_comparison = pd.DataFrame()
        self.udpipe_comparison = pd.DataFrame()

    def signature(self, *frames: pd.DataFrame) -> tuple:
        """A key that changes exactly when the data a page derives from changes.

        A plain "already computed" flag is the wrong shape: it survives the user
        applying a correction, and the page then shows figures for a corpus that
        no longer exists. Identity plus length plus the run identifier moves the
        moment anything is replaced — the pipeline always hands back new frames —
        and ``invalidate`` still clears everything on a reload.
        """
        return (self.run_id, *((id(frame), len(frame)) for frame in frames))

    def cached(self, name: str, compute, *frames: pd.DataFrame):
        """``compute()``, remembered until the frames it was derived from change."""
        key = self.signature(*frames)
        entry = self.cache.get(name)
        if entry is not None and entry[0] == key:
            return entry[1]
        value = compute()
        self.cache[name] = (key, value)
        return value

    def cache_peek(self, name: str, *frames: pd.DataFrame):
        """The cached value if it is still current, otherwise ``None``."""
        entry = self.cache.get(name)
        if entry is not None and entry[0] == self.signature(*frames):
            return entry[1]
        return None


#: The ``ResultWorker`` instances that are running, kept here until they really finish.
#: It is not a cache: it is the only thing that prevents Python from destroying a QThread
#: while it works, and Qt from aborting the process.
_IN_CORSA: set = set()


def thread_di_pagina_in_corsa() -> int:
    """How many page computations are still running."""
    return sum(1 for w in _IN_CORSA if w.isRunning())


class Page(QWidget):
    """A step of the workflow.

    Subclasses build their interface in ``build`` and refresh it in ``refresh``.
    ``refresh`` may be called many times — on load, on language change, after a
    correction — so it must be idempotent and cheap; anything expensive belongs
    behind an explicit button or in ``state.cache``.
    """

    #: Ask the main window to run something on a worker thread.
    requestWork = pyqtSignal(object, tuple, dict, str)
    #: Ask the main window to jump to another step.
    requestNavigate = pyqtSignal(str)
    #: Write a line to the activity log.
    logMessage = pyqtSignal(str)
    #: Ask the main window to reload the current run from disk.
    requestReload = pyqtSignal()

    title_key = ""
    intro_key = ""
    #: The keys of the long text inside “How to read this page”.
    #:
    #: A page that has more than one sentence to say puts the first in ``intro_key`` and
    #: all the rest here: the box is created closed, and whoever opens the page for the
    #: first time opens it once only.
    howto_keys: tuple[str, ...] = ()

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setObjectName("page")
        #: Background slots, so a superseded result can be recognised and dropped.
        self._async_generation: dict[str, int] = {}
        self._async_workers: dict[tuple, object] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = Scrollable()
        outer.addWidget(self.scroll)

        self._title = heading(tr(self.title_key) if self.title_key else "", "pageTitle")
        self._intro = paragraph(tr(self.intro_key) if self.intro_key else "")
        self.scroll.add(self._title)
        if self.intro_key:
            self.scroll.add(self._intro)
        self._howto: HowToBox | None = None
        if self.howto_keys:
            self._howto = HowToBox(self._howto_body())
            self.scroll.add(self._howto)

        self.build()

    def _howto_body(self) -> str:
        """The text of the box: one paragraph per key, in the order given."""
        pezzi = [tr(chiave) for chiave in self.howto_keys]
        return "".join(f"<p style='margin:0 0 10px 0'>{pezzo}</p>"
                       for pezzo in pezzi if pezzo)

    # ── To be implemented by subclasses ────────────────────────────────
    def build(self) -> None:
        """Create the widgets. Called once."""

    def refresh(self) -> None:
        """Update the widgets from ``self.state``. Called often."""

    # ── Shared helpers ─────────────────────────────────────────────────
    def body(self) -> QVBoxLayout:
        return self.scroll.body()

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        return self.scroll.add(widget, stretch)

    def retranslate(self) -> None:
        """Rewrites what ``build`` has written once only.

        ``refresh`` alone is not enough: it rereads the state, but the captions, the
        titles of the tabs and the labels of the buttons are created with the window and
        would never change. Each page that has them rewrites its own above; tables and
        charts know how to rewrite their own bar by themselves, and for those it is
        enough to ask, instead of keeping the list in every page.
        """
        if self.title_key:
            self._title.setText(tr(self.title_key))
        if self.intro_key:
            self._intro.setText(tr(self.intro_key))
        if self._howto is not None:
            self._howto.retranslate(self._howto_body())
        for child in self.findChildren(QWidget):
            method = getattr(child, "retranslate", None)
            if callable(method):
                try:
                    method()
                except Exception:                     # noqa: BLE001
                    # A widget that does not know how to restate itself must not stop
                    # the others.
                    pass
        # refresh() is NOT called here: it is called by _change_language() on
        # the visible page only, and by _go_to() whenever the user navigates to
        # any page. Calling it for every page on every language change was the
        # source of the multi-second freeze.

    def run_work(self, function, *args, label: str = "", **kwargs) -> None:
        self.requestWork.emit(function, args, kwargs, label)

    def work_finished(self, riuscito: bool, messaggio: str = "") -> None:
        """The work requested with ``run_work`` has finished.

        The window tells the page that asked for it. It is needed because ``run_work``
        starts the work and returns at once: a page must not write “done” on the line
        after it, because the message would be written while the work is still running,
        and would be false whenever the work then fails.
        """

    def compute_in_background(self, slot: str, compute, apply) -> None:
        """Run *compute* off the main thread and hand the result to *apply*.

        ``refresh`` runs on Qt's thread, so a second spent in pandas is a second
        in which the window does not repaint; on Windows that is long enough for
        "Not responding" to appear over it. Anything above half a second belongs
        here: the page draws its structure with a waiting line, and fills in when
        the answer arrives.

        Two things have to be true for that to be safe, and the *slot* name is
        what makes them true. Refreshing twice in quick succession — which the
        rail does whenever the user clicks about — must not leave two threads
        writing into the same widget, so each new request supersedes the previous
        one under the same name. And a result must never be written into a page
        the user has already left, so a superseded or hidden page drops it; the
        value is in ``state.cache`` by then, and coming back is instant.
        """
        generation = self._async_generation.get(slot, 0) + 1
        self._async_generation[slot] = generation
        # Keyed by generation as well as by slot. Keying by slot alone means the
        # older of two overlapping runs removes the *newer* one's reference when
        # it finishes: Python then collects a QThread that is still running, and
        # the result the page was actually waiting for never arrives.
        ticket = (slot, generation)

        def _finished(result, ticket=ticket, slot=slot, generation=generation) -> None:
            self._async_workers.pop(ticket, None)
            if self._async_generation.get(slot) != generation:
                return
            if not self.isVisible():
                return
            apply(result)

        def _failed(message: str, ticket=ticket, slot=slot, generation=generation) -> None:
            self._async_workers.pop(ticket, None)
            if self._async_generation.get(slot) == generation:
                self.logMessage.emit(message.splitlines()[0])

        from ..workers import ResultWorker

        worker = ResultWorker(compute)
        worker.done.connect(_finished)
        worker.error.connect(_failed)
        # Held so that Python does not collect a running QThread.
        self._async_workers[ticket] = worker
        # It is also kept outside the page.  The dictionary above lives as long as the
        # page: if the page is destroyed while the thread works — a window closed and
        # collected, a test run that moves on to the next test — the C++ destructor of
        # a running QThread calls ``qFatal()`` and the process aborts without a message.
        # The module-level registry keeps the reference until the thread has really
        # finished, and releases it by itself.
        _IN_CORSA.add(worker)
        worker.finished.connect(lambda w=worker: _IN_CORSA.discard(w))
        worker.start()
