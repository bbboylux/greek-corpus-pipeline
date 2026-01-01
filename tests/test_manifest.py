# -*- coding: utf-8 -*-
"""The provenance of a result, and the check that it is the real one."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from greek_corpus_pipeline import manifest
from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
from greek_corpus_pipeline.units import build_units


@pytest.fixture
def unita(tokens):
    return build_units(tokens, active=tokens)


def test_il_manifest_dichiara_le_cinque_unita_e_sono_quelle_vere(tokens, unita):
    documento = manifest.build(tokens=tokens, unita=unita)
    dichiarate = documento["unita"]
    assert dichiarate["imported_records"] == unita.n_imported_records
    assert dichiarate["active_records"] == unita.n_active_records
    assert dichiarate["words"] == unita.n_words
    assert dichiarate["analyzable_links"] == unita.n_analyzable_links
    assert dichiarate["analyzable_sentences"] == unita.n_analyzable_sentences


def test_ogni_percentuale_ha_il_suo_denominatore_nelle_due_lingue():
    for nome, coppia in manifest.DENOMINATORS.items():
        italiano, inglese = coppia
        assert italiano.strip(), nome
        assert inglese.strip(), nome
        assert italiano != inglese, f"“{nome}” has the same sentence in both languages"


def test_il_manifest_segue_la_lingua():
    it = manifest.build(lingua="it")["denominatori"]["tasso_segnalazioni"]
    en = manifest.build(lingua="en")["denominatori"]["tasso_segnalazioni"]
    assert "record attivi" in it
    assert "active records" in en


def test_ogni_lista_scientifica_arriva_con_la_sua_impronta():
    liste = manifest.build()["liste"]
    assert liste, "no list declared"
    for riga in liste:
        assert riga["checksum"] and len(riga["checksum"]) == 16
        assert riga["versione"]
        assert riga["voci"] > 0


def test_il_catalogo_dichiarato_e_quello_caricato():
    catalogo = manifest.build()["catalogo"]
    assert catalogo["controlli"] == len(RULE_CATALOG)
    assert sum(catalogo["per_classe"].values()) == len(RULE_CATALOG)
    assert sum(catalogo["per_trattamento"].values()) == len(RULE_CATALOG)


def test_un_confronto_che_non_c_e_viene_dichiarato_assente():
    modelli = manifest.build()["modelli"]
    assert set(modelli) == {"stanza", "udpipe"}
    for etichetta, stato in modelli.items():
        assert stato["stato"] != "eseguito sul corpus corrente"


def test_un_confronto_valido_entra_con_la_sua_provenienza():
    valutazione = {"provenienza": {"modello": "stanza", "modello_versione": "1.5.0",
                                   "impronta_corpus": "abc"},
                   "lemma": {"quota": 91.2, "denominatore": "parole"},
                   "postag": {"quota": 88.0, "denominatore": "parole"}}
    documento = manifest.build(modelli={"stanza": {"stato": "valido",
                                                   "valutazione": valutazione}})
    voce = documento["modelli"]["stanza"]
    assert voce["stato"] == "eseguito sul corpus corrente"
    assert voce["provenienza"]["impronta_corpus"] == "abc"
    assert voce["lemma"]["denominatore"] == "parole"


def test_l_impronta_del_corpus_cambia_col_corpus(tokens):
    prima = manifest.corpus_fingerprint(tokens)
    assert prima == manifest.corpus_fingerprint(tokens.copy())
    diverso = tokens.copy()
    diverso.loc[0, "form"] = "ἄλλο"
    assert manifest.corpus_fingerprint(diverso) != prima


def test_il_manifest_e_scrivibile_come_json(tokens, unita):
    documento = manifest.build(corpus_name="prova", run_id="r1", tokens=tokens,
                               unita=unita, filtri={"exclude_punctuation": False})
    testo = json.dumps(documento, ensure_ascii=False)
    assert "unita" in json.loads(testo)


def test_il_tasso_dichiarato_e_quello_calcolato(tokens, unita):
    findings = pd.DataFrame({"rule_id": ["a", "a", "b"]})
    documento = manifest.build(tokens=tokens, unita=unita, findings=findings)
    atteso = round(10000 * 3 / unita.n_active_records, 2)
    assert documento["risultati"]["per_diecimila_record_attivi"] == atteso
    assert documento["risultati"]["controlli_che_scattano"] == 2
