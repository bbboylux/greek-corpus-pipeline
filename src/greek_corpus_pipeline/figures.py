"""Every chart the program can draw, and the export of all of them at once.

Matplotlib only — no interactive plotting stack, nothing to install beyond what
the setup script already fetches, and every figure saveable at 300 dpi for a
journal.

Two rules govern the look of these charts, and both come from the fact that the
audience is philologists rather than statisticians.

*The reader must never have to decode the picture.* Bars are labelled with their
values, axes say what they measure in words, and the caption of every figure is
generated together with the figure so that an exported PNG can be dropped into
an article and still be intelligible.

*Colour never carries the meaning by itself.* One colour for a single series;
a diverging scale only where the data really is diverging (agreement above and
below a midpoint); a sequential scale for counts. Where several series share
one pair of axes each of them also gets its own hatch, so the figure survives a
black-and-white printer and a reader who does not separate reds. No colour of
the palette stands for a judgement: bordeaux is not "worse" and rose is not
"better" — what a series is, its legend and its caption say.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # no display server in a worker thread

import matplotlib.pyplot as plt
import textwrap as _textwrap

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------

# The same colours as the interface: burgundy, powder pink, warm neutrals.
#
# None of these colours means anything on its own. Whoever looks at a figure must not
# infer anything from the fact that one series is burgundy and another pink: burgundy is
# not “worse” and pink is not “better”. The colour separates the series, the legend
# names them, and the caption says what they are. The categories, their order and their
# values do not depend on this.
#
# For the same reason colour is never the only sign that distinguishes one series from
# another: every series also gets a hatching of its own. A figure printed in black and
# white, or seen by someone who does not separate reds well, remains legible.

INK = "#252326"
MUTED = "#716B6E"
GRID = "#E1DADD"
PAPER = "#F8F7F6"

BORDEAUX = "#6E2230"
BORDEAUX_DARK = "#4C1821"
ROSE = "#B97886"
ROSE_LIGHT = "#D8AEB7"
GREY_WARM = "#716B6E"
GREY_MID = "#A29A9D"

ACCENT = BORDEAUX               # a single series
ACCENT_LIGHT = ROSE
ANNOTATION = GREY_WARM          # medians, references: they are not a series

# The order alternates light and dark and alternates colour family, so two series that
# are neighbours in the legend are never two shades of the same colour.
SERIES_COLORS = [BORDEAUX, ROSE, GREY_WARM, ROSE_LIGHT, BORDEAUX_DARK, GREY_MID]
SERIES_HATCHES = ["", "//", ".", "\\\\", "x", "--"]

SEQUENTIAL = LinearSegmentedColormap.from_list(
    "gcp_sequential",
    ["#F8F7F6", "#EBD7DC", "#D8AEB7", "#B97886", "#8E4152", "#6E2230", "#4C1821"])
# The two directions are distinguished by colour family before intensity: pink on one
# side, neutrals on the other. Whoever does not separate reds still sees “coloured” on
# one side and “grey” on the other, and in any case the matrix carries the number
# written inside the cell.
DIVERGING = LinearSegmentedColormap.from_list(
    "gcp_diverging",
    ["#4C1821", "#8E4152", "#C68E9B", "#F1EDEE", "#BDB6B9", "#8A8285", "#4A4448"])


def _serie_colore(indice: int) -> str:
    return SERIES_COLORS[indice % len(SERIES_COLORS)]


def _serie_tratteggio(indice: int) -> str:
    return SERIES_HATCHES[indice % len(SERIES_HATCHES)]


def _luminanza(colore) -> float:
    """Relative luminance according to WCAG, to decide what is legible on top."""
    canali = []
    for canale in matplotlib.colors.to_rgb(colore):
        canali.append(canale / 12.92 if canale <= 0.04045
                      else ((canale + 0.055) / 1.055) ** 2.4)
    rosso, verde, blu = canali
    return 0.2126 * rosso + 0.7152 * verde + 0.0722 * blu


def _testo_su(colore) -> str:
    """The text written inside a bar or a cell must remain legible."""
    return "white" if _luminanza(colore) < 0.18 else INK


def _bordo_su(colore) -> str:
    """The colour of the hatching: the same as the series, lightened or darkened.

    Pure white over the burgundy would make the hatching the most conspicuous thing in
    the figure, and the bars would become a wall of texture. Mixed a little over half
    way towards the light (or towards the ink, over light tones) the pattern is visible,
    stays visible even printed in black and white, and does not cover the number written
    inside the bar.
    """
    verso = ((1.0, 1.0, 1.0) if _luminanza(colore) < 0.30
             else matplotlib.colors.to_rgb(INK))
    base = matplotlib.colors.to_rgb(colore)
    return matplotlib.colors.to_hex(
        tuple(canale + (meta - canale) * 0.55 for canale, meta in zip(base, verso)))


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.labelsize": 10,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "hatch.linewidth": 0.6,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "font.size": 10,
        "figure.autolayout": False,
    })


apply_style()


def _new_figure(width: float = 8.0, height: float = 4.6) -> tuple[Figure, plt.Axes]:
    """A figure that leaves room for what is written inside it.

    ``layout="constrained"`` measures the real labels before deciding the margins, and
    the labels of this program are long: a check name, an ancient author, a relation
    with its suffix. With fixed margins the first letter of every row would end up
    outside the figure, and whoever looked would read half a word.
    """
    figure = Figure(figsize=(width, height), dpi=110, layout="constrained")
    axes = figure.add_subplot(111)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    return figure, axes


# ---------------------------------------------------------------------------
# Network layout (Fruchterman-Reingold, pure numpy — no networkx required)
# ---------------------------------------------------------------------------

def _t(key: str, fallback: str, *args: object) -> str:
    """The text of a title or a label, in the language of the interface.

    The figures are drawn here and shown in the window, and titles written by
    hand would stay in Italian even with the interface in English. The strings
    live where all the others live — in ``gui_qt.i18n`` — and this function is
    the only point at which this module goes to fetch them: *fallback* is
    Italian, and applies when the interface is not available, because ``figures``
    must keep working on its own (from the command line, or imported as a
    library).
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:                                    # key missing
        return fallback.format(*args) if args else fallback
    return text


def _value(value: object) -> str:
    """A category value as it reads inside a chart."""
    try:
        from gui_qt.i18n import value_label                # noqa: PLC0415
    except Exception:                                      # noqa: BLE001
        return str(value)
    return value_label(value)


def _values(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """A copy with *column* translated, for the axis and for the legend.

    The data stay as they are: the comparisons that the code makes on that column — “the
    two models against the corpus”, the totals that begin with TOTALE — continue to see
    Italian.
    """
    if frame is None or frame.empty or column not in frame.columns:
        return frame
    return frame.assign(**{column: frame[column].map(_value)})


def _lingua() -> str:
    """The language of the interface, “it” when there is no interface.

    It serves the names that are not in ``i18n`` but in the catalogue of checks, where
    every entry carries its own ``name`` and ``name_en``.
    """
    try:
        from gui_qt.i18n import T                      # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return "it"
    return getattr(T, "language", "it")


def _group_name(group: str) -> str:
    """The name of a metadata column as it reads to whoever looks at the chart.

    In the data the column is called ``periodo`` even with the interface in English; on
    the axis of a chart it must say “period”.
    """
    return _t("group." + str(group), str(group))


def _label(pair) -> str:
    """Italian or English, from a pair already declared in the catalogue.

    The names of the families and of the diagnostic classes travel in the catalogue as
    ``(Italian, English)`` pairs: they must be taken from the pair according to the
    language of the interface, not always from the first.
    """
    if not isinstance(pair, (tuple, list)) or len(pair) < 2:
        return str(pair)
    try:
        from gui_qt.i18n import pick                   # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return str(pair[0])
    return pick(pair)


def caption(name: str) -> str:
    """The caption of a figure, in the language of the interface."""
    return _t("figcap." + name, CAPTIONS.get(name, ""))


def _empty(message: str = "") -> Figure:
    figure, axes = _new_figure(6, 3)
    message = message or _t("table.empty", "Nothing to show yet")
    axes.axis("off")
    axes.text(0.5, 0.5, message, ha="center", va="center",
              color=MUTED, fontsize=12, transform=axes.transAxes)
    return figure


def _shorten(label: object, limit: int = 26) -> str:
    """Shorten a label without throwing away the part that identifies it.

    Cutting the tail is the obvious thing and it is wrong for this program's
    rule names, because a whole family of them shares a prefix and differs only
    at the end: "Possible PoS–relation mismatch (καί)" and the same for
    μέν, τε, ἤ. Tail-cut at twenty-six characters they all become "Possible
    PoS–relation mis…", and a chart of the most frequent rules turns into six
    identical rows. When the distinguishing part is a parenthesis at the end,
    the ellipsis goes in the middle and the parenthesis survives.
    """
    text = " ".join(str(label).split())
    if len(text) <= limit:
        return text
    # Wrapped, not cut. Cutting a line makes disappear precisely the part that
    # distinguishes one check from another, and on a chart there is no way to
    # recover it: the line becomes illegible and the chart useless.
    righe = _textwrap.wrap(text, width=max(12, limit), max_lines=3,
                           placeholder="…", break_long_words=False)
    return "\n".join(righe) if righe else text


# ---------------------------------------------------------------------------
# Basic chart types
# ---------------------------------------------------------------------------

def _numero(valore: float, formato: str) -> str:
    """A number with its thousands separator as the interface language writes it:
    72.836 in Italian, 72,836 in English."""
    testo = formato.format(valore)
    if "," in formato and _lingua() == "it":
        testo = testo.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return testo


def bar_chart(
    frame: pd.DataFrame,
    label_column: str,
    value_column: str,
    *,
    title: str = "",
    xlabel: str = "",
    top: int = 20,
    horizontal: bool = True,
    color: str = ACCENT,
    value_format: str = "{:,.0f}",
) -> Figure:
    """One series of counts. Values are printed on the bars, always."""
    if frame is None or frame.empty or label_column not in frame.columns:
        return _empty()
    data = frame.head(top).copy()
    labels = [_shorten(value, 34) for value in data[label_column]]
    values = pd.to_numeric(data[value_column], errors="coerce").fillna(0).to_numpy()

    # The tallest bar and the widest figure are decided by the longest label, not by a
    # fixed number: a check name on three lines needs three lines of space, and a wide
    # column of labels needs a wide figure. With fixed measures the words would come out
    # of the frame.
    righe_per_etichetta = max((etichetta.count("\n") + 1) for etichetta in labels) if labels else 1
    larghezza_etichetta = max((len(riga) for etichetta in labels
                               for riga in etichetta.split("\n")), default=0)
    if horizontal:
        height = max(2.8, 0.34 * righe_per_etichetta * len(labels) + 1.6)
        width = min(13.0, max(8.6, 4.6 + 0.11 * larghezza_etichetta))
    else:
        height = max(4.6, 4.2 + 0.22 * righe_per_etichetta)
        width = min(13.0, max(8.6, 0.62 * len(labels) + 3.0))
    figure, axes = _new_figure(width, height)

    if horizontal:
        positions = np.arange(len(labels))[::-1]
        axes.barh(positions, values, color=color, height=0.68)
        axes.set_yticks(positions)
        axes.set_yticklabels(labels)
        axes.set_xlabel(xlabel or value_column)
        axes.grid(axis="y", visible=False)
        span = values.max() if len(values) and values.max() else 1
        for position, value in zip(positions, values):
            axes.text(value + span * 0.012, position, _numero(value, value_format),
                      va="center", fontsize=8.5, color=MUTED)
        axes.set_xlim(0, span * 1.16)
    else:
        positions = np.arange(len(labels))
        axes.bar(positions, values, color=color, width=0.68)
        axes.set_xticks(positions)
        axes.set_xticklabels(labels, rotation=35, ha="right")
        axes.set_ylabel(xlabel or value_column)
        axes.grid(axis="x", visible=False)
        span = values.max() if len(values) and values.max() else 1
        for position, value in zip(positions, values):
            axes.text(position, value + span * 0.02, _numero(value, value_format),
                      ha="center", fontsize=8.5, color=MUTED)

    if title:
        axes.set_title(title, loc="left", pad=12)
    return figure


def grouped_bar_chart(
    frame: pd.DataFrame,
    label_column: str,
    value_columns: list[str],
    *,
    title: str = "",
    ylabel: str = "",
    top: int = 12,
) -> Figure:
    """Several series side by side — models compared, periods compared."""
    if frame is None or frame.empty or label_column not in frame.columns:
        return _empty()
    columns = [column for column in value_columns if column in frame.columns]
    if not columns:
        return _empty()
    data = frame.head(top)
    labels = [_shorten(value, 18) for value in data[label_column]]

    figure, axes = _new_figure(max(8.0, 0.9 * len(labels) + 2.5), 4.8)
    positions = np.arange(len(labels))
    width = 0.8 / len(columns)
    for index, column in enumerate(columns):
        values = pd.to_numeric(data[column], errors="coerce").fillna(0).to_numpy()
        offset = (index - (len(columns) - 1) / 2) * width
        colore = _serie_colore(index)
        axes.bar(positions + offset, values, width=width * 0.92,
                 label=column, color=colore,
                 hatch=_serie_tratteggio(index),
                 edgecolor=_bordo_su(colore), linewidth=0.55)
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, rotation=30, ha="right")
    axes.set_ylabel(ylabel)
    axes.grid(axis="x", visible=False)
    axes.legend(ncol=min(len(columns), 3), loc="upper right")
    if title:
        axes.set_title(title, loc="left", pad=12)
    return figure


def heatmap(
    matrix: pd.DataFrame,
    *,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    diverging: bool = False,
    centre: float = 50.0,
    annotate: bool = True,
    value_format: str = "{:.0f}",
    colorbar_label: str = "",
) -> Figure:
    """A matrix as colour. Cells are annotated whenever the grid is small enough.

    Used for confusion matrices (gold against a source, or one model against
    another) and for agreement matrices by author and feature. When *diverging*
    is set the palette is centred on *centre*, so "better than the midpoint"
    and "worse" read as different directions rather than as different shades.
    """
    if matrix is None or matrix.empty:
        return _empty()
    data = matrix.copy()
    if data.columns.size and not np.issubdtype(data.dtypes.iloc[0], np.number):
        data = data.set_index(data.columns[0])
    numeric = data.apply(pd.to_numeric, errors="coerce")

    rows, columns = numeric.shape
    figure, axes = _new_figure(
        min(16, max(6.0, 0.62 * columns + 3.0)),
        min(14, max(3.4, 0.42 * rows + 2.0)))

    if diverging:
        extent = max(abs(numeric.to_numpy(dtype=float) - centre).max(), 1e-6)
        image = axes.imshow(numeric, cmap=DIVERGING, aspect="auto",
                            vmin=centre - extent, vmax=centre + extent)
    else:
        image = axes.imshow(numeric, cmap=SEQUENTIAL, aspect="auto")

    axes.set_xticks(np.arange(columns))
    axes.set_xticklabels([_shorten(value, 16) for value in numeric.columns],
                         rotation=35, ha="right")
    axes.set_yticks(np.arange(rows))
    axes.set_yticklabels([_shorten(value, 24) for value in numeric.index])
    axes.grid(False)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)

    if annotate and rows * columns <= 400:
        values = numeric.to_numpy(dtype=float)
        for row in range(rows):
            for column in range(columns):
                value = values[row, column]
                if not np.isfinite(value):
                    continue
                shade = _testo_su(image.cmap(image.norm(value)))
                axes.text(column, row, value_format.format(value),
                          ha="center", va="center", fontsize=7.6, color=shade)

    bar = figure.colorbar(image, ax=axes, fraction=0.03, pad=0.02)
    if colorbar_label:
        bar.set_label(colorbar_label, fontsize=9, color=MUTED)
    bar.outline.set_visible(False)
    if title:
        axes.set_title(title, loc="left", pad=12)
    return figure


def histogram(
    values: pd.Series,
    *,
    bins: int = 40,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    clip_quantile: float = 0.99,
) -> Figure:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if series.empty:
        return _empty()
    # Sentence length and dependency distance both have very long right tails;
    # showing them raw compresses the informative part into two pixels.
    upper = series.quantile(clip_quantile)
    clipped = series[series <= upper]
    figure, axes = _new_figure(8.0, 4.2)
    axes.hist(clipped, bins=bins, color=ACCENT, edgecolor="white", linewidth=0.6)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel or _t("fig.axis.sentences", "sentences"))
    axes.grid(axis="x", visible=False)
    median = float(series.median())
    axes.axvline(median, color=ANNOTATION, linestyle="--", linewidth=1.4)
    axes.text(median, axes.get_ylim()[1] * 0.94,
              "  " + _t("fig.median", "median {0}", f"{median:.0f}"),
              color=ANNOTATION, fontsize=9)
    if title:
        axes.set_title(title, loc="left", pad=12)
    return figure


def grouped_distribution_chart(
    table: pd.DataFrame,
    group: str,
    category_column: str,
    value_column: str,
    *,
    title: str = "",
    top_categories: int = 12,
    top_groups: int = 12,
) -> Figure:
    """The same distribution, split by author, work, period — as percentages.

    Raw counts cannot be compared across groups of different size: a corpus
    with one author of 300,000 tokens and one of 8,000 shows the first
    everywhere and the second nowhere, and the reader learns only which author
    is longer. Every value here is therefore a share of its own group's total,
    computed before any category is dropped, so the shares of the groups stay
    honest even when the tail is not drawn.

    Few groups and few categories read best as bars side by side. Past that the
    same numbers go into a heat map: thirty bars in six colours is not a chart
    anybody reads, while a matrix of the same thirty cells is.
    """
    if table is None or table.empty:
        return _empty(_t("charts.no_data_for_group", "No data for this grouping"))
    needed = {group, category_column, value_column}
    if not needed <= set(table.columns):
        return _empty()

    pivot = table.pivot_table(index=group, columns=category_column,
                              values=value_column, aggfunc="sum", fill_value=0)
    if pivot.empty:
        return _empty()

    # Shares first, truncation second: dropping the tail before dividing would
    # inflate every remaining percentage and silently rescale each group by a
    # different factor.
    totals = pivot.sum(axis=1)
    shares = pivot.div(totals.where(totals > 0, 1), axis=0) * 100
    shares = shares.loc[totals.sort_values(ascending=False).index[:top_groups]]
    order = shares.sum(axis=0).sort_values(ascending=False).index[:top_categories]
    shares = shares[order]
    if shares.empty:
        return _empty()

    groups = [_shorten(value, 18) for value in shares.index]
    categories = [_shorten(value, 18) for value in shares.columns]

    if len(groups) <= 6 and len(categories) <= 10:
        figure, axes = _new_figure(max(8.4, 1.05 * len(categories) + 2.6), 4.9)
        positions = np.arange(len(categories))
        width = 0.8 / len(groups)
        for index, name in enumerate(groups):
            values = shares.iloc[index].to_numpy(dtype=float)
            offset = (index - (len(groups) - 1) / 2) * width
            colore = _serie_colore(index)
            axes.bar(positions + offset, values, width=width * 0.92, label=name,
                     color=colore, hatch=_serie_tratteggio(index),
                     edgecolor=_bordo_su(colore), linewidth=0.55)
        axes.set_xticks(positions)
        axes.set_xticklabels(categories, rotation=30, ha="right")
        axes.set_ylabel(_t("fig.axis.own_share", "% of its own {0}",
                           _group_name(group)))
        axes.grid(axis="x", visible=False)
        # Underneath, not on top of the bars: at "upper right" the legend of a
        # four-series chart covers the tallest category, which is the one the
        # reader came for.
        axes.legend(ncol=min(len(groups), 4), loc="upper center",
                    bbox_to_anchor=(0.5, -0.22), title=_group_name(group),
                    fontsize=8.5, title_fontsize=8.5)
        if title:
            axes.set_title(title, loc="left", pad=12)
        return figure

    matrix = shares.copy()
    matrix.index = groups
    matrix.columns = categories
    return heatmap(matrix, title=title, xlabel=_group_name(category_column),
                   ylabel=_group_name(group),
                   annotate=len(groups) * len(categories) <= 200,
                   value_format="{:.1f}",
                   colorbar_label=_t("fig.axis.own_share", "% of its own {0}",
                                     _group_name(group)))


# ---------------------------------------------------------------------------
# Named figures built directly from analysis output
# ---------------------------------------------------------------------------

def findings_by_family(findings: pd.DataFrame) -> Figure:
    """How many findings each family of rules produced."""
    if findings is None or findings.empty or "rule_id" not in findings.columns:
        return _empty(_t("fig.empty.no_findings_yet",
                      "No findings: run the check first"))
    from .rule_catalog import FAMILY_LABELS, rule_family

    families = findings["rule_id"].map(rule_family).map(
        lambda key: _label(FAMILY_LABELS.get(key, (key, key))))
    table = families.value_counts().reset_index()
    table.columns = ["famiglia", "segnalazioni"]
    return bar_chart(table, "famiglia", "segnalazioni",
                     title=_t("fig.title.family",
                              "Findings by family of check"),
                     xlabel=_t("fig.axis.findings_count", "number of findings"))


def findings_by_class(findings: pd.DataFrame) -> Figure:
    """The five diagnostic levels, from mechanical slip to open question."""
    if findings is None or findings.empty or "rule_id" not in findings.columns:
        return _empty(_t("fig.empty.no_findings", "No findings"))
    from .rule_catalog import CLASS_LABELS, CLASS_ORDER, rule_class

    classes = findings["rule_id"].map(rule_class).map(
        lambda key: _label(CLASS_LABELS.get(key, (key, key))))
    table = classes.value_counts().reindex(
        [_label(CLASS_LABELS[key]) for key in CLASS_ORDER]).dropna().reset_index()
    table.columns = ["classe", "segnalazioni"]
    return bar_chart(table, "classe", "segnalazioni",
                     title=_t("fig.title.class", "Findings by diagnostic class"),
                     xlabel=_t("fig.axis.findings_count", "number of findings"),
                     horizontal=False)


def findings_by_rule(findings: pd.DataFrame, top: int = 22) -> Figure:
    if findings is None or findings.empty:
        return _empty(_t("fig.empty.no_findings", "No findings"))
    # The name of the check is derived here from the rule, in the language of the
    # moment, and not read from the column “anomaly_name”, which is created when the
    # table of findings is computed: after switching to English the chart would keep
    # showing the names in Italian.
    from .rule_catalog import rule_name
    lingua = _lingua()
    table = findings["rule_id"].value_counts().head(top).reset_index()
    table.columns = ["regola", "segnalazioni"]
    table["regola"] = table["regola"].map(lambda rule: rule_name(str(rule), lingua))
    return bar_chart(table, "regola", "segnalazioni",
                     title=_t("fig.title.rule", "The {0} checks that report most", top),
                     xlabel=_t("fig.axis.findings_count", "number of findings"),
                     top=top)


def findings_density_by_document(findings: pd.DataFrame, tokens: pd.DataFrame,
                                 top: int = 20) -> Figure:
    """Findings per 10,000 active records, document by document.

    The rate is the one the run declares, on the same unit and with the same
    factor: changing either of the two here would mean showing a number that is
    not the one of the backend. *tokens* must be the **active records**.

    The normalisation is needed: without it, the ranking measures the length of
    the texts.
    """
    if findings is None or findings.empty or tokens is None or tokens.empty:
        return _empty(_t("fig.empty.no_findings", "No findings"))
    sizes = tokens.groupby("document_id", sort=False).size().rename("token")
    counts = findings.groupby("document_id", sort=False).size().rename("segnalazioni")
    table = pd.concat([counts, sizes], axis=1).dropna()
    table = table[table["token"] >= 200].reset_index()
    if table.empty:
        return _empty()
    table["per 10.000"] = (table["segnalazioni"] / table["token"] * 10000).round(1)
    table = table.sort_values("per 10.000", ascending=False)
    return bar_chart(table, "document_id", "per 10.000",
                     title=_t("fig.title.density", "Anomaly density by document"),
                     xlabel=_t("fig.axis.per_ten_thousand",
                               "findings per 10,000 active records"), top=top,
                     value_format="{:,.1f}")


def slot_distribution_chart(table: pd.DataFrame, title: str) -> Figure:
    if table is None or table.empty:
        return _empty()
    column = "categoria" if "categoria" in table.columns else table.columns[0]
    return bar_chart(table, column, "occorrenze", title=title,
                     xlabel=_t("fig.axis.occurrences", "occurrences"), top=16)


def profile_comparison_chart(profile: pd.DataFrame, group: str,
                             metrics: list[str]) -> Figure:
    available = [metric for metric in metrics if metric in profile.columns]
    if profile is None or profile.empty or not available:
        return _empty()
    return grouped_bar_chart(profile, group, available,
                             title=_t("fig.title.profile_by",
                                      "Morphological profile by {0}",
                                      _group_name(group)),
                             ylabel=_t("fig.axis.ratio", "ratio"))


def agreement_heatmap(per_slot: pd.DataFrame) -> Figure:
    """Agreement on each of the nine tag slots, as one strip of colour."""
    if per_slot is None or per_slot.empty:
        return _empty(_t("fig.empty.run_models", "Run the models first"))
    frame = per_slot.set_index("tratto")[["% accordo"]].T
    return heatmap(frame.reset_index(),
                   title=_t("fig.title.slot_agreement",
                            "Agreement by position of the tag"),
                   diverging=True, centre=90.0, value_format="{:.1f}",
                   colorbar_label=_t("fig.axis.agreement_share", "% agreement"))


def model_agreement_heatmap(table: pd.DataFrame, group: str = "autore") -> Figure:
    """Corpus↔Stanza, corpus↔UDPipe and Stanza↔UDPipe agreement, per author."""
    if table is None or table.empty:
        return _empty(_t("fig.empty.run_both",
                      "Run Stanza and UDPipe to see this chart"))
    columns = [column for column in table.columns if column.startswith("%")]
    if not columns or group not in table.columns:
        return _empty()
    frame = table.set_index(group)[columns]
    return heatmap(frame.reset_index(),
                   title=_t("fig.title.model_agreement",
                            "Agreement between corpus and models"),
                   diverging=True, centre=float(frame.to_numpy().mean()),
                   value_format="{:.1f}",
                   colorbar_label=_t("fig.axis.agreement_share", "% agreement"),
                   ylabel=_group_name(group))


def three_way_chart(summary: pd.DataFrame) -> Figure:
    if summary is None or summary.empty:
        return _empty(_t("fig.empty.run_both",
                      "Run Stanza and UDPipe to see this chart"))
    data = _values(summary[summary["esito"] != "TOTALE allineati"], "esito")
    return bar_chart(data, "esito", "%",
                     title=_t("fig.title.three_way",
                              "Corpus, Stanza and UDPipe on the same words"),
                     xlabel=_t("fig.axis.aligned_share", "% of the aligned words"),
                     value_format="{:.1f}%")


def noise_replication_chart(table: pd.DataFrame) -> Figure:
    if table is None or table.empty:
        return _empty(_t("fig.empty.need_analysis",
                      "The analysis and at least one model are needed"))
    data = _values(table[~table["esito"].str.startswith("TOTALE")], "esito")
    model = _value(table.attrs.get("modello", _t("fig.the_model", "the model")))
    return bar_chart(data, "esito", "%",
                     title=_t("fig.title.noise",
                              "On the words the rules corrected, what does {0} do?",
                              model),
                     xlabel=_t("fig.axis.changed_share", "% of the changed records"),
                     value_format="{:.1f}%")


def sentence_length_chart(sentence_metrics: pd.DataFrame) -> Figure:
    if sentence_metrics is None or sentence_metrics.empty:
        return _empty()
    return histogram(sentence_metrics["token"], bins=45,
                     title=_t("fig.title.sentence_length",
                              "Distribution of sentence length"),
                     xlabel=_t("fig.axis.tokens_per_sentence", "words per sentence"))


def dependency_distance_chart(arcs: pd.DataFrame) -> Figure:
    if arcs is None or arcs.empty or "arc_length" not in arcs.columns:
        return _empty()
    return histogram(arcs["arc_length"], bins=40,
                     title=_t("fig.title.distance", "Distance between head and "
                                                    "dependent"),
                     xlabel=_t("fig.axis.distance_tokens", "records of distance"),
                     ylabel=_t("fig.axis.arcs", "arcs"))


def diachronic_chart(profile: pd.DataFrame, metric: str,
                     group: str = "periodo") -> Figure:
    """One morphological ratio across periods, authors or genres."""
    if profile is None or profile.empty or metric not in profile.columns:
        return _empty()
    data = profile[[group, metric, "token"]].dropna(subset=[metric])
    if data.empty:
        return _empty()
    return bar_chart(data.sort_values(metric, ascending=False), group, metric,
                     title=metric, xlabel=metric, value_format="{:.3f}", top=20)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def save_figure(figure: Figure, path: str | Path, *, dpi: int = 300) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, dpi=dpi, bbox_inches="tight", facecolor="white")
    return target


CAPTIONS: dict[str, str] = {
    "01-anomalie-per-famiglia":
        "Findings produced by the diagnostic checks, grouped by family. The "
        "families correspond to the five levels at which the pipeline "
        "interrogates a treebank: morphology, lemmatisation, syntactic "
        "structure, text and encoding, agreement and government.",
    "02-anomalie-per-livello":
        "The same findings ordered by diagnostic class. The class says what the "
        "program can assert: a verifiable violation breaks an explicit rule of "
        "the scheme, a systematic variant follows a regular convention of the "
        "corpus, a case to check is a suspicious point the context decides.",
    "03-anomalie-per-regola":
        "The checks that report most, one by one.",
    "04-densita-per-documento":
        "Findings per document, per 10,000 active records. It is the rate the "
        "run declares, on the same unit and with the same factor. The "
        "normalisation is necessary: without it the ranking measures the length "
        "of the texts, not the quality of the annotation.",
    "05-distribuzione-casi":
        "Distribution of the cases over the nominals of the corpus.",
    "06-distribuzione-modi":
        "Distribution of the verbal moods.",
    "07-distribuzione-tempi":
        "Distribution of the verbal tenses.",
    "08-relazioni-sintattiche":
        "Frequency of the syntactic functions: the syntactic fingerprint of the "
        "corpus.",
    "09-lunghezza-frasi":
        "Distribution of sentence length, punctuation excluded.",
    "10-distanza-dipendenze":
        "Distribution of the linear distance between head and dependent. In a "
        "free word-order language this distribution is the quantitative measure "
        "of hyperbaton.",
    "11-profilo-per-periodo":
        "Morphological profile by linguistic period. The genitive/dative ratio "
        "and the optative index are the two sharpest diachronic markers among "
        "those a treebank can compute.",
    "12-accordo-modelli":
        "Agreement between corpus, Stanza and UDPipe, by author. The scale is "
        "centred on the observed mean, so that departures read as directions "
        "rather than as shades.",
    "13-tre-vie":
        "Corpus, Stanza and UDPipe on the same words. The category “the two "
        "models against the corpus” is the strongest unsupervised signal that "
        "the annotation deserves a second reading.",
    "14-rumore-replicato":
        "On the words the automatic rules changed: the model reproduces the "
        "original annotation, converges on the correction, or proposes a third "
        "value.",
    "15-accordo-per-posizione":
        "Agreement between the two sources on each of the nine positions of the "
        "tag, computed only on the words where at least one of the two marks "
        "that feature.",
}


def export_article_figures(
    output_dir: str | Path,
    *,
    tokens: pd.DataFrame,
    findings: pd.DataFrame | None = None,
    arcs: pd.DataFrame | None = None,
    sentence_metrics: pd.DataFrame | None = None,
    stanza_comparison: pd.DataFrame | None = None,
    udpipe_comparison: pd.DataFrame | None = None,
    corrected: pd.DataFrame | None = None,
    dpi: int = 300,
    progress=None,
) -> pd.DataFrame:
    """Render the figures of a run, at publication resolution.

    Writes PNG and PDF for each chart plus a ``didascalie.md`` file holding the
    captions, so that what leaves the program is a folder one can hand to a
    typesetter rather than a pile of untitled images.
    """
    from . import modelcmp, stats
    from .agdt_schema import CASE_SLOT, MOOD_SLOT, TENSE_SLOT

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    produced: list[dict[str, object]] = []

    def _emit(name: str, figure: Figure) -> None:
        if figure is None:
            return
        png = save_figure(figure, target / f"{name}.png", dpi=dpi)
        save_figure(figure, target / f"{name}.pdf", dpi=dpi)
        plt.close(figure)
        produced.append({"figura": name, "file": png.name,
                         "didascalia": caption(name)})
        if progress:
            progress(len(produced), 15, _t("fig.progress", "Figure {0}", name))

    if findings is not None and not findings.empty:
        _emit("01-anomalie-per-famiglia", findings_by_family(findings))
        _emit("02-anomalie-per-livello", findings_by_class(findings))
        _emit("03-anomalie-per-regola", findings_by_rule(findings))
        _emit("04-densita-per-documento", findings_density_by_document(findings, tokens))

    _emit("05-distribuzione-casi", slot_distribution_chart(
        stats.slot_distribution(tokens, CASE_SLOT, restrict_pos=set("naplm")),
        _t("fig.title.cases", "Case distribution")))
    _emit("06-distribuzione-modi", slot_distribution_chart(
        stats.slot_distribution(tokens, MOOD_SLOT, restrict_pos={"v"}),
        _t("fig.title.moods", "Verbal mood distribution")))
    _emit("07-distribuzione-tempi", slot_distribution_chart(
        stats.slot_distribution(tokens, TENSE_SLOT, restrict_pos={"v"}),
        _t("fig.title.tenses", "Verbal tense distribution")))

    relations = stats.relation_distribution(tokens)
    if not relations.empty:
        _emit("08-relazioni-sintattiche", bar_chart(
            relations, "relazione", "occorrenze",
            title=_t("fig.relations", "Frequency of syntactic functions"),
            xlabel=_t("fig.axis.occurrences", "occurrences"), top=18))

    if sentence_metrics is not None and not sentence_metrics.empty:
        _emit("09-lunghezza-frasi", sentence_length_chart(sentence_metrics))
    if arcs is not None and not arcs.empty:
        _emit("10-distanza-dipendenze", dependency_distance_chart(arcs))

    if "periodo" in tokens.columns:
        profile = stats.profile_by_group(tokens, "periodo")
        if not profile.empty:
            _emit("11-profilo-per-periodo", grouped_bar_chart(
                profile, "periodo",
                ["genitivi / dativi", "participi / verbi finiti", "indice di ottativo"],
                title=_t("fig.title.profile_by", "Morphological profile by {0}",
                         _t("group.periodo", "period")),
                ylabel=_t("fig.axis.ratio", "ratio")))

    if (stanza_comparison is not None and udpipe_comparison is not None
            and not stanza_comparison.empty and not udpipe_comparison.empty):
        if "autore" in tokens.columns:
            agreement = modelcmp.agreement_by_group(
                stanza_comparison, udpipe_comparison, tokens, group="autore")
            _emit("12-accordo-modelli", model_agreement_heatmap(agreement))
        summary, _detail = modelcmp.three_way_agreement(
            stanza_comparison, udpipe_comparison)
        if not summary.empty:
            _emit("13-tre-vie", three_way_chart(summary))
        if corrected is not None and not corrected.empty:
            replication = modelcmp.noise_replication(
                tokens, corrected, stanza_comparison, label="stanza")
            if not replication.empty:
                _emit("14-rumore-replicato", noise_replication_chart(replication))
        reference = modelcmp._pick(stanza_comparison, "postag_reference", "postag")
        model = modelcmp._pick(stanza_comparison, "postag_stanza")
        if reference and model:
            per_slot = modelcmp.per_slot_agreement(
                stanza_comparison[reference], stanza_comparison[model],
                left_label="corpus", right_label="Stanza")
            _emit("15-accordo-per-posizione", agreement_heatmap(per_slot))

    index = pd.DataFrame(produced)
    if not index.empty:
        lines = ["# Didascalie delle figure", ""]
        for record in produced:
            lines.append(f"**{record['figura']}** (`{record['file']}`)  ")
            lines.append(f"{record['didascalia']}")
            lines.append("")
        (target / "didascalie.md").write_text("\n".join(lines), encoding="utf-8")
        index.to_csv(target / "indice_figure.csv", index=False, encoding="utf-8-sig")
    return index
