# -*- coding: utf-8 -*-
"""One word, written in every way, and the same answer everywhere.

Whoever types ``ανθρωπος`` in the box of “Search the corpus” finds ἄνθρωπος,
and whoever types the same thing in “Statistics → Lemma profile” must find it
too: it would be wrong for one page to say that the lemma does not occur in
the corpus when the other page has just shown it.  Two pages must not apply
two criteria.

The principle, which these tests hold fixed: **finding** and **counting** are
two different operations and need two different keys, but the key used to
find must be **one only** for the whole program.  One finds with
``search.key_test``, which is the key of the “Search” page; one counts with
``stats.statistical_lemma_key``, which is exact and does not change.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from greek_corpus_pipeline import search, stats  # noqa: E402

#: A minimal corpus containing the things that matter: the Perseus numbering on the
#: lemma, a mangled spelling next to the good one, a word with a breathing and one with
#: an iota subscript.
CORPUS = pd.DataFrame({
    "source_file": ["prova.xml"] * 8,
    "document_id": ["d1"] * 8,
    "sentence_id": [1, 1, 1, 1, 2, 2, 2, 2],
    "sentence_index": [1, 1, 1, 1, 2, 2, 2, 2],
    "token_id": [1, 2, 3, 4, 1, 2, 3, 4],
    "form":   ["λέγει", "ἄνθρωπος", "ὁδόν", "τῷ", "λέγω", "ἄνθρωπον", "ὁδός", "λόγῳ"],
    "lemma":  ["λέγω1", "ἄνθρωπος", "ὁδός", "ὁ", "λέγω3", "ἄνθρωπος", "ὁδός", "λόγος"],
    "postag": ["v3spia---", "n-s---mn-", "n-s---fa-", "l-s---md-",
               "v1spia---", "n-s---ma-", "n-s---fn-", "n-s---md-"],
    "head":     [0, 1, 1, 2, 0, 1, 1, 1],
    "relation": ["PRED", "SBJ", "OBJ", "ATR", "PRED", "OBJ", "SBJ", "ATR"],
})


def _occorrenze(digitato: str) -> int:
    return int(stats.lemma_profile(CORPUS, digitato).get("occorrenze", 0))


def _risolto(digitato: str) -> str:
    return str(stats.lemma_profile(CORPUS, digitato).get("chiave", ""))


# ── λέγω, in every way in which it is written ───────────────────────────────

@pytest.mark.parametrize("digitato", [
    "λέγω",                                        # as written
    "λεγω",                                        # without accent
    "Λέγω",                                        # with a capital letter
    "λέγω1",                                       # with Perseus numbering
    unicodedata.normalize("NFD", "λέγω"),          # decomposed
    unicodedata.normalize("NFC", "λέγω"),          # composed
    "lego",                                        # in Latin letters
    "legō",                                        # with vowel length marked
    "LEGO",                                        # Latin capitals
])
def test_ogni_modo_di_scrivere_lego_trova_lo_stesso_lemma(digitato):
    assert _risolto(digitato) == "λέγω"
    assert _occorrenze(digitato) == 2


@pytest.mark.parametrize("digitato", [
    "ἄνθρωπος", "ανθρωπος", "ἀνθρωπος", "ΑΝΘΡΩΠΟΣ", "anthropos", "anthrōpos",
    unicodedata.normalize("NFD", "ἄνθρωπος"),
])
def test_ogni_modo_di_scrivere_anthropos_trova_lo_stesso_lemma(digitato):
    """Breathing, accent, capitals, NFC/NFD and Latin alphabet, all together."""
    assert _risolto(digitato) == "ἄνθρωπος"
    assert _occorrenze(digitato) == 2


@pytest.mark.parametrize("digitato", ["ὁδός", "οδος", "ὁδὸς", "hodos", "odos"])
def test_lo_spirito_aspro_non_impedisce_di_trovare_odos(digitato):
    assert _risolto(digitato) == "ὁδός"
    assert _occorrenze(digitato) == 2


@pytest.mark.parametrize("digitato", ["λόγος", "λογος", "logos", "λόγοσ"])
def test_il_sigma_finale_non_e_una_lettera_diversa(digitato):
    assert _risolto(digitato) == "λόγος"
    assert _occorrenze(digitato) == 1


# ── the two pages must say the same thing ───────────────────────────────────

@pytest.mark.parametrize("digitato", [
    "ἄνθρωπος", "ανθρωπος", "anthropos", "ὁδός", "οδος", "hodos", "λόγος", "logos",
])
def test_se_la_ricerca_lo_trova_il_profilo_lo_profila(digitato):
    """The reported defect, in its shortest form.

    The two counts are not required to coincide — the search is generous and the
    statistics are exact, and they must stay so.  What is required is that one
    page must not say “does not occur in the corpus” of a word that the other is
    showing.
    """
    trovate = len(search.find_lemmas(CORPUS, digitato, mode="esatto"))
    assert trovate > 0, "the test corpus is of no use: the search finds nothing"
    assert _occorrenze(digitato) > 0, (
        f"“Search” finds {trovate} occurrences of {digitato}, the profile says zero")


def test_una_parola_che_non_c_e_continua_a_non_esserci():
    """The generous key must not become a key that finds everything."""
    assert _occorrenze("ἵππος") == 0
    assert _occorrenze("hippos") == 0
    assert _occorrenze("") == 0


# ── normalisation serves to find, not to count ──────────────────────────────

def test_la_chiave_statistica_non_e_cambiata():
    """The key used to count stays exact: accents, breathings and capitals count."""
    chiave = stats.statistical_lemma_key
    assert chiave("λέγω3") == "λέγω"
    assert chiave(unicodedata.normalize("NFD", "λέγω1")) == "λέγω"
    assert chiave("λεγω") != chiave("λέγω")
    assert chiave("Ἄνθρωπος") != chiave("ἄνθρωπος")


def test_il_profilo_conta_sempre_sulla_grafia_esatta():
    """Typing without accents does not add two spellings into a single count.

    The corpus has ``ἄνθρωπος`` twice.  Whoever types ``ανθρωπος`` must see two,
    not “two plus the neighbouring spellings”: the search key chooses **which**
    lemma to profile and stops there.
    """
    esatto = stats.lemma_profile(CORPUS, "ἄνθρωπος")
    generoso = stats.lemma_profile(CORPUS, "ανθρωπος")
    assert esatto["occorrenze"] == generoso["occorrenze"]
    assert esatto["chiave"] == generoso["chiave"]
    pd.testing.assert_frame_equal(esatto["forme"], generoso["forme"])


def test_il_corpus_non_viene_toccato():
    """The raw forms and lemmas stay what they were, byte for byte."""
    prima = CORPUS.copy(deep=True)
    stats.lemma_profile(CORPUS, "ανθρωπος")
    stats.word_sketch(CORPUS, "λεγω")
    search.find_lemmas(CORPUS, "anthropos")
    pd.testing.assert_frame_equal(CORPUS, prima)


def test_il_profilo_dice_su_quale_grafia_ha_risposto():
    """Whoever types without accents must see that the answer concerns ἄνθρωπος."""
    assert stats.lemma_profile(CORPUS, "ανθρωπος")["chiave"] == "ἄνθρωπος"
    assert stats.word_sketch(CORPUS, "ανθρωπος")["chiave"] == "ἄνθρωπος"


# ── the syntactic profile uses the same key as the descriptive profile ──────

@pytest.mark.parametrize("digitato", ["λέγω", "λεγω", "lego", "Λέγω"])
def test_le_due_meta_della_scheda_rispondono_sullo_stesso_lemma(digitato):
    """``lemma_profile`` and ``word_sketch`` are a single card and must agree."""
    profilo = stats.lemma_profile(CORPUS, digitato)
    sketch = stats.word_sketch(CORPUS, digitato)
    assert profilo["chiave"] == sketch["chiave"] == "λέγω"


# ── the mangled spelling does not take the place of the good one ────────────

def test_fra_una_grafia_e_la_sua_storpiatura_si_profila_quella_del_corpus():
    """In Gorman ``λέγω`` occurs 1,957 times and ``λἐγω`` once: they are not two
    words.

    Whoever types without accents cannot tell them apart, and answering that the
    lemma does not occur in the corpus would be false.  The more frequent
    spelling is the one taken, and the card shows which.
    """
    # Two good occurrences against one mangled, as in the real corpus.
    riga = CORPUS.iloc[[0]].copy()
    riga["lemma"] = "λἐγω"
    riga["sentence_id"] = riga["sentence_index"] = 3
    storpiato = pd.concat([CORPUS, riga], ignore_index=True)

    profilo = stats.lemma_profile(storpiato, "λεγω")
    assert profilo["chiave"] == "λέγω"
    assert profilo["occorrenze"] == 2
    # and the mangled spelling stays reachable by typing it exactly
    assert stats.lemma_profile(storpiato, "λἐγω")["occorrenze"] == 1


def test_a_parita_di_occorrenze_non_si_indovina():
    """Two equally frequent spellings are two questions, and no choice is made for the
    user."""
    pari = CORPUS.copy()
    pari.loc[pari.index[1], "lemma"] = "Ἄνθρωπος"            # one and one
    profilo = stats.lemma_profile(pari, "ανθρωπος")
    assert profilo["occorrenze"] == 0


# ── a single implementation of the criterion ────────────────────────────────

def test_il_criterio_di_ricerca_sta_in_un_posto_solo():
    """``key_mask`` and ``resolve_lemma_key`` must go through the same function."""
    import inspect

    assert "key_test" in inspect.getsource(search.key_mask)
    assert "key_test" in inspect.getsource(stats.resolve_lemma_key)


def test_le_pagine_che_accettano_una_parola_digitata_sono_quelle_che_crediamo():
    """If a third appears, this test says so before the two diverge.

    There are two boxes in which one types a form or a lemma in order to **find**
    it: those of “Search the corpus” and the profile box in the statistics.  The
    lemma box in the corrections page does not search: it writes, and must not
    normalise anything.
    """
    ricerca = (ROOT / "gui_qt" / "pages" / "search_page.py").read_text(encoding="utf-8")
    statistiche = (ROOT / "gui_qt" / "pages" / "stats_page.py").read_text(encoding="utf-8")
    assert "find_occurrences" in ricerca
    assert "lemma_profile" in statistiche and "word_sketch" in statistiche
    revisione = (ROOT / "gui_qt" / "pages" / "review_page.py").read_text(encoding="utf-8")
    assert "search_key" not in revisione and "resolve_lemma_key" not in revisione


# ── Perseus numbering does not hide the lemma in the search either ───────────
#
# `λέγω1`, `λέγω2`, `λέγω3` and `λέγω` are the same lemma: the digit is
# Perseus metadata inside the string.  The profile knows this; “Search the
# corpus → lemma” must know it too, because otherwise a search for `λέγω` in
# Gorman would find 52 occurrences instead of 1,958.  This holds for matching
# and for nothing else: the raw lemma stays what it is, and the statistical key
# keeps distinguishing the spellings.

@pytest.mark.parametrize("digitato", [
    "λέγω", "λεγω", "λέγω1", "λέγω3", "Λέγω", "ΛΕΓΩ", "lego", "legō",
    unicodedata.normalize("NFD", "λέγω"),
    unicodedata.normalize("NFD", "λέγω1"),
])
def test_cerca_lemma_trova_la_stessa_famiglia_comunque_si_scriva(digitato):
    trovate = search.find_lemmas(CORPUS, digitato, mode="esatto")
    grafie = set(trovate["lemma"]) if "lemma" in trovate.columns else set()
    assert len(trovate) == 2, f"“{digitato}” finds {len(trovate)} instead of 2"
    assert grafie == {"λέγω1", "λέγω3"}, grafie


def test_cerca_lemma_e_profilo_concordano_su_lego():
    """The point of the correction, in its shortest form."""
    for digitato in ("λέγω", "λεγω", "lego", "λέγω1", "Λέγω"):
        trovate = len(search.find_lemmas(CORPUS, digitato, mode="esatto"))
        profilate = _occorrenze(digitato)
        assert trovate == profilate == 2, (
            f"«{digitato}»: Cerca {trovate}, Profilo {profilate}")


def test_la_query_combinata_usa_la_stessa_chiave_del_lemma():
    """The “Search” page has two routes — a single word and the compound query."""
    from greek_corpus_pipeline.search import Query, run_query

    esito = run_query(CORPUS, Query(lemma="λεγω", lemma_mode="esatto"))
    assert len(esito) == 2
    assert set(esito["lemma"]) == {"λέγω1", "λέγω3"}


def test_anche_il_lemma_della_testa_usa_la_stessa_chiave():
    """“every object of λέγω” cannot depend on how λέγω is written."""
    from greek_corpus_pipeline.search import Query, run_query

    con_cifra = run_query(CORPUS, Query(head_lemma="λέγω1"))
    senza = run_query(CORPUS, Query(head_lemma="λεγω"))
    assert len(senza) == len(con_cifra) > 0


# ── and the search by form is not touched ───────────────────────────────────

def test_la_cifra_finale_si_toglie_al_lemma_e_mai_alla_forma():
    """A digit at the end of a form is not metadata: it is part of the form.

    In Pedalion 34 forms end in a digit and are lacuna markers —
    ``G2``, ``G3``, ``G15``.  Stripping the number from them would make them
    collapse onto one another, and ``G2`` would find ``G15``.
    """
    from greek_corpus_pipeline.search import key_mask

    lacune = pd.DataFrame({
        "document_id": ["d"] * 3, "sentence_id": [1] * 3, "sentence_index": [1] * 3,
        "token_id": [1, 2, 3], "form": ["G2", "G3", "G15"],
        "lemma": ["G2", "G3", "G15"], "postag": ["u--------"] * 3,
        "head": [0, 1, 1], "relation": ["AuxG"] * 3,
    })
    forme = lacune["form"].astype("string")
    assert int(key_mask(forme, "G2", "esatto").sum()) == 1
    assert int(key_mask(forme, "G15", "esatto").sum()) == 1
    # on the lemma column, by contrast, the digit is metadata and is dropped
    lemmi = lacune["lemma"].astype("string")
    assert int(key_mask(lemmi, "G", "esatto", campo="lemma").sum()) == 3


def test_le_chiavi_della_forma_e_del_lemma_sono_due_e_dichiarate():
    from greek_corpus_pipeline.search import lemma_key, search_key

    assert search_key("λέγω1") == "legō1"
    assert lemma_key("λέγω1") == lemma_key("λέγω") == "legō"
    assert search_key("λέγω") == "legō"


def test_il_lemma_grezzo_non_viene_mai_riscritto():
    """The digit disappears from the key, not from the data: the results show it."""
    trovate = search.find_lemmas(CORPUS, "λεγω", mode="esatto")
    assert set(trovate["lemma"]) == {"λέγω1", "λέγω3"}
    assert "λέγω" not in set(trovate["lemma"])
    prima = CORPUS.copy(deep=True)
    search.find_lemmas(CORPUS, "λεγω")
    pd.testing.assert_frame_equal(CORPUS, prima)
