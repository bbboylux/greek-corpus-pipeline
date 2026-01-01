# -*- coding: utf-8 -*-
"""Headers and explanations of the tables of the cores, plane by plane.

The same five tables appear in two places — inside “Diagnostic findings”, in the
tab of the inconsistencies, and in the “Variation n-gram” page — and must say
the same things in both.  This module is the only place where they are written,
so the two pages cannot diverge.

**Why the headers are per plane.**  The five planes share the names of the
columns and not their meaning: in the lemma plane the column ``etichette``
(“labels”) contains lemmas, in the positions plane it contains a single
character.  A single translation would be false in three planes out of five.
The name of the datum never changes — filters, sorting and export use it — only
what is read changes.
"""
from __future__ import annotations

from .i18n import data_label, tr

#: The columns that a table of the cores can carry, in the order in which the
#: backend writes them.  ``tipo`` (type) is not shown everywhere: see
#: :data:`MOSTRA_TIPO`.
COLONNE = ("tipo", "nucleo", "chiave", "n_etichette", "etichette",
           "occorrenze", "distribuzione", "esempi")

#: The planes in which the column ``tipo`` says something that the tab does not
#: already say.
#:
#: In the other tabs ``tipo`` repeats the name of the tab.  In the positions plane
#: it does not: there the nine positions are all in the same table, and without
#: this column one cannot tell whether the row speaks of gender or of case.
MOSTRA_TIPO = frozenset({"posizioni"})

#: The planes in which the column ``chiave`` (key) adds something to the core.
#:
#: In the context plane the key is the whole trigram and the core is only the
#: middle word; in the lemma plane the key carries the part of speech.  In the
#: other three it repeats the core — in the dependencies it repeats it even worse,
#: writing the internal separator of the program on the screen — and it is not
#: shown on screen.  It stays in the data, in the export and in the files of the
#: cores: it is hidden, not removed.
MOSTRA_CHIAVE = frozenset({"contesto", "lemmi"})


def _voce(piano: str, colonna: str, prefisso: str) -> str:
    """The entry of the plane if there is one, otherwise the general one, otherwise ""."""
    specifica = f"{prefisso}.{piano}.{colonna}"
    testo = tr(specifica)
    if testo != specifica:
        return testo
    generale = f"{prefisso}.{colonna}"
    testo = tr(generale)
    return "" if testo == generale else testo


def intestazioni(piano: str) -> dict[str, str]:
    """The name to read for each column, where the general one would be false."""
    fuori = {}
    for colonna in COLONNE:
        proprio = _voce(piano, colonna, "varhdr")
        if proprio:
            fuori[colonna] = proprio
    return fuori


def spiegazioni(piano: str) -> dict[str, str]:
    """The explanation of each column, for the tooltip on the header."""
    return {colonna: testo for colonna in COLONNE
            if (testo := _voce(piano, colonna, "varcol"))}


def nascoste(piano: str) -> set[str]:
    """The columns that this tab does not show."""
    fuori = set()
    if piano not in MOSTRA_TIPO:
        fuori.add("tipo")
    if piano not in MOSTRA_CHIAVE:
        fuori.add("chiave")
    return fuori


def guida_html(piano: str) -> str:
    """The box “How to read this table”: one line per column.

    The same text as the tooltip on the header, all together, for whoever does not think
    of moving the mouse over a table.
    """
    righe = []
    fuori_vista = nascoste(piano)
    for colonna in COLONNE:
        if colonna in fuori_vista:
            continue
        testo = _voce(piano, colonna, "varcol")
        if not testo:
            continue
        nome = intestazioni(piano).get(colonna) or data_label(colonna)
        righe.append(f"<p style='margin:0 0 8px 0'><b>{nome}</b> — {testo}</p>")
    return "".join(righe)
