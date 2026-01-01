"""Step 6 — searching the corpus: the occurrences first, the analysis after.

The page is built around the two sentences a philologist actually says when
she sits down in front of it: *let me write the word*, and *now tell me what
this one is*.

Three things follow from that, and they are the whole design.

*Writing the word must be forgiving.* ἄνθρωπος, ανθρωπος and anthropos are the
same word. The polytonic keyboard is not installed, the accent is
half-remembered, the word was copied out of a Latin-script bibliography — none
of that is the reader's problem. The folding lives in
:mod:`greek_corpus_pipeline.search`, where both the query and a copy of the
corpus's forms are reduced to one key; the corpus itself is never touched.

*The form and the lemma are two searches, not two filters.* They have a row
each and a button each, and each button reads its own row and nothing else.
Joining them with an implicit AND answers
neither question and silently returns nothing whenever both boxes have
something in them.

*The list comes first, the analysis second.* What comes back is one row per
occurrence with the sentence around it, because that is the list a reader
chooses from. Only when a row is chosen does the right-hand panel fill, and it
holds five things: the morphology, the syntactic function, the lemma, the lemma
of the head, the author. Nothing else: anything more would answer a question
about the file rather than about the word.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSplitter,
    QVBoxLayout, QWidget,
)

from ..i18n import T, data_label, number, tr
from ..style import ACCENT, ACCENT_DARK, ACCENT_SOFT, CARD, LINE, MUTED
from ..widgets import (
    Card, DataTable, LabeledField, ghost_button, greek_line_edit, heading,
    notice, paragraph, primary_button,
)
from ..workers import ResultWorker
from .base import Page


def _mode_box() -> QComboBox:
    """The comparison modes: the word is translated, the value is not.

    ``find_occurrences`` recognises ``"esatto"`` (“exact”), not “exact”: what is read
    and what is searched on must be kept separate, as already for the metadata.
    """
    from greek_corpus_pipeline.search import WORD_MATCH_MODES

    box = QComboBox()
    for mode in WORD_MATCH_MODES:
        box.addItem(tr(f"search.mode.{mode}"), mode)
    box.setFixedWidth(170)
    return box


class SearchPage(Page):

    title_key = "search.title"
    intro_key = "search.intro"

    #: Beyond this number of occurrences the table is filled and no more: the number is
    #: stated, because a list truncated in silence is a lie.
    LIMIT = 25_000

    def build(self) -> None:
        self._worker: ResultWorker | None = None
        #: All the occurrences found, with the columns that the list does not show as
        #: well: the right-hand panel reads from here.
        self._results = pd.DataFrame()
        #: What the status line says, in a form that knows how to restate itself in
        #: another language: the key and its arguments, not the ready-made sentence.
        self._status_key = ""
        self._status_args: tuple = ()
        #: The last search, for the same reason: the line “form exact «λόγος»” can be
        #: restated in English too.
        self._last_query = None

        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        # ── The two searches ───────────────────────────────────────────
        search_card = Card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)

        self._form = greek_line_edit(tr("search.form.placeholder"))
        self._form.returnPressed.connect(self._search_form)
        self._form_mode = _mode_box()
        self._form_field = LabeledField(tr("search.form"), self._form)
        self._form_mode_field = LabeledField(tr("search.mode"), self._form_mode)
        self._form_button = primary_button(tr("search.go_form"))
        self._form_button.clicked.connect(self._search_form)
        grid.addWidget(self._form_field, 0, 0)
        grid.addWidget(self._form_mode_field, 0, 1)
        grid.addWidget(self._form_button, 0, 2, Qt.AlignmentFlag.AlignBottom)

        self._lemma = greek_line_edit(tr("search.lemma.placeholder"))
        self._lemma.returnPressed.connect(self._search_lemma)
        self._lemma_mode = _mode_box()
        self._lemma_field = LabeledField(tr("search.lemma"), self._lemma)
        self._lemma_mode_field = LabeledField(tr("search.mode"), self._lemma_mode)
        self._lemma_button = primary_button(tr("search.go_lemma"))
        self._lemma_button.clicked.connect(self._search_lemma)
        grid.addWidget(self._lemma_field, 1, 0)
        grid.addWidget(self._lemma_mode_field, 1, 1)
        grid.addWidget(self._lemma_button, 1, 2, Qt.AlignmentFlag.AlignBottom)
        search_card.add_layout(grid)

        self._independent = paragraph(tr("search.independent"), "hint")
        search_card.add(self._independent)
        self._typing_hint = paragraph(tr("search.typing_hint"), "hint")
        search_card.add(self._typing_hint)

        actions = QHBoxLayout()
        self._clear_button = ghost_button(tr("search.clear"))
        self._clear_button.clicked.connect(self._clear)
        actions.addWidget(self._clear_button)
        actions.addStretch(1)
        self._query_label = QLabel("")
        self._query_label.setObjectName("hint")
        actions.addWidget(self._query_label)
        search_card.add_layout(actions)
        self.add(search_card)

        # ── The occurrences, and what one of them is ───────────────────
        self._results_card = Card(tr("search.list"))
        self._list_hint = paragraph(tr("search.list_hint"), "hint")
        self._results_card.add(self._list_hint)
        self._status = QLabel("")
        self._status.setObjectName("hint")
        self._results_card.add(self._status)

        self._table = DataTable(min_height=380, column_picker=False)
        self._table.rowSelected.connect(self._show_detail)
        self._detail = _DetailPanel()
        # The panel can be narrowed but not closed: it is the half of the page that
        # answers the question, and a divider dragged by mistake must not be able to
        # make it disappear.
        self._detail.setMinimumWidth(280)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._table)
        splitter.addWidget(self._detail)
        splitter.setSizes([780, 400])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setCollapsible(1, False)
        splitter.setMinimumHeight(440)
        self._results_card.add(splitter, 1)
        self.add(self._results_card, 1)

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        """Rewrites what ``build`` has written once only.

        The two dropdowns are created in the language in which the window was opened and
        would never change by themselves: here they are rewritten keeping the choice
        already made, which is a datum and not a word. The right-hand panel redraws
        itself — morphology and syntactic function are read in two languages — and does
        so with the row that it is already showing.
        """
        for box in (getattr(self, "_form_mode", None),
                    getattr(self, "_lemma_mode", None)):
            if box is None:
                continue
            chosen = box.currentData()
            box.blockSignals(True)
            for index in range(box.count()):
                box.setItemText(index, tr(f"search.mode.{box.itemData(index)}"))
            found = box.findData(chosen)
            if found >= 0:
                box.setCurrentIndex(found)
            box.blockSignals(False)

        self._locked.setText(tr("step.locked"))
        self._form.setPlaceholderText(tr("search.form.placeholder"))
        self._lemma.setPlaceholderText(tr("search.lemma.placeholder"))
        self._form_field.set_label(tr("search.form"))
        self._lemma_field.set_label(tr("search.lemma"))
        self._form_mode_field.set_label(tr("search.mode"))
        self._lemma_mode_field.set_label(tr("search.mode"))
        self._form_button.setText(tr("search.go_form"))
        self._lemma_button.setText(tr("search.go_lemma"))
        self._independent.setText(tr("search.independent"))
        self._typing_hint.setText(tr("search.typing_hint"))
        self._clear_button.setText(tr("search.clear"))
        self._results_card.set_title(tr("search.list"))
        self._list_hint.setText(tr("search.list_hint"))
        # What is already written under the bar: the search made and how many
        # occurrences it gave. They are rewritten on a change of language, otherwise
        # those two lines would stay in the previous language.
        if self._last_query is not None:
            self._query_label.setText(self._last_query.describe())
        self._write_status()
        super().retranslate()

    # ── The line under the search bar ──────────────────────────────────
    def _say(self, key: str, *args) -> None:
        """Remembers what the status line says, and then says it."""
        self._status_key, self._status_args = key, args
        self._write_status()

    def _write_status(self) -> None:
        key, args = self._status_key, self._status_args
        if not key:
            # A message already written — the error of a failed search, which comes from
            # the library and has no key.
            self._status.setText(str(args[0]) if args else "")
            return
        if key == "search.count":
            found = int(args[0])
            shown = number(found)
            message = f"{shown} {tr('search.count')}"
            if found >= self.LIMIT:
                message = f"{message} — {tr('search.capped', shown)}"
            self._status.setText(message)
            return
        self._status.setText(tr(key, *args))

    # ── State ──────────────────────────────────────────────────────────
    def refresh(self) -> None:
        has_corpus = self.state.has_corpus
        self._locked.setVisible(not has_corpus)
        self._form_button.setEnabled(has_corpus)
        self._lemma_button.setEnabled(has_corpus)

    # ── Searching ──────────────────────────────────────────────────────
    def _search_form(self) -> None:
        self._search("forma")

    def _search_lemma(self) -> None:
        self._search("lemma")

    def _search(self, field: str) -> None:
        """Run one search, on one field.

        The other row is not read — not here, not in the query, not in the
        engine. That is the whole of what "independent" means, and it is worth
        being able to point at the line where it is true.
        """
        if not self.state.has_corpus:
            return
        from greek_corpus_pipeline.search import WordQuery, find_occurrences

        edit, mode_box = ((self._form, self._form_mode) if field == "forma"
                          else (self._lemma, self._lemma_mode))
        text = edit.text().strip()
        if not text:
            self._last_query = None
            self._query_label.clear()
            self._say("search.no_criteria")
            return

        query = WordQuery(
            text=text,
            field=field,
            mode=mode_box.currentData() or "esatto",
            context_words=25,
            limit=self.LIMIT,
        )
        self._last_query = query
        self._query_label.setText(query.describe())
        self._say("app.working")
        self._form_button.setEnabled(False)
        self._lemma_button.setEnabled(False)
        self._start(find_occurrences, self.state.tokens, query)

    def _start(self, function, *args) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(200)
        self._worker = ResultWorker(function, *args)
        self._worker.done.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results) -> None:
        from greek_corpus_pipeline.search import LIST_COLUMNS

        self._form_button.setEnabled(True)
        self._lemma_button.setEnabled(True)
        self._detail.clear()
        self._results = results if isinstance(results, pd.DataFrame) else pd.DataFrame()
        if self._results.empty:
            self._say("search.none")
            self._table.set_dataframe(pd.DataFrame())
            return

        self._say("search.count", len(self._results))
        self._table.set_dataframe(self._results[LIST_COLUMNS])
        # The first occurrence is shown at once: the panel exists to be read,
        # and a reader who has just searched for a word wants to see one.
        self._table.select_first()
        # The search bar is tall; without this the results appear below the
        # fold and the program looks as though nothing happened.
        self.scroll.ensureWidgetVisible(self._results_card, 0, 40)

    def _on_error(self, message: str) -> None:
        self._form_button.setEnabled(True)
        self._lemma_button.setEnabled(True)
        first_line = message.splitlines()[0]
        self._say("", first_line)
        self.logMessage.emit(tr("search.failed", first_line))

    # ── The chosen occurrence ──────────────────────────────────────────
    def _show_detail(self, row) -> None:
        """Fill the right-hand panel from the row the reader selected.

        The table is sortable and filterable, so its row numbers are not the
        result set's row numbers; the occurrence number travels with the row
        and is what the lookup uses.
        """
        if row is None or self._results.empty:
            self._detail.clear()
            return
        full = self._full_row(row)
        if full is None:
            self._detail.clear()
            return
        self._detail.show_row(full)

    def _full_row(self, row):
        try:
            number = int(row["n."])
        except (KeyError, TypeError, ValueError):
            return None
        position = number - 1
        if 0 <= position < len(self._results):
            candidate = self._results.iloc[position]
            if int(candidate["n."]) == number:
                return candidate
        matches = self._results[self._results["n."] == number]
        return None if matches.empty else matches.iloc[0]

    def _clear(self) -> None:
        self._form.clear()
        self._lemma.clear()
        self._last_query = None
        self._query_label.clear()
        self._say("")
        self._results = pd.DataFrame()
        self._table.set_dataframe(pd.DataFrame())
        self._detail.clear()


class _FiveThings(QWidget):
    """Field name on the left, value on the right, one row per item.

    Written here instead of reusing ``KeyValueList`` for a single reason: the value
    must wrap. The longest row of all is the morphology of a participle — “verb ·
    third person · plural · aorist · participle · middle · masculine · genitive” —
    and in a narrow panel a label that does not wrap cuts it in half, that is it
    cuts off exactly the thing that one came to read.

    The name of the field stays that of the datum — ``morfologia`` (morphology),
    ``autore`` (author) — and is translated at the moment it is drawn, as the
    headers of the tables do: so the two languages never enter the data.
    """

    #: The fields that carry Greek: Greek is given a typeface drawn for it.
    _GREEK_FIELDS = {"lemma", "lemma della testa"}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(18)
        self._grid.setVerticalSpacing(9)
        self._grid.setColumnStretch(1, 1)

    def set_items(self, items: dict) -> None:
        while self._grid.count():
            widget = self._grid.takeAt(0).widget()
            if widget is not None:
                # Detached at once, destroyed when Qt gets round to it.
                # ``deleteLater`` alone leaves the old label parented and
                # visible until the event loop next runs, and two renderings
                # in the same turn — choosing a row, then changing language —
                # draw the second on top of the first.
                widget.setParent(None)
                widget.deleteLater()
        top = Qt.AlignmentFlag.AlignTop
        for row, (name, value) in enumerate(items.items()):
            caption = QLabel(data_label(name))
            caption.setWordWrap(True)
            caption.setStyleSheet(f"color: {MUTED};")
            shown = QLabel("" if value is None else str(value))
            shown.setWordWrap(True)
            shown.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            if name in self._GREEK_FIELDS:
                shown.setStyleSheet(
                    "font-weight:600; font-size:15px;"
                    "font-family:'GFS Didot','Palatino Linotype',serif;")
            else:
                shown.setStyleSheet("font-weight:600;")
            self._grid.addWidget(caption, row, 0, top)
            self._grid.addWidget(shown, row, 1, top)


class _DetailPanel(QWidget):
    """The right-hand panel: what the chosen word is, in five lines.

    Morphology, syntactic function, lemma, lemma of the head, author. The list
    is closed on purpose — it is the answer to a question about the word, and
    the document, the sentence number and the token number answer a question
    about the file.

    Everything scrolls, for the same reason the findings panel does: a
    morphological gloss of a participle is long, and a panel whose job is to
    show you something cannot be a panel that hides it.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        inner = QWidget()
        inner.setObjectName("page")
        area.setWidget(inner)
        outer.addWidget(area)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 0, 6, 12)
        layout.setSpacing(12)

        self._title = heading(tr("search.detail"))
        self._word = QLabel("")
        self._word.setWordWrap(True)
        self._word.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._word.setStyleSheet(
            f"background:{ACCENT_SOFT}; border:1px solid {LINE};"
            f"border-left:3px solid {ACCENT}; padding:11px 16px;"
            "border-radius:7px; font-family:'GFS Didot','Palatino Linotype',serif;"
            f"font-size:20px; color:{ACCENT_DARK};")
        self._placeholder = paragraph(tr("search.select_row"), "hint")
        self._context_title = heading(tr("search.context"))
        self._context = QLabel("")
        self._context.setWordWrap(True)
        self._context.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._context.setStyleSheet(
            f"background:{CARD}; border:1px solid {LINE};"
            f"border-left:3px solid {ACCENT}; padding:13px 16px;"
            "border-radius:7px; font-family:'GFS Didot','Palatino Linotype',serif;"
            "font-size:15px; line-height:180%;")
        self._values = _FiveThings()

        self._doc_id = QLabel("")
        self._doc_id.setWordWrap(True)
        self._doc_id.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._doc_id.setObjectName("hint")

        layout.addWidget(self._title)
        layout.addWidget(self._placeholder)
        layout.addWidget(self._word)
        layout.addWidget(self._context_title)
        layout.addWidget(self._context)
        layout.addWidget(self._values)
        layout.addWidget(self._doc_id)
        layout.addStretch(1)

        self._row = None
        self._render()

    # ── Data ───────────────────────────────────────────────────────────
    def show_row(self, row) -> None:
        self._row = row
        self._render()

    def clear(self) -> None:
        self._row = None
        self._render()

    def items(self) -> dict:
        """What the panel is showing — it serves the tests and nothing else."""
        from greek_corpus_pipeline.search import detail_of

        if self._row is None:
            return {}
        return detail_of(self._row, T.language)

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        self._title.setText(tr("search.detail"))
        self._placeholder.setText(tr("search.select_row"))
        self._context_title.setText(tr("search.context"))
        # Morphology and syntactic function are read in two languages: the panel redraws
        # itself with the row that it is already showing.
        self._render()

    # ── Internals ──────────────────────────────────────────────────────
    def _render(self) -> None:
        empty = self._row is None
        self._placeholder.setVisible(empty)
        self._word.setVisible(not empty)
        self._values.setVisible(not empty)
        if empty:
            self._word.clear()
            self._context_title.setVisible(False)
            self._context.setVisible(False)
            self._context.clear()
            self._values.set_items({})
            self._doc_id.clear()
            return
        try:
            form = str(self._row["forma"])
        except (KeyError, TypeError):
            form = ""
        self._word.setText(form)
        try:
            context = str(self._row["contesto"]).strip()
        except (KeyError, TypeError):
            context = ""
        has_context = bool(context)
        self._context_title.setVisible(has_context)
        self._context.setVisible(has_context)
        self._context.setText(context if has_context else "")
        self._values.set_items(self.items())
        try:
            doc_id = str(self._row["document_id"]).strip()
        except (KeyError, TypeError):
            doc_id = ""
        self._doc_id.setText(f"document_id: {doc_id}" if doc_id else "")
        self._doc_id.setVisible(bool(doc_id))
