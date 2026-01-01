# -*- coding: utf-8 -*-
"""The explanations of the nuclei tables: one per column, in two languages.

The defect to prevent is not a missing explanation — that is seen — but a *generic
explanation applied to the wrong plane*: “the same word with two labels” said of the
lemma plane, where the value is a lemma and not a label, is a false sentence written
with the air of being helpful.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication  # noqa: E402

PIANI = ("morfologia", "posizioni", "contesto", "dipendenze", "lemmi")

#: The columns that every nuclei table carries, minus ``tipo`` (“type”), which is shown
#: in one plane only.
COLONNE = ("nucleo", "chiave", "n_etichette", "etichette", "occorrenze",
           "distribuzione", "esempi")


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def italiano():
    """For the tests that read the Italian texts: they choose the language themselves
    instead of inheriting it from the test that ran before, and give it back."""
    from gui_qt.i18n import T
    lingua = T.language
    T.set_language("it")
    yield
    T.set_language(lingua)


def test_ogni_colonna_di_ogni_piano_ha_la_sua_spiegazione():
    from gui_qt.variazione_testi import spiegazioni
    for piano in PIANI:
        testi = spiegazioni(piano)
        for colonna in COLONNE:
            assert testi.get(colonna), f"“{colonna}” without an explanation in “{piano}”"


def test_ogni_spiegazione_italiana_ha_la_sua_inglese():
    from gui_qt.i18n import T
    from gui_qt.variazione_testi import spiegazioni

    lingua = T.language
    try:
        T.set_language("it")
        italiano = {p: spiegazioni(p) for p in PIANI}
        T.set_language("en")
        inglese = {p: spiegazioni(p) for p in PIANI}
    finally:
        T.set_language(lingua)

    for piano in PIANI:
        assert set(italiano[piano]) == set(inglese[piano])
        for colonna, testo in italiano[piano].items():
            altro = inglese[piano][colonna]
            assert altro, f"“{colonna}” of “{piano}” has no English"
            assert altro != testo, \
                f"“{colonna}” of “{piano}”: the two languages give the same string"


def test_il_nucleo_e_spiegato_per_il_piano_e_non_in_generale(italiano):
    """Five planes, five different definitions of the nucleus."""
    from gui_qt.variazione_testi import spiegazioni
    testi = {p: spiegazioni(p)["nucleo"] for p in PIANI}
    assert len(set(testi.values())) == len(PIANI), \
        "two planes give the same definition of nucleus"
    # and each one names the key of its own plane
    atteso = {
        "morfologia": "etichetta morfologica completa",
        "posizioni": "una sola posizione",
        "contesto": "trigramma",
        "dipendenze": "coppia di parole",
        "lemmi": "forma e parte del discorso",
    }
    for piano, frammento in atteso.items():
        assert frammento in testi[piano], \
            f"the definition of “{piano}” does not mention “{frammento}”"


def test_le_intestazioni_non_chiamano_etichette_quello_che_non_lo_e(italiano):
    """In the lemmas and in the dependencies the value is not a morphological label."""
    from gui_qt.variazione_testi import intestazioni
    assert intestazioni("lemmi")["etichette"] == "lemmi"
    assert intestazioni("dipendenze")["etichette"] == "relazioni"
    assert intestazioni("posizioni")["etichette"] == "valori"
    # where the value *is* a morphological label, the name stays that one
    assert "etichette" not in intestazioni("morfologia")
    assert "etichette" not in intestazioni("contesto")


def test_le_posizioni_dicono_di_quale_posizione_parla_la_riga():
    """The nine positions are in a single table: without “tipo” (“type”) they are a heap."""
    from gui_qt.variazione_testi import intestazioni, nascoste
    assert "tipo" not in nascoste("posizioni")
    assert intestazioni("posizioni")["tipo"]
    for piano in ("morfologia", "contesto", "dipendenze", "lemmi"):
        assert "tipo" in nascoste(piano), \
            f"in “{piano}” the column “tipo” repeats the name of the tab"


def test_la_guida_elenca_solo_le_colonne_che_si_vedono(italiano):
    from gui_qt.variazione_testi import guida_html, intestazioni
    for piano in PIANI:
        html = guida_html(piano)
        for colonna in COLONNE:
            nome = intestazioni(piano).get(colonna)
            if nome:
                assert f"<b>{nome}</b>" in html, \
                    f"the guide of “{piano}” does not mention “{nome}”"
    assert "<b>posizione del tag</b>" in guida_html("posizioni")
    assert "posizione del tag" not in guida_html("morfologia")


def test_le_tabelle_a_video_portano_le_spiegazioni(application, tmp_path):
    """It is not enough that the texts exist: they must reach the header."""
    from PyQt6.QtCore import Qt
    from gui_qt.pages.base import AppState
    from gui_qt.pages.variation_page import VariationPage
    from gui_qt.variazione_testi import spiegazioni

    import pandas as pd
    from greek_corpus_pipeline.variation import NUCLEUS_COLUMNS

    pagina = VariationPage(AppState(workspace=tmp_path))
    pagina.build()
    finto = pd.DataFrame([{c: "x" for c in NUCLEUS_COLUMNS}])
    for piano in PIANI:
        tabella = pagina._tabelle[piano]
        tabella.set_dataframe(finto)
        modello = tabella._model
        for indice, nome in enumerate(finto.columns):
            atteso = spiegazioni(piano).get(str(nome))
            visto = modello.headerData(indice, Qt.Orientation.Horizontal,
                                       Qt.ItemDataRole.ToolTipRole)
            assert visto == (atteso or None), \
                f"“{nome}” of “{piano}”: the tooltip does not arrive"
    pagina.deleteLater()
    application.processEvents()


def test_la_sezione_non_dice_errore():
    """“Incoerenze fra passi simili” (“Inconsistencies between similar passages”) describes
    a variation, not an error."""
    from gui_qt.i18n import T, tr
    lingua = T.language
    try:
        for scelta, vietata in (("it", "sbagliat"), ("en", "wrong")):
            T.set_language(scelta)
            for chiave in ("errors.variation_intro", "variation.intro"):
                testo = tr(chiave).lower()
                assert "error" not in testo.replace("errore può", ""), \
                    f"“{chiave}” in {scelta} speaks of an error"
                if vietata in testo:
                    assert "non significa" in testo or "does not" in testo, \
                        f"“{chiave}” in {scelta} says that the annotation is wrong"
    finally:
        T.set_language(lingua)


def test_la_colonna_del_tipo_segue_la_lingua():
    """The backend writes “posizione 4 — Tempo” (“position 4 — Tense”): on screen in
    English it must read in English."""
    from greek_corpus_pipeline.agdt_schema import POSITION_NAMES
    from gui_qt.i18n import T, value_label

    lingua = T.language
    try:
        for indice, (it_nome, en_nome) in POSITION_NAMES.items():
            dato = f"posizione {indice + 1} — {it_nome}"
            T.set_language("it")
            assert value_label(dato) == dato
            T.set_language("en")
            tradotto = value_label(dato)
            assert tradotto != dato, f"“{dato}” stays in Italian when English is selected"
            assert en_nome in tradotto
    finally:
        T.set_language(lingua)


def test_ogni_tipo_che_il_backend_scrive_ha_la_sua_voce():
    """If a plane changed its own “tipo”, the test would say so at once."""
    import pandas as pd
    from greek_corpus_pipeline.variation import run_variation_suite
    from gui_qt.i18n import _STRINGS

    frame = pd.DataFrame({
        "source_file": ["a.xml"] * 8,
        "document_id": ["d"] * 8,
        "sentence_index": [1, 1, 1, 1, 2, 2, 2, 2],
        "sentence_id": ["1"] * 4 + ["2"] * 4,
        "token_id": [1, 2, 3, 4, 1, 2, 3, 4],
        "token_index": [0, 1, 2, 3, 0, 1, 2, 3],
        "form": ["ὁ", "λόγος", "καί", "ἦν", "ὁ", "λόγος", "καί", "ἦν"],
        "lemma": ["ὁ", "λόγος", "καί", "εἰμί", "ὁ", "λόγος1", "καί", "εἰμί"],
        "postag": ["l-s---mn-", "n-s---mn-", "c--------", "v3siia---",
                   "l-s---mn-", "n-s---fn-", "d--------", "v3siia---"],
        "relation": ["ATR", "SBJ", "AuxY", "PRED",
                     "ATR", "OBJ", "AuxY", "PRED"],
        "head": [2, 4, 4, 0, 2, 4, 4, 0],
    })
    tipi = set()
    for tabella in run_variation_suite(frame).values():
        if not tabella.empty and "tipo" in tabella.columns:
            tipi |= set(tabella["tipo"].astype(str))
    assert tipi, "the test corpus produces no nucleus"
    for tipo in sorted(tipi):
        assert f"value.{tipo}" in _STRINGS, f"«{tipo}» non ha una voce value.*"
