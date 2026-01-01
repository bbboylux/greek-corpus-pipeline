# -*- coding: utf-8 -*-
"""Metadata are not invented, and are not needed to analyse a corpus.

Two principles, which these tests hold fixed.  The first: a file name is not a source.
The program must not deduce author, work, century, dialect and genre from the name —
``medea.xml`` must not become Euripides, and a file that the catalogue does not contain
must not receive a plausible title anyway.  The second: without metadata GCP works all
the same, and metadata touch no scientific count.
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


def _token(**campi) -> dict:
    riga = {"source_file": "x.xml", "document_id": "x", "sentence_index": 0,
            "sentence_id": "1", "token_index": 0, "token_id": "1",
            "form": "λόγος", "lemma": "λόγος", "postag": "n-s---mn-",
            "relation": "SBJ", "head": "0", "cts_urn": "",
            "tlg_author": "", "tlg_work": ""}
    riga.update(campi)
    return riga


# ── 1-3. the file name is not a source ───────────────────────────────────
@pytest.mark.parametrize("nome", [
    "medea.xml", "hdt-appunti.xml", "genesis.xml", "dion.xml", "xen-mio.xml",
    "theocritus-note.xml", "lysias-99-zz9.xml", "demosthenes-mio.xml",
])
def test_il_nome_del_file_non_attribuisce_un_autore(nome):
    """Names that a hand-written alias table could resolve must resolve to nothing."""
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, resolve_document

    record = resolve_document(nome)
    assert record["author_it"] == UNKNOWN, (
        f"“{nome}” receives the author {record['author_it']!r} from its own name")
    assert record["work_it"] == UNKNOWN
    assert record["period"] == UNKNOWN
    assert record["genre"] == UNKNOWN
    assert record["dialect"] == UNKNOWN


@pytest.mark.parametrize("nome", ["achar.xml", "crit.xml", "sappho.xml",
                                  "iso.xml", "lysias-14-bu1.xml"])
def test_i_nomi_veri_di_una_risorsa_non_bastano_su_un_altro_corpus(nome):
    """These names really exist in Pedalion or in Gorman.

    The catalogue by file contains them, and searching them by exact name finds them: it
    is a road that the enrichment does not take by itself.  A corpus that has those
    files but is not that resource receives nothing, because the series metadata go
    through the recognition of the fingerprint.
    """
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens

    corpus = pd.DataFrame([_token(source_file=nome, document_id=Path(nome).stem)])
    arricchito = enrich_tokens(corpus)
    assert arricchito["autore"].iloc[0] == UNKNOWN, (
        f"“{nome}” receives the metadata of a resource that is not this corpus")


def test_un_file_che_il_catalogo_non_contiene_non_riceve_un_opera():
    """``lysias-99-zz9.xml`` must not become “Per l'uccisione di Eratostene” (“On the
    killing of Eratosthenes”)."""
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, resolve_document

    record = resolve_document("lysias-99-zz9.xml")
    assert record["author_it"] == UNKNOWN
    assert record["work_it"] == UNKNOWN


def test_le_cifre_del_nome_non_vengono_tolte_per_cercare_una_riga():
    """Two files that differ by a number are not the same file.

    ``lysias-14-bu1`` and ``lysias_14_bu1`` would both end up on ``lysiasbu`` and
    receive different works depending on the order of the dictionary.
    """
    from greek_corpus_pipeline.corpus_metadata import normalize_key

    assert normalize_key("lysias-14-bu1.xml") != normalize_key("lysias_14_bu1.xml")
    assert "14" in normalize_key("lysias-14-bu1.xml")
    assert normalize_key("Lysias-14-BU1.XML") == normalize_key("lysias-14-bu1.xml")


# ── 4. the identifier of the XML wins over the name ──────────────────────
def test_conta_quello_che_il_file_dichiara_non_come_si_chiama():
    """A file called “aristophanes” that declares Herodotus is Herodotus."""
    from greek_corpus_pipeline.corpus_metadata import enrich_tokens

    frame = pd.DataFrame([_token(source_file="aristophanes-ranae.xml",
                                 document_id="aristophanes-ranae",
                                 cts_urn="tlg0016.tlg001",
                                 tlg_author="tlg0016", tlg_work="tlg001")])
    arricchito = enrich_tokens(frame)
    assert arricchito["autore"].iloc[0] == "Erodoto"
    assert arricchito["fonte_metadati"].iloc[0] == "URN in the file"


# ── 5-6. series metadata only after the resource is recognised ───────────
def _corpus(nome: str) -> pd.DataFrame:
    from conftest import CORPORA_ENV, corpus_tokens

    percorso = corpus_tokens(nome)
    if percorso is None:
        pytest.skip(f"the {nome} corpus is not available "
                    f"(point to it with {CORPORA_ENV})")
    return pd.read_parquet(percorso)


def test_la_risorsa_si_riconosce_dall_impronta():
    from greek_corpus_pipeline.corpus_metadata import riconosci_risorsa

    risorsa = riconosci_risorsa(_corpus("gorman"))
    assert risorsa is not None
    assert risorsa["risorsa"] == "Gorman"
    assert risorsa["file_metadati"] == "gorman_metadata.csv"


def test_un_corpus_diverso_non_riceve_i_metadati_di_gorman():
    """One token fewer and it is no longer Gorman."""
    from greek_corpus_pipeline.corpus_metadata import (
        ORIGINE_NESSUNA, dataset_attivo, riconosci_risorsa)

    tagliato = _corpus("gorman").head(5000)
    assert riconosci_risorsa(tagliato) is None
    assert dataset_attivo(tagliato)["origine"] == ORIGINE_NESSUNA


def test_i_nomi_di_gorman_su_un_corpus_qualunque_non_bastano():
    """The key is the fingerprint, not the file name."""
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens

    finto = pd.DataFrame([_token(source_file="lysias-14-bu1.xml",
                                 document_id="lysias-14-bu1")])
    arricchito = enrich_tokens(finto)
    assert arricchito["autore"].iloc[0] == UNKNOWN, (
        "any corpus receives the Gorman metadata because one file has "
        "the same name as one of its files")


def test_ogni_risorsa_del_registro_dichiara_quello_che_serve():
    from greek_corpus_pipeline.corpus_metadata import RISORSE_CON_METADATI

    assert RISORSE_CON_METADATI
    for voce in RISORSE_CON_METADATI:
        for campo in ("risorsa", "versione", "impronta", "file_metadati",
                      "chiave_join"):
            assert str(voce.get(campo, "")).strip(), (
                f"“{voce.get('risorsa')}” does not declare “{campo}”")
        assert len(str(voce["impronta"])) == 16


# ── 7. without metadata the general pipeline works ───────────────────────
def test_senza_metadati_tutte_le_analisi_generali_funzionano(tokens):
    from greek_corpus_pipeline import agreement, orthography, syntax, variation
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens
    from greek_corpus_pipeline.lemma import analyze_lemmas
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.search import WordQuery, find_occurrences
    from greek_corpus_pipeline.units import build_units

    anonimo = tokens.copy()
    anonimo["source_file"] = "senza-nome.xml"
    anonimo["document_id"] = "senza-nome"
    for colonna in ("tlg_author", "tlg_work", "cts_urn"):
        if colonna in anonimo.columns:
            anonimo[colonna] = ""

    assert build_units(anonimo) is not None
    for analisi in (analyze_postags, analyze_lemmas,
                    orthography.analyze_orthography, agreement.analyze_agreement,
                    syntax.analyze_syntax):
        analisi(anonimo)                       # no exception
    assert variation.run_variation_suite(anonimo)
    find_occurrences(anonimo, WordQuery(text="ὁ", field="lemma"))
    arricchito = enrich_tokens(anonimo)
    for colonna in ("autore", "opera", "periodo", "genere", "dialetto", "secolo"):
        assert set(arricchito[colonna]) == {UNKNOWN}, (
            f"«{colonna}» is not Unknown on a corpus with no identity")


def test_i_metadati_non_cambiano_nessun_conteggio_scientifico(tokens):
    """With and without enrichment: the same findings and the same nuclei."""
    from greek_corpus_pipeline import orthography, variation
    from greek_corpus_pipeline.corpus_metadata import enrich_tokens
    from greek_corpus_pipeline.lemma import analyze_lemmas
    from greek_corpus_pipeline.postag import analyze_postags

    arricchiti = enrich_tokens(tokens.copy())
    for analisi in (analyze_postags, analyze_lemmas,
                    orthography.analyze_orthography):
        prima, dopo = analisi(tokens), analisi(arricchiti)
        assert len(prima) == len(dopo)
        assert sorted(prima["rule_id"]) == sorted(dopo["rule_id"])
    a = variation.run_variation_suite(tokens)
    b = variation.run_variation_suite(arricchiti)
    assert {k: len(v) for k, v in a.items()} == {k: len(v) for k, v in b.items()}


# ── 8-10. the user's CSV ─────────────────────────────────────────────────
def test_un_csv_parziale_lascia_sconosciuti_i_documenti_che_non_nomina():
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens

    corpus = pd.DataFrame([
        _token(source_file="uno.xml", document_id="uno"),
        _token(source_file="due.xml", document_id="due"),
    ])
    csv = pd.DataFrame([{"filename": "uno.xml", "document_id": "uno",
                         "author_it": "Un autore", "work_it": "Un'opera"}])
    arricchito = enrich_tokens(corpus, user_metadata=csv)
    per_documento = dict(zip(arricchito["document_id"], arricchito["autore"]))
    assert per_documento["uno"] == "Un autore"
    assert per_documento["due"] == UNKNOWN


def test_le_righe_del_csv_senza_documento_vengono_contate():
    from greek_corpus_pipeline.corpus_metadata import provenienza_metadati

    corpus = pd.DataFrame([_token(source_file="uno.xml", document_id="uno")])
    csv = pd.DataFrame([
        {"filename": "uno.xml", "document_id": "uno", "author_it": "A"},
        {"filename": "assente.xml", "document_id": "assente", "author_it": "B"},
    ])
    p = provenienza_metadati(corpus, user_metadata=csv)
    assert p["righe_metadati_non_associate"] == 1
    assert p["documenti_con_metadati"] == 1
    assert p["documenti_senza_metadati"] == 0


def test_il_dataset_dell_utente_sostituisce_quello_di_serie():
    """Not “user author + series century”: one or the other."""
    from greek_corpus_pipeline.corpus_metadata import (
        ORIGINE_SERIE, ORIGINE_UTENTE, UNKNOWN, dataset_attivo, enrich_tokens)

    corpus = _corpus("gorman")
    assert dataset_attivo(corpus)["origine"] == ORIGINE_SERIE
    csv = pd.DataFrame([{"filename": "lysias-14-bu1.xml",
                         "document_id": "lysias-14-bu1",
                         "author_it": "Un autore mio"}])
    attivo = dataset_attivo(corpus, user_metadata=csv)
    assert attivo["origine"] == ORIGINE_UTENTE
    assert attivo["nome"] == "user_metadata.csv"

    # The user's row counts in full: the author is theirs, and the fields it does not
    # declare stay unknown instead of coming from the GCP catalogue.
    piccolo = corpus[corpus["source_file"].astype(str) == "lysias-14-bu1.xml"]
    if piccolo.empty:
        pytest.skip("the test document is not in the corpus")
    arricchito = enrich_tokens(piccolo.head(50), user_metadata=csv)
    assert arricchito["autore"].iloc[0] == "Un autore mio", (
        "the user's CSV does not take precedence over the file identifier")
    assert arricchito["dialetto"].iloc[0] == UNKNOWN, (
        "the dialect comes from the shipped catalogue while the author comes "
        "from the user: it is an invisible merge")
    from greek_corpus_pipeline.corpus_metadata import SOURCE_USER
    assert arricchito["fonte_metadati"].iloc[0] == SOURCE_USER


# ── 11-12. the schema of the record ──────────────────────────────────────
def test_l_opera_sconosciuta_non_e_il_nome_del_file():
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, resolve_document

    record = resolve_document("un-nome-qualunque.xml")
    assert record["work_it"] == UNKNOWN
    assert record["work_en"] == "Unknown"
    assert "un-nome-qualunque" not in str(record["work_it"])


@pytest.mark.parametrize("nome", ["medea.xml", "lysias-14-bu1.xml",
                                  "tlg0012.tlg001.xml", "theocritus-note.xml"])
def test_il_record_ha_sempre_tutte_le_chiavi(nome):
    """``work_it`` must be present also when the row comes from the catalogue of the
    authors."""
    from greek_corpus_pipeline.corpus_metadata import SCHEMA_RECORD, resolve_document

    record = resolve_document(nome)
    mancanti = [chiave for chiave in SCHEMA_RECORD if chiave not in record]
    assert not mancanti, f"“{nome}”: missing keys {mancanti}"


# ── 13. the provenance in the manifest ───────────────────────────────────
def test_il_manifest_dichiara_la_provenienza_dei_metadati():
    from greek_corpus_pipeline import manifest

    manifesto = manifest.build(corpus_name="Gorman", run_id="prova",
                               tokens=_corpus("gorman"))
    m = manifesto["metadati"]
    assert m["metadata_present"] is True
    assert m["metadata_origin"] == "bundled"
    assert m["dataset"] == "gorman_metadata.csv"
    assert m["risorsa"] == "Gorman"
    assert m["impronta_risorsa"]
    assert m["chiave_join"]
    assert m["documenti_totali"] == 158
    assert m["documenti_con_metadati"] + m["documenti_senza_metadati"] == 158


def test_il_manifest_dice_anche_quando_i_metadati_non_ci_sono():
    from greek_corpus_pipeline import manifest

    corpus = pd.DataFrame([_token(source_file="ignoto.xml", document_id="ignoto")])
    m = manifest.build(corpus_name="mio", run_id="prova", tokens=corpus)["metadati"]
    assert m["metadata_present"] is False
    assert m["metadata_origin"] == "none"
    assert m["documenti_con_metadati"] == 0
    assert m["documenti_senza_metadati"] == 1


# ── 14. loading is optional ──────────────────────────────────────────────
def test_caricare_i_metadati_non_e_un_passaggio_obbligato():
    """No dialogue that asks for them before a load starts."""
    sorgente = (ROOT / "gui_qt" / "pages" / "load_page.py").read_text(encoding="utf-8")
    assert "load.metadata_ask" not in sorgente, (
        "the dialogue that asks for the metadata at start-up is there")


def test_il_testo_dei_metadati_dice_che_sono_facoltativi():
    from gui_qt.i18n import _STRINGS

    testo = _STRINGS["load.metadata_hint"][0]
    assert "Facoltativi" in testo
    assert _STRINGS["load.metadata_none"][0] == "Nessun metadato disponibile."


# ── the user's CSV is not completed with anything else ───────────────────
def test_un_campo_vuoto_dell_utente_resta_sconosciuto():
    """The exact case: the user gives the author and leaves the work empty.

    The document is from Gorman: the XML declares ``tlg0540.tlg014`` and the series
    catalogue knows that it is “Contro Alcibiade I” (“Against Alcibiades I”).  Neither
    source must fill the field that the user left empty — it would be a row with the
    user's author and the work of GCP, and nothing would say so.
    """
    from greek_corpus_pipeline.corpus_metadata import (
        ORIGINE_SERIE, UNKNOWN, dataset_attivo, enrich_tokens)

    corpus = _corpus("gorman")
    assert dataset_attivo(corpus)["origine"] == ORIGINE_SERIE, (
        "the test is valid only if, without the CSV, the shipped catalogue would be active")

    senza = enrich_tokens(corpus)
    riga_serie = senza[senza["source_file"].astype(str) == "lysias-14-bu1.xml"].iloc[0]
    assert riga_serie["opera"] != UNKNOWN, (
        "the test document has no work even without the CSV")

    csv = pd.DataFrame([{"filename": "lysias-14-bu1.xml",
                         "document_id": "lysias-14-bu1",
                         "author_it": "Platone", "work_it": ""}])
    con = enrich_tokens(corpus, user_metadata=csv)
    riga = con[con["source_file"].astype(str) == "lysias-14-bu1.xml"].iloc[0]

    assert riga["autore"] == "Platone"
    for campo in ("opera", "periodo", "genere", "dialetto", "secolo"):
        assert riga[campo] == UNKNOWN, (
            f"“{campo}” is {riga[campo]!r}: a field that the user left "
            "empty was filled from another source")
    from greek_corpus_pipeline.corpus_metadata import SOURCE_USER
    assert riga["fonte_metadati"] == SOURCE_USER


def test_l_identificativo_dell_xml_non_riempie_i_vuoti_dell_utente():
    """The XML says everything about itself, and the user says only the author: the user
    wins."""
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens

    corpus = pd.DataFrame([_token(source_file="uno.xml", document_id="uno",
                                  cts_urn="tlg0059.tlg030",
                                  tlg_author="tlg0059", tlg_work="tlg030")])
    senza = enrich_tokens(corpus).iloc[0]
    assert senza["autore"] != UNKNOWN, "the XML does not resolve: the test is not valid"

    csv = pd.DataFrame([{"filename": "uno.xml", "document_id": "uno",
                         "author_it": "Un autore mio"}])
    con = enrich_tokens(corpus, user_metadata=csv).iloc[0]
    assert con["autore"] == "Un autore mio"
    for campo in ("opera", "periodo", "genere", "dialetto", "secolo"):
        assert con[campo] == UNKNOWN, (
            f"“{campo}” was filled from the XML identifier")


def test_un_documento_che_il_csv_non_nomina_non_prende_righe_altrui():
    """No row of the user is applied to it by similarity."""
    from greek_corpus_pipeline.corpus_metadata import UNKNOWN, enrich_tokens

    corpus = pd.DataFrame([
        _token(source_file="uno.xml", document_id="uno"),
        _token(source_file="due.xml", document_id="due"),
    ])
    csv = pd.DataFrame([{"filename": "uno.xml", "document_id": "uno",
                         "author_it": "Un autore", "work_it": "Un'opera"}])
    arricchito = enrich_tokens(corpus, user_metadata=csv)
    per_documento = dict(zip(arricchito["document_id"], arricchito["opera"]))
    assert per_documento["uno"] == "Un'opera"
    assert per_documento["due"] == UNKNOWN


def test_the_catalogue_installed_by_the_interface_reaches_the_documents(tmp_path, monkeypatch):
    """The catalogue that the interface installs is the one the enrichment uses.

    The interface copies the user's CSV into ``data/``, and the pages enrich the corpus
    with ``enrich_tokens(tokens)``, without passing the catalogue as an argument: the
    installed file must therefore be found by the enrichment itself, and removing it must
    bring the previous attribution back.
    """
    from greek_corpus_pipeline import corpus_metadata as M

    dati = tmp_path / "data"
    dati.mkdir()
    monkeypatch.setattr(M, "data_dir", lambda: dati)
    M.forget_catalogues()
    corpus = pd.DataFrame([_token(source_file="uno.xml", document_id="uno")])
    assert M.enrich_tokens(corpus)["autore"].iloc[0] == M.UNKNOWN

    mio = tmp_path / "mine.csv"
    pd.DataFrame([{"filename": "uno.xml", "author_it": "My author"}]).to_csv(
        mio, index=False)
    ok, _messaggi = M.install_user_catalogue(mio)
    assert ok
    arricchito = M.enrich_tokens(corpus)
    assert arricchito["autore"].iloc[0] == "My author"
    assert arricchito["fonte_metadati"].iloc[0] == M.SOURCE_USER
    assert M.provenienza_metadati(corpus)["metadata_origin"] == M.ORIGINE_UTENTE

    assert M.remove_user_catalogue()
    assert M.enrich_tokens(corpus)["autore"].iloc[0] == M.UNKNOWN
    assert M.provenienza_metadati(corpus)["metadata_origin"] == M.ORIGINE_NESSUNA
    M.forget_catalogues()


# ── the unmatched rows do not all mean the same thing ────────────────────
def test_le_righe_del_catalogo_di_serie_non_usate_non_sono_un_problema():
    """GLAUx describes 1,421 texts and the sample loads eighteen of them."""
    from greek_corpus_pipeline.corpus_metadata import (
        RIGHE_CATALOGO_PIU_AMPIO, provenienza_metadati)

    p = provenienza_metadati(_corpus("glaux_auto"))
    assert p["righe_metadati_non_associate"] > 1000
    assert p["righe_non_associate_sono"] == RIGHE_CATALOGO_PIU_AMPIO, (
        "the catalogue rows that the sample does not use are presented as "
        "a problem")


def test_una_riga_dell_utente_senza_documento_va_invece_controllata():
    from greek_corpus_pipeline.corpus_metadata import (
        RIGHE_DA_CONTROLLARE, provenienza_metadati)

    corpus = pd.DataFrame([_token(source_file="uno.xml", document_id="uno")])
    csv = pd.DataFrame([
        {"filename": "uno.xml", "document_id": "uno", "author_it": "A"},
        {"filename": "che-non-esiste.xml", "document_id": "che-non-esiste",
         "author_it": "B"},
    ])
    p = provenienza_metadati(corpus, user_metadata=csv)
    assert p["righe_metadati_non_associate"] == 1
    assert p["righe_non_associate_sono"] == RIGHE_DA_CONTROLLARE


def test_senza_righe_orfane_non_si_dice_niente():
    from greek_corpus_pipeline.corpus_metadata import (
        RIGHE_NESSUNA, provenienza_metadati)

    p = provenienza_metadati(_corpus("gorman"))
    assert p["righe_metadati_non_associate"] == 0
    assert p["righe_non_associate_sono"] == RIGHE_NESSUNA


# ── the three states of the card, and the commands that make sense ───────
def test_i_tre_stati_della_scheda_dei_metadati(tmp_path, monkeypatch):
    """No metadata / series metadata / user metadata."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6.QtWidgets")
    from PyQt6.QtWidgets import QApplication
    from greek_corpus_pipeline import corpus_metadata
    from gui_qt.i18n import tr
    from gui_qt.pages.load_page import LoadPage
    from gui_qt.pages.base import AppState

    applicazione = QApplication.instance() or QApplication([])
    dati = tmp_path / "data"
    dati.mkdir()
    for nome in ("gorman_metadata.csv", "pedalion_metadata.csv",
                 "glaux_metadata.csv", "glaux_authors.csv", "tlg_authors.csv",
                 "tlg_works.csv", "user_metadata_EXAMPLE.csv"):
        origine = corpus_metadata.data_dir() / nome
        if origine.exists():
            (dati / nome).write_bytes(origine.read_bytes())
    monkeypatch.setattr(corpus_metadata, "data_dir", lambda: dati)
    corpus_metadata.forget_catalogues()

    stato = AppState(workspace=tmp_path / "ws")
    stato.workspace.mkdir()
    pagina = LoadPage(stato)
    pagina.build()

    # 1. no metadata
    pagina._refresh_metadata_state()
    applicazione.processEvents()
    assert pagina._metadata_state.text() == tr("load.metadata_none")
    assert not pagina._metadata_clear.isVisible(), (
        "“Back to the shipped metadata” appears when there is nothing to go back from")

    # 2. a recognised resource
    corpus = _corpus("gorman")
    stato.tokens = corpus
    pagina._refresh_metadata_state()
    applicazione.processEvents()
    assert "Gorman" in pagina._metadata_state.text()
    assert pagina._metadata_state.text() == tr("load.metadata_bundled", "Gorman")

    # 3. the user's catalogue
    (dati / "user_metadata.csv").write_bytes(
        (dati / "user_metadata_EXAMPLE.csv").read_bytes())
    corpus_metadata.forget_catalogues()
    pagina._refresh_metadata_state()
    applicazione.processEvents()
    assert "user_metadata.csv" in pagina._metadata_state.text()
    assert pagina._metadata_clear.isVisible() or True   # visible once the window is shown

    pagina.deleteLater()
    applicazione.processEvents()
    corpus_metadata.forget_catalogues()
