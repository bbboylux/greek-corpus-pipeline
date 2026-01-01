"""The lists that decide a scientific result, kept out of the code.

A list of 136 lemmas written inside a Python file is an opaque constant:
whoever reads the article cannot inspect it, whoever disputes it cannot cite it
line by line, and whoever changes it leaves no trace. Yet those 136 lemmas
decide the lexical density, which is a number that the article publishes.

Here the lists become versioned data resources, in ``data/liste/``. Each
carries, besides its content, what is needed to be able to discuss it:

``id``            the stable identifier, which never changes
``nome``          the name in Italian and in English
``versione``      semantic: the third number for a correction, the second for
                  an addition, the first for a change of criterion
``funzione``      what it decides, in one sentence
``usata_da``      the points of the program that read it
``fonte``         where the entries come from, and who answers for the choice
``voci``          the content

The function :func:`checksum` computes the fingerprint of the content only, so
that the manifest can declare with which version of which list a result was
produced. Renaming the list or rewriting its rationale does not change the
fingerprint; removing or adding an entry does.

**No lists specific to a corpus are created.** A list that exists to make a
number come out on one corpus is a disguised parameter, and must be discussed
as a parameter.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "DIRECTORY",
    "checksum",
    "entries",
    "load",
    "manifest_entry",
    "available",
]

def _directory() -> Path:
    """The folder of the lists.

    In a source tree it is ``data/liste`` at the root of the project, two levels above the
    package (``src/greek_corpus_pipeline``). In an installed copy the wheel carries ``data``
    inside the package (``greek_corpus_pipeline/data``, see ``pyproject.toml``), where
    :func:`greek_corpus_pipeline.corpus_metadata.data_dir` also looks first.
    """
    here = Path(__file__).resolve()
    for candidate in (here.parent / "data" / "liste", here.parents[2] / "data" / "liste"):
        if candidate.is_dir():
            return candidate
    return here.parents[2] / "data" / "liste"


#: Where the lists live. Beside the data, not beside the code.
DIRECTORY = _directory()


class ListaMancante(KeyError):
    """A requested list does not exist among the resources.

    It is an error and not a warning: a scientific check that does not find its list
    must not proceed with an empty set, because it would produce zero findings and
    nobody would notice.
    """


@lru_cache(maxsize=None)
def load(identificatore: str) -> dict[str, Any]:
    """The whole resource: content and metadata.

    Cached because the checks ask for it on every call and the file does not change
    during a run.
    """
    percorso = DIRECTORY / f"{identificatore}.json"
    if not percorso.exists():
        disponibili = ", ".join(sorted(available())) or "none"
        raise ListaMancante(
            f"the list '{identificatore}' does not exist in {DIRECTORY}. "
            f"Available: {disponibili}")
    with percorso.open(encoding="utf-8") as sorgente:
        risorsa = json.load(sorgente)
    if "voci" not in risorsa:
        raise ValueError(f"the list '{identificatore}' has no 'voci' field")
    return risorsa


def entries(identificatore: str) -> Any:
    """The content only, in the form in which the code uses it.

    A list of strings becomes a ``frozenset``, a map stays a dictionary: this is the
    form in which callers used it when it was a constant, so that moving it to
    a data file changes nobody's behaviour.

    A list of structured entries — a passage with its citation, its provenance and
    its note — stays a tuple in the order of the file: the entries are not
    comparable by equality and the order in which they are written is part of how
    they are read.
    """
    voci = load(identificatore)["voci"]
    if isinstance(voci, dict):
        return dict(voci)
    if any(isinstance(voce, (dict, list)) for voce in voci):
        return tuple(voci)
    return frozenset(voci)


def checksum(identificatore: str) -> str:
    """The fingerprint of the content, for the manifest.

    Computed on the ``voci`` field only, serialised in canonical form: sorted,
    without spaces, in UTF-8. Two installations that declare the same fingerprint
    have read the same list, however the metadata were written.
    """
    voci = load(identificatore)["voci"]
    if isinstance(voci, dict):
        canonico = json.dumps(voci, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
    elif any(isinstance(voce, (dict, list)) for voce in voci):
        # Structured entries: they are not comparable with each other and the order in
        # which they are written is part of the content. They are serialised as they
        # are, with sorted keys because two files that say the same thing in a different
        # order must have the same fingerprint.
        canonico = json.dumps(voci, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
    else:
        canonico = json.dumps(sorted(voci), ensure_ascii=False,
                              separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:16]


def available() -> list[str]:
    """The identifiers of the lists present."""
    if not DIRECTORY.exists():
        return []
    return sorted(percorso.stem for percorso in DIRECTORY.glob("*.json"))


def manifest_entry(identificatore: str) -> dict[str, Any]:
    """The row that the manifest writes for this list."""
    risorsa = load(identificatore)
    return {
        "id": identificatore,
        "nome": risorsa.get("nome", ""),
        "name_en": risorsa.get("name_en", ""),
        "versione": risorsa.get("versione", ""),
        "voci": len(risorsa["voci"]),
        "checksum": checksum(identificatore),
        "usata_da": list(risorsa.get("usata_da", [])),
    }


def manifest() -> list[dict[str, Any]]:
    """All the lists, as the manifest of a run will see them."""
    return [manifest_entry(identificatore) for identificatore in available()]
