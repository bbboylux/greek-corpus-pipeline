# -*- coding: utf-8 -*-
"""The basic functions: reading, diagnosis, correction, exports.

It is not a complete coverage of the catalogue — that is in the counts that the article
reports — but it is the net that prevents a change in the gold flow from breaking by
mistake what works.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_il_corpus_si_legge_con_le_colonne_attese(tokens):
    for colonna in ("document_id", "sentence_id", "token_id", "form",
                    "lemma", "postag", "relation", "head"):
        assert colonna in tokens.columns
    assert len(tokens) == 9


def test_la_diagnosi_trova_il_tag_corto_e_il_numero_in_coda(tokens):
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.lemma import analyze_lemmas

    morfologia = analyze_postags(tokens)
    regole = set(morfologia["rule_id"]) if not morfologia.empty else set()
    assert "invalid-length-padding" in regole or "invalid-length-broken" in regole, \
        "n-p---mn has eight characters and must be flagged"

    lemmi = analyze_lemmas(tokens)
    regole_lemma = set(lemmi["rule_id"]) if not lemmi.empty else set()
    assert "lemma-tool-numbering" in regole_lemma, \
        "στρατιώτης1 carries the program's number at the end"


def test_il_catalogo_dichiara_settantasette_controlli():
    """Seventy-seven checks, and the catalogue is the only source of the number.

    Three diagnostic classes and two treatments: either the program proposes, or it
    stays silent.
    """
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    assert len(RULE_CATALOG) == 77
    for identificatore, regola in RULE_CATALOG.items():
        assert regola["class"] in {"violazione", "variante", "verifica"}, identificatore
        assert regola["treatment"] in {"automatica", "manuale"}, identificatore


def test_le_relazioni_rare_sono_una_regola_sola():
    """The check on rare relations is a single rule of the catalogue."""
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    assert "rare-relation-for-lemma-and-pos" in RULE_CATALOG


def test_il_catalogo_e_quello_della_tabella_dello_studio():
    """The identifiers of the catalogue are those of the reference table of the study
    (``reproducibility/reference/checks_overview.csv``): no check more, no check less."""
    import csv
    from pathlib import Path
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    tabella = (Path(__file__).resolve().parents[1] / "reproducibility" / "reference"
               / "checks_overview.csv")
    with tabella.open(encoding="utf-8", newline="") as handle:
        identificatori = {riga["rule_id"] for riga in csv.DictReader(handle)}
    assert len(identificatori) == 77
    assert set(RULE_CATALOG) == identificatori


def test_il_diff_vede_esattamente_le_parole_cambiate(tokens, corrected):
    from greek_corpus_pipeline.analysis import compute_token_diff
    differenza = compute_token_diff(tokens, corrected)
    assert len(differenza) == 2
    # Because the form is corrected too, the comparison keeps it in two columns, like
    # the lemma and the label.
    forme = set(differenza["form_original"])
    assert forme == {"στρατιῶται", "ἄνδρες"}
    assert list(differenza["form_original"]) == list(differenza["form_corrected"])


def test_le_correzioni_manuali_si_applicano_sul_token_giusto(tokens, manual):
    from greek_corpus_pipeline.analysis import apply_manual_corrections
    risultato = apply_manual_corrections(tokens, manual)
    riga = risultato.loc[risultato["form"] == "στρατιῶται"].iloc[0]
    assert riga["lemma"] == "στρατιώτης"
    riga = risultato.loc[risultato["form"] == "ἄνδρες"].iloc[0]
    assert riga["postag"] == "n-p---mn-"
    # the other words stay where they were
    riga = risultato.loc[risultato["form"] == "πόλιν"].iloc[0]
    assert riga["lemma"] == "πόλις" and riga["postag"] == "n-s---fa-"


def test_il_confronto_con_un_modello_conta_gli_accordi(tokens, stanza_like):
    from greek_corpus_pipeline.analysis import compare_annotation_sets
    finto = tokens.copy()
    finto["lemma"] = stanza_like["lemma_stanza"].to_numpy()
    finto["postag"] = stanza_like["postag_stanza"].to_numpy()
    _, sintesi = compare_annotation_sets(tokens, finto, "stanza")
    assert sintesi["aligned_tokens"] == len(tokens)
    assert sintesi["lemma_matches"] == len(tokens) - 1
    assert sintesi["postag_matches"] == len(tokens) - 1


def test_l_esportazione_xml_si_rilegge_uguale(tmp_path, tokens):
    """Round trip: what I write I must be able to read back."""
    from greek_corpus_pipeline.xmlio import (
        export_corrected_xml, load_corpus_from_directory,
    )
    destinazione = tmp_path / "uscita"
    export_corrected_xml(tokens, destinazione)
    riletto = load_corpus_from_directory(destinazione)
    assert len(riletto) == len(tokens)
    assert list(riletto.sort_values(["sentence_id", "token_id"])["form"]) == \
        list(tokens.sort_values(["sentence_id", "token_id"])["form"])


def test_il_conllu_esce_con_dieci_campi_per_riga(tmp_path, tokens):
    from greek_corpus_pipeline.conllu import export_conllu
    scritti = export_conllu(tokens, tmp_path / "c.conllu", corpus_name="test")
    righe = [r for r in Path(scritti[0]).read_text(encoding="utf-8").splitlines()
             if r and not r.startswith("#")]
    assert righe, "no token row"
    for riga in righe:
        assert len(riga.split("\t")) == 10, riga


def test_i_modelli_si_allineano_a_blocchi_senza_sfasarsi(tokens):
    """Rewriting by blocks must not shift even one line."""
    from greek_corpus_pipeline import analyzers

    lavoro, inizi, forme = analyzers._model_input(tokens)
    assert len(inizi) - 1 == 2, "two sentences"
    assert len(forme) == len(tokens)

    finti_lemmi = [f.lower() for f in forme]
    finti_tag = ["TEST-----"] * len(forme)
    tenuti = [True] * len(forme)
    risultato = analyzers._assemble(lavoro, finti_lemmi, finti_tag, tenuti,
                                    "stanza", tokens.columns)
    assert list(risultato["form"]) == list(lavoro["form"])
    assert list(risultato["lemma"]) == finti_lemmi


def test_una_frase_risegmentata_viene_scartata_non_disallineata(tokens):
    from greek_corpus_pipeline import analyzers
    lavoro, inizi, forme = analyzers._model_input(tokens)
    prima = int(inizi[1]) - int(inizi[0])
    tenuti = [False] * prima + [True] * (len(forme) - prima)
    risultato = analyzers._assemble(
        lavoro, [f.lower() for f in forme], ["X"] * len(forme), tenuti,
        "stanza", tokens.columns)
    assert len(risultato) == len(forme) - prima
    assert list(risultato["form"]) == list(lavoro["form"].iloc[prima:])


def test_le_correzioni_reggono_le_chiavi_di_tipo_diverso(tokens, manual):
    """The CSV file comes back with a text token_id, the corpus has a numeric one.

    It is the case that would make “Apply every correction” fail with a merge
    error: the proof that the two keys meet all the same.
    """
    from greek_corpus_pipeline.analysis import apply_manual_corrections
    testuali = manual.astype(str)
    assert tokens["token_id"].dtype != object, "the corpus keeps a numeric token_id"
    risultato = apply_manual_corrections(tokens, testuali)
    riga = risultato.loc[risultato["form"] == "στρατιῶται"].iloc[0]
    assert riga["lemma"] == "στρατιώτης"


def test_una_correzione_vuota_non_cancella_il_valore(tokens, manual):
    """Correcting the lemma must not empty the label of that word."""
    from greek_corpus_pipeline.analysis import apply_manual_corrections
    risultato = apply_manual_corrections(tokens, manual)
    riga = risultato.loc[risultato["form"] == "στρατιῶται"].iloc[0]
    assert riga["postag"] == "n-p---mn-", "the tag was deleted"
    riga = risultato.loc[risultato["form"] == "ἄνδρες"].iloc[0]
    assert riga["lemma"] == "ἀνήρ", "the lemma was deleted"


def test_il_conllu_regge_un_riferimento_mancante(tmp_path, tokens):
    """An empty ref must not kill the export with TypeError."""
    from greek_corpus_pipeline.conllu import export_conllu
    import pandas as pd
    frame = tokens.copy()
    if "ref" not in frame.columns:
        frame["ref"] = pd.NA
    frame.loc[frame.index[:3], "ref"] = pd.NA
    scritti = export_conllu(frame, tmp_path / "c.conllu")
    assert Path(scritti[0]).read_text(encoding="utf-8").strip()


# ── the sentence with more than one root: from violation to case to check ───
def _frase_con_due_radici(tokens):
    """Detaches the second sentence from the first: two words with head 0."""
    frame = tokens.copy()
    frame.loc[frame["form"] == "ἦλθον", "head"] = 0
    return frame


def test_una_frase_con_piu_radici_viene_individuata(tokens):
    from greek_corpus_pipeline.syntax import analyze_syntax
    frame = tokens.copy()
    # in sentence 1 I also attach πόλιν to the root: two vertices
    mask = (frame["sentence_id"].astype(str) == "1") & (frame["form"] == "πόλιν")
    frame.loc[mask, "head"] = 0
    segnalazioni, _ = analyze_syntax(frame)
    regole = set(segnalazioni["rule_id"]) if not segnalazioni.empty else set()
    assert "sentence-many-roots" in regole, "the sentence with two roots is not flagged"


def test_la_frase_con_piu_radici_non_e_una_violazione(tokens):
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    regola = RULE_CATALOG["sentence-many-roots"]
    assert regola["class"] != "violazione", \
        "more than one root is not a certain violation: it may be the way an ellipsis is annotated"
    assert regola["class"] == "verifica"


def test_la_frase_con_piu_radici_non_viene_corretta_da_sola(tokens):
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG, auto_applicable_rule_ids
    regola = RULE_CATALOG["sentence-many-roots"]
    assert regola["treatment"] == "manuale"
    assert regola["default_auto_apply"] is False
    assert "sentence-many-roots" not in set(auto_applicable_rule_ids())


def test_la_frase_senza_radice_e_una_violazione():
    """A sentence with no root is a certain violation: the class of the rule on several
    roots does not extend to it."""
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    assert RULE_CATALOG["sentence-no-root"]["class"] == "violazione"


def test_la_classe_arriva_fino_alla_segnalazione(tokens):
    """What ends up in the exported report carries the class given by the catalogue."""
    from greek_corpus_pipeline.syntax import analyze_syntax
    from greek_corpus_pipeline.rule_catalog import rule_class, rule_severity
    frame = tokens.copy()
    mask = (frame["sentence_id"].astype(str) == "1") & (frame["form"] == "πόλιν")
    frame.loc[mask, "head"] = 0
    segnalazioni, _ = analyze_syntax(frame)
    righe = segnalazioni[segnalazioni["rule_id"] == "sentence-many-roots"]
    assert not righe.empty
    assert rule_class("sentence-many-roots") == "verifica"
    assert rule_severity("sentence-many-roots") == "sospetto", \
        "a finding to be checked cannot come out with severity “errore” (error)"
    if "severity" in righe.columns:
        assert set(righe["severity"]) == {"sospetto"}
    if "auto_correctable" in righe.columns:
        assert not righe["auto_correctable"].any()


def test_frase_con_piu_radici_e_un_caso_da_verificare():
    """The description does not promise an error: it says what to look at."""
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    regola = RULE_CATALOG["sentence-many-roots"]
    assert regola["class"] == "verifica"
    assert regola["treatment"] == "manuale"
    testo = regola["description"].lower()
    assert "una sola radice" in testo
    assert "può indicare" in testo


# ── three behaviours: MWE, double counting, register of decisions ────────
def test_mwe_e_una_relazione_dell_inventario():
    """It is documented by the 2.0 guidelines: flagging it would be a false positive."""
    from greek_corpus_pipeline.agdt_schema import RELATIONS, is_known_relation
    assert "MWE" in RELATIONS
    assert is_known_relation("MWE")
    assert is_known_relation("MWE_CO"), "the coordination suffix must hold"


def test_un_carattere_con_regola_propria_non_e_contato_due_volte(tokens):
    """The degree “p” is told by grade-p: invalid-character must stay silent."""
    from greek_corpus_pipeline.postag import analyze_postags
    frame = tokens.copy()
    frame.loc[frame.index[0], "postag"] = "a-s---mnp"     # explicit positive degree
    segnalazioni = analyze_postags(frame)
    riga = (segnalazioni["document_id"].astype(str) == str(frame.iloc[0]["document_id"])) \
        & (segnalazioni["token_id"].astype(str) == str(frame.iloc[0]["token_id"]))
    regole = set(segnalazioni.loc[riga, "rule_id"])
    assert "grade-p" in regole
    assert "invalid-character" not in regole, \
        "the same fact counted once as a violation and once as a variant"


def test_il_trattino_basso_nel_grado_lo_racconta_una_regola_sola(tokens):
    from greek_corpus_pipeline.postag import analyze_postags
    frame = tokens.copy()
    frame.loc[frame.index[0], "postag"] = "a-s---mn_"
    segnalazioni = analyze_postags(frame)
    riga = (segnalazioni["document_id"].astype(str) == str(frame.iloc[0]["document_id"])) \
        & (segnalazioni["token_id"].astype(str) == str(frame.iloc[0]["token_id"]))
    regole = set(segnalazioni.loc[riga, "rule_id"])
    assert "degree-underscore" in regole
    assert "invalid-character" not in regole


def test_un_carattere_senza_regola_propria_viene_segnalato(tokens):
    """The exclusion must not switch off the general check."""
    from greek_corpus_pipeline.postag import analyze_postags
    frame = tokens.copy()
    frame.loc[frame.index[0], "postag"] = "a-s---mnZ"     # no other check reports Z
    segnalazioni = analyze_postags(frame)
    riga = (segnalazioni["document_id"].astype(str) == str(frame.iloc[0]["document_id"])) \
        & (segnalazioni["token_id"].astype(str) == str(frame.iloc[0]["token_id"]))
    assert "invalid-character" in set(segnalazioni.loc[riga, "rule_id"])


def test_il_registro_delle_decisioni_dice_quando_perche_e_da_chi(tokens):
    from greek_corpus_pipeline.gold import MANUAL_COLUMNS, manual_record
    riga = dict(tokens.iloc[0])
    riga["rule_id"] = "lemma-tool-numbering"
    record = manual_record(riga, lemma="στρατιώτης",
                           decided_by="YI", reason="numero del programma in coda")
    assert list(record.columns) == MANUAL_COLUMNS
    solo = record.iloc[0]
    assert solo["decided_by"] == "YI"
    assert solo["reason"].startswith("numero")
    assert solo["rule_id"] == "lemma-tool-numbering"
    assert solo["status"] == "accettata"
    assert solo["previous_lemma"] == str(riga["lemma"]), "the starting value is lost"
    assert solo["decided_at"] and "T" in solo["decided_at"]
    assert solo["program_version"]


def test_un_registro_a_sette_colonne_si_rilegge_senza_rompersi(tmp_path):
    """A file with the seven columns of the base format is completed on reading."""
    import pandas as pd
    from greek_corpus_pipeline.gold import (
        BASE_MANUAL_COLUMNS, MANUAL_COLUMNS, ensure_manual_columns,
    )
    base = pd.DataFrame([{c: "x" for c in BASE_MANUAL_COLUMNS}])
    completo = ensure_manual_columns(base)
    assert list(completo.columns) == MANUAL_COLUMNS
    assert completo.iloc[0]["form"] == "x"
    assert completo.iloc[0]["decided_by"] == ""


def test_le_correzioni_si_applicano_col_registro_completo(tokens):
    """The extra columns must not confuse whoever applies the corrections."""
    from greek_corpus_pipeline.analysis import apply_manual_corrections
    from greek_corpus_pipeline.gold import manual_record
    riga = dict(tokens.loc[tokens["form"] == "στρατιῶται"].iloc[0])
    record = manual_record(riga, lemma="στρατιώτης", decided_by="YI", reason="prova")
    risultato = apply_manual_corrections(tokens, record)
    corretta = risultato.loc[risultato["form"] == "στρατιῶται"].iloc[0]
    assert corretta["lemma"] == "στρατιώτης"


# ── GLAUx: a third treebank with different conventions ──────────────────────

GLAUX_XML = """<treebank version="2" xml:lang="grc">
  <sentence struct_id="1" id="1" document_id="0029-004" analysis="auto">
    <word id="103436030" form="ὁ" lemma="ὁ" postag="l-s---mn-" head="103436032" relation="ATR"/>
    <word id="103436032" form="δημαγωγὸς" lemma="δημαγωγός" postag="n-s---mn-" head="103436051" relation="SBJ"/>
    <word id="103436051" form="ἐξελήλεγκται" lemma="ἐξελέγχω" postag="v3srpp---" head="0" relation="PRED"/>
    <word id="103436034" form="," lemma="," postag="u--------" head="0" relation="AuxX"/>
    <word id="103436099" form="E" lemma="E" postag="z--------" head="103436051" relation="ADV" artificial="elliptic"/>
  </sentence>
  <sentence struct_id="2" id="2" document_id="0029-004" analysis="manual">
    <word id="103436100" form="τέκνον" lemma="τέκνον" postag="n-s---nv-" head="0" relation="PRED"/>
  </sentence>
</treebank>"""


def _glaux_tokens(tmp_path):
    from greek_corpus_pipeline.xmlio import parse_treebank_xml
    percorso = tmp_path / "0029-004.xml"
    percorso.write_text(GLAUX_XML, encoding="utf-8")
    return parse_treebank_xml(percorso, corpus_name="glaux")


def test_gli_identificativi_globali_di_glaux_si_leggono(tmp_path):
    """In GLAUx the @id does not restart from 1 at every sentence: it is a number of the
    corpus."""
    t = _glaux_tokens(tmp_path)
    assert len(t) == 6
    prima = t[t["sentence_id"] == "1"]
    assert list(prima["token_index"]) == [1, 2, 3, 4, 5], "the position in the sentence is 1..n"
    assert prima["token_id"].min() > 100_000, "the identifier stays the one from the file"
    assert t["tlg_author"].iloc[0] == "tlg0029" and t["tlg_work"].iloc[0] == "tlg004"


def test_la_testa_si_risolve_anche_con_identificativi_globali(tmp_path):
    """head points to an @id, not to a position: the lookup must cope with it."""
    from greek_corpus_pipeline.syntax import _prepare, build_head_index
    work = _prepare(_glaux_tokens(tmp_path))
    indice = build_head_index(work)
    riga_ho = work.index[work["form"] == "ὁ"][0]
    riga_dem = work.index[work["form"] == "δημαγωγὸς"][0]
    assert indice.loc[riga_ho] == work.index.get_loc(riga_dem), \
        "ὁ depends on δημαγωγὸς, not on row number 103436032"


def test_glaux_dichiara_quali_frasi_sono_a_mano(tmp_path):
    """analysis="auto"/"manual": without it, the two kinds of annotation get mixed up."""
    t = _glaux_tokens(tmp_path)
    assert "annotation_mode" in t.columns
    assert set(t["annotation_mode"]) == {"auto", "manual"}
    assert (t["annotation_mode"] == "manual").sum() == 1


def test_il_filtro_toglie_i_nodi_ellittici_dichiarati(tmp_path):
    """The GLAUx placeholder is not “[0]”: it is declared by the attribute."""
    from gui_qt.workers import filter_tokens
    t = _glaux_tokens(tmp_path)
    tenuti, tolti = filter_tokens(t, {"exclude_placeholders": True})
    assert tolti == 1, "the artificial=elliptic node must be excluded even if the form is “E”"
    assert "E" not in set(tenuti["form"])
    tenuti_tutti, tolti_zero = filter_tokens(t, {"exclude_placeholders": False})
    assert tolti_zero == 0 and len(tenuti_tutti) == len(t)


def test_il_filtro_toglie_anche_la_parola_aggiunta_dall_annotatore():
    """Gorman writes ἐστιν on an elliptical node: it must stay out of the diagnosis."""
    import pandas as pd
    from gui_qt.workers import filter_tokens
    t = pd.DataFrame([
        {"form": "ἐστιν", "artificial": "elliptic", "postag": "v3spia---"},
        {"form": "[0]",   "artificial": "elliptic", "postag": None},
        {"form": "λόγος", "artificial": None,       "postag": "n-s---mn-"},
    ])
    tenuti, tolti = filter_tokens(t, {"exclude_placeholders": True})
    assert tolti == 2 and list(tenuti["form"]) == ["λόγος"]


def test_l_esportazione_non_perde_la_dichiarazione_di_glaux(tmp_path):
    """A corpus that says which sentences are manual must not lose that information by
    passing through here."""
    from greek_corpus_pipeline.xmlio import export_corrected_xml
    t = _glaux_tokens(tmp_path)
    scritti = export_corrected_xml(t, tmp_path / "out", version="2")
    testo = scritti[0].read_text(encoding="utf-8")
    assert 'analysis="auto"' in testo and 'analysis="manual"' in testo


# ── Consistency of the taxonomy: one fact, one class ────────────────────────

def _tag_frame(righe):
    import pandas as pd
    return pd.DataFrame([
        {"document_id": "d", "sentence_id": "1", "token_id": i + 1,
         "token_index": i + 1, "form": forma, "lemma": forma,
         "postag": tag, "relation": "ATR", "head": 0}
        for i, (forma, tag) in enumerate(righe)])


def test_il_trattino_basso_e_un_fatto_solo_in_ogni_casella():
    """`a-_---___` must not produce one variant and three violations for a single fact."""
    from greek_corpus_pipeline.postag import analyze_postags
    esito = analyze_postags(_tag_frame([("τριάκοντα", "a-_---___")]))
    regole = list(esito["rule_id"])
    assert "invalid-character" not in regole, \
        "the underscore has a rule of its own at every position"
    assert regole.count("underscore-person-number") == 1, \
        "one finding per token, not one per slot"
    proposta = esito.loc[esito.rule_id == "underscore-person-number",
                         "suggested_postag"].iloc[0]
    assert proposta == "a-----" + "---", f"unexpected proposal: {proposta}"


def test_la_b_di_pedalion_non_e_una_violazione():
    """The Pedalion README declares it: it is a case to check, not an error."""
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    esito = analyze_postags(_tag_frame([("καὶ", "b--------")]))
    regole = set(esito["rule_id"])
    assert "pedalion-b-pos" in regole and "invalid-character" not in regole
    # Class: “systematic variant”, not “case to check”.  The value does not violate the
    # scheme: it extends it with a convention that the project declares, which is
    # exactly what a systematic variant records.
    assert RULE_CATALOG["pedalion-b-pos"]["class"] == "variante"
    assert RULE_CATALOG["pedalion-b-pos"]["treatment"] == "manuale"
    # The name does not carry the name of the corpus on which the rule was written.
    assert "Pedalion" not in RULE_CATALOG["pedalion-b-pos"]["name"]
    assert "Pedalion" not in RULE_CATALOG["pedalion-b-pos"]["name_en"]
    assert RULE_CATALOG["pedalion-b-pos"]["treatment"] == "manuale"
    assert esito.loc[esito.rule_id == "pedalion-b-pos", "auto_correctable"].iloc[0] is False \
        or not bool(esito.loc[esito.rule_id == "pedalion-b-pos", "auto_correctable"].iloc[0])


def test_il_genere_comune_c_e_un_caso_da_verificare():
    """The “c” of the gender does not pass in silence: it has a check of its own."""
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    esito = analyze_postags(_tag_frame([("ἐγώ", "p1s---cn-")]))
    regole = list(esito["rule_id"])
    assert "common-gender-c" in regole
    assert "invalid-character" not in regole, \
        "the generic check must stay silent where the dedicated one speaks"
    assert regole.count("common-gender-c") == 1
    assert RULE_CATALOG["common-gender-c"]["class"] == "verifica"
    assert RULE_CATALOG["common-gender-c"]["treatment"] == "manuale"
    riga = esito.loc[esito.rule_id == "common-gender-c"].iloc[0]
    assert not bool(riga["auto_correctable"])
    import pandas as pd
    assert pd.isna(riga["suggested_postag"]), "no correction proposed"


def test_maschile_e_femminile_restano_ammessi_nel_genere():
    """The check looks at the “c”, not at the gender: m, f and n make no noise."""
    from greek_corpus_pipeline.postag import analyze_postags
    esito = analyze_postags(_tag_frame([
        ("ἀνήρ", "n-s---mn-"), ("γυνή", "n-s---fn-"), ("ἔργον", "n-s---nn-")]))
    regole = set(esito["rule_id"])
    assert "common-gender-c" not in regole
    assert "invalid-character" not in regole


def test_il_genere_comune_vale_per_qualunque_lemma():
    """The check looks at the value, not at the word: βοῦς has no rule of its own."""
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    esito = analyze_postags(_tag_frame([
        ("βοῦς", "n-s---cn-"), ("παῖς", "n-s---cn-"), ("τις", "p-s---cn-")]))
    assert list(esito["rule_id"]).count("common-gender-c") == 3


def test_bous_marcato_maschile_non_e_una_segnalazione():
    """βοῦς in the masculine is a legitimate analysis: the catalogue does not ask for it."""
    from greek_corpus_pipeline.postag import analyze_postags
    esito = analyze_postags(_tag_frame([("βοῦς", "n-s---mn-")]))
    assert esito.empty


def test_la_z_marca_un_record_non_lessicale():
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    esito = analyze_postags(_tag_frame([("G?", "z--------")]))
    assert "nonlexical-z-pos" in set(esito["rule_id"])
    assert "invalid-character" not in set(esito["rule_id"])
    assert RULE_CATALOG["nonlexical-z-pos"]["class"] == "verifica"


def test_il_luogo_contestato_di_dein_ha_una_regola_propria():
    """The class is a property of the rule: two outcomes, two identifiers."""
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    assert RULE_CATALOG["dein-participle"]["class"] == "violazione"
    assert RULE_CATALOG["dein-participle"]["treatment"] == "automatica"
    assert RULE_CATALOG["dein-participle-disputed"]["class"] == "verifica"
    assert RULE_CATALOG["dein-participle-disputed"]["treatment"] == "manuale"


# ── The declared GLAUx sample ───────────────────────────────────────────────

def test_il_campione_glaux_e_completo_e_coerente():
    from greek_corpus_pipeline import glaux_sample as gs
    testi = gs.load_sample()
    assert len(testi) == 40, "twenty texts per sample, two samples"
    for campione, atteso in (("principale", 20), ("conferma", 20)):
        assert len([t for t in testi if t.campione == campione]) == atteso
    assert {t.strato for t in testi} == {"automatico", "manuale"}
    assert len({t.tlg for t in testi}) == 40, "no text appears twice"
    for t in testi:
        assert t.percorso == f"xml/{t.tlg}.xml"
        assert t.token_dichiarati > 0


def test_i_due_campioni_non_si_sovrappongono():
    from greek_corpus_pipeline import glaux_sample as gs
    principale = {t.tlg for t in gs.select("principale", None)}
    conferma = {t.tlg for t in gs.select("conferma", None)}
    assert not (principale & conferma), \
        "the confirmation sample must be disjoint from the main one"


def test_nessun_autore_del_campione_sta_in_gorman_o_pedalion():
    """It is the requirement that makes the test valid: without it, it is circular."""
    import pandas as pd
    from greek_corpus_pipeline import glaux_sample as gs
    # The 37 author identifiers derived from the two corpora in the deposited version.
    gorman = pd.DataFrame({"tlg_author": [
        "tlg0003", "tlg0006", "tlg0007", "tlg0008", "tlg0009", "tlg0010",
        "tlg0014", "tlg0016", "tlg0019", "tlg0026", "tlg0028", "tlg0032",
        "tlg0058", "tlg0059", "tlg0086", "tlg0093"]})
    pedalion = pd.DataFrame({"tlg_author": [
        "tlg0007", "tlg0010", "tlg0014", "tlg0026", "tlg0041", "tlg0059",
        "tlg0060", "tlg0062", "tlg0081", "tlg0096", "tlg0343", "tlg0526",
        "tlg0537", "tlg0540", "tlg0541", "tlg0543", "tlg0544", "tlg0551",
        "tlg0554", "tlg0557", "tlg0559", "tlg0561", "tlg0585", "tlg1220",
        "tlg2003", "tlg4029"]})
    vietati = gs.overlapping_tlg_ids(gorman, pedalion)
    assert len(vietati) == 37, f"37 authors expected, found {len(vietati)}"
    violazioni = gs.check_no_overlap(vietati)
    assert violazioni == [], \
        f"these sample texts share the author with Gorman or Pedalion: {violazioni}"


def test_la_selezione_del_campione_rifiuta_le_richieste_senza_senso():
    import pytest
    from greek_corpus_pipeline import glaux_sample as gs
    with pytest.raises(ValueError):
        gs.select("inesistente", "automatico")
    with pytest.raises(ValueError):
        gs.select("principale", "inesistente")


def test_lo_scaricamento_chiede_esattamente_i_file_del_campione(tmp_path, monkeypatch):
    """The network is not needed for the test: the call is intercepted and the list is
    looked at."""
    from greek_corpus_pipeline import github, glaux_sample as gs
    chiamate = []

    def finto_urlretrieve(url, destinazione):
        chiamate.append(url)
        Path(destinazione).write_text("<treebank/>", encoding="utf-8")

    monkeypatch.setattr(github.urllib.request, "urlretrieve", finto_urlretrieve)
    cartella = gs.download(tmp_path, "principale", "automatico")
    attesi = gs.select("principale", "automatico")
    assert len(chiamate) == len(attesi) == 18
    for testo in attesi:
        atteso = (f"https://raw.githubusercontent.com/{gs.GLAUX_OWNER}/"
                  f"{gs.GLAUX_REPO}/{gs.GLAUX_BRANCH}/xml/{testo.tlg}.xml")
        assert atteso in chiamate, f"not requested: {testo.tlg}"
    assert len(list(cartella.glob("*.xml"))) == 18


def test_un_file_gia_scaricato_non_si_riscarica(tmp_path, monkeypatch):
    from greek_corpus_pipeline import github, glaux_sample as gs
    chiamate = []
    monkeypatch.setattr(github.urllib.request, "urlretrieve",
                        lambda url, dest: (chiamate.append(url),
                                           Path(dest).write_text("<treebank/>", encoding="utf-8")))
    gs.download(tmp_path, "principale", "manuale")
    prima = len(chiamate)
    gs.download(tmp_path, "principale", "manuale")
    assert len(chiamate) == prima, "the second time nothing must be downloaded again"


# ── The two columns that contradicted each other ────────────────────────────

def test_la_gravita_viene_dalla_classe_e_non_la_contraddice():
    """“3 — Caso da verificare” (“3 — Case to check”) next to “errore” (“error”) would be a
    row that contradicts itself."""
    from greek_corpus_pipeline.rule_catalog import (
        CLASS_SEVERITY, RULE_CATALOG, rule_severity,
    )
    for identificatore, regola in RULE_CATALOG.items():
        atteso = CLASS_SEVERITY[regola["class"]]
        assert rule_severity(identificatore) == atteso, identificatore
    assert rule_severity("a-check-that-is-not-in-the-catalogue") == "sospetto"
    assert rule_severity("unicode-not-nfc") == "sospetto"
    assert rule_severity("missing-postag") == "errore"


def test_nessuna_segnalazione_esce_con_una_gravita_sbagliata(tokens):
    import pandas as pd
    from greek_corpus_pipeline.rule_catalog import rule_severity
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.lemma import analyze_lemmas
    from greek_corpus_pipeline.syntax import analyze_syntax
    from greek_corpus_pipeline.agreement import analyze_agreement
    from greek_corpus_pipeline.orthography import analyze_orthography
    pezzi = []
    for funzione in (analyze_postags, analyze_syntax, analyze_agreement,
                     analyze_orthography, analyze_lemmas):
        try:
            esito_funzione = funzione(tokens)
        except Exception:
            continue
        # orthography returns a pair, the others a single DataFrame
        if isinstance(esito_funzione, tuple):
            pezzi.extend(x for x in esito_funzione if isinstance(x, pd.DataFrame))
        elif isinstance(esito_funzione, pd.DataFrame):
            pezzi.append(esito_funzione)
    esito = pd.concat([p for p in pezzi if p is not None and not p.empty],
                      ignore_index=True) if pezzi else pd.DataFrame()
    if esito.empty or "severity" not in esito.columns:
        return
    esito = esito[esito["severity"].notna()]
    sbagliate = esito[esito["severity"] != esito["rule_id"].map(rule_severity)]
    assert sbagliate.empty, \
        f"severity in conflict with the class: {set(sbagliate['rule_id'])}"


def _forma_con_due_lemmi():
    import pandas as pd
    return pd.DataFrame([
        {"document_id": "d", "sentence_id": "1", "token_id": i + 1,
         "token_index": i + 1, "form": "κυρία", "lemma": lemma,
         "postag": "a-s---fn-", "relation": "ATR", "head": 0}
        for i, lemma in enumerate(["κυρία", "κύριος", "κυρία"])])


def test_una_forma_con_piu_lemmi_non_e_una_segnalazione():
    """In Greek homography is normal: describing it is not diagnosing it.

    In Gorman there are about 2,500 such forms, and with the part of speech in the key
    about 2,100 remain: it is not a defect that shrinks by adding information.
    """
    from greek_corpus_pipeline.lemma import analyze_lemmas
    esito = analyze_lemmas(_forma_con_due_lemmi())
    assert esito.empty


def test_le_forme_ambigue_sono_disponibili_come_statistica():
    """The information is in the statistics: it lists all the lemmas."""
    from greek_corpus_pipeline.lemma import ambiguous_forms, normalize_lemma
    frame = _forma_con_due_lemmi()
    frame["normalized_lemma"] = frame["lemma"].map(normalize_lemma)
    tabella = ambiguous_forms(frame)
    assert len(tabella) == 1, "one row per form, not per occurrence"
    riga = tabella.iloc[0]
    assert riga["forma"] == "κυρία"
    assert riga["n_lemmi"] == 2
    assert riga["occorrenze"] == 3
    assert "κυρία" in riga["lemmi"] and "κύριος" in riga["lemmi"]

def test_la_relazione_rara_si_misura_su_lemma_e_pos():
    """The merged check: profile and domain coincide, no PoS excluded.

    The group is (lemma, part of speech) and the outcome is the base relation.  A
    unanimous pair says nothing; the exception under one per cent does.
    """
    from greek_corpus_pipeline.agreement import check_rare_relation

    def corpus(relazioni, pos="d"):
        n = len(relazioni)
        return pd.DataFrame({
            "source_file": ["f.xml"] * n,
            "document_id": ["d"] * n,
            "sentence_index": list(range(n)),
            "sentence_id": list(range(n)),
            "token_index": [1] * n,
            "token_id": [1] * n,
            "form": ["δέ"] * n,
            "lemma": ["δέ"] * n,
            "postag": [f"{pos}--------"] * n,
            "relation": relazioni,
            "head": [0] * n,
        })

    def conta(frame):
        return int(len(check_rare_relation(frame)))

    # Unanimous, and above the minimum support: nothing to say.
    assert conta(corpus(["AuxY"] * 300)) == 0
    # Two hundred and ninety-nine AuxY and one ADV: 0.33%, below one per cent.
    assert conta(corpus(["AuxY"] * 299 + ["ADV"])) == 1
    # Below the minimum support nothing is said, not even with the exception.
    assert conta(corpus(["AuxY"] * 99 + ["ADV"])) == 0
    # Above one per cent the relation is not rare.
    assert conta(corpus(["AuxY"] * 280 + ["ADV"] * 20)) == 0


def test_la_relazione_rara_non_esclude_nessuna_parte_del_discorso():
    """The profile covers every PoS, not only g, c and d: the article is seen too."""
    from greek_corpus_pipeline.agreement import check_rare_relation
    n = 300
    frame = pd.DataFrame({
        "source_file": ["f.xml"] * n, "document_id": ["d"] * n,
        "sentence_index": list(range(n)), "sentence_id": list(range(n)),
        "token_index": [1] * n, "token_id": [1] * n,
        "form": ["τοῦ"] * n, "lemma": ["ὁ"] * n,
        "postag": ["l-s---mg-"] * n,          # article: outside g, c, d
        "relation": ["ATR"] * 299 + ["ADV"],
        "head": [0] * n,
    })
    assert len(check_rare_relation(frame)) == 1


def test_la_relazione_rara_usa_la_relazione_di_base():
    """ATR_CO and ATR are the same relation: the suffixes do not make rarity."""
    from greek_corpus_pipeline.agreement import check_rare_relation
    n = 300
    frame = pd.DataFrame({
        "source_file": ["f.xml"] * n, "document_id": ["d"] * n,
        "sentence_index": list(range(n)), "sentence_id": list(range(n)),
        "token_index": [1] * n, "token_id": [1] * n,
        "form": ["δέ"] * n, "lemma": ["δέ"] * n, "postag": ["d--------"] * n,
        "relation": ["ATR"] * 299 + ["ATR_CO"],
        "head": [0] * n,
    })
    assert len(check_rare_relation(frame)) == 0

def test_il_campione_glaux_risolve_i_metadati():
    """The authors of the GLAUx sample are not in the curated catalogue."""
    from greek_corpus_pipeline.corpus_metadata import resolve_glaux

    record = resolve_glaux(document_id="0011-004")
    assert record is not None
    assert record["author_en"] == "Sophocles"
    assert record["work_en"] == "Oedipus tyrannus"
    assert record["genre"] == "Tragedy"
    assert record["period"] == "Classical"
    # and also by TLG identifier, as xmlio writes it
    assert resolve_glaux(tlg_author="tlg0011", tlg_work="tlg004") is not None


def test_i_numerali_indeclinabili_non_chiedono_genere_ne_caso():
    """Also when the corpus is written in NFD."""
    import unicodedata
    from greek_corpus_pipeline.agdt_schema import is_indeclinable_numeral
    from greek_corpus_pipeline.postag import _is_alphabetic_numeral

    for parola in ("ὀκτώ", "δεκαέξ", "ἑξκαίδεκα", "τριάκοντα"):
        assert is_indeclinable_numeral(parola), parola
        assert is_indeclinable_numeral(unicodedata.normalize("NFD", parola)), parola
    # τρεῖς is declined and remains reportable
    assert not is_indeclinable_numeral("τρεῖς")
    # abbreviations and alphabetic numerals
    for sigla in ("αβγδεʹ", "͵αφʹ", "σξδʹ", "ΑΒΓ", "ΘΗΚ", "β"):
        assert _is_alphabetic_numeral(sigla), sigla
    # but not short words without an accent: they are not alphabetic numerals
    for parola in ("δε", "τε", "τις", "ΑΝΘΡΩΠΟΣ"):
        assert not _is_alphabetic_numeral(parola), parola


def test_la_tabella_delle_occorrenze_mostra_tutte_le_letture():
    """Whoever reads a type-level finding must see the competing readings."""
    import pandas as pd
    from greek_corpus_pipeline.evidence import grouping_field, readings

    tokens = pd.DataFrame({
        "document_id": ["d"] * 5,
        "sentence_id": ["1", "1", "2", "2", "3"],
        "token_id": ["1", "2", "3", "4", "5"],
        "form": ["τοῦ", "τοῦ", "τοῦ", "τοῦ", "ἄλλο"],
        "lemma": ["ὁ", "ὁ", "τίς", "ὁ", "ἄλλος"],
        "postag": ["l-s---mg-", "l-s---mg-", "p-s---ng-", "l-s---ng-", "a-s---nn-"],
        "relation": ["ATR", "ATR", "ATR", "ATR", "SBJ"],
    })
    tabella, resto = readings(tokens, "τοῦ", "form")
    assert resto == 0
    assert len(tabella) == 3
    assert int(tabella["occorrenze"].max()) == 2
    assert set(tabella["lemma"]) == {"ὁ", "τίς"}
    assert tabella["esempio"].iloc[0].startswith("d")
    # the checks on the lemma group on the lemma
    assert grouping_field("uninflected-lemma") == "lemma"
    assert grouping_field("agreement-modifier") == "form"


def test_le_decisioni_prese_sulle_linee_guida_restano_fisse():
    """The decisions taken by checking the AGDT guidelines stay fixed here."""
    from greek_corpus_pipeline.agdt_schema import SLOT_PROFILE, slot_profile
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG
    from greek_corpus_pipeline.syntax import (
        TRANSPARENT_FOR_COORDINATION, TRANSPARENT_RELATIONS,
    )

    # The numeral has no obligatory features: the guidelines do not ask for them.
    assert SLOT_PROFILE["m"]["require"] == frozenset()
    # The noun does: “annotated for gender, number, and case”.
    assert len(SLOT_PROFILE["n"]["require"]) == 3
    # The climb towards the COORD also crosses correlative conjunctions.
    assert "AuxY" in TRANSPARENT_FOR_COORDINATION
    assert "AuxY" not in TRANSPARENT_RELATIONS
    # OBJ in the nominative is a case to check, not a violation.
    assert RULE_CATALOG["case-object"]["class"] == "verifica"
    # The completely empty label is a case to check; the incomplete one is not.
    assert RULE_CATALOG["slot-missing-bare"]["class"] == "verifica"
    assert RULE_CATALOG["slot-missing"]["class"] == "violazione"
    # The encoding of the whole corpus is a variant, and the conversion to NFC is a
    # proposal that the program writes: the user accepts it or not.
    assert RULE_CATALOG["corpus-not-nfc"]["class"] == "variante"
    assert RULE_CATALOG["corpus-not-nfc"]["treatment"] == "automatica"
    assert RULE_CATALOG["corpus-not-nfc"]["default_auto_apply"] is True


def test_nessuna_riparazione_propone_una_violazione():
    """An automatic correction that introduces a violation is not a correction.

    A tag with gender and case filled in on a finite-mood verb and the person empty, for
    instance, would be flagged by the program itself.  Every tag that a lexical repair
    proposes must therefore pass through the same checks that apply to the corpus, and
    none of them may be flagged for anything but the lexical reasons listed below.
    """
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import LEXICAL_REPAIRS

    righe = [{
        "source_file": "prova.xml", "document_id": "d", "sentence_index": n,
        "sentence_id": n, "token_index": 1, "token_id": 1,
        "form": riga.get("form") or "λόγος", "lemma": "λόγος",
        "postag": riga["suggest"], "relation": "ATR", "head": 0,
    } for n, riga in enumerate(LEXICAL_REPAIRS)]
    esito = analyze_postags(pd.DataFrame(righe))

    # Indeclinable nouns stay without number and case for lexical reasons: it is
    # the only flag that a proposal may legitimately carry along, and the catalogue
    # classifies it as a case to check.
    ammesse = {"slot-missing", "slot-missing-bare", "uninflected-lemma"}
    colpevoli = sorted(set(esito.loc[~esito["rule_id"].isin(ammesse), "rule_id"]))
    assert not colpevoli, f"proposals that the program itself would flag: {colpevoli}"


def test_nessun_token_riceve_due_proposte_automatiche_diverse():
    """Two automatic corrections must never conflict on the same token.

    A token whose tag has the mood “g” must not receive both the proposal of
    “participle-mood-g”, which proposes the participle, and that of the rule on the
    verbal adjective, which proposes the adjective and asks not to touch: the catalogue
    would contradict itself, and the counts would count the same fact twice in two
    different classes.
    """
    import pandas as pd
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG

    casi = [
        # form, label: the five profiles with mood “g” observed in the corpora
        ("ποιητέον", "v-s-g-nn-"), ("πρακτέον", "v-s-g-na-"),
        ("ποιητέα", "v-p-g-nn-"), ("διωκτέος", "v-s-g-mn-"),
        ("ποιητέοι", "v-p-g-mn-"),
        ("ἔχων", "v-spgamn-"), ("οὖσα", "v-spgafn-"),
        ("ὀσφράνθητι", "v-sagpnd-"),
    ]
    tokens = pd.DataFrame({
        "document_id": ["d"] * len(casi),
        "sentence_id": [str(i) for i in range(len(casi))],
        "sentence_index": list(range(len(casi))),
        "token_id": list(range(1, len(casi) + 1)),
        "token_index": list(range(len(casi))),
        "form": [f for f, _ in casi],
        "lemma": [f for f, _ in casi],
        "postag": [t for _, t in casi],
        "relation": ["ATR"] * len(casi),
        "head": [0] * len(casi),
        "source_file": ["d.xml"] * len(casi),
    })
    findings = analyze_postags(tokens)
    if findings.empty:
        return
    auto = findings[findings["auto_correctable"].fillna(False)]
    chiave = ["document_id", "sentence_id", "token_id"]
    for _, gruppo in auto.groupby(chiave):
        proposte = set(gruppo["suggested_postag"].dropna())
        assert len(proposte) <= 1, (
            gruppo[["rule_id", "form", "postag", "suggested_postag"]].to_dict("records"))


def test_il_csv_del_catalogo_e_una_vista_del_catalogo():
    """The distributed CSV must say what the program executes.

    It is regenerated with ``tools_regenerate_catalogue.py``, so that it cannot declare
    a number of checks different from that of the catalogue, and this test verifies it.
    """
    import csv
    from pathlib import Path
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG

    percorso = Path(__file__).resolve().parent.parent / "data" / "catalogo_controlli.csv"
    with percorso.open(encoding="utf-8-sig", newline="") as sorgente:
        righe = list(csv.DictReader(sorgente, delimiter=";"))

    assert len(righe) == len(RULE_CATALOG) == 77
    assert {riga["id"] for riga in righe} == set(RULE_CATALOG)
    for riga in righe:
        regola = RULE_CATALOG[riga["id"]]
        assert riga["nome"] == regola["name"]
        assert riga["classe"] == regola["class"]
        assert riga["trattamento"] == regola["treatment"]
