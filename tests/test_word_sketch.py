# -*- coding: utf-8 -*-
"""The syntactic profile of a word, and the units from which its numbers come.

logDice rewards rarity, so counting a lemma a few times too many is enough for
the score to change.  These tests fix by hand what each of the three terms
counts, on a corpus small enough to be computed in the head.
"""
from __future__ import annotations

import math
import unicodedata

import pandas as pd
import pytest

from greek_corpus_pipeline.stats import word_sketch
from greek_corpus_pipeline.units import build_units


COLONNE = ("source_file", "document_id", "sentence_index", "sentence_id",
           "token_index", "token_id", "head", "form", "lemma", "postag",
           "relation", "artificial")


def frase(indice: int, parole) -> list[dict]:
    """(form, lemma, tag, relation, head, artificial)."""
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


#: Three sentences, eight words, two punctuation marks and a technical node.
#:
#: 1  ὁ ἄνθρωπος λέγει .
#: 2  ἄνθρωπος λέγει λόγον ·
#: 3  λέγω βιβλίον  + an elliptical node that carries the lemma λέγω
#:
#: The two signs carry a lexical lemma on purpose: if the filter looked at the
#: lemma instead of the class of the record, the test would say so.
CORPUS = pd.DataFrame(
    frase(1, [("ὁ", "ὁ", "l-s---mn-", "ATR", 2),
              ("ἄνθρωπος", "ἄνθρωπος", "n-s---mn-", "SBJ", 3),
              ("λέγει", "λέγω", "v3spia---", "PRED", 0),
              (".", "λέγω", "u--------", "AuxK", 0)])
    + frase(2, [("ἄνθρωπος", "ἄνθρωπος", "n-s---mn-", "SBJ", 2),
                ("λέγει", "λέγω", "v3spia---", "PRED", 0),
                ("λόγον", "λόγος", "n-s---ma-", "OBJ", 2),
                ("·", "ἄνθρωπος", "u--------", "AuxK", 0)])
    + frase(3, [("λέγω", "λέγω", "v1spia---", "PRED", 0),
                ("βιβλίον", "βιβλίον", "n-s---na-", "OBJ", 1),
                ("", "λέγω", "", "ExD", 0, "elliptic")]),
    columns=list(COLONNE),
)


@pytest.fixture
def parole() -> pd.DataFrame:
    unita = build_units(CORPUS, active=CORPUS)
    return unita.words


def test_il_corpus_giocattolo_ha_le_unita_che_dico(parole):
    """Eight words out of eleven records: two signs and a technical node stay out."""
    assert len(CORPUS) == 11
    assert len(parole) == 8
    assert sorted(parole["form"]) == sorted(
        ["ὁ", "ἄνθρωπος", "λέγει", "ἄνθρωπος", "λέγει", "λόγον", "λέγω", "βιβλίον"])


def test_logdice_coincide_con_il_calcolo_a_mano(parole):
    """The three terms, counted by hand, and the canonical formula.

    ``λέγω`` occurs three times among the words, ``ἄνθρωπος`` twice, ``λόγος`` and
    ``βιβλίον`` once.  The arcs between two words that touch ``λέγω`` are four,
    towards three different lemmas: two subjects ``ἄνθρωπος`` and two different
    objects, ``λόγος`` and ``βιβλίον``, once each.
    """
    profilo = word_sketch(parole, "λέγω")
    assert profilo["f_target"] == 3

    tabella = profilo["associazioni"]
    per_parola = tabella.set_index("lemma associato")

    assert per_parola.loc["ἄνθρωπος", "co-occorrenze"] == 2
    assert per_parola.loc["ἄνθρωπος", "occorrenze del lemma associato"] == 2
    assert per_parola.loc["λόγος", "co-occorrenze"] == 1
    assert per_parola.loc["βιβλίον", "co-occorrenze"] == 1

    atteso_soggetto = 14 + math.log2(2 * 2 / (3 + 2))
    atteso_oggetto = 14 + math.log2(2 * 1 / (3 + 1))
    assert per_parola.loc["ἄνθρωπος", "logDice"] == pytest.approx(round(atteso_soggetto, 2))
    assert per_parola.loc["λόγος", "logDice"] == pytest.approx(round(atteso_oggetto, 2))
    assert per_parola.loc["βιβλίον", "logDice"] == pytest.approx(round(atteso_oggetto, 2))
    # and the two numbers are different, otherwise the test would distinguish nothing
    assert atteso_soggetto != atteso_oggetto


def test_la_punteggiatura_e_i_record_tecnici_non_contano_come_lemmi(parole):
    """The defect that this test exists to prevent.

    The full stop carries the lemma ``λέγω`` and so does the elliptical node: if
    they entered the lexical count, ``f_target`` would be 5 instead of 3 and all
    the scores would change.  The sign ``·`` carries ``ἄνθρωπος`` and would do the
    same with ``f_partner``.
    """
    profilo = word_sketch(parole, "λέγω")
    assert profilo["f_target"] == 3
    assert profilo["unita"]["words"] == 8

    # the counter-proof: on the active records, which include signs and the technical
    # node, the same three terms give different numbers
    sbagliato = word_sketch(CORPUS, "λέγω")
    assert sbagliato["f_target"] == 5
    per_parola = profilo["associazioni"].set_index("lemma associato")
    per_parola_sbagliata = sbagliato["associazioni"].set_index("lemma associato")
    assert (per_parola.loc["ἄνθρωπος", "logDice"]
            != per_parola_sbagliata.loc["ἄνθρωπος", "logDice"])


def test_gli_archi_contati_sono_quelli_fra_due_parole(parole):
    """An arc towards a punctuation sign has no lemma to associate."""
    profilo = word_sketch(parole, "λέγω")
    assert profilo["unita"]["f_joint"] == "archi fra due words che uniscono i due lemmi"
    # five words have a head that is a word of the same sentence: ὁ→ἄνθρωπος,
    # ἄνθρωπος→λέγει (twice), λόγον→λέγει, βιβλίον→λέγω
    assert profilo["unita"]["links"] == 5


def test_una_coppia_vista_una_volta_sola_si_vede(parole):
    """No minimum threshold on the co-occurrences, and the count next to the score."""
    profilo = word_sketch(parole, "λέγω")
    singole = profilo["associazioni"][profilo["associazioni"]["co-occorrenze"] == 1]
    assert set(singole["lemma associato"]) == {"λόγος", "βιβλίον"}
    assert "co-occorrenze" in profilo["associazioni"].columns


def test_la_direzione_e_dichiarata(parole):
    """Who is head and who is dependent is not deduced from the relation."""
    profilo = word_sketch(parole, "ἄνθρωπος")
    tabella = profilo["associazioni"]
    assert set(tabella["direzione"]) <= {"dipendente", "testa"}
    # ἄνθρωπος has λέγω as head and ὁ as dependent
    assert tabella.loc[tabella["lemma associato"] == "λέγω", "direzione"].iloc[0] == "testa"
    assert tabella.loc[tabella["lemma associato"] == "ὁ", "direzione"].iloc[0] == "dipendente"


# ---------------------------------------------------------------------------
# The statistical key of the lemma
# ---------------------------------------------------------------------------

#: Five sentences in which the same lemma is written in three ways, and in which
#: one word occurs twice, once with its relation and once without.
#:
#: 1  λέγει [λέγω3]  λόγον [λόγος] OBJ
#: 2  λέγω  [λέγω]   λόγον [λόγος] OBJ
#: 3  ἔλεγε [λέγω1 in NFD]  λόγον [λόγος] OBJ
#: 4  λέγει [λέγω]   βιβλίον [βιβλίον] without relation
#: 5  λέγει [λέγω]   βιβλίον [βιβλίον] OBJ
CHIAVI = pd.DataFrame(
    frase(1, [("λέγει", "λέγω3", "v3spia---", "PRED", 0),
              ("λόγον", "λόγος", "n-s---ma-", "OBJ", 1)])
    + frase(2, [("λέγω", "λέγω", "v1spia---", "PRED", 0),
                ("λόγον", "λόγος", "n-s---ma-", "OBJ", 1)])
    + frase(3, [("ἔλεγε", unicodedata.normalize("NFD", "λέγω1"), "v3siia---", "PRED", 0),
                ("λόγον", "λόγος", "n-s---ma-", "OBJ", 1)])
    + frase(4, [("λέγει", "λέγω", "v3spia---", "PRED", 0),
                ("βιβλίον", "βιβλίον", "n-s---na-", "", 1)])
    + frase(5, [("λέγει", "λέγω", "v3spia---", "PRED", 0),
                ("βιβλίον", "βιβλίον", "n-s---na-", "OBJ", 1)]),
    columns=list(COLONNE),
)


@pytest.fixture
def parole_chiavi() -> pd.DataFrame:
    return build_units(CHIAVI, active=CHIAVI).words


def test_la_numerazione_dello_strumento_non_frammenta_le_frequenze(parole_chiavi):
    """The measured case: in Gorman λέγω is written λέγω3 1,738 times out of 1,908.

    Counting on the lemma as it is written would give a profile built on three per cent
    of the occurrences, and logDice rewards rarity.
    """
    profilo = word_sketch(parole_chiavi, "λέγω")
    assert profilo["chiave"] == "λέγω"
    assert profilo["f_target"] == 5


def test_nfc_e_numerazione_si_applicano_tutt_e_due(parole_chiavi):
    """A spelling in NFD and a numbered one fall on the same key."""
    from greek_corpus_pipeline.stats import statistical_lemma_key
    assert statistical_lemma_key("λέγω3") == "λέγω"
    assert statistical_lemma_key(unicodedata.normalize("NFD", "λέγω1")) == "λέγω"
    assert statistical_lemma_key("λέγω") == "λέγω"


def test_la_mappa_delle_varianti_canoniche_non_si_applica_al_profilo():
    """Harmonising two different lemmas is an operation between resources, not within one.

    ``νοῦς`` and ``νόος`` are in the map of canonical variants and must remain two
    distinct lemmas in an intra-corpus statistic.
    """
    from greek_corpus_pipeline.normalise import LEMMA_VARIANTS
    from greek_corpus_pipeline.stats import statistical_lemma_key
    for variante, canonica in LEMMA_VARIANTS.items():
        assert statistical_lemma_key(variante) != statistical_lemma_key(canonica), \
            f"{variante} and {canonica} were merged by the profile key"


def test_le_grafie_da_cui_viene_la_chiave_non_si_perdono(parole_chiavi):
    """Knowing that λέγω is in the corpus as λέγω3 is a datum, not noise."""
    profilo = word_sketch(parole_chiavi, "λέγω")
    grafie = profilo["grafie"]
    assert set(grafie.columns) == {"grafia", "occorrenze"}
    assert int(grafie["occorrenze"].sum()) == 5
    assert len(grafie) == 3          # λέγω3, λέγω, λέγω1 in NFD
    assert "λέγω3" in set(grafie["grafia"])


# ---------------------------------------------------------------------------
# The empty relation
# ---------------------------------------------------------------------------

def test_la_relazione_vuota_conta_come_lemma_e_non_come_associazione(parole_chiavi):
    """Lexical frequency yes, syntactic association no.

    ``βιβλίον`` occurs twice, once without relation and once as object.  The occurrence
    without relation enters ``f_partner``, because it is a real occurrence of the lemma,
    and does not enter ``f_joint``, because the absence of a relation is not a relation.
    The catalogue flags it on its own with ``relation-missing``.
    """
    profilo = word_sketch(parole_chiavi, "λέγω")
    riga = profilo["associazioni"].set_index("lemma associato").loc["βιβλίον"]
    assert riga["occorrenze del lemma associato"] == 2
    assert riga["co-occorrenze"] == 1
    assert profilo["unita"]["archi_senza_relazione"] == 1


def test_nessuna_riga_del_profilo_ha_la_relazione_vuota(parole_chiavi):
    profilo = word_sketch(parole_chiavi, "λέγω")
    relazioni = profilo["associazioni"]["relazione"].astype(str)
    assert not relazioni.str.strip().eq("").any()
    assert not relazioni.str.startswith("(").any()


def test_logdice_usa_le_frequenze_della_chiave(parole_chiavi):
    """λέγω is worth 5 and λόγος is worth 3, with three arcs in common."""
    profilo = word_sketch(parole_chiavi, "λέγω")
    riga = profilo["associazioni"].set_index("lemma associato").loc["λόγος"]
    assert riga["co-occorrenze"] == 3
    assert riga["occorrenze del lemma associato"] == 3
    assert riga["occorrenze lemma"] == 5
    assert riga["logDice"] == pytest.approx(round(14 + math.log2(2 * 3 / (5 + 3)), 2))
