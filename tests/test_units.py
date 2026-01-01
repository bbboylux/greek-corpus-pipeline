"""The five units, the sentence key and the structure of the measure.

The expected values are not invented: they come from the audit of the
counting units run on the six frozen corpora of the article.  A test that
sees them change is signalling either a defect or a scientific decision, and
in neither case may the number be updated without saying which of the two.
"""
from __future__ import annotations

import pandas as pd
import pytest

from greek_corpus_pipeline.units import (
    INTERPRETABLE_POS,
    Measure,
    Units,
    analyzable_link_mask,
    analyzable_sentence_keys,
    build_units,
    is_punctuation,
    is_technical_record,
    is_word,
    sentence_key,
)


def _corpus() -> pd.DataFrame:
    """A minimal corpus that contains one example of every limiting case.

    Two sentences in two different files, with the same ``sentence_index``: it is the
    case that unmasks the use of ``sentence_id`` as a key.
    """
    rows = [
        # sentence 1 of alfa: root, two dependents, a comma, an elliptical node
        dict(source_file="alfa.xml", document_id="alfa", sentence_index=1,
             sentence_id="1", token_id=1, head=0, form="λέγει", lemma="λέγω",
             postag="v3spia---", relation="PRED", artificial=""),
        dict(source_file="alfa.xml", document_id="alfa", sentence_index=1,
             sentence_id="1", token_id=2, head=1, form="ἄνθρωπος", lemma="ἄνθρωπος",
             postag="n-s---mn-", relation="SBJ", artificial=""),
        dict(source_file="alfa.xml", document_id="alfa", sentence_index=1,
             sentence_id="1", token_id=3, head=1, form="ταῦτα", lemma="οὗτος",
             postag="p-p---na-", relation="OBJ", artificial=""),
        dict(source_file="alfa.xml", document_id="alfa", sentence_index=1,
             sentence_id="1", token_id=4, head=0, form=",", lemma=",",
             postag="u--------", relation="AuxX", artificial=""),
        dict(source_file="alfa.xml", document_id="alfa", sentence_index=1,
             sentence_id="1", token_id=5, head=1, form="ἐστιν", lemma="εἰμί",
             postag="v3spia---", relation="AuxV", artificial="elliptic"),
        # sentence 1 of beta: same sentence_index and same sentence_id
        dict(source_file="beta.xml", document_id="beta", sentence_index=1,
             sentence_id="1", token_id=1, head=0, form="γράφει", lemma="γράφω",
             postag="v3spia---", relation="PRED", artificial=""),
        dict(source_file="beta.xml", document_id="beta", sentence_index=1,
             sentence_id="1", token_id=2, head=1, form="[0]", lemma="",
             postag="", relation="ExD", artificial=""),
        dict(source_file="beta.xml", document_id="beta", sentence_index=1,
             sentence_id="1", token_id=3, head=1, form="G", lemma="",
             postag="z--------", relation="ExD", artificial=""),
        # a sign with a malformed tag but a punctuation relation
        dict(source_file="beta.xml", document_id="beta", sentence_index=1,
             sentence_id="1", token_id=4, head=0, form="·", lemma="·",
             postag="u-", relation="AuxK", artificial=""),
        # a dangling arc: head 99 does not exist in the sentence
        dict(source_file="beta.xml", document_id="beta", sentence_index=1,
             sentence_id="1", token_id=5, head=99, form="δέ", lemma="δέ",
             postag="d--------", relation="AuxY", artificial=""),
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The three predicates
# ---------------------------------------------------------------------------

def test_record_tecnico_riconosciuto_in_tutti_e_cinque_i_modi():
    corpus = _corpus()
    technical = is_technical_record(corpus)
    # artificial with a value, form [0], form G, tag starting with z
    assert technical.sum() == 3
    assert technical.iloc[4]          # artificial="elliptic", real form ἐστιν
    assert technical.iloc[6]          # form [0]
    assert technical.iloc[7]          # form G, and tag z--------


def test_punteggiatura_riconosciuta_dal_tag_e_dalla_relazione():
    corpus = _corpus()
    punctuation = is_punctuation(corpus)
    assert punctuation.sum() == 2
    assert punctuation.iloc[3]        # tag u--------
    assert punctuation.iloc[8]        # malformed tag «u-», but relation AuxK


# ── The hierarchy: the label decides, the relation speaks in its silence ───

def _record(**campi):
    """A minimal record, with the fields that the predicates read."""
    base = dict(source_file="x.xml", document_id="x", sentence_index=1,
                sentence_id="1", token_id=1, head=1, form="", lemma="",
                postag="", relation="", artificial="")
    base.update(campi)
    return pd.DataFrame([base])


def test_una_parola_vera_con_relazione_di_punteggiatura_resta_parola():
    """The case that led to rejecting the unconditional fallback.

    οὔ, δὲ, οὖν, καὶ carry a readable linguistic label and, in a few dozen records, a
    punctuation relation.  The wrong relation is an anomaly of the syntactic annotation:
    the catalogue flags it, and it does not change the lexical nature of the record.
    """
    for forma, tag in (("οὔ", "d--------"), ("δὲ", "d--------"),
                       ("οὖν", "d--------"), ("καὶ", "c--------"),
                       ("ὥσπερ", "c--------")):
        for relazione in ("AuxG", "AuxK", "AuxX"):
            r = _record(form=forma, postag=tag, relation=relazione)
            assert bool(is_word(r).iloc[0]), f"{forma} con {relazione}"
            assert not bool(is_punctuation(r).iloc[0]), f"{forma} con {relazione}"


def test_un_segno_con_etichetta_non_interpretabile_e_punteggiatura():
    """The opposite side: “e” is a letter and is not a part of speech.

    In Gorman 17 semicolons carry “e--------”, and they are the same ones that the check
    “PoS e on a punctuation mark” flags.
    """
    for tag in ("e--------", "--------", "---------", ""):
        r = _record(form=";", postag=tag, relation="AuxK")
        assert bool(is_punctuation(r).iloc[0]), f"tag {tag!r}"
        assert not bool(is_word(r).iloc[0]), f"tag {tag!r}"


def test_letichetta_u_decide_da_sola():
    """Whatever relation it carries, a record labelled “u” is a sign."""
    for relazione in ("AuxK", "ATR", "PRED", "COORD", ""):
        r = _record(form="·", postag="u--------", relation=relazione)
        assert bool(is_punctuation(r).iloc[0]), f"relazione {relazione!r}"
        assert not bool(is_word(r).iloc[0]), f"relazione {relazione!r}"


def test_un_record_tecnico_non_e_mai_una_parola():
    """It takes precedence over everything: label and relation do not count."""
    casi = [
        dict(form="ἐστιν", postag="v3spia---", relation="AuxV", artificial="elliptic"),
        dict(form="[0]", postag="n-s---mn-", relation="SBJ"),
        dict(form="G", postag="z--------", relation="ExD"),
        dict(form="G?", postag="d--------", relation="ATR"),
        dict(form="", postag="", relation="ATR"),
    ]
    for campi in casi:
        r = _record(**campi)
        assert bool(is_technical_record(r).iloc[0]), campi
        assert not bool(is_word(r).iloc[0]), campi


def test_una_estensione_locale_documentata_e_una_categoria_linguistica():
    """The “b” of Pedalion is not an empty field.

    A forward guard, not a correction: on the six frozen corpora none of the
    12,092 records labelled “b” carries a punctuation relation, so the fallback
    never meets them.  The test is there so that it does not meet them tomorrow
    either, if a corpus were to annotate them so.
    """
    assert "b" in INTERPRETABLE_POS
    for relazione in ("AuxG", "AuxK", "AuxX"):
        r = _record(form="τε", postag="b--------", relation=relazione)
        assert bool(is_word(r).iloc[0]), relazione


def test_z_e_x_non_sono_categorie_linguistiche():
    """“z” marks a technical record, “x” declares that AGDT cannot classify.

    Neither must prevent the relation from speaking, and “z” is in any case already
    intercepted by is_technical_record.
    """
    assert "z" not in INTERPRETABLE_POS
    assert "x" not in INTERPRETABLE_POS
    r = _record(form=";", postag="x--------", relation="AuxK")
    assert bool(is_punctuation(r).iloc[0])


def test_senza_prova_di_punteggiatura_il_record_resta_una_parola():
    """Mute label and a relation that does not say punctuation: no proof.

    These are the three Gorman records with form “->”, “..”, “...” and tag “--------”:
    they stay among the words because nothing says that they are signs.
    """
    r = _record(form="...", postag="--------", relation="ATR")
    assert bool(is_word(r).iloc[0])


def test_una_parola_non_e_ne_tecnica_ne_punteggiatura():
    corpus = _corpus()
    words = is_word(corpus)
    assert list(corpus.loc[words, "form"]) == [
        "λέγει", "ἄνθρωπος", "ταῦτα", "γράφει", "δέ"]


def test_il_filtro_dellutente_non_cambia_le_words():
    """The point for which this module exists.

    With the exclusion of the technical records on and off, the ``words`` are the
    same: an elliptical node does not become a word because a tick has been
    removed.
    """
    corpus = _corpus()
    con_filtro = build_units(corpus)
    senza_filtro = build_units(corpus, active=corpus)

    assert con_filtro.n_active_records == 7
    assert senza_filtro.n_active_records == 10
    assert con_filtro.n_words == senza_filtro.n_words == 5
    assert list(con_filtro.words["form"]) == list(senza_filtro.words["form"])


# ---------------------------------------------------------------------------
# The sentence key
# ---------------------------------------------------------------------------

def test_sentence_id_da_solo_fonderebbe_due_frasi():
    corpus = _corpus()
    assert corpus["sentence_id"].nunique() == 1      # the field says “one sentence”
    assert sentence_key(corpus).nunique() == 2       # the sentences are two


def test_la_chiave_usa_tutte_e_tre_le_colonne():
    corpus = _corpus()
    chiavi = sentence_key(corpus).unique()
    assert all("alfa" in k or "beta" in k for k in chiavi)
    assert all(k.endswith("1") for k in chiavi)


# ---------------------------------------------------------------------------
# Arcs and sentences
# ---------------------------------------------------------------------------

def test_un_arco_verso_un_nodo_tecnico_non_e_analizzabile():
    corpus = _corpus()
    units = build_units(corpus)
    forme = list(units.analyzable_links["form"])
    # ἄνθρωπος and ταῦτα point to the root, which is active: analysable. ἐστιν is
    # technical and is not among the active ones. δέ points to 99, which does not exist.
    assert forme == ["ἄνθρωπος", "ταῦτα"]


def test_head_zero_non_produce_un_arco():
    corpus = _corpus()
    mask = analyzable_link_mask(corpus, within=corpus)
    radici = corpus["head"] == 0
    assert not mask[radici].any()


def test_una_frase_analizzabile_ha_una_radice_e_nessun_arco_pendente():
    corpus = _corpus()
    chiavi = analyzable_sentence_keys(corpus)
    # alfa has a single non-punctuation root and no dangling arc. beta has the arc of δέ
    # towards token 99, which does not exist.
    assert len(chiavi) == 1
    assert any("alfa" in k for k in chiavi)


def test_la_punteggiatura_appesa_a_zero_non_e_una_seconda_radice():
    corpus = _corpus()
    alfa = corpus[corpus["source_file"] == "alfa.xml"]
    # in alfa, λέγει and the comma both have head = 0
    assert (pd.to_numeric(alfa["head"]) == 0).sum() == 2
    # but the sentence is analysable: the comma does not count as a root
    assert len(analyzable_sentence_keys(alfa)) == 1


# ---------------------------------------------------------------------------
# The structure of the measure
# ---------------------------------------------------------------------------

def test_una_misura_dichiara_i_sei_campi():
    units = build_units(_corpus(), filters={"exclude_placeholders": True})
    misura = units.measure("tasso di prova", 1, denominator_name="active_records")
    dati = misura.as_dict()
    for campo in ("numerator", "denominator", "denominator_name",
                  "universe", "filters", "parameters"):
        assert campo in dati
    assert dati["denominator"] == units.n_active_records
    assert dati["filters"] == {"exclude_placeholders": True}


def test_il_denominatore_viene_dallunita_nominata():
    units = build_units(_corpus())
    su_parole = units.measure("x", 1, denominator_name="words")
    su_attivi = units.measure("x", 1, denominator_name="active_records")
    assert su_parole.denominator == 5
    assert su_attivi.denominator == 7
    assert su_parole.value != su_attivi.value


def test_un_denominatore_esplicito_dichiara_luniverso():
    units = build_units(_corpus())
    misura = units.measure(
        "parole con etichetta valida", 3,
        denominator_name="words_con_tag_valido", denominator=4, universe="words")
    assert misura.universe == "words"
    assert misura.denominator_name == "words_con_tag_valido"


def test_i_tassi_per_diecimila_usano_la_stessa_struttura():
    units = build_units(_corpus())
    misura = units.measure("segnalazioni ogni diecimila", 7,
                           denominator_name="active_records", per=10000)
    assert misura.per == 10000
    assert misura.value == round(10000 * 7 / 7, 4)


def test_un_nome_di_unita_sbagliato_e_un_errore_esplicito():
    units = build_units(_corpus())
    with pytest.raises(KeyError, match="five units"):
        units.size_of("token")


def test_denominatore_zero_non_esplode():
    units = build_units(pd.DataFrame(columns=[
        "source_file", "document_id", "sentence_index", "sentence_id",
        "token_id", "head", "form", "lemma", "postag", "relation", "artificial"]))
    assert units.measure("x", 0, denominator_name="words").value == 0.0


# ---------------------------------------------------------------------------
# The values measured on the real corpora, as a reminder of the contract
# ---------------------------------------------------------------------------

#: What the six frozen corpora must produce with these definitions.  They are the values
#: of the audit, approved as verification targets.
VALORI_ATTESI = {
    "gorman": dict(imported_records=625_176, active_records=616_646, words=548_912),
    "pedalion": dict(imported_records=281_245, active_records=274_609, words=238_413),
    "glaux_auto": dict(imported_records=300_292, active_records=292_567, words=251_994),
    "glaux_man": dict(imported_records=21_652, active_records=21_107, words=17_834),
    "glaux_conf_auto": dict(imported_records=273_354, active_records=267_313, words=231_725),
    "glaux_conf_man": dict(imported_records=28_666, active_records=28_143, words=24_351),
}


def test_i_valori_attesi_sono_dichiarati_per_tutti_e_sei_gli_strati():
    """It does not touch the corpora: it verifies that the contract is written in full.

    The real comparison with the data is done by the script of the complete run, which
    has the corpora at hand; here it is only checked that no stratum is left without a
    target when the numbers are regenerated.
    """
    assert len(VALORI_ATTESI) == 6
    for nome, attesi in VALORI_ATTESI.items():
        assert set(attesi) == {"imported_records", "active_records", "words"}
        assert attesi["words"] < attesi["active_records"] < attesi["imported_records"], nome
