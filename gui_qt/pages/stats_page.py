"""Step 7 — the corpus in numbers.

Four tabs and only two questions: what the corpus is made of, and whether the annotation
holds. Morphology, syntax, frequency lists, profile of a word.

Three things hold for the whole page.

The first: what is read elsewhere is not repeated here. Documents, sentences, records,
words, distinct forms and lemmas are in the Overview; findings, violations, variants and
triggered rules are in “Diagnostic findings”. Repeating them would only give two chances
of being inconsistent.

The second: it is computed on request. No statistic is produced at start-up, at import,
after the diagnosis or when moving from one page to another. The computation starts when
whoever works chooses a dimension, a value and a tab, and the result stays in the cache
until those four elements and the corpus change.

The third: the metadata are not invented. Author, work, period, genre and dialect appear
only if the loaded corpus carries them with it. They are not derived from the file name,
not completed, not taken from another corpus. When they are missing, the dimension is
not there.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout,
    QWidget,
)

from ..i18n import decimal, number, tr, value_label
from ..style import ACCENT, INK
from ..widgets import (
    Card, DataTable, HowToBox, KeyValueList, combo, ghost_button,
    greek_line_edit, notice, paragraph, primary_button,
)
from .base import Page

#: The dimensions of analysis, in the order in which they appear in the menu. The key is
#: the token column; ``""`` is the whole corpus and ``document_id`` is always there,
#: because the document comes from the imported file and not from the metadata.
DIMENSIONI: list[tuple[str, str]] = [
    ("", "stats.dim.corpus"),
    ("document_id", "stats.dim.documento"),
    ("autore", "stats.dim.autore"),
    ("opera", "stats.dim.opera"),
    ("periodo", "stats.dim.periodo"),
    ("genere", "stats.dim.genere"),
    ("dialetto", "stats.dim.dialetto"),
]

#: The six morphological distributions, with the relevant denominator. The second
#: element is the set of parts of speech to which the feature applies: ``None``
#: means all the analysed words.
#:
#: The tabs of the profile of a word, in order.  “associazioni” (associations)
#: comes first because it is the answer to the question that the tab poses;
#: “teste” (heads) and “dipendenti” (dependents) are not there because they would
#: be raw counts of the same pairs that “associazioni” measures, and the note under
#: the tab promises the measure.
SCHEDE_PAROLA = ("associazioni", "grafie", "forme", "postag", "relazioni",
                 "documenti", "esempi")

DISTRIBUZIONI: list[tuple[str, int, "set[str] | None"]] = [
    ("pos",      0, None),
    ("casi",     7, {"n", "a", "p", "l", "m"}),
    ("modi",     4, {"v"}),
    ("tempi",    3, {"v"}),
    ("diatesi",  5, {"v"}),
    ("persone",  1, {"v"}),
]


class StatsPage(Page):

    title_key = "stats.title"
    intro_key = "stats.intro"
    howto_keys = ("stats.howto.1",)

    # ── building the page ─────────────────────────────────────────────────
    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        #: The lemmas that whoever works has added to or removed from the grammatical
        #: list.
        self._stop_extra: list[str] = []
        self._stop_remove: list[str] = []
        #: The tabs already computed for the current key, so as not to redo them.
        self._interagito = False

        riga = QHBoxLayout()
        self._dim_caption = QLabel(tr("stats.dimension"))
        riga.addWidget(self._dim_caption)
        self._dim = QComboBox()
        self._dim.setMinimumWidth(190)
        self._dim.currentIndexChanged.connect(self._dimensione_cambiata)
        riga.addWidget(self._dim)

        self._val_caption = QLabel(tr("stats.value"))
        riga.addWidget(self._val_caption)
        self._val = QComboBox()
        self._val.setMinimumWidth(260)
        self._val.currentIndexChanged.connect(self._selezione_cambiata)
        riga.addWidget(self._val)

        self._selezione_nota = QLabel("")
        self._selezione_nota.setObjectName("hint")
        riga.addWidget(self._selezione_nota, 1)
        riga.addStretch(1)
        contenitore = QWidget()
        contenitore.setLayout(riga)
        self.add(contenitore)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._scheda_morfologia(), tr("stats.tab_morfologia"))
        self._tabs.addTab(self._scheda_sintassi(), tr("stats.tab_sintassi"))
        self._tabs.addTab(self._scheda_frequenza(), tr("stats.tab_frequency"))
        self._tabs.addTab(self._scheda_parola(), tr("stats.tab_sketch"))
        self._tabs.currentChanged.connect(self._scheda_cambiata)
        self.add(self._tabs, 1)

    # ── card 1: morphology ────────────────────────────────────────────────
    def _scheda_morfologia(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._morf_nota = paragraph(tr("stats.morf.hint"), "hint")
        layout.addWidget(self._morf_nota)
        self._universo_morfologia = HowToBox(tr("stats.universo.morfologia"))
        layout.addWidget(self._universo_morfologia)
        self._morf_bottone = primary_button(tr("stats.compute"))
        self._morf_bottone.clicked.connect(lambda: self._calcola("morfologia", forzato=True))
        riga = QHBoxLayout()
        riga.addWidget(self._morf_bottone)
        riga.addStretch(1)
        contenitore = QWidget(); contenitore.setLayout(riga)
        layout.addWidget(contenitore)

        self._morf_tabs = QTabWidget()
        self._morf_tabelle: dict[str, DataTable] = {}
        self._morf_note: dict[str, QLabel] = {}
        for chiave, _slot, _pos in DISTRIBUZIONI:
            tabella = DataTable(min_height=300)
            nota = paragraph("", "hint")
            scheda = Card()
            scheda.add(nota)
            scheda.add(tabella, 1)
            self._morf_tabelle[chiave] = tabella
            self._morf_note[chiave] = nota
            self._morf_tabs.addTab(scheda, tr(f"stats.slot.{chiave}"))
        layout.addWidget(self._morf_tabs, 1)
        return pagina

    # ── card 2: syntax ────────────────────────────────────────────────────
    def _scheda_sintassi(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._sin_nota = paragraph(tr("stats.sin.hint"), "hint")
        layout.addWidget(self._sin_nota)
        self._universo_sintassi = HowToBox(tr("stats.universo.sintassi"))
        layout.addWidget(self._universo_sintassi)
        self._sin_bottone = primary_button(tr("stats.compute"))
        self._sin_bottone.clicked.connect(lambda: self._calcola("sintassi", forzato=True))
        riga = QHBoxLayout()
        riga.addWidget(self._sin_bottone)
        riga.addStretch(1)
        contenitore = QWidget(); contenitore.setLayout(riga)
        layout.addWidget(contenitore)

        self._sin_scheda = Card(tr("stats.sin.misure"))
        self._sin_valori = KeyValueList()
        self._sin_scheda.add(self._sin_valori)
        self._sin_esclusioni = paragraph("", "hint")
        self._sin_scheda.add(self._sin_esclusioni)
        layout.addWidget(self._sin_scheda)

        self._sin_relazioni_scheda = Card(tr("stats.syn.relazioni"))
        self._sin_relazioni = DataTable(min_height=300)
        self._sin_relazioni_scheda.add(self._sin_relazioni, 1)
        layout.addWidget(self._sin_relazioni_scheda, 1)
        return pagina

    # ── card 3: frequency lists ───────────────────────────────────────────
    def _scheda_frequenza(self) -> QWidget:
        from greek_corpus_pipeline.stats import STOPWORD_PROFILES

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        riga = QHBoxLayout()
        self._freq_campo_caption = QLabel(tr("stats.count_the"))
        riga.addWidget(self._freq_campo_caption)
        self._freq_campo = combo([tr("stats.field.lemma"), tr("stats.field.form")],
                                 current=tr("stats.field.lemma"), width=150)
        self._freq_campo.currentIndexChanged.connect(lambda _: self._calcola("frequenza"))
        riga.addWidget(self._freq_campo)

        self._freq_profilo_caption = QLabel(tr("stats.stopword_profile"))
        riga.addWidget(self._freq_profilo_caption)
        # The key of the profile travels in the data and in the cache; on screen it is
        # read translated. The two things must not be the same string.
        self._freq_profilo = QComboBox()
        self._freq_profilo.setMinimumWidth(230)
        for chiave_profilo in STOPWORD_PROFILES:
            self._freq_profilo.addItem(value_label(chiave_profilo), chiave_profilo)
        self._freq_profilo.currentIndexChanged.connect(lambda _: self._calcola("frequenza"))
        riga.addWidget(self._freq_profilo)

        # Five commands to manage a list of lemmas are not what one does on opening this
        # tab: one chooses what to count and presses. They are behind “Advanced
        # options”, and whoever needs them opens them.
        self._freq_avanzate = ghost_button(tr("stats.stop.advanced"))
        self._freq_avanzate.setCheckable(True)
        riga.addWidget(self._freq_avanzate)
        riga.addStretch(1)
        contenitore = QWidget(); contenitore.setLayout(riga)
        layout.addWidget(contenitore)

        riga_avanzate = QHBoxLayout()
        riga_avanzate.setContentsMargins(0, 0, 0, 0)
        self._freq_aggiungi = ghost_button(tr("stats.stop.add"))
        self._freq_aggiungi.clicked.connect(self._stopword_aggiungi)
        riga_avanzate.addWidget(self._freq_aggiungi)
        self._freq_togli = ghost_button(tr("stats.stop.remove"))
        self._freq_togli.clicked.connect(self._stopword_togli)
        riga_avanzate.addWidget(self._freq_togli)
        self._freq_ripristina = ghost_button(tr("stats.stop.reset"))
        self._freq_ripristina.clicked.connect(self._stopword_ripristina)
        riga_avanzate.addWidget(self._freq_ripristina)
        self._freq_esporta = ghost_button(tr("stats.stop.export"))
        self._freq_esporta.clicked.connect(self._stopword_esporta)
        riga_avanzate.addWidget(self._freq_esporta)
        self._freq_importa = ghost_button(tr("stats.stop.import"))
        self._freq_importa.clicked.connect(self._stopword_importa)
        riga_avanzate.addWidget(self._freq_importa)
        riga_avanzate.addStretch(1)
        self._freq_avanzate_box = QWidget()
        self._freq_avanzate_box.setLayout(riga_avanzate)
        self._freq_avanzate_box.setVisible(False)
        self._freq_avanzate.toggled.connect(self._freq_avanzate_box.setVisible)
        layout.addWidget(self._freq_avanzate_box)

        self._freq_bottone = primary_button(tr("stats.compute"))
        self._freq_bottone.clicked.connect(lambda: self._calcola("frequenza", forzato=True))
        riga2 = QHBoxLayout()
        riga2.addWidget(self._freq_bottone)
        riga2.addStretch(1)
        c2 = QWidget(); c2.setLayout(riga2)
        layout.addWidget(c2)

        self._freq_nota = paragraph(tr("stats.freq.hint"), "hint")
        layout.addWidget(self._freq_nota)
        self._universo_frequenza = HowToBox(tr("stats.universo.frequenza"))
        layout.addWidget(self._universo_frequenza)

        self._freq_tabs = QTabWidget()
        self._freq_tabella = DataTable(min_height=320)
        scheda = Card(); scheda.add(self._freq_tabella, 1)
        self._freq_tabs.addTab(scheda, tr("stats.tab_frequency"))

        self._freq_esclusi = DataTable(min_height=320)
        self._freq_esclusi_nota = paragraph("", "hint")
        scheda2 = Card(); scheda2.add(self._freq_esclusi_nota); scheda2.add(self._freq_esclusi, 1)
        self._freq_tabs.addTab(scheda2, tr("stats.stop.excluded"))
        layout.addWidget(self._freq_tabs, 1)
        return pagina

    # ── tab 4: profile of a word ──────────────────────────────────────────
    def _scheda_parola(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # The long explanation is behind a button: the tab is for typing a lemma and
        # pressing, not for reading two paragraphs.
        self._universo_parola = HowToBox(
            f"<p style='margin:0 0 10px 0'>{tr('stats.sketch.hint')}</p>"
            f"<p style='margin:0'>{tr('stats.sketch.unita')}</p>")
        layout.addWidget(self._universo_parola)

        riga = QHBoxLayout()
        self._par_caption = QLabel(tr("stats.sketch_lemma"))
        riga.addWidget(self._par_caption)
        self._par_campo = greek_line_edit("λέγω")
        self._par_campo.setFixedWidth(240)
        self._par_campo.returnPressed.connect(self._profilo_parola)
        riga.addWidget(self._par_campo)
        self._par_bottone = primary_button(tr("stats.compute"))
        self._par_bottone.clicked.connect(self._profilo_parola)
        riga.addWidget(self._par_bottone)
        riga.addStretch(1)
        contenitore = QWidget(); contenitore.setLayout(riga)
        layout.addWidget(contenitore)

        # The lemma searched and its occurrences must be seen at once: they are the
        # answer, and must not sit in a grey line beside the button.
        self._par_testata = QFrame()
        self._par_testata.setObjectName("howto")
        testata = QHBoxLayout(self._par_testata)
        testata.setContentsMargins(16, 12, 16, 12)
        testata.setSpacing(14)
        self._par_lemma = QLabel("")
        self._par_lemma.setStyleSheet(
            "font-family:'GFS Didot','Palatino Linotype',serif; font-size:24px;"
            f"font-weight:700; color:{INK}; background:transparent;")
        self._par_esito = QLabel("")
        self._par_esito.setStyleSheet(
            f"color:{ACCENT}; font-size:13.5px; font-weight:600; background:transparent;")
        self._par_esito.setWordWrap(True)
        testata.addWidget(self._par_lemma)
        testata.addWidget(self._par_esito, 1)
        self._par_testata.setVisible(False)
        layout.addWidget(self._par_testata)

        self._par_tabs = QTabWidget()
        self._par_tabelle: dict[str, DataTable] = {}
        for chiave in SCHEDE_PAROLA:
            tabella = DataTable(min_height=280)
            scheda = Card(); scheda.add(tabella, 1)
            self._par_tabelle[chiave] = tabella
            self._par_tabs.addTab(scheda, tr(f"stats.par.{chiave}"))
        layout.addWidget(self._par_tabs, 1)
        return pagina

    # ── selectors ─────────────────────────────────────────────────────────
    def refresh(self) -> None:
        """Fills the two menus. It computes nothing: the computation is requested by the
        user."""
        ha_corpus = self.state.has_corpus
        self._locked.setVisible(not ha_corpus)
        if not ha_corpus:
            return
        self._popola_dimensioni()
        self._aggiorna_valori()

    def _popola_dimensioni(self) -> None:
        colonne = set(getattr(self.state.tokens, "columns", []))
        corrente = self._dim.currentData()
        self._dim.blockSignals(True)
        self._dim.clear()
        for colonna, chiave in DIMENSIONI:
            if colonna and colonna not in colonne:
                continue          # metadatum absent: the dimension is not there
            if colonna and self.state.tokens[colonna].notna().sum() == 0:
                continue          # column present but empty: same
            self._dim.addItem(tr(chiave), colonna)
        if self._dim.count() == 0:
            self._dim.addItem(tr("stats.dim.corpus"), "")
        indice = self._dim.findData(corrente)
        self._dim.setCurrentIndex(indice if indice >= 0 else 0)
        self._dim.blockSignals(False)

        mancanti = [tr(chiave) for colonna, chiave in DIMENSIONI
                    if colonna and colonna not in colonne]
        self._selezione_nota.setText(
            tr("stats.dim.missing", ", ".join(mancanti)) if mancanti else "")

    def _aggiorna_valori(self) -> None:
        colonna = self._dim.currentData() or ""
        self._val.blockSignals(True)
        self._val.clear()
        if not colonna:
            self._val.setEnabled(False)
            self._val.addItem(tr("stats.whole_corpus"), "")
        else:
            self._val.setEnabled(True)
            valori = (self.state.tokens[colonna].dropna().astype(str)
                      .value_counts().index.tolist())
            for valore in sorted(valori):
                self._val.addItem(valore, valore)
        self._val.blockSignals(False)

    def _dimensione_cambiata(self) -> None:
        self._interagito = True
        self._aggiorna_valori()
        self._calcola(self._scheda_corrente())

    def _selezione_cambiata(self) -> None:
        self._interagito = True
        self._calcola(self._scheda_corrente())

    def _scheda_cambiata(self) -> None:
        if not self._interagito:
            self._interagito = True     # the first click chooses, it does not compute
            return
        self._calcola(self._scheda_corrente())

    def _scheda_corrente(self) -> str:
        return ["morfologia", "sintassi", "frequenza", "parola"][self._tabs.currentIndex()]

    # ── the chosen subset ─────────────────────────────────────────────────
    def _sottoinsieme(self) -> pd.DataFrame:
        """The active records of the chosen group, not the imported records.

        This is the difference between the number that the page shows and the number
        that the run declares. The imported records include what the inclusion filters
        remove, and counting on them would give every corpus a few thousand more words
        than the run declares. The statistics therefore start from the active records,
        which are the unit from which the words descend.
        """
        unita = self.state.units()
        base = self.state.tokens if unita is None else unita.active_records
        colonna = self._dim.currentData() or ""
        if not colonna or colonna not in base.columns:
            return base
        valore = self._val.currentData()
        if valore is None:
            return base
        return base[base[colonna].astype(str) == str(valore)]

    def _chiave(self, scheda: str, *extra: object) -> str:
        """The cache key: corpus, dimension, value, tab, parameters."""
        pezzi = ["stats", scheda, self._dim.currentData() or "corpus",
                 str(self._val.currentData() or ""), *(str(x) for x in extra)]
        return "|".join(pezzi)

    # ── the computation ───────────────────────────────────────────────────
    def _calcola(self, scheda: str, *, forzato: bool = False) -> None:
        if not self.state.has_corpus:
            return
        if scheda == "morfologia":
            self._calcola_morfologia(forzato)
        elif scheda == "sintassi":
            self._calcola_sintassi(forzato)
        elif scheda == "frequenza":
            self._calcola_frequenza(forzato)
        # the profile of a word starts only from its own button

    def _calcola_morfologia(self, forzato: bool) -> None:
        from greek_corpus_pipeline import stats

        chiave = self._chiave("morfologia")
        pronto = self.state.cache_peek(chiave, self.state.tokens)
        if pronto is None and not forzato:
            self._morf_bottone.setVisible(True)
            return
        self._morf_bottone.setVisible(False)
        parte = self._sottoinsieme()

        def calcola():
            return {nome: stats.slot_distribution(parte, indice, restrict_pos=pos)
                    for nome, indice, pos in DISTRIBUZIONI}

        risultato = self.state.cached(chiave, calcola, self.state.tokens)
        for nome, _indice, pos in DISTRIBUZIONI:
            tabella = risultato.get(nome, pd.DataFrame())
            self._morf_tabelle[nome].set_dataframe(tabella)
            totale = int(tabella["occorrenze"].sum()) if not tabella.empty else 0
            self._morf_note[nome].setText(
                tr(f"stats.den.{nome}", number(totale)))

    def _calcola_sintassi(self, forzato: bool) -> None:
        from greek_corpus_pipeline import stats

        chiave = self._chiave("sintassi")
        pronto = self.state.cache_peek(chiave, self.state.tokens, self.state.arcs)
        if pronto is None and not forzato:
            self._sin_bottone.setVisible(True)
            return
        self._sin_bottone.setVisible(False)
        parte = self._sottoinsieme()

        def calcola():
            riassunto = stats.syntax_summary(parte, self.state.arcs)
            return riassunto, stats.relation_distribution(parte)

        riassunto, relazioni = self.state.cached(
            chiave, calcola, self.state.tokens, self.state.arcs)
        mostra = {chiave_: valore for chiave_, valore in riassunto.items()
                  if chiave_ not in {"ragione dell'esclusione"}}
        self._sin_valori.set_items(mostra)
        self._sin_esclusioni.setText(
            tr("stats.sin.esclusioni",
               number(riassunto.get('frasi con archi', 0)),
               number(riassunto.get('frasi senza archi', 0)),
               value_label(riassunto.get("ragione dell'esclusione", ""))))
        self._sin_relazioni.set_dataframe(relazioni)

    def _calcola_frequenza(self, forzato: bool) -> None:
        from greek_corpus_pipeline import stats

        campo = "lemma" if self._freq_campo.currentIndex() == 0 else "form"
        profilo = self._freq_profilo.currentData()
        chiave = self._chiave("frequenza", campo, profilo,
                              ",".join(sorted(self._stop_extra)),
                              ",".join(sorted(self._stop_remove)))
        pronto = self.state.cache_peek(chiave, self.state.tokens)
        if pronto is None and not forzato:
            self._freq_bottone.setVisible(True)
            return
        self._freq_bottone.setVisible(False)
        parte = self._sottoinsieme()

        def calcola():
            # The corpus is filtered once only: the three answers that follow all come
            # from here.
            contenuto = stats._content(parte)
            parole = stats.apply_stopword_profile(
                contenuto, profilo,
                extra=self._stop_extra, remove=self._stop_remove)
            if profilo == "solo parole di contenuto" and campo == "lemma":
                tabella, tfidf = stats.content_words_ranked(
                    parole, profile="nessun filtro", top=500)
            else:
                tabella, tfidf = stats.frequency_list(parole, field=campo), False
            relazione = stats.stopword_profile_report(
                contenuto, profilo, extra=self._stop_extra,
                remove=self._stop_remove, rimasti=parole)
            return tabella, tfidf, relazione

        tabella, tfidf, relazione = self.state.cached(chiave, calcola, self.state.tokens)
        self._freq_tabella.set_dataframe(tabella)
        self._freq_nota.setText(
            tr("stats.freq.tfidf") if tfidf else tr("stats.freq.plain"))
        self._freq_esclusi.set_dataframe(relazione.get("lemmi_esclusi", pd.DataFrame()))
        self._freq_esclusi_nota.setText(
            tr("stats.stop.report",
               number(relazione.get('token_esclusi', 0)),
               decimal(relazione.get("percentuale_esclusa", 0.0))))

    def _profilo_parola(self) -> None:
        """The descriptive and the syntactic profile, on the canonical units.

        The two halves answer two different questions and must be counted on the same
        key of the lemma, otherwise the tab says two numbers for the same word.  The
        associations are computed on the ``words``, which is the only unit in which a
        lexical frequency makes sense.
        """
        from greek_corpus_pipeline import stats

        lemma = self._par_campo.text().strip()
        if not lemma or not self.state.has_corpus:
            return
        parte = self._sottoinsieme()
        chiave = self._chiave("parola", lemma)

        def calcola():
            unita = self.state.units(parte)
            parole = unita.words if unita is not None else parte
            return (stats.lemma_profile(parte, lemma),
                    stats.word_sketch(parole, lemma))

        profilo, sketch = self.state.cached(chiave, calcola, self.state.tokens)
        if not profilo.get("occorrenze"):
            self._par_lemma.setText(lemma)
            self._par_esito.setText(tr("stats.sketch.absent"))
            self._par_testata.setVisible(True)
            for tabella in self._par_tabelle.values():
                tabella.set_dataframe(pd.DataFrame())
            return

        esito = tr("stats.par.trovato",
                   number(profilo['occorrenze']))
        if sketch.get("troncate"):
            esito += "  " + tr("stats.sketch.troncate",
                               number(sketch['troncate']), "40")
        # The spelling on which the profile was computed, not the one typed: whoever
        # writes “ανθρωπος” must see that the answer is about ἄνθρωπος, otherwise the
        # normalisation of the box becomes something that happens without being said.
        self._par_lemma.setText(
            str(profilo.get("chiave") or sketch.get("chiave") or lemma))
        self._par_esito.setText(esito)
        self._par_testata.setVisible(True)

        tabelle = dict(profilo)
        tabelle["associazioni"] = sketch.get("associazioni", pd.DataFrame())
        if not sketch.get("grafie", pd.DataFrame()).empty:
            tabelle["grafie"] = sketch["grafie"]
        for nome, tabella in self._par_tabelle.items():
            tabella.set_dataframe(tabelle.get(nome, pd.DataFrame()))

    # ── the custom stop list ──────────────────────────────────────────────
    def _stopword_aggiungi(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        testo, ok = QInputDialog.getText(self, tr("stats.stop.add"), tr("stats.stop.which"))
        if not ok or not testo.strip():
            return
        for lemma in testo.replace(",", " ").split():
            if lemma not in self._stop_extra:
                self._stop_extra.append(lemma)
            if lemma in self._stop_remove:
                self._stop_remove.remove(lemma)
        self._calcola("frequenza", forzato=True)

    def _stopword_togli(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        testo, ok = QInputDialog.getText(self, tr("stats.stop.remove"), tr("stats.stop.which"))
        if not ok or not testo.strip():
            return
        for lemma in testo.replace(",", " ").split():
            if lemma not in self._stop_remove:
                self._stop_remove.append(lemma)
            if lemma in self._stop_extra:
                self._stop_extra.remove(lemma)
        self._calcola("frequenza", forzato=True)

    def _stopword_ripristina(self) -> None:
        self._stop_extra.clear()
        self._stop_remove.clear()
        self._calcola("frequenza", forzato=True)

    def _stopword_esporta(self) -> None:
        from greek_corpus_pipeline.stats import stopword_list

        percorso, _ = QFileDialog.getSaveFileName(
            self, tr("stats.stop.export"), "stopword.txt", "Testo (*.txt)")
        if not percorso:
            return
        elenco = sorted(stopword_list(extra=self._stop_extra, remove=self._stop_remove))
        with open(percorso, "w", encoding="utf-8") as file:
            file.write("\n".join(elenco))

    def _stopword_importa(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(
            self, tr("stats.stop.import"), "", "Testo (*.txt)")
        if not percorso:
            return
        from greek_corpus_pipeline.stats import GRAMMATICAL_LEMMAS

        with open(percorso, encoding="utf-8") as file:
            letti = {r.strip() for r in file if r.strip() and not r.startswith("#")}
        self._stop_extra = sorted(letti - set(GRAMMATICAL_LEMMAS))
        self._stop_remove = sorted(set(GRAMMATICAL_LEMMAS) - letti)
        self._calcola("frequenza", forzato=True)

    # ── language ──────────────────────────────────────────────────────────
    def retranslate(self) -> None:
        self._locked.setText(tr("step.locked"))
        self._dim_caption.setText(tr("stats.dimension"))
        self._val_caption.setText(tr("stats.value"))
        self._morf_nota.setText(tr("stats.morf.hint"))
        self._sin_nota.setText(tr("stats.sin.hint"))
        self._freq_nota.setText(tr("stats.freq.hint"))
        self._universo_parola.retranslate(
            f"<p style='margin:0 0 10px 0'>{tr('stats.sketch.hint')}</p>"
            f"<p style='margin:0'>{tr('stats.sketch.unita')}</p>")
        self._par_caption.setText(tr("stats.sketch_lemma"))
        self._freq_campo_caption.setText(tr("stats.count_the"))
        self._freq_profilo_caption.setText(tr("stats.stopword_profile"))
        for scheda in ("morfologia", "sintassi", "frequenza"):
            getattr(self, f"_universo_{scheda}").retranslate(
                tr(f"stats.universo.{scheda}"))
        for indice in range(self._freq_profilo.count()):
            self._freq_profilo.setItemText(
                indice, value_label(self._freq_profilo.itemData(indice)))
        self._freq_tabs.setTabText(0, tr("stats.tab_frequency"))
        self._freq_tabs.setTabText(1, tr("stats.stop.excluded"))
        for bottone, chiave in ((self._morf_bottone, "stats.compute"),
                                (self._sin_bottone, "stats.compute"),
                                (self._freq_bottone, "stats.compute"),
                                (self._par_bottone, "stats.compute"),
                                (self._freq_aggiungi, "stats.stop.add"),
                                (self._freq_togli, "stats.stop.remove"),
                                (self._freq_ripristina, "stats.stop.reset"),
                                (self._freq_esporta, "stats.stop.export"),
                                (self._freq_importa, "stats.stop.import"),
                                (self._freq_avanzate, "stats.stop.advanced")):
            bottone.setText(tr(chiave))
        for indice, chiave in enumerate(("stats.tab_morfologia", "stats.tab_sintassi",
                                         "stats.tab_frequency", "stats.tab_sketch")):
            self._tabs.setTabText(indice, tr(chiave))
        for indice, (nome, _s, _p) in enumerate(DISTRIBUZIONI):
            self._morf_tabs.setTabText(indice, tr(f"stats.slot.{nome}"))
        self._sin_scheda.set_title(tr("stats.sin.misure"))
        self._sin_relazioni_scheda.set_title(tr("stats.syn.relazioni"))
        for indice, nome in enumerate(SCHEDE_PAROLA):
            self._par_tabs.setTabText(indice, tr(f"stats.par.{nome}"))
        super().retranslate()
