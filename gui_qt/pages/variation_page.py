# -*- coding: utf-8 -*-
"""The variation cores: the same thing annotated in two ways.

The page computes nothing of its own. The five planes are those of
``greek_corpus_pipeline.variation``, and the numbers it shows are those that the run
produced: if a table is not there, it is requested from the backend with the same
``run_variation_suite`` that runs in the complete run.

The method is the adaptation of a known technique — Boyd, Dickinson and Meurers 2008 —
and not an invention of this program: if the same word, in the same context, carries two
different labels, at least one of the two deserves a look. The program does not say
which.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QTabWidget,
                             QWidget)

from ..i18n import tr
from ..variazione_testi import guida_html, intestazioni, nascoste, spiegazioni
from ..widgets import (Card, DataTable, MetricGrid, ghost_button, notice,
                       paragraph, primary_button)
from .base import Page

#: The five planes, in the order in which the suite produces them.
PIANI = ("morfologia", "posizioni", "contesto", "dipendenze", "lemmi")


class VariationPage(Page):
    """One plane per tab, and above it the count of the cores."""

    title_key = "variation.title"
    intro_key = "variation.intro"
    howto_keys = ("variation.howto.1", "variation.howto.2", "variation.howto.3")

    def build(self) -> None:
        self._locked = notice(tr("step.locked"), "info")
        self.add(self._locked)

        scheda = Card(tr("variation.counts"))
        self._scheda_conto = scheda
        # The main numbers in tabs, not in a list: they are the first thing one looks at
        # when opening the page, and a two-column list makes them look like a footnote.
        self._conto = MetricGrid(6)
        scheda.add(self._conto)
        riga = QHBoxLayout()
        self._bottone = primary_button(tr("variation.compute"))
        self._bottone.clicked.connect(lambda: self._calcola(forzato=True))
        riga.addWidget(self._bottone)
        self._esito = paragraph("", "hint")
        riga.addWidget(self._esito, 1)
        riga.addStretch(1)
        contenitore = QWidget(); contenitore.setLayout(riga)
        scheda.add(contenitore)
        self.add(scheda)

        self._tabs = QTabWidget()
        self._tabelle: dict[str, DataTable] = {}
        self._guide: dict[str, QLabel] = {}
        self._pulsanti_guida: list = []
        for piano in PIANI:
            # “tipo” (type) repeats the name of the tab in four planes out of five, and
            # in the fifth it does not: in the positions plane it says which of the nine
            # the row is about, and without it one cannot tell whether one is looking at
            # gender or case.
            tabella = DataTable(min_height=320, hidden=nascoste(piano),
                                labels=intestazioni(piano),
                                tips=spiegazioni(piano))
            tabella.set_empty_text("empty.variation", "empty.variation.hint")
            corpo = Card()
            corpo.add(self._riga_guida(piano))
            corpo.add(self._guide[piano])
            corpo.add(tabella, 1)
            self._tabelle[piano] = tabella
            self._tabs.addTab(corpo, tr(f"variation.plane.{piano}"))
        self.add(self._tabs, 1)

    def _riga_guida(self, piano: str) -> QWidget:
        """The “How to read this table” button and the box it opens.

        The box is created closed: the same explanations are already in the tooltip of
        each header, and a page that opens with a wall of definitions is read by nobody.
        """
        guida = QLabel(guida_html(piano))
        guida.setWordWrap(True)
        guida.setTextFormat(Qt.TextFormat.RichText)
        guida.setObjectName("hint")
        guida.setVisible(False)
        self._guide[piano] = guida

        bottone = ghost_button(tr("vartab.howto"))
        bottone.setCheckable(True)
        bottone.toggled.connect(
            lambda aperto, p=piano, b=bottone: self._mostra_guida(p, b, aperto))
        self._pulsanti_guida.append(bottone)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.addWidget(bottone)
        riga.addStretch(1)
        contenitore = QWidget()
        contenitore.setLayout(riga)
        return contenitore

    def _mostra_guida(self, piano: str, bottone, aperto: bool) -> None:
        self._guide[piano].setVisible(aperto)
        bottone.setText(tr("vartab.howto.close") if aperto
                        else tr("vartab.howto")) 

    # ── the computation, which is a request to the backend ─────────────
    def _calcola(self, *, forzato: bool) -> None:
        if not self.state.has_corpus:
            return
        pronte = {p: t for p, t in (self.state.variation or {}).items()
                  if isinstance(t, pd.DataFrame) and not t.empty}
        if not pronte and not forzato:
            return
        if not pronte:
            from greek_corpus_pipeline.variation import run_variation_suite

            def calcola():
                unita = self.state.units()
                if unita is None:
                    return {}
                return run_variation_suite(unita.active_records)

            pronte = self.state.cached("variation_suite", calcola, self.state.tokens)
            self.state.variation = dict(pronte)
        for piano in PIANI:
            self._tabelle[piano].set_dataframe(pronte.get(piano, pd.DataFrame()))
        self._mostra_conto(pronte)

    def _mostra_conto(self, tabelle: dict) -> None:
        voci = {}
        totale = 0
        for piano in PIANI:
            quanti = int(len(tabelle.get(piano, pd.DataFrame())))
            voci[tr(f"variation.plane.{piano}")] = quanti
            totale += quanti
        voci[tr("variation.total")] = totale
        self._conto.set_metrics(voci)
        self._bottone.setVisible(totale == 0)
        self._esito.setText(tr("variation.done") if totale else tr("variation.empty"))

    # ── life cycle ─────────────────────────────────────────────────────
    def refresh(self) -> None:
        ha_corpus = self.state.has_corpus
        self._locked.setVisible(not ha_corpus)
        self._tabs.setVisible(ha_corpus)
        if not ha_corpus:
            self._conto.set_metrics({})
            self._esito.setText("")
            for tabella in self._tabelle.values():
                tabella.set_dataframe(pd.DataFrame())
            return
        self._calcola(forzato=False)
        if not any(not t.dataframe().empty for t in self._tabelle.values()):
            self._mostra_conto({})

    def retranslate(self) -> None:
        self._locked.setText(tr("step.locked"))
        self._bottone.setText(tr("variation.compute"))
        self._scheda_conto.set_title(tr("variation.counts"))
        for piano in PIANI:
            self._tabelle[piano].set_headers(intestazioni(piano), spiegazioni(piano))
            self._guide[piano].setText(guida_html(piano))
        for bottone in self._pulsanti_guida:
            bottone.setText(tr("vartab.howto.close") if bottone.isChecked()
                            else tr("vartab.howto"))
        for indice, piano in enumerate(PIANI):
            self._tabs.setTabText(indice, tr(f"variation.plane.{piano}"))
        super().retranslate()
