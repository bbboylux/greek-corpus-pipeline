# -*- coding: utf-8 -*-
"""The correction of the form and the conversion of the corpus to NFC.

Six automatic checks out of eight propose a new form: the elision apostrophe written
with a breathing, the final sigma in the middle of a word, Latin letters inside a Greek
word, the different encodings of the apostrophe, the Unicode decomposition of the single
token and that of the whole corpus.  The proposal shown on screen must also reach the
exported corpus: a function that applied the corrections looking only at label and lemma
would lose it.  These tests keep that road open.
"""
from __future__ import annotations

import unicodedata

import pandas as pd
import pytest


def _finding(document_id, sentence_id, token_id, rule_id, **campi):
    riga = {"document_id": document_id, "sentence_id": sentence_id,
            "token_id": token_id, "rule_id": rule_id, "auto_correctable": True}
    riga.update(campi)
    return riga


# ── The proposed form reaches the corpus ───────────────────────────────

def test_la_forma_proposta_viene_applicata(tokens):
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    proposte = pd.DataFrame([
        _finding("test-doc", "1", 2, "apostrophe-mixed", suggested_form="πόλινʼ"),
    ])
    risultato = apply_suggested_corrections(
        tokens, pd.DataFrame(), pd.DataFrame(),
        enabled_rule_ids={"apostrophe-mixed"}, form_findings=proposte)
    riga = risultato.loc[risultato["token_id"] == 2].iloc[0]
    assert riga["form"] == "πόλινʼ"
    assert bool(riga["form_corrected"]) is True
    assert "form->" in riga["correction_log"]


def test_una_regola_spenta_non_cambia_la_forma(tokens):
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    proposte = pd.DataFrame([
        _finding("test-doc", "1", 2, "apostrophe-mixed", suggested_form="πόλινʼ"),
    ])
    risultato = apply_suggested_corrections(
        tokens, pd.DataFrame(), pd.DataFrame(),
        enabled_rule_ids=set(), form_findings=proposte)
    assert list(risultato["form"]) == list(tokens["form"])
    assert not risultato["form_corrected"].any()


def test_la_forma_non_tocca_il_lemma(tokens):
    """Whoever changes the writing of a word does not change the word."""
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    proposte = pd.DataFrame([
        _finding("test-doc", "1", 2, "final-sigma-inside", suggested_form="πόλισν"),
    ])
    risultato = apply_suggested_corrections(
        tokens, pd.DataFrame(), pd.DataFrame(),
        enabled_rule_ids={"final-sigma-inside"}, form_findings=proposte)
    assert list(risultato["lemma"]) == list(tokens["lemma"])
    assert not risultato["lemma_corrected"].any()


# ── Two proposals on the same token combine ────────────────────────────

def test_due_proposte_sullo_stesso_token_si_compongono(tokens):
    """δεξιώματ’ has an apostrophe to be made uniform and an encoding to be composed.

    The two proposals are each computed on the starting form, and whoever proposes the
    composition does not know that the apostrophe will change.  The character rule wins,
    and the composition is redone on the result: so the token receives both corrections
    instead of one only, and the result does not depend on the order in which the
    families ran.
    """
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    decomposta = unicodedata.normalize("NFD", "δεξιώματ") + "’"
    frame = tokens.copy()
    frame.loc[frame["token_id"] == 2, "form"] = decomposta
    proposte = pd.DataFrame([
        _finding("test-doc", "1", 2, "apostrophe-mixed",
                 suggested_form=decomposta.replace("’", "ʼ")),
        _finding("test-doc", "1", 2, "unicode-not-nfc",
                 suggested_form=unicodedata.normalize("NFC", decomposta)),
    ])
    risultato = apply_suggested_corrections(
        frame, pd.DataFrame(), pd.DataFrame(),
        enabled_rule_ids={"apostrophe-mixed", "unicode-not-nfc"},
        form_findings=proposte)
    forma = risultato.loc[risultato["token_id"] == 2, "form"].iloc[0]
    assert forma == unicodedata.normalize("NFC", "δεξιώματ") + "ʼ"
    assert unicodedata.normalize("NFC", forma) == forma


def test_l_ordine_delle_famiglie_non_cambia_il_risultato(tokens):
    from greek_corpus_pipeline.analysis import apply_suggested_corrections
    decomposta = unicodedata.normalize("NFD", "δεξιώματ") + "’"
    frame = tokens.copy()
    frame.loc[frame["token_id"] == 2, "form"] = decomposta
    righe = [
        _finding("test-doc", "1", 2, "unicode-not-nfc",
                 suggested_form=unicodedata.normalize("NFC", decomposta)),
        _finding("test-doc", "1", 2, "apostrophe-mixed",
                 suggested_form=decomposta.replace("’", "ʼ")),
    ]
    abilitate = {"apostrophe-mixed", "unicode-not-nfc"}
    primo = apply_suggested_corrections(frame, pd.DataFrame(), pd.DataFrame(),
                                        enabled_rule_ids=abilitate,
                                        form_findings=pd.DataFrame(righe))
    secondo = apply_suggested_corrections(frame, pd.DataFrame(), pd.DataFrame(),
                                          enabled_rule_ids=abilitate,
                                          form_findings=pd.DataFrame(righe[::-1]))
    assert list(primo["form"]) == list(secondo["form"])


# ── The conversion of the whole corpus ─────────────────────────────────

def test_la_conversione_nfc_converte_tutto_e_non_lascia_niente(tokens):
    from greek_corpus_pipeline.analysis import normalise_corpus_to_nfc
    frame = tokens.copy()
    frame["form"] = frame["form"].map(lambda v: unicodedata.normalize("NFD", v))
    frame["lemma"] = frame["lemma"].map(lambda v: unicodedata.normalize("NFD", v))
    convertito, quanti = normalise_corpus_to_nfc(frame)
    assert quanti > 0
    resta = convertito["form"].map(
        lambda v: unicodedata.normalize("NFC", v) != v).sum()
    assert resta == 0
    assert convertito["lemma"].map(
        lambda v: unicodedata.normalize("NFC", v) != v).sum() == 0


def test_la_conversione_nfc_non_cambia_una_lettera(tokens):
    """The encoding changes, not the text: at NFD the two corpora coincide."""
    from greek_corpus_pipeline.analysis import normalise_corpus_to_nfc
    frame = tokens.copy()
    frame["form"] = frame["form"].map(lambda v: unicodedata.normalize("NFD", v))
    convertito, _ = normalise_corpus_to_nfc(frame)
    prima = frame["form"].map(lambda v: unicodedata.normalize("NFD", v))
    dopo = convertito["form"].map(lambda v: unicodedata.normalize("NFD", v))
    assert list(prima) == list(dopo)


def test_la_conversione_nfc_su_un_corpus_gia_composto_non_fa_niente(tokens):
    from greek_corpus_pipeline.analysis import normalise_corpus_to_nfc
    convertito, quanti = normalise_corpus_to_nfc(tokens)
    assert quanti == 0
    assert list(convertito["form"]) == list(tokens["form"])


def test_la_conversione_nfc_segna_i_record_toccati(tokens):
    from greek_corpus_pipeline.analysis import normalise_corpus_to_nfc
    frame = tokens.copy()
    frame["form"] = frame["form"].map(lambda v: unicodedata.normalize("NFD", v))
    convertito, quanti = normalise_corpus_to_nfc(frame)
    assert int(convertito["form_corrected"].sum()) == quanti
    assert convertito.loc[convertito["form_corrected"], "correction_log"] \
        .str.contains("nfc").all()


def test_la_conversione_e_stabile(tokens):
    """Applied twice it gives the same result as the first time."""
    from greek_corpus_pipeline.analysis import normalise_corpus_to_nfc
    frame = tokens.copy()
    frame["form"] = frame["form"].map(lambda v: unicodedata.normalize("NFD", v))
    una, _ = normalise_corpus_to_nfc(frame)
    due, quanti = normalise_corpus_to_nfc(una)
    assert quanti == 0
    assert list(una["form"]) == list(due["form"])


# ── The check declares the action, and the action exists ───────────────

def test_il_controllo_sul_corpus_e_dichiarato():
    from greek_corpus_pipeline.proposte import AZIONI_SUL_CORPUS
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    assert "corpus-not-nfc" in AZIONI_SUL_CORPUS
    for regola in AZIONI_SUL_CORPUS:
        assert regola in RULE_CATALOG
        assert RULE_CATALOG[regola]["treatment"] == "automatica"


def test_un_controllo_automatico_o_propone_o_agisce_sul_corpus():
    """No automatic treatment is left without effect.

    It is the case of “Corpus predominantly in NFD”: a check that declares itself
    automatic must apply something.
    """
    from greek_corpus_pipeline.proposte import AZIONI_SUL_CORPUS
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    import greek_corpus_pipeline.analysis as analisi
    automatiche = {r for r, d in RULE_CATALOG.items()
                   if d["treatment"] == "automatica"}
    for regola in automatiche & AZIONI_SUL_CORPUS:
        assert hasattr(analisi, "normalise_corpus_to_nfc")


def test_l_azione_sul_corpus_gira_nel_flusso_delle_correzioni():
    """The call is in the worker, not only in the library."""
    from pathlib import Path
    sorgente = Path(__file__).resolve().parent.parent / "gui_qt" / "workers.py"
    testo = sorgente.read_text(encoding="utf-8")
    assert "AZIONI_SUL_CORPUS" in testo
    assert "normalise_corpus_to_nfc" in testo


# ── The before/after comparison sees the form ──────────────────────────

def test_il_confronto_vede_la_forma_cambiata(tokens):
    from greek_corpus_pipeline.analysis import compute_token_diff
    dopo = tokens.copy()
    dopo.loc[(dopo["sentence_id"] == "1") & (dopo["token_id"] == 2), "form"] = "πόλινʼ"
    differenza = compute_token_diff(tokens, dopo)
    assert len(differenza) == 1
    assert differenza["form_original"].iloc[0] == "πόλιν"
    assert differenza["form_corrected"].iloc[0] == "πόλινʼ"


def test_due_celle_vuote_non_sono_un_cambiamento(tokens):
    """NaN != NaN would give “changed” for every record without a lemma."""
    from greek_corpus_pipeline.analysis import compute_token_diff
    prima = tokens.copy()
    prima["lemma"] = pd.NA
    dopo = prima.copy()
    assert compute_token_diff(prima, dopo).empty


# ── The text shown does not promise what the program does not do ───────

def test_nessun_controllo_manuale_promette_una_correzione(tokens):
    """A manual check must not write “Proposed correction”.

    Three checks are manual and must not promise one: the number at the end of the
    lemma, the competing graphic variant and the lemma that is rare for the form. Their
    text must follow their treatment, otherwise a reader sees a proposal on screen and
    no proposal in the column.
    """
    import re
    from pathlib import Path
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    sorgenti = (Path(__file__).resolve().parent.parent
                / "src" / "greek_corpus_pipeline")
    manuali = {r for r, d in RULE_CATALOG.items() if d["treatment"] == "manuale"}
    colpevoli = []
    for modulo in sorgenti.glob("*.py"):
        testo = modulo.read_text(encoding="utf-8")
        for regola in manuali:
            # the string of the identifier and the 40 lines that follow it
            for m in re.finditer(re.escape(f'"{regola}"'), testo):
                # the block stops where the call that produces it closes, otherwise it
                # spills into the text of the next check
                blocco = testo[m.end():m.end() + 2000]
                for fine in ("))", "\n    #", "\n\n"):
                    blocco = blocco.split(fine)[0]
                if re.search(r"(?<!Nessuna )[Cc]orrezione proposta", blocco):
                    colpevoli.append((modulo.name, regola))
    assert colpevoli == [], f"manual checks that promise a correction: {colpevoli}"
