"""Reusable pieces of interface, built once and used by every page.

The one that matters most is :class:`DataTable`. A table placed into a layout
without a stretch factor collapses to a few rows at the bottom of the window and
cannot be scrolled through comfortably: the user could see the beginning and the
end of a result set but not the middle.
The rules that fix that are enforced here rather than left to each page:

* a table always claims the space it is given (a minimum height and an expanding
  size policy, so a layout cannot squash it);
* the header stays put while the body scrolls, and both scrollbars are always
  reachable;
* columns size themselves to their content up to a sane maximum, and stay
  draggable afterwards;
* the row count, the filter, the column chooser and the CSV export sit on one
  bar above the table, so nothing about a result set is hidden.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QTableView, QVBoxLayout, QWidget,
)

from .df_model import PandasTableModel
from .i18n import counted, data_label, number, tr
from .style import MUTED

GREEK_COLUMNS = {
    "form", "forma", "lemma", "parola", "sinistra", "destra", "nucleo",
    "chiave", "varianti", "etichette", "suggested_lemma", "suggested_form",
    "preposizione", "verbo", "congiunzione", "autore", "opera",
}


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

def heading(text: str, object_name: str = "sectionTitle") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def paragraph(text: str, object_name: str = "pageIntro") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def notice(text: str, kind: str = "info") -> QLabel:
    label = QLabel(text)
    label.setObjectName({"info": "noticeInfo", "good": "noticeGood",
                         "warn": "noticeWarn", "bad": "noticeBad"}.get(kind, "noticeInfo"))
    label.setWordWrap(True)
    return label


class HowToBox(QWidget):
    """The box “How to read this page”, closed until it is needed.

    Long methodological explanations are useful the first time and clutter every
    other time.  Putting them at the top of every page fills the best space with
    text that whoever works has already read; removing them leaves without help
    whoever opens the page for the first time.  A button that opens them solves
    both, and the box is created closed because the normal case is the second.
    """

    def __init__(self, body: str = "", label_key: str = "page.howto",
                 parent=None) -> None:
        super().__init__(parent)
        self._label_key = label_key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._button = ghost_button(tr(label_key))
        self._button.setCheckable(True)
        self._button.toggled.connect(self._toggle)
        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.addWidget(self._button)
        riga.addStretch(1)
        contenitore = QWidget()
        contenitore.setLayout(riga)
        layout.addWidget(contenitore)

        self._box = QFrame()
        self._box.setObjectName("howto")
        interno = QVBoxLayout(self._box)
        interno.setContentsMargins(16, 14, 16, 14)
        self._body = QLabel(body)
        self._body.setObjectName("howtoBody")
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        interno.addWidget(self._body)
        self._box.setVisible(False)
        layout.addWidget(self._box)

    def _toggle(self, aperto: bool) -> None:
        self._box.setVisible(aperto)
        self._button.setText(tr("page.howto.close") if aperto
                             else tr(self._label_key))

    def set_body(self, body: str) -> None:
        self._body.setText(body)

    def retranslate(self, body: str | None = None) -> None:
        if body is not None:
            self._body.setText(body)
        self._button.setText(tr("page.howto.close") if self._button.isChecked()
                             else tr(self._label_key))


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "ghost")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def chip_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "chip")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class Card(QFrame):
    """A white panel with a title, used to group related controls."""

    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(12)
        self._title_label: QLabel | None = None
        if title:
            self._title_label = heading(title)
            self._layout.addWidget(self._title_label)

    def set_title(self, title: str) -> None:
        if self._title_label is not None:
            self._title_label.setText(title)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self._layout.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class MetricGrid(QWidget):
    """A row of headline numbers. Rebuilt wholesale whenever the data changes."""

    def __init__(self, columns: int = 4, parent=None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(10)

    def set_metrics(self, metrics: dict[str, object] | list[tuple[str, object]]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # As in :meth:`KeyValueList.set_items`: ``deleteLater`` postpones the
                # destruction to the next turn of the event loop, and in the meantime
                # the old card stays drawn under the new one. On a change of language
                # the two labels would end up one above the other, unreadable. Hiding it
                # makes it disappear at once.
                widget.hide()
                widget.deleteLater()
        items = list(metrics.items()) if isinstance(metrics, dict) else list(metrics)
        for index, (label, value) in enumerate(items):
            card = QFrame()
            card.setObjectName("metric")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(2)
            shown = number(value) if isinstance(value, int) else (
                "—" if value is None else str(value))
            value_label = QLabel(shown)
            value_label.setObjectName("metricValue")
            name_label = QLabel(data_label(label))
            name_label.setObjectName("metricLabel")
            name_label.setWordWrap(True)
            layout.addWidget(value_label)
            layout.addWidget(name_label)
            self._grid.addWidget(card, index // self._columns, index % self._columns)


class KeyValueList(QWidget):
    """A two-column list of label/value pairs — the shape a report wants."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(7)
        self._grid.setColumnStretch(1, 1)

    def set_items(self, items: dict[str, object]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # ``deleteLater`` postpones the destruction to the next turn of the
                # event loop, and in the meantime the old widget stays drawn under the
                # new one: on a change of language the two labels would end up one above
                # the other. Hiding it makes it disappear at once, and the destruction
                # arrives when it arrives.
                #
                # Not ``setParent(None)``: that turns it into a top-level window owned
                # by Python, and if the reference drops before ``deleteLater`` runs the
                # C++ object is destroyed twice.
                widget.hide()
                widget.deleteLater()
        for row, (label, value) in enumerate(items.items()):
            name = QLabel(data_label(label))
            name.setStyleSheet(f"color: {MUTED};")
            shown = ("—" if value is None
                     else number(value) if isinstance(value, int)
                     else str(value))
            result = QLabel(shown)
            result.setStyleSheet("font-weight: 600;")
            result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(result, row, 1)


class Scrollable(QScrollArea):
    """A vertically scrolling page body. Every page is wrapped in one."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._inner = QWidget()
        self._inner.setObjectName("page")
        self.setWidget(self._inner)
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(28, 24, 28, 28)
        self._layout.setSpacing(18)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self._layout.addWidget(widget, stretch)
        return widget


# ---------------------------------------------------------------------------
# The data table
# ---------------------------------------------------------------------------

class DataTable(QWidget):
    """A pandas DataFrame, shown properly.

    "Properly" means: it fills the space it is given, it scrolls in both
    directions, the header stays visible, columns can be hidden and resized,
    the row count is always on screen, and the whole thing exports to CSV in one
    click. None of that is remarkable, and all of it was missing.
    """

    rowSelected = pyqtSignal(object)      # emits a pandas Series, or None

    #: Beyond this many rows Qt starts to feel sluggish, so the view is capped
    #: and the cap is *stated* — a silently truncated table is a lie.
    MAX_DISPLAY_ROWS = 60_000

    def __init__(
        self,
        *,
        searchable: bool = True,
        exportable: bool = True,
        column_picker: bool = True,
        min_height: int = 260,
        hidden: "set[str] | None" = None,
        labels: "dict[str, str] | None" = None,
        tips: "dict[str, str] | None" = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._full = pd.DataFrame()
        #: The object the caller last handed us, so an identical hand-over is free.
        self._source: pd.DataFrame | None = None
        self._model = PandasTableModel()
        self._hidden: set[str] = set(hidden or ())
        self._model.set_headers(labels, tips)
        self._empty_keys: tuple[str, str] = ("table.empty", "")

        self._search = QLineEdit()
        self._search.setObjectName("tableFilter")
        self._search.setPlaceholderText(tr("table.filter") + "…")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(210)
        self._search.setMaximumWidth(320)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(280)
        self._debounce.timeout.connect(self._apply_filter)
        self._search.textChanged.connect(lambda _: self._debounce.start())

        self._count = QLabel("")
        self._count.setObjectName("hint")

        self._columns_button = ghost_button(tr("table.columns") + " ▾")
        self._columns_button.clicked.connect(self._show_column_menu)
        self._export_button = ghost_button("⤓ " + tr("table.export"))
        self._export_button.clicked.connect(self.export_csv)
        self._copy_button = ghost_button(tr("table.copy"))
        self._copy_button.clicked.connect(self.copy_to_clipboard)
        # Copying and saving must not finish without saying anything: whoever pressed
        # would be left looking at an identical screen, with no way of knowing whether
        # they had succeeded.
        self._esito = QLabel("")
        self._esito.setObjectName("hint")

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)
        if searchable:
            bar.addWidget(self._search)
        bar.addWidget(self._count)
        bar.addStretch(1)
        bar.addWidget(self._esito)
        if column_picker:
            bar.addWidget(self._columns_button)
        bar.addWidget(self._copy_button)
        if exportable:
            bar.addWidget(self._export_button)

        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setSortingEnabled(True)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._view.setWordWrap(False)
        self._view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._view.setCornerButtonEnabled(False)

        header = self._view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setMinimumSectionSize(52)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        vertical = self._view.verticalHeader()
        vertical.setDefaultSectionSize(34)
        vertical.setVisible(False)

        # The two lines that keep a table from being squashed into a strip.
        self._view.setMinimumHeight(min_height)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # An empty table that shows an empty grid says nothing. In its place a line
        # appears saying what is missing, and when a computation is in progress a bar
        # saying so.
        self._empty = QWidget()
        vuoto = QVBoxLayout(self._empty)
        vuoto.setContentsMargins(24, 34, 24, 34)
        vuoto.setSpacing(8)
        self._empty_title = QLabel(tr("table.empty"))
        self._empty_title.setObjectName("emptyTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_body = QLabel("")
        self._empty_body.setObjectName("emptyBody")
        self._empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_body.setWordWrap(True)
        self._empty_bar = QProgressBar()
        self._empty_bar.setRange(0, 0)          # indeterminate: it is working
        self._empty_bar.setFixedWidth(240)
        self._empty_bar.setVisible(False)
        vuoto.addWidget(self._empty_title)
        vuoto.addWidget(self._empty_body)
        riga_barra = QHBoxLayout()
        riga_barra.addStretch(1)
        riga_barra.addWidget(self._empty_bar)
        riga_barra.addStretch(1)
        vuoto.addLayout(riga_barra)
        self._empty.setMinimumHeight(min_height)
        self._empty.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(bar)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._empty, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._view.selectionModel().selectionChanged.connect(self._emit_selection)
        # A newly built table has not yet received a frame, and without this it would
        # show an empty grid instead of saying that there is nothing.
        self._aggiorna_vuoto()
        self._mostra_vuoto(True)
        self._aggiorna_comandi(0, 0)

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        """Rewrites the bar above the table when the language changes.

        Filter, count, choice of columns, copy and export are created once, together
        with the table, and without this they would stay in the language in which the
        window was opened — on every table of the program, which is the place where a
        leftover language is most noticeable.
        """
        self._search.setPlaceholderText(tr("table.filter") + "…")
        self._columns_button.setText(tr("table.columns") + " ▾")
        self._export_button.setText("⤓ " + tr("table.export"))
        self._copy_button.setText(tr("table.copy"))
        if self._empty.isVisible() and not self._empty_bar.isVisible():
            self._aggiorna_vuoto()
        # The count carries the words “righe” and “di” (“rows” and “of”), and the
        # headers are field names translated by the model: redrawing what is already on
        # the screen rewrites both, without losing the filter.
        self._apply_filter()

    # ── Data ───────────────────────────────────────────────────────────
    def set_dataframe(self, frame: pd.DataFrame | None, *, keep_filter: bool = False) -> None:
        if not keep_filter:
            self._search.blockSignals(True)
            self._search.clear()
            self._search.blockSignals(False)
        # Handed the very same object again — which is what a second visit to a
        # page does, now that the pages cache what they derive — there is nothing
        # to redraw. It is worth testing for: Qt samples a thousand rows of every
        # column to size it, and on the findings table that is 131,072 calls back
        # into the model, half a second the user spends looking at a frozen window
        # for a table that already says the right thing.
        if frame is not None and frame is self._source and not self._search.text().strip():
            return
        self._source = frame
        self._full = (frame.reset_index(drop=True)
                      if frame is not None else pd.DataFrame())
        self._show(self._full)
        self._autosize()

    def set_empty_text(self, title_key: str, body_key: str = "") -> None:
        """What to say when the table has no rows.

        The **keys** are passed, not the sentences: the empty state is interface text
        like everything else and must change with the language, and a sentence already
        translated at construction time would remain in the language in which the window
        was opened.
        """
        self._empty_keys = (title_key, body_key)
        if self._full.empty and not self._empty_bar.isVisible():
            self._aggiorna_vuoto()

    def _aggiorna_vuoto(self) -> None:
        titolo_chiave, corpo_chiave = self._empty_keys
        titolo = tr(titolo_chiave) if titolo_chiave else tr("table.empty")
        corpo = tr(corpo_chiave) if corpo_chiave else ""
        self._empty_title.setText(titolo)
        self._empty_body.setText(corpo)
        self._empty_body.setVisible(bool(corpo))

    def _mostra_vuoto(self, mostra: bool) -> None:
        self._view.setVisible(not mostra)
        self._empty.setVisible(mostra)

    def show_waiting(self, message: str) -> None:
        """Empty the table and say why, while the answer is computed elsewhere."""
        self._source = None
        self._full = pd.DataFrame()
        self._model.setDataFrame(pd.DataFrame())
        self._count.setText(message)
        self._empty_title.setText(message)
        self._empty_body.setText("")
        self._empty_body.setVisible(False)
        self._empty_bar.setVisible(True)
        self._mostra_vuoto(True)

    def dataframe(self) -> pd.DataFrame:
        return self._full

    def visible_dataframe(self) -> pd.DataFrame:
        return self._model.dataFrame()

    def set_boolean_highlight(self, enabled: bool = True) -> None:
        self._model.setHighlightBooleans(enabled)

    def set_highlight_pairs(self, pairs: list[tuple[str, str]]) -> None:
        """Colour both cells in each column pair when their values differ."""
        self._model.setHighlightPairs(pairs)

    def selected_row(self) -> pd.Series | None:
        """The chosen row, with all its columns.

        The model shows the visible columns, and a row read from there would lose
        everything else: the identifier of the document, that of the sentence, that of
        the token, the rule that produced the finding. Whoever opened a finding would
        then see the form alone in place of the sentence, and no explanation. The hidden
        columns stay here.
        """
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.rowAt(indexes[0].row())

    def select_first(self) -> None:
        if self._model.rowCount():
            self._view.selectRow(0)

    def select_row(self, indice: int) -> None:
        """Chooses the *index* row of the view, if there is one."""
        if 0 <= indice < self._model.rowCount():
            self._view.selectRow(indice)

    # ── Internals ──────────────────────────────────────────────────────
    def _show(self, frame: pd.DataFrame) -> None:
        # The hidden columns stay in the model and are hidden by the view. Removing them
        # earlier would make them disappear from the row that the table hands to whoever
        # selects it, and the right-hand panel would find itself without the identifier
        # of the sentence, without the rule and without the proposal. Hiding them here
        # costs nothing and keeps them together with the row even after sorting.
        capped = frame.iloc[: self.MAX_DISPLAY_ROWS]
        self._model.setDataFrame(capped)
        self._nascondi_colonne(capped)
        self._apply_greek_font(capped)

        total = len(self._full)
        visible = len(frame)
        displayed = len(capped)
        vuota = visible == 0
        self._empty_bar.setVisible(False)
        if vuota and total:
            # There is data, but the filter lets nothing through: it is something other
            # than having no data, and it must be said.
            self._empty_title.setText(tr("table.no_match"))
            self._empty_body.setText(tr("table.no_match.hint"))
            self._empty_body.setVisible(True)
        else:
            self._aggiorna_vuoto()
        self._mostra_vuoto(vuota)
        self._aggiorna_comandi(visible, total)
        if total == 0:
            self._count.setText(tr("table.empty"))
        elif displayed < visible:
            self._count.setText(
                f"{tr('table.capped')} {number(displayed)} {tr('table.of')} "
                f"{number(visible)}")
        elif visible < total:
            self._count.setText(
                f"{number(visible)} {tr('table.of')} {counted('riga', total)}")
        else:
            self._count.setText(counted("riga", total))

    def _aggiorna_comandi(self, righe_visibili: int, righe_in_tutto: int = 0) -> None:
        """Copy, columns and export make sense only with rows.

        They stay disabled when there are none: enabled, on an empty table they would
        respond to a click by returning at once, without a file, without a message,
        without anything: from outside that is indistinguishable from a broken button.

        The three conditions are different, and must be kept different. “Copy” takes the
        rows that are seen, so it is switched off also when the filter lets none
        through; “Save as CSV” and the choice of columns work on the whole table, and
        stay enabled as long as the table has rows, filter or no filter.
        """
        c_e_da_copiare = righe_visibili > 0
        c_e_una_tabella = righe_in_tutto > 0
        self._copy_button.setEnabled(c_e_da_copiare)
        self._copy_button.setToolTip(
            "" if c_e_da_copiare
            else tr("table.no_match" if c_e_una_tabella else "table.nothing_to_do"))
        for bottone in (self._export_button, self._columns_button):
            bottone.setEnabled(c_e_una_tabella)
            bottone.setToolTip("" if c_e_una_tabella else tr("table.nothing_to_do"))
        if not c_e_una_tabella:
            self._esito.setText("")

    def _di_esito(self, chiave: str, *argomenti) -> None:
        self._esito.setText(tr(chiave, *argomenti))

    def _apply_greek_font(self, frame: pd.DataFrame) -> None:
        """Polytonic Greek gets a serif face; everything else stays as it is."""
        greek = QFont()
        greek.setFamilies(["GFS Didot", "Palatino Linotype", "Gentium Plus", "Segoe UI"])
        greek.setPointSizeF(11.5)
        columns = {str(name).lower() for name in frame.columns} & GREEK_COLUMNS
        self._model.setGreekColumns(
            {index for index, name in enumerate(frame.columns)
             if str(name).lower() in columns}, greek)

    def _apply_filter(self) -> None:
        needle = self._search.text().strip()
        if not needle or self._full.empty:
            self._show(self._full)
            return
        mask = pd.Series(False, index=self._full.index)
        for column in self._full.columns:
            try:
                mask |= (self._full[column].astype("string").fillna("")
                         .str.contains(needle, case=False, regex=False))
            except Exception:
                continue
        self._show(self._full[mask.fillna(False)].reset_index(drop=True))

    def _autosize(self) -> None:
        self._view.resizeColumnsToContents()
        header = self._view.horizontalHeader()
        for index in range(header.count()):
            width = header.sectionSize(index)
            header.resizeSection(index, max(70, min(width + 18, 380)))

    def _nascondi_colonne(self, frame: pd.DataFrame) -> None:
        """The service columns are not seen, but stay in the row."""
        for indice, nome in enumerate(frame.columns):
            self._view.setColumnHidden(
                indice, nome in self._hidden or str(nome).startswith("_"))

    def _show_column_menu(self) -> None:
        if self._full.empty:
            return
        menu = QMenu(self)
        for column in self._full.columns:
            if str(column).startswith("_"):
                continue
            action = QAction(data_label(column), menu)
            action.setCheckable(True)
            action.setChecked(column not in self._hidden)
            action.toggled.connect(
                lambda checked, name=column: self._toggle_column(name, checked))
            menu.addAction(action)
        menu.exec(self._columns_button.mapToGlobal(
            self._columns_button.rect().bottomLeft()))

    def _toggle_column(self, column: object, visible: bool) -> None:
        if visible:
            self._hidden.discard(column)
        else:
            self._hidden.add(column)
        self._apply_filter()
        self._autosize()

    def _emit_selection(self) -> None:
        self.rowSelected.emit(self.selected_row())

    # ── Output ─────────────────────────────────────────────────────────
    def set_headers(self, labels: "dict[str, str] | None" = None,
                    tips: "dict[str, str] | None" = None) -> None:
        """Headers and explanations specific to this table.

        The ``retranslate`` of the page calls them, because they are interface text like
        everything else and must change with the language.
        """
        self._model.set_headers(labels, tips)

    def _intestazioni_tradotte(self, frame: pd.DataFrame) -> pd.DataFrame:
        """The frame with the headers in the language of the interface.

        The data stays what it is: only the names of the columns change, and they change
        because an exported file is read by a person, not by the program. Whoever has
        the interface in English must not find a sheet with Italian headers.
        """
        rinomina = {colonna: self._model.header_label(colonna)
                    for colonna in frame.columns}
        # If two different columns fell on the same label the sheet would become
        # ambiguous, and then it is better to leave them as they are.
        if len(set(rinomina.values())) != len(rinomina):
            return frame
        return frame.rename(columns=rinomina)

    def export_csv(self, title: str = "") -> str | None:
        if self._full.empty:
            self._di_esito("table.nothing_to_save")
            return None
        path, _ = QFileDialog.getSaveFileName(
            self, title or tr("table.export"), "", "CSV (*.csv)")
        if not path:
            self._di_esito("table.save_cancelled")
            return None
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            # utf-8-sig so that Excel opens Greek correctly without being told to.
            self._intestazioni_tradotte(self._full).to_csv(
                path, index=False, encoding="utf-8-sig")
        except Exception as errore:
            self._di_esito("table.save_failed", str(errore))
            return None
        self._di_esito("table.saved_to", Path(path).name)
        return path

    def copy_to_clipboard(self) -> None:
        frame = self.visible_dataframe()
        if frame.empty:
            self._di_esito("table.nothing_to_copy")
            return
        try:
            QGuiApplication.clipboard().setText(
                self._intestazioni_tradotte(frame).to_csv(sep="\t", index=False))
        except Exception as errore:
            self._di_esito("table.copy_failed", str(errore))
            return
        self._di_esito("table.copied", number(len(frame)))


class LabeledField(QWidget):
    """A caption above a control — the layout that reads best in a form."""

    def __init__(self, label: str, widget: QWidget, hint: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        caption = QLabel(label)
        caption.setStyleSheet(f"color: {MUTED}; font-size: 12.5px; font-weight: 600;")
        layout.addWidget(caption)
        layout.addWidget(widget)
        self._caption = caption
        self._note = None
        if hint:
            note = QLabel(hint)
            note.setObjectName("hint")
            note.setWordWrap(True)
            layout.addWidget(note)
            self._note = note
        self.widget = widget

    def set_label(self, label: str, hint: str = "") -> None:
        """Rewrites the caption when the language changes.

        Without this the label above a control would stay the one with which the field
        was built, and changing language would translate the dropdown but not the word
        above it.
        """
        self._caption.setText(label)
        if hint and self._note is not None:
            self._note.setText(hint)


def combo(items: list[str], *, current: str = "", width: int = 0) -> QComboBox:
    box = QComboBox()
    box.addItems(items)
    if current and current in items:
        box.setCurrentText(current)
    if width:
        box.setFixedWidth(width)
    return box


class GreekLineEdit(QLineEdit):
    """QLineEdit with Perseus keyboard (Beta Code → polytonic Greek).

    The ASCII keys a–z / A–Z are converted into the corresponding Greek letter according
    to the Beta Code encoding of the Perseus Project. The diacritic keys (/ \\ = ) ( +
    |) combine with the preceding character via Unicode NFC and produce the correct
    precomposed character.

    Whoever already uses a hardware polytonic keyboard is not affected: its code points
    are > 127 and do not fall into either of the two tables.
    """

    # Beta Code → Greek letter (lower and upper case)
    _LETTERS: dict[str, str] = {
        'a': 'α', 'b': 'β', 'g': 'γ', 'd': 'δ', 'e': 'ε', 'z': 'ζ', 'h': 'η',
        'q': 'θ', 'i': 'ι', 'j': 'ς', 'k': 'κ', 'l': 'λ', 'm': 'μ', 'n': 'ν',
        'c': 'ξ', 'o': 'ο', 'p': 'π', 'r': 'ρ', 's': 'σ', 't': 'τ', 'u': 'υ',
        'f': 'φ', 'x': 'χ', 'y': 'ψ', 'w': 'ω',
        'A': 'Α', 'B': 'Β', 'G': 'Γ', 'D': 'Δ', 'E': 'Ε', 'Z': 'Ζ', 'H': 'Η',
        'Q': 'Θ', 'I': 'Ι', 'J': 'Σ', 'K': 'Κ', 'L': 'Λ', 'M': 'Μ', 'N': 'Ν',
        'C': 'Ξ', 'O': 'Ο', 'P': 'Π', 'R': 'Ρ', 'S': 'Σ', 'T': 'Τ', 'U': 'Υ',
        'F': 'Φ', 'X': 'Χ', 'Y': 'Ψ', 'W': 'Ω',
    }

    # Perseus diacritics → combining Unicode
    _COMBINING: dict[str, str] = {
        '/':  '́',  # acute / oxia
        '\\': '̀',  # grave / varia
        '=':  '͂',  # circumflex / perispomeni
        ')':  '̓',  # smooth breathing / psili
        '(':  '̔',  # rough breathing / dasia
        '+':  '̈',  # diaeresis / dialytika
        '|':  'ͅ',  # iota subscript / ypogegrammeni
    }

    def keyPressEvent(self, event) -> None:
        text = event.text()
        if not text:
            super().keyPressEvent(event)
            return

        # ── Letter: replaced by the corresponding Greek letter ────────────
        if text in self._LETTERS:
            greek = self._LETTERS[text]
            if self.hasSelectedText():
                start = self.selectionStart()
                end = start + len(self.selectedText())
                full = self.text()
                self.setText(full[:start] + greek + full[end:])
                self.setCursorPosition(start + len(greek))
            else:
                pos = self.cursorPosition()
                full = self.text()
                self.setText(full[:pos] + greek + full[pos:])
                self.setCursorPosition(pos + len(greek))
            return

        # ── Diacritic: combines with the preceding character ──────────────
        if text in self._COMBINING:
            combining = self._COMBINING[text]
            pos = self.cursorPosition()
            full = self.text()
            if pos > 0:
                prev = full[pos - 1]
                composed = unicodedata.normalize(
                    'NFC', unicodedata.normalize('NFD', prev) + combining)
                self.setText(full[:pos - 1] + composed + full[pos:])
                self.setCursorPosition(pos - 1 + len(composed))
            return

        # Everything else (Unicode, Ctrl+…, space, digits…) passes through unchanged,
        # including direct input from a hardware polytonic keyboard.
        super().keyPressEvent(event)


def greek_line_edit(placeholder: str = "") -> GreekLineEdit:
    field = GreekLineEdit()
    field.setProperty("greek", "true")
    field.setPlaceholderText(placeholder)
    field.setClearButtonEnabled(True)
    return field
