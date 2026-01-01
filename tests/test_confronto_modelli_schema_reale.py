# -*- coding: utf-8 -*-
"""The comparison between the models, on the schema the program really writes.

These tests guard against a failure of the card “Model disagreements”, which
would open and die with

    KeyError: 'corpus'

The cause would not lie in the card.  ``modelcmp`` must not look for columns
called ``postag_reference``, ``postag_stanza`` and ``postag_udpipe``: those
names have never existed in a file produced by the program.  The table saved
by ``model_eval.evaluate_predictions`` carries the value of the corpus under
``postag`` and the prediction of the model under ``postag_modello``.  A search
for the wrong names falls back on the bare name, and the three columns —
corpus, Stanza, UDPipe — become the same one.

A test that builds the tables by hand, with the names that the module
expects, cannot see this.  Here the table has **exactly** the columns of the
real files, in the same order, and the first thing verified is precisely
that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from greek_corpus_pipeline import modelcmp  # noqa: E402

#: The columns of `stanza_comparison.parquet`, copied from a real file produced
#: by GCP 3.1.0.  If the program changes this schema, this list must change with
#: it — which is the point of the test.
COLONNE_REALI = [
    "corpus", "analyzer", "source_file", "document_id", "sentence_index",
    "sentence_id", "token_index", "token_id", "head", "ref", "form", "lemma",
    "postag", "relation", "artificial", "annotation_mode", "tlg_author",
    "tlg_work", "cts_urn", "_model_form", "_sentenza", "_posizione",
    "lemma_modello", "postag_modello", "lemma_normalizzato",
    "lemma_modello_normalizzato", "accordo_lemma", "accordo_postag",
    "eleggibile_lemma", "eleggibile_postag",
]


def _tabella(previsioni_postag, previsioni_lemma=None, *, nome="gorman"):
    """A comparison table with the real schema and the given predictions."""
    n = len(previsioni_postag)
    corpus_tag = ["n-s---mn-", "v3spia---", "d--------", "c--------"][:n]
    corpus_lemma = ["θεός", "λέγω", "οὕτως", "καί"][:n]
    previsioni_lemma = previsioni_lemma or corpus_lemma
    dati = {
        "corpus": [nome] * n, "analyzer": ["corpus"] * n,
        "source_file": ["a.xml"] * n, "document_id": ["a"] * n,
        "sentence_index": [1] * n, "sentence_id": [1] * n,
        "token_index": list(range(1, n + 1)), "token_id": list(range(1, n + 1)),
        "head": [0] * n, "ref": [None] * n,
        "form": ["θεός", "λέγει", "οὕτως", "καὶ"][:n],
        "lemma": corpus_lemma, "postag": corpus_tag,
        "relation": ["SBJ", "PRED", "ADV", "COORD"][:n],
        "artificial": [None] * n, "annotation_mode": [None] * n,
        "tlg_author": ["tlg0026"] * n, "tlg_work": ["tlg001"] * n,
        "cts_urn": ["x"] * n, "_model_form": ["θεός", "λέγει", "οὕτως", "καὶ"][:n],
        "_sentenza": ["a.xml␟a␟1"] * n, "_posizione": list(range(n)),
        "lemma_modello": previsioni_lemma, "postag_modello": previsioni_postag,
        "lemma_normalizzato": corpus_lemma,
        "lemma_modello_normalizzato": previsioni_lemma,
        "accordo_lemma": [a == b for a, b in zip(corpus_lemma, previsioni_lemma)],
        "accordo_postag": [a == b for a, b in zip(corpus_tag, previsioni_postag)],
        "eleggibile_lemma": [True] * n, "eleggibile_postag": [True] * n,
    }
    return pd.DataFrame(dati, columns=COLONNE_REALI)


# ── the schema, first of all ─────────────────────────────────────────────────

def test_il_modulo_sa_dove_stanno_le_due_colonne():
    """The corpus under the bare name, the model under ``_modello``."""
    tabella = _tabella(["n-s---mn-", "v3spia---"])
    assert modelcmp._colonna_corpus(tabella, "postag") == "postag"
    assert modelcmp._colonna_modello(tabella, "postag") == "postag_modello"
    assert modelcmp._colonna_corpus(tabella, "lemma") == "lemma"
    assert modelcmp._colonna_modello(tabella, "lemma") == "lemma_modello"


def test_le_due_colonne_non_sono_mai_la_stessa():
    """The defect, in its shortest form.

    If the column of the corpus and that of the model resolve to the same name, every
    comparison that follows compares the corpus with itself.
    """
    tabella = _tabella(["n-s---mn-", "v3spia---"])
    for campo in ("postag", "lemma"):
        assert modelcmp._colonna_corpus(tabella, campo) != modelcmp._colonna_modello(tabella, campo)


# ── the three-way comparison ─────────────────────────────────────────────────

def test_il_confronto_a_tre_vie_non_solleva_sullo_schema_reale():
    """This is the case that raised `KeyError: 'corpus'`."""
    stanza = _tabella(["n-s---mn-", "v3spia---", "d--------", "c--------"])
    udpipe = _tabella(["n-s---mn-", "v3spia---", "c--------", "c--------"])
    riassunto, dettaglio = modelcmp.three_way_agreement(stanza, udpipe)
    assert not riassunto.empty
    assert set(dettaglio.columns) >= {"corpus", "stanza", "udpipe", "esito"}


def test_le_quattro_categorie_contano_quello_che_dicono():
    corpus_tag = ["n-s---mn-", "v3spia---", "d--------", "c--------"]
    stanza = _tabella(["n-s---mn-",   # all three agree
                       "v3spia---",   # corpus and Stanza against UDPipe
                       "c--------",   # the two models against the corpus
                       "a-s---mn-"])  # all three different
    udpipe = _tabella(["n-s---mn-", "v1spia---", "c--------", "l-s---mn-"])
    riassunto, _ = modelcmp.three_way_agreement(stanza, udpipe)
    conteggi = dict(zip(riassunto["esito"], riassunto["token"]))
    assert conteggi["tutti e tre d'accordo"] == 1
    assert conteggi["corpus e Stanza contro UDPipe"] == 1
    assert conteggi["i due modelli contro il corpus"] == 1
    assert conteggi["tutti e tre diversi"] == 1
    assert conteggi["TOTALE allineati"] == 4
    assert stanza.columns.tolist() == COLONNE_REALI, "the input table was modified"


def test_la_colonna_corpus_del_file_non_confonde_il_confronto():
    """The real table already has a column called ``corpus``.

    It carries the name of the corpus — “gorman” — and not the annotated value.
    The comparison creates one with the same name for the reference value, and
    the two must not overlap.
    """
    stanza = _tabella(["n-s---mn-", "c--------"])
    udpipe = _tabella(["n-s---mn-", "c--------"])
    assert "corpus" in stanza.columns and set(stanza["corpus"]) == {"gorman"}
    _riassunto, dettaglio = modelcmp.three_way_agreement(stanza, udpipe)
    assert not dettaglio.empty
    # The “corpus” column of the result carries the annotated label, not the name of the
    # corpus: if it carried “gorman” the two columns would have overlapped.
    assert "gorman" not in set(dettaglio["corpus"])
    assert set(dettaglio["corpus"]) <= set(stanza["postag"])


def test_i_due_modelli_contro_il_corpus_si_raggruppano_per_sostituzione():
    stanza = _tabella(["c--------", "c--------", "d--------", "c--------"])
    udpipe = _tabella(["c--------", "c--------", "d--------", "c--------"])
    tabella = modelcmp.models_against_corpus(stanza, udpipe)
    assert not tabella.empty
    assert {"valore nel corpus", "valore dei modelli", "token"} <= set(tabella.columns)


def test_le_forme_su_cui_i_due_modelli_divergono_si_trovano():
    """A ``divergence_hotspots`` that compared the corpus with itself would find nothing."""
    stanza = _tabella(["d--------"] * 4)
    udpipe = _tabella(["c--------"] * 4)
    # a single form, repeated enough to exceed the internal threshold
    stanza = pd.concat([stanza] * 2, ignore_index=True)
    udpipe = pd.concat([udpipe] * 2, ignore_index=True)
    stanza["token_id"] = range(1, len(stanza) + 1)
    udpipe["token_id"] = range(1, len(udpipe) + 1)
    stanza["form"] = "καὶ"
    udpipe["form"] = "καὶ"
    tabella = modelcmp.divergence_hotspots(stanza, udpipe)
    assert not tabella.empty, "two models that say different things must come out as divergent"
    assert tabella.iloc[0]["divergenze"] > 0


# ── the evaluation of the label ──────────────────────────────────────────────

def test_una_previsione_malformata_e_un_disaccordo_non_una_sospensione():
    """Three skewed labels out of half a million do not cancel the measure.

    The real case: UDPipe returns AGDT positional labels on all of Gorman except three,
    and those three must not suspend the measurement on the other 548,909.
    """
    from greek_corpus_pipeline.model_eval import postag_comparability

    tante = pd.Series(["n-s---mn-"] * 1000 + ["v-sagamn-"])
    verdetto = postag_comparability(tante)
    assert verdetto["verdetto"] == "misto"
    assert verdetto["malformate"] == 1
    assert verdetto["malformate_distinte"] == [{"etichetta": "v-sagamn-", "occorrenze": 1}]


def test_solo_un_tagset_completamente_diverso_ferma_la_misura():
    """Zero readable labels: there is no object to measure, and it stops."""
    from greek_corpus_pipeline.model_eval import postag_comparability

    ud = pd.Series(["NOUN", "VERB", "ADV", "CCONJ"])
    verdetto = postag_comparability(ud)
    assert verdetto["verdetto"] == "incompatibile"
    assert verdetto["forma_agdt"] == 0


def test_la_soglia_non_esiste():
    """The decision is qualitative — none interpretable — not a percentage.

    A single good label out of a thousand is enough to make the measure available,
    because the question is “are the two tagsets the same?”, not “how noisy is it?”.
    """
    from greek_corpus_pipeline.model_eval import postag_comparability

    quasi_tutte_storte = pd.Series(["NOUN"] * 999 + ["n-s---mn-"])
    assert postag_comparability(quasi_tutte_storte)["verdetto"] == "misto"


# ── the grouping, when the chosen field is one of the keys ───────────────────

def _corpus_di_due_documenti():
    """The tokens of the two documents, with the schema that the program writes."""
    a = _tabella(["n-s---mn-", "v3spia---"])
    b = _tabella(["d--------", "c--------"])
    b["document_id"] = "b"
    b["source_file"] = "b.xml"
    b["token_id"] = [3, 4]
    return pd.concat([a, b], ignore_index=True)


def test_il_raggruppamento_per_document_id_non_si_ferma():
    """The defect: “The column label 'document_id' is not unique”.

    ``document_id`` is one of the merge keys, so it is already inside the merged
    table; taking it again from ``tokens`` would create two columns with the same
    name and ``drop_duplicates`` would stop.  On the real corpora — Gorman and
    Pedalion — ``document_id`` is the only grouping field available, so the
    “By author” card would never produce anything, and with it the whole
    recomputation of the five tabs would stop.
    """
    stanza = _corpus_di_due_documenti()
    udpipe = _corpus_di_due_documenti()
    udpipe["postag_modello"] = ["n-s---mn-", "v1spia---", "d--------", "d--------"]
    tabella = modelcmp.agreement_by_group(stanza, udpipe, stanza, group="document_id")
    assert not tabella.empty, "the per-group card stays empty"
    assert set(tabella["document_id"]) == {"a", "b"}
    assert tabella["token"].sum() == 4


def test_il_raggruppamento_per_document_id_conta_quello_che_dice():
    """The percentages per document, with the predictions chosen by hand.

    Stanza repeats the corpus everywhere; UDPipe gets one label out of two wrong in
    document a and both in document b.
    """
    stanza = _corpus_di_due_documenti()
    udpipe = _corpus_di_due_documenti()
    stanza["postag_modello"] = list(stanza["postag"])
    udpipe["postag_modello"] = [stanza["postag"][0], "v1spia---", "d--------", "d--------"]

    tabella = modelcmp.agreement_by_group(stanza, udpipe, stanza, group="document_id")
    per_documento = tabella.set_index("document_id")
    assert per_documento.loc["a", "token"] == 2
    assert per_documento.loc["b", "token"] == 2
    assert per_documento.loc["a", "% corpus ↔ Stanza"] == 100.0
    assert per_documento.loc["b", "% corpus ↔ Stanza"] == 100.0
    assert per_documento.loc["a", "% corpus ↔ UDPipe"] == 50.0
    assert per_documento.loc["b", "% corpus ↔ UDPipe"] == 0.0


def test_il_raggruppamento_per_un_campo_che_non_e_chiave_resta_com_era():
    """The route does not change: the field is still taken from ``tokens``."""
    stanza = _corpus_di_due_documenti()
    udpipe = _corpus_di_due_documenti()
    token = stanza.copy()
    token["autore"] = ["Tucidide", "Tucidide", "Senofonte", "Senofonte"]
    tabella = modelcmp.agreement_by_group(stanza, udpipe, token, group="autore")
    assert set(tabella["autore"]) == {"Tucidide", "Senofonte"}
    assert tabella["token"].sum() == 4
    assert "autore" not in stanza.columns, "the input table was modified"


def test_un_campo_che_nel_corpus_non_c_e_non_solleva():
    stanza = _corpus_di_due_documenti()
    assert modelcmp.agreement_by_group(stanza, stanza, stanza, group="periodo").empty
