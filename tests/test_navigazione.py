# -*- coding: utf-8 -*-
"""The names of the sidebar, frozen.

The labels of the navigation are decided once and are not to be rewritten by a
round of graphic work: a redesign can change the look, not what things are
called.  This test is the written constraint.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")

#: The Italian bar, exactly. Number, title, subtitle.
ITALIANO = [
    ("Carica il corpus", "Da cartella o da GitHub"),
    ("Panoramica", "Che cosa c'è dentro"),
    ("Trova le segnalazioni", "Controlli diagnostici"),
    ("Variation n-gram", "Incoerenze fra passi simili"),
    ("Correggi", "Decidi cosa modificare"),
    ("Cerca nel corpus", "Forme e lemmi, con il contesto"),
    ("Statistiche", "Il ritratto del corpus"),
    ("Grafici", "Sintesi visive"),
    ("Confronta i modelli", "Stanza e UDPipe"),
    ("Versione revisionata", "Esporta, conserva, confronta"),
]
RIFERIMENTO_IT = ("Lo schema AGDT 2.0", "L'etichetta e le funzioni, spiegate")

#: The English bar. The subtitles are natural translations, the titles are not: they are
#: decided one by one, and “Diagnostic findings” at step 3 is among them.
INGLESE = [
    "Load a corpus", "Overview", "Diagnostic findings", "Variation n-gram",
    "Correct", "Search the corpus", "Statistics", "Charts",
    "Compare the models", "Revised corpus",
]
RIFERIMENTO_EN = "The AGDT 2.0 scheme"

#: What must not come back. These are all wordings already discarded.
VIETATE = [
    "Trova gli errori", "Find the errors", "Variazione",
    "Rivedi", "Il tuo gold standard", "Gold standard corretto",
    "Corrected gold standard", "Figure per l'articolo",
    "Figures for the article",
]


def _barra(lingua: str) -> list[tuple[str, str]]:
    from gui_qt.i18n import T, tr
    from gui_qt.main_window import RIFERIMENTO, STEPS
    lingua_prima = T.language
    try:
        T.set_language(lingua)
        return [(chiave, tr(titolo), tr(nota))
                for chiave, _classe, titolo, nota, _needs in STEPS]
    finally:
        T.set_language(lingua_prima)


def test_la_barra_italiana_e_quella_approvata():
    voci = [(t, n) for chiave, t, n in _barra("it") if chiave != "rules"]
    assert voci == ITALIANO


def test_il_riferimento_italiano_e_quello_approvato():
    voce = [(t, n) for chiave, t, n in _barra("it") if chiave == "rules"]
    assert voce == [RIFERIMENTO_IT]


def test_la_barra_inglese_e_quella_approvata():
    titoli = [t for chiave, t, _n in _barra("en") if chiave != "rules"]
    assert titoli == INGLESE


def test_il_passo_tre_inglese_e_diagnostic_findings():
    """Not “Find findings” and not “Review annotations”."""
    titoli = {chiave: t for chiave, t, _n in _barra("en")}
    assert titoli["errors"] == "Diagnostic findings"


def test_il_riferimento_inglese_e_quello_approvato():
    voce = [t for chiave, t, _n in _barra("en") if chiave == "rules"]
    assert voce == [RIFERIMENTO_EN]


def test_il_passo_quattro_si_chiama_variation_n_gram_in_tutt_e_due():
    from gui_qt.i18n import T, tr
    lingua = T.language
    try:
        for scelta in ("it", "en"):
            T.set_language(scelta)
            assert tr("step.variation") == "Variation n-gram"
            assert tr("variation.title") == "Variation n-gram"
    finally:
        T.set_language(lingua)


def test_le_formulazioni_scartate_non_tornano():
    """None of the discarded wordings appears in any string."""
    from gui_qt.i18n import _STRINGS
    colpevoli = []
    for chiave, (italiano, inglese) in _STRINGS.items():
        for vietata in VIETATE:
            for testo in (italiano, inglese):
                if vietata == "Variazione" and vietata in testo:
                    # “Variazione” (variation) as an ordinary word is allowed: what must
                    # not come back is the *title* of page 4.
                    continue
                if vietata != "Variazione" and vietata in testo:
                    colpevoli.append(f"{chiave}: «{vietata}»")
    assert not colpevoli, "discarded wordings:\n" + "\n".join(sorted(set(colpevoli)))


def test_gold_standard_non_e_il_nome_di_una_pagina_o_di_un_risultato():
    """It remains only where it is explained methodologically."""
    from gui_qt.i18n import _STRINGS
    ammesse = {
        "gold.howto.1",              # the paragraph that explains why it is not
        "gold.msg.load_error", "gold.msg.load_incomplete",
        "gold.err.nothing_to_save",
        "models.three_way.hint",     # “does not treat either of the two as...”
    }
    colpevoli = []
    for chiave, (italiano, inglese) in _STRINGS.items():
        if chiave in ammesse or not chiave.startswith(("step.", "gold.", "review.")):
            continue
        for testo in (italiano, inglese):
            if "gold standard" in testo.lower():
                colpevoli.append(chiave)
    assert not colpevoli, "“gold standard” as a name: " + ", ".join(sorted(set(colpevoli)))


#: The keys of step 4 — the only ones where “Incoerenze fra passi simili”
#: (“Inconsistencies between similar passages”) stays.  There that wording names the
#: method, Variation n-gram, and not the object that the reader has in front of them; in
#: step 3 it is replaced by “Confronti tra annotazioni” (“Comparisons between
#: annotations”), which is what the step shows.
PASSO_QUATTRO = {"step.variation.hint", "variation.subtitle", "variation.intro"}


def test_incoerenze_fra_passi_simili_resta_solo_nel_passo_quattro():
    """In step 3 that wording must not appear."""
    from gui_qt.i18n import _STRINGS
    fuori_posto = []
    for chiave, (italiano, inglese) in _STRINGS.items():
        if chiave in PASSO_QUATTRO:
            continue
        if ("incoerenze fra passi simili" in italiano.lower()
                or "inconsistencies across similar passages" in inglese.lower()):
            fuori_posto.append(chiave)
    assert not fuori_posto, (
        "“Inconsistencies between similar passages” outside step 4: "
        + ", ".join(sorted(fuori_posto)))


def test_la_casella_e_la_scheda_del_passo_tre_si_chiamano_allo_stesso_modo():
    """They are the same thing seen before and after: they must have the same name."""
    from gui_qt.i18n import T, tr
    lingua = T.language
    try:
        for scelta, atteso in (("it", "Confronti tra annotazioni"),
                               ("en", "Annotation comparisons")):
            T.set_language(scelta)
            assert tr("errors.family.variation") == atteso
            assert tr("errors.variation_card") == atteso
    finally:
        T.set_language(lingua)


def test_il_passo_quattro_non_e_stato_toccato():
    """Title and subtitle of step 4, in the two languages, as they are."""
    from gui_qt.i18n import T, tr
    lingua = T.language
    try:
        T.set_language("it")
        assert tr("step.variation") == "Variation n-gram"
        assert tr("step.variation.hint") == "Incoerenze fra passi simili"
        T.set_language("en")
        assert tr("step.variation") == "Variation n-gram"
        assert tr("step.variation.hint") == "Inconsistencies across similar passages"
    finally:
        T.set_language(lingua)
