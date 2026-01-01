"""The scientific lists as versioned data resources."""
from __future__ import annotations

import json

import pytest

from greek_corpus_pipeline import resources


CAMPI_OBBLIGATORI = ("id", "nome", "name_en", "versione", "funzione",
                     "usata_da", "fonte", "voci")


def test_ogni_lista_dichiara_tutti_i_campi():
    """A list without a motivation is an opaque constant under another name."""
    disponibili = resources.available()
    assert disponibili, "no list found in data/liste"
    for identificatore in disponibili:
        risorsa = resources.load(identificatore)
        for campo in CAMPI_OBBLIGATORI:
            assert campo in risorsa, f"{identificatore} has no “{campo}”"
            assert risorsa[campo] not in ("", [], {}), \
                f"{identificatore}: “{campo}” is empty"
        assert risorsa["id"] == identificatore


def test_la_versione_e_semantica():
    for identificatore in resources.available():
        versione = resources.load(identificatore)["versione"]
        parti = versione.split(".")
        assert len(parti) == 3, f"{identificatore}: versione «{versione}»"
        assert all(parte.isdigit() for parte in parti), identificatore


def test_il_checksum_dipende_dal_contenuto_e_non_dai_metadati(tmp_path, monkeypatch):
    """Renaming a list does not change its fingerprint; removing an entry does."""
    directory = tmp_path / "liste"
    directory.mkdir()
    base = {"id": "prova", "nome": "Prova", "name_en": "Test",
            "versione": "1.0.0", "funzione": "f", "usata_da": ["x"],
            "fonte": "y", "voci": ["α", "β", "γ"]}
    (directory / "prova.json").write_text(json.dumps(base, ensure_ascii=False),
                                          encoding="utf-8")
    monkeypatch.setattr(resources, "DIRECTORY", directory)
    resources.load.cache_clear()
    primo = resources.checksum("prova")

    base["nome"] = "Un altro nome"
    base["fonte"] = "una motivazione riscritta"
    (directory / "prova.json").write_text(json.dumps(base, ensure_ascii=False),
                                          encoding="utf-8")
    resources.load.cache_clear()
    assert resources.checksum("prova") == primo

    base["voci"] = ["α", "β"]
    (directory / "prova.json").write_text(json.dumps(base, ensure_ascii=False),
                                          encoding="utf-8")
    resources.load.cache_clear()
    assert resources.checksum("prova") != primo
    resources.load.cache_clear()


def test_una_lista_che_manca_e_un_errore_non_un_insieme_vuoto():
    """A check without its list must not produce zero findings."""
    with pytest.raises(KeyError, match="does not exist"):
        resources.load("una-lista-che-non-esiste")


def test_le_liste_collegate_hanno_il_contenuto_atteso():
    """Moving them out of the code must change no content."""
    from greek_corpus_pipeline import agdt_schema, lemma, orthography, postag, stats

    assert len(stats.GRAMMATICAL_LEMMAS) == 136
    assert len(stats.PARTICLE_LEMMAS) == 56
    assert len(postag.FIRST_PERSON_FORMS) == 11
    assert len(postag.SECOND_PERSON_FORMS) == 9
    assert len(postag.THIRD_PERSON_FORMS) == 16
    assert len(orthography.ENCLITICS) == 82
    assert len(agdt_schema.INDECLINABLE_NUMERAL_LEMMAS) == 47
    assert len(agdt_schema.NON_AGREEING_QUANTIFIER_LEMMAS) == 4
    assert len(lemma.NOTEBOOK_LEMMA_NORMALIZATIONS) == 12
    # and a few entries, to be sure that it is not just any list
    assert "δέ" in stats.GRAMMATICAL_LEMMAS
    assert "ἐγώ" in postag.FIRST_PERSON_FORMS
    assert "ὅς" not in postag.THIRD_PERSON_FORMS
    assert lemma.NOTEBOOK_LEMMA_NORMALIZATIONS["ἀείρω"] == "αἴρω"


def test_le_estensioni_locali_sono_dichiarate_con_la_loro_risorsa():
    """The “b” is not just any value: it is known whose it is and why it is admitted."""
    risorsa = resources.load("estensioni-locali-di-pos")
    assert "b" in risorsa["voci"]
    b = risorsa["voci"]["b"]
    assert b["risorsa"] == "Pedalion"
    assert b["conversione"] is None, \
        "the documentation says “in most cases”: no unambiguous conversion"
    # “z” is not an extension: it marks a technical record
    assert "z" not in risorsa["voci"]


def test_nessuna_lista_e_specifica_per_far_tornare_un_corpus():
    """A list written for a single corpus is a disguised parameter.

    The test is weak by construction — it cannot read intentions — but it catches the
    case in which someone names a resource after a corpus.
    """
    corpora = ("gorman", "pedalion", "glaux")
    for identificatore in resources.available():
        nome = identificatore.lower()
        assert not any(corpus in nome for corpus in corpora), \
            f"«{identificatore}» ha il nome di un corpus"


def test_il_manifest_dichiara_ogni_lista_con_la_sua_impronta():
    righe = resources.manifest()
    assert len(righe) == len(resources.available())
    for riga in righe:
        assert riga["checksum"] and len(riga["checksum"]) == 16
        assert riga["voci"] > 0
        assert riga["usata_da"]


def test_lo_script_di_controllo_non_scrive_a_mano_versione_e_numero_di_regole():
    """CHECK_INSTALL.py must read its own references, not keep them written.

    The script tells the user whether the program is loading the right copy of the code.
    To do it, it must not compare the imported version with a literal and the length of
    the catalogue with another: at the first change of version the two numbers would age
    and the script would declare a correct installation broken — exactly the opposite of
    its purpose.  It reads the version from ``pyproject.toml`` and the number of checks
    from the table shipped in ``data/``, and this test keeps the door closed.
    """
    import re
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1]
    sorgente = (radice / "CHECK_INSTALL.py").read_text(encoding="utf-8")
    codice = "\n".join(riga for riga in sorgente.splitlines()
                       if not riga.lstrip().startswith("#"))

    versioni = re.findall(r"""["'](\d+\.\d+\.\d+)["']""", codice)
    assert not versioni, (
        "CHECK_INSTALL.py contains a hand-written version number: "
        f"{versioni}. It must be read from pyproject.toml with declared_version().")

    quanti = len(__import__("greek_corpus_pipeline.rule_catalog",
                            fromlist=["RULE_CATALOG"]).RULE_CATALOG)
    confronti = re.findall(rf"\b{quanti}\b", codice)
    assert not confronti, (
        "CHECK_INSTALL.py contains a hand-written number of checks: "
        f"{confronti}. It must be read from data/catalogo_controlli.csv with "
        "shipped_rules().")


def test_la_guida_in_word_dice_le_stesse_cose_di_quella_in_markdown():
    """The shipped .docx must say what GUIDE.md says.

    The Word version is a derivation of GUIDE.md, and could fall behind it: it could
    name steps, pages or figures that the program does not have, and whoever opened the
    Word file would read the description of another program.

    This test does not compare the two files word for word — the layout changes,
    and that is fine — but checks that the names used by the program are in the .docx.
    """
    import re
    import zipfile
    from pathlib import Path

    percorso = Path(__file__).resolve().parents[1] / "docs" / "GCP_user_guide.docx"
    if not percorso.exists():
        pytest.skip("the Word guide is not in this copy")
    with zipfile.ZipFile(percorso) as archivio:
        grezzo = archivio.read("word/document.xml").decode("utf-8")
    testo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", grezzo))

    for nome in ("Diagnostic findings", "Variation n-gram", "Correct",
                 "Revised corpus", "The AGDT 2.0 scheme"):
        assert nome in testo, (
            f"the Word guide does not mention “{nome}”: it must be regenerated from GUIDE.md.")

    # The headings of the two guides are the same, in the same order: a heading that is in
    # one guide and not in the other means that the Word file was not regenerated.
    def pulito(titolo: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", titolo)).strip().lower()

    titoli_word = []
    for paragrafo in re.findall(r"<w:p[ >].*?</w:p>", grezzo, flags=re.S):
        stile = re.search(r'<w:pStyle w:val="([^"]+)"', paragrafo)
        if stile and re.match(r"(Heading|Title)", stile.group(1), re.I):
            titoli_word.append(pulito(re.sub(r"<[^>]+>", "", paragrafo)))
    guida = (Path(__file__).resolve().parents[1] / "GUIDE.md").read_text(encoding="utf-8")
    titoli_md = [pulito(re.sub(r"^#+\s*", "", riga)) for riga in guida.splitlines()
                 if riga.startswith("#")]
    assert titoli_word, "the Word guide has no headings"
    assert titoli_word == titoli_md, (
        "the headings of the Word guide are not those of GUIDE.md: "
        "it must be regenerated from GUIDE.md.")
