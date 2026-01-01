"""Step 2 — what is actually in the corpus that was just loaded.

The numbers first, then what the filter leaves out, then the composition. The
composition tables are the reason the metadata catalogue exists: without them a
treebank is a pile of files with opaque names, and questions about period,
genre or dialect cannot even be asked.

Two things here are deliberate and easy to undo by accident.

*The three exclusion counts are always on screen*, filter on or filter off.
Switched on, the number says how many records are being left out of the
diagnosis; switched off, it says how many there are and stay in, and the label
says which of the two it is. A page that showed «0 nodi ellittici esclusi»
because the user had not switched the filter on would be telling them there are
none, which is a different statement and usually a false one.

*``locus`` and ``editore`` are dropped at display time*, not at the source.
They come out of the metadata catalogue (``corpus_metadata``), which other
things read; the tables here simply do not show them.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QTabWidget, QWidget

from ..i18n import number, tr
from ..widgets import (
    Card, DataTable, MetricGrid, ghost_button, notice, paragraph, primary_button,
)
from ..workers import EXCLUSION_KINDS, excluded_counts
from .base import Page


#: (key of the table, key of its label)
TABS = [
    ("author", "overview.by_author"),
    ("document", "overview.by_document"),
    ("period", "overview.by_period"),
    ("genre", "overview.by_genre"),
    ("dialect", "overview.by_dialect"),
]

#: Columns of the metadata catalogue that the overview does not show. They are not wrong
#: — the locus and the editor are in the CSVs and serve whoever builds the metadata — but
#: here they widen every table without answering any of the questions that the overview
#: poses, so they are kept out of the way. They are removed on a copy, at the moment of
#: drawing: the catalogue stays what it is.
HIDDEN_COLUMNS = ("locus", "editore")

#: (name of the count, option that activates it), taken from ``workers`` instead of
#: rewritten here: the three numbers must be the same three that the filter of the
#: diagnosis removes, and a copied list is a list that sooner or later diverges.
EXCLUSION_LABELS = tuple((name, option) for name, option, _test in EXCLUSION_KINDS)


def _thousands(value: object) -> str:
    """1234567 → “1.234.567”, the way a number is written in Italian."""
    try:
        return number(int(value))
    except (TypeError, ValueError):
        return str(value)


def _shown(frame: pd.DataFrame | None) -> pd.DataFrame:
    """The table without the columns that the overview does not show."""
    if frame is None:
        return pd.DataFrame()
    drop = [column for column in HIDDEN_COLUMNS if column in frame.columns]
    return frame.drop(columns=drop) if drop else frame


class OverviewPage(Page):

    title_key = "overview.title"
    intro_key = "overview.intro"

    def build(self) -> None:
        self._empty = notice(tr("step.locked"), "info")
        self.add(self._empty)

        self._metrics = MetricGrid(5)
        self.add(self._metrics)

        # ── What the filter leaves out ──────────────────────────────────
        self._excluded_card = Card(tr("overview.excluded"))
        self._excluded_hint = paragraph(tr("overview.excluded.hint"), "hint")
        self._excluded_card.add(self._excluded_hint)
        self._excluded_grid = MetricGrid(3)
        self._excluded_card.add(self._excluded_grid)
        self._excluded_total = paragraph("", "hint")
        self._excluded_card.add(self._excluded_total)
        self.add(self._excluded_card)
        #: The last count received, to redraw it when the language changes.
        self._excluded: dict | None = None

        # CoNLL-U conversion belongs here, not only in the correction step: it
        # is a format conversion, it needs nothing but a loaded corpus, and a
        # user who wants to hand the treebank to a UD tool should not have to
        # run a diagnosis first to find the button.
        self._conllu_button = primary_button(tr("overview.conllu"))
        self._conllu_button.setToolTip(tr("review.export_conllu.hint"))
        self._conllu_button.clicked.connect(self._export_conllu)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._conllu_button)
        # The manifest: units, denominators, lists with their fingerprint, version and
        # configuration. A number without its provenance cannot be checked.
        self._manifest_button = ghost_button(tr("overview.manifest"))
        self._manifest_button.setToolTip(tr("overview.manifest.hint"))
        self._manifest_button.clicked.connect(self._export_manifest)
        layout.addWidget(self._manifest_button)
        self._manifest_esito = paragraph("", "hint")
        layout.addWidget(self._manifest_esito)
        layout.addStretch(1)
        self._conllu_row = row
        self.add(row)

        self._tabs = QTabWidget()
        self._tables: dict[str, DataTable] = {}
        for key, label_key in TABS:
            table = DataTable(min_height=340)
            self._tables[key] = table
            container = Card()
            container.add(table, 1)
            self._tabs.addTab(container, tr(label_key))
        self.add(self._tabs, 1)

        self._unmatched_card = Card(tr("overview.unmatched"))
        self._unmatched_hint = paragraph(tr("overview.unmatched_hint"), "hint")
        self._unmatched_card.add(self._unmatched_hint)
        self._unmatched = DataTable(min_height=140, column_picker=False)
        self._unmatched_card.add(self._unmatched, 1)
        self.add(self._unmatched_card)

    def retranslate(self) -> None:
        self._empty.setText(tr("step.locked"))
        self._conllu_button.setText(tr("overview.conllu"))
        self._conllu_button.setToolTip(tr("review.export_conllu.hint"))
        self._manifest_button.setText(tr("overview.manifest"))
        self._manifest_button.setToolTip(tr("overview.manifest.hint"))
        self._excluded_card.set_title(tr("overview.excluded"))
        self._excluded_hint.setText(tr("overview.excluded.hint"))
        for index, (_key, label_key) in enumerate(TABS):
            self._tabs.setTabText(index, tr(label_key))
        self._unmatched_card.set_title(tr("overview.unmatched"))
        self._unmatched_hint.setText(tr("overview.unmatched_hint"))
        super().retranslate()

    def _export_manifest(self) -> None:
        """Writes the provenance of what the window is showing."""
        import json

        from PyQt6.QtWidgets import QFileDialog

        from greek_corpus_pipeline import manifest as manifest_module
        from greek_corpus_pipeline.model_support import (
            default_stanza_model_dir, default_udpipe_model_path,
            stanza_identity, udpipe_identity,
        )
        from ..i18n import T

        if not self.state.has_corpus:
            return
        percorso, _ = QFileDialog.getSaveFileName(
            self, tr("overview.manifest"), "manifest.json", "JSON (*.json)")
        if not percorso:
            return
        if not percorso.lower().endswith(".json"):
            percorso += ".json"

        modelli = {}
        for etichetta, identita, radice in (
                ("stanza", stanza_identity, default_stanza_model_dir(self.state.workspace)),
                ("udpipe", udpipe_identity, default_udpipe_model_path(self.state.workspace))):
            versione, risorse = identita(radice)
            modelli[etichetta] = self.state.model_status(
                etichetta, versione=versione, risorse=risorse)

        documento = manifest_module.build(
            corpus_name=self.state.corpus_name,
            run_id=self.state.run_id or "",
            tokens=self.state.tokens,
            unita=self.state.units(),
            filtri=self.state.filter_options,
            findings=self.state.findings,
            modelli=modelli,
            lingua=T.language,
        )
        Path(percorso).write_text(
            json.dumps(documento, ensure_ascii=False, indent=1), encoding="utf-8")
        self._manifest_esito.setText(tr("overview.manifest.done", Path(percorso).name))
        self.logMessage.emit(tr("overview.manifest.done", percorso))

    def _export_conllu(self) -> None:
        tokens = self.state.tokens
        if tokens is None or tokens.empty:
            return
        folder = QFileDialog.getExistingDirectory(self, tr("overview.conllu"))
        if not folder:
            return
        from greek_corpus_pipeline.conllu import export_conllu

        written = export_conllu(tokens, folder,
                                corpus_name=str(self.state.run_id or ""),
                                per_file=True)
        QMessageBox.information(
            self, tr("overview.conllu"),
            tr("overview.conllu.done").format(n=len(written), path=folder))

    def refresh(self) -> None:
        tokens = self.state.tokens
        has_corpus = not tokens.empty
        self._empty.setVisible(not has_corpus)
        self._metrics.setVisible(has_corpus)
        self._excluded_card.setVisible(has_corpus)
        self._tabs.setVisible(has_corpus)
        self._conllu_row.setVisible(has_corpus)
        if not has_corpus:
            self._unmatched_card.setVisible(False)
            self._excluded = None
            return

        self._refresh_excluded(tokens)

        # Five composition tables over 625,176 tokens — three group counts and
        # two catalogue joins — take about 3.3 s, so they are keyed on the token
        # table itself, computed off the Qt thread and recomputed only when it
        # changes: the window keeps repainting, and showing the page again costs
        # nothing.
        ready = self.state.cache_peek("overview_tables", tokens)
        if ready is not None:
            self._apply_tables(ready)
            return
        waiting = tr("table.computing")
        for table in self._tables.values():
            table.show_waiting(waiting)
        self._unmatched_card.setVisible(False)
        self.compute_in_background(
            "overview_tables",
            lambda frame=tokens: self._compute_tables(frame),
            self._apply_tables)

    # ── What the filter leaves out ─────────────────────────────────────
    def _filter_signature(self) -> str:
        """The three boxes of the loading page, as a string.

        It is part of the cache key because the excluded total — the union of the
        categories switched on — changes when the user changes their mind about the
        boxes, while the corpus stays the same.
        """
        options = self.state.filter_options or {}
        return "|".join(f"{name}={int(bool(options.get(option)))}"
                        for name, option in EXCLUSION_LABELS)

    def _refresh_excluded(self, tokens: pd.DataFrame) -> None:
        name = f"overview_excluded::{self._filter_signature()}"
        ready = self.state.cache_peek(name, tokens)
        if ready is not None:
            self._apply_excluded(ready)
            return
        options = dict(self.state.filter_options or {})
        if self._excluded is None:
            self._excluded_total.setText(tr("table.computing"))

        def compute(frame=tokens, choices=options) -> dict:
            counts = excluded_counts(frame, choices)
            self.state.cache[name] = (self.state.signature(frame), counts)
            return counts

        self.compute_in_background("overview_excluded", compute,
                                   self._apply_excluded)

    def _apply_excluded(self, counts: dict) -> None:
        if not isinstance(counts, dict):
            return
        self._excluded = counts
        options = self.state.filter_options or {}
        rows: list[tuple[str, object]] = []
        for name, option in EXCLUSION_LABELS:
            state = "on" if options.get(option) else "off"
            rows.append((tr(f"overview.excluded.{name}.{state}"),
                         int(counts.get(name, 0))))
        self._excluded_grid.set_metrics(rows)

        # The explanation of what ends up in each count is in the box, not on the page:
        # there are three lines of criteria for each, and on the page they would drown
        # the numbers.
        grid = self._excluded_grid.layout()
        for index, (name, _option) in enumerate(EXCLUSION_LABELS):
            item = grid.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setToolTip(tr(f"overview.excluded.{name}.tip"))

        total = _thousands(counts.get("total", 0))
        removed = int(counts.get("removed", 0))
        self._excluded_total.setText(
            tr("overview.excluded.total", _thousands(removed), total) if removed
            else tr("overview.excluded.none", total))

    # ── The composition tables ─────────────────────────────────────────
    def _compute_tables(self, tokens: pd.DataFrame) -> dict:
        """The composition tables. Runs on a worker thread."""
        from greek_corpus_pipeline import corpus_metadata, stats

        tables = {
            "author": self.state.cached(
                "author_catalogue",
                lambda: corpus_metadata.author_catalogue(tokens), tokens),
            "document": self.state.cached(
                "document_catalogue",
                lambda: corpus_metadata.document_catalogue(tokens), tokens),
        }
        for key, column in (("period", "periodo"), ("genre", "genere"),
                            ("dialect", "dialetto")):
            tables[key] = (stats.counts_by_group(tokens, column)
                           if column in tokens.columns else pd.DataFrame())
        tables["_unmatched"] = corpus_metadata.unmatched_documents(tokens)
        # A single copy, made here and cached: ``DataTable`` recognises that it has
        # already received the same object and redraws nothing, and cutting the columns
        # at every refresh would take that shortcut away from it.
        for key, table in list(tables.items()):
            tables[key] = _shown(table)

        counts = stats.basic_counts(tokens)
        authors = tokens["autore"].nunique() if "autore" in tokens.columns else 0
        works = tokens["opera"].nunique() if "opera" in tokens.columns else 0
        # The labels remain keys, not words: the table is cached and survives the change
        # of language, so the translation must be done at the moment of drawing it, not
        # at the moment of computing it.
        tables["_metrics"] = {
            "overview.metric.tokens": counts.get("token (tutto)", 0),
            "overview.metric.words": counts.get("token (parole)", 0),
            "overview.metric.sentences": counts.get("frasi", 0),
            "overview.documents": counts.get("documenti", 0),
            "overview.authors": int(authors),
            "overview.metric.forms": counts.get("forme distinte", 0),
            "overview.metric.lemmas": counts.get("lemmi distinti", 0),
            "overview.works": int(works),
            "overview.metric.mean_sentence": counts.get("lunghezza media frase", 0),
            "overview.metric.longest_sentence": counts.get("frase più lunga", 0),
        }
        self.state.cache["overview_tables"] = (self.state.signature(tokens), tables)
        return tables

    def _apply_tables(self, tables: dict) -> None:
        metrics = tables.get("_metrics")
        if metrics:
            self._metrics.set_metrics([(tr(key), value)
                                       for key, value in metrics.items()])
        for key, table in self._tables.items():
            table.set_dataframe(tables.get(key, pd.DataFrame()))
        unmatched = tables.get("_unmatched", pd.DataFrame())
        self._unmatched_card.setVisible(not unmatched.empty)
        if not unmatched.empty:
            self._unmatched.set_dataframe(unmatched)
