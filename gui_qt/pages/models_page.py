"""Step 9 — Stanza and UDPipe against the corpus, and against each other.

The whole page is built around a claim worth stating plainly: the comparison
does not treat either automatic model as a gold standard. Two independently
trained systems that converge on a reading the corpus does not have are a
stronger review signal than either of them alone, and the categories below are
arranged so that that case is the one that stands out — as a place to look, not
as a verdict on the annotation.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..i18n import decimal, number, pick, tr, value_label
from ..widgets import (
    Card, DataTable, KeyValueList, combo, notice, paragraph, primary_button,
)
from ..workers import run_stanza, run_udpipe
from .base import Page


class ModelsPage(Page):

    title_key = "models.title"
    intro_key = "models.intro"
    howto_keys = ("models.howto.1",)

    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        # The two models, side by side. Two buttons and two status lines on the same row
        # would leave the reader to infer from the position which status belongs to
        # which model: with four possible states — not available, not run, to be redone,
        # run — that is not enough.
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)          # pulsing / indeterminate
        self._busy_bar.setMaximumWidth(220)
        self._busy_bar.setVisible(False)
        self._running = False

        schede = QHBoxLayout()
        schede.setSpacing(16)
        self._stanza_card, self._stanza_button, self._stanza_status = \
            self._scheda_modello("Stanza", tr("models.run_stanza"), self._run_stanza)
        self._udpipe_card, self._udpipe_button, self._udpipe_status = \
            self._scheda_modello("UDPipe", tr("models.run_udpipe"), self._run_udpipe)
        schede.addWidget(self._stanza_card, 1)
        schede.addWidget(self._udpipe_card, 1)
        contenitore = QWidget(); contenitore.setLayout(schede)
        self.add(contenitore)

        run_card = Card()
        self._first_time = paragraph(tr("models.first_time"), "hint")
        run_card.add(self._first_time)
        self._units_hint = paragraph(tr("models.units.hint"), "hint")
        run_card.add(self._units_hint)
        riga_barra = QHBoxLayout()
        riga_barra.addWidget(self._busy_bar)
        riga_barra.addStretch(1)
        run_card.add_layout(riga_barra)

        model_row = QHBoxLayout()
        self._custom_caption = QLabel(tr("models.custom_model"))
        model_row.addWidget(self._custom_caption)
        self._udpipe_path = QLineEdit()
        self._udpipe_path.setPlaceholderText(tr("models.custom_model.hint"))
        model_row.addWidget(self._udpipe_path, 1)
        run_card.add_layout(model_row)
        self.add(run_card)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), tr("models.tab_overview"))
        self._tabs.addTab(self._build_three_way_tab(), tr("models.tab_three_way"))
        self._tabs.addTab(self._build_slots_tab(), tr("models.tab_slots"))
        self._tabs.addTab(self._build_divergence_tab(), tr("models.tab_divergence"))
        self._tabs.addTab(self._build_by_author_tab(), tr("models.tab_by_author"))
        self.add(self._tabs, 1)

    def _scheda_modello(self, nome: str, etichetta: str, azione):
        """A card for each model: name, status, and the button that runs it.

        Returns the card, the button and the status label, because the rest of the page
        already drives them under those names.
        """
        scheda = Card()
        titolo = QLabel(nome)
        titolo.setObjectName("sectionTitle")
        scheda.add(titolo)
        stato = QLabel("")
        stato.setObjectName("hint")
        stato.setWordWrap(True)
        scheda.add(stato)
        bottone = primary_button(etichetta)
        bottone.clicked.connect(azione)
        riga = QHBoxLayout()
        riga.addWidget(bottone)
        riga.addStretch(1)
        scheda.add_layout(riga)
        return scheda, bottone, stato

    def _build_overview_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(18)
        stanza_card = Card("Stanza")
        self._stanza_summary = KeyValueList()
        stanza_card.add(self._stanza_summary)
        udpipe_card = Card("UDPipe")
        self._udpipe_summary = KeyValueList()
        udpipe_card.add(self._udpipe_summary)
        row.addWidget(stanza_card, 1)
        row.addWidget(udpipe_card, 1)
        layout.addLayout(row)

        self._mismatch_card = Card(tr("models.mismatches"))
        card = self._mismatch_card
        self._mismatch_source = combo(["Stanza", "UDPipe"], width=150)
        self._mismatch_source.currentIndexChanged.connect(self._ricalcola_viste)
        source_row = QHBoxLayout()
        self._mismatch_caption = QLabel(tr("models.model"))
        source_row.addWidget(self._mismatch_caption)
        source_row.addWidget(self._mismatch_source)
        source_row.addStretch(1)
        card.add_layout(source_row)
        self._mismatches = DataTable(min_height=320)
        self._mismatches.set_empty_text("empty.models", "empty.models.hint")
        card.add(self._mismatches, 1)
        layout.addWidget(card, 1)
        return page

    def _build_three_way_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        self._three_way_hint = paragraph(tr("models.three_way.hint"), "hint")
        layout.addWidget(self._three_way_hint)
        self._three_way = DataTable(min_height=200, column_picker=False)
        layout.addWidget(self._three_way)

        self._recurring_card = Card(tr("models.recurring"))
        card = self._recurring_card
        self._recurring_hint = paragraph(tr("models.recurring.hint"), "hint")
        card.add(self._recurring_hint)
        self._recurring = DataTable(min_height=280)
        card.add(self._recurring, 1)
        layout.addWidget(card, 1)

        detail_card = Card(tr("models.affected_tokens"))
        self._detail_card = detail_card
        self._three_way_detail = DataTable(min_height=280)
        detail_card.add(self._three_way_detail, 1)
        layout.addWidget(detail_card, 1)
        return page

    def _build_slots_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        self._slots_hint = paragraph(tr("models.slots.hint"), "hint")
        layout.addWidget(self._slots_hint)
        controls = QHBoxLayout()
        self._compare_caption = QLabel(tr("models.compare"))
        controls.addWidget(self._compare_caption)
        self._slot_left = combo(["corpus"], width=150)
        self._slot_right = combo(["Stanza", "UDPipe"], width=150)
        for box in (self._slot_left, self._slot_right):
            box.currentIndexChanged.connect(self._ricalcola_viste)
        controls.addWidget(self._slot_left)
        self._with_caption = QLabel(tr("models.compare_with"))
        controls.addWidget(self._with_caption)
        controls.addWidget(self._slot_right)
        controls.addStretch(1)
        layout.addLayout(controls)
        self._slots = DataTable(min_height=300, column_picker=False)
        layout.addWidget(self._slots, 1)

        self._confusion_card = Card(tr("models.confusion"))
        confusion_card = self._confusion_card
        position_row = QHBoxLayout()
        self._position_caption = QLabel(tr("models.position"))
        position_row.addWidget(self._position_caption)
        from greek_corpus_pipeline.agdt_schema import POSITION_NAMES
        self._position = QComboBox()
        for index, names in POSITION_NAMES.items():
            self._position.addItem(f"{index + 1} — {pick(names)}", index)
        self._position.currentIndexChanged.connect(self._ricalcola_viste)
        position_row.addWidget(self._position)
        position_row.addStretch(1)
        confusion_card.add_layout(position_row)
        self._confusion = DataTable(min_height=280)
        confusion_card.add(self._confusion, 1)
        layout.addWidget(confusion_card, 1)
        return page

    def _build_divergence_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        self._divergence_hint = paragraph(tr("models.divergence.hint"), "hint")
        layout.addWidget(self._divergence_hint)
        self._divergence = DataTable(min_height=420)
        layout.addWidget(self._divergence, 1)
        return page

    def _build_by_author_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        self._by_author_hint = paragraph(tr("models.by_author.hint"), "hint")
        layout.addWidget(self._by_author_hint)
        controls = QHBoxLayout()
        self._group_caption = QLabel(tr("stats.group_by"))
        controls.addWidget(self._group_caption)
        self._group = QComboBox()
        self._group.setMinimumWidth(180)
        self._group.currentIndexChanged.connect(self._ricalcola_viste)
        controls.addWidget(self._group)
        controls.addStretch(1)
        layout.addLayout(controls)
        self._by_group = DataTable(min_height=380)
        layout.addWidget(self._by_group, 1)
        return page

    # ── Actions ────────────────────────────────────────────────────────
    def work_finished(self, riuscito: bool, messaggio: str = "") -> None:
        """The comparison has finished, however it finished, and the page comes alive
        again.

        When it succeeds, the run is reloaded and ``refresh`` puts everything back in
        place.  When it fails nothing is reloaded, and without this the page would stay
        as it was an instant before the error: spinning bar and two buttons switched
        off, that is the look of a job still in progress laid over a job that has died.
        With the popup closed it would not even be possible to try again.
        """
        self._running = False
        self._busy_bar.setVisible(False)
        # ``refresh`` rereads the state of the two models from the folder of the run and
        # re-enables the buttons: what went wrong is told by the message, not by the
        # page, which has only to become usable again.
        self.refresh()

    def _run_stanza(self) -> None:
        if not self.state.run_id:
            return
        from greek_corpus_pipeline.model_support import default_stanza_model_dir
        self._running = True
        self._stanza_button.setEnabled(False)
        self._udpipe_button.setEnabled(False)
        self._stanza_status.setText(tr("app.working"))
        self._busy_bar.setVisible(True)
        self.run_work(run_stanza, self.state.workspace, self.state.run_id,
                      str(default_stanza_model_dir(self.state.workspace)),
                      dict(self.state.filter_options),
                      label=tr("models.run_stanza"))

    def _run_udpipe(self) -> None:
        if not self.state.run_id:
            return
        from greek_corpus_pipeline.model_support import default_udpipe_model_path
        self._running = True
        self._stanza_button.setEnabled(False)
        self._udpipe_button.setEnabled(False)
        self._udpipe_status.setText(tr("app.working"))
        self._busy_bar.setVisible(True)
        self.run_work(run_udpipe, self.state.workspace, self.state.run_id,
                      self._udpipe_path.text().strip(),
                      str(default_udpipe_model_path(self.state.workspace)),
                      dict(self.state.filter_options),
                      label=tr("models.run_udpipe"))

    # ── Rendering ──────────────────────────────────────────────────────
    def retranslate(self) -> None:
        """The dropdown of the nine positions is created in ``build`` and must be
        rewritten."""
        self._units_hint.setText(tr("models.units.hint"))
        from greek_corpus_pipeline.agdt_schema import POSITION_NAMES
        box = getattr(self, "_position", None)
        if box is not None:
            chosen = box.currentData()
            box.blockSignals(True)
            box.clear()
            for index, names in POSITION_NAMES.items():
                box.addItem(f"{index + 1} — {pick(names)}", index)
            found = box.findData(chosen)
            box.setCurrentIndex(found if found >= 0 else 0)
            box.blockSignals(False)
        self._locked.setText(tr("step.locked"))
        self._first_time.setText(tr("models.first_time"))
        self._stanza_button.setText(tr("models.run_stanza"))
        self._udpipe_button.setText(tr("models.run_udpipe"))
        self._custom_caption.setText(tr("models.custom_model"))
        self._udpipe_path.setPlaceholderText(tr("models.custom_model.hint"))
        for index, key in enumerate(("models.tab_overview", "models.tab_three_way",
                                     "models.tab_slots", "models.tab_divergence",
                                     "models.tab_by_author")):
            self._tabs.setTabText(index, tr(key))
        self._mismatch_card.set_title(tr("models.mismatches"))
        self._mismatch_caption.setText(tr("models.model"))
        self._three_way_hint.setText(tr("models.three_way.hint"))
        self._recurring_card.set_title(tr("models.recurring"))
        self._recurring_hint.setText(tr("models.recurring.hint"))
        self._detail_card.set_title(tr("models.affected_tokens"))
        self._slots_hint.setText(tr("models.slots.hint"))
        self._compare_caption.setText(tr("models.compare"))
        self._with_caption.setText(tr("models.compare_with"))
        self._confusion_card.set_title(tr("models.confusion"))
        self._position_caption.setText(tr("models.position"))
        self._divergence_hint.setText(tr("models.divergence.hint"))
        self._by_author_hint.setText(tr("models.by_author.hint"))
        self._group_caption.setText(tr("stats.group_by"))
        super().retranslate()

    def refresh(self) -> None:
        from greek_corpus_pipeline.analyzers import (
            check_stanza_available, check_udpipe_available,
        )

        # If a model was running, it has now finished.
        if self._running:
            self._running = False
            self._busy_bar.setVisible(False)

        has_corpus = self.state.has_corpus
        self._locked.setVisible(not has_corpus)
        self._tabs.setVisible(has_corpus)

        stanza_ok, _ = check_stanza_available()
        udpipe_ok, _ = check_udpipe_available()
        self._stanza_button.setEnabled(has_corpus and stanza_ok)
        self._udpipe_button.setEnabled(has_corpus and udpipe_ok)

        if not has_corpus:
            self._stanza_status.setText(
                tr("models.state.available") if stanza_ok else tr("models.not_here"))
            self._udpipe_status.setText(
                tr("models.state.available") if udpipe_ok else tr("models.not_here"))
            return

        # From here on the work is heavy and must not stay in the interface thread.  On
        # Gorman, measured on the real files of the runs: two reads of the comparison
        # table (548,912 x 30), the computation of the surface of the model on the whole
        # corpus, and five aggregations.  About ten seconds in which the window does not
        # redraw.  The reads and the aggregations are done outside; ready-to-show tables
        # arrive at the Qt thread.
        sorgente_disaccordi = self._mismatch_source.currentText()
        modello_posizioni = self._slot_right.currentText()
        posizione = self._position.currentData()
        gruppo = self._group.currentText()
        percorso_udpipe = self._udpipe_path.text().strip()

        def calcola():
            return self._tabelle_dei_modelli(
                sorgente_disaccordi, modello_posizioni, posizione, gruppo,
                percorso_udpipe)

        self.compute_in_background("modelli", calcola, self._mostra_tabelle)

    # ── The computation, outside the interface thread ──────────────────
    def _tabelle_dei_modelli(self, sorgente_disaccordi: str, modello_posizioni: str,
                             posizione, gruppo: str, percorso_udpipe: str) -> dict:
        """Everything that the five tabs show, already computed.

        It runs in a worker thread: it **touches no widget**.  It reads the state of
        the two models from the folder of the run — which is the only thing that really
        knows what it contains — loads the comparison tables and produces the eight
        tables to be shown.
        """
        from greek_corpus_pipeline import modelcmp
        from greek_corpus_pipeline.analyzers import (
            check_stanza_available, check_udpipe_available,
        )
        from greek_corpus_pipeline.model_support import (
            default_stanza_model_dir, default_udpipe_model_path,
            stanza_identity, udpipe_identity,
        )

        stanza_ok, _ = check_stanza_available()
        udpipe_ok, _ = check_udpipe_available()
        versione_s, risorse_s = stanza_identity(
            default_stanza_model_dir(self.state.workspace)) if stanza_ok else ("", "")
        scelto = percorso_udpipe or str(default_udpipe_model_path(self.state.workspace))
        versione_u, risorse_u = udpipe_identity(scelto) if udpipe_ok else ("", "")

        stato = {
            "stanza": self.state.model_status("stanza", versione=versione_s,
                                              risorse=risorse_s) if stanza_ok else None,
            "udpipe": self.state.model_status("udpipe", versione=versione_u,
                                              risorse=risorse_u) if udpipe_ok else None,
        }
        S = self.state.stanza_comparison
        U = self.state.udpipe_comparison
        entrambi = not S.empty and not U.empty

        vuota = pd.DataFrame()
        tabelle: dict[str, object] = {}

        # 1. the disagreements of a single model
        confronto = S if sorgente_disaccordi == "Stanza" else U
        coppie: list[tuple[str, str]] = []
        if confronto.empty:
            tabelle["disaccordi"] = vuota
        else:
            accordo_tag = modelcmp._colonna_accordo(confronto, "postag")
            accordo_lemma = modelcmp._colonna_accordo(confronto, "lemma")
            if accordo_tag and accordo_lemma:
                sotto = confronto[~confronto[accordo_tag].fillna(True)
                                  | ~confronto[accordo_lemma].fillna(True)]
            else:
                sotto = confronto
            for campo in ("lemma", "postag"):
                a = modelcmp._colonna_corpus(confronto, campo)
                b = modelcmp._colonna_modello(confronto, campo)
                if a and b and a != b:
                    coppie.append((a, b))
            chiavi = [c for c in ("form", "document_id", "sentence_id", "token_id")
                      if c in confronto.columns]
            colonne = chiavi + [c for coppia in coppie for c in coppia]
            tabelle["disaccordi"] = sotto[colonne].head(20_000)
        tabelle["coppie_disaccordi"] = coppie

        # 2. the three ways
        if not entrambi:
            tabelle["tre_vie"] = tabelle["ricorrenti"] = tabelle["dettaglio"] = vuota
        else:
            riassunto, dettaglio = modelcmp.three_way_agreement(S, U)
            tabelle["tre_vie"] = riassunto
            tabelle["ricorrenti"] = modelcmp.models_against_corpus(S, U)
            colonne = [c for c in dettaglio.columns
                       if c in ("form", "corpus", "stanza", "udpipe", "esito",
                                "document_id", "sentence_id", "token_id")]
            tabelle["dettaglio"] = dettaglio[colonne] if colonne else dettaglio

        # 3. position by position, and the confusion in one position
        confronto_pos = S if modello_posizioni == "Stanza" else U
        rif = modelcmp._colonna_corpus(confronto_pos, "postag") if not confronto_pos.empty else None
        mod = modelcmp._colonna_modello(confronto_pos, "postag") if not confronto_pos.empty else None
        if not rif or not mod or rif == mod:
            tabelle["posizioni"] = tabelle["confusione"] = vuota
        else:
            tabelle["posizioni"] = modelcmp.per_slot_agreement(
                confronto_pos[rif], confronto_pos[mod],
                left_label="corpus", right_label=modello_posizioni)
            tabelle["confusione"] = modelcmp.slot_confusion(
                confronto_pos[rif], confronto_pos[mod], int(posizione or 0))

        # 4. the forms on which the two models diverge
        tabelle["divergenza"] = (modelcmp.divergence_hotspots(S, U)
                                 if entrambi else vuota)

        # 5. by author, or by the chosen field
        tabelle["per_gruppo"] = (
            modelcmp.agreement_by_group(S, U, self.state.tokens, group=gruppo)
            if entrambi and gruppo else vuota)

        return {"stato": stato, "tabelle": tabelle,
                "gruppi": self.state.group_fields()}

    # ── The application of the result, in the interface thread ─────────
    def _mostra_tabelle(self, risultato: dict) -> None:
        """Only assignments to widgets: no computation."""
        stato = risultato["stato"]
        for etichetta, campo, scheda in (
                ("stanza", self._stanza_status, self._stanza_summary),
                ("udpipe", self._udpipe_status, self._udpipe_summary)):
            s = stato.get(etichetta)
            if s is None:
                campo.setText(tr("models.not_here"))
                scheda.set_items({tr("models.field.model"): tr("models.not_here")})
                continue
            campo.setText(self._etichetta_stato(s))
            scheda.set_items(self._voci_stato(s))

        corrente = self._group.currentText()
        self._group.blockSignals(True)
        self._group.clear()
        self._group.addItems(risultato["gruppi"])
        indice = self._group.findText(corrente or "autore")
        self._group.setCurrentIndex(indice if indice >= 0 else 0)
        self._group.blockSignals(False)

        t = risultato["tabelle"]
        self._mismatches.set_dataframe(t["disaccordi"])
        self._mismatches.set_highlight_pairs(t["coppie_disaccordi"])
        riassunto = t["tre_vie"]
        self._three_way.set_dataframe(
            riassunto.assign(esito=riassunto["esito"].map(value_label))
            if "esito" in getattr(riassunto, "columns", []) else riassunto)
        self._recurring.set_dataframe(t["ricorrenti"])
        dettaglio = t["dettaglio"]
        if "esito" in getattr(dettaglio, "columns", []):
            dettaglio = dettaglio.assign(esito=dettaglio["esito"].map(value_label))
        self._three_way_detail.set_dataframe(dettaglio)
        self._three_way_detail.set_highlight_pairs([("corpus", "stanza"),
                                                    ("corpus", "udpipe")])
        self._slots.set_dataframe(t["posizioni"])
        self._confusion.set_dataframe(t["confusione"])
        self._divergence.set_dataframe(t["divergenza"])
        self._by_group.set_dataframe(t["per_gruppo"])

    @staticmethod
    def _etichetta_stato(stato: dict) -> str:
        return {"valido": tr("models.state.done"),
                "inapplicabile": tr("models.stale.short")}.get(
                    stato["stato"], tr("models.state.available"))

    def _voci_stato(self, stato: dict) -> dict:
        if stato["stato"] == "valido":
            return self._voci_valutazione(stato["valutazione"])
        if stato["stato"] == "inapplicabile":
            return {tr("models.field.model"): tr("models.stale", stato["motivo"])}
        return {tr("models.field.model"): tr("models.not_on_this_corpus")}

    @staticmethod
    def _voci_valutazione(valutazione: dict) -> dict:
        """The numbers of the comparison, each beside its own denominator."""
        provenienza = valutazione.get("provenienza", {}) or {}
        lemma = valutazione.get("lemma", {}) or {}
        postag = valutazione.get("postag", {}) or {}

        def quota(metrica: dict) -> str:
            if metrica.get("sospesa"):
                return tr("models.postag_suspended", metrica["sospesa"])
            eleggibili = metrica.get("eleggibili", 0)
            if not eleggibili:
                return "—"
            return (number(metrica.get('accordi', 0))
                    + " / " + number(eleggibili)
                    + f"  ({decimal(metrica.get('quota', 0))}%)"
                    + "  · " + metrica.get("denominatore", ""))

        voci = {
            tr("models.field.model"): provenienza.get("modello", ""),
            tr("models.field.version"): provenienza.get("modello_versione", ""),
            tr("models.field.resources"): provenienza.get("risorse_modello", ""),
            tr("models.field.corpus"): provenienza.get("impronta_corpus", ""),
            tr("models.field.when"): provenienza.get("quando", ""),
            tr("models.field.definition"): provenienza.get("definizione_valutazione", ""),
            tr("models.field.words"): number(valutazione.get('parole', 0)),
            tr("models.field.coverage"):
                f"{decimal(lemma.get('copertura', 0))}%",
            tr("models.field.lemma"): quota(lemma),
            tr("models.field.postag"): quota(postag),
        }
        esclusi = {**(lemma.get("esclusi") or {}), **(postag.get("esclusi") or {})}
        if esclusi:
            voci[tr("models.field.excluded")] = " · ".join(
                f"{k}: {v}" for k, v in esclusi.items())
        return voci

    def _ricalcola_viste(self) -> None:
        """A dropdown has changed: the tables are rebuilt, always outside the Qt thread.

        A single entry point for all four dropdowns, and the same computation as
        ``refresh``: two different ways to fill the same tables are two chances for them
        to show different things.
        """
        if not self.state.has_corpus:
            return
        sorgente = self._mismatch_source.currentText()
        posizioni = self._slot_right.currentText()
        posizione = self._position.currentData()
        gruppo = self._group.currentText()
        percorso = self._udpipe_path.text().strip()

        def calcola():
            return self._tabelle_dei_modelli(sorgente, posizioni, posizione,
                                             gruppo, percorso)

        self.compute_in_background("modelli", calcola, self._mostra_tabelle)
