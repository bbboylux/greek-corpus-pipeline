"""Step 1 — put a corpus into the program.

Three ways in, in the order people actually use them: a ready-made example (one
click, nothing to type, and the fastest way to find out whether the program does
what you hoped), a folder on your own disk, a GitHub address.

Below them, the list of corpora already loaded. Every load is kept, so the work
of an afternoon is still there tomorrow.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QRadioButton, QWidget,
)

from ..i18n import counted, tr
from ..widgets import (
    Card, LabeledField, chip_button, ghost_button, paragraph, primary_button,
)
from ..workers import prepare_corpus
from .base import Page

EXAMPLES = [
    ("load.example.gorman",
     "https://github.com/perseids-publications/gorman-trees/tree/master/public/xml",
     "gorman"),
    ("load.example.pedalion",
     "https://github.com/perseids-publications/pedalion-trees/tree/master/public/xml",
     "pedalion"),
    # GLAUx is the different case, and the buttons say so. Gorman and Pedalion are
    # manual annotation of a few hundred thousand records each; GLAUx has about twenty
    # million tokens, almost all annotated automatically, and loading it whole makes the
    # program unusable: the table cannot be looked at and the machine stops. The four
    # buttons therefore download the strata of the two declared samples — forty files in
    # all, listed in data/glaux_sample.csv — on which the article looks at how the checks
    # behave on GLAUx (§ 6). The first criterion of extraction is that no author is
    # shared with Gorman or with Pedalion.
    ("load.example.glaux_campione",
     "principale/automatico", "glaux_campione"),
    ("load.example.glaux_conferma",
     "conferma/automatico", "glaux_conferma"),
    # The manual strata of the two samples. They are five texts in all, inherited from
    # earlier treebanking projects, and GLAUx declares them sentence by sentence with
    # analysis="manual". The article counts them in the table of six strata, so the
    # button must be there: without it, whoever reads can redo two columns out of four.
    ("load.example.glaux_campione_manuale",
     "principale/manuale", "glaux_campione_manuale"),
    ("load.example.glaux_conferma_manuale",
     "conferma/manuale", "glaux_conferma_manuale"),
]


class LoadPage(Page):

    title_key = "load.title"
    intro_key = "load.intro"

    def build(self) -> None:
        # ── Examples ───────────────────────────────────────────────────
        self._examples_card = Card(tr("load.examples"))
        examples = self._examples_card
        self._examples_hint = paragraph(tr("load.examples_hint"), "hint")
        examples.add(self._examples_hint)
        # Six buttons on a single row would fall out of the window: two columns keep
        # them inside whatever the width, and the text stays whole.
        row = QGridLayout()
        row.setSpacing(10)
        self._example_buttons: list[tuple[str, object]] = []
        for indice, (label_key, url, name) in enumerate(EXAMPLES):
            button = chip_button(tr(label_key))
            self._example_buttons.append((label_key, button))
            modo = "glaux-sample" if name.startswith("glaux_") else "github"
            button.clicked.connect(
                lambda _checked=False, u=url, n=name, m=modo: self._load_example(u, n, m))
            row.addWidget(button, indice // 2, indice % 2)
        row.setColumnStretch(2, 1)
        examples.add_layout(row)
        self.add(examples)

        # ── Manual source ──────────────────────────────────────────────
        self._source_card = Card(tr("load.source"))
        source = self._source_card
        self._folder_radio = QRadioButton(tr("load.folder"))
        self._github_radio = QRadioButton(tr("load.github"))
        self._folder_radio.setChecked(True)
        self._folder_radio.toggled.connect(self._on_mode_changed)
        # The second of the two needs no signal of its own: its position is read by
        # “Load” when it starts. The marker says so in writing, so that the check that
        # looks for mute commands knows that this one is not.
        self._github_radio.setProperty("letto_al_via", True)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self._folder_radio)
        mode_row.addWidget(self._github_radio)
        mode_row.addStretch(1)
        source.add_layout(mode_row)

        self._path = QLineEdit()
        self._path.setPlaceholderText("C:\\… \\treebank\\xml")
        self._browse = ghost_button(tr("load.browse"))
        self._browse.clicked.connect(self._choose_folder)
        path_row = QHBoxLayout()
        path_row.addWidget(self._path, 1)
        path_row.addWidget(self._browse)
        holder = QWidget()
        holder.setLayout(path_row)
        self._path_field = LabeledField(tr("load.source"), holder)
        source.add(self._path_field)

        self._name = QLineEdit("corpus")
        self._name_field = LabeledField(tr("load.name"), self._name,
                                        tr("load.name_hint"))
        source.add(self._name_field)

        self._go = primary_button(tr("load.go"))
        self._go.clicked.connect(self._load_manual)
        go_row = QHBoxLayout()
        go_row.addStretch(1)
        go_row.addWidget(self._go)
        source.add_layout(go_row)
        self.add(source)

        # ── Filters ────────────────────────────────────────────────────
        self._filters_card = Card(tr("load.filters"))
        filters = self._filters_card
        self._filter_placeholders = QCheckBox(tr("load.filter_placeholders"))
        self._filter_placeholders.setChecked(True)
        filters.add(self._filter_placeholders)
        self._placeholders_help = paragraph(
            tr("load.filter_placeholders_help"), "hint")
        filters.add(self._placeholders_help)
        self._filter_non_greek = QCheckBox(tr("load.filter_nongreek"))
        self._filter_punctuation = QCheckBox(tr("load.filter_punct"))
        filters.add(self._filter_non_greek)
        filters.add(self._filter_punctuation)
        for box in (self._filter_placeholders, self._filter_non_greek,
                    self._filter_punctuation):
            box.stateChanged.connect(self._sync_filters)
        self.add(filters)

        # ── The corpus metadata ────────────────────────────────────────
        #
        # Optional, and the tab says so first. The program carries the metadata of some
        # resources and applies them only to a resource that it has recognised by the
        # fingerprint of the corpus; for everything else the CSV that the user loads
        # applies, and in the absence of both the tables by author, century and dialect
        # say “Unknown”, which is the truth.
        self._metadata_card = Card(tr("load.metadata"))
        self._metadata_hint = paragraph(tr("load.metadata_hint"), "hint")
        self._metadata_card.add(self._metadata_hint)
        self._metadata_state = paragraph("", "hint")
        self._metadata_card.add(self._metadata_state)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        self._metadata_load = ghost_button(tr("load.metadata_choose"))
        self._metadata_load.clicked.connect(self._choose_metadata)
        self._metadata_template = ghost_button(tr("load.metadata_template"))
        self._metadata_template.clicked.connect(self._save_metadata_template)
        self._metadata_clear = ghost_button(tr("load.metadata_clear"))
        self._metadata_clear.clicked.connect(self._clear_metadata)
        meta_row.addWidget(self._metadata_load)
        meta_row.addWidget(self._metadata_template)
        meta_row.addWidget(self._metadata_clear)
        meta_row.addStretch(1)
        self._metadata_card.add_layout(meta_row)
        self.add(self._metadata_card)
        self._refresh_metadata_state()

        # ── Saved runs ─────────────────────────────────────────────────
        self._saved_card = Card(tr("load.saved"))
        saved = self._saved_card
        self._saved_hint = paragraph(tr("load.saved_hint"), "hint")
        saved.add(self._saved_hint)
        self._runs = QListWidget()
        self._runs.setMinimumHeight(190)
        self._runs.itemDoubleClicked.connect(lambda _item: self._open_selected())
        self._runs.currentItemChanged.connect(
            lambda *_: self._aggiorna_comandi_giri())
        saved.add(self._runs, 1)

        buttons = QHBoxLayout()
        self._open = primary_button(tr("load.open"))
        self._open.clicked.connect(self._open_selected)
        self._delete = ghost_button(tr("load.delete"))
        self._delete.clicked.connect(self._delete_selected)
        buttons.addWidget(self._open)
        buttons.addWidget(self._delete)
        buttons.addStretch(1)
        saved.add_layout(buttons)
        self.add(saved)
        self._aggiorna_comandi_giri()

        self.body().addStretch(1)
        self.refresh_runs()

    # ── The metadata catalogue ─────────────────────────────────────────
    def _refresh_metadata_state(self) -> None:
        """Which set of metadata applies now, stated in full.

        The status must not say “No catalogue of your own: the shipped metadata apply”,
        which for an arbitrary corpus would suggest that applicable shipped metadata
        exist. The shipped metadata apply only to a resource recognised by its
        fingerprint, and the status says so.
        """
        from greek_corpus_pipeline.corpus_metadata import (
            riconosci_risorsa, user_catalogue_path)
        percorso = user_catalogue_path()
        if percorso.exists():
            self._metadata_state.setText(
                tr("load.metadata_active").format(file=percorso.name))
        else:
            risorsa = riconosci_risorsa(getattr(self.state, "tokens", None))
            self._metadata_state.setText(
                tr("load.metadata_bundled", risorsa["risorsa"]) if risorsa
                else tr("load.metadata_none"))
        # “Back to the shipped metadata” makes no sense as long as there is nothing to
        # go back from: if it were visible while switched off it would suggest that
        # shipped metadata exist anyway.
        self._metadata_clear.setVisible(percorso.exists())

    def _choose_metadata(self) -> None:
        from greek_corpus_pipeline.corpus_metadata import install_user_catalogue
        percorso, _ = QFileDialog.getOpenFileName(
            self, tr("load.metadata_choose"), "", "CSV (*.csv);;*")
        if not percorso:
            return
        ok, messaggi = install_user_catalogue(percorso)
        testo = "\n".join(messaggi) if messaggi else ""
        if ok:
            QMessageBox.information(self, tr("load.metadata"),
                                    tr("load.metadata_ok") + "\n\n" + testo)
            self._refresh_metadata_state()
        else:
            QMessageBox.warning(self, tr("load.metadata"),
                                tr("load.metadata_ko") + "\n\n" + testo)

    def _save_metadata_template(self) -> None:
        from greek_corpus_pipeline.corpus_metadata import data_dir
        modello = data_dir() / "user_metadata_EXAMPLE.csv"
        destinazione, _ = QFileDialog.getSaveFileName(
            self, tr("load.metadata_template"), "user_metadata.csv", "CSV (*.csv)")
        if not destinazione:
            return
        Path(destinazione).write_bytes(modello.read_bytes())
        QMessageBox.information(self, tr("load.metadata"),
                                tr("load.metadata_template_ok").format(
                                    file=Path(destinazione).name))

    def _clear_metadata(self) -> None:
        from greek_corpus_pipeline.corpus_metadata import remove_user_catalogue
        if remove_user_catalogue():
            self._refresh_metadata_state()

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        for key, button in getattr(self, "_example_buttons", []):
            button.setText(tr(key))
        self._examples_card.set_title(tr("load.examples"))
        self._examples_hint.setText(tr("load.examples_hint"))
        self._source_card.set_title(tr("load.source"))
        self._folder_radio.setText(tr("load.folder"))
        self._github_radio.setText(tr("load.github"))
        self._browse.setText(tr("load.browse"))
        self._path_field.set_label(tr("load.source"))
        self._name_field.set_label(tr("load.name"), tr("load.name_hint"))
        self._go.setText(tr("load.go"))
        self._metadata_card.set_title(tr("load.metadata"))
        self._metadata_hint.setText(tr("load.metadata_hint"))
        self._metadata_load.setText(tr("load.metadata_choose"))
        self._metadata_template.setText(tr("load.metadata_template"))
        self._metadata_clear.setText(tr("load.metadata_clear"))
        self._refresh_metadata_state()
        self._filters_card.set_title(tr("load.filters"))
        self._filter_placeholders.setText(tr("load.filter_placeholders"))
        self._placeholders_help.setText(tr("load.filter_placeholders_help"))
        self._filter_non_greek.setText(tr("load.filter_nongreek"))
        self._filter_punctuation.setText(tr("load.filter_punct"))
        self._saved_card.set_title(tr("load.saved"))
        self._saved_hint.setText(tr("load.saved_hint"))
        self._open.setText(tr("load.open"))
        self._delete.setText(tr("load.delete"))
        super().retranslate()

    # ── Behaviour ──────────────────────────────────────────────────────
    def _on_mode_changed(self) -> None:
        folder = self._folder_radio.isChecked()
        self._browse.setVisible(folder)
        self._path.setPlaceholderText(
            "C:\\… \\treebank\\xml" if folder
            else "https://github.com/owner/repo/tree/master/public/xml")

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("load.browse"))
        if path:
            self._path.setText(path)
            if self._name.text().strip() in ("", "corpus"):
                self._name.setText(Path(path).name or "corpus")

    def _sync_filters(self) -> None:
        self.state.filter_options = {
            "exclude_placeholders": self._filter_placeholders.isChecked(),
            "exclude_non_greek": self._filter_non_greek.isChecked(),
            "exclude_punctuation": self._filter_punctuation.isChecked(),
        }

    def _load_example(self, url: str, name: str, mode: str = "github") -> None:
        if mode == "github":
            self._github_radio.setChecked(True)
            self._path.setText(url)
        self._name.setText(name)
        self._start(url, name, mode)

    def _load_manual(self) -> None:
        value = self._path.text().strip()
        if not value:
            QMessageBox.information(self, tr("load.title"), tr("load.missing"))
            return
        mode = "folder" if self._folder_radio.isChecked() else "github"
        if mode == "folder" and not Path(value).exists():
            QMessageBox.warning(
                self, tr("load.title"), tr("load.missing_folder", value))
            return
        self._start(value, self._name.text().strip() or "corpus", mode)

    def _start(self, value: str, name: str, mode: str) -> None:
        # No dialogue that asks for the metadata before starting. The metadata are
        # optional, and a dialogue that opens by itself at the start of every load would
        # make them look like a compulsory step. Whoever wants them loads them from the
        # “Corpus metadata” tab, which is just above.

        from greek_corpus_pipeline.storage import create_run_id, save_metadata

        run_id = create_run_id(name)
        save_metadata(self.state.workspace, run_id, {
            "run_id": run_id,
            "corpus_name": name,
            "source_mode": mode,
            "source_value": value,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stages": {},
        })
        self.state.run_id = run_id
        self.state.corpus_name = name
        self.logMessage.emit(tr("load.log_loading", name, value))
        self.run_work(prepare_corpus, self.state.workspace, run_id, mode, value, name,
                      label=tr("step.load"))

    # ── Saved runs list ────────────────────────────────────────────────
    def refresh_runs(self) -> None:
        from greek_corpus_pipeline.storage import list_runs

        self._runs.clear()
        try:
            runs = list_runs(self.state.workspace)
        except Exception:
            runs = []
        for run in runs:
            stages = run.get("stages", {}) or {}
            prepared = stages.get("prepare", {})
            tokens = prepared.get("tokens")
            detected = "detection" in stages
            corrected = "corrections" in stages
            models = [name for name in ("stanza", "udpipe") if name in stages]

            bits = [str(run.get("corpus_name", "")).strip() or run["run_id"]]
            if tokens:
                bits.append(counted("record_importato", int(tokens)))
            created = str(run.get("created_at", ""))[:10]
            if created:
                bits.append(created)
            marks = []
            if detected:
                marks.append(tr("load.mark.checked"))
            if corrected:
                marks.append(tr("load.mark.corrected"))
            if models:
                marks.append(" + ".join(models))
            if marks:
                bits.append("· " + ", ".join(marks))

            item = QListWidgetItem("   ".join(bits))
            item.setData(Qt.ItemDataRole.UserRole, run["run_id"])
            item.setToolTip(str(run.get("source_value", "")))
            self._runs.addItem(item)
        self._aggiorna_comandi_giri()

    def _aggiorna_comandi_giri(self) -> None:
        """“Open” and “Delete” act on the chosen run: with no choice, nothing.

        They are disabled when the list is empty or nothing is selected: left enabled, a
        click would return at once without saying anything, and from the outside they
        would look like two broken buttons.
        """
        scelto = self._runs.currentItem() is not None
        motivo = "" if scelto else tr("load.pick_a_run")
        for bottone in (self._open, self._delete):
            bottone.setEnabled(scelto)
            bottone.setToolTip(motivo)

    def _open_selected(self) -> None:
        item = self._runs.currentItem()
        if item is None:
            return
        run_id = item.data(Qt.ItemDataRole.UserRole)
        self.state.run_id = run_id
        self.requestReload.emit()

    def _delete_selected(self) -> None:
        item = self._runs.currentItem()
        if item is None:
            return
        run_id = item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self, tr("load.delete"), tr("load.delete_confirm", run_id))
        if answer != QMessageBox.StandardButton.Yes:
            return
        import shutil
        from greek_corpus_pipeline.storage import run_dir
        try:
            shutil.rmtree(run_dir(self.state.workspace, run_id))
        except Exception as exception:
            QMessageBox.warning(self, tr("app.error"), str(exception))
            return
        if self.state.run_id == run_id:
            self.state.run_id = None
        self.refresh_runs()
        self.logMessage.emit(tr("load.log_deleted", run_id))

    def refresh(self) -> None:
        self.refresh_runs()
        self._refresh_metadata_state()
        options = self.state.filter_options
        for box, key in ((self._filter_placeholders, "exclude_placeholders"),
                         (self._filter_non_greek, "exclude_non_greek"),
                         (self._filter_punctuation, "exclude_punctuation")):
            box.blockSignals(True)
            box.setChecked(bool(options.get(key)))
            box.blockSignals(False)
