"""The five normalisations: each does its own job and no other."""
from __future__ import annotations

import unicodedata

from greek_corpus_pipeline.normalise import (
    LEMMA_VARIANTS,
    canonical_variant,
    nfc,
    search_key,
    skeleton,
    without_lemma_numbering,
)


# ---------------------------------------------------------------------------
# NFC
# ---------------------------------------------------------------------------

def test_nfc_unisce_le_due_scritture_della_stessa_forma():
    composta = "ἄνθρωπος"
    decomposta = unicodedata.normalize("NFD", composta)
    assert composta != decomposta
    assert nfc(composta) == nfc(decomposta)


def test_nfc_non_taglia_le_cifre_del_lemma():
    """The defect that made it necessary to separate the functions.

    ``lemma-tool-numbering`` must see the digit that it flags; if NFC removed it, the
    check could not use NFC.
    """
    assert nfc("θεῖος1") == "θεῖος1"


def test_nfc_non_mappa_le_varianti():
    assert nfc("ἀείρω") == "ἀείρω"


def test_nfc_di_un_valore_non_stringa_e_vuoto():
    assert nfc(None) == ""
    assert nfc(3) == ""


# ---------------------------------------------------------------------------
# The numbering of the lemmas
# ---------------------------------------------------------------------------

def test_taglia_la_numerazione_di_perseus():
    assert without_lemma_numbering("θεῖος1") == "θεῖος"
    assert without_lemma_numbering("θεῖος2") == "θεῖος"
    assert without_lemma_numbering("ἔρχομαι1") == "ἔρχομαι"


def test_un_lemma_senza_cifre_resta_intatto():
    assert without_lemma_numbering("ἄνθρωπος") == "ἄνθρωπος"


def test_un_lemma_fatto_di_sole_cifre_non_viene_svuotato():
    assert without_lemma_numbering("12") == "12"


def test_il_taglio_non_normalizza_e_non_mappa():
    decomposta = unicodedata.normalize("NFD", "θεῖος1")
    assert without_lemma_numbering(decomposta) == unicodedata.normalize("NFD", "θεῖος")
    assert without_lemma_numbering("ἀείρω") == "ἀείρω"


# ---------------------------------------------------------------------------
# The canonical variant
# ---------------------------------------------------------------------------

def test_la_mappa_delle_varianti_si_applica_solo_dove_dichiarata():
    assert canonical_variant("ἀείρω") == "αἴρω"
    assert canonical_variant("ἄνθρωπος") == "ἄνθρωπος"


def test_la_mappa_e_ispezionabile():
    assert "ἀείρω" in LEMMA_VARIANTS
    assert all(isinstance(k, str) and isinstance(v, str)
               for k, v in LEMMA_VARIANTS.items())


# ---------------------------------------------------------------------------
# The skeleton
# ---------------------------------------------------------------------------

def test_lo_scheletro_toglie_i_diacritici_e_abbassa():
    assert skeleton("ἄνθρωπος") == "ανθρωπος"
    assert skeleton("Ἄνθρωπος") == "ανθρωπος"


def test_lo_scheletro_e_severo_e_non_fonde_il_sigma_finale():
    """The difference between grouping key and search key.

    For grouping, ``ἀλλά`` and ``ἄλλα`` must remain two distinct words as to their
    accentuation: the skeleton merges them because it is the key of the orthographic
    nuclei, and it is precisely that collapse which is to be measured.  But the final
    sigma is not a diacritic and the skeleton does not touch it.
    """
    assert skeleton("ἀλλά") == skeleton("ἄλλα")
    assert skeleton("λόγος") != skeleton("λόγοσ")


def test_lo_scheletro_ricompone_in_nfc():
    decomposta = unicodedata.normalize("NFD", "ἄνθρωπος")
    assert skeleton(decomposta) == skeleton("ἄνθρωπος")


# ---------------------------------------------------------------------------
# The search key
# ---------------------------------------------------------------------------

def test_le_tre_modalita_di_ricerca_trovano_la_stessa_parola():
    politonico = search_key("ἄνθρωπος")
    senza_diacritici = search_key("ανθρωπος")
    traslitterato = search_key("anthropos")
    assert politonico == senza_diacritici == traslitterato


def test_la_ricerca_e_indifferente_a_nfc_e_nfd():
    assert search_key(unicodedata.normalize("NFD", "ἄνθρωπος")) == search_key("ἄνθρωπος")


def test_la_ricerca_fonde_il_sigma_finale():
    assert search_key("λόγος") == search_key("λόγοσ")
    assert search_key("λόγος") == search_key("logos")


def test_la_ricerca_ignora_lapostrofo_di_elisione():
    assert search_key("δ’") == search_key("δ")
    assert search_key("ἀλλ’") == search_key("ἀλλ")


def test_la_ricerca_gestisce_iota_sottoscritto_e_dieresi():
    assert search_key("τῷ") == search_key("τω")
    assert search_key("ἀΰπνος") == search_key("αυπνος")


def test_la_ricerca_scioglie_la_quantita_vocalica():
    """The price of transliteration, declared.

    The Latin alphabet does not distinguish ο from ω nor ε from η, so the distinction
    has to be dissolved on both sides for “anthropos” to find ἄνθρωπος.  The cost is
    that whoever searches ὄνος also finds ὦνος: acceptable in a search box, unacceptable
    in a count, and it is the reason why the search key is not the grouping key.
    """
    assert search_key("ὄνος") == search_key("ὦνος")
    assert search_key("ψυχή") == search_key("ψυχε")
    assert skeleton("ὄνος") != skeleton("ὦνος")


def test_lo_spirito_aspro_latino_non_e_una_lettera():
    """The isolated “h” is the breathing, not an eta.

    Mapping it to η would break ὁδός: “hodos” would become ηοδοσ against οδοσ.
    """
    assert search_key("ὁδός") == search_key("hodos")
    assert search_key("ῥόδον") == search_key("rhodon")


def test_le_digrafie_si_risolvono_prima_delle_lettere_singole():
    assert search_key("theos") == search_key("θεος")
    assert search_key("philos") == search_key("φιλος")
    assert search_key("psuche") == search_key("ψυχη")


def test_una_stringa_greca_non_viene_traslitterata():
    """Transliteration applies only to all-Latin text.

    Without this condition a Greek ρ would be treated as a Latin r in a mixed string,
    and the search would return results that the person typing did not ask for.
    """
    assert search_key("ῥόδον").startswith("ρ")


def test_la_chiave_di_ricerca_non_si_usa_per_contare():
    """Documents the reason for the separation, with the case that shows it.

    ``ἀλλά`` and ``ἄλλα`` are two different words; the search key merges them because
    whoever searches does not know where the accent falls, and counting on that key
    would give a wrong lexicon.  For counting there is :func:`nfc`.
    """
    assert search_key("ἀλλά") == search_key("ἄλλα")
    assert nfc("ἀλλά") != nfc("ἄλλα")


# ---------------------------------------------------------------------------
# The key of the rare lemma: intra-corpus, and therefore without the map
# ---------------------------------------------------------------------------

def test_la_chiave_intracorpus_non_applica_la_mappa_delle_varianti():
    """Two lemmas of the map stay distinct in the intra-corpus check.

    The map serves to make different resources comparable; the check on the rare lemma
    measures the internal consistency of a single resource.  Applying it there would
    erase the difference that the check must see — ``τ᾽`` lemmatised ``τέ`` once against
    ``τε`` in all the others.
    """
    from greek_corpus_pipeline.lemma import _chiave_lemma_intracorpus as chiave

    for variante, canonica in LEMMA_VARIANTS.items():
        assert chiave(variante) != chiave(canonica), \
            f"{variante} and {canonica} were merged by the intra-corpus key"


def test_la_chiave_intracorpus_non_crea_lemmi_distinti_per_nulla():
    """NFC and Perseus numbering must not produce artificially different lemmas."""
    from greek_corpus_pipeline.lemma import _chiave_lemma_intracorpus as chiave

    # difference of encoding only
    assert chiave(unicodedata.normalize("NFD", "θεῖος")) == chiave("θεῖος")
    # difference of the tool's numbering only
    assert chiave("Ζεύς1") == chiave("Ζεύς2") == chiave("Ζεύς")
    # and the two things together
    assert chiave(unicodedata.normalize("NFD", "θεῖος1")) == chiave("θεῖος")


def test_la_mappa_delle_varianti_viene_dalla_risorsa_e_non_e_inventata():
    """The table of canonical variants is tied to the data resource.

    The resource is inspectable and versioned: the table must come from it, so that no
    entry that no source documents can slip in unseen.
    """
    from greek_corpus_pipeline import resources
    from greek_corpus_pipeline.lemma import NOTEBOOK_LEMMA_NORMALIZATIONS

    risorsa = dict(resources.entries("varianti-canoniche-di-lemma"))
    assert dict(LEMMA_VARIANTS) == risorsa
    assert dict(NOTEBOOK_LEMMA_NORMALIZATIONS) == risorsa
    # and a few real entries, to recognise it
    assert LEMMA_VARIANTS["τέ"] == "τε"
    assert LEMMA_VARIANTS["νοῦς"] == "νόος"
