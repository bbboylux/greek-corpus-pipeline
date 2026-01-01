# -*- coding: utf-8 -*-
"""Searching the corpus: type the word, find it, read what it is.

Three things must work, and they are checked here one by one.

*Typing the word.* ἄνθρωπος, ανθρωπος and anthropos are the same word, and
must return exactly the same rows — not “more or less the same”: the same.

*Form and lemma.* They are two searches, not two filters: searching for a form
must in no case also restrict by lemma, and vice versa.

*Occurrences first, then the analysis.* Every occurrence arrives with the
sentence in which it occurs; once the occurrence is chosen, the detail says
five things — morphology, syntactic function, lemma, lemma of the head,
author — and nothing else.
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

from greek_corpus_pipeline.search import (           # noqa: E402
    DETAIL_FIELDS, LIST_COLUMNS, OCCURRENCE_COLUMNS, WordQuery, detail_of,
    find_forms, find_lemmas, find_occurrences, key_column, search_key,
)


# ── A fake corpus but with the real columns ─────────────────────────────
#
# The columns are those that ``xmlio.load_corpus_from_directory`` produces, plus
# ``autore`` (“author”), which the program adds when it recognises the document: a table
# that did not have the same shape would prove something about itself and nothing about
# the program.

_SENTENCES = [
    # (document, author, [(id, form, lemma, postag, relation, head), …])
    ("aristotele-pol", "Aristotele", [
        (1, "ὁ", "ὁ", "l-s---mn-", "ATR", 2),
        (2, "ἄνθρωπος", "ἄνθρωπος", "n-s---mn-", "SBJ", 3),
        (3, "λέγει", "λέγω", "v3spia---", "PRED", 0),
    ]),
    ("aristotele-pol", "Aristotele", [
        (1, "τοῦ", "ὁ", "l-s---mg-", "ATR", 2),
        (2, "ἀνθρώπου", "ἄνθρωπος", "n-s---mg-", "ATR", 4),
        (3, "ἡ", "ὁ", "l-s---fn-", "ATR", 4),
        (4, "φύσις", "φύσις", "n-s---fn-", "PRED", 0),
    ]),
    ("isocrate-or", "Isocrate", [
        (1, "οἱ", "ὁ", "l-p---mn-", "ATR", 2),
        (2, "ἄνθρωποι", "ἄνθρωπος", "n-p---mn-", "SBJ", 4),
        (3, "λόγῳ", "λόγος", "n-s---md-", "ADV", 4),
        (4, "διαφέρουσιν", "διαφέρω", "v3ppia---", "PRED", 0),
    ]),
    ("isocrate-or", "Isocrate", [
        (1, "ὁ", "ὁ", "l-s---mn-", "ATR", 2),
        (2, "λόγος", "λόγος", "n-s---mn-", "SBJ", 4),
        (3, "ἀληθής", "ἀληθής", "a-s---mn-", "PNOM", 4),
        (4, "ἐστιν", "εἰμί", "v3spia---", "PRED", 0),
    ]),
]


@pytest.fixture
def corpus() -> pd.DataFrame:
    rows = []
    counters: dict[str, int] = {}
    for document, author, words in _SENTENCES:
        counters[document] = counters.get(document, 0) + 1
        index = counters[document]
        for position, (token_id, form, lemma, postag, relation, head) in enumerate(words, 1):
            rows.append({
                "corpus": "prova",
                "analyzer": "corpus",
                "source_file": f"{document}.xml",
                "document_id": document,
                "sentence_index": index,
                "sentence_id": str(index),
                "token_index": position,
                "token_id": token_id,
                "head": head,
                "ref": None,
                "form": form,
                "lemma": lemma,
                "postag": postag,
                "relation": relation,
                "artificial": None,
                "annotation_mode": None,
                "tlg_author": "",
                "tlg_work": "",
                "cts_urn": "",
                "autore": author,
            })
    return pd.DataFrame(rows)


# ── 1. Typing the word ──────────────────────────────────────────────────

def test_le_tre_grafie_trovano_le_stesse_righe(corpus):
    """With accents, without accents, in Latin characters: one result."""
    atteso = find_forms(corpus, "ἄνθρωπος")
    assert len(atteso) == 1
    assert atteso.iloc[0]["forma"] == "ἄνθρωπος"
    for scritta in ("ανθρωπος", "ΑΝΘΡΩΠΟΣ", "anthropos", "Anthropos",
                    "anthrōpos", "anthrwpos"):
        pd.testing.assert_frame_equal(find_forms(corpus, scritta), atteso)


def test_il_sigma_finale_vale_come_il_sigma(corpus):
    """ς and σ are the same letter for whoever searches, and nobody can be expected to type
    the right one."""
    pd.testing.assert_frame_equal(find_forms(corpus, "ανθρωποσ"),
                                  find_forms(corpus, "ἄνθρωπος"))


def test_le_vocali_lunghe_si_possono_precisare(corpus):
    """Latin e and o stand for both short and long vowels until the user decides."""
    # “logo” leaves the two vowels undecided: it finds λόγῳ, which has an omega.
    assert find_forms(corpus, "logo")["forma"].tolist() == ["λόγῳ"]
    # written long, only η and ω count…
    assert find_forms(corpus, "logō")["forma"].tolist() == ["λόγῳ"]
    # …and in Greek the question does not arise: the letter is already written.
    assert find_forms(corpus, "λογω")["forma"].tolist() == ["λόγῳ"]
    # an omicron written as such does not become an omega
    assert find_forms(corpus, "logos")["forma"].tolist() == ["λόγος"]
    assert find_forms(corpus, "lōgos")["forma"].tolist() == []


def test_lo_spirito_aspro_si_puo_scrivere_h(corpus):
    """ὁ is searched as “ho”: this is how the breathing is written in Latin characters."""
    assert find_forms(corpus, "ho")["forma"].tolist() == ["ὁ", "ὁ"]


def test_le_modalita_di_confronto(corpus):
    forme = find_forms(corpus, "anthrop", mode="inizia con")["forma"].tolist()
    assert forme == ["ἄνθρωπος", "ἀνθρώπου", "ἄνθρωποι"]
    contenute = find_forms(corpus, "nthrop", mode="contiene")["forma"].tolist()
    assert contenute == ["ἄνθρωπος", "ἀνθρώπου", "ἄνθρωποι"]


def test_la_chiave_normalizzata_e_una_copia(corpus):
    """The key is built next to the corpus, never inside it."""
    prima = corpus.copy(deep=True)
    chiavi = key_column(corpus["form"])
    assert chiavi.iloc[1] == "anthrōpos"
    assert search_key("ἄνθρωπος") == search_key("anthrōpos") == "anthrōpos"
    pd.testing.assert_frame_equal(corpus, prima)


def test_la_ricerca_non_tocca_il_corpus(corpus):
    prima = corpus.copy(deep=True)
    find_forms(corpus, "anthropos")
    find_lemmas(corpus, "anthropos")
    pd.testing.assert_frame_equal(corpus, prima)


# ── 2. Form and lemma, independent of each other ────────────────────────

def test_forma_e_lemma_sono_due_ricerche(corpus):
    """The form is that of the text, the lemma that of the dictionary."""
    per_forma = find_forms(corpus, "ἄνθρωπος")
    per_lemma = find_lemmas(corpus, "ἄνθρωπος")
    assert per_forma["forma"].tolist() == ["ἄνθρωπος"]
    assert per_lemma["forma"].tolist() == ["ἄνθρωπος", "ἀνθρώπου", "ἄνθρωποι"]


def test_una_ricerca_legge_una_colonna_sola(corpus):
    """No query can express “form X *and* lemma Y”: there is no such field."""
    assert WordQuery(text="x", field="forma").column_name == "form"
    assert WordQuery(text="x", field="lemma").column_name == "lemma"
    # A form that is never a lemma is found all the same: the search by form does not go
    # through the lemma.
    assert len(find_forms(corpus, "ἀνθρώπου")) == 1
    # And a lemma that is never a form is found all the same: εἰμί is in the corpus only
    # as ἐστιν.
    assert find_lemmas(corpus, "εἰμί")["forma"].tolist() == ["ἐστιν"]
    assert find_forms(corpus, "εἰμί")["forma"].tolist() == []


def test_una_ricerca_vuota_non_trova_niente(corpus):
    vuoto = find_occurrences(corpus, WordQuery(text="   ", field="forma"))
    assert vuoto.empty
    assert list(vuoto.columns) == OCCURRENCE_COLUMNS
    assert find_forms(corpus, "ξξξξ").empty


# ── 3. The occurrences, then the detail ─────────────────────────────────

def test_ogni_occorrenza_porta_la_sua_frase(corpus):
    riga = find_forms(corpus, "ἀνθρώπου").iloc[0]
    assert riga["contesto"] == "τοῦ «ἀνθρώπου» ἡ φύσις"
    assert riga["n."] == 1
    # The list has three columns: number, form, sentence.
    assert LIST_COLUMNS == ["n.", "forma", "contesto"]
    assert set(LIST_COLUMNS) <= set(find_forms(corpus, "ἀνθρώπου").columns)


def test_il_contesto_si_ferma_alla_fine_della_frase(corpus):
    """The sentence next to it is the one of the corpus, not the neighbouring words in the
    file."""
    riga = find_forms(corpus, "ἄνθρωπος").iloc[0]
    assert riga["contesto"] == "ὁ «ἄνθρωπος» λέγει"
    ultima = find_forms(corpus, "διαφέρουσιν").iloc[0]
    assert ultima["contesto"] == "οἱ ἄνθρωποι λόγῳ «διαφέρουσιν»"


def test_il_dettaglio_dice_cinque_cose_e_nient_altro(corpus):
    riga = find_forms(corpus, "anthropos").iloc[0]
    dettaglio = detail_of(riga)
    assert list(dettaglio) == list(DETAIL_FIELDS)
    assert len(dettaglio) == 5
    assert dettaglio["morfologia"].startswith(
        "sostantivo · singolare · maschile · nominativo")
    assert "n-s---mn-" in dettaglio["morfologia"]
    assert dettaglio["funzione sintattica"].startswith("soggetto")
    assert dettaglio["lemma"] == "ἄνθρωπος"
    assert dettaglio["lemma della testa"] == "λέγω"
    assert dettaglio["autore"] == "Aristotele"


def test_il_dettaglio_si_legge_anche_in_inglese(corpus):
    dettaglio = detail_of(find_forms(corpus, "anthropos").iloc[0], "en")
    assert dettaglio["morfologia"].startswith(
        "noun · singular · masculine · nominative")
    assert dettaglio["funzione sintattica"].startswith("subject")


def test_il_lemma_della_testa_esce_dalla_stessa_frase(corpus):
    """head=4 means “token 4 *of this sentence*”, and every sentence has one."""
    teste = dict(zip(find_lemmas(corpus, "ἄνθρωπος")["forma"],
                     find_lemmas(corpus, "ἄνθρωπος")["lemma_testa"]))
    assert teste == {"ἄνθρωπος": "λέγω",       # sentence 1, head 3
                     "ἀνθρώπου": "φύσις",      # sentence 2, head 4
                     "ἄνθρωποι": "διαφέρω"}    # sentence 3, head 4 of another document


def test_la_radice_non_ha_lemma_della_testa(corpus):
    riga = find_forms(corpus, "λέγει").iloc[0]
    assert riga["lemma_testa"] == ""
    assert detail_of(riga)["lemma della testa"] == "—"


def test_l_autore_arriva_dal_documento(corpus):
    assert detail_of(find_forms(corpus, "λόγος").iloc[0])["autore"] == "Isocrate"


def test_un_corpus_senza_autore_non_inventa_niente(corpus):
    senza = corpus.drop(columns=["autore"])
    assert detail_of(find_forms(senza, "λόγος").iloc[0])["autore"] == "—"


# ── 4. The same, on a corpus really loaded from XML ─────────────────────

def test_funziona_sul_corpus_di_esempio(tokens):
    """The ``tokens`` fixture is a real AGDT treebank, read from its XMLs."""
    atteso = find_forms(tokens, "στρατιῶται")
    assert len(atteso) == 1
    for scritta in ("στρατιωται", "stratiotai", "stratiōtai"):
        pd.testing.assert_frame_equal(find_forms(tokens, scritta), atteso)
    dettaglio = detail_of(atteso.iloc[0])
    assert dettaglio["lemma"] == "στρατιώτης1"
    assert dettaglio["lemma della testa"] == "φυλάσσω"
    assert atteso.iloc[0]["contesto"] == "τὴν πόλιν ἐφύλαττον οἱ «στρατιῶται»"


# ── 5. The page ─────────────────────────────────────────────────────────

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication                      # noqa: E402


@pytest.fixture(scope="module")
def application():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def pagina(application, tmp_path, corpus):
    from gui_qt.i18n import T
    from gui_qt.pages.base import AppState
    from gui_qt.pages.search_page import SearchPage

    T.set_language("it")
    state = AppState(workspace=tmp_path)
    state.tokens = corpus
    page = SearchPage(state)
    page.refresh()
    yield page
    T.set_language("it")
    page.deleteLater()


def _cerca(page, campo: str, testo: str) -> None:
    """The search that the page performs, without the thread that performs it."""
    from greek_corpus_pipeline.search import WordQuery, find_occurrences

    edit = page._form if campo == "forma" else page._lemma
    edit.setText(testo)
    query = WordQuery(text=testo, field=campo,
                      mode=(page._form_mode if campo == "forma"
                            else page._lemma_mode).currentData())
    page._last_query = query
    page._query_label.setText(query.describe())
    page._on_results(find_occurrences(page.state.tokens, query))


def test_la_pagina_mostra_elenco_e_dettaglio(pagina):
    _cerca(pagina, "forma", "anthropos")
    mostrate = pagina._table.dataframe()
    assert list(mostrate.columns) == ["n.", "forma", "contesto"]
    assert mostrate["forma"].tolist() == ["ἄνθρωπος"]
    # The first row is already chosen: the panel reads at once.
    dettaglio = pagina._detail.items()
    assert len(dettaglio) == 5
    assert dettaglio["lemma della testa"] == "λέγω"
    assert dettaglio["autore"] == "Aristotele"


def test_la_pagina_tiene_separate_le_due_ricerche(pagina):
    """With both written, each button reads only its own row."""
    pagina._form.setText("ἄνθρωπος")
    pagina._lemma.setText("λόγος")
    # The search by lemma must not see the form written above…
    _cerca(pagina, "lemma", "λόγος")
    assert pagina._table.dataframe()["forma"].tolist() == ["λόγῳ", "λόγος"]
    # …nor the search by form the lemma written below.
    _cerca(pagina, "forma", "ἄνθρωπος")
    assert pagina._table.dataframe()["forma"].tolist() == ["ἄνθρωπος"]


def test_il_dettaglio_segue_la_riga_anche_dopo_un_ordinamento(pagina):
    """The table is sorted by clicking: the occurrence number travels with the row.

    Without this the panel would show the analysis of the row that *was* in that
    position before the sorting — the most insidious error that a sortable table can
    make, because what one reads is plausible.
    """
    from PyQt6.QtCore import Qt

    _cerca(pagina, "lemma", "ἄνθρωπος")
    modello = pagina._table._model
    modello.sort(1, Qt.SortOrder.DescendingOrder)     # by form, reversed
    for riga in range(modello.rowCount()):
        pagina._table._view.selectRow(riga)
        mostrata = modello.rowAt(riga)
        dettaglio = pagina._detail.items()
        atteso = {"ἄνθρωπος": "λέγω", "ἀνθρώπου": "φύσις",
                  "ἄνθρωποι": "διαφέρω"}[mostrata["forma"]]
        assert dettaglio["lemma della testa"] == atteso


def test_la_pagina_dice_che_cosa_ha_cercato(pagina):
    _cerca(pagina, "forma", "anthropos")
    assert "forma" in pagina._query_label.text()
    assert "anthropos" in pagina._query_label.text()
    assert "occorrenze" in pagina._status.text()


def test_senza_testo_la_pagina_lo_dice(pagina):
    from gui_qt.i18n import tr

    pagina._form.clear()
    pagina._search("forma")
    assert pagina._status.text() == tr("search.no_criteria")


def test_niente_di_scelto_niente_dettaglio(pagina):
    _cerca(pagina, "forma", "ξξξξ")
    assert pagina._detail.items() == {}
    assert pagina._table.dataframe().empty


def test_la_pagina_cambia_lingua(pagina):
    from gui_qt.i18n import T

    _cerca(pagina, "forma", "anthropos")
    assert "sostantivo" in pagina._detail.items()["morfologia"]
    assert "occorrenze" in pagina._status.text()
    T.set_language("en")
    pagina.retranslate()
    assert "noun" in pagina._detail.items()["morfologia"]
    # also what was already written: the search done and the count
    assert "hits found" in pagina._status.text()
    assert "form" in pagina._query_label.text()
    assert "exact" in pagina._query_label.text()
    assert pagina._form_button.text() == "Search this form"
    assert [pagina._form_mode.itemText(i)
            for i in range(pagina._form_mode.count())] == \
        ["exact", "starts with", "contains"]
    # and the value searched on stays Italian, because it is the datum
    assert pagina._form_mode.currentData() == "esatto"


def test_le_voci_sono_scritte_in_due_lingue():
    from gui_qt.i18n_cerca import STRINGS

    for chiave, coppia in STRINGS.items():
        assert chiave.startswith(("search.", "column.")), chiave
        assert isinstance(coppia, tuple) and len(coppia) == 2, chiave
        assert coppia[0].strip() and coppia[1].strip(), chiave
