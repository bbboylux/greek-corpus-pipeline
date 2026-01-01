"""PandasTableModel — the bridge between a DataFrame and a QTableView.

Read-only, deliberately. Editing a cell would give the impression that the
corpus is being changed in place, and the whole design rests on the opposite
promise: the original is never touched, corrections live in their own file.

Three display behaviours are worth naming.

*Booleans render as ✓ / ✗ / —* on a coloured ground, because a column of
``True``/``False`` is unreadable at a glance and correctness columns are read at
a glance or not at all. The dash is not "false": it means the question did not
apply to this token, which is a third state and must look like one.

*Greek columns get a serif face.* The default Windows UI font places polytonic
accents inconsistently; a text column of Greek deserves a face that was drawn
for it.

*Sorting happens in the model, on the DataFrame.* A proxy model would have to
compare rendered strings, which puts 10 before 9.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont

from .i18n import data_label, tr, value_label

#: The separator with which ``variation`` builds composite keys.
SEPARATORE = "\u241f"


class PandasTableModel(QAbstractTableModel):

    _NA_COLOR = QColor("#f6f3ef")
    _TRUE_COLOR = QColor("#e6f1de")
    _FALSE_COLOR = QColor("#fbe4e4")
    _BOOL_NA_COLOR = QColor("#ececec")
    _DIFF_COLOR = QColor("#ffe4b3")   # amber — marks a value that differs from its pair

    _TRUE_TEXT = "✓"
    _FALSE_TEXT = "✗"
    _NA_TEXT = "—"

    _SEVERITY_COLORS = {
        "errore": QColor("#fbecec"),
        "sospetto": QColor("#fdf4e3"),
    }

    def __init__(self, frame: pd.DataFrame | None = None, parent=None,
                 highlight_booleans: bool = False) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame = pd.DataFrame() if frame is None else frame.reset_index(drop=True)
        self._highlight_booleans = highlight_booleans
        self._bool_columns: set[int] = set()
        self._greek_columns: set[int] = set()
        self._greek_font: QFont | None = None
        self._severity_column: int | None = None
        self._values: list = []
        self._missing: list = []
        self._row_count = 0
        self._column_count = 0
        self._highlight_pairs_names: list[tuple[str, str]] = []
        #: Headers and explanations for this table only, indexed on the name of the datum.
        #: They are needed where five tables share the names of the columns but not their
        #: meaning: in the lemma plane the column ``etichette`` (“labels”) contains lemmas,
        #: and calling it “labels” would be false. The name of the datum does not change —
        #: filters, sorting and export use it — only what is read changes.
        self._labels: dict[str, str] = {}
        self._tips: dict[str, str] = {}
        self._pair_map: dict[int, int] = {}   # column_index → paired column_index
        self._scan()

    # ── Public API ─────────────────────────────────────────────────────
    def setDataFrame(self, frame: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = frame.reset_index(drop=True)
        self._scan()
        self.endResetModel()

    def setHighlightBooleans(self, enabled: bool) -> None:
        if enabled == self._highlight_booleans:
            return
        self.beginResetModel()
        self._highlight_booleans = enabled
        self._scan()
        self.endResetModel()

    def setGreekColumns(self, columns: set[int], font: QFont) -> None:
        self.beginResetModel()
        self._greek_columns = set(columns)
        self._greek_font = font
        self.endResetModel()

    def setHighlightPairs(self, pairs: list[tuple[str, str]]) -> None:
        """Highlight both cells in a column pair when their values differ.

        *pairs* is a list of (col_a, col_b) column-name tuples.  When the value
        in col_a differs from the value in col_b on the same row, both cells are
        shown with a distinct background (_DIFF_COLOR).  Useful for comparing
        a reference annotation against a model's output.
        """
        self.beginResetModel()
        self._highlight_pairs_names = list(pairs)
        self._scan()
        self.endResetModel()

    def dataFrame(self) -> pd.DataFrame:
        return self._df

    def rowAt(self, row: int) -> pd.Series | None:
        if 0 <= row < len(self._df):
            return self._df.iloc[row]
        return None

    # ── Internals ──────────────────────────────────────────────────────
    #: The columns whose content is not a datum of the corpus but a key of the program,
    #: and which are therefore read translated on screen. The datum does not change:
    #: the filter, the sorting and the export continue to see the key.
    COLONNE_DI_CHIAVI = frozenset({"direzione", "tipo", "categoria", "ragione"})

    def _scan(self) -> None:
        self._bool_columns = set()
        self._value_columns = {
            indice for indice, nome in enumerate(map(str, self._df.columns))
            if nome in self.COLONNE_DI_CHIAVI}
        self._severity_column = None
        # Each column is kept as a plain array so that ``data`` can read a cell
        # with a list index instead of ``DataFrame.iat``.
        #
        # This is the single most expensive thing the window did. Qt asks the
        # model for every cell of the first thousand rows of each column when it
        # autosizes a table, and it autosizes on every ``set_dataframe``: the
        # error page alone fills nine tables, which is 131,072 calls to ``data``.
        # Through pandas' scalar indexing each one would cost some forty
        # microseconds on the Arrow-backed string columns this program uses, most
        # of the time that page takes to refresh. Reading the same cell out of a
        # numpy array costs about a microsecond, and the value handed back is the
        # identical object, so nothing on screen changes.
        self._values = [self._df.iloc[:, index].to_numpy()
                        for index in range(len(self._df.columns))]
        # "Is this cell missing" is asked four times per cell, once per role, and
        # ``pd.isna`` on a scalar is a dispatch through pandas, again on every
        # refresh of the error page. Answered for the whole column at once where that is
        # defined — a column holding lists or sets is left to the per-cell test,
        # which is what the ``except`` below is for.
        # Qt asks for the bounds on every single ``data`` call; going through
        # ``DataFrame.__len__`` and ``Index.__len__`` 887,205 times per error-page
        # refresh cost more than reading the cells did.
        self._row_count = len(self._df)
        self._column_count = len(self._df.columns)
        self._missing = []
        for values in self._values:
            try:
                flags = pd.isna(values)
                self._missing.append(flags if flags.dtype == bool else None)
            except (TypeError, ValueError):
                self._missing.append(None)
        if self._df.empty:
            return
        for index, column in enumerate(self._df.columns):
            if str(column).lower() in ("severity", "gravità", "gravita"):
                self._severity_column = index
            if not self._highlight_booleans:
                continue
            series = self._df[column]
            try:
                if pd.api.types.is_bool_dtype(series.dtype):
                    self._bool_columns.add(index)
                    continue
                if series.dtype == object:
                    values = series.dropna().unique()
                    if len(values) and all(isinstance(value, bool) for value in values):
                        self._bool_columns.add(index)
            except Exception:
                continue
        # Build a fast col-index → paired-col-index lookup for diff highlighting.
        self._pair_map = {}
        cols = list(self._df.columns)
        for (a_name, b_name) in self._highlight_pairs_names:
            if a_name in cols and b_name in cols:
                a, b = cols.index(a_name), cols.index(b_name)
                self._pair_map[a] = b
                self._pair_map[b] = a

    # ── QAbstractTableModel ────────────────────────────────────────────
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._row_count

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._column_count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        if row >= self._row_count or column >= self._column_count:
            return None
        value = self._values[column][row]
        is_boolean = column in self._bool_columns
        flags = self._missing[column]
        if flags is not None:
            missing = bool(flags[row])
        else:
            try:
                missing = pd.isna(value)
            except (TypeError, ValueError):
                missing = False

        if role == Qt.ItemDataRole.DisplayRole:
            if is_boolean:
                return self._NA_TEXT if missing else (
                    self._TRUE_TEXT if bool(value) else self._FALSE_TEXT)
            if missing:
                return ""
            if isinstance(value, float):
                return f"{value:g}"
            if isinstance(value, str) and SEPARATORE in value:
                # The internal separator with which the program builds composite keys is
                # not a datum of the corpus: it is an implementation detail, and says
                # nothing to the reader.
                return value.replace(SEPARATORE, " · ")
            if column in self._value_columns:
                # Some columns do not contain a datum of the corpus but a key of the
                # program — “dipendente” (dependent), “testa” (head) — and a key is read
                # translated. The datum stays what it is: only the label changes.
                return value_label(value)
            return str(value)

        if role == Qt.ItemDataRole.FontRole and column in self._greek_columns:
            return self._greek_font

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if is_boolean:
                return int(Qt.AlignmentFlag.AlignCenter)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.BackgroundRole:
            if is_boolean:
                if missing:
                    return self._BOOL_NA_COLOR
                return self._TRUE_COLOR if bool(value) else self._FALSE_COLOR
            if column in self._pair_map:
                partner = self._pair_map[column]
                if partner < self._column_count:
                    partner_val = self._values[partner][row]
                    if str(value) != str(partner_val):
                        return self._DIFF_COLOR
            if self._severity_column is not None:
                severity = self._values[self._severity_column][row]
                colour = self._SEVERITY_COLORS.get(str(severity))
                if colour is not None:
                    return colour
            if missing:
                return self._NA_COLOR

        if role == Qt.ItemDataRole.ToolTipRole:
            if is_boolean:
                if missing:
                    return tr("common.not_applicable")
                return tr("table.true") if bool(value) else tr("table.false")
            if not missing:
                text = str(value)
                # Long cells are elided in the view; the tooltip is where the
                # rest of a sentence or a rule explanation actually lives.
                if len(text) > 40:
                    return text
        return None

    def set_headers(self, labels: "dict[str, str] | None" = None,
                    tips: "dict[str, str] | None" = None) -> None:
        """Headers and explanations specific to this table."""
        self._labels = dict(labels or {})
        self._tips = dict(tips or {})
        if self._column_count:
            self.headerDataChanged.emit(
                Qt.Orientation.Horizontal, 0, self._column_count - 1)

    def header_label(self, name: object) -> str:
        """What is read in the header, for the given datum name."""
        proprio = self._labels.get(str(name))
        if proprio:
            return proprio
        shown = data_label(name)
        return shown if shown != str(name) else shown.replace("_", " ")

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            return str(section + 1)
        if section >= self._column_count:
            return "" if role == Qt.ItemDataRole.DisplayRole else None
        name = self._df.columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            # The name of the column stays that of the datum — filters, sorting and
            # export use it — and only what is read is translated here.
            return self.header_label(name)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tips.get(str(name)) or None
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if self._df.empty or column >= self._column_count:
            return
        self.beginResetModel()
        name = self._df.columns[column]
        try:
            self._df = self._df.sort_values(
                name, ascending=order == Qt.SortOrder.AscendingOrder,
                na_position="last", kind="stable").reset_index(drop=True)
        except Exception:
            pass
        # The cached column arrays belong to the old row order.
        self._scan()
        self.endResetModel()
