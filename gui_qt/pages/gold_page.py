"""Step 10 — the gold standard corrected by the user: the result only.

This page decides nothing. The decisions are taken at step 5, one at a time, and
they stay there: here there is no proposal to accept, no list of rules, no
dictionary to load. Whoever arrives here has already corrected, and wants to
know what has come into their hands. The division is deliberate, because a page
that is a copy of another forces one to ask every time which of the two is the
one that counts.

Four jobs, all on the result and none on the decision.

First: **look at what has changed**. One row per changed word, with the value
before and the one after. It is the only place in the program where this table
lives, and nothing needs to be pressed to see it: if a corrected corpus exists,
the count of the differences is already there.

Second: **export**. Three buttons, three formats, and what comes out is always
and only the corrected corpus — not the original, not a version left in memory
from before the last correction. If there is no correction the program says so
and asks for confirmation, because exporting a copy identical to the original
and calling it a gold standard is something that is done by mistake.

Third: **keep**. A gold scattered over three files inside the working folder is
not something that can be set aside or sent to a colleague. The save button
makes a single file of it, which the load button puts back into a run without
losing anything.

Fourth: **compare**, behind a separate button because it is a different
question from the others: how much do Stanza and UDPipe agree with the original
corpus, and how much with the corrected corpus? The second measure does not say
that the model has improved — the model has not been touched — but that the
yardstick has changed.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..i18n import tr
from ..widgets import (
    Card, DataTable, MetricGrid, ghost_button, notice, paragraph, primary_button,
)
from .base import Page


def _text(values: pd.Series) -> pd.Series:
    return values.astype("string").fillna("").astype(str)


class GoldPage(Page):

    title_key = "gold.title"
    intro_key = "gold.intro"
    howto_keys = ("gold.howto.1", "gold.howto.2")

    # ── Building the page ──────────────────────────────────────────────
    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        # The warning “you have not applied anything yet” carries the way to remedy it
        # with it: the place where one decides is another, and saying so without giving
        # the means to go there is half the information.
        self._state_box = QWidget()
        state_layout = QVBoxLayout(self._state_box)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(8)
        self._state_notice = notice("", "warn")
        state_layout.addWidget(self._state_notice)
        state_row = QHBoxLayout()
        self._goto_review = ghost_button(tr("gold.goto_review"))
        self._goto_review.clicked.connect(
            lambda: self.requestNavigate.emit("review"))
        state_row.addWidget(self._goto_review)
        state_row.addStretch(1)
        state_layout.addLayout(state_row)
        self._state_box.setVisible(False)
        self.add(self._state_box)

        self._metrics = MetricGrid(3)
        self.add(self._metrics)

        self._export_card = Card(tr("gold.export.title"))
        export_card = self._export_card
        self._export_hint = paragraph(tr("gold.export.hint"), "hint")
        export_card.add(self._export_hint)
        row = QHBoxLayout()
        self._export_xml = primary_button(tr("gold.export.xml"))
        self._export_xml.clicked.connect(self._do_export_xml)
        self._export_csv = primary_button(tr("gold.export.csv"))
        self._export_csv.clicked.connect(self._do_export_csv)
        self._export_conllu = primary_button(tr("gold.export.conllu"))
        self._export_conllu.clicked.connect(self._do_export_conllu)
        for button in (self._export_xml, self._export_csv, self._export_conllu):
            row.addWidget(button)
        row.addStretch(1)
        export_card.add_layout(row)
        self._export_status = QLabel("")
        self._export_status.setObjectName("hint")
        export_card.add(self._export_status)
        self.add(export_card)

        self._keep_card = Card(tr("gold.keep.title"))
        keep_card = self._keep_card
        self._keep_hint = paragraph(tr("gold.keep.hint"), "hint")
        keep_card.add(self._keep_hint)
        keep_row = QHBoxLayout()
        self._save_bundle = ghost_button(tr("gold.keep.save"))
        self._save_bundle.clicked.connect(self._do_save_bundle)
        self._load_bundle = ghost_button(tr("gold.keep.load"))
        self._load_bundle.clicked.connect(self._do_load_bundle)
        keep_row.addWidget(self._save_bundle)
        keep_row.addWidget(self._load_bundle)
        keep_row.addStretch(1)
        keep_card.add_layout(keep_row)
        self._keep_status = QLabel("")
        self._keep_status.setObjectName("hint")
        keep_card.add(self._keep_status)
        self.add(keep_card)

        self._compare_card = Card(tr("gold.compare.title"))
        compare_card = self._compare_card
        self._compare_hint = paragraph(tr("gold.compare.hint"), "hint")
        compare_card.add(self._compare_hint)
        compare_row = QHBoxLayout()
        self._compare = primary_button(tr("gold.compare.open"))
        self._compare.clicked.connect(self._do_compare)
        compare_row.addWidget(self._compare)
        compare_row.addStretch(1)
        compare_card.add_layout(compare_row)
        self._compare_status = QLabel("")
        self._compare_status.setObjectName("hint")
        compare_card.add(self._compare_status)
        self.add(compare_card)

        self._tabs = QTabWidget()

        diff_page = QWidget()
        diff_layout = QVBoxLayout(diff_page)
        diff_layout.setContentsMargins(16, 16, 16, 16)
        self._diff_hint = paragraph(tr("gold.tab.diff.hint"), "hint")
        diff_layout.addWidget(self._diff_hint)
        self._diff_empty = notice(tr("gold.diff.none"), "info")
        self._diff_empty.setVisible(False)
        diff_layout.addWidget(self._diff_empty)
        self._diff_table = DataTable(min_height=300)
        diff_layout.addWidget(self._diff_table, 1)
        self._tabs.addTab(diff_page, tr("gold.tab.diff"))

        models_page = QWidget()
        models_layout = QVBoxLayout(models_page)
        models_layout.setContentsMargins(16, 16, 16, 16)
        self._models_hint = paragraph(tr("gold.tab.models.hint"), "hint")
        models_layout.addWidget(self._models_hint)
        self._models_table = DataTable(min_height=240, column_picker=False)
        models_layout.addWidget(self._models_table, 1)
        self._tabs.addTab(models_page, tr("gold.tab.models"))

        self.add(self._tabs, 1)
        self._tabs.setVisible(False)

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        self._locked.setText(tr("step.locked"))
        self._goto_review.setText(tr("gold.goto_review"))
        self._export_card.set_title(tr("gold.export.title"))
        self._export_hint.setText(tr("gold.export.hint"))
        self._export_xml.setText(tr("gold.export.xml"))
        self._export_csv.setText(tr("gold.export.csv"))
        self._export_conllu.setText(tr("gold.export.conllu"))
        self._keep_card.set_title(tr("gold.keep.title"))
        self._keep_hint.setText(tr("gold.keep.hint"))
        self._save_bundle.setText(tr("gold.keep.save"))
        self._load_bundle.setText(tr("gold.keep.load"))
        self._compare_card.set_title(tr("gold.compare.title"))
        self._compare_hint.setText(tr("gold.compare.hint"))
        self._compare.setText(tr("gold.compare.open"))
        self._diff_hint.setText(tr("gold.tab.diff.hint"))
        self._diff_empty.setText(tr("gold.diff.none"))
        self._models_hint.setText(tr("gold.tab.models.hint"))
        self._tabs.setTabText(0, tr("gold.tab.diff"))
        self._tabs.setTabText(1, tr("gold.tab.models"))
        super().retranslate()

    # ── State ──────────────────────────────────────────────────────────
    def _gold_state(self):
        from greek_corpus_pipeline.gold import gold_state
        return gold_state(self.state.tokens, self.state.corrected_tokens,
                          self._manual(), self.state.token_diff)

    def _manual(self) -> pd.DataFrame:
        from greek_corpus_pipeline.gold import read_manual_corrections
        directory = self._run_directory()
        if directory is None:
            return pd.DataFrame()
        return read_manual_corrections(directory)

    def _run_directory(self) -> Path | None:
        if not self.state.run_id:
            return None
        from greek_corpus_pipeline.storage import run_dir
        return run_dir(self.state.workspace, self.state.run_id)

    def refresh(self) -> None:
        has_corpus = self.state.has_corpus
        self._locked.setVisible(not has_corpus)
        for button in (self._export_xml, self._export_csv, self._export_conllu,
                       self._save_bundle, self._compare):
            button.setEnabled(has_corpus)
        self._load_bundle.setEnabled(bool(self.state.run_id))
        if not has_corpus:
            self._state_box.setVisible(False)
            self._metrics.set_metrics({})
            self._tabs.setVisible(False)
            return

        info = self._gold_state()
        has_corrected = not self.state.corrected_tokens.empty
        if not has_corrected:
            self._state_notice.setText(tr("gold.state.none"))
            self._state_box.setVisible(True)
        elif not info.has_corrections:
            self._state_notice.setText(tr("gold.state.identical"))
            self._state_box.setVisible(True)
        else:
            self._state_box.setVisible(False)

        before = self.state.stats_before or {}
        after = self.state.stats_after or {}
        self._metrics.set_metrics({
            tr("gold.metric.tokens"): len(self.state.tokens),
            tr("gold.metric.manual"): info.manual_corrections,
            tr("gold.metric.changed"): info.changed_tokens,
            tr("gold.metric.share"): f"{100 * info.changed_share:.2f} %",
            tr("gold.metric.missing_before"): before.get("missing_lemmas", 0),
            tr("gold.metric.missing_after"): after.get("missing_lemmas", 0),
        })

        # “What has changed” is the result, and the result is the job of this page: it
        # is here without anything having to be asked, and there is no second copy of
        # the same table in the “Correct” tab.
        self._tabs.setVisible(has_corrected)
        difference = self._difference()
        self._diff_empty.setVisible(has_corrected and difference.empty)
        self._diff_table.set_dataframe(difference)

    # ── What has changed ───────────────────────────────────────────────
    def _difference(self) -> pd.DataFrame:
        """The table of differences as it is read, not as it comes out of the computation.

        ``lemma_original`` and ``lemma_corrected`` are good names for a merge and bad
        ones for whoever reads: here they become “lemma before” and “lemma after”, and
        the empty column — the one where the value has not changed — does not appear.
        """
        difference = self.state.token_diff
        if difference is None or difference.empty:
            return pd.DataFrame()
        view = pd.DataFrame(index=difference.index)
        # The form is the anchor: the word as it was written is always visible, even
        # when only the lemma has changed. Since the form is corrected too, the “after”
        # column appears if needed.
        forma = next((n for n in ("form_original", "form") if n in difference.columns), None)
        if forma is not None:
            view["forma"] = _text(difference[forma])
        if "form_corrected" in difference.columns and forma is not None:
            dopo = _text(difference["form_corrected"])
            if not dopo.equals(view["forma"]):
                view["forma_dopo"] = dopo
        for target, *candidates in (
                ("lemma_prima", "lemma_original", "lemma"),
                ("lemma_dopo", "lemma_corrected"),
                ("etichetta_prima", "postag_original", "postag"),
                ("etichetta_dopo", "postag_corrected")):
            source = next((name for name in candidates
                           if name in difference.columns), None)
            if source is not None:
                view[target] = _text(difference[source])
        for target, source in (("documento", "document_id"),
                               ("frase", "sentence_id"),
                               ("parola_n", "token_id")):
            if source in difference.columns:
                view[target] = difference[source]
        # A column in which before and after coincide on all the rows says nothing: if
        # only the lemmas have changed, the two columns of the label are noise.
        for prima, dopo in (("lemma_prima", "lemma_dopo"),
                            ("etichetta_prima", "etichetta_dopo")):
            if prima in view.columns and dopo in view.columns \
                    and view[prima].equals(view[dopo]):
                view = view.drop(columns=[prima, dopo])
        return view.reset_index(drop=True)

    # ── Exports ────────────────────────────────────────────────────────
    def _corrected(self) -> pd.DataFrame | None:
        """The corpus to export: the corrected one, and nothing else.

        If the corrections have never been applied there is no corrected corpus, and
        returning the original under that name would be the worst lie this page could
        tell. Better to stop and explain.
        """
        corrected = self.state.corrected_tokens
        if corrected is None or corrected.empty:
            QMessageBox.information(
                self, tr("gold.title"), tr("gold.msg.not_applied"))
            return None
        return corrected

    def _confirm_if_unchanged(self) -> bool:
        """If the gold is identical to the original, say so and ask for confirmation."""
        info = self._gold_state()
        if info.has_corrections:
            return True
        answer = QMessageBox.question(
            self, tr("gold.title"), tr("gold.msg.identical_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _ready(self) -> pd.DataFrame | None:
        corrected = self._corrected()
        if corrected is None:
            return None
        if not self._confirm_if_unchanged():
            return None
        return corrected

    def _do_export_xml(self) -> None:
        corrected = self._ready()
        if corrected is None:
            return
        directory = QFileDialog.getExistingDirectory(self, tr("gold.export.xml"))
        if not directory:
            return
        from greek_corpus_pipeline.gold import export_gold_xml
        written = export_gold_xml(corrected, directory)
        message = tr("gold.msg.xml_done").format(n=len(written), path=directory)
        self._export_status.setText(message)
        self.logMessage.emit(message)

    def _do_export_csv(self) -> None:
        corrected = self._ready()
        if corrected is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("gold.export.csv"), "gold_corretto.csv", "CSV (*.csv)")
        if not path:
            return
        from greek_corpus_pipeline.gold import export_gold_csv
        written = export_gold_csv(corrected, path)
        message = tr("gold.msg.csv_done").format(n=len(corrected), path=written)
        self._export_status.setText(message)
        self.logMessage.emit(message)

    def _do_export_conllu(self) -> None:
        corrected = self._ready()
        if corrected is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("gold.export.conllu"), "gold_corretto.conllu", "CoNLL-U (*.conllu)")
        if not path:
            return
        from greek_corpus_pipeline.gold import export_gold_conllu
        written = export_gold_conllu(corrected, path,
                                     corpus_name=self.state.corpus_name)
        message = tr("gold.msg.conllu_done").format(
            n=len(corrected), path=written[0] if written else path)
        self._export_status.setText(message)
        self.logMessage.emit(message)

    # ── Saving and resuming ────────────────────────────────────────────
    def _do_save_bundle(self) -> None:
        corrected = self._ready()
        if corrected is None:
            return
        from greek_corpus_pipeline.gold import BUNDLE_SUFFIX, save_gold_bundle
        default = f"{self.state.corpus_name or 'gold'}{BUNDLE_SUFFIX}"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("gold.keep.save"), default, f"{tr('gold.keep.filter')} (*{BUNDLE_SUFFIX})")
        if not path:
            return
        written = save_gold_bundle(
            path, corrected, self._manual(), self.state.token_diff,
            corpus_name=self.state.corpus_name, run_id=self.state.run_id or "")
        message = tr("gold.msg.saved").format(path=written)
        self._keep_status.setText(message)
        self.logMessage.emit(message)

    def _do_load_bundle(self) -> None:
        directory = self._run_directory()
        if directory is None:
            return
        from greek_corpus_pipeline.gold import BUNDLE_SUFFIX, load_gold_bundle
        path, _ = QFileDialog.getOpenFileName(
            self, tr("gold.keep.load"), "", f"{tr('gold.keep.filter')} (*{BUNDLE_SUFFIX})")
        if not path:
            return
        answer = QMessageBox.question(
            self, tr("gold.keep.load"), tr("gold.msg.load_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            meta = load_gold_bundle(path, directory)
        except Exception as error:                     # noqa: BLE001
            QMessageBox.warning(self, tr("gold.keep.load"), str(error))
            return
        message = tr("gold.msg.loaded").format(
            n=meta.get("changed_tokens", 0), corpus=meta.get("corpus_name", "—"))
        self._keep_status.setText(message)
        self.logMessage.emit(message)
        self.requestReload.emit()

    # ── Comparison ─────────────────────────────────────────────────────
    def _do_compare(self) -> None:
        """Opens the comparison between original, gold, Stanza and UDPipe."""
        if not self.state.has_corpus:
            return
        self._tabs.setVisible(True)
        self._tabs.setCurrentIndex(1)
        self._compare_status.setText(tr("app.working"))

        tokens = self.state.tokens
        corrected = self.state.corrected_tokens
        stanza = self.state.stanza_comparison
        udpipe = self.state.udpipe_comparison

        def compute():
            from greek_corpus_pipeline.gold import model_reference_table
            return model_reference_table(tokens, corrected, stanza, udpipe)

        def apply(models: pd.DataFrame) -> None:
            self._models_table.set_dataframe(models)
            if models is None or models.empty:
                self._compare_status.setText(tr("gold.msg.no_models"))
            else:
                self._compare_status.setText(tr("gold.msg.compare_done"))

        self.compute_in_background("gold-compare", compute, apply)
