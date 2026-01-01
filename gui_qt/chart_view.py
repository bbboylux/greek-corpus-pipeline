"""A matplotlib figure inside a Qt page, with a save button that works.

Charts are drawn in the analysis layer (``figures.py``), which knows nothing
about Qt; this widget only displays them. That separation is what lets the same
code produce the on-screen chart and the 300 dpi file for the article, with no
risk of the two drifting apart.
"""
from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from .i18n import tr
from .widgets import ghost_button, paragraph
from .style import MUTED


class ChartView(QWidget):
    """One figure, with a caption underneath and save/copy above."""

    def __init__(self, *, min_height: int = 340, parent=None) -> None:
        super().__init__(parent)
        self._figure: Figure | None = None
        self._natural_ratio: float | None = None

        self._canvas = FigureCanvasQTAgg(Figure(figsize=(7, 4), dpi=100))
        self._canvas.setMinimumHeight(min_height)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._save = ghost_button("⤓ " + tr("charts.save"))
        self._save.clicked.connect(self.save)
        self._copy = ghost_button(tr("table.copy"))
        self._copy.clicked.connect(self.copy)
        self._status = QLabel("")
        self._status.setObjectName("hint")

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self._status, 1)
        bar.addWidget(self._copy)
        bar.addWidget(self._save)

        #: What the chart counts, and on which denominator. It sits above the caption and
        #: not inside it: a reader looking at a bar must be able to know in one line
        #: whether they are looking at counts or shares, and of what.
        self._unit = paragraph("", "hint")
        self._unit.setStyleSheet("font-size: 12.5px; font-weight: 600;")
        self._caption = paragraph("", "hint")
        self._caption.setStyleSheet(f"color: {MUTED}; font-size: 12.5px;")

        # The empty state: a chart that cannot be drawn must say so, not leave a blank
        # canvas on the screen — or worse, the previous chart.
        self._empty = QWidget()
        vuoto = QVBoxLayout(self._empty)
        vuoto.setContentsMargins(24, 40, 24, 40)
        vuoto.setSpacing(10)
        # Title and explanation stay together, in the centre: left free they drift apart
        # to the two edges of the frame, and no longer read as a single sentence.
        vuoto.addStretch(1)
        self._empty_title = QLabel("")
        self._empty_title.setObjectName("emptyTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_title.setWordWrap(True)
        self._empty_body = QLabel("")
        self._empty_body.setObjectName("emptyBody")
        self._empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_body.setWordWrap(True)
        vuoto.addWidget(self._empty_title)
        vuoto.addWidget(self._empty_body)
        vuoto.addStretch(1)
        for etichetta in (self._empty_title, self._empty_body):
            etichetta.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Fixed)
        self._empty.setMinimumHeight(min_height)
        self._empty.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(bar)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._empty, 1)
        layout.addWidget(self._unit)
        layout.addWidget(self._caption)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def retranslate(self) -> None:
        """The two buttons above the figure are created once."""
        self._save.setText("⤓ " + tr("charts.save"))
        self._copy.setText(tr("table.copy"))

    #: A chart is never allowed to be shorter than this, nor taller: below the
    #: first number a bar chart of twenty categories is unreadable, above the
    #: second it stops fitting on a screen and the reader has to scroll past it
    #: to reach the caption.
    MIN_CANVAS_HEIGHT = 380
    MAX_CANVAS_HEIGHT = 900

    def show_message(self, title: str, body: str = "") -> None:
        """In place of the chart, the reason why there is none.

        A call to ``set_figure(None, ...)`` replaces the previous chart with this
        message: leaving it on the screen would make whoever has just chosen another
        entry read the numbers of the previous one believing that they were its own.
        """
        self._figure = None
        self._empty_title.setText(title)
        self._empty_body.setText(body)
        self._empty_body.setVisible(bool(body))
        self._canvas.setVisible(False)
        self._empty.setVisible(True)
        self._unit.setText("")
        self._unit.setVisible(False)
        self._caption.setText("")
        self._caption.setVisible(False)
        self._status.setText("")
        self._save.setEnabled(False)
        self._copy.setEnabled(False)

    def set_figure(self, figure: Figure | None, caption: str = "",
                   unit: str = "") -> None:
        if figure is None:
            self.show_message(caption or tr("charts.empty"), unit)
            return
        self._empty.setVisible(False)
        self._canvas.setVisible(True)
        self._save.setEnabled(True)
        self._copy.setEnabled(True)
        self._figure = figure
        old = self._canvas
        self._canvas = FigureCanvasQTAgg(figure)
        # Each chart asks matplotlib for the size it needs — a bar chart of
        # twenty-two rules is taller than one of five families — and that size
        # has to reach Qt, or the canvas keeps the height of the *previous*
        # chart and squashes the new one into it. Squashing a figure whose
        # layout was computed at its natural size cuts the title off the top,
        # which is the symptom this avoids.
        self._natural_ratio = None
        try:
            width_inches, height_inches = figure.get_size_inches()
            if width_inches > 0:
                self._natural_ratio = float(height_inches) / float(width_inches)
        except Exception:                                  # noqa: BLE001
            pass
        self._canvas.setMinimumHeight(self._wanted_height(self.width()))
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = self.layout()
        layout.replaceWidget(old, self._canvas)
        old.setParent(None)
        old.deleteLater()
        self._canvas.draw_idle()
        self._unit.setText(unit)
        self._unit.setVisible(bool(unit))
        self._caption.setText(caption)
        self._caption.setVisible(bool(caption))
        self._status.setText("")

    def wanted_height(self) -> int:
        """The height the current figure would like, at the present width."""
        return self._wanted_height(self.width())

    def _wanted_height(self, width: int) -> int:
        """The height this figure needs at *width*, within the two bounds."""
        ratio = getattr(self, "_natural_ratio", None)
        if not ratio or width <= 0:
            return self.MIN_CANVAS_HEIGHT
        return int(max(self.MIN_CANVAS_HEIGHT,
                       min(self.MAX_CANVAS_HEIGHT, width * ratio)))

    def resizeEvent(self, event) -> None:                  # noqa: N802 (Qt)
        """Keep the figure's proportions as the window is resized."""
        super().resizeEvent(event)
        if getattr(self, "_natural_ratio", None):
            self._canvas.setMinimumHeight(self._wanted_height(self.width()))

    def save(self) -> None:
        # A save that fails must say so where the person who pressed is looking: if the
        # error went only to the console, the status line would keep the previous message
        # and would say that the save succeeded.
        if self._figure is None:
            self._status.setText(tr("charts.nothing_to_save"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("charts.save"), "", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            self._status.setText(tr("table.save_cancelled"))
            return
        if not Path(path).suffix:
            path += ".png"
        try:
            # 300 dpi regardless of what it looks like on screen: a chart saved
            # from here should be usable in print without being redrawn.
            self._figure.savefig(path, dpi=300, bbox_inches="tight",
                                 facecolor="white")
        except Exception as errore:                        # noqa: BLE001
            self._status.setText(tr("table.save_failed", str(errore)))
            return
        self._status.setText(tr("table.saved_to", Path(path).name))

    def copy(self) -> None:
        if self._figure is None:
            self._status.setText(tr("charts.nothing_to_copy"))
            return
        try:
            buffer = self._canvas.buffer_rgba()
            width, height = self._canvas.get_width_height()
            image = QImage(bytes(buffer), width, height,
                           QImage.Format.Format_RGBA8888)
            QGuiApplication.clipboard().setImage(image)
        except Exception as errore:                        # noqa: BLE001
            self._status.setText(tr("table.copy_failed", str(errore)))
            return
        self._status.setText(tr("common.copied"))
