# -*- coding: utf-8 -*-
"""The comparison with a model: what it receives, on what it is measured.

The model is not installed in this environment and does not need to be: what these tests
verify are the definitions — input, universe, denominators, alignment, normalisation —
and those are checked with fake predictions, written by hand, whose answer is already
known.
"""
from __future__ import annotations

import unicodedata

import pandas as pd
import pytest

from greek_corpus_pipeline.model_eval import (
    EVALUATION_DEFINITION,
    align_predictions,
    corpus_fingerprint,
    evaluate_predictions,
    evaluation_universe,
    lemma_comparison_key,
    model_input_records,
    postag_comparability,
    prepare_model_input,
    provenance,
    provenance_matches,
)
from greek_corpus_pipeline.units import build_units


COLONNE = ("source_file", "document_id", "sentence_index", "sentence_id",
           "token_index", "token_id", "head", "form", "lemma", "postag",
           "relation", "artificial")


def frase(indice, parole):
    righe = []
    for posizione, voce in enumerate(parole, start=1):
        forma, lemma, etichetta, relazione, testa = voce[:5]
        artificiale = voce[5] if len(voce) > 5 else ""
        righe.append({
            "source_file": "prova.xml", "document_id": "prova",
            "sentence_index": indice, "sentence_id": str(indice),
            "token_index": posizione, "token_id": posizione, "head": testa,
            "form": forma, "lemma": lemma, "postag": etichetta,
            "relation": relazione, "artificial": artificiale,
        })
    return righe


#: 1  ὁ θεός λέγει .            with λέγω3 as lemma, and a full stop
#: 2  θεός λέγει                with θεός written in NFD, and an elliptical node
CORPUS = pd.DataFrame(
    frase(1, [("ὁ", "ὁ", "l-s---mn-", "ATR", 2),
              ("θεός", "θεός", "n-s---mn-", "SBJ", 3),
              ("λέγει", "λέγω3", "v3spia---", "PRED", 0),
              (".", ".", "u--------", "AuxK", 0)])
    + frase(2, [("θεός", unicodedata.normalize("NFD", "θεός"), "n-s---mn-", "SBJ", 2),
                ("λέγει", "λέγω", "v3spia---", "PRED", 0),
                ("", "", "", "ExD", 0, "elliptic")]),
    columns=list(COLONNE),
)


@pytest.fixture
def unita():
    return build_units(CORPUS, active=CORPUS)


@pytest.fixture
def superficie():
    return prepare_model_input(CORPUS)


def previsioni(superficie, lemmi, etichette):
    """The fake predictions of a model, aligned by position."""
    fuori = superficie[["_sentenza", "_posizione"]].copy()
    fuori["lemma"] = lemmi
    fuori["postag"] = etichette
    return fuori


# ---------------------------------------------------------------------------
# What the model receives
# ---------------------------------------------------------------------------

def test_al_modello_vanno_le_parole_e_la_punteggiatura_vera(superficie):
    """Punctuation is linguistic context and the model reads it.

    The elliptical node, instead, corresponds to nothing in the text, and asking a
    tagger to analyse it makes no sense.
    """
    assert list(superficie["form"]) == ["ὁ", "θεός", "λέγει", ".", "θεός", "λέγει"]
    assert "." in set(superficie["form"])


def test_il_nodo_tecnico_non_arriva_al_modello():
    superficie = model_input_records(CORPUS)
    assert (superficie["artificial"].astype(str) != "elliptic").all()
    assert len(superficie) == 6


def test_l_universo_della_valutazione_sono_le_parole(unita, superficie):
    """The input is not the universe: the full stop enters the first and not the second."""
    universo = evaluation_universe(unita.words, superficie)
    assert len(universo) == 5
    assert "." not in set(universo["form"])


# ---------------------------------------------------------------------------
# The alignment
# ---------------------------------------------------------------------------

def test_l_allineamento_passa_dalla_posizione_e_non_dalla_forma(unita, superficie):
    """The defect that this test exists to prevent.

    The model returns the form as it wrote it, and a difference of encoding or a cleaned
    space would be enough to make the token vanish from the comparison without anyone
    noticing.  Here the predicted forms are all different from those of the corpus, and
    the alignment holds all the same.
    """
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["ὁ", "θεός", "λέγω", ".", "θεός", "λέγω"],
                   [""] * 6)
    p["form"] = "una forma che non esiste"
    allineato = align_predictions(universo, p)
    assert len(allineato) == len(universo)
    assert allineato["lemma_modello"].notna().all()


def test_previsioni_senza_le_colonne_di_allineamento_sono_un_errore(unita, superficie):
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["x"] * 6, [""] * 6).drop(columns=["_posizione"])
    with pytest.raises(ValueError, match="alignment"):
        align_predictions(universo, p)


# ---------------------------------------------------------------------------
# The comparison keys
# ---------------------------------------------------------------------------

def test_la_chiave_del_lemma_toglie_codifica_e_numerazione():
    assert lemma_comparison_key("λέγω3") == lemma_comparison_key("λέγω")
    assert lemma_comparison_key(unicodedata.normalize("NFD", "θεός")) == \
        lemma_comparison_key("θεός")


def test_la_mappa_delle_varianti_canoniche_non_si_applica_al_confronto():
    """If the model chooses νόος where the corpus chooses νοῦς it is a real disagreement."""
    from greek_corpus_pipeline.normalise import LEMMA_VARIANTS
    for variante, canonica in LEMMA_VARIANTS.items():
        assert lemma_comparison_key(variante) != lemma_comparison_key(canonica)


def test_il_modello_che_scrive_il_lemma_senza_numero_e_in_nfc_va_daccordo(unita, superficie):
    """The GLAUx case: 252,047 lemmas out of 300,292 in NFD.

    With raw equality the agreement would be close to zero for a typographic reason, and
    it would be a number worse than no number.
    """
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["ὁ", "θεός", "λέγω", ".", "θεός", "λέγω"],
                   ["l-s---mn-", "n-s---mn-", "v3spia---", "u--------",
                    "n-s---mn-", "v3spia---"])
    esito = evaluate_predictions(universo, p, modello="finto")
    assert esito.lemma.eleggibili == 5
    assert esito.lemma.accordi == 5
    assert esito.lemma.quota == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Denominators and coverage
# ---------------------------------------------------------------------------

def test_una_previsione_mancante_e_un_disaccordo_non_una_sparizione(unita, superficie):
    """A model must not improve its own rate by dropping the hard cases."""
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["ὁ", "θεός", "", ".", "θεός", "λέγω"],
                   ["l-s---mn-", "n-s---mn-", "", "u--------",
                    "n-s---mn-", "v3spia---"])
    esito = evaluate_predictions(universo, p, modello="finto")
    assert esito.lemma.eleggibili == 5          # the denominator does not move
    assert esito.lemma.con_previsione == 4
    assert esito.lemma.accordi == 4
    assert esito.lemma.disaccordi == 1
    assert esito.lemma.copertura == pytest.approx(80.0)
    assert esito.lemma.quota == pytest.approx(80.0)


def test_ogni_metrica_dichiara_il_proprio_denominatore(unita, superficie):
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["x"] * 6, ["l-s---mn-"] * 6)
    esito = evaluate_predictions(universo, p, modello="finto")
    assert esito.lemma.denominatore == "words with a reference lemma present"
    assert "9 characters" in esito.postag.denominatore
    assert esito.universo == "words"


# ---------------------------------------------------------------------------
# The guard on the label
# ---------------------------------------------------------------------------

def test_un_tagset_diverso_ferma_la_metrica_invece_di_dare_zero(unita, superficie):
    """Comparing an AGDT positional tag with a UPOS would give zero by construction."""
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["x"] * 6,
                   ["DET", "NOUN", "VERB", "PUNCT", "NOUN", "VERB"])
    esito = evaluate_predictions(universo, p, modello="finto")
    assert esito.comparabilita_postag["verdetto"] == "incompatibile"
    assert esito.postag.sospesa
    assert esito.postag.accordi == 0
    assert esito.postag.eleggibili == 5     # the denominator is there all the same


def test_un_tagset_agdt_autorizza_la_metrica(unita, superficie):
    universo = evaluation_universe(unita.words, superficie)
    p = previsioni(superficie, ["x"] * 6,
                   ["l-s---mn-", "n-s---mn-", "v3spia---", "u--------",
                    "n-s---mn-", "v3siia---"])
    esito = evaluate_predictions(universo, p, modello="finto")
    assert esito.comparabilita_postag["verdetto"] == "compatibile"
    assert not esito.postag.sospesa
    assert esito.postag.eleggibili == 5
    assert esito.postag.accordi == 4        # the last label is different


def test_un_tagset_misto_non_passa_di_nascosto():
    misto = postag_comparability(pd.Series(["n-s---mn-", "NOUN", "v3spia---"]))
    assert misto["verdetto"] == "misto"
    assert misto["motivo"]


# ---------------------------------------------------------------------------
# Provenance and reuse
# ---------------------------------------------------------------------------

def _provenienza(superficie, **cambi):
    base = dict(gcp_version="3.1.1", filtri={"exclude_punctuation": False},
                modello="stanza", modello_versione="1.5.0",
                risorse_modello="grc/abc123")
    base.update(cambi)
    return provenance(surface=superficie, **base)


def test_un_confronto_vale_solo_per_il_corpus_su_cui_e_stato_fatto(superficie):
    prima = _provenienza(superficie)
    assert provenance_matches(prima, _provenienza(superficie))[0]

    altro = superficie.iloc[:-1]
    valido, motivo = provenance_matches(prima, _provenienza(altro))
    assert not valido and "impronta_corpus" in motivo


def test_cambiare_modello_versione_o_filtri_invalida_il_confronto(superficie):
    prima = _provenienza(superficie)
    for campo, valore in (("modello", "udpipe"),
                          ("modello_versione", "1.6.0"),
                          ("risorse_modello", "grc/def456"),
                          ("gcp_version", "3.2.0"),
                          ("filtri", {"exclude_punctuation": True})):
        valido, motivo = provenance_matches(prima, _provenienza(superficie, **{campo: valore}))
        assert not valido, f"{campo} did not invalidate the comparison"
        assert campo in motivo


def test_cambiare_la_definizione_della_valutazione_invalida_il_confronto(superficie):
    prima = _provenienza(superficie)
    dopo = dict(prima)
    dopo["definizione_valutazione"] = "2.0"
    valido, motivo = provenance_matches(prima, dopo)
    assert not valido and "definizione_valutazione" in motivo
    assert prima["definizione_valutazione"] == EVALUATION_DEFINITION


def test_la_data_non_invalida_niente(superficie):
    prima = _provenienza(superficie)
    dopo = dict(prima)
    dopo["quando"] = "1999-01-01T00:00:00+00:00"
    assert provenance_matches(prima, dopo)[0]


def test_l_impronta_e_quella_di_quello_che_il_modello_ha_ricevuto(superficie):
    assert corpus_fingerprint(superficie) == corpus_fingerprint(superficie.copy())
    diverso = superficie.copy()
    diverso.loc[0, "form"] = "ἡ"
    assert corpus_fingerprint(diverso) != corpus_fingerprint(superficie)
