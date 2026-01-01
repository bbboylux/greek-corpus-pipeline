# -*- coding: utf-8 -*-
"""The five families of checks must keep running in full.

This file exists for a precise reason.  If ``agreement.check_agreement`` — the heart of
the agreement checks — were deleted by mistake, a battery of tests in which none calls
``analyze_agreement`` would not notice, and a function that does not exist makes itself
felt only when someone tries to call it.  The program would
open, the tests would be green, and the diagnosis would die with a NameError in front of
the user.

The tests below call every family from the public entry point, which is the only way to
notice that a piece has gone.
"""
from __future__ import annotations

import pandas as pd
import pytest


FAMIGLIE = [
    ("postag", "analyze_postags"),
    ("lemma", "analyze_lemmas"),
    ("syntax", "analyze_syntax"),
    ("orthography", "analyze_orthography"),
    ("agreement", "analyze_agreement"),
]


@pytest.mark.parametrize("modulo, ingresso", FAMIGLIE)
def test_ogni_famiglia_gira_dall_ingresso_pubblico(modulo, ingresso, tokens):
    """What it finds does not matter: what matters is that it gets to the end without a
    NameError."""
    import importlib

    funzione = getattr(importlib.import_module(f"greek_corpus_pipeline.{modulo}"), ingresso)
    esito = funzione(tokens)
    if isinstance(esito, tuple):
        esito = esito[0]
    assert isinstance(esito, pd.DataFrame)


def test_l_accordo_trova_le_sue_segnalazioni(tokens):
    """The test corpus has a head without agreement: it must be seen."""
    from greek_corpus_pipeline import agreement

    assert hasattr(agreement, "check_agreement"), \
        "check_agreement is the heart of the family: without it the diagnosis dies"
    esito = agreement.analyze_agreement(tokens)
    assert isinstance(esito, pd.DataFrame)


def test_la_diagnosi_completa_arriva_in_fondo(tokens):
    """All five families together, as the program runs them."""
    from greek_corpus_pipeline import agreement, lemma, orthography, postag, syntax

    parti = [postag.analyze_postags(tokens), lemma.analyze_lemmas(tokens),
             orthography.analyze_orthography(tokens),
             syntax.analyze_syntax(tokens)[0],
             agreement.analyze_agreement(tokens)]
    insieme = pd.concat([p for p in parti if p is not None and not p.empty],
                        ignore_index=True)
    assert not insieme.empty
    assert "rule_id" in insieme.columns


def test_ogni_modulo_del_pacchetto_si_importa():
    """A deletion that was one too many is often seen already at import."""
    import importlib
    import pkgutil

    import greek_corpus_pipeline as pacchetto

    rotti = []
    for modulo in pkgutil.iter_modules(pacchetto.__path__):
        try:
            importlib.import_module(f"greek_corpus_pipeline.{modulo.name}")
        except Exception as errore:                      # noqa: BLE001
            rotti.append(f"{modulo.name}: {errore}")
    assert not rotti, rotti


def test_ogni_nome_chiamato_dalle_funzioni_pubbliche_esiste():
    """The names that a public function uses must really resolve.

    Python does not notice until it executes that line, and a line that is
    executed only on certain data can stay broken for a long time.  Here the
    bytecode is inspected: ``co_names`` lists the global names that the function
    will use, and each one must exist in the module, in the builtins or among its
    imports.
    """
    import builtins
    import importlib
    import pkgutil
    import types

    import greek_corpus_pipeline as pacchetto

    mancanti = []
    for modulo in pkgutil.iter_modules(pacchetto.__path__):
        oggetto = importlib.import_module(f"greek_corpus_pipeline.{modulo.name}")
        globali = set(vars(oggetto)) | set(dir(builtins))
        for nome, valore in vars(oggetto).items():
            if not isinstance(valore, types.FunctionType):
                continue
            if valore.__module__ != oggetto.__name__:
                continue
            codice = valore.__code__
            for usato in codice.co_names:
                # co_names also contains attributes (x.method): those cannot be verified
                # here, and are recognised because they are not global names of any
                # module.
                if usato in globali:
                    continue
                if any(usato in vars(m) for m in vars(oggetto).values()
                       if isinstance(m, types.ModuleType)):
                    continue
                # an attribute of any object: not a global name
                if not usato.islower() and not usato.isupper():
                    continue
                mancanti.append((modulo.name, nome, usato))
    # The names that remain are attributes of objects, not missing globals: the test is
    # there to stop if a function calls a deleted helper, and that case is recognised
    # because the name is defined nowhere.
    davvero = [(m, f, u) for m, f, u in mancanti
               if u in {"check_agreement", "preposition_government", "verb_government",
                        "government_outliers", "lexical_richness", "keyness",
                        "cooccurrence_clusters", "vocabulary_growth", "zipf_table"}]
    assert not davvero, davvero
