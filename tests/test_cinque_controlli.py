# -*- coding: utf-8 -*-
"""Checks whose canonical text makes a promise, held to it.

A canonical text says what the program does.  These tests verify that it really does it:
that the suggestion is there where the text promises it, that the automatic correction
is not there where the text excludes it, and that the list of characters that a rule
deletes is the one written and no other.
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


# ── lemma-rare-for-form: suggests, does not correct ──────────────────────
def _segnalazioni(rule_id: str, strato: str = "gorman") -> pd.DataFrame:
    from conftest import CORPORA_ENV, findings_dir

    cartella = findings_dir()
    percorso = None if cartella is None else cartella / f"findings-{strato}.parquet"
    if percorso is None or not percorso.exists():
        pytest.skip(f"the frozen findings of {strato} are not available "
                    f"(point to the corpora with {CORPORA_ENV})")
    tabella = pd.read_parquet(percorso)
    return tabella[tabella["rule_id"] == rule_id]


def test_lemma_raro_suggerisce_il_lemma_di_maggioranza(tokens):
    """The canonical text promises an alternative: it must be there."""
    from greek_corpus_pipeline.lemma import check_rare_lemma_for_form

    # Twenty-five occurrences of the same form+PoS pair, twenty-four with the majority
    # lemma and one with a different lemma: the exact threshold.
    righe = []
    for indice in range(25):
        righe.append({
            "source_file": "p.xml", "document_id": "p", "sentence_index": 0,
            "sentence_id": "1", "token_index": indice, "token_id": str(indice + 1),
            "form": "ὄντα", "postag": "v-sppana-",
            "lemma": "εἰμί" if indice < 24 else "ὤν",
        })
    trovate = check_rare_lemma_for_form(pd.DataFrame(righe))
    assert len(trovate) == 1, "the threshold of twenty-five is not the declared one"
    riga = trovate.iloc[0]
    assert riga["lemma"] == "ὤν"
    assert riga["suggested_lemma"] == "εἰμί", "the majority lemma is not suggested"
    assert not bool(riga["auto_correctable"]), (
        "the check declares itself automatically applicable")


def test_lemma_raro_non_corregge_mai_da_se():
    """On the whole frozen corpus: always a suggestion, never an application."""
    trovate = _segnalazioni("lemma-rare-for-form")
    if trovate.empty:
        pytest.skip("no occurrence in the frozen corpus")
    assert trovate["suggested_lemma"].notna().all(), (
        "some finding does not carry the majority lemma")
    assert not trovate["auto_correctable"].fillna(False).astype(bool).any(), (
        "some finding is automatically applicable")


def test_le_tre_soglie_del_lemma_raro_sono_quelle_scritte():
    """Twenty-five, one, 95%: the canonical description names them."""
    import inspect
    from greek_corpus_pipeline.lemma import check_rare_lemma_for_form
    parametri = inspect.signature(check_rare_lemma_for_form).parameters
    assert parametri["min_form_total"].default == 25
    assert parametri["max_rare"].default == 1
    assert parametri["min_major_share"].default == 0.95


# ── dein-participle-disputed: closed list, no whole author ───────────────
def test_i_luoghi_contestati_sono_un_elenco_chiuso():
    from greek_corpus_pipeline.postag import DEIN_DISPUTED_LOCI

    assert DEIN_DISPUTED_LOCI, "the list of contested passages is empty"
    for luogo in DEIN_DISPUTED_LOCI:
        assert luogo.get("locus"), "an entry without the name of the passage"
        assert luogo.get("stato"), f"“{luogo['locus']}” does not declare its own status"
        assert luogo.get("autore_urn"), (
            f"“{luogo['locus']}” does not even say which author it belongs to")


def test_ogni_luogo_dichiara_con_quale_precisione_e_identificabile():
    """“identificato” (identified) carries the work, “non_escludibile” (not excludable)
    only the author."""
    from greek_corpus_pipeline.postag import DEIN_DISPUTED_LOCI

    stati = {str(luogo["stato"]) for luogo in DEIN_DISPUTED_LOCI}
    assert stati <= {"identificato", "non_escludibile"}, f"unknown statuses: {stati}"
    for luogo in DEIN_DISPUTED_LOCI:
        assert luogo.get("granularita"), (
            f"“{luogo['locus']}” does not declare how precisely it can be identified")
        if luogo["stato"] == "identificato":
            urn = str(luogo["cts_urn"])
            assert "." in urn, (
                f"“{urn}” identifies an author and not a work: a passage declared "
                "identified must carry the work")
            assert luogo.get("verificato_su"), (
                f"“{luogo['locus']}” declares itself identified without a verified occurrence")
        else:
            assert not luogo.get("cts_urn"), (
                f"“{luogo['locus']}” declares itself not excludable but carries a work")


def _dein(**campi) -> pd.DataFrame:
    base = {"source_file": "x.xml", "sentence_index": 0, "sentence_id": "1",
            "token_index": 0, "token_id": "1", "form": "δεῖν", "lemma": "δεῖ",
            "postag": "v-sppana-", "relation": "OBJ", "head": "0",
            "document_id": "d", "cts_urn": ""}
    base.update(campi)
    return pd.DataFrame([base])


def _esito(tabella: pd.DataFrame) -> tuple[str, bool]:
    """The rule that took the occurrence, and whether it proposes a correction."""
    from greek_corpus_pipeline.postag import analyze_postags
    trovate = analyze_postags(tabella)
    d = trovate[trovate["rule_id"].isin(("dein-participle",
                                         "dein-participle-disputed"))]
    assert len(d) == 1, f"rules found: {sorted(set(trovate['rule_id']))}"
    riga = d.iloc[0]
    return str(riga["rule_id"]), bool(riga["auto_correctable"])


def test_uno_il_luogo_identificato_va_a_revisione():
    """Lysias 14: the resource identifies it, the program does not correct."""
    from greek_corpus_pipeline.postag import DEIN_DISPUTED_LOCI

    luogo = next(l for l in DEIN_DISPUTED_LOCI if l["stato"] == "identificato")
    regola, auto = _esito(_dein(
        document_id=luogo["verificato_su"]["document_id"],
        cts_urn=luogo["cts_urn"]))
    assert regola == "dein-participle-disputed"
    assert not auto


def test_due_autore_noto_ma_frammento_non_identificabile_va_a_revisione():
    """Aristophanes: the author is known, not whether it is fragment 220."""
    from greek_corpus_pipeline.postag import DEIN_DISPUTED_LOCI

    luogo = next(l for l in DEIN_DISPUTED_LOCI if l["stato"] == "non_escludibile")
    autore = str(luogo["autore_urn"])
    regola, auto = _esito(_dein(document_id="aristofane",
                                cts_urn=f"{autore}.tlg003"))
    assert regola == "dein-participle-disputed", (
        "a participial δεῖν in Aristophanes is corrected automatically")
    assert not auto
    # and also when the author is in “tlg_author” rather than in the citation
    regola, auto = _esito(_dein(document_id="aristofane", cts_urn="",
                                tlg_author=autore, tlg_work="tlg003"))
    assert regola == "dein-participle-disputed"
    assert not auto


@pytest.mark.parametrize("campi,descrizione", [
    ({}, "nessuna provenienza"),
    ({"tlg_author": "tlg0014"}, "autore senza opera"),
    ({"tlg_work": "tlg050"}, "opera senza autore"),
])
def test_tre_provenienza_insufficiente_va_a_revisione(campi, descrizione):
    """Without author and work no doubtful place can be excluded."""
    regola, auto = _esito(_dein(**campi))
    assert regola == "dein-participle-disputed", (
        f"with {descrizione} the occurrence is corrected automatically")
    assert not auto, (
        "a missing provenance becomes a licence to correct")


@pytest.mark.parametrize("campi,descrizione", [
    ({"cts_urn": "tlg0010.tlg004"}, "citazione composta"),
    ({"cts_urn": "", "tlg_author": "tlg0014", "tlg_work": "tlg050"},
     "autore e opera separati, come in Demostene 50"),
    ({"document_id": "aristophanes-copia", "cts_urn": "tlg0010.tlg004"},
     "nome di file che somiglia a un autore contestato"),
])
def test_quattro_provenienza_piena_e_non_contestata_viene_corretta(campi, descrizione):
    """Where the provenance exists and says that it is not one of those places, it is
    corrected."""
    regola, auto = _esito(_dein(**campi))
    assert regola == "dein-participle", f"with {descrizione} it is not corrected"
    assert auto


def test_il_nome_del_file_non_e_una_provenienza():
    """A document called “aristophanes” is not proof that it is."""
    regola, _ = _esito(_dein(document_id="aristophanes-ranae",
                             cts_urn="tlg0010.tlg004"))
    assert regola == "dein-participle", (
        "the file name is used to infer the author")


def test_la_segnalazione_dice_quale_delle_tre_ragioni_e():
    """Three different situations, three different explanations in the row."""
    from greek_corpus_pipeline.postag import analyze_postags, DEIN_DISPUTED_LOCI

    identificato = next(l for l in DEIN_DISPUTED_LOCI if l["stato"] == "identificato")
    non_escludibile = next(l for l in DEIN_DISPUTED_LOCI
                           if l["stato"] == "non_escludibile")
    testi = []
    for tabella in (_dein(cts_urn=identificato["cts_urn"]),
                    _dein(cts_urn=f"{non_escludibile['autore_urn']}.tlg003"),
                    _dein()):
        trovate = analyze_postags(tabella)
        riga = trovate[trovate["rule_id"] == "dein-participle-disputed"].iloc[0]
        testi.append(str(riga["issue"]))
    assert len(set(testi)) == 3, "two different situations give the same explanation"
    assert "LSJ" in testi[0]
    assert "granularità" in testi[1]
    assert "non identifica autore e opera" in testi[2]
    for testo in testi[1:]:
        assert "è uno dei luoghi" not in testo, (
            "the row declares as an LSJ passage a case that is not one")


# ── isolated-breathing: proposed from a closed table, never applied ──────
def test_lo_spirito_isolato_propone_solo_dove_e_stato_verificato():
    """Twenty-nine occurrences with a proposal, two without, none applicable."""
    from greek_corpus_pipeline.proposte import allinea_proposte

    from conftest import CORPORA_ENV, corpus_tokens

    corpus = corpus_tokens("pedalion")
    if corpus is None:
        pytest.skip(f"the Pedalion corpus is not available "
                    f"(point to it with {CORPORA_ENV})")
    trovate = _segnalazioni("isolated-breathing", "pedalion")
    if trovate.empty:
        pytest.skip("no occurrence in the frozen corpus")
    complete = allinea_proposte(
        _segnalazioni("isolated-breathing", "pedalion"),
        pd.read_parquet(corpus), corpus="pedalion")
    con = int(complete["suggested_form"].notna().sum())
    senza = int(complete["suggested_form"].isna().sum())
    assert con == 29, f"the verified occurrences with a proposal are {con}, not 29"
    assert senza == 2, f"the occurrences without a proposal are {senza}, not 2"
    assert not complete["auto_correctable"].fillna(False).astype(bool).any(), (
        "a bracket proposal turns out to be automatically applicable")
    assert set(complete["suggested_form"].dropna()) <= {"(", ")"}


def test_le_riparazioni_delle_parentesi_sono_una_tabella_chiusa():
    from greek_corpus_pipeline.rule_catalog import PARENTHESIS_REPAIRS

    nostre = [r for r in PARENTHESIS_REPAIRS
              if str(r["rule_id"]) == "isolated-breathing"]
    assert len(nostre) == 29
    for riga in nostre:
        assert riga["ref"], "a repair without a citation of the resource"
        assert riga["suggest"] in ("(", ")")


# ── format characters: only the whitelist, and only Cf ───────────────────
FORMATO_ATTESI = ("​", "‌", "‍", "⁠", "﻿")


def test_i_caratteri_di_formato_sono_esattamente_i_cinque_dichiarati():
    from greek_corpus_pipeline.orthography import FORMAT_CHARS

    assert tuple(FORMAT_CHARS) == FORMATO_ATTESI


def test_ogni_carattere_di_formato_e_di_categoria_cf():
    from greek_corpus_pipeline.orthography import FORMAT_CHARS

    for carattere in FORMAT_CHARS:
        assert unicodedata.category(carattere) == "Cf", (
            f"U+{ord(carattere):04X} is not of category Cf")


def test_lo_spazio_unificatore_non_e_un_carattere_di_formato():
    """U+00A0 is Zs like U+0020: it belongs with the separators, not with the Cf."""
    from greek_corpus_pipeline.orthography import FORMAT_CHARS, SEPARATOR_CHARS

    assert unicodedata.category(" ") == "Zs"
    assert " " not in FORMAT_CHARS
    assert " " in SEPARATOR_CHARS


def _riga(campo: str, valore: str) -> pd.DataFrame:
    base = {"source_file": "x.xml", "document_id": "d", "sentence_index": 0,
            "sentence_id": "1", "token_index": 0, "token_id": "1",
            "form": "λόγος", "lemma": "λόγος", "postag": "n-s---mn-",
            "relation": "SBJ", "head": "0"}
    base[campo] = valore
    return pd.DataFrame([base])


@pytest.mark.parametrize("carattere", FORMATO_ATTESI,
                         ids=[f"U+{ord(c):04X}" for c in FORMATO_ATTESI])
@pytest.mark.parametrize("campo,regola", [("form", "invisible-char-form"),
                                          ("lemma", "invisible-char-lemma")])
def test_ogni_carattere_di_formato_viene_proposto_in_rimozione(carattere, campo, regola):
    """Greek + Cf + Greek → the same sequence without the Cf."""
    from greek_corpus_pipeline.orthography import check_invisible_characters

    valore = "λόγ" + carattere + "ος"
    trovate = check_invisible_characters(_riga(campo, valore))
    assert not trovate.empty, f"U+{ord(carattere):04X} is not flagged"
    riga = trovate.iloc[0]
    assert riga["rule_id"] == regola
    proposta = riga["suggested_form"] if campo == "form" else riga["suggested_lemma"]
    assert proposta == "λόγος", (
        f"the proposal for U+{ord(carattere):04X} is {proposta!r}, not “λόγος”")
    assert bool(riga["auto_correctable"])


@pytest.mark.parametrize("carattere,nome", [
    (" ", "U+00A0 NO-BREAK SPACE"),
    (" ", "U+0020 SPACE"),
    ("\t", "U+0009 TAB"),
    ("\n", "U+000A LINE FEED"),
])
@pytest.mark.parametrize("campo,regola", [("form", "whitespace-in-form"),
                                          ("lemma", "whitespace-in-lemma")])
def test_i_separatori_vanno_in_revisione_e_non_si_cancellano(carattere, nome, campo, regola):
    from greek_corpus_pipeline.orthography import check_invisible_characters

    trovate = check_invisible_characters(_riga(campo, "λόγ" + carattere + "ος"))
    assert not trovate.empty, f"{nome} is not flagged"
    riga = trovate.iloc[0]
    assert riga["rule_id"] == regola, (
        f"{nome} ends up in “{riga['rule_id']}”: it would be deleted automatically")
    assert not bool(riga["auto_correctable"]), f"{nome} turns out to be correctable by itself"


@pytest.mark.parametrize("carattere,nome", [
    ("́", "U+0301 COMBINING ACUTE ACCENT"),
    ("̓", "U+0313 COMBINING COMMA ABOVE"),
    ("·", "U+00B7 MIDDLE DOT"),
    ("’", "U+2019 RIGHT SINGLE QUOTATION MARK"),
    ("‐", "U+2010 HYPHEN"),
])
def test_nessun_carattere_fuori_dalla_whitelist_viene_toccato(carattere, nome):
    """A mark that is not in the whitelist must be neither removed nor flagged."""
    from greek_corpus_pipeline.orthography import check_invisible_characters

    trovate = check_invisible_characters(_riga("form", "λόγ" + carattere + "ος"))
    regole = set(trovate["rule_id"]) if not trovate.empty else set()
    assert "invisible-char-form" not in regole, (
        f"{nome} is treated as a format character")
