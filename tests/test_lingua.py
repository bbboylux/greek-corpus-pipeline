# -*- coding: utf-8 -*-
"""The change of language must reach the dropdowns and the charts.

The defect to prevent is this: labels built only once — the list of charts, the metadata
menus, the names of the morphological positions — would stay in the language in which
the window was opened.  Here the real window is opened, the language switch is pressed,
and what is written there is examined.
"""
from __future__ import annotations

import os
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
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def application():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def finestra(application, tmp_path):
    from gui_qt.i18n import T
    from gui_qt.main_window import MainWindow
    T.set_language("it")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    window = MainWindow(workspace)
    yield window
    T.set_language("it")
    window.close()


def _in_inglese(finestra, pagina: str = "charts") -> None:
    """Switches to English from the menu and opens the page, as a user of the program
    would.

    The change of language rewrites the fixed strings of all the pages and redoes the
    computed content of the open page only: the closed ones redo it when they are
    opened.  Testing the guarantee therefore means making both gestures, not only the
    first.
    """
    combo = finestra._language
    for indice in range(combo.count()):
        if combo.itemData(indice) == "en":
            combo.setCurrentIndex(indice)
            break
    else:
        raise AssertionError("English is not in the language menu")
    finestra._go_to(pagina)


def _pagine(finestra) -> dict:
    return getattr(finestra, "_pages", {})


# ── the translator ──────────────────────────────────────────────────────
def test_pick_segue_la_lingua_corrente():
    from gui_qt.i18n import T, pick
    coppia = ("sostantivo", "noun")
    T.set_language("it")
    assert pick(coppia) == "sostantivo"
    T.set_language("en")
    assert pick(coppia) == "noun"
    T.set_language("it")


def test_ogni_grafico_ha_le_due_lingue():
    from gui_qt.i18n import T, tr
    from gui_qt.pages.charts_page import CHARTS
    for key, _needs in CHARTS:
        T.set_language("it")
        italiano = tr(f"chart.{key}")
        T.set_language("en")
        inglese = tr(f"chart.{key}")
        T.set_language("it")
        assert italiano != f"chart.{key}", f"the Italian text of {key} is missing"
        assert inglese != f"chart.{key}", f"the English text of {key} is missing"
        assert italiano != inglese, f"“{key}” has the same string in both languages"


def test_nessuna_chiave_e_rimasta_senza_inglese():
    from gui_qt.i18n import _STRINGS
    senza = [k for k, (it, en) in _STRINGS.items() if not en.strip()]
    assert not senza, f"keys with no English: {senza[:5]}"


# ── the real window ─────────────────────────────────────────────────────
def _carica(finestra, tokens: pd.DataFrame) -> None:
    from greek_corpus_pipeline.storage import run_dir
    stato = finestra.state
    stato.run_id = "run-lingua"
    stato.corpus_name = "prova"
    stato.tokens = tokens
    directory = run_dir(stato.workspace, stato.run_id)
    directory.mkdir(parents=True, exist_ok=True)
    tokens.to_parquet(directory / "tokens.parquet", index=False)


def test_la_lista_dei_grafici_cambia_lingua(finestra, tokens):
    from gui_qt.i18n import T
    pagina = _pagine(finestra)["charts"]
    _carica(finestra, tokens)
    pagina.refresh()
    prima = [pagina._list.item(i).text() for i in range(pagina._list.count())]
    assert any("Segnalazioni per famiglia" in t for t in prima)

    # The language is changed as a user of the program changes it, that is, from the
    # menu: ``retranslate()`` alone rewrites the fixed strings, while the computed
    # content is redone by ``refresh()``, which the window calls on the open page. The
    # short road, calling ``retranslate()`` alone, would not prove the real one.
    _in_inglese(finestra)
    dopo = [pagina._list.item(i).text() for i in range(pagina._list.count())]
    assert any("Findings by family" in t for t in dopo), \
        "the list of charts stayed in Italian"
    assert not any("Segnalazioni per famiglia" in t for t in dopo)


def test_il_menu_dei_gruppi_conserva_il_nome_della_colonna(finestra, tokens):
    """Translating the label must not break the query, which uses the column."""
    from gui_qt.i18n import T
    pagina = _pagine(finestra)["charts"]
    frame = tokens.copy()
    frame["periodo"] = "classico"
    _carica(finestra, frame)
    pagina.refresh()
    valori = [pagina._group.itemData(i) for i in range(pagina._group.count())]
    assert "periodo" in valori
    _in_inglese(finestra)
    valori_en = [pagina._group.itemData(i) for i in range(pagina._group.count())]
    assert valori_en == valori, "the column value changed with the language"
    testi_en = [pagina._group.itemText(i) for i in range(pagina._group.count())]
    assert "period" in testi_en, "the displayed label was not translated"


def test_le_posizioni_morfologiche_seguono_la_lingua(finestra, tokens):
    """The morphology is read in the search panel, and changes language.

    The “Search the corpus” card has no dropdowns for the nine positions: the
    morphological label is read in full in the right-hand panel, once an occurrence is
    chosen.  What this test checks is that a text created only once follows the change
    of language, in the place where it is read.
    """
    from greek_corpus_pipeline.search import WordQuery, find_occurrences

    from gui_qt.i18n import T
    pagina = _pagine(finestra)["search"]
    _carica(finestra, tokens)
    pagina.refresh()
    pagina._on_results(find_occurrences(
        tokens, WordQuery(text="στρατιῶται", field="forma")))
    assert "sostantivo" in pagina._detail.items()["morfologia"]

    T.set_language("en")
    pagina.retranslate()
    assert "noun" in pagina._detail.items()["morfologia"], \
        "the morphological analysis stayed in Italian"
    tendina = pagina._form_mode
    testi = [tendina.itemText(i) for i in range(tendina.count())]
    assert "exact" in testi, "the drop-down values stayed in Italian"


def test_i_filtri_dei_metadati_sono_tradotti(finestra, tokens):
    from gui_qt.i18n import T, tr
    pagina = _pagine(finestra)["search"]
    _carica(finestra, tokens)
    pagina.refresh()
    T.set_language("it")
    assert tr("search.filter.autore") == "Autore"
    T.set_language("en")
    assert tr("search.filter.autore") == "Author"


# ── the steps of the path ───────────────────────────────────────────────
def test_i_passi_della_barra_sono_quelli_del_programma(finestra):
    """The bar offers these steps, in this order, and each of them has its page."""
    from gui_qt.main_window import STEPS
    chiavi = [passo[0] for passo in STEPS]
    assert chiavi == ["load", "overview", "errors", "variation", "review", "search",
                      "stats", "charts", "models", "gold", "rules"]
    assert set(_pagine(finestra)) == set(chiavi)


def test_la_barra_dei_passi_e_numerata_senza_buchi(finestra):
    """The bar of the steps is numbered without gaps."""
    from gui_qt.main_window import RIFERIMENTO, STEPS
    chiavi = [passo[0] for passo in STEPS]
    percorso = [c for c in chiavi if c not in RIFERIMENTO]
    numeri = [finestra._step_buttons[chiave]._number.text() for chiave in percorso]
    assert numeri == [str(n) for n in range(1, len(percorso) + 1)], \
        f"the numbering of the bar has a gap: {numeri}"


def test_le_pagine_di_riferimento_non_sono_passi_numerati(finestra):
    """Numbering a manual tells whoever reads the bar that it must be done last.

    ``The AGDT 2.0 scheme`` is not a step of the path: it is a page to open when needed,
    and it sits under its heading, without a number.
    """
    from gui_qt.main_window import RIFERIMENTO
    assert RIFERIMENTO, "no reference page declared"
    for chiave in RIFERIMENTO:
        bottone = finestra._step_buttons[chiave]
        assert bottone._number.text() == "\u00b7"
        assert not bottone._numerata


def test_lo_schema_agdt_ha_due_sole_schede_nelle_due_lingue(finestra):
    """The label and the functions, and nothing else: no list of the rules."""
    from gui_qt.i18n import T, tr
    pagina = _pagine(finestra)["rules"]
    for lingua in ("it", "en"):
        T.set_language(lingua)
        pagina.retranslate()
        schede = [pagina._tabs.tabText(i) for i in range(pagina._tabs.count())]
        assert schede == [tr("schema.tab.tag"), tr("schema.tab.relations")], schede
        assert not any(s.startswith("schema.") for s in schede), \
            f"a translation is missing: {schede}"
    T.set_language("it")
    assert not hasattr(pagina, "_rules"), "the list of rules is still there"
    assert not hasattr(pagina, "_levels"), "the classification block is still there"


def test_lo_schema_si_legge_dal_modulo_dello_schema(finestra):
    """The tables are generated from ``agdt_schema``: no inventory rewritten by hand."""
    from greek_corpus_pipeline.agdt_schema import (
        POSITION_NAMES, POSITION_VALUES, RELATIONS,
    )
    from gui_qt.i18n import T
    pagina = _pagine(finestra)["rules"]
    pagina.refresh()

    posizioni = pagina._positions.dataframe()
    assert len(posizioni) == len(POSITION_NAMES) == 9
    valori = pagina._values.dataframe()
    assert len(valori) == sum(len(v) for v in POSITION_VALUES.values())

    relazioni = pagina._relations.dataframe()
    assert sorted(relazioni["etichetta AGDT"]) == sorted(RELATIONS), \
        "the displayed inventory is not the schema's"
    assert relazioni["che cosa segna"].str.len().min() > 20, \
        "a function was left without an explanation"

    # The suffixes and the infix, shown with the real function that removes them.
    affissi = pagina._affixes.dataframe()
    assert dict(zip(affissi["etichetta nel file"], affissi["funzione di base"])) \
        == {"SBJ_CO": "SBJ", "PRED_CO_CO": "PRED", "ADV_AP_CO": "ADV",
            "SBJ_ExD0_ADV": "SBJ"}

    for lingua in ("it", "en"):
        T.set_language(lingua)
        pagina.retranslate()
        for tag, _parola in __import__(
                "gui_qt.pages.rules_page", fromlist=["EXAMPLES"]).EXAMPLES:
            assert tag in pagina._examples.text(), f"the example {tag} is missing"
    T.set_language("it")
