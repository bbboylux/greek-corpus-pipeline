"""Step 3 — run the diagnostic checks and read the results.

The layout answers three questions in order: *how many*, *of what kind*, and
*show me this one*. The last is where the real work happens, so the detail panel
gets a permanent home on the right rather than a pop-up: a philologist deciding
whether ``ATR`` should be ``ADV`` needs the whole sentence in front of them, and
needs it to stay there while they scroll the list.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from ..i18n import T, data_label, number, pick, tr
from ..style import ACCENT, ACCENT_DARK, ACCENT_PICK, CARD, LINE, MUTED
from ..variazione_testi import guida_html, intestazioni, nascoste, spiegazioni
from ..widgets import (
    Card, DataTable, MetricGrid, ghost_button, heading, notice, paragraph,
    primary_button, separator,
)
#: The Greek inside the HTML of the panel.
GREEK_HTML = "'GFS Didot','Palatino Linotype',serif"

from ..workers import run_detection
from .base import Page

FAMILIES = [
    ("morphology", "errors.family.morphology", True),
    ("lemma", "errors.family.lemma", True),
    ("syntax", "errors.family.syntax", True),
    ("text", "errors.family.text", True),
    ("agreement", "errors.family.agreement", True),
    ("variation", "errors.family.variation", False),
]

#: The tabs of the inconsistencies, in the order in which they are read. Accents and
#: breathings have no tab: the checks on encoding list each case in the findings, with
#: the sentence around it, and as a tab they would produce rows that cannot be used —
#: ὡς with seven “variants” is the normal accentuation of Greek, not a defect.
VARIATION_TABS = ["morfologia", "posizioni", "contesto", "dipendenze"]

#: The columns that the table shows.
#:
#: ``form`` and ``lemma`` are not there, and the choice has to be justified: the
#: right-hand panel already shows them for the selected row, and repeating them
#: here would take width away from the three columns with which a finding is
#: really looked up — diagnostic class, treatment and name of the check.  Without
#: them, however, two rows of the same rule in the same document would be
#: indistinguishable, and this is why the reference of the sentence is there in
#: their place: it is what makes a row findable.  They remain in the data, in the
#: selected row, in the search and in the export.
DISPLAY_COLUMNS = [
    "anomaly_name", "document_id", "sentence_id", "autore", "opera",
]

#: The columns that the selected row must carry with it without showing them: the
#: right-hand panel needs them to find the sentence, the rule and the values that
#: the corpus really carries.  Without them the panel would show the form alone.
#:
#: The ``suggested_*`` fields stay here because they are part of the finding and
#: must come out in the export, but **this page does not show them**: the proposed
#: correction is read at the “Correct” step, where it is decided whether to apply
#: it.  Here one sees what is in the corpus and why it is flagged.
#:
#: ``issue_key`` and ``issue_params`` are here and not among the visible columns:
#: they are the same diagnosis in a form readable by a program, and they serve two
#: purposes.  For the panel, which recomposes from them the sentence in the
#: current language; and for the exported file, where they make the values — how
#: many occurrences, which position, which code point — recoverable without
#: rereading a sentence.
CARRIED_COLUMNS = [
    "rule_id", "form", "lemma", "sentence_index", "token_id",
    "token_index", "postag", "relation", "head",
    "issue", "issue_key", "issue_params",
    "suggested_postag", "suggested_lemma", "suggested_relation",
    "suggested_form", "suggested_head",
]


class ErrorsPage(Page):

    title_key = "errors.title"
    intro_key = "errors.intro"
    howto_keys = ("errors.howto.1",)

    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        # ── What to run ────────────────────────────────────────────────
        self._chooser_card = Card(tr("errors.choose"))
        chooser = self._chooser_card
        self._family_boxes: dict[str, QCheckBox] = {}
        grid = QHBoxLayout()
        grid.setSpacing(18)
        column = QVBoxLayout()
        for index, (key, label_key, default) in enumerate(FAMILIES):
            box = QCheckBox(tr(label_key))
            box.setChecked(default)
            # No signal: these boxes say what to look for, and the run button reads them
            # when it starts (see _run). The marker distinguishes a command read at
            # start from a mute command, which would be a defect.
            box.setProperty("letto_al_via", True)
            self._family_boxes[key] = box
            column.addWidget(box)
            if index == 2:
                grid.addLayout(column)
                column = QVBoxLayout()
        grid.addLayout(column)
        grid.addStretch(1)
        chooser.add_layout(grid)
        self._variation_warning = paragraph(
            tr("errors.variation_warning"), "hint")
        chooser.add(self._variation_warning)

        run_row = QHBoxLayout()
        self._run = primary_button(tr("errors.run"))
        self._run.clicked.connect(self._run_checks)
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)          # pulsating / indeterminate
        self._busy_bar.setMaximumWidth(200)
        self._busy_bar.setVisible(False)
        run_row.addWidget(self._run)
        run_row.addWidget(self._busy_bar)
        run_row.addStretch(1)
        self._running = False
        chooser.add_layout(run_row)
        self.add(chooser)

        # ── Summary ────────────────────────────────────────────────────
        self._summary_card = Card(tr("errors.summary"))
        self._metrics = MetricGrid(5)
        self._summary_card.add(self._metrics)
        self._summary_card.add(separator())
        self._levels = QLabel("")
        self._levels.setWordWrap(True)
        self._levels.setObjectName("hint")
        self._summary_card.add(self._levels)
        self._by_rule = DataTable(min_height=200, column_picker=False)
        self._summary_card.add(self._by_rule, 1)
        self.add(self._summary_card)

        # ── Findings list + detail ─────────────────────────────────────
        self._list_card = Card(tr("errors.list"))

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self._family_filter = QComboBox()
        self._level_filter = QComboBox()
        self._rule_filter = QComboBox()
        self._rule_filter.setMinimumWidth(280)
        self._filter_captions: list[tuple[str, QLabel]] = []
        for label_key, box in (("errors.filter_family", self._family_filter),
                               ("errors.filter_level", self._level_filter),
                               ("errors.filter_rule", self._rule_filter)):
            caption = QLabel(tr(label_key))
            caption.setObjectName("hint")
            self._filter_captions.append((label_key, caption))
            filter_row.addWidget(caption)
            filter_row.addWidget(box)
        filter_row.addStretch(1)
        self._family_filter.currentIndexChanged.connect(self._on_family_changed)
        self._level_filter.currentIndexChanged.connect(self._on_level_changed)
        self._rule_filter.currentIndexChanged.connect(self._apply_filters)
        self._list_card.add_layout(filter_row)

        self._table = DataTable(min_height=380, hidden=set(CARRIED_COLUMNS))
        self._table.set_empty_text("empty.findings", "empty.findings.hint")
        self._table.rowSelected.connect(self._show_detail)

        self._detail = _DetailPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._table)
        splitter.addWidget(self._detail)
        splitter.setSizes([700, 480])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setMinimumHeight(500)
        self._list_card.add(splitter, 1)
        self.add(self._list_card, 1)

        # ── Inconsistencies across similar passages ────────────────────
        # Kept apart from the findings list on purpose: a variation nucleus is
        # not a token with something wrong on it, it is a *set* of occurrences
        # annotated two ways. Merging the two would force one of them into the
        # wrong shape.
        self._variation_card = Card(tr("errors.variation_card"))
        self._variation_intro = paragraph(tr("errors.variation_intro"), "hint")
        self._variation_card.add(self._variation_intro)
        self._variation_tabs = QTabWidget()
        self._variation_tables: dict[str, DataTable] = {}
        self._variation_notes: list[QLabel] = []
        self._variation_guides: dict[str, QLabel] = {}
        self._variation_howto: list = []
        for key in VARIATION_TABS:
            table = DataTable(min_height=300, hidden=nascoste(key),
                              labels=intestazioni(key), tips=spiegazioni(key))
            table.set_empty_text("empty.variation", "empty.variation.hint")
            self._variation_tables[key] = table
            container = Card()
            note = paragraph(tr(f"errors.var.{key}.hint"), "hint")
            self._variation_notes.append(note)
            container.add(note)
            container.add(self._howto_row(key))
            container.add(self._variation_guides[key])
            container.add(table, 1)
            self._variation_tabs.addTab(container, tr(f"errors.var.{key}"))
        self._variation_card.add(self._variation_tabs, 1)
        self.add(self._variation_card, 1)

        self._filtered = pd.DataFrame()

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        self._locked.setText(tr("step.locked"))
        self._chooser_card.set_title(tr("errors.choose"))
        for key, _label_key, _default in FAMILIES:
            box = self._family_boxes.get(key)
            if box is not None:
                box.setText(tr(_label_key))
        self._variation_warning.setText(tr("errors.variation_warning"))
        self._summary_card.set_title(tr("errors.summary"))
        self._list_card.set_title(tr("errors.list"))
        for label_key, caption in self._filter_captions:
            caption.setText(tr(label_key))
        self._variation_card.set_title(tr("errors.variation_card"))
        self._variation_intro.setText(tr("errors.variation_intro"))
        for index, key in enumerate(VARIATION_TABS):
            self._variation_tabs.setTabText(index, tr(f"errors.var.{key}"))
            self._variation_notes[index].setText(tr(f"errors.var.{key}.hint"))
            self._variation_tables[key].set_headers(intestazioni(key),
                                                    spiegazioni(key))
            self._variation_guides[key].setText(guida_html(key))
        for bottone in self._variation_howto:
            bottone.setText(tr("vartab.howto.close") if bottone.isChecked()
                            else tr("vartab.howto"))
        # The right-hand panel rewrites itself: ``Page.retranslate`` finds it among the
        # children and asks it to.
        super().retranslate()

    # ── Actions ────────────────────────────────────────────────────────
    def _run_checks(self) -> None:
        if not self.state.run_id:
            return
        families = {key: box.isChecked() for key, box in self._family_boxes.items()}
        if not any(families.values()):
            return
        self._running = True
        self._run.setEnabled(False)
        self._busy_bar.setVisible(True)
        self.run_work(run_detection, self.state.workspace, self.state.run_id,
                      families, self.state.filter_options, label=tr("step.errors"))

    # ── Rendering ──────────────────────────────────────────────────────
    def refresh(self) -> None:
        has_corpus = self.state.has_corpus
        self._locked.setVisible(not has_corpus)
        # If an analysis was running, it has now finished.
        if self._running:
            self._running = False
            self._busy_bar.setVisible(False)
        self._run.setEnabled(has_corpus)

        findings = self.state.findings
        has_findings = not findings.empty
        self._summary_card.setVisible(has_findings)
        self._list_card.setVisible(has_findings)
        self._render_variation()
        self._run.setText(tr("errors.run_again") if has_findings else tr("errors.run"))
        if not has_findings:
            return

        # Everything below reads the findings whole — the enrichment, the
        # per-rule table, the counts — so it is computed once per set of
        # findings, off the main thread, and the page shows its structure with
        # a waiting line until the answer lands.
        # The summary carries the words of the chosen language inside it — names
        # of families, classes and checks — so the language is part of what
        # identifies it: without it, changing language would fetch the previous
        # summary from the cache and the page would stay in the old language.
        slot = f"errors_summary::{T.language}"
        ready = self.state.cache_peek(slot, findings)
        if ready is not None:
            self._apply_summary(ready)
            return
        waiting = tr("table.computing")
        self._by_rule.show_waiting(waiting)
        self._table.show_waiting(waiting)
        self._levels.setText(waiting)
        self.compute_in_background(
            slot,
            lambda frame=findings, tokens=self.state.tokens, name=slot:
                self._compute_summary(frame, tokens, name),
            self._apply_summary)

    def _compute_summary(self, findings: pd.DataFrame, tokens: pd.DataFrame,
                         slot: str = "errors_summary") -> dict:
        """The enriched findings, the per-rule table and the headline counts.

        Runs on a worker thread; touches nothing but pandas.
        """
        from greek_corpus_pipeline.fastmap import map_unique
        from greek_corpus_pipeline.rule_catalog import (
            CLASS_LABELS, FAMILY_LABELS, TREATMENT_LABELS,
            rule_class, rule_family, rule_treatment,
        )

        # The text of the finding in the current language, and not in the one in which
        # the analysis was run. Name of the check, canonical description and sentence of
        # the single occurrence are all derived from data — ``rule_id``, ``issue_key``,
        # ``issue_params`` — and not from the file: running in Italian and then
        # switching to English would show an English interface with Italian sentences
        # inside, and would export them that way.
        from greek_corpus_pipeline.issue_testi import localizza
        work = localizza(findings, pick(("it", "en")))
        work["_famiglia"] = map_unique(
            work["rule_id"],
            lambda rule: pick(FAMILY_LABELS.get(rule_family(rule), ("?", "?"))))
        work["_livello"] = map_unique(
            work["rule_id"],
            lambda rule: pick(CLASS_LABELS.get(rule_class(rule), ("?", "?"))))
        # The third coordinate of § 4.1 of the article, next to the other two: whoever
        # reads can tell, row by row, whether the program is able to propose a correction
        # or asks for a reading.
        work["_trattamento"] = map_unique(
            work["rule_id"],
            lambda rule: pick(TREATMENT_LABELS.get(rule_treatment(rule), ("?", "?"))))

        tokens_touched = 0
        if {"document_id", "sentence_id", "token_id"} <= set(work.columns):
            tokens_touched = int(
                work[["document_id", "sentence_id", "token_id"]].drop_duplicates().shape[0])
        corpus_size = max(len(tokens), 1)
        metrics = {
            tr("errors.metric.findings"): int(len(work)),
            tr("errors.metric.tokens_touched"): tokens_touched,
            tr("errors.metric.share"): f"{tokens_touched / corpus_size * 100:.2f} %",
            # The class of a violation is not called “certain errors”: § 4 of the
            # article states that a violation of the scheme is a verifiable
            # non-conformity, not an established error.
            tr("errors.metric.violations"):
                int((work.get("severity", "sospetto") == "errore").sum()),
            tr("errors.metric.variants"):
                int((work.get("severity", "sospetto") == "sospetto").sum()),
            tr("errors.metric.auto"):
                int(work.get("auto_correctable", pd.Series(dtype=bool)).fillna(False).sum()),
            tr("errors.metric.rules"): int(work["rule_id"].nunique()),
        }

        # The name of the class in full, and in the order 1-2-3 instead of by frequency.
        # Cutting everything after the hyphen would leave “2 1,651 · 3 680 · 1 59”,
        # which says nothing to anybody.
        level_counts = work["_livello"].value_counts()
        levels = tr("errors.levels_explained") + ":  " + "   ·   ".join(
            f"{name}: {number(int(level_counts[name]))}"
            for name in sorted(level_counts.index, key=str))

        # ``anomaly_name`` is already in the current language: ``localizza``
        # (“localise”) rewrote it at the top of this function.
        by_rule = (work.groupby(["_famiglia", "_livello", "_trattamento", "anomaly_name"],
                                sort=False)
                   .agg(segnalazioni=("rule_id", "size"),
                        documenti=("document_id", "nunique") if "document_id" in work.columns
                        else ("rule_id", "size"),
                        forme=("form", "nunique") if "form" in work.columns
                        else ("rule_id", "size"))
                   .reset_index()
                   .rename(columns={"_famiglia": "famiglia",
                                    "_livello": "classe diagnostica",
                                    "_trattamento": "trattamento",
                                    "anomaly_name": "controllo diagnostico"})
                   .sort_values("segnalazioni", ascending=False))

        summary = {"enriched": work, "metrics": metrics,
                   "levels": levels, "by_rule": by_rule}
        self.state.cache[slot] = (self.state.signature(findings), summary)
        return summary

    def _apply_summary(self, summary: dict) -> None:
        self._enriched = summary["enriched"]
        self._metrics.set_metrics(summary["metrics"])
        self._levels.setText(summary["levels"])
        self._by_rule.set_dataframe(summary["by_rule"])
        self._populate_filters(self._enriched)
        self._apply_filters()

    def _populate_filters(self, work: pd.DataFrame) -> None:
        """Initial population: all three menus from the complete dataset."""
        self._populate_family_filter(work)
        self._populate_level_filter(work)
        self._populate_rule_filter(work)

    def _populate_family_filter(self, work: pd.DataFrame) -> None:
        self._populate_value_filter(self._family_filter, work, "_famiglia")

    def _populate_level_filter(self, work: pd.DataFrame) -> None:
        self._populate_value_filter(self._level_filter, work, "_livello")

    def _populate_value_filter(self, box: QComboBox, work: pd.DataFrame,
                               column: str) -> None:
        # The menu of the checks carries the name of the check in the chosen language
        # and, beneath, its identifier: the name is translated, the identifier is what
        # the filter uses.
        current = box.currentText()
        box.blockSignals(True)
        box.clear()
        box.addItem(tr("errors.filter_all"))
        if column in work.columns:
            values = sorted(work[column].dropna().unique().tolist())
            box.addItems([str(v) for v in values])
        index = box.findText(current)
        box.setCurrentIndex(index if index >= 0 else 0)
        box.blockSignals(False)

    def _populate_rule_filter(self, work: pd.DataFrame) -> None:
        from greek_corpus_pipeline.rule_catalog import rule_name
        from ..i18n import T
        box = self._rule_filter
        chosen = box.currentData()
        box.blockSignals(True)
        box.clear()
        box.addItem(tr("errors.filter_all"), "")
        if "rule_id" in work.columns:
            counts = work["rule_id"].value_counts()
            for rule_id, count in counts.items():
                label = rule_name(str(rule_id), T.language)
                box.addItem(f"{label}  ({number(int(count))})", str(rule_id))
        index = box.findData(chosen)
        box.setCurrentIndex(index if index >= 0 else 0)
        box.blockSignals(False)

    def _on_family_changed(self) -> None:
        """Family changed: narrows the level and the rule to those present."""
        work = getattr(self, "_enriched", pd.DataFrame())
        if work.empty:
            return
        family = self._family_filter.currentText()
        subset = (work[work["_famiglia"] == family]
                  if family and family != tr("errors.filter_all")
                  else work)
        self._populate_level_filter(subset)
        level = self._level_filter.currentText()
        if level and level != tr("errors.filter_all"):
            subset = subset[subset["_livello"] == level]
        self._populate_rule_filter(subset)
        self._apply_filters()

    def _on_level_changed(self) -> None:
        """Level changed: reduces the menu of the rules to those present."""
        work = getattr(self, "_enriched", pd.DataFrame())
        if work.empty:
            return
        family = self._family_filter.currentText()
        subset = (work[work["_famiglia"] == family]
                  if family and family != tr("errors.filter_all")
                  else work)
        level = self._level_filter.currentText()
        if level and level != tr("errors.filter_all"):
            subset = subset[subset["_livello"] == level]
        self._populate_rule_filter(subset)
        self._apply_filters()

    def _apply_filters(self) -> None:
        work = getattr(self, "_enriched", pd.DataFrame())
        if work.empty:
            return
        # Rebuilding the same slice of a corpus-sized findings table on every visit, and then
        # handing the table a new object so that it resized all its columns
        # again, was the whole cost of a second visit to this page. The three
        # combo boxes and the enriched frame are the only things it depends on.
        from ..i18n import T as _lang
        chosen = (id(work), self._family_filter.currentText(),
                  self._level_filter.currentText(), self._rule_filter.currentData(),
                  _lang.language)
        if getattr(self, "_filter_key", None) == chosen:
            self._table.set_dataframe(self._filter_view)
            self._table.select_first()
            return

        mask = pd.Series(True, index=work.index)
        family = self._family_filter.currentText()
        if family and family != tr("errors.filter_all"):
            mask &= work["_famiglia"] == family
        level = self._level_filter.currentText()
        if level and level != tr("errors.filter_all"):
            mask &= work["_livello"] == level
        rule = self._rule_filter.currentData()
        if rule and "rule_id" in work.columns:
            mask &= work["rule_id"].astype(str) == str(rule)

        filtered = work[mask]
        self._filtered = filtered
        columns = [column for column in DISPLAY_COLUMNS if column in filtered.columns]
        portate = [column for column in CARRIED_COLUMNS
                   if column in filtered.columns and column not in columns]
        extra = [column for column in ("_famiglia", "_livello", "_trattamento")
                 if column in filtered.columns]
        view = filtered[extra + columns + portate].rename(
            columns={"_famiglia": "famiglia", "_livello": "classe diagnostica",
                     "_trattamento": "trattamento",
                     "anomaly_name": "controllo diagnostico"})
        self._filter_key = chosen
        self._filter_view = view
        self._table.set_dataframe(view)
        self._table.select_first()

    def _howto_row(self, key: str) -> QWidget:
        """The “How to read this table” button and the box it opens.

        The box is created closed: the same explanations are already in the tooltip of
        each header, and a tab that opens with a wall of definitions is read by nobody.
        """
        guida = QLabel(guida_html(key))
        guida.setWordWrap(True)
        guida.setTextFormat(Qt.TextFormat.RichText)
        guida.setObjectName("hint")
        guida.setVisible(False)
        self._variation_guides[key] = guida

        bottone = ghost_button(tr("vartab.howto"))
        bottone.setCheckable(True)
        bottone.toggled.connect(
            lambda aperto, k=key, b=bottone: self._mostra_guida(k, b, aperto))
        self._variation_howto.append(bottone)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.addWidget(bottone)
        riga.addStretch(1)
        contenitore = QWidget()
        contenitore.setLayout(riga)
        return contenitore

    def _mostra_guida(self, key: str, bottone, aperto: bool) -> None:
        self._variation_guides[key].setVisible(aperto)
        bottone.setText(tr("vartab.howto.close") if aperto
                        else tr("vartab.howto"))

    def _render_variation(self) -> None:
        """Fill the inconsistency tabs, hiding the card when nothing was run."""
        sources: dict[str, pd.DataFrame] = dict(self.state.variation)

        any_data = False
        for key, table in self._variation_tables.items():
            frame = sources.get(key, pd.DataFrame())
            table.set_dataframe(frame)
            # A tab without rows stays clickable. Disabling it would make it mute:
            # whoever clicked would get nothing and would not understand why. An empty
            # table says “I found nothing here”, which is information.
            index = list(self._variation_tables).index(key)
            self._variation_tabs.setTabEnabled(index, True)
            any_data = any_data or not frame.empty
        self._variation_card.setVisible(any_data)

    def _show_detail(self, row) -> None:
        self._detail.show_row(row, self.state.tokens)


class _DetailPanel(QWidget):
    """The right-hand panel: the sentence, the values, the explanation.

    Everything in here scrolls, and that is the whole design.  The panel used
    to be a plain column of labels inside the splitter, which meant its height
    was whatever the splitter gave it and anything past that simply was not
    drawn: a Thucydidean period ran off the bottom of the box with no way to
    reach the rest of it, and the explanation of a καί — the longest text the
    program writes — was cut off in the middle of the sentence that said why
    the finding was there.  A panel whose job is to show you the passage cannot
    be a panel that hides the passage.

    Two things do it.  The contents live inside a ``QScrollArea`` with
    ``setWidgetResizable(True)``, so the column grows to whatever the text
    needs and the panel scrolls to it; and every label is given
    ``minimumHeight`` control back by leaving its size policy alone, because a
    word-wrapped ``QLabel`` in a scroll area reports the height its text
    actually occupies only when the width is fixed first — which is what
    ``setWidgetResizable`` guarantees.
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
        self._area = area

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 0, 6, 12)
        layout.setSpacing(12)

        self._placeholder = paragraph(tr("errors.select_row"), "hint")
        layout.addWidget(self._placeholder)

        self._sentence_title = heading(tr("errors.context"), "panelSection")
        self._sentence = QLabel("")
        self._sentence.setWordWrap(True)
        self._sentence.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._sentence.setStyleSheet(
            f"background:{CARD}; border:1px solid {LINE};"
            f"border-left:3px solid {ACCENT}; padding:13px 16px;"
            "border-radius:7px; font-family:'GFS Didot','Palatino Linotype',serif;"
            "font-size:17px; line-height:180%;")

        self._values = QLabel("")
        self._values.setWordWrap(True)
        self._values.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        self._what_title = heading(tr("errors.what"), "panelSection")
        self._what = QLabel("")
        self._what.setWordWrap(True)
        self._what.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        # The diagnosis of the single occurrence is the richest field of the program,
        # and it is shown on screen and not only in the exported CSV: the description of
        # the catalogue repeated by the panel is the same for all the rows of the same
        # rule, while whoever reviews needs to know why *this* row.
        self._diagnosis_title = heading(tr("errors.diagnosis"), "panelSection")
        self._diagnosis = QLabel("")
        self._diagnosis.setWordWrap(True)
        self._diagnosis.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        # The occurrences behind the finding.
        #
        # Some checks speak of a type and not of a record: “this form appears with two
        # lemmas”, “this lemma never carries a case”. For those the selected row is only
        # a representative, and whoever reads cannot correct anything until they see
        # which readings compete, how many times each occurs and where to read them.
        # This table shows it, and sits inside the area that already scrolls.
        self._evidence_title = heading(tr("errors.evidence"), "panelSection")
        self._evidence = QLabel("")
        self._evidence.setWordWrap(True)
        self._evidence.setTextFormat(Qt.TextFormat.RichText)
        self._evidence.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        for widget in (self._sentence_title, self._sentence, self._values,
                       self._what_title, self._what,
                       self._diagnosis_title, self._diagnosis,
                       self._evidence_title, self._evidence):
            # A word-wrapped label must be allowed to become as tall as its
            # text; the default policy lets a cramped layout squash it, and a
            # squashed label paints the first line and drops the rest.
            widget.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.MinimumExpanding)
            layout.addWidget(widget)
            widget.setVisible(False)
        layout.addStretch(1)

    def retranslate(self) -> None:
        """The little titles of the panel, and the line that invites the user to choose."""
        self._placeholder.setText(tr("errors.select_row"))
        self._sentence_title.setText(tr("errors.context"))
        self._what_title.setText(tr("errors.what"))
        self._diagnosis_title.setText(tr("errors.diagnosis"))
        self._evidence_title.setText(tr("errors.evidence"))

    def show_row(self, row, tokens: pd.DataFrame) -> None:
        from greek_corpus_pipeline.agdt_schema import describe_postag, describe_relation
        from greek_corpus_pipeline.rule_catalog import rule_description

        visible = row is not None
        self._placeholder.setVisible(not visible)
        for widget in (self._sentence_title, self._sentence, self._values,
                       self._what_title, self._what,
                       self._diagnosis_title, self._diagnosis):
            widget.setVisible(visible)
        if not visible:
            self._evidence_title.setVisible(False)
            self._evidence.setVisible(False)
            return

        # A new finding starts at the top of the panel, not wherever the
        # previous one was scrolled to.
        self._area.verticalScrollBar().setValue(0)
        self._sentence.setText(_sentence_with_marker(row, tokens))

        # “nan” is how pandas writes “missing field”: it is not a lemma of the corpus
        # and must not appear on screen. An empty field is stated as such.
        def _value(*keys) -> str:
            for key in keys:
                if key in row:
                    value = row.get(key)
                    if value is None or pd.isna(value):
                        return ""
                    text = str(value).strip()
                    if text.lower() in ("nan", "<na>", "none"):
                        return ""
                    return text
            return ""

        def _shown(text: str) -> str:
            return text if text else (
                f"<i style='color:{MUTED}'>{tr('errors.empty_field')}</i>")

        form = _value("forma", "form")
        lemma = _value("lemma")
        postag = _value("postag")
        relation = _value("relazione", "relation")
        head = _value("testa", "head")
        if not head:
            head = _testa_dai_token(row, tokens)
        testa_forma = _forma_della_testa(row, tokens, head)
        mono = "font-family:monospace"
        etichetta = f"color:{MUTED}"
        righe = [f"<div><span style='{etichetta}'>{tr('errors.field.form')}</span> "
                 f"<span style='font-size:19px; font-family:{GREEK_HTML}; "
                 f"color:{ACCENT_DARK}'><b>{_shown(form)}</b></span></div>",
                 f"<div><span style='{etichetta}'>{tr('errors.field.postag')}</span> "
                 f"<span style='{mono}'>{_shown(postag)}</span>"
                 + (f"<br><span style='{etichetta};padding-left:1.2em'>"
                    f"{describe_postag(postag, T.language)}</span>"
                    if postag else "") + "</div>",
                 f"<div><span style='{etichetta}'>{tr('errors.field.lemma')}</span> "
                 f"<i>{_shown(lemma)}</i></div>",
                 f"<div><span style='{etichetta}'>{tr('errors.field.relation')}</span> "
                 f"<span style='{mono}'>{_shown(relation)}</span>"
                 + (f"<br><span style='{etichetta};padding-left:1.2em'>"
                    f"{describe_relation(relation, T.language)}</span>"
                    if relation else "") + "</div>",
                 f"<div><span style='{etichetta}'>{tr('errors.field.head')}</span> "
                 f"<span style='{mono}'>{_shown(head)}</span>"
                 + (f" <span style='{etichetta}'>({testa_forma})</span>"
                    if testa_forma else "") + "</div>"]
        self._values.setText("".join(righe))

        rule_id = str(row.get("rule_id", "") or "")

        # “What it checks” gives the definition of the check, as it stands in the
        # catalogue and in the reference table: the same sentence, always, for the same
        # anomaly. The catalogue carries it in the two languages.
        self._what.setText(rule_description(rule_id, T.language) if rule_id else "—")

        # “What does not fit in this occurrence” says what this row shows, and changes
        # from one occurrence to another. It is recomposed from key and parameters in
        # the current language; a run saved before the key existed shows the sentence
        # that it has.
        self._diagnosis.setText(_diagnosi(row))

        self._show_evidence(rule_id, row, tokens, form, lemma)



    def _show_evidence(self, rule_id: str, row, tokens: pd.DataFrame,
                       form: str, lemma: str) -> None:
        """All the readings of the word in question, with the counts."""
        from greek_corpus_pipeline.evidence import grouping_field, readings

        field = grouping_field(rule_id)
        value = lemma if field == "lemma" else form
        if not value or tokens is None or tokens.empty:
            self._evidence_title.setVisible(False)
            self._evidence.setVisible(False)
            return
        table, resto = readings(tokens, value, field, lingua=T.language)
        if table.empty:
            self._evidence_title.setVisible(False)
            self._evidence.setVisible(False)
            return

        what = tr("errors.evidence.this_lemma" if field == "lemma"
                  else "errors.evidence.this_form")
        righe = [
            "<div style='color:#5a6472;margin-bottom:6px'>"
            + tr("errors.evidence.intro", what, value) + "</div>",
            "<table cellspacing='0' cellpadding='4' width='100%' "
            "style='border-collapse:collapse'>",
            "<tr style='background:#e8ecf2'>"
            f"<th align='left'>{data_label('lemma')}</th>"
            f"<th align='left'>{data_label('etichetta')}</th>"
            f"<th align='left'>{data_label('relazione')}</th>"
            f"<th align='right'>{data_label('occorrenze')}</th>"
            f"<th align='left'>{tr('errors.evidence.example')}</th></tr>",
        ]
        selected_lemma = lemma
        selected_tag = str(row.get("postag", "") or "")
        for record in table.itertuples(index=False):
            questa = (str(record.lemma) == selected_lemma
                      and str(record.postag) == selected_tag)
            stile = (f"background:{ACCENT_PICK};font-weight:bold" if questa
                     else f"border-top:1px solid {LINE}")
            righe.append(
                f"<tr style='{stile}'>"
                f"<td>{record.lemma or '—'}</td>"
                f"<td style='font-family:monospace'>{record.postag or '—'}</td>"
                f"<td>{record.relation or '—'}</td>"
                f"<td align='right'>{int(record.occorrenze)}</td>"
                f"<td style='color:#5a6472'>{record.esempio}</td></tr>")
        righe.append("</table>")
        if resto:
            righe.append(
                "<div style='color:#8a6d1f;margin-top:6px'>"
                + tr("errors.evidence.more", resto) + "</div>")
        self._evidence.setText("".join(righe))
        self._evidence_title.setVisible(True)
        self._evidence.setVisible(True)


def _diagnosi(row) -> str:
    """The sentence of this finding, in the language of the interface.

    No proposed value: the proposed correction is read at the “Correct” step, where it
    is decided whether to apply it. Here it says what does not fit.
    """
    from greek_corpus_pipeline.issue_testi import rendi

    chiave = row.get("issue_key") if hasattr(row, "get") else None
    if chiave is not None and not pd.isna(chiave) and str(chiave).strip():
        parametri = row.get("issue_params")
        if parametri is None or (not isinstance(parametri, str) and pd.isna(parametri)):
            parametri = ""
        testo = rendi(str(chiave), str(parametri), T.language, row)
        if testo:
            return testo
    scritta = row.get("issue") if hasattr(row, "get") else None
    if scritta is None or pd.isna(scritta):
        return "—"
    testo = str(scritta).strip()
    return testo if testo and testo.lower() not in ("nan", "<na>", "none") else "—"


def _riga_dei_token(row, tokens: pd.DataFrame):
    """The corpus record that the finding comes from."""
    if tokens is None or tokens.empty:
        return None
    for chiave in ("document_id", "sentence_id", "token_id"):
        if chiave not in tokens.columns or chiave not in row:
            return None
    mask = ((tokens["document_id"].astype(str) == str(row.get("document_id")))
            & (tokens["sentence_id"].astype(str) == str(row.get("sentence_id")))
            & (tokens["token_id"].astype(str) == str(row.get("token_id"))))
    trovati = tokens[mask]
    return None if trovati.empty else trovati.iloc[0]


def _testa_dai_token(row, tokens: pd.DataFrame) -> str:
    """The syntactic head, which the table of findings does not carry."""
    record = _riga_dei_token(row, tokens)
    if record is None or "head" not in record:
        return ""
    valore = record["head"]
    if valore is None or pd.isna(valore):
        return ""
    testo = str(valore).strip()
    if testo.lower() in ("nan", "<na>", "none"):
        return ""
    # pandas reads the head as a floating-point number: “10.0” is not an identifier, it
    # is an artefact of reading.
    try:
        return str(int(float(testo)))
    except (TypeError, ValueError):
        return testo


def _forma_della_testa(row, tokens: pd.DataFrame, head: str) -> str:
    """The word on which the token depends: a number alone says nothing."""
    if not head or tokens is None or tokens.empty:
        return ""
    try:
        numero = str(int(float(head)))
    except (TypeError, ValueError):
        return ""
    if numero == "0":
        return "radice della frase"
    mask = ((tokens["document_id"].astype(str) == str(row.get("document_id")))
            & (tokens["sentence_id"].astype(str) == str(row.get("sentence_id")))
            & (tokens["token_id"].astype(str).map(
                lambda v: v.split(".")[0] if v else v) == numero))
    trovati = tokens[mask]
    if trovati.empty:
        return ""
    forma = trovati.iloc[0].get("form")
    return "" if forma is None or pd.isna(forma) else str(forma)


def _sentence_with_marker(row, tokens: pd.DataFrame) -> str:
    """The whole sentence, with the token in question in square brackets."""
    if tokens is None or tokens.empty:
        return str(row.get("forma", row.get("form", "")))
    document = row.get("document_id")
    sentence = row.get("sentence_id")
    token_id = row.get("token_id")
    if document is None or sentence is None:
        return str(row.get("forma", row.get("form", "")))

    mask = ((tokens["document_id"].astype(str) == str(document))
            & (tokens["sentence_id"].astype(str) == str(sentence)))
    subset = tokens[mask]
    if subset.empty:
        return str(row.get("forma", row.get("form", "")))
    subset = subset.sort_values("token_index")

    pieces = []
    for record in subset.itertuples(index=False):
        text = "" if pd.isna(record.form) else str(record.form)
        if token_id is not None and str(record.token_id) == str(token_id):
            # The chosen record is not in square brackets but on a pink background:
            # square brackets in a Greek text are already a philological sign, and
            # adding a pair that mean something else in the middle of an edited sentence
            # is the quickest way to make people misread.
            pieces.append(
                f"<span style='background:{ACCENT_PICK}; color:{ACCENT_DARK};"
                f"font-weight:700'>&nbsp;{text}&nbsp;</span>")
        else:
            pieces.append(text)
    return " ".join(pieces)
