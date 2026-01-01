"""The look of the application: a palette, and the rules that use it.

Three decisions hold everything that follows.

**Size.**  Every element that can be clicked is large enough to be hit without
aiming: the buttons are 38 pixels tall, the table rows 34, the body text 14.
Density is not a virtue when the reader is squinting at polytonic Greek.

**One identity colour, used sparingly.**  Burgundy marks the thing to press and
nothing else competes with it.  Powder pink — which is burgundy diluted almost
to white — carries the selections and the secondary backgrounds.  Everything
else is warm neutral: about eighty per cent of the surface.  A screen in which
everything is coloured says nothing.

**The identity colour is not the colour of the error.**  Burgundy is the
identity of the program; the red of ``BAD`` says that something is wrong.  They
are two different things and stay two different colours, otherwise every
primary button would look like an alarm.

Greek has a font stack of its own, tried in order, because the default interface
font on Windows draws polytonic accents in inconsistent positions.
"""
from __future__ import annotations

from pathlib import Path

#: Small SVG marks — the tick, the chevron, the sorting arrows.
#:
#: The Qt style sheet language cannot draw a tick, and redrawing a checkbox without
#: supplying one produces a solid square that says nothing about the state.  Five
#: tiny files solve it, and they are referred to by absolute path because a Qt
#: resource bundle would require a compilation step in the installation script,
#: which whoever double-clicks setup.bat must not have to think about.
ASSETS = (Path(__file__).resolve().parent / "assets").as_posix()

# ── The palette ───────────────────────────────────────────────────────
#
# Warm neutrals, and a single identity colour.  The names are imported by half the
# program, so they are stable: the value may change, not the key.

INK = "#252326"          # main text
INK_SOFT = "#4a4448"     # body text, one step below
MUTED = "#716B6E"        # secondary text
LINE = "#E1DADD"         # borders
LINE_STRONG = "#cfc5c9"  # borders of the controls
PAPER = "#F8F7F6"        # general background
CARD = "#FFFFFF"         # cards and tables

#: Burgundy: identity, not alarm.
ACCENT = "#6E2230"
ACCENT_DARK = "#4C1821"
ACCENT_HOVER = "#823342"
#: Powder pink: burgundy diluted almost to white.  Background of the selected item.
ACCENT_SOFT = "#F8F1F3"
#: A pink one step more visible, for the chosen row in a table.
ACCENT_PICK = "#F3E5E9"

# Semantic colours, deliberately far from burgundy.
GOOD = "#47765B"
GOOD_SOFT = "#EAF1EC"
WARN = "#A66B22"
WARN_SOFT = "#FBF2E6"
BAD = "#A33A3A"
BAD_SOFT = "#F9ECEC"
INFO = "#4a6472"
INFO_SOFT = "#EDF2F4"

GREEK_FONT = '"GFS Didot", "Palatino Linotype", "Gentium Plus", "Segoe UI", serif'
MONO_FONT = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'

APP_STYLE = f"""
* {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
    color: {INK};
}}

QMainWindow, QWidget#page {{ background: {PAPER}; }}

/* ── The title bar ──────────────────────────────────────────────── */
/* Light, not a solid band: the burgundy is a thin line at the bottom. */
QWidget#titleBar {{
    background: {CARD};
    border-bottom: 2px solid {ACCENT};
}}
QLabel#appTitle {{ font-size: 19px; font-weight: 700; color: {INK}; }}
QLabel#appVersion {{ font-size: 12px; color: {MUTED}; font-weight: 600; }}
QLabel#appSubtitle {{ color: {MUTED}; font-size: 12.5px; }}
QLabel#corpusBadge {{
    color: {ACCENT_DARK}; background: {ACCENT_SOFT};
    border: 1px solid {LINE}; border-radius: 14px;
    padding: 6px 16px; font-size: 12.5px; font-weight: 600;
}}
QLabel#corpusBadgeEmpty {{
    color: {MUTED}; background: {PAPER};
    border: 1px solid {LINE}; border-radius: 14px;
    padding: 6px 16px; font-size: 12.5px;
}}

/* ── The step rail ──────────────────────────────────────────────── */
QWidget#rail {{ background: {CARD}; border-right: 1px solid {LINE}; }}
QPushButton#stepButton {{
    background: transparent;
    border-top: none; border-right: none; border-bottom: none;
    border-left: 3px solid transparent; border-radius: 0;
    text-align: left; padding: 10px 12px 10px 11px; color: {INK_SOFT};
    font-size: 14px; font-weight: 600;
}}
QPushButton#stepButton:hover  {{ background: {ACCENT_SOFT}; }}
QPushButton#stepButton:checked {{
    background: {ACCENT_SOFT}; color: {ACCENT_DARK};
    border-left: 3px solid {ACCENT};
}}
QPushButton#stepButton:disabled {{ color: #b3aaae; }}
QLabel#stepHint {{ color: {MUTED}; font-size: 11px; }}
QLabel#railHeading {{
    color: {MUTED}; font-size: 10.5px; font-weight: 700;
    letter-spacing: 1.4px; padding: 4px 12px;
}}

/* ── Titles and texts ───────────────────────────────────────────── */
QLabel#pageTitle {{ font-size: 23px; font-weight: 700; color: {INK}; }}
QLabel#pageIntro {{ font-size: 14px; color: {INK_SOFT}; line-height: 170%; }}
QLabel#sectionTitle {{ font-size: 16.5px; font-weight: 700; color: {INK}; }}
/* The small title of a section inside a panel: small, accented, and
   with a burgundy hairline that separates it from what precedes it. */
QLabel#panelSection {{
    font-size: 12.5px; font-weight: 700; color: {ACCENT}; padding: 4px 0 2px 0;
    letter-spacing: 0.4px; border-top: 1px solid {LINE}; margin-top: 4px;
}}
QLabel#hint {{ color: {MUTED}; font-size: 12.5px; }}
QLabel#emptyTitle {{ font-size: 15px; font-weight: 600; color: {INK_SOFT}; }}
QLabel#emptyBody {{ font-size: 13px; color: {MUTED}; }}

QFrame#card {{
    background: {CARD}; border: 1px solid {LINE}; border-radius: 10px;
}}
QFrame#separator {{ background: {LINE}; max-height: 1px; border: none; }}

/* The box “How to read this page”: almost white pink, no visual weight. */
QFrame#howto {{
    background: {ACCENT_SOFT}; border: 1px solid {LINE}; border-radius: 8px;
}}
QLabel#howtoBody {{ color: {INK_SOFT}; font-size: 13px; line-height: 165%; }}

QLabel#noticeInfo {{
    background: {INFO_SOFT}; border-left: 3px solid {INFO};
    border-radius: 6px; padding: 13px 16px; color: #33474f; font-size: 13.5px;
}}
QLabel#noticeGood {{
    background: {GOOD_SOFT}; border-left: 3px solid {GOOD};
    border-radius: 6px; padding: 13px 16px; color: #2f4e3c; font-size: 13.5px;
}}
QLabel#noticeWarn {{
    background: {WARN_SOFT}; border-left: 3px solid {WARN};
    border-radius: 6px; padding: 13px 16px; color: #6d461a; font-size: 13.5px;
}}
QLabel#noticeBad {{
    background: {BAD_SOFT}; border-left: 3px solid {BAD};
    border-radius: 6px; padding: 13px 16px; color: #6f2727; font-size: 13.5px;
}}

/* ── The number cards ───────────────────────────────────────────── */
QFrame#metric {{
    background: {CARD}; border: 1px solid {LINE}; border-radius: 10px;
}}
QLabel#metricValue {{ font-size: 25px; font-weight: 700; color: {ACCENT}; }}
QLabel#metricLabel {{ font-size: 12.5px; color: {MUTED}; }}

/* ── Buttons ────────────────────────────────────────────────────── */
QPushButton {{
    background: {CARD}; border: 1px solid {LINE_STRONG}; border-radius: 7px;
    padding: 8px 18px; min-height: 22px; color: {INK}; font-size: 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT_DARK}; }}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton:disabled {{ color: #b3aaae; border-color: {LINE}; background: #f5f2f3; }}

QPushButton[kind="primary"] {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: white;
    font-weight: 600; padding: 10px 26px;
}}
QPushButton[kind="primary"]:hover {{
    background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; color: white;
}}
QPushButton[kind="primary"]:disabled {{
    background: #ded4d7; border-color: #ded4d7; color: #f6f2f3;
}}

QPushButton[kind="ghost"] {{
    background: transparent; border: none; color: {ACCENT_DARK}; padding: 6px 10px;
}}
QPushButton[kind="ghost"]:hover {{ background: {ACCENT_SOFT}; }}
QPushButton[kind="ghost"]:checked {{ background: {ACCENT_PICK}; }}
/* A disabled control must be seen to be disabled. The generic rule above
   lost against the selector with the attribute, and a “Copy” button that
   could not be pressed looked identical to one that could: whoever pressed
   it concluded that it was broken. */
QPushButton[kind="ghost"]:disabled {{ color: #b3aaae; background: transparent; }}

QPushButton[kind="chip"] {{
    background: {CARD}; border: 1px solid {LINE_STRONG}; border-radius: 15px;
    padding: 6px 14px; font-size: 13px;
}}
QPushButton[kind="chip"]:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
QPushButton[kind="chip"]:disabled {{
    color: #b3aaae; border-color: {LINE}; background: #f5f2f3;
}}

/* ── Fields ─────────────────────────────────────────────────────── */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background: {CARD}; border: 1px solid {LINE_STRONG}; border-radius: 7px;
    padding: 8px 12px; min-height: 22px; selection-background-color: {ACCENT_PICK};
    selection-color: {INK};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit[greek="true"] {{ font-family: {GREEK_FONT}; font-size: 16px; }}
/* The field that filters a table must look like a search box. */
QLineEdit#tableFilter {{
    background: {PAPER}; border-radius: 15px; padding-left: 30px;
    background-image: url({ASSETS}/search.svg);
    background-repeat: no-repeat; background-position: left 10px center;
}}
QLineEdit#tableFilter:focus {{ background-color: {CARD}; border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({ASSETS}/chevron.svg); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {LINE_STRONG};
    selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
    padding: 4px; outline: none;
}}

QCheckBox, QRadioButton {{ spacing: 9px; padding: 4px 0; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 19px; height: 19px; }}
QCheckBox::indicator:unchecked {{
    border: 1.5px solid {LINE_STRONG}; border-radius: 5px; background: {CARD};
}}
QCheckBox::indicator:checked {{
    border: 1.5px solid {ACCENT}; border-radius: 5px; background: {ACCENT};
    image: url({ASSETS}/check.svg);
}}
QCheckBox::indicator:unchecked:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:disabled {{ border-color: {LINE}; background: #f2eef0; }}

QRadioButton::indicator:unchecked {{
    border: 1.5px solid {LINE_STRONG}; border-radius: 10px; background: {CARD};
}}
QRadioButton::indicator:checked {{
    border: 1.5px solid {ACCENT}; border-radius: 10px; background: {ACCENT};
    image: url({ASSETS}/radio.svg);
}}

/* ── Tabs ───────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {LINE}; border-radius: 10px; background: {CARD}; top: -1px;
}}
QTabBar::tab {{
    background: transparent; padding: 10px 18px; margin-right: 4px;
    color: {MUTED}; border: none; border-bottom: 2.5px solid transparent;
    font-size: 13.5px;
}}
QTabBar::tab:selected {{
    color: {ACCENT}; border-bottom-color: {ACCENT}; font-weight: 600;
    background: {ACCENT_SOFT};
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:hover {{ color: {INK}; }}

/* ── Tables ─────────────────────────────────────────────────────── */
QTableView {{
    background: {CARD}; alternate-background-color: #FCFAFB;
    gridline-color: transparent; border: 1px solid {LINE}; border-radius: 10px;
    selection-background-color: {ACCENT_PICK}; selection-color: {INK};
    font-size: 13.5px;
}}
QTableView::item {{ padding: 3px 2px; border-bottom: 1px solid #F1ECEE; }}
QTableView::item:hover {{ background: {ACCENT_SOFT}; }}
QTableView::item:selected {{ background: {ACCENT_PICK}; color: {INK}; }}
QHeaderView::section {{
    background: {PAPER}; color: {INK_SOFT}; border: none;
    border-bottom: 1.5px solid {LINE_STRONG};
    padding: 10px 10px; font-weight: 700; font-size: 12px;
}}
QHeaderView::section:hover {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}
QHeaderView::up-arrow {{ image: url({ASSETS}/sort-up.svg); width: 11px; height: 11px; }}
QHeaderView::down-arrow {{ image: url({ASSETS}/sort-down.svg); width: 11px; height: 11px; }}
QTableView QTableCornerButton::section {{ background: {PAPER}; border: none; }}

QListWidget {{
    background: {CARD}; border: 1px solid {LINE}; border-radius: 10px;
    padding: 4px; outline: none;
}}
QListWidget::item {{ padding: 9px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT_PICK}; color: {INK}; }}
QListWidget::item:hover {{ background: {ACCENT_SOFT}; }}

QTreeView {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 10px; }}

/* ── Scroll bars ────────────────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 13px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cfc5c9; border-radius: 6px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 13px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cfc5c9; border-radius: 6px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QScrollArea {{ border: none; background: transparent; }}

/* ── Progress and log ───────────────────────────────────────────── */
QProgressBar {{
    background: {ACCENT_SOFT}; border: 1px solid {LINE}; border-radius: 6px;
    height: 12px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QLabel#progressText {{ font-size: 12.5px; color: {ACCENT_DARK}; font-weight: 600; }}

QTextEdit#logView {{
    background: {PAPER}; border: 1px solid {LINE}; border-radius: 8px;
    font-family: {MONO_FONT}; font-size: 12px; color: {INK_SOFT};
}}

QGroupBox {{
    border: 1px solid {LINE}; border-radius: 10px; margin-top: 14px;
    padding-top: 14px; background: {CARD}; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {INK_SOFT};
}}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}

QToolTip {{
    background: {INK}; color: #f8f7f6; border: none;
    border-radius: 6px; padding: 8px 11px; font-size: 12.5px;
}}
"""
