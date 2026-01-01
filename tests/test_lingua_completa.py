# -*- coding: utf-8 -*-
"""With English chosen, not one Italian word must remain in the whole window.

The test opens the real window, changes language from the menu as a user of
the program does, visits every page with and without a corpus, presses the
computation buttons, opens every card, and then walks the widget tree reading
everything that is visible: labels, tooltips, placeholders, titles, cards,
dropdown entries, table headers and texts drawn inside the figures.

The tell-tales are words that do not exist in English and are very common in
Italian.  The list is deliberately narrow: better to miss a report than to
fill the report with false positives on Greek and proper names.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QComboBox, QListWidget, QPlainTextEdit,
    QTableView, QTabWidget, QTextEdit, QWidget,
)

SPIE = """
 il lo la gli le un uno una dei degli delle del della dello nel nella nei nelle
 al alla ai alle dal dalla dai dalle sul sulla sui sulle col
 che non sono stato stata stati state essere
 questo questa questi queste quello quella quelli quelle
 quando perche perché quanto quanti quante ogni tutti tutte tutto tutta
 senza sopra sotto dopo prima ancora anche soltanto solo gia già
 puo può deve devono viene vengono fatta serve servono
 parola parole forma forme lemmi etichette relazione relazioni
 occorrenze conteggio conteggi frase frasi documento documenti riga righe
 segnalazione segnalazioni controllo controlli errore errori regola regole
 nessuno nessuna niente
 carica caricato caricata mostra nascondi esporta salva apri chiudi scegli
 elabora calcola cerca trova correggi
 lingua guida pronto elaborazione
"""
PAROLE = {p for p in SPIE.split() if p}
ITALIANO = re.compile(r"(?<![\w'-])(" + "|".join(sorted(PAROLE, key=len, reverse=True))
                      + r")(?![\w'-])", re.IGNORECASE)


def _e_dato(testo: str) -> bool:
    t = testo.strip()
    if not t or len(t) < 3:
        return True
    if any("Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿" for c in t):
        return True
    if re.fullmatch(r"[\d\s.,%/:+()\-–—×·]+", t):
        return True
    return bool(re.fullmatch(r"[a-z0-9_.\-]+", t))


#: Bibliographic Latin, which is written the same in English.  “Boyd et al.
#: (2008)” contains “al”, which is also an Italian preposition: without this
#: line the tell-tale would fire on a correct citation.
LATINO = re.compile(r"\bet\s+al\.", re.IGNORECASE)


def _sospetto(testo: str) -> str:
    if _e_dato(testo):
        return ""
    trovate = ITALIANO.findall(LATINO.sub(" ", testo))
    return ", ".join(sorted({w.lower() for w in trovate})) if trovate else ""


def _stringhe(w) -> list[tuple[str, str]]:
    fuori = []
    nome = type(w).__name__
    for metodo in ("text", "toolTip", "placeholderText", "windowTitle", "title"):
        funzione = getattr(w, metodo, None)
        if callable(funzione):
            try:
                valore = funzione()
            except Exception:                          # noqa: BLE001
                continue
            if isinstance(valore, str) and valore.strip():
                fuori.append((f"{nome}.{metodo}", valore))
    if isinstance(w, QComboBox):
        fuori += [(f"{nome}.item", w.itemText(i)) for i in range(w.count())]
    if isinstance(w, QListWidget):
        fuori += [(f"{nome}.row", w.item(i).text()) for i in range(w.count())]
    if isinstance(w, QTabWidget):
        fuori += [(f"{nome}.tab", w.tabText(i)) for i in range(w.count())]
    if isinstance(w, (QTextEdit, QPlainTextEdit)):
        fuori.append((f"{nome}.body", w.toPlainText()[:400]))
    if isinstance(w, QTableView) and w.model() is not None:
        modello = w.model()
        for c in range(min(modello.columnCount(), 40)):
            valore = modello.headerData(c, Qt.Orientation.Horizontal,
                                        Qt.ItemDataRole.DisplayRole)
            if isinstance(valore, str):
                fuori.append((f"{nome}.header", valore))
    return fuori


def _cammina(radice) -> list[str]:
    trovate = []
    for widget in [radice] + radice.findChildren(QWidget):
        for sorgente, testo in _stringhe(widget):
            spia = _sospetto(testo)
            if spia:
                trovate.append(f"[{sorgente}] {testo[:120]!r} ← {spia}")
    return trovate


def _apri_tutto(pagina, app) -> None:
    for bottone in pagina.findChildren(QAbstractButton):
        if not bottone.isEnabled():
            continue
        testo = (bottone.text() or "").lower()
        if any(x in testo for x in ("compute", "profile", "find", "draw", "show")):
            try:
                bottone.click(); app.processEvents()
            except Exception:                          # noqa: BLE001
                pass
    for schede in pagina.findChildren(QTabWidget):
        for i in range(schede.count()):
            schede.setCurrentIndex(i); app.processEvents()


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def finestra_inglese(application, tmp_path, tokens):
    from gui_qt.i18n import T
    from gui_qt.main_window import MainWindow
    from greek_corpus_pipeline.storage import run_dir

    T.set_language("it")
    workspace = tmp_path / "workspace"; workspace.mkdir()
    finestra = MainWindow(workspace)
    stato = finestra.state
    stato.run_id = "lingua"; stato.corpus_name = "prova"
    stato.tokens = tokens
    directory = run_dir(workspace, "lingua"); directory.mkdir(parents=True, exist_ok=True)
    tokens.to_parquet(directory / "tokens.parquet", index=False)

    combo = finestra._language
    for indice in range(combo.count()):
        if combo.itemData(indice) == "en":
            combo.setCurrentIndex(indice)
            break
    else:
        pytest.fail("English is not in the language menu")
    application.processEvents()
    yield finestra
    T.set_language("it")
    finestra.close()
    application.processEvents()


def test_con_l_inglese_scelto_non_resta_una_parola_italiana(finestra_inglese, application):
    from gui_qt.main_window import STEPS

    trovate: list[str] = []
    for chiave, *_ in STEPS:
        pagina = finestra_inglese._pages.get(chiave)
        if pagina is None:
            continue
        finestra_inglese._go_to(chiave)
        pagina.retranslate(); pagina.refresh()
        application.processEvents()
        _apri_tutto(pagina, application)
        trovate += [f"{chiave}: {riga}" for riga in _cammina(pagina)]
    trovate += [f"finestra: {riga}" for riga in _cammina(finestra_inglese)]
    assert not trovate, "Italian strings with English selected:\n" + "\n".join(trovate[:20])


def test_anche_le_pagine_vuote_sono_in_inglese(finestra_inglese, application):
    """Empty states are the ones that are seen first, and the ones that most often slip
    through."""
    from gui_qt.main_window import STEPS

    stato = finestra_inglese.state
    stato.run_id = None
    stato.tokens = pd.DataFrame(); stato.findings = pd.DataFrame()
    stato.arcs = pd.DataFrame(); stato.variation = {}
    stato.invalidate()

    trovate: list[str] = []
    for chiave, *_ in STEPS:
        pagina = finestra_inglese._pages.get(chiave)
        if pagina is None:
            continue
        finestra_inglese._go_to(chiave)
        pagina.retranslate(); pagina.refresh()
        application.processEvents()
        trovate += [f"{chiave}: {riga}" for riga in _cammina(pagina)]
    assert not trovate, "Italian strings in the empty state:\n" + "\n".join(trovate[:20])


def test_nessuna_stringa_visibile_e_scritta_nel_codice():
    """What the tour of the interface does not manage to bring up.

    Error messages and rare branches are not seen by opening the pages, but if they are
    written by hand in the source they stay in Italian for ever.
    """
    import ast

    visibili = {
        "setText", "setToolTip", "setPlaceholderText", "setWindowTitle", "setTitle",
        "addItem", "addTab", "setTabText", "setItemText", "setLabelText",
        "information", "warning", "critical", "question", "about",
        "paragraph", "heading", "notice", "primary_button", "ghost_button",
        "set_title",
    }
    spia = re.compile(r"(?<![\w'])(il|lo|la|gli|le|un|del|della|nel|che|non|sono|"
                      r"senza|perch[eé]|carica|mostra|esporta|salva|cerca|errore|"
                      r"frase|frasi|parola|parole|segnalazioni|controlli|regole)"
                      r"(?![\w'])", re.IGNORECASE)
    colpevoli = []
    for percorso in sorted((ROOT / "gui_qt").rglob("*.py")):
        if "__pycache__" in str(percorso) or percorso.name.startswith("i18n"):
            continue
        albero = ast.parse(percorso.read_text(encoding="utf-8"), str(percorso))
        for nodo in ast.walk(albero):
            if not isinstance(nodo, ast.Call):
                continue
            nome = (nodo.func.attr if isinstance(nodo.func, ast.Attribute)
                    else nodo.func.id if isinstance(nodo.func, ast.Name) else "")
            if nome not in visibili:
                continue
            for argomento in list(nodo.args) + [k.value for k in nodo.keywords]:
                if (isinstance(argomento, ast.Constant)
                        and isinstance(argomento.value, str)
                        and spia.search(argomento.value)):
                    colpevoli.append(
                        f"{percorso.name}:{nodo.lineno} {nome}(…) {argomento.value[:80]!r}")
    assert not colpevoli, "Italian strings in the code:\n" + "\n".join(colpevoli[:20])
