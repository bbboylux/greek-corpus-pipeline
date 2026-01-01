"""The provenance of a result, in a single file.

A number without its provenance cannot be verified. This module gathers
everything that is needed to know what a number counts and where it comes from:

``programma``   version of GCP and of Python
``corpus``      which corpus, how many records, with what fingerprint
``filtri``      the inclusion choices in force
``unita``       the five canonical units, with their counts
``denominatori`` what lies under every percentage that the program shows
``catalogo``    how many checks, and how they divide by class and treatment
``liste``       every scientific list with its version and its fingerprint
``modelli``     the state of the comparison with Stanza and UDPipe, if any

**One implementation.** The complete run and the interface write the same
manifest with the same function: if the file of the one said one thing and
that of the other another, neither would be worth anything.
"""
from __future__ import annotations

import hashlib
import platform
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from . import __version__, corpus_metadata, resources
from .model_eval import EVALUATION_DEFINITION
from .rule_catalog import RULE_CATALOG
from .units import Units, sentence_key

__all__ = ["DENOMINATORS", "build", "corpus_fingerprint"]


#: What lies under every percentage and every rate that the program shows.
#:
#: It is not documentation: it is the line that accompanies the number, and the reason it
#: exists is that a percentage without a denominator cannot be checked.
DENOMINATORS: dict[str, tuple[str, str]] = {
    "tasso_segnalazioni": (
        "segnalazioni ogni 10.000 record attivi",
        "findings per 10,000 active records"),
    "distribuzione_morfologica": (
        "occorrenze della posizione, sulle parole che quella posizione la usano",
        "occurrences of the slot, out of the words that use that slot"),
    "funzioni_sintattiche": (
        "occorrenze della funzione, sui record che portano una relazione",
        "occurrences of the function, out of the records carrying a relation"),
    "legami_non_proiettivi": (
        "legami non proiettivi, sui legami del gruppo",
        "non-projective links, out of the group's links"),
    "frasi_non_proiettive": (
        "frasi con almeno un legame non proiettivo, sulle frasi con archi utilizzabili",
        "sentences with at least one non-projective link, out of the sentences "
        "with usable links"),
    "frequenza_lessicale": (
        "occorrenze del lemma o della forma, sulle parole del testo",
        "occurrences of the lemma or form, out of the words of the text"),
    "logdice": (
        "f_target e f_partner sulle parole; f_joint sugli archi fra due parole",
        "f_target and f_partner on the words; f_joint on the links between two words"),
    "accordo_lemma": (
        "parole su cui corpus e modello concordano, sulle parole con lemma di "
        "riferimento presente",
        "words on which corpus and model agree, out of the words with a "
        "reference lemma present"),
    "accordo_etichetta": (
        "parole su cui corpus e modello concordano, sulle parole con etichetta "
        "di riferimento di nove caratteri",
        "words on which corpus and model agree, out of the words with a "
        "nine-character reference tag"),
    "copertura_modello": (
        "parole con una previsione utilizzabile, sulle parole eleggibili",
        "words with a usable prediction, out of the eligible words"),
}


def corpus_fingerprint(tokens: pd.DataFrame) -> str:
    """The fingerprint of the corpus: canonical sentence and form, in reading order.

    It changes if a token changes, if their order changes or if the corpus changes. It
    also changes if the name of a file or the identifier of a document changes, because
    the sentence key (:func:`units.sentence_key`) contains them: the same sentences under
    other file names are, for this purpose, another corpus.
    """
    if tokens is None or tokens.empty:
        return "0" * 16
    chiavi = sentence_key(tokens).to_numpy()
    forme = tokens["form"].astype("string").fillna("").to_numpy()
    digest = hashlib.sha256()
    for chiave, forma in zip(chiavi, forme):
        digest.update(f"{chiave}\x00{forma}\n".encode("utf-8"))
    return digest.hexdigest()[:16]


def build(
    *,
    corpus_name: str = "",
    run_id: str = "",
    tokens: pd.DataFrame | None = None,
    unita: Units | None = None,
    filtri: dict | None = None,
    findings: pd.DataFrame | None = None,
    modelli: dict[str, dict] | None = None,
    lingua: str = "it",
) -> dict[str, Any]:
    """The manifest of this corpus, with these filters, at this moment."""
    indice = 0 if lingua == "it" else 1

    classi: dict[str, int] = {}
    trattamenti: dict[str, int] = {}
    for regola in RULE_CATALOG.values():
        classi[regola["class"]] = classi.get(regola["class"], 0) + 1
        trattamenti[regola["treatment"]] = trattamenti.get(regola["treatment"], 0) + 1

    manifesto: dict[str, Any] = {
        "programma": {
            "nome": "Greek Corpus Pipeline",
            "versione": __version__,
            "python": platform.python_version(),
            "definizione_valutazione_modelli": EVALUATION_DEFINITION,
        },
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "nome": corpus_name,
            "run_id": run_id,
            "record_importati": int(0 if tokens is None else len(tokens)),
            "impronta": corpus_fingerprint(tokens),
        },
        "filtri": dict(sorted((filtri or {}).items())),
        "catalogo": {
            "controlli": len(RULE_CATALOG),
            "per_classe": dict(sorted(classi.items())),
            "per_trattamento": dict(sorted(trattamenti.items())),
        },
        "liste": resources.manifest(),
        # Where the metadata come from, and how much they cover. Without this line an
        # analysis “by author” cannot be repeated: it is not known with which
        # attribution it was made, nor whether there was an attribution.
        "metadati": corpus_metadata.provenienza_metadati(tokens),
        "denominatori": {nome: coppia[indice] for nome, coppia in DENOMINATORS.items()},
    }

    if unita is not None:
        manifesto["unita"] = {
            "imported_records": unita.n_imported_records,
            "active_records": unita.n_active_records,
            "words": unita.n_words,
            "analyzable_links": unita.n_analyzable_links,
            "analyzable_sentences": unita.n_analyzable_sentences,
            "sentences": unita.n_sentences,
        }
        if findings is not None and unita.n_active_records:
            manifesto["risultati"] = {
                "segnalazioni": int(len(findings)),
                "controlli_che_scattano": int(
                    findings["rule_id"].nunique()) if "rule_id" in findings.columns else 0,
                "per_diecimila_record_attivi": round(
                    10000 * len(findings) / unita.n_active_records, 2),
            }

    # The models: either the comparison is there and belongs to this corpus, or it is
    # said that there is none.
    manifesto["modelli"] = {}
    for etichetta in ("stanza", "udpipe"):
        stato = (modelli or {}).get(etichetta) or {}
        if stato.get("stato") == "valido":
            valutazione = stato.get("valutazione", {})
            manifesto["modelli"][etichetta] = {
                "stato": "eseguito sul corpus corrente",
                "provenienza": valutazione.get("provenienza", {}),
                "lemma": valutazione.get("lemma", {}),
                "postag": valutazione.get("postag", {}),
            }
        else:
            manifesto["modelli"][etichetta] = {
                "stato": stato.get("stato", "assente"),
                "motivo": stato.get("motivo", ""),
            }
    return manifesto
