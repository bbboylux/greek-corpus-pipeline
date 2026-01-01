"""Step 8 — the charts, and the one button that exports all of them.

A chooser on the left, one large figure on the right. Every chart is drawn by
``greek_corpus_pipeline.figures``, the same module that writes the 300 dpi files,
so what you see is what gets published.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QWidget,
)

from ..chart_view import ChartView
from ..i18n import data_label, pick, tr, value_label
from ..widgets import Card, notice, primary_button
from ..workers import ResultWorker, export_figures
from .base import Page

#: The "compare by" chooser governs every chart that can be split — see
#: ``_build_chart`` — so there is no list of exceptions to keep here.  A reader
#: who changes it while looking at "parts of speech" and sees nothing move
#: would conclude the control is broken, and greying it out on the charts it
#: does not apply to would only make it look broken in a second way.
#:
#: The grouped views show shares of each group's own total rather than counts:
#: across groups of different size a count chart compares the length of the
#: texts and nothing else.

# key -> (label, needs)
#: The charts that the page shows: the findings and the comparison with the models, the
#: two things that the study is about. The button that exports the figures writes the
#: whole set of :func:`greek_corpus_pipeline.figures.export_article_figures`, which also
#: includes figures that describe the corpus.
CHARTS = [
    ("famiglia", "findings"),
    ("livello", "findings"),
    ("regola", "findings"),
    ("densita", "findings"),
    ("accordo", "both_models"),
    ("treway", "both_models"),
]


class ChartsPage(Page):

    title_key = "charts.title"
    intro_key = "charts.intro"
    howto_keys = ("charts.howto.1",)

    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)
        self._worker: ResultWorker | None = None

        controls = QHBoxLayout()
        self._group_caption = QLabel(tr("stats.group_by"))
        controls.addWidget(self._group_caption)
        self._group = QComboBox()
        self._group.setMinimumWidth(180)
        self._group.currentIndexChanged.connect(self._draw)
        controls.addWidget(self._group)
        self._group_hint = QLabel("")
        self._group_hint.setObjectName("hint")
        controls.addWidget(self._group_hint, 1)
        controls.addStretch(1)
        holder = QWidget()
        holder.setLayout(controls)
        self.add(holder)

        self._list = QListWidget()
        self._list.setMinimumWidth(300)
        self._list.setMaximumWidth(380)
        # Entries that are not available carry a note beside them saying so, and that
        # line does not fit in a single column: without this the text would be cut off
        # halfway and a horizontal scroll bar would appear under the list.
        self._list.setWordWrap(True)
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.currentItemChanged.connect(lambda *_: self._draw())
        # The plain click too, not only the change of row: pressing the entry that is
        # already selected must redraw, not stay still without saying anything.
        self._list.itemClicked.connect(lambda *_: self._draw())

        self._view = ChartView(min_height=420)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._list)
        splitter.addWidget(self._view)
        splitter.setSizes([350, 880])
        splitter.setStretchFactor(1, 1)
        splitter.setMinimumHeight(480)
        self._splitter = splitter
        self.add(splitter, 1)

        export_card = Card()
        export_row = QHBoxLayout()
        self._export = primary_button(tr("charts.export_all"))
        self._export.clicked.connect(self._export_all)
        export_row.addWidget(self._export)
        self._export_hint = QLabel(tr("charts.export_all.hint"))
        self._export_hint.setObjectName("hint")
        export_row.addWidget(self._export_hint)
        self._export_status = QLabel("")
        self._export_status.setObjectName("hint")
        export_row.addWidget(self._export_status, 1)
        export_card.add_layout(export_row)
        self.add(export_card)

    def retranslate(self) -> None:
        self._locked.setText(tr("step.locked"))
        self._group_caption.setText(tr("stats.group_by"))
        self._export.setText(tr("charts.export_all"))
        self._export_hint.setText(tr("charts.export_all.hint"))
        super().retranslate()

    def refresh(self) -> None:
        has_corpus = self.state.has_corpus
        self._locked.setVisible(not has_corpus)
        self._export.setEnabled(has_corpus)
        if not has_corpus:
            return

        # The menu shows the translated name and carries the name of the column with it:
        # what ``_draw`` needs is the column, what the reader needs is the word in their
        # own language. Keeping them separate is also what makes the selection survive a
        # change of language.
        fields = self.state.group_fields()
        current = self._group.currentData()
        self._group.blockSignals(True)
        self._group.clear()
        for field in fields:
            self._group.addItem(tr(f"group.{field}") if f"group.{field}" != tr(f"group.{field}")
                                else field, field)
        index = self._group.findData(current or "periodo")
        self._group.setCurrentIndex(index if index >= 0 else 0)
        self._group.blockSignals(False)

        selected = self._list.currentRow()
        self._list.blockSignals(True)
        self._list.clear()
        for key, needs in CHARTS:
            label = tr(f"chart.{key}")
            available = self._disponibile(needs)
            item = QListWidgetItem(
                label if available else f"{label}  —  {tr('chart.unavailable')}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            # What is missing, if anything: ``_draw`` reads it to say so instead of
            # drawing an empty panel that looks like a successful chart.
            item.setData(Qt.ItemDataRole.UserRole + 1, "" if available else needs)
            if not available:
                item.setForeground(Qt.GlobalColor.gray)
                item.setToolTip(tr(f"chart.needs.{needs}"))
            self._list.addItem(item)
        self._list.setCurrentRow(selected if selected >= 0 else 0)
        self._list.blockSignals(False)
        self._draw()

    def _disponibile(self, needs: str) -> bool:
        """Whether the data that this chart asks for are already there."""
        return (needs == "corpus"
                or (needs == "findings" and self.state.has_findings)
                or (needs == "arcs" and not self.state.arcs.empty)
                or (needs == "models" and self.state.has_models)
                or (needs == "both_models" and self.state.has_both_models))

    def _draw(self) -> None:
        item = self._list.currentItem()
        if item is None or not self.state.has_corpus:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        manca = item.data(Qt.ItemDataRole.UserRole + 1)
        if manca:
            # The chart asks for data that are not there. Drawing it all the same would
            # produce an empty panel that looks like a successful chart: here instead it
            # says what is missing and where to obtain it.
            self._view.show_message(tr("chart.unavailable"), tr(f"chart.needs.{manca}"))
            self._group_hint.setText("")
            return
        group = self._group.currentData() or ""
        # The chooser applies to whatever is on screen, always.
        splits = bool(group) and group in getattr(self.state.tokens, "columns", [])
        self._group_hint.setText(
            tr("chart.split_by", self._group.currentText()) if splits
            else tr("chart.no_metadata"))
        try:
            figure, caption = _build_chart(self.state, key, group)
        except Exception as exception:                # noqa: BLE001
            # Without this the previous chart would stay on the screen, and whoever had
            # just chosen another entry would read the wrong numbers believing that they
            # were their own.
            self.logMessage.emit(tr("charts.failed", key, exception))
            self._view.show_message(tr("charts.failed.title"),
                                    tr("charts.failed", key, exception))
            return
        self._view.set_figure(figure, caption, self._unita_del_grafico(key, group))
        # A chart of twenty-two bars is taller than one of five, and the
        # splitter has to be told: without this the tall ones were cut off at
        # the bottom, or — before the canvas learned to ask for its own height —
        # squashed until the title disappeared. The page itself scrolls, so
        # growing here costs nothing.
        self._splitter.setMinimumHeight(max(480, self._view.wanted_height() + 90))

    def _unita_del_grafico(self, key: str, group: str) -> str:
        """What the chart counts, and on which denominator.

        Two entries per chart where the grouping changes the answer: divided by author
        the same bar is no longer a count but a share of that author's total, and saying
        so under the chart costs a line.
        """
        diviso = bool(group) and group in getattr(self.state.tokens, "columns", [])
        if diviso:
            specifica = tr(f"chartunit.{key}.gruppo")
            if specifica != f"chartunit.{key}.gruppo":
                return specifica
        generica = tr(f"chartunit.{key}")
        return "" if generica == f"chartunit.{key}" else generica

    def _export_all(self) -> None:
        if not self.state.run_id:
            self._export_status.setText(tr("charts.export_needs_run"))
            return
        from greek_corpus_pipeline.storage import report_dir

        default = str(report_dir(self.state.workspace, self.state.run_id) / "figure")
        target = QFileDialog.getExistingDirectory(
            self, tr("charts.export_all"), default)
        if not target:
            return
        self._cartella_uscita = target
        self._export_status.setText(tr("app.working"))
        self.run_work(export_figures, self.state.workspace, self.state.run_id, target,
                      label=tr("charts.export_all"))

    def work_finished(self, riuscito: bool, messaggio: str = "") -> None:
        """The export has really finished: now it is possible to say how it went.

        The line “Exported to …” must not appear right after the start, while the work
        is still running: it would say that the export succeeded even when it then
        fails, and whoever read it would go looking for files that are not there.
        """
        cartella = getattr(self, "_cartella_uscita", "")
        if not cartella:
            return
        self._cartella_uscita = ""
        if riuscito:
            self._export_status.setText(f"{tr('charts.exported')} {cartella}")
        else:
            self._export_status.setText(tr("charts.export_failed", messaggio))


def _group_of_documents(tokens, group: str):
    """document_id → group value. The join every grouped chart needs.

    Findings, arcs and sentence metrics all carry ``document_id`` and nothing
    else from the metadata; the grouping columns live on the token table. One
    small lookup table joins the two, and it is built once per chart rather
    than merged row by row.
    """
    import pandas as pd

    if tokens is None or tokens.empty or group not in tokens.columns:
        return pd.DataFrame()
    return (tokens[["document_id", group]]
            .drop_duplicates(subset="document_id")
            .reset_index(drop=True))


def _attach_group(frame, tokens, group: str):
    """Add the grouping column to a frame that only knows its document."""
    import pandas as pd

    if frame is None or frame.empty:
        return pd.DataFrame()
    if group in frame.columns:
        return frame
    if "document_id" not in frame.columns:
        return pd.DataFrame()
    lookup = _group_of_documents(tokens, group)
    if lookup.empty:
        return pd.DataFrame()
    merged = frame.merge(lookup, on="document_id", how="left")
    return merged[merged[group].notna()]


def _relabelled(frame, columns: list[str]):
    """A copy with the translated columns, for the legend and for nothing else.

    ``grouped_bar_chart`` writes the name of the column in the legend. Translating the
    name in the data would break it for anyone else who reads it; translating it in a
    copy, just before drawing, leaves the data where it is.
    """
    if frame is None or getattr(frame, "empty", True):
        return frame
    renamed = {name: data_label(name) for name in columns if name in frame.columns}
    return frame.rename(columns=renamed) if renamed else frame


def _counted(frame, group: str, category: str, value_name: str = "segnalazioni"):
    """Long table (group, category, count) — the shape the grouped chart wants."""
    if frame is None or frame.empty:
        import pandas as pd
        return pd.DataFrame()
    return (frame.groupby([group, category], dropna=False, sort=False)
            .size().reset_index(name=value_name))


def _build_chart(state, key: str, group: str):
    """Return (figure, caption) for one chart key, split by *group* if asked.

    Every chart that can be split is split, so that the chooser never reads as
    broken.  Where a split is meaningful the values become percentages of each
    group's own total, because counts across groups of different size compare
    the length of the texts and nothing else.
    """
    import pandas as pd

    from greek_corpus_pipeline import figures, modelcmp, stats
    from greek_corpus_pipeline.agdt_schema import (
        CASE_SLOT, MOOD_SLOT, POS_SLOT, TENSE_SLOT,
    )

    # The charts count on the **active records**, which are the unit with which the run
    # expresses its rates. Counting on the imported records would give the same density
    # a denominator different from that of the backend.
    unita = state.units()
    tokens = state.tokens if unita is None else unita.active_records
    # The name of the group as the user reads it: in the titles of the charts “period”
    # must appear, not “periodo”, when the interface is in English.
    shown = tr(f"group.{group}") if group and tr(f"group.{group}") != f"group.{group}" else group
    # A grouping is live only if the corpus actually carries that column.
    split = bool(group) and group in getattr(tokens, "columns", [])
    if not split and key in {"profilo", "composizione", "accordo"}:
        # These three have no ungrouped form at all: drawing them without a
        # grouping produces a blank panel rather than a chart. Fall back to the
        # document, which every corpus has.
        for candidate in ("periodo", "autore", "opera", "document_id"):
            if candidate in getattr(tokens, "columns", []):
                group, split = candidate, True
                break

    def by(group_caption: str, plain: str) -> str:
        return group_caption if split else plain

    # ── anomalies ──────────────────────────────────────────────────────
    if key in {"famiglia", "livello", "regola"} and split:
        from greek_corpus_pipeline.rule_catalog import (
            CLASS_LABELS, FAMILY_LABELS, rule_class, rule_family,
        )
        frame = _attach_group(state.findings, tokens, group)
        if frame.empty:
            return figures._empty(tr("charts.none_for_group")), ""
        frame = frame.copy()
        if key == "famiglia":
            frame["famiglia"] = frame["rule_id"].map(rule_family).map(
                lambda name: pick(FAMILY_LABELS.get(name, (name, name))))
            category, title = "famiglia", tr("fig.family_by", shown)
            top = 8
        elif key == "livello":
            frame["classe"] = frame["rule_id"].map(rule_class).map(
                lambda name: pick(CLASS_LABELS.get(name, (name, name))))
            category, title = "classe", tr("fig.class_by", shown)
            top = 6
        else:
            # The name of the check is derived from the rule, in the current language.
            # Reading it from ``anomaly_name`` — which is created when the analysis is
            # run — would keep the chart in Italian after the switch to English. Same
            # categories, same counts: only the language of the label changes.
            from greek_corpus_pipeline.rule_catalog import rule_name as _nome
            frame["regola"] = frame["rule_id"].astype(str).map(
                lambda rid: _nome(rid, pick(("it", "en"))))
            category, title = "regola", tr("fig.rule_by", shown)
            top = 12
        table = _counted(frame, group, category)
        return (figures.grouped_distribution_chart(
            table, group, category, "segnalazioni", title=title,
            top_categories=top),
            tr("charts.cap.findings_by_group", shown))

    if key == "densita" and split:
        frame = _attach_group(state.findings, tokens, group)
        if frame.empty or group not in tokens.columns:
            return figures._empty(tr("charts.none_for_group")), ""
        sizes = tokens.groupby(group, dropna=False, sort=False).size().rename("token")
        counts = frame.groupby(group, dropna=False, sort=False).size().rename("segnalazioni")
        table = pd.concat([counts, sizes], axis=1).dropna()
        table = table[table["token"] >= 200].reset_index()
        if table.empty:
            return figures._empty(tr("charts.no_group_big_enough")), ""
        table["per 10.000"] = (table["segnalazioni"] / table["token"] * 10000).round(1)
        table = table.sort_values("per 10.000", ascending=False)
        return (figures.bar_chart(table, group, "per 10.000",
                                  title=tr("fig.density_by", shown),
                                  xlabel=tr("charts.axis.per_ten_thousand"), top=20,
                                  value_format="{:,.1f}"),
                tr("charts.cap.density", shown))

    if key == "famiglia":
        return figures.findings_by_family(state.findings), figures.caption("01-anomalie-per-famiglia")
    if key == "livello":
        return figures.findings_by_class(state.findings), figures.caption("02-anomalie-per-livello")
    if key == "regola":
        return figures.findings_by_rule(state.findings), figures.caption("03-anomalie-per-regola")
    if key == "densita":
        return (figures.findings_density_by_document(state.findings, tokens),
                figures.caption("04-densita-per-documento"))

    # ── tag-slot distributions ─────────────────────────────────────────
    slots = {
        "casi": (CASE_SLOT, set("naplm"), "Distribuzione dei casi", "05-distribuzione-casi"),
        "modi": (MOOD_SLOT, {"v"}, "Distribuzione dei modi verbali", "06-distribuzione-modi"),
        "tempi": (TENSE_SLOT, {"v"}, "Distribuzione dei tempi verbali", "07-distribuzione-tempi"),
        "pos": (POS_SLOT, None, "Parti del discorso", None),
    }
    if key in slots:
        slot, restrict, title, caption_key = slots[key]
        # The title shown follows the language; the Italian one remains as a fallback
        # for the caption, which is still monolingual.
        title = tr(f"chart.{key}") if tr(f"chart.{key}") != f"chart.{key}" else title
        if split:
            table = stats.slot_distribution(tokens, slot, restrict_pos=restrict, group=group)
            return (figures.grouped_distribution_chart(
                table, group, "categoria", "occorrenze",
                title=tr("fig.by", title, shown)),
                tr("charts.cap.slot_by_group", title, shown))
        table = stats.slot_distribution(tokens, slot, restrict_pos=restrict)
        return (figures.slot_distribution_chart(table, title),
                figures.caption(caption_key) if caption_key else "")

    if key == "relazioni":
        if split:
            table = stats.relation_distribution(tokens, group)
            return (figures.grouped_distribution_chart(
                table, group, "relazione", "occorrenze",
                title=tr("fig.relations_by", shown), top_categories=14),
                tr("charts.cap.relations_by_group", shown))
        table = stats.relation_distribution(tokens)
        return (figures.bar_chart(table, "relazione", "occorrenze",
                                  title=tr("fig.relations"),
                                  xlabel=tr("fig.axis.occurrences"), top=18),
                figures.caption("08-relazioni-sintattiche"))

    # ── sentence shape ─────────────────────────────────────────────────
    if key == "frasi":
        metrics = stats.tree_metrics(tokens, state.arcs)
        if split:
            frame = _attach_group(metrics, tokens, group)
            if frame.empty:
                return figures._empty(tr("charts.no_data_for_group")), ""
            table = frame.groupby(group, dropna=False, sort=False).agg(
                **{"token per frase": ("token", "mean"),
                   "profondità media": ("profondità massima", "mean"),
                   "frasi": ("token", "size")}).reset_index()
            table = table[table["frasi"] >= 20].round(2)
            if table.empty:
                return figures._empty(tr("charts.no_sentences")), ""
            table = table.sort_values("token per frase", ascending=False)
            return (figures.grouped_bar_chart(
                _relabelled(table, ["token per frase", "profondità media"]),
                group, [data_label("token per frase"), data_label("profondità media")],
                title=tr("fig.shape_by", shown), ylabel=tr("fig.axis.mean"), top=14),
                tr("charts.cap.shape_by_group", shown))
        return figures.sentence_length_chart(metrics), figures.caption("09-lunghezza-frasi")

    if key == "distanze":
        if split:
            frame = _attach_group(state.arcs, tokens, group)
            if frame.empty or "arc_length" not in frame.columns:
                return figures._empty(tr("charts.no_arcs_for_group")), ""
            work = frame.copy()
            work["_len"] = pd.to_numeric(work["arc_length"], errors="coerce").abs()
            table = work.groupby(group, dropna=False, sort=False).agg(
                **{"distanza media": ("_len", "mean"),
                   "archi": ("_len", "size")}).reset_index()
            table = table[table["archi"] >= 100].round(2)
            if table.empty:
                return figures._empty(tr("charts.no_arcs")), ""
            table = table.sort_values("distanza media", ascending=False)
            return (figures.bar_chart(table, group, "distanza media",
                                      title=tr("fig.distance_by", shown),
                                      xlabel=tr("charts.axis.head_distance"),
                                      top=18, value_format="{:,.2f}"),
                    tr("charts.cap.distance_by_group", shown))
        return figures.dependency_distance_chart(state.arcs), figures.caption("10-distanza-dipendenze")

    # ── charts that were grouped from the start ────────────────────────
    if key == "profilo":
        profile = stats.profile_by_group(tokens, group)
        caption = (figures.caption("13-profilo-per-periodo") if group == "periodo"
                   else tr("charts.cap.profile_by_group", shown))
        metrics = ["genitivi / dativi", "participi / verbi finiti",
                   "indice di ottativo"]
        return (figures.grouped_bar_chart(
            _relabelled(profile, metrics), group,
            [data_label(name) for name in metrics],
            title=tr("fig.profile_by", shown), ylabel=tr("fig.axis.ratio")),
            caption)
    if key == "composizione":
        table = stats.counts_by_group(tokens, group)
        return (figures.bar_chart(table, group, "token",
                                 title=tr("fig.composition_by", shown),
                                 xlabel=data_label("token")),
                tr("charts.cap.composition_by_group", shown))
    if key == "accordo":
        table = modelcmp.agreement_by_group(
            state.stanza_comparison, state.udpipe_comparison, tokens, group=group)
        return (figures.model_agreement_heatmap(table, group),
                figures.caption("14-accordo-modelli") if group == "periodo"
                else tr("charts.cap.agreement_by_group", shown))

    # ── model comparisons ──────────────────────────────────────────────
    if key == "treway":
        summary, detail = modelcmp.three_way_agreement(
            state.stanza_comparison, state.udpipe_comparison)
        if split and not detail.empty:
            frame = _attach_group(detail, tokens, group)
            if not frame.empty and "esito" in frame.columns:
                table = _counted(frame, group, "esito", "token")
                table = table.assign(esito=table["esito"].map(value_label))
                return (figures.grouped_distribution_chart(
                    table, group, "esito", "token",
                    title=tr("fig.threeway_by", shown), top_categories=5),
                    tr("charts.cap.threeway_by_group", shown))
        return figures.three_way_chart(summary), figures.caption("15-tre-vie")

    if key == "posizioni":
        comparison = (state.stanza_comparison if not state.stanza_comparison.empty
                      else state.udpipe_comparison)
        label = "stanza" if not state.stanza_comparison.empty else "udpipe"
        reference = modelcmp._pick(comparison, "postag_reference", "postag")
        model = modelcmp._pick(comparison, f"postag_{label}")
        if not reference or not model:
            return figures._empty(), ""
        if split:
            frame = _attach_group(comparison, tokens, group)
            rows = {}
            if not frame.empty:
                for name, subset in frame.groupby(group, dropna=False, sort=False):
                    if len(subset) < 500:
                        continue
                    per_slot = modelcmp.per_slot_agreement(
                        subset[reference], subset[model])
                    if per_slot.empty:
                        continue
                    value = next((column for column in per_slot.columns
                                  if "accordo" in str(column).lower()
                                  or "%" in str(column)), per_slot.columns[-1])
                    name_column = per_slot.columns[0]
                    rows[str(name)] = dict(zip(per_slot[name_column].astype(str),
                                               pd.to_numeric(per_slot[value],
                                                             errors="coerce")))
            if rows:
                matrix = pd.DataFrame(rows).T
                return (figures.heatmap(
                    matrix, title=tr("fig.slots_by", shown),
                    xlabel=tr("charts.axis.tag_position"), ylabel=shown,
                    diverging=True, value_format="{:.0f}",
                    colorbar_label=tr("charts.axis.agreement_share")),
                    tr("charts.cap.slots_by_group", shown))
        per_slot = modelcmp.per_slot_agreement(comparison[reference], comparison[model])
        return figures.agreement_heatmap(per_slot), figures.caption("17-accordo-per-posizione")

    return figures._empty(), ""
