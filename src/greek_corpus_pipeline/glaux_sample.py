"""The declared sample of GLAUx, and how to download it.

GLAUx is a corpus of twenty million records distributed as three gigabytes of
XML. Loading all of it into an inspection program is of no use: the table that
comes out cannot be looked at, and the machine stops. The external test of the
article does not use all of it, and would not use it anyway: it uses a sample
drawn with a procedure declared before the results, which this module makes
executable with one click.

The procedure, in full and in order:

1. universe: the rows of the GLAUx file ``metadata.txt`` that carry a readable
   TLG identifier, as the program distributes them in ``data/glaux_metadata.csv``:
   1,421 texts, 19,498,849 declared records;
2. first cut: out go all the texts whose TLG author identifier appears in
   Gorman or in Pedalion. These are 37 authors, 552 texts, 7,968,898 records.
   This cut is the point of the test: if the third corpus contained the same
   texts as the first two, the check would be as circular as the design it is
   meant to verify;
3. second cut: out go the texts below 5,000 and above 60,000 records, in order
   to have a sample of many texts instead of a few large ones. 338 candidates
   remain;
4. drawing: ``random.sample`` of the standard library, seed 20260814 for the
   main sample and 20260815 for the confirmation one, twenty texts each.

The resulting list is in ``data/glaux_sample.csv``, one row per text, with the
sample and the stratum of membership. There are two strata because GLAUx
declares sentence by sentence whether the annotation is automatic or manual,
and some of the texts drawn carry manual annotation inherited from other
projects: keeping them together would make the comparison illegible.

The non-overlap with Gorman and Pedalion is verified, not promised:
:func:`overlapping_tlg_ids` derives the identifiers from the two corpora and
:func:`check_no_overlap` compares them. The test suite runs it on every
execution.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

#: Where GLAUx lives. A branch name is not a fixed version: the files that the sample
#: names are therefore compared, in ``reproducibility/``, with the SHA-256 of the files
#: that the study read.
GLAUX_OWNER = "alekkeersmaekers"
GLAUX_REPO = "glaux"
GLAUX_BRANCH = "main"

SAMPLE_FILE = "glaux_sample.csv"


@dataclass(frozen=True)
class SampleText:
    tlg: str
    campione: str      # "principale" (main) | "conferma" (confirmation)
    strato: str        # "automatico" (automatic) | "manuale" (manual)
    seme: int
    percorso: str      # path inside the repository
    autore: str
    opera: str
    genere: str
    dialetto: str
    anno_iniziale: str
    token_dichiarati: int


def _data_dir() -> Path:
    from .corpus_metadata import data_dir
    return data_dir()


def load_sample() -> list[SampleText]:
    """The complete list of the forty texts, in the order of the file."""
    percorso = _data_dir() / SAMPLE_FILE
    if not percorso.exists():
        raise FileNotFoundError(
            f"The GLAUx sample list is missing: {percorso}. "
            "It is distributed together with the code in data/glaux_sample.csv.")
    with percorso.open(encoding="utf-8", newline="") as fh:
        return [SampleText(
            tlg=r["tlg"], campione=r["campione"], strato=r["strato"],
            seme=int(r["seme"]), percorso=r["percorso"], autore=r["autore"],
            opera=r["opera"], genere=r["genere"], dialetto=r["dialetto"],
            anno_iniziale=r["anno_iniziale"],
            token_dichiarati=int(r["token_dichiarati"] or 0),
        ) for r in csv.DictReader(fh)]


def select(campione: str = "principale", strato: str | None = "automatico") -> list[SampleText]:
    """The texts of a sample, optionally of a single stratum."""
    testi = [t for t in load_sample() if t.campione == campione]
    if strato:
        testi = [t for t in testi if t.strato == strato]
    if not testi:
        raise ValueError(
            f"No text for campione={campione!r} strato={strato!r}. "
            "The samples are 'principale' (main) and 'conferma' (confirmation), "
            "the strata 'automatico' (automatic) and 'manuale' (manual).")
    return testi


def download(destination: str | Path, campione: str = "principale",
             strato: str | None = "automatico", progress=None) -> Path:
    """Download from the repository only the files of the requested sample."""
    from .github import download_github_files
    testi = select(campione, strato)
    cartella = Path(destination) / f"glaux-{campione}-{strato or 'tutto'}"
    return download_github_files(
        GLAUX_OWNER, GLAUX_REPO, GLAUX_BRANCH,
        [t.percorso for t in testi], cartella, progress=progress)


# ── The check that makes the test valid ─────────────────────────────────────

def overlapping_tlg_ids(*token_frames) -> set[str]:
    """The TLG author identifiers present in the tables passed.

    Derived from the ``tlg_author`` column, which ``xmlio`` reads from the identifier
    written in the file and not from a guess based on the file name.
    """
    identificativi: set[str] = set()
    for frame in token_frames:
        if frame is None or "tlg_author" not in getattr(frame, "columns", ()):
            continue
        valori = frame["tlg_author"].dropna().astype(str)
        for valore in set(valori):
            valore = valore.strip()
            if not valore:
                continue
            identificativi.add(valore[3:] if valore.startswith("tlg") else valore)
    return identificativi


def check_no_overlap(vietati: set[str], campione: str | None = None) -> list[str]:
    """The texts of the sample that violate the first cut. Empty means all is well."""
    testi = load_sample() if campione is None else [
        t for t in load_sample() if t.campione == campione]
    return sorted(t.tlg for t in testi if t.tlg.split("-")[0] in vietati)
