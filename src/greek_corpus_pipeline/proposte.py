# -*- coding: utf-8 -*-
"""Who proposes a correction, and who must propose nothing.

For every check the catalogue declares a treatment, and the treatment decides
what the program may write next to the finding.

* **automatic** — the condition that triggers the check suffices to establish
  the right value, and the program proposes it. The user decides whether to
  apply it.
* **manual** — the right value depends on the reading of the sentence, and the
  program proposes nothing.

There is a single exception to the second case, and it is declared row by row
in ``rule_catalog.VERIFIED_REPAIRS``: the occurrences that have already been
checked by hand, one by one, on Gorman or on Pedalion. There the value is
known because somebody read that sentence, and the proposal appears only on
*that occurrence*: corpus, document, work, sentence, token identifier, form,
lemma and tag must all coincide. The same form with the same anomaly, in
another passage, receives nothing.

The module does one thing and does it at the end of the chain, after every
family of checks has produced its findings, so that the rule applies to all of
them without having to be repeated in five modules.
"""
from __future__ import annotations

import pandas as pd

from .rule_catalog import (
    RULE_CATALOG,
    VERIFIED_META,
    rule_treatment,
    verified_repairs,
)

#: The checks whose automatic treatment is an action on the whole corpus and not a
#: proposal on a token.
#:
#: “Corpus predominantly in NFD” is the only one: the conversion to NFC is either done on
#: everything or not done, and writing the normalised form next to a single record would
#: say something false. The coherence test here does not look for a proposal, it looks
#: for the existence of the action: ``workers.apply_corrections`` performs it.
AZIONI_SUL_CORPUS: frozenset[str] = frozenset({"corpus-not-nfc"})

#: The columns in which a check may write a proposal.
COLONNE_PROPOSTA = ("suggested_postag", "suggested_lemma", "suggested_form",
                    "suggested_relation", "suggested_head")

#: The checks that the catalogue declares automatic.
def controlli_automatici() -> frozenset[str]:
    return frozenset(rid for rid in RULE_CATALOG
                     if rule_treatment(rid) == "automatica")


def _testo(valore: object) -> str:
    if valore is None or (isinstance(valore, float) and pd.isna(valore)):
        return ""
    try:
        if pd.isna(valore):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valore)


#: The columns that a finding does not carry and that must be fetched from the corpus:
#: the work and the citation of the resource. Without them the key does not close.
DA_RIPESCARE = ("cts_urn", "ref")


def _chiave_riga(riga: dict) -> tuple[str, ...]:
    """The fields with which a verified repair identifies itself, in order."""
    return tuple(sorted(c for c in riga if c not in VERIFIED_META))


def _indice_verificate() -> dict[tuple, tuple[str, str]]:
    """The verified repairs, indexed on their key.

    Each row declares by itself the fields with which it wants to be recognised: a
    morphological repair is identified by document, sentence and token, a parenthesis of
    Pedalion by the citation of the resource. All of those that the row declares must
    coincide.
    """
    indice: dict[tuple, tuple[str, str]] = {}
    for riga in verified_repairs():
        campi = _chiave_riga(riga)
        chiave = (str(riga["rule_id"]), campi) + tuple(
            _testo(riga.get(campo)) for campo in campi)
        indice[chiave] = (str(riga.get("campo", "postag")), str(riga["suggest"]))
    return indice


def allinea_proposte(findings: pd.DataFrame, tokens: pd.DataFrame | None = None,
                     corpus: str = "") -> pd.DataFrame:
    """Remove the proposals from the manual checks and restore the verified ones.

    *findings* is the table of findings already collected; *tokens* serves only to
    recover ``cts_urn``, which identifies the work and is not among the columns of
    a finding. *corpus* is the name of the loaded corpus.
    """
    if findings is None or findings.empty:
        return findings
    lavoro = findings.copy()
    for colonna in COLONNE_PROPOSTA:
        if colonna not in lavoro.columns:
            lavoro[colonna] = pd.NA

    automatici = controlli_automatici()
    manuali = ~lavoro["rule_id"].isin(automatici)
    if manuali.any():
        for colonna in COLONNE_PROPOSTA:
            lavoro.loc[manuali, colonna] = pd.NA
        if "auto_correctable" in lavoro.columns:
            lavoro.loc[manuali, "auto_correctable"] = False

    indice = _indice_verificate()
    if not indice:
        return lavoro
    campi_possibili = sorted({chiave[1] for chiave in indice})

    # The work and the citation are not among the columns of a finding: they are fetched
    # from the corpus, on the document-sentence-token triple.
    ripescate: dict[str, object] = {}
    chiavi = ["document_id", "sentence_id", "token_id"]
    if (tokens is not None and all(c in tokens.columns for c in chiavi)
            and all(c in lavoro.columns for c in chiavi)):
        presenti = [c for c in DA_RIPESCARE if c in tokens.columns]
        if presenti:
            mappa = tokens[chiavi + presenti].copy()
            for c in chiavi:
                mappa[c] = mappa[c].map(_testo)
            mappa = mappa.drop_duplicates(subset=chiavi)
            sinistra = pd.DataFrame({c: lavoro[c].map(_testo) for c in chiavi})
            unito = sinistra.merge(mappa, on=chiavi, how="left")
            for c in presenti:
                ripescate[c] = unito[c].map(_testo).to_numpy()

    def valore(campo: str, posizione: int, riga) -> str:
        if campo == "corpus":
            return _testo(corpus)
        if campo in ripescate:
            return _testo(ripescate[campo][posizione])
        return _testo(riga.get(campo))

    proposte: list[tuple[str, str] | None] = []
    for posizione, (_, riga) in enumerate(lavoro.iterrows()):
        trovata = None
        for chiave_campi in campi_possibili:
            chiave = (str(riga["rule_id"]), chiave_campi) + tuple(
                valore(campo, posizione, riga) for campo in chiave_campi)
            trovata = indice.get(chiave)
            if trovata is not None:
                break
        proposte.append(trovata)

    for posizione, (etichetta, trovata) in enumerate(zip(lavoro.index, proposte)):
        if trovata is None:
            continue
        colonna, valore_proposto = trovata
        colonna = f"suggested_{colonna}" if not colonna.startswith("suggested_") else colonna
        if colonna not in lavoro.columns:
            lavoro[colonna] = pd.NA
        lavoro.loc[etichetta, colonna] = valore_proposto
    return lavoro


def controlla_coerenza(findings: pd.DataFrame) -> list[str]:
    """Do the automatic checks really propose something? Do the manual ones stay silent?

    It returns the list of problems found, empty if all is well. It is the test that
    holds together the treatment declared in the catalogue and the real behaviour of the
    program.
    """
    if findings is None or findings.empty:
        return []
    problemi: list[str] = []
    automatici = controlli_automatici()
    colonne = [c for c in COLONNE_PROPOSTA if c in findings.columns]
    ha_proposta = pd.Series(False, index=findings.index)
    for colonna in colonne:
        ha_proposta |= findings[colonna].map(lambda v: _testo(v) != "")
    for rid, gruppo in findings.groupby("rule_id"):
        senza = int((~ha_proposta[gruppo.index]).sum())
        con = int(ha_proposta[gruppo.index].sum())
        if rid in automatici and senza and rid not in AZIONI_SUL_CORPUS:
            problemi.append(
                f"{rid}: declared automatic but {senza} findings out of "
                f"{len(gruppo)} propose nothing")
        if rid not in automatici and con:
            verificate = sum(1 for r in verified_repairs() if str(r["rule_id"]) == rid)
            if con > verificate:
                problemi.append(
                    f"{rid}: declared manual but {con} findings propose "
                    f"a value, and the verified repairs are {verificate}")
    return problemi
