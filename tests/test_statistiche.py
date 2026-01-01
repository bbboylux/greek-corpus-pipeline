# -*- coding: utf-8 -*-
"""The Statistics page: what it shows, and what is not invented.

Three things are verified, and they are three different things: that the statistics that
are offered give the right number with the right denominator, that the charts and the
figures are those that the program declares, and that the metadata are not invented when
the corpus does not carry them.
"""
from __future__ import annotations

import unicodedata

import pandas as pd
import pytest


# ── the statistics offered ────────────────────────────────────────────────
def test_le_distribuzioni_usano_il_denominatore_pertinente(tokens):
    """The moods are counted on the verbs, not on all the words of the corpus."""
    from greek_corpus_pipeline import stats

    modi = stats.slot_distribution(tokens, 4, restrict_pos={"v"})
    assert not modi.empty
    # The two sentences have two finite verbs and no other form with a mood.
    assert int(modi["occorrenze"].sum()) == 2
    assert abs(float(modi["%"].sum()) - 100.0) < 0.01

    casi = stats.slot_distribution(tokens, 7, restrict_pos={"n", "a", "p", "l", "m"})
    # No verb enters the count of the cases.
    assert int(casi["occorrenze"].sum()) == 5


def test_il_riassunto_sintattico_dichiara_le_frasi_lasciate_fuori(tokens):
    from greek_corpus_pipeline import stats

    riassunto = stats.syntax_summary(tokens, None)
    assert riassunto["frasi nel gruppo"] == 2
    assert riassunto["relazioni distinte"] >= 4
    assert "ragione dell'esclusione" in riassunto
    assert riassunto["frasi con archi"] + riassunto["frasi senza archi"] \
        == riassunto["frasi nel gruppo"]


def test_il_riassunto_sintattico_conta_sui_legami_utilizzabili(tokens):
    """Numerator and denominator come from the same canonical set.

    The denominator is not the number of rows of the arcs table, which is a second
    population of the same thing, but the ``analyzable_links``: the active records whose
    head exists as a record of the same sentence.  Projectivity is read in the table,
    and the share of links really looked at is declared separately.
    """
    from greek_corpus_pipeline import stats
    from greek_corpus_pipeline.units import analyzable_link_mask

    utilizzabili = int(analyzable_link_mask(tokens, within=tokens).sum())
    assert utilizzabili > 0

    # One arc for every usable link, with the keys needed to recognise it, plus one that
    # belongs to another document.
    maschera = analyzable_link_mask(tokens, within=tokens).to_numpy()
    veri = tokens[maschera]
    archi = pd.DataFrame({
        "source_file": list(veri["source_file"]) + ["altro.xml"],
        "document_id": list(veri["document_id"]) + ["altro-doc"],
        "sentence_index": list(veri["sentence_index"]) + [1],
        "token_id": list(veri["token_id"]) + [1],
        "non_projective": [True] + [False] * (len(veri) - 1) + [True],
    })
    riassunto = stats.syntax_summary(tokens, archi)
    assert riassunto["legami utilizzabili"] == utilizzabili
    assert riassunto["legami misurati"] == utilizzabili, \
        "the arc of the other document entered the count"
    assert riassunto["legami non proiettivi"] == 1
    assert riassunto["% legami non proiettivi"] == round(100 / utilizzabili, 1)


def test_un_arco_che_non_e_un_legame_utilizzabile_non_entra(tokens):
    """The real case: on Pedalion, 436 arcs of this kind are not usable links.

    They are ``G?`` lacunae and other records that the inclusion filters remove.
    Counting them would inflate the denominator.
    """
    from greek_corpus_pipeline import stats

    archi = pd.DataFrame({
        "source_file": ["test-doc.xml"], "document_id": ["test-doc"],
        "sentence_index": [1], "token_id": [999],       # token that does not exist
        "non_projective": [True],
    })
    riassunto = stats.syntax_summary(tokens, archi)
    assert riassunto["legami misurati"] == 0
    assert riassunto["legami non proiettivi"] == 0


def test_la_copertura_si_dichiara(tokens):
    """A usable link about which the table says nothing stays in the count."""
    from greek_corpus_pipeline import stats
    from greek_corpus_pipeline.units import analyzable_link_mask

    veri = tokens[analyzable_link_mask(tokens, within=tokens).to_numpy()]
    # The table covers only one link out of all the usable ones.
    archi = pd.DataFrame({
        "source_file": [veri["source_file"].iloc[0]],
        "document_id": [veri["document_id"].iloc[0]],
        "sentence_index": [veri["sentence_index"].iloc[0]],
        "token_id": [veri["token_id"].iloc[0]],
        "non_projective": [True],
    })
    riassunto = stats.syntax_summary(tokens, archi)
    assert riassunto["legami utilizzabili"] > riassunto["legami misurati"] == 1
    # the denominator stays the canonical unit, not the measured links
    assert riassunto["% legami non proiettivi"] == round(
        100 / riassunto["legami utilizzabili"], 1)


def test_il_riassunto_non_costruisce_una_seconda_popolazione_di_archi():
    """The syntactic universe is one only, and it is asked of ``analyzable_link_mask``."""
    import inspect
    from greek_corpus_pipeline import stats

    sorgente = inspect.getsource(stats.syntax_summary)
    assert "analyzable_link_mask" in sorgente
    assert "sentence_key" in sorgente
    assert "len(miei)" not in sorgente


def test_la_lista_di_frequenza_porta_le_colonne_richieste(tokens):
    from greek_corpus_pipeline import stats

    tabella = stats.frequency_list(tokens, field="lemma")
    for colonna in ("occorrenze", "per 10.000", "%", "% cumulativa", "rango"):
        assert colonna in tabella.columns, colonna
    assert tabella["occorrenze"].iloc[0] >= tabella["occorrenze"].iloc[-1]


def test_il_profilo_di_una_parola_guarda_soltanto_quel_lemma(tokens):
    from greek_corpus_pipeline import stats

    profilo = stats.lemma_profile(tokens, "ὁ")
    assert profilo["occorrenze"] == 3
    assert set(profilo["forme"]["forma"]) == {"τὴν", "οἱ"}
    assert not profilo["relazioni"].empty
    assert not profilo["documenti"].empty
    assert stats.lemma_profile(tokens, "ἵππος")["occorrenze"] == 0


# ── the stopwords ─────────────────────────────────────────────────────────
def test_le_parole_funzionali_escono_davvero(tokens):
    from greek_corpus_pipeline import stats

    parole = stats._content(tokens)
    filtrate = stats.apply_stopword_profile(parole, "senza parole funzionali")
    lemmi = set(filtrate["lemma"].astype(str))
    assert "ὁ" not in lemmi and "καί" not in lemmi
    assert "πόλις" in lemmi and "στρατιώτης1" in lemmi


def test_le_stopword_si_confrontano_sul_lemma_normalizzato(tokens):
    """A corpus in NFD must not escape the filter: a decomposed ὁ is always ὁ."""
    from greek_corpus_pipeline import stats

    decomposto = tokens.copy()
    decomposto["lemma"] = decomposto["lemma"].astype(str).map(
        lambda v: unicodedata.normalize("NFD", v))
    filtrate = stats.apply_stopword_profile(
        stats._content(decomposto), "senza parole funzionali")
    normalizzati = {unicodedata.normalize("NFC", v)
                    for v in filtrate["lemma"].astype(str)}
    assert "ὁ" not in normalizzati


def test_la_lista_personalizzata_aggiunge_e_toglie(tokens):
    from greek_corpus_pipeline import stats

    parole = stats._content(tokens)
    con_aggiunta = stats.apply_stopword_profile(
        parole, "lista personalizzata", extra=["πόλις"])
    assert "πόλις" not in set(con_aggiunta["lemma"].astype(str))

    con_rimozione = stats.apply_stopword_profile(
        parole, "lista personalizzata", remove=["ὁ"])
    assert "ὁ" in set(con_rimozione["lemma"].astype(str))

    elenco = stats.stopword_list(extra=["πόλις"], remove=["ὁ"])
    assert "πόλις" in elenco and "ὁ" not in elenco


def test_il_rapporto_dice_quali_lemmi_sono_usciti_e_perché(tokens):
    from greek_corpus_pipeline import stats

    parole = stats._content(tokens)
    rapporto = stats.stopword_profile_report(parole, "senza parole funzionali")
    assert rapporto["token_esclusi"] > 0
    tabella = rapporto["lemmi_esclusi"]
    assert set(tabella.columns) == {"lemma", "ragione", "occorrenze"}
    assert "ὁ" in set(tabella["lemma"].astype(str))
    assert set(tabella["ragione"]) <= {"parte del discorso",
                                       "elenco dei lemmi grammaticali",
                                       "non è una parola"}


def test_il_filtro_adattivo_sposta_e_non_cancella():
    """A word that is frequent everywhere goes down; one that is frequent and concentrated
    goes up."""
    from greek_corpus_pipeline import stats

    righe = []
    for documento in range(10):
        for _ in range(10):
            righe.append({"document_id": f"d{documento}", "lemma": "εἰμί",
                          "form": "ἐστί", "postag": "v3spia---",
                          "source_file": "f", "sentence_index": 1,
                          "sentence_id": "1", "token_id": 1, "head": 0,
                          "relation": "PRED"})
        if documento == 0:
            for _ in range(60):
                righe.append({"document_id": "d0", "lemma": "τριήρης",
                              "form": "τριήρης", "postag": "n-s---fn-",
                              "source_file": "f", "sentence_index": 1,
                              "sentence_id": "1", "token_id": 2, "head": 0,
                              "relation": "SBJ"})
    frame = pd.DataFrame(righe)
    tabella, usato = stats.content_words_ranked(frame)
    assert usato is True
    lemmi = list(tabella["lemma"])
    assert lemmi.index("τριήρης") < lemmi.index("εἰμί")
    assert "εἰμί" in lemmi, "the frequent word is moved, not removed"


def test_con_un_solo_documento_il_peso_tfidf_non_si_usa(tokens):
    from greek_corpus_pipeline import stats

    _tabella, usato = stats.content_words_ranked(tokens)
    assert usato is False


# ── the charts ────────────────────────────────────────────────────────────
def test_la_pagina_grafici_ha_sei_voci():
    from gui_qt.pages.charts_page import CHARTS

    chiavi = [chiave for chiave, _ in CHARTS]
    assert chiavi == ["famiglia", "livello", "regola", "densita",
                      "accordo", "treway"]


def test_le_figure_sono_numerate_senza_buchi():
    """The figures are numbered without gaps."""
    from pathlib import Path

    sorgente = Path(__file__).resolve().parent.parent
    testo = (sorgente / "src" / "greek_corpus_pipeline" / "figures.py").read_text(encoding="utf-8")
    import re
    numeri = sorted({int(n) for n in re.findall(r'_emit\("(\d\d)-', testo)})
    assert numeri == list(range(1, len(numeri) + 1)), numeri


def test_ogni_figura_esportata_ha_la_sua_didascalia():
    """Every figure that the export writes has a caption, in both languages, and no
    caption is left without its figure."""
    import re
    from pathlib import Path
    from greek_corpus_pipeline import figures
    from gui_qt.i18n import _STRINGS

    sorgente = Path(__file__).resolve().parent.parent
    testo = (sorgente / "src" / "greek_corpus_pipeline" / "figures.py").read_text(encoding="utf-8")
    emesse = set(re.findall(r'_emit\("(\d\d-[^"]+)"', testo))
    assert len(emesse) == 15
    assert set(figures.CAPTIONS) == emesse
    assert {k[len("figcap."):] for k in _STRINGS if k.startswith("figcap.")} == emesse


def test_i_file_di_un_giro_che_altri_strumenti_leggono_hanno_nomi_fissi():
    """The artifacts that other tools read have fixed names: they are a contract."""
    from greek_corpus_pipeline import storage

    assert set(storage.ARTIFACT_FILENAMES) == {
        "tokens", "findings", "arcs", "postag_findings", "lemma_findings",
        "corrected_tokens", "token_diff", "lemma_inventory", "spelling_variation",
        "stanza_tokens", "stanza_comparison", "udpipe_tokens", "udpipe_comparison"}
    for chiave, nome in storage.ARTIFACT_FILENAMES.items():
        assert nome == f"{chiave}.parquet", chiave


# ── metadata are not invented ─────────────────────────────────────────────
def test_le_dimensioni_compaiono_solo_con_i_metadati(tokens):
    """The test corpus has no author, work, period, genre or dialect."""
    from gui_qt.pages.stats_page import DIMENSIONI

    colonne = set(tokens.columns)
    disponibili = [chiave for colonna, chiave in DIMENSIONI
                   if not colonna or colonna in colonne]
    assert "stats.dim.corpus" in disponibili
    assert "stats.dim.documento" in disponibili
    for assente in ("stats.dim.autore", "stats.dim.opera", "stats.dim.periodo",
                    "stats.dim.genere", "stats.dim.dialetto"):
        assert assente not in disponibili, assente


def test_ogni_selezione_usa_soltanto_i_record_del_gruppo(tokens):
    """The totals of the groups must add up to the total of the corpus."""
    from greek_corpus_pipeline import stats

    frame = tokens.copy()
    frame.loc[frame["sentence_index"] == 1, "document_id"] = "a"
    frame.loc[frame["sentence_index"] != 1, "document_id"] = "b"
    intero = int(stats.slot_distribution(frame, 0)["occorrenze"].sum())
    per_gruppo = 0
    for nome in ("a", "b"):
        parte = frame[frame["document_id"] == nome]
        tabella = stats.slot_distribution(parte, 0)
        per_gruppo += int(tabella["occorrenze"].sum()) if not tabella.empty else 0
    assert per_gruppo == intero
