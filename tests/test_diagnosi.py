# -*- coding: utf-8 -*-
"""The diagnosis of a finding: key, parameters, and the sentence that comes out.

Three things are kept apart: *which* sentence (``issue_key``), *with which
values* (``issue_params``) and *in which language* it is read.  These tests
verify that the separation really holds — that is, that the sentence is
always derived and never a second source, that changing language does not
require rerunning the analysis, and that step 3 does not anticipate the
proposed correction that is decided at step 5.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


# ═══════════════════════════════════════════════════════════════════════════
# 1. The texts module
# ═══════════════════════════════════════════════════════════════════════════

def test_ogni_chiave_comincia_con_un_controllo_del_catalogo():
    """``issue_key`` is ``rule_id``, except for a suffix after the dot."""
    from greek_corpus_pipeline.issue_testi import TESTI
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG

    orfane = [chiave for chiave in TESTI
              if chiave.split(".")[0] not in RULE_CATALOG]
    assert orfane == [], f"keys with no check in the catalogue: {orfane}"


def test_ogni_testo_esiste_nelle_due_lingue():
    from greek_corpus_pipeline.issue_testi import TESTI

    for chiave, coppia in TESTI.items():
        assert len(coppia) == 2, chiave
        italiano, inglese = coppia
        assert italiano.strip(), f"{chiave}: Italian text empty"
        assert inglese.strip(), f"{chiave}: English text empty"
        assert italiano != inglese, f"{chiave}: the two languages are the same sentence"


def test_i_due_modelli_hanno_gli_stessi_segnaposto():
    """A value that appears in one language and not in the other would vanish."""
    from string import Formatter

    from greek_corpus_pipeline.issue_testi import TESTI

    for chiave, (italiano, inglese) in TESTI.items():
        campi_it = {c for _, c, _, _ in Formatter().parse(italiano) if c}
        campi_en = {c for _, c, _, _ in Formatter().parse(inglese) if c}
        assert campi_it == campi_en, (
            f"{chiave}: different placeholders between the two languages "
            f"({campi_it ^ campi_en})")


def test_nessun_modello_promette_un_valore_da_scrivere():
    """Step 3 says what does not add up, not what to write in its place.

    The formula “Proposed correction: X” would carry into the diagnosis the value that
    is decided at the step “Correct”.  Here it is verified that it does not appear: the
    search is on the models, that is, on the place from which it could come back in.
    """
    from greek_corpus_pipeline.issue_testi import TESTI

    # The ways in which a value is announced.  The negation — “No correction proposed” —
    # is not among them: saying that nothing is proposed is a diagnosis, not a proposal.
    vietate = (
        re.compile(r"(?<![Nn]essuna )[Cc]orrezione proposta\s*:"),
        re.compile(r"(?<![Nn]o )[Cc]orrection proposed\s*:"),
        re.compile(r"(?<![Nn]o )[Pp]roposed correction\s*:"),
        re.compile(r"propone\s+«"),
        re.compile(r"proposes\s+«"),
        re.compile(r"sarebbe\s+«"),
        re.compile(r"would be\s+«"),
    )
    colpevoli = []
    for chiave, coppia in TESTI.items():
        for modello in coppia:
            for vietata in vietate:
                if vietata.search(modello):
                    colpevoli.append((chiave, vietata.pattern))
    assert colpevoli == [], f"text templates that announce a value: {colpevoli}"


def test_i_parametri_non_contengono_parole_di_una_lingua():
    """The parameters carry codes and numbers; the names are derived on the spot.

    A parameter that contained “genere” or “gender” would carry a language into the
    backend, which is exactly what the separation avoids.
    """
    from greek_corpus_pipeline import issue_testi

    parole = ("genere", "numero", "caso", "posizione", "gender", "number",
              "case", "position", "lettera greca", "Greek letter")
    esempi = [
        ("invalid-character", issue_testi.parametri(slot=6, valore="c")),
        ("underscore-person-number", issue_testi.parametri(slots=(1, 2))),
        ("relation-greek-lookalike", issue_testi.parametri(
            coppie=({"greco": "U+039A", "latino": "U+004B"},))),
        ("agreement-modifier", issue_testi.serializza(
            {"discordanze": [{"slot": 6, "modificatore": "m", "testa": "f"}]})),
    ]
    for chiave, testo in esempi:
        for parola in parole:
            assert parola not in str(testo), f"{chiave}: “{parola}” in the parameters"


def test_una_chiave_sconosciuta_non_inventa_una_frase():
    from greek_corpus_pipeline.issue_testi import rendi

    assert rendi("questa-regola-non-esiste", '{"a":1}') == ""
    assert rendi("", None) == ""


def test_i_parametri_sono_json_deterministico_e_il_greco_resta_greco():
    from greek_corpus_pipeline.issue_testi import serializza

    testo = serializza({"zeta": 1, "alfa": "δεῖν", "beta": [3, 2]})
    assert testo == '{"alfa":"δεῖν","beta":[3,2],"zeta":1}'
    assert json.loads(testo)["alfa"] == "δεῖν"
    assert "\\u" not in testo


def test_le_riparazioni_lessicali_hanno_tutte_la_loro_chiave():
    from greek_corpus_pipeline.issue_testi import TESTI
    from greek_corpus_pipeline.rule_catalog import LEXICAL_REPAIRS

    mancanti = [str(r["rule_id"]) for r in LEXICAL_REPAIRS
                if str(r["rule_id"]) not in TESTI]
    assert mancanti == [], f"lexical repairs with no text: {mancanti}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. The sentence is derived, not written
# ═══════════════════════════════════════════════════════════════════════════

def test_la_frase_della_segnalazione_si_ricompone_dai_suoi_dati(tokens):
    """``issue`` is a cache: regenerating it must give the same string."""
    from greek_corpus_pipeline.issue_testi import rendi_serie
    from greek_corpus_pipeline.postag import analyze_postags

    segnalazioni = analyze_postags(tokens)
    assert not segnalazioni.empty
    rifatta = rendi_serie(segnalazioni, "it").fillna("")
    scritta = segnalazioni["issue"].astype("string").fillna("")
    assert (rifatta == scritta).all(), "the stored sentence and the derived one diverge"


def test_ogni_segnalazione_porta_una_chiave_conosciuta(tokens):
    from greek_corpus_pipeline import agreement, lemma, orthography, postag, syntax
    from greek_corpus_pipeline.issue_testi import TESTI

    sintassi, _archi = syntax.analyze_syntax(tokens)
    pezzi = [postag.analyze_postags(tokens), lemma.analyze_lemmas(tokens),
             sintassi, orthography.analyze_orthography(tokens),
             agreement.analyze_agreement(tokens)]
    for pezzo in pezzi:
        if pezzo is None or pezzo.empty:
            continue
        assert "issue_key" in pezzo.columns
        chiavi = set(pezzo["issue_key"].astype(str))
        assert chiavi <= set(TESTI), f"keys with no text: {chiavi - set(TESTI)}"
        assert not pezzo["issue"].astype("string").fillna("").eq("").any()


def test_la_frase_cambia_lingua_e_i_valori_no(tokens):
    """Numbers, Greek forms, labels and code points survive the translation."""
    from greek_corpus_pipeline.issue_testi import rendi_serie
    from greek_corpus_pipeline.postag import analyze_postags

    segnalazioni = analyze_postags(tokens)
    italiano = rendi_serie(segnalazioni, "it").fillna("")
    inglese = rendi_serie(segnalazioni, "en").fillna("")
    assert (italiano != inglese).any(), "no sentence changes with the language"

    numero = re.compile(r"\d+")
    greco = re.compile(r"[Ͱ-Ͽἀ-῿]{2,}")
    for it, en in zip(italiano, inglese):
        for modello in (numero, greco):
            assert set(modello.findall(it)) == set(modello.findall(en)), (
                f"a value is lost in translation:\n  it: {it}\n  en: {en}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. The text columns are not frozen in the language of the analysis
# ═══════════════════════════════════════════════════════════════════════════

def test_nome_e_descrizione_seguono_la_lingua_richiesta(tokens):
    from greek_corpus_pipeline.issue_testi import localizza
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import rule_description, rule_name

    segnalazioni = analyze_postags(tokens)
    for lingua in ("it", "en"):
        vista = localizza(segnalazioni, lingua)
        for _, riga in vista.iterrows():
            regola = str(riga["rule_id"])
            assert riga["anomaly_name"] == rule_name(regola, lingua)
            assert riga["anomaly_description"] == rule_description(regola, lingua)
    italiano = localizza(segnalazioni, "it")
    inglese = localizza(segnalazioni, "en")
    assert (italiano["anomaly_name"] != inglese["anomaly_name"]).any()
    assert (italiano["issue"] != inglese["issue"]).any()


def test_localizza_non_tocca_le_colonne_scientifiche(tokens):
    from greek_corpus_pipeline.issue_testi import COLONNE_TESTUALI, localizza
    from greek_corpus_pipeline.postag import analyze_postags

    segnalazioni = analyze_postags(tokens)
    inglese = localizza(segnalazioni, "en")
    for colonna in segnalazioni.columns:
        if colonna in COLONNE_TESTUALI:
            continue
        prima = segnalazioni[colonna].astype("string").fillna("␀")
        dopo = inglese[colonna].astype("string").fillna("␀")
        assert (prima.to_numpy() == dopo.to_numpy()).all(), colonna


def test_un_giro_salvato_senza_chiave_resta_leggibile():
    """Without ``issue_key`` the sentence that is there is shown as it is."""
    from greek_corpus_pipeline.issue_testi import localizza

    vecchio = pd.DataFrame({
        "rule_id": ["grade-p"],
        "anomaly_name": ["un nome vecchio"],
        "anomaly_description": ["una descrizione vecchia"],
        "issue": ["una frase scritta prima del refactoring"],
    })
    vista = localizza(vecchio, "en")
    assert vista["issue"].iloc[0] == "una frase scritta prima del refactoring"
    # Name and description, instead, are derived from the catalogue, which is always
    # there.
    from greek_corpus_pipeline.rule_catalog import rule_name
    assert vista["anomaly_name"].iloc[0] == rule_name("grade-p", "en")


# ═══════════════════════════════════════════════════════════════════════════
# 4. The panel of step 3
# ═══════════════════════════════════════════════════════════════════════════

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def corpus_ricco(tokens):
    """The test corpus, plus the rows that switch on the checks that are needed.

    The corpus of the tests is nine words chosen to be correct: none carries a positive
    degree written “p”, none has two different empty boxes.  The rows added here are
    synthetic and serve this file only.
    """
    extra = []
    modello = tokens.iloc[0].to_dict()
    aggiunte = [
        # positive degree written “p”: proposes the label with the hyphen
        {"form": "μείζων", "lemma": "μέγας", "postag": "a-s---mnp",
         "relation": "ATR", "head": 2, "token_id": 6, "token_index": 6},
        # two different empty boxes, for two different diagnoses
        {"form": "ἄνθρωπος", "lemma": "ἄνθρωπος", "postag": "n-s---m--",
         "relation": "SBJ", "head": 3, "token_id": 7, "token_index": 7},
        {"form": "λόγον", "lemma": "λόγος", "postag": "n-----ma-",
         "relation": "OBJ", "head": 3, "token_id": 8, "token_index": 8},
    ]
    for aggiunta in aggiunte:
        riga = dict(modello)
        riga.update(aggiunta)
        extra.append(riga)
    return pd.concat([tokens, pd.DataFrame(extra)], ignore_index=True)


@pytest.fixture
def pagina(application, tmp_path, corpus_ricco):
    from greek_corpus_pipeline import agreement, lemma, orthography, postag, syntax
    from gui_qt.pages.base import AppState
    from gui_qt.pages.errors_page import ErrorsPage

    tokens = corpus_ricco
    sintassi, _archi = syntax.analyze_syntax(tokens)
    pezzi = [postag.analyze_postags(tokens), lemma.analyze_lemmas(tokens),
             sintassi, orthography.analyze_orthography(tokens),
             agreement.analyze_agreement(tokens)]
    vive = [p for p in pezzi if p is not None and not p.empty]
    colonne: list[str] = []
    for pezzo in vive:
        for nome in pezzo.columns:
            if nome not in colonne:
                colonne.append(nome)
    stato = AppState(workspace=tmp_path)
    stato.run_id = "prova"
    stato.corpus_name = "prova"
    stato.tokens = tokens
    stato.findings = pd.concat([p.reindex(columns=colonne) for p in vive],
                               ignore_index=True)
    assert not stato.findings.empty
    vista = ErrorsPage(stato)
    vista.build()
    vista._apply_summary(
        vista._compute_summary(stato.findings, stato.tokens, "prova"))
    application.processEvents()
    yield vista
    vista.deleteLater()
    application.processEvents()


def _riga(pagina, regola: str):
    frame = pagina._table.dataframe()
    scelte = frame[frame["rule_id"].astype(str) == regola]
    if scelte.empty:
        pytest.skip(f"il corpus di prova non produce {regola}")
    return scelte.iloc[0]


def test_il_pannello_ha_due_riquadri_distinti(pagina, application):
    """The first says what the check looks for, the second what the row shows."""
    from gui_qt.i18n import tr

    riga = _riga(pagina, "grade-p")
    pagina._detail.show_row(riga, pagina.state.tokens)
    application.processEvents()
    assert pagina._detail._what_title.text() == tr("errors.what")
    assert pagina._detail._diagnosis_title.text() == tr("errors.diagnosis")
    assert pagina._detail._what.text().strip()
    assert pagina._detail._diagnosis.text().strip()
    assert pagina._detail._what.text() != pagina._detail._diagnosis.text()


def test_le_etichette_dei_riquadri_sono_quelle_decise():
    from gui_qt.i18n import _STRINGS

    assert _STRINGS["errors.what"] == ("Che cosa controlla",
                                       "What this check looks for")
    assert _STRINGS["errors.diagnosis"] == (
        "Che cosa non torna in questa occorrenza", "What does not add up here")


def test_due_occorrenze_della_stessa_regola(pagina, application):
    """Same first box, different second box when the values are different."""
    from gui_qt.i18n import T

    frame = pagina._table.dataframe()
    scelte = frame[frame["rule_id"].astype(str) == "slot-missing"]
    if len(scelte) < 2:
        pytest.skip("two occurrences of slot-missing are needed")
    lette = []
    for _, riga in scelte.iterrows():
        pagina._detail.show_row(riga, pagina.state.tokens)
        application.processEvents()
        lette.append((pagina._detail._what.text(), pagina._detail._diagnosis.text()))
    assert len({voce[0] for voce in lette}) == 1, (
        "“What it checks” must be the same description as in the catalogue")
    diverse = {voce[1] for voce in lette}
    parametri = set(scelte["issue_params"].astype("string").fillna(""))
    if len(parametri) > 1:
        assert len(diverse) > 1, (
            "different parameters must give different diagnoses")


def test_il_pannello_cambia_lingua_senza_rieseguire_l_analisi(pagina, application):
    from gui_qt.i18n import T

    riga = _riga(pagina, "grade-p")
    prima_lingua = T.language
    try:
        T.language = "it"
        pagina._detail.show_row(riga, pagina.state.tokens)
        application.processEvents()
        italiano = (pagina._detail._what.text(), pagina._detail._diagnosis.text())
        T.language = "en"
        pagina._detail.show_row(riga, pagina.state.tokens)
        application.processEvents()
        inglese = (pagina._detail._what.text(), pagina._detail._diagnosis.text())
    finally:
        T.language = prima_lingua
    assert italiano[0] != inglese[0]
    assert italiano[1] != inglese[1]
    assert inglese[1].strip()


# ═══════════════════════════════════════════════════════════════════════════
# 5. Step 3 and step 5 do not say the same thing
# ═══════════════════════════════════════════════════════════════════════════

def _citato(valore: str, testo: str) -> bool:
    """The value appears as a value, not inside another word."""
    confine = r"[^\wͰ-῿]"
    return re.search(f"(?:^|{confine}){re.escape(valore)}(?:{confine}|$)",
                     testo) is not None


@pytest.mark.parametrize("colonna", ["suggested_postag", "suggested_lemma"])
def test_il_valore_proposto_non_compare_al_passo_3(pagina, application, colonna):
    frame = pagina._table.dataframe()
    if colonna not in frame.columns:
        pytest.skip(f"{colonna} is not among the columns carried")
    valori = frame[colonna].astype("string")
    scelte = frame[valori.notna() & valori.fillna("").str.strip().ne("")]
    if scelte.empty:
        pytest.skip(f"no finding with {colonna}")
    for _, riga in scelte.head(20).iterrows():
        proposto = str(riga[colonna]).strip()
        pagina._detail.show_row(riga, pagina.state.tokens)
        application.processEvents()
        assert not _citato(proposto, pagina._detail._diagnosis.text()), (
            f"{riga['rule_id']}: “{proposto}” appears in the diagnosis of step 3")


def test_il_valore_proposto_resta_nella_segnalazione(pagina):
    """Removing it from the sentence must not remove it from the data."""
    frame = pagina._table.dataframe()
    proposte = 0
    for colonna in ("suggested_postag", "suggested_lemma", "suggested_relation",
                    "suggested_form"):
        if colonna in frame.columns:
            valori = frame[colonna].astype("string").fillna("")
            proposte += int(valori.str.strip().ne("").sum())
    assert proposte > 0, "no proposal survived the refactoring"


def test_le_colonne_della_diagnosi_escono_nell_esportazione(pagina):
    from gui_qt.pages.errors_page import CARRIED_COLUMNS

    assert "issue_key" in CARRIED_COLUMNS
    assert "issue_params" in CARRIED_COLUMNS
    assert "issue" in CARRIED_COLUMNS
    frame = pagina._table.dataframe()
    for colonna in ("issue", "issue_key", "issue_params"):
        assert colonna in frame.columns


def test_le_colonne_della_diagnosi_non_si_vedono_in_tabella(pagina):
    """They come out in the file, they do not widen the table."""
    tabella = pagina._table
    frame = tabella.dataframe()
    vista = tabella._view
    visibili = [str(nome) for indice, nome in enumerate(frame.columns)
                if not vista.isColumnHidden(indice)]
    assert "issue_key" not in visibili
    assert "issue_params" not in visibili
    assert "issue" not in visibili


def test_nessun_parametro_ripete_un_dato_della_segnalazione(tokens):
    """What is derived from the columns does not enter the parameters.

    The character of a box is character *n* of the label, and the length of the label is
    its length: the parameters hold which box to look at, not what is written in it.
    """
    from greek_corpus_pipeline import agreement, lemma, orthography, postag, syntax

    sintassi, _archi = syntax.analyze_syntax(tokens)
    pezzi = [postag.analyze_postags(tokens), lemma.analyze_lemmas(tokens),
             sintassi, orthography.analyze_orthography(tokens),
             agreement.analyze_agreement(tokens)]
    ripetuti = []
    for pezzo in pezzi:
        if pezzo is None or pezzo.empty:
            continue
        for _, riga in pezzo.iterrows():
            testo = str(riga.get("issue_params") or "")
            if not testo:
                continue
            parametri = json.loads(testo)
            for colonna in ("form", "lemma", "postag", "relation"):
                valore = riga.get(colonna)
                if valore is None or pd.isna(valore) or not str(valore).strip():
                    continue
                for nome, contenuto in parametri.items():
                    if contenuto == valore:
                        ripetuti.append((str(riga["issue_key"]), nome, colonna))
    assert ripetuti == [], f"parameters that repeat a column: {set(ripetuti)}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Bilingualism, from end to end
# ═══════════════════════════════════════════════════════════════════════════

def _impronta(findings: pd.DataFrame) -> str:
    import hashlib
    colonne = [c for c in ("rule_id", "document_id", "sentence_id", "token_id")
               if c in findings.columns]
    righe = sorted("␟".join(str(v) for v in riga)
                   for riga in findings[colonne].astype(str).to_numpy())
    return hashlib.md5("\n".join(righe).encode("utf-8")).hexdigest()[:12]


def _nuclei(tokens: pd.DataFrame) -> dict:
    from greek_corpus_pipeline import variation
    return {piano: int(len(tabella))
            for piano, tabella in variation.run_variation_suite(tokens).items()}


def _grafico_per_regola(findings: pd.DataFrame) -> list[str]:
    """The labels that the chart “by rule” shows, in the active language."""
    from greek_corpus_pipeline.rule_catalog import rule_name

    from gui_qt.i18n import pick
    lingua = pick(("it", "en"))
    conteggi = findings["rule_id"].astype(str).value_counts()
    return [rule_name(str(regola), lingua) for regola in conteggi.index]


def test_bilinguismo_da_capo_a_fondo(pagina, application, corpus_ricco):
    """Detection once only; then the language changes and the data does not.

    What changes: the description of the check, the sentence of the finding, the gloss
    of the label, the gloss of the relation, the reference to the sentence among the
    occurrences and the name of the check in the chart.  What does not change:
    ``rule_id``, raw form, lemma, label and relation, head, proposals, counts,
    fingerprint and nuclei.
    """
    from gui_qt.i18n import T

    tokens = corpus_ricco
    findings = pagina.state.findings

    # What must not change, measured beforehand.
    scientifiche = [c for c in ("rule_id", "form", "lemma", "postag", "relation",
                                "head", "suggested_postag", "suggested_lemma",
                                "suggested_relation", "suggested_form",
                                "suggested_head", "auto_correctable", "severity")
                    if c in findings.columns]
    prima_dati = {c: findings[c].astype("string").fillna("␀").to_numpy().tolist()
                  for c in scientifiche}
    prima_conto = len(findings)
    prima_per_regola = findings["rule_id"].astype(str).value_counts().to_dict()
    prima_impronta = _impronta(findings)
    prima_nuclei = _nuclei(tokens)

    riga = _riga(pagina, "grade-p")
    letture = {}
    lingua_iniziale = T.language
    try:
        for lingua in ("it", "en"):
            T.language = lingua
            pagina._detail.show_row(riga, tokens)
            application.processEvents()
            dettaglio = pagina._detail
            letture[lingua] = {
                "descrizione": dettaglio._what.text(),
                "issue": dettaglio._diagnosis.text(),
                "valori": dettaglio._values.text(),
                "occorrenze": dettaglio._evidence.text(),
                "grafico": _grafico_per_regola(findings),
            }
    finally:
        T.language = lingua_iniziale

    italiano, inglese = letture["it"], letture["en"]

    # ── they change ───────────────────────────────────────────────────
    assert italiano["descrizione"] != inglese["descrizione"]
    assert italiano["issue"] != inglese["issue"]
    assert inglese["issue"].strip()
    # The two glosses are in the same box as the values: the morphological label and the
    # relation stay the same, their reading changes.
    assert italiano["valori"] != inglese["valori"]
    assert "singolare" in italiano["valori"] or "plurale" in italiano["valori"]
    assert "singular" in inglese["valori"] or "plural" in inglese["valori"]
    assert "singolare" not in inglese["valori"]
    # The reference to the sentence, among the occurrences.
    if italiano["occorrenze"].strip():
        assert "· frase " in italiano["occorrenze"]
        assert "· sentence " in inglese["occorrenze"]
        assert "· frase " not in inglese["occorrenze"]
    # The name of the check in the chart by rule.
    assert italiano["grafico"] != inglese["grafico"]
    assert len(italiano["grafico"]) == len(inglese["grafico"])

    # ── they do not change ────────────────────────────────────────────
    dopo = pagina.state.findings
    assert len(dopo) == prima_conto
    assert dopo["rule_id"].astype(str).value_counts().to_dict() == prima_per_regola
    for colonna, valori in prima_dati.items():
        assert dopo[colonna].astype("string").fillna("␀").to_numpy().tolist() == valori, colonna
    assert _impronta(dopo) == prima_impronta
    assert _nuclei(tokens) == prima_nuclei


def test_le_riparazioni_non_automatiche_non_hanno_acquisito_proposte(tokens):
    """The majority reading stays a datum, it does not become a correction."""
    from greek_corpus_pipeline.rule_catalog import LEXICAL_REPAIRS

    manuali = {str(r["rule_id"]) for r in LEXICAL_REPAIRS if not r.get("auto", True)}
    assert manuali, "the catalogue has no lexical repairs to verify"
    from conftest import CORPORA_ENV, findings_dir

    percorso = findings_dir()
    if percorso is None:
        pytest.skip("the findings of the six corpora are not available "
                    f"(point to them with {CORPORA_ENV})")
    trovate = 0
    for file in sorted(percorso.glob("findings-*.parquet")):
        tabella = pd.read_parquet(file)
        scelte = tabella[tabella["rule_id"].astype(str).isin(manuali)]
        trovate += len(scelte)
        for colonna in ("suggested_postag", "suggested_lemma",
                        "suggested_relation", "suggested_form", "suggested_head"):
            if colonna in scelte.columns:
                valori = scelte[colonna].astype("string").fillna("")
                assert valori.str.strip().eq("").all(), (
                    f"{file.name}: {colonna} filled in on a manual repair")
        assert not scelte["auto_correctable"].fillna(False).any()
        # The information is there all the same, as data.
        parametri = scelte["issue_params"].astype("string").fillna("")
        assert parametri.str.contains("lettura_diffusa").all()
    assert trovate == 7, f"seven findings expected, found {trovate}"
