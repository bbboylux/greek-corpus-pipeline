# -*- coding: utf-8 -*-
"""The trigram plane, aligned with the other four.

Two things are required of ``ngram_variation`` as of every other plane: the
empty label must not enter as if it were an analysis, and the sentence must be
identified by a key that includes ``document_id``.  These tests fix both.
"""
from __future__ import annotations

import pandas as pd
import pytest

from greek_corpus_pipeline.variation import (
    dependency_variation,
    ngram_variation,
    pos_variation,
)


COLONNE = ("source_file", "document_id", "sentence_index", "sentence_id",
           "token_index", "token_id", "head", "form", "lemma", "postag",
           "relation", "artificial")


def frase(file: str, documento: str, indice: int, parole) -> list[dict]:
    """A sentence: ``parole`` (“words”) is a sequence of (form, label, relation, head)."""
    righe = []
    for posizione, voce in enumerate(parole, start=1):
        forma, etichetta = voce[0], voce[1]
        relazione = voce[2] if len(voce) > 2 else "ATR"
        testa = voce[3] if len(voce) > 3 else 0
        righe.append({
            "source_file": file, "document_id": documento,
            "sentence_index": indice, "sentence_id": str(indice),
            "token_index": posizione, "token_id": posizione, "head": testa,
            "form": forma, "lemma": forma, "postag": etichetta,
            "relation": relazione, "artificial": "",
        })
    return righe


def tabella(*gruppi) -> pd.DataFrame:
    righe = [riga for gruppo in gruppi for riga in gruppo]
    return pd.DataFrame(righe, columns=list(COLONNE))


# ---------------------------------------------------------------------------
# The empty label
# ---------------------------------------------------------------------------

def test_un_postag_vuoto_non_apre_un_nucleo():
    """Missing annotation and competing annotation are not the same thing.

    The real case: in Gorman ``ἐν σ᾽ Κωμῳδουμένων`` and in Pedalion
    ``εὖ ἴσθι ὅτι`` would show up as variation nuclei because the central token
    has no label in one occurrence and is annotated in the other.  The absence of
    the label is already flagged on its own by ``missing-postag``.
    """
    corpus = tabella(
        frase("a.xml", "a", 1, [("μὲν", "d--------"), ("οὖν", "d--------"), ("δέ", "d--------")]),
        frase("a.xml", "a", 2, [("μὲν", "d--------"), ("οὖν", ""), ("δέ", "d--------")]),
    )
    assert ngram_variation(corpus).empty


def test_due_etichette_vere_nello_stesso_contesto_restano_un_nucleo():
    """The previous check must not have switched the plane off."""
    corpus = tabella(
        frase("a.xml", "a", 1, [("μὲν", "d--------"), ("οὖν", "d--------"), ("δέ", "d--------")]),
        frase("a.xml", "a", 2, [("μὲν", "d--------"), ("οὖν", "c--------"), ("δέ", "d--------")]),
    )
    nuclei = ngram_variation(corpus)
    assert len(nuclei) == 1
    assert nuclei.loc[0, "chiave"] == "μὲν οὖν δέ"
    assert nuclei.loc[0, "n_etichette"] == 2


def test_l_etichetta_vuota_e_esclusa_anche_dagli_altri_piani():
    """The rule is common, and this test states it for the morphological plane."""
    corpus = tabella(
        frase("a.xml", "a", 1, [("οὖν", "d--------")]),
        frase("a.xml", "a", 2, [("οὖν", "")]),
    )
    assert pos_variation(corpus).empty


# ---------------------------------------------------------------------------
# The sentence key
# ---------------------------------------------------------------------------

@pytest.fixture
def due_documenti_un_file() -> pd.DataFrame:
    """A file that contains two documents, with the same sentence numbers.

    In the six measured corpora it never happens, and that is the reason why the
    defect has never changed a result.  Here it happens on purpose.
    """
    return tabella(
        frase("misto.xml", "alfa", 1, [("ἄλφα", "n-s---mn-"), ("βῆτα", "n-s---mn-"), ("γάμμα", "n-s---mn-")]),
        frase("misto.xml", "alfa", 2, [("ἄλφα", "n-s---mn-"), ("βῆτα", "v3spia---"), ("γάμμα", "n-s---mn-")]),
        frase("misto.xml", "beta", 1, [("δέλτα", "n-s---mn-"), ("εἶ", "n-s---mn-"), ("ζῆτα", "n-s---mn-")]),
        frase("misto.xml", "beta", 2, [("δέλτα", "n-s---mn-"), ("εἶ", "a-s---mn-"), ("ζῆτα", "n-s---mn-")]),
    )


def test_nessun_trigramma_attraversa_il_confine_fra_documenti(due_documenti_un_file):
    nuclei = ngram_variation(due_documenti_un_file)
    chiavi = set(nuclei["chiave"])
    assert chiavi == {"ἄλφα βῆτα γάμμα", "δέλτα εἶ ζῆτα"}

    di_alfa = {"ἄλφα", "βῆτα", "γάμμα"}
    di_beta = {"δέλτα", "εἶ", "ζῆτα"}
    for chiave in chiavi:
        parole = set(chiave.split())
        assert not (parole & di_alfa and parole & di_beta), \
            f"the context “{chiave}” puts two documents together"


def test_nessun_arco_attraversa_il_confine_fra_documenti():
    """The same defect could occur in the dependency plane too.

    Without ``document_id`` the two documents become a single sentence, and since each
    numbers its own tokens from 1 the head of a token is resolved on the token of the
    other document: ``ἄλφα`` would end up attached to ``ζῆτα``, which is in another
    text, and the pair would become a variation nucleus.
    """
    corpus = tabella(
        frase("misto.xml", "alfa", 1,
              [("ἄλφα", "n-s---mn-", "SBJ", 2), ("βῆτα", "v3spia---", "PRED", 0)]),
        frase("misto.xml", "alfa", 2,
              [("ἄλφα", "n-s---mn-", "OBJ", 2), ("βῆτα", "v3spia---", "PRED", 0)]),
        frase("misto.xml", "beta", 1,
              [("δέλτα", "n-s---mn-", "OBJ", 2), ("ζῆτα", "v3spia---", "PRED", 0)]),
        frase("misto.xml", "beta", 2,
              [("δέλτα", "n-s---mn-", "OBJ", 2), ("ζῆτα", "v3spia---", "PRED", 0)]),
    )
    nuclei = dependency_variation(corpus)
    di_alfa = {"ἄλφα", "βῆτα"}
    di_beta = {"δέλτα", "ζῆτα"}
    for chiave in nuclei["chiave"]:
        parole = set(chiave.replace("\u241f", " ").replace(" / ", " ").replace("\u2026", " ").split())
        assert not (parole & di_alfa and parole & di_beta), \
            f"the arc “{chiave}” puts two documents together"
    # and the real arc, the one inside alfa, is there
    assert any({"ἄλφα", "βῆτα"} <= set(
        c.replace("\u241f", " ").replace(" / ", " ").replace("\u2026", " ").split())
        for c in nuclei["chiave"])


def test_la_frase_resta_quella_giusta_dentro_un_documento_solo(due_documenti_un_file):
    """The normal case does not change: one file, one document, the usual nuclei."""
    solo_alfa = due_documenti_un_file[
        due_documenti_un_file["document_id"] == "alfa"].reset_index(drop=True)
    nuclei = ngram_variation(solo_alfa)
    assert set(nuclei["chiave"]) == {"ἄλφα βῆτα γάμμα"}
