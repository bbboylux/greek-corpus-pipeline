# -*- coding: utf-8 -*-
"""The breathing that is an apostrophe, and the sign that is not a word.

Four questions, and each has done damage at least once.

An elision apostrophe written with the character of the smooth breathing must
be corrected: δ̓ is δʼ, and nobody doubts it.  A breathing that stands where it
must, above the initial vowel, is not touched: Ἵππων is perfect Greek, and a
rule that flagged it would be wrong, because in the Gorman file the two
diacritics are written *before* the capital iota.  A record whose form is the
sign alone is not a word with the wrong apostrophe: Pedalion has thirty-one of
them, with label “u--------” and relation AuxG, and they are editorial signs.
And the two checks on format characters propose the cleaned string, which is
the only possible answer and does not change a letter of what is read.
"""
from __future__ import annotations

import unicodedata

import pandas as pd
import pytest

#: How Gorman writes the elision of δέ: the consonant and the smooth breathing.
DELTA_ELISO = "δ" + "̓"

#: How Gorman writes Ἵππων: the two diacritics come *before* the capital.
IPPON_GORMAN = "̓́" + "Ιππων"

#: And the same word written as anyone else writes it.
IPPON_NORMALE = unicodedata.normalize("NFC", "Ἵππων")

#: The thirty-one isolated signs of Pedalion: the smooth and the rough breathing, alone.
SEGNI_ISOLATI = ["̓", "̔"]


def _corpus(forme: list[str], postag: str = "n-s---mn-",
            relation: str = "ATR") -> pd.DataFrame:
    """A minimal token table, with the columns that the checks read."""
    righe = []
    for indice, forma in enumerate(forme, start=1):
        righe.append({
            "source_file": "prova.xml", "document_id": "prova",
            "sentence_index": 0, "sentence_id": "1",
            "token_index": indice, "token_id": str(indice),
            "form": forma, "lemma": forma, "postag": postag,
            "relation": relation, "head": 0, "artificial": "",
        })
    return pd.DataFrame(righe)


# ── 1. the thirty-one isolated signs do not receive the apostrophe ────────
def test_i_segni_isolati_non_ricevono_l_apostrofo():
    """An editorial sign is not a word: there is nothing to replace."""
    from greek_corpus_pipeline.orthography import check_breathings

    tokens = _corpus(SEGNI_ISOLATI, postag="u--------", relation="AuxG")
    trovate = check_breathings(tokens)
    assert trovate.empty, "an isolated sign is not a badly written apostrophe"


def test_il_filtro_non_nasconde_i_segni_isolati():
    """They must be seen, not hidden: twenty-nine out of thirty-one are correctable.

    Hiding them as mere non-lexical records would make the correction of the bracket
    unreachable, and the two word fragments would vanish together with them.
    """
    from gui_qt.workers import filter_tokens

    tokens = _corpus(SEGNI_ISOLATI + ["λόγος"], postag="u--------", relation="AuxG")
    tenuti, tolti = filter_tokens(
        tokens, {"exclude_placeholders": True, "exclude_non_greek": False,
                 "exclude_punctuation": False})
    assert tolti == 0
    assert len(tenuti) == len(SEGNI_ISOLATI) + 1


def test_il_segno_isolato_ha_il_suo_controllo():
    """One fact, one check.

    The recognition of technical records is preprocessing and produces no findings: the
    dedicated check is the only one that reports an isolated breathing, and no other
    description needs to point to it.
    """
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG

    assert "isolated-breathing" in RULE_CATALOG
    dedicato = RULE_CATALOG["isolated-breathing"]
    assert dedicato["name"] == "Spirito isolato nella forma"
    assert dedicato["treatment"] == "manuale"


# ── 2. δ̓ still receives δʼ ───────────────────────────────────────────────
def test_delta_eliso_riceve_l_apostrofo_canonico():
    from greek_corpus_pipeline.orthography import CANONICAL_APOSTROPHE, check_breathings

    tokens = _corpus([DELTA_ELISO], postag="d--------").assign(lemma="δέ")
    trovate = check_breathings(tokens)
    assert len(trovate) == 1
    assert trovate.iloc[0]["suggested_form"] == "δ" + CANONICAL_APOSTROPHE
    assert trovate.iloc[0]["suggested_form"] == "δʼ"
    assert bool(trovate.iloc[0]["auto_correctable"]) is True


def test_lo_spirito_aspro_in_fondo_non_diventa_un_apostrofo():
    """The rough breathing was never an apostrophe: replacing it would be a reading."""
    from greek_corpus_pipeline.orthography import check_breathings

    assert check_breathings(_corpus(["δ" + "̔"])).empty


# ── 3. Ἵππων is not flagged ──────────────────────────────────────────────
@pytest.mark.parametrize("forma", [IPPON_GORMAN, IPPON_NORMALE])
def test_ippon_non_viene_segnalato(forma):
    """The breathing is on the vowel, where it must be, however it is written."""
    from greek_corpus_pipeline.orthography import check_breathings

    assert check_breathings(_corpus([forma])).empty


def test_una_vocale_con_lo_spirito_in_fondo_non_viene_segnalata():
    """ὁ ends with the breathing, but the breathing is its own: it is a diacritic."""
    from greek_corpus_pipeline.orthography import check_breathings

    assert check_breathings(_corpus([unicodedata.normalize("NFC", "ὁ")])).empty


# ── 4. the format characters propose the cleaned string ──────────────────
def test_i_caratteri_di_formato_propongono_la_stringa_ripulita():
    """Removing a format character has a single answer, and the program gives it.

    The zero-width character has no rendering on screen: removing it does not change a
    letter of what is read and makes two tokens match that no comparison recognised as
    equal before.  The check therefore declares automatic treatment, and the proposal
    must reach the corpus.
    """
    from greek_corpus_pipeline.proposte import allinea_proposte, controlla_coerenza
    from greek_corpus_pipeline.orthography import check_invisible_characters
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG, default_auto_apply

    for rid in ("invisible-char-form", "invisible-char-lemma"):
        assert RULE_CATALOG[rid]["treatment"] == "automatica"
        assert default_auto_apply(rid) is True

    tokens = _corpus(["\u03bb\u03cc\u200b\u03b3\u03bf\u03c2"])
    tokens.loc[0, "lemma"] = "\u03bb\u03cc\ufeff\u03b3\u03bf\u03c2"
    trovate = check_invisible_characters(tokens)
    assert not trovate.empty, "the check must flag it"
    assert set(trovate["rule_id"]) <= {"invisible-char-form", "invisible-char-lemma"}

    allineate = allinea_proposte(trovate, tokens, "prova")
    assert allineate["auto_correctable"].all()
    forma = allineate.loc[allineate["rule_id"] == "invisible-char-form", "suggested_form"]
    lemma = allineate.loc[allineate["rule_id"] == "invisible-char-lemma", "suggested_lemma"]
    assert list(forma) == ["\u03bb\u03cc\u03b3\u03bf\u03c2"]
    assert list(lemma) == ["\u03bb\u03cc\u03b3\u03bf\u03c2"]
    assert controlla_coerenza(allineate) == []


def test_la_stringa_ripulita_arriva_nel_corpus():
    """It is not enough that the proposal is seen: it must enter the exported text."""
    import pandas as pd
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    from greek_corpus_pipeline.orthography import check_invisible_characters

    tokens = _corpus(["\u03bb\u03cc\u200b\u03b3\u03bf\u03c2"])
    trovate = check_invisible_characters(tokens)
    forma = trovate[trovate["rule_id"] == "invisible-char-form"]
    corretto = apply_suggested_corrections(
        tokens, pd.DataFrame(), pd.DataFrame(),
        enabled_rule_ids={"invisible-char-form"}, form_findings=forma)
    assert list(corretto["form"]) == ["\u03bb\u03cc\u03b3\u03bf\u03c2"]


# ── 5. the isolated breathing: verified brackets and broken words ─────────
ASPRO, DOLCE = "̔", "̓"

#: The two records that are not brackets but word fragments.
PAEAN_MANUALI = ("Leuven|PaeanBrev|5|28", "Leuven|PaeanBrev|10|12")


def _pedalion(righe: list[dict]) -> pd.DataFrame:
    """A corpus fragment with the columns that the check reads."""
    fuori = []
    for indice, r in enumerate(righe, start=1):
        fuori.append({
            "corpus": r.get("corpus", "pedalion"), "source_file": "pedalion.xml",
            "document_id": r.get("document_id", "prova"),
            "sentence_index": 0, "sentence_id": "1",
            "token_index": indice, "token_id": str(indice),
            "ref": r["ref"], "form": r["form"], "lemma": r.get("lemma", r["form"]),
            "postag": r.get("postag", "u--------"),
            "relation": r.get("relation", "AuxG"), "head": r.get("head", 0),
            "artificial": "",
        })
    return pd.DataFrame(fuori)


def _tutti_i_segni() -> pd.DataFrame:
    """The thirty-one records of Pedalion: the twenty-nine validated plus the two Paean."""
    from greek_corpus_pipeline.rule_catalog import PARENTHESIS_REPAIRS

    righe = [{"ref": str(r["ref"]), "form": str(r["form"]), "lemma": str(r["lemma"]),
              "postag": str(r["postag"]), "relation": str(r["relation"])}
             for r in PARENTHESIS_REPAIRS]
    righe += [{"ref": ref, "form": ASPRO} for ref in PAEAN_MANUALI]
    return _pedalion(righe)


def _proposte(tokens: pd.DataFrame, corpus: str = "pedalion") -> pd.DataFrame:
    from greek_corpus_pipeline.orthography import check_isolated_breathing
    from greek_corpus_pipeline.proposte import allinea_proposte

    return allinea_proposte(check_isolated_breathing(tokens), tokens, corpus)


def test_lo_spirito_isolato_trova_trentuno_record():
    trovate = _proposte(_tutti_i_segni())
    assert len(trovate) == 31
    assert set(trovate["rule_id"]) == {"isolated-breathing"}


def test_ventinove_proposte_sedici_aperte_e_tredici_chiuse():
    trovate = _proposte(_tutti_i_segni())
    proposte = [p for p in trovate["suggested_form"] if isinstance(p, str)]
    assert len(proposte) == 29
    assert proposte.count("(") == 16
    assert proposte.count(")") == 13


@pytest.mark.parametrize("ref", PAEAN_MANUALI)
def test_i_due_casi_paean_restano_manuali(ref):
    """They are word fragments, not brackets: no proposal."""
    trovate = _proposte(_tutti_i_segni())
    riga = trovate[trovate["form"] == ASPRO].reset_index(drop=True)
    tokens = _tutti_i_segni()
    posizione = list(tokens["ref"]).index(ref)
    corrispondente = trovate.iloc[posizione]
    assert corrispondente["ref"] == ref if "ref" in trovate.columns else True
    senza = _proposte(_pedalion([{"ref": ref, "form": ASPRO}]))
    assert len(senza) == 1
    assert pd.isna(senza.iloc[0]["suggested_form"])
    assert not bool(senza.iloc[0]["auto_correctable"])


def test_un_ref_non_validato_non_riceve_proposta():
    """The list is closed: a new case is flagged and that is all."""
    senza = _proposte(_pedalion([{"ref": "Leuven|0006-003|9999|1", "form": ASPRO}]))
    assert len(senza) == 1
    assert pd.isna(senza.iloc[0]["suggested_form"])


def test_un_ref_validato_fuori_da_pedalion_non_riceve_proposta():
    """The proposal is valid for the resource in which it was checked."""
    from greek_corpus_pipeline.rule_catalog import PARENTHESIS_REPAIRS

    prima = PARENTHESIS_REPAIRS[0]
    riga = [{"ref": str(prima["ref"]), "form": str(prima["form"]),
             "lemma": str(prima["lemma"]), "postag": str(prima["postag"]),
             "relation": str(prima["relation"]), "corpus": "gorman"}]
    altrove = _proposte(_pedalion(riga), corpus="gorman")
    assert len(altrove) == 1
    assert pd.isna(altrove.iloc[0]["suggested_form"])


def test_le_parentesi_gia_scritte_non_vengono_segnalate():
    """The 73 plus 73 records already converted are fine and stay out."""
    gia_fatte = _pedalion([
        {"ref": "Leuven|0006-003|1|1", "form": "(", "lemma": ASPRO},
        {"ref": "Leuven|0006-003|1|2", "form": ")", "lemma": DOLCE},
    ])
    from greek_corpus_pipeline.orthography import check_isolated_breathing
    assert check_isolated_breathing(gia_fatte).empty


def test_la_proposta_tocca_soltanto_la_forma():
    """Lemma, label, relation and head stay what they are."""
    from greek_corpus_pipeline.rule_catalog import PARENTHESIS_REPAIRS

    prima = PARENTHESIS_REPAIRS[0]
    tokens = _pedalion([{"ref": str(prima["ref"]), "form": str(prima["form"]),
                         "lemma": str(prima["lemma"]), "postag": str(prima["postag"]),
                         "relation": str(prima["relation"]), "head": 0}])
    trovata = _proposte(tokens).iloc[0]
    assert trovata["suggested_form"] == str(prima["suggest"])
    for colonna in ("suggested_lemma", "suggested_postag", "suggested_relation",
                    "suggested_head"):
        if colonna in trovata.index:
            assert pd.isna(trovata[colonna]), colonna
    # and the corpus has not been touched
    assert list(tokens["lemma"]) == [str(prima["lemma"])]
    assert list(tokens["postag"]) == [str(prima["postag"])]
    assert list(tokens["relation"]) == [str(prima["relation"])]
    assert list(tokens["head"]) == [0]


def test_l_elenco_delle_parentesi_e_chiuso_e_coerente():
    from greek_corpus_pipeline.rule_catalog import PARENTHESIS_REPAIRS

    assert len(PARENTHESIS_REPAIRS) == 29
    riferimenti = [str(r["ref"]) for r in PARENTHESIS_REPAIRS]
    assert len(set(riferimenti)) == 29
    for ref in PAEAN_MANUALI:
        assert ref not in riferimenti
    aperte = [r for r in PARENTHESIS_REPAIRS if r["suggest"] == "("]
    chiuse = [r for r in PARENTHESIS_REPAIRS if r["suggest"] == ")"]
    assert len(aperte) == 16 and len(chiuse) == 13
    assert all(str(r["form"]) == ASPRO for r in aperte)
    assert all(str(r["form"]) == DOLCE for r in chiuse)
    assert all(str(r.get("campo")) == "form" for r in PARENTHESIS_REPAIRS)


# ── 6. the apostrophe: broad detection, narrow proposal ──────────────────
def test_delta_con_lemma_diverso_non_riceve_proposta():
    from greek_corpus_pipeline.orthography import check_breathings

    trovate = check_breathings(_corpus([DELTA_ELISO]))
    assert len(trovate) == 1
    trovate = check_breathings(
        _corpus([DELTA_ELISO]).assign(lemma="δεῖνα"))
    assert len(trovate) == 1, "it must be flagged anyway"
    assert pd.isna(trovate.iloc[0]["suggested_form"]), "but without a proposal"


def test_un_altra_consonante_con_lo_spirito_finale_e_solo_segnalata():
    from greek_corpus_pipeline.orthography import check_breathings

    trovate = check_breathings(_corpus(["τ" + DOLCE]).assign(lemma="τε"))
    assert len(trovate) == 1
    assert pd.isna(trovate.iloc[0]["suggested_form"])


def test_ou_in_nfd_non_viene_segnalato():
    """οὐ ends with U+0313, but above an upsilon: it is its breathing."""
    from greek_corpus_pipeline.orthography import check_breathings

    assert check_breathings(_corpus([unicodedata.normalize("NFC", "οὐ")])).empty
    assert check_breathings(_corpus([unicodedata.normalize("NFD", "οὐ")])).empty


def test_il_rho_con_lo_spirito_non_viene_segnalato():
    from greek_corpus_pipeline.orthography import check_breathings

    assert check_breathings(_corpus(["ῥ" + DOLCE])).empty
