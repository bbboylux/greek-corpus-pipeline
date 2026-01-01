# -*- coding: utf-8 -*-
"""The gold standard corrected by the user: saving, exporting, comparing.

Every test here answers a question that the user really asks:
- is what I export my version or the original?
- if I have corrected nothing, does the program notice?
- if I save and reopen tomorrow, do I find my work again?
- how much does the judgement on a model change if I change the reference?
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from greek_corpus_pipeline.analysis import compute_token_diff
from greek_corpus_pipeline.gold import (
    BUNDLE_SUFFIX,
    export_gold_conllu,
    export_gold_csv,
    export_gold_xml,
    gold_state,
    load_gold_bundle,
    model_reference_table,
    read_gold_meta,
    read_manual_corrections,
    rescore_model,
    save_gold_bundle,
)


# ── the state of the gold ────────────────────────────────────────────────
def test_senza_correzioni_lo_stato_lo_dice(tokens):
    """Corrected corpus identical to the original: no correction."""
    stato = gold_state(tokens, tokens.copy(), pd.DataFrame())
    assert stato.changed_tokens == 0
    assert stato.manual_corrections == 0
    assert not stato.has_corrections
    assert stato.total_tokens == len(tokens)


def test_con_correzioni_lo_stato_le_conta(tokens, corrected, manual):
    stato = gold_state(tokens, corrected, manual)
    assert stato.changed_tokens == 2, "a lemma and a tag have changed"
    assert stato.manual_corrections == 2
    assert stato.has_corrections
    assert 0 < stato.changed_share < 1


def test_lo_stato_usa_il_diff_quando_c_e(tokens, corrected, manual):
    """The diff already computed is not recomputed: same result."""
    diff = compute_token_diff(tokens, corrected)
    stato = gold_state(tokens, corrected, manual, diff)
    assert stato.changed_tokens == len(diff) == 2


def test_correzioni_manuali_assenti_danno_tabella_vuota_ma_con_colonne(tmp_path):
    frame = read_manual_corrections(tmp_path)
    assert frame.empty
    assert "corrected_lemma" in frame.columns
    assert "corrected_postag" in frame.columns


# ── the three exports ────────────────────────────────────────────────────
def test_esportazione_xml_scrive_il_corpus_corretto(tmp_path, corrected):
    """The XML file must contain the corrected lemma, not the original one."""
    written = export_gold_xml(corrected, tmp_path / "xml")
    assert written, "no file written"
    testo = Path(written[0]).read_text(encoding="utf-8")
    assert 'lemma="στρατιώτης"' in testo
    assert 'lemma="στρατιώτης1"' not in testo, "the original was exported, not the gold"


def test_esportazione_csv_scrive_il_corpus_corretto(tmp_path, corrected):
    target = export_gold_csv(corrected, tmp_path / "gold.csv")
    frame = pd.read_csv(target)
    assert len(frame) == len(corrected)
    riga = frame.loc[frame["form"] == "στρατιῶται"].iloc[0]
    assert riga["lemma"] == "στρατιώτης"
    riga = frame.loc[frame["form"] == "ἄνδρες"].iloc[0]
    assert riga["postag"] == "n-p---mn-", "the corrected tag is not in the CSV"


def test_esportazione_csv_aggiunge_l_estensione(tmp_path, corrected):
    target = export_gold_csv(corrected, tmp_path / "senza_estensione")
    assert target.suffix == ".csv"


def test_esportazione_conllu_scrive_il_corpus_corretto(tmp_path, corrected):
    written = export_gold_conllu(corrected, tmp_path / "gold.conllu",
                                 corpus_name="test")
    testo = Path(written[0]).read_text(encoding="utf-8")
    assert "στρατιώτης" in testo
    assert "στρατιώτης1" not in testo, "the original was exported, not the gold"


def test_le_esportazioni_non_toccano_l_originale(tmp_path, tokens, corrected):
    """Exporting the gold must not modify the table of the original corpus."""
    prima = tokens.copy()
    export_gold_xml(corrected, tmp_path / "xml")
    export_gold_csv(corrected, tmp_path / "g.csv")
    export_gold_conllu(corrected, tmp_path / "g.conllu")
    pd.testing.assert_frame_equal(tokens, prima)


# ── saving and resuming ──────────────────────────────────────────────────
def test_salva_e_ricarica_senza_perdere_niente(tmp_path, tokens, corrected, manual):
    diff = compute_token_diff(tokens, corrected)
    bundle = save_gold_bundle(tmp_path / "mio_gold", corrected, manual, diff,
                              corpus_name="test", run_id="run-1")
    assert bundle.suffix == BUNDLE_SUFFIX
    assert bundle.exists()

    meta = read_gold_meta(bundle)
    assert meta["corpus_name"] == "test"
    assert meta["manual_corrections"] == 2
    assert meta["changed_tokens"] == 2

    destinazione = tmp_path / "altra-esecuzione"
    riletto = load_gold_bundle(bundle, destinazione)
    assert riletto["run_id"] == "run-1"

    ripreso = pd.read_parquet(destinazione / "corrected_tokens.parquet")
    assert len(ripreso) == len(corrected)
    riga = ripreso.loc[ripreso["form"] == "στρατιῶται"].iloc[0]
    assert riga["lemma"] == "στρατιώτης", "the corrected lemma was lost"

    decisioni = read_manual_corrections(destinazione)
    assert len(decisioni) == 2, "the decisions were not carried over"


def test_ricaricare_non_tocca_il_corpus_originale(tmp_path, tokens, corrected, manual):
    """The reloaded gold must not overwrite tokens.parquet."""
    esecuzione = tmp_path / "run"
    esecuzione.mkdir()
    tokens.to_parquet(esecuzione / "tokens.parquet", index=False)
    impronta = (esecuzione / "tokens.parquet").read_bytes()

    bundle = save_gold_bundle(tmp_path / "g", corrected, manual)
    load_gold_bundle(bundle, esecuzione)

    assert (esecuzione / "tokens.parquet").read_bytes() == impronta
    assert (esecuzione / "corrected_tokens.parquet").exists()


def test_salvare_un_gold_vuoto_e_un_errore(tmp_path, manual):
    with pytest.raises(ValueError, match="no revised corpus"):
        save_gold_bundle(tmp_path / "g", pd.DataFrame(), manual)


def test_un_file_qualsiasi_non_e_un_gold(tmp_path):
    import zipfile
    finto = tmp_path / "finto.gcpgold"
    with zipfile.ZipFile(finto, "w") as archive:
        archive.writestr("qualcosa.txt", "niente")
    with pytest.raises(ValueError, match="bundle produced by GCP"):
        read_gold_meta(finto)


# ── the models against the two references ────────────────────────────────
def test_riconteggio_contro_l_originale(tokens, stanza_like):
    esito = rescore_model(tokens, stanza_like, "stanza")
    assert esito["aligned_tokens"] == len(tokens)
    # the fake model gets one lemma and one label wrong with respect to the original
    assert esito["lemma_matches"] == len(tokens) - 1
    assert esito["postag_matches"] == len(tokens) - 1


def test_riconteggio_contro_il_gold(corrected, stanza_like):
    """Against the corrected corpus the fake model agrees on everything."""
    esito = rescore_model(corrected, stanza_like, "stanza")
    assert esito["lemma_matches"] == len(corrected)
    assert esito["postag_matches"] == len(corrected)
    assert esito["lemma_match_rate"] == 100.0


def test_la_tabella_di_confronto_mostra_la_differenza(tokens, corrected, stanza_like):
    tabella = model_reference_table(tokens, corrected, stanza_like, None)
    assert set(tabella["modello"]) == {"Stanza"}
    assert set(tabella["campo"]) == {"lemma", "etichetta"}
    for _, riga in tabella.iterrows():
        assert riga["accordo con il gold %"] > riga["accordo con l'originale %"]
        assert riga["differenza"] > 0


def test_senza_modelli_la_tabella_e_vuota(tokens, corrected):
    assert model_reference_table(tokens, corrected, None, None).empty
    assert model_reference_table(tokens, corrected, pd.DataFrame(), pd.DataFrame()).empty


def test_riconteggio_senza_le_colonne_del_modello(tokens):
    """A table without lemma_stanza must not blow up."""
    esito = rescore_model(tokens, tokens, "stanza")
    assert esito["aligned_tokens"] == 0
    assert esito["lemma_match_rate"] is None


def test_il_riconteggio_non_riesegue_il_modello(tokens, corrected, stanza_like, monkeypatch):
    """No call to Stanza: the comparison uses what was already saved."""
    import greek_corpus_pipeline.analyzers as analyzers

    def esplodi(*args, **kwargs):
        raise AssertionError("il modello è stato rieseguito")

    monkeypatch.setattr(analyzers, "run_stanza_analysis", esplodi)
    monkeypatch.setattr(analyzers, "run_udpipe_analysis", esplodi)
    tabella = model_reference_table(tokens, corrected, stanza_like, None)
    assert not tabella.empty
