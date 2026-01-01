"""Who wrote what, when, where and in which dialect.

A treebank file is called ``hdt-1-1-19-bu3-2019.xml``. That string carries
everything a computer needs and nothing a classicist wants: it does not say
Herodotus, it does not say fifth century, it does not say Ionic. Every question
worth asking of a Greek corpus — does the optative recede after the classical
period? do Ionic and Attic differ in article density? which author uses this
lemma most? — needs that mapping, and until it exists the corpus is a heap of
tokens.

The name of a file is never a source of attribution. The metadata of a document
come from three places, tried in this order:

1. the row that the user's own catalogue (``data/user_metadata.csv``, loaded from
   the interface) has for the document, if there is one. The row counts in full:
   what it does not declare stays unknown, and nothing is completed from the
   shipped catalogues;
2. the identifier that the file declares about itself in the XML (a TLG author
   and work), looked up in ``tlg_authors.csv`` and ``tlg_works.csv`` (43 authors,
   72 works) and, for the authors that these two tables do not cover, in
   ``glaux_metadata.csv`` (1,421 texts). When the file names its author but not
   its work, the work may come from the catalogue of item 3, and the provenance
   says so;
3. the catalogue of the resource that the program recognises from the
   fingerprint of the imported corpus: ``gorman_metadata.csv`` (142 files) and
   ``pedalion_metadata.csv`` (40 files), one row per file, and
   ``glaux_metadata.csv`` for the samples of GLAUx.

While a catalogue of the user's is installed it replaces the one of item 3:
there is only ever one catalogue at work, never two mixed. What cannot be
resolved reads ``Unknown`` and is listed, not hidden. ``glaux_authors.csv`` (300
authors) is distributed as a reference table and is not read by this
resolution.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import resources

DATA_DIRNAME = "data"

CATALOGUE_FILES = {
    "Gorman": "gorman_metadata.csv",
    "Pedalion": "pedalion_metadata.csv",
}
AUTHOR_CATALOGUE_FILES = {
    "GLAUx": "glaux_authors.csv",
}

METADATA_COLUMNS = [
    "filename", "corpus", "author_it", "author_en", "tlg_author_id",
    "work_it", "work_en", "date_start", "date_end", "date_label",
    "century", "period", "dialect", "genre", "origin",
]

#: The order in which linguistic periods should be sorted on an axis.
PERIOD_ORDER = ["Archaic", "Classical", "Hellenistic", "Imperial",
                "Late antique", "Byzantine", "Unknown"]

UNKNOWN = "Unknown"


def data_dir() -> Path:
    """The folder holding the shipped catalogues.

    Kept next to the installed package so a frozen build still finds it, and
    resolved lazily so tests can point elsewhere.
    """
    here = Path(__file__).resolve()
    for candidate in (here.parent / DATA_DIRNAME,
                      here.parents[2] / DATA_DIRNAME,
                      here.parents[3] / DATA_DIRNAME):
        if candidate.is_dir():
            return candidate
    return here.parents[2] / DATA_DIRNAME


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    except Exception:
        return pd.DataFrame()
    for column in ("date_start", "date_end"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    return frame


#: The user's catalogue, if there is one. It lies beside the others in ``data/`` and not
#: inside them: updating the program does not overwrite it, and deleting it brings
#: everything back as it was.
USER_CATALOGUE_FILE = "user_metadata.csv"

#: The only columns that a user's catalogue must have. All the others of
#: ``METADATA_COLUMNS`` are optional: what is missing stays empty and the tables by
#: author show it as “Unknown”, which is the truth.
REQUIRED_USER_COLUMNS = ["filename", "author_it"]


#: The resources for which GCP distributes its own metadata, with the fingerprint
#: that identifies them: see ``data/liste/risorse-con-metadati.json``.
RISORSE_CON_METADATI = tuple(resources.entries("risorse-con-metadati"))

ORIGINE_NESSUNA = "none"
ORIGINE_SERIE = "bundled"
ORIGINE_UTENTE = "user"

#: What a metadata row that does not find a document means.
RIGHE_NESSUNA = "none"
#: In the user's CSV: a row written for a file that is not in the corpus.
RIGHE_DA_CONTROLLARE = "to check"
#: In a series catalogue: the normal case, because the catalogue covers the whole
#: resource and the loaded corpus is a sample of it.
RIGHE_CATALOGO_PIU_AMPIO = "catalogue wider than the loaded corpus"


def riconosci_risorsa(tokens: "pd.DataFrame | None") -> "dict | None":
    """Which known resource this corpus is, if it is one.

    Recognition is by fingerprint of the imported corpus and by nothing else. The
    metadata of Gorman apply only to a corpus that is recognised as Gorman: a corpus
    with a file ``lysias-14-bu1.xml`` does not receive the Gorman row unless its
    fingerprint says it is Gorman.
    """
    if tokens is None or getattr(tokens, "empty", True):
        return None
    from .manifest import corpus_fingerprint
    impronta = corpus_fingerprint(tokens)
    for voce in RISORSE_CON_METADATI:
        if str(voce.get("impronta", "")) == impronta:
            return dict(voce)
    return None


def load_bundled_catalogue(file_metadati: str) -> pd.DataFrame:
    """The series catalogue of a resource, that one and no other."""
    return _read_csv(data_dir() / str(file_metadati))


@lru_cache(maxsize=1)
def load_file_catalogue() -> pd.DataFrame:
    """All the per-file catalogues put together.

    It serves the views that must count how many rows GCP carries and how many
    the user has added. It is **not** the route by which metadata reach a corpus:
    that goes through the recognition of the resource.
    """
    percorsi = [data_dir() / filename for filename in CATALOGUE_FILES.values()]
    percorsi.append(data_dir() / USER_CATALOGUE_FILE)
    frames = [_read_csv(percorso) for percorso in percorsi]
    live = [frame for frame in frames if not frame.empty]
    if not live:
        return pd.DataFrame(columns=METADATA_COLUMNS)
    catalogue = pd.concat(live, ignore_index=True)
    for column in METADATA_COLUMNS:
        if column not in catalogue.columns:
            catalogue[column] = ""
    if "filename" in catalogue.columns:
        chiave = catalogue["filename"].astype("string").str.strip().str.lower()
        catalogue = catalogue[~chiave.duplicated(keep="last")].reset_index(drop=True)
    return catalogue


def user_catalogue_path() -> Path:
    """Where the user's catalogue lives, whether or not it exists yet."""
    return data_dir() / USER_CATALOGUE_FILE


def installed_user_catalogue() -> "pd.DataFrame | None":
    """The user's catalogue as installed in ``data/``, or ``None`` if there is none.

    It is read at every call and never cached: installing or removing the catalogue
    from the interface takes effect the next time a corpus is opened, without having
    to restart the program.
    """
    percorso = user_catalogue_path()
    if not percorso.exists():
        return None
    frame = _read_csv(percorso)
    return None if frame.empty else frame


def read_user_catalogue(percorso: object) -> tuple[pd.DataFrame, list[str]]:
    """Read a candidate catalogue and say what is wrong with it.

    Returns the frame — empty if it cannot be used — and a list of messages in
    English, ready to be shown. The check is deliberately shallow: it verifies
    that the file can be read, that the two required columns are there and
    filled, and that any date columns hold numbers. Everything else is the
    user's business, and refusing a file for a genre spelled differently would
    be an obstacle, not a safeguard.
    """
    percorso = Path(str(percorso))
    problemi: list[str] = []
    if not percorso.exists():
        return pd.DataFrame(), [f"The file “{percorso.name}” does not exist."]
    try:
        frame = _read_csv(percorso)
    except Exception as errore:                            # pragma: no cover
        return pd.DataFrame(), [f"The file cannot be read as CSV: {errore}"]
    if frame.empty:
        return pd.DataFrame(), ["The file is empty, or has no data rows."]

    mancanti = [c for c in REQUIRED_USER_COLUMNS if c not in frame.columns]
    if mancanti:
        return pd.DataFrame(), [
            "Required columns are missing: " + ", ".join(mancanti) + ". "
            "The first row of the file must contain the column names."]

    for colonna in REQUIRED_USER_COLUMNS:
        vuote = frame[colonna].astype("string").fillna("").str.strip() == ""
        if vuote.any():
            problemi.append(
                f"{int(vuote.sum())} rows have an empty “{colonna}”: "
                f"they are ignored.")
            frame = frame[~vuote]
    if frame.empty:
        return pd.DataFrame(), problemi + ["No usable row is left."]

    for colonna in ("date_start", "date_end"):
        if colonna in frame.columns:
            numeri = pd.to_numeric(frame[colonna], errors="coerce")
            scritte = frame[colonna].astype("string").fillna("").str.strip() != ""
            rotte = scritte & numeri.isna()
            if rotte.any():
                problemi.append(
                    f"{int(rotte.sum())} rows have a “{colonna}” that is not a "
                    f"number: the date is left empty.")
                frame.loc[rotte, colonna] = ""

    ignote = [c for c in frame.columns if c not in METADATA_COLUMNS]
    if ignote:
        problemi.append("Unrecognised columns, which the program ignores: "
                        + ", ".join(ignote) + ".")

    doppie = frame["filename"].astype("string").str.strip().str.lower().duplicated()
    if doppie.any():
        problemi.append(f"{int(doppie.sum())} file names appear more than once: "
                        f"the last row wins.")
    return frame, problemi


def install_user_catalogue(percorso: object) -> tuple[bool, list[str]]:
    """Validate a catalogue and put it where the program will read it."""
    frame, problemi = read_user_catalogue(percorso)
    if frame.empty:
        return False, problemi
    for colonna in METADATA_COLUMNS:
        if colonna not in frame.columns:
            frame[colonna] = ""
    destinazione = user_catalogue_path()
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    frame[METADATA_COLUMNS].to_csv(destinazione, index=False, encoding="utf-8-sig")
    forget_catalogues()
    return True, [f"{len(frame)} rows loaded."] + problemi


def remove_user_catalogue() -> bool:
    """Throw the user's catalogue away and go back to the shipped ones."""
    percorso = user_catalogue_path()
    if not percorso.exists():
        return False
    percorso.unlink()
    forget_catalogues()
    return True


def forget_catalogues() -> None:
    """Drop the cached catalogues, so the next question re-reads the files."""
    for funzione in (load_file_catalogue, load_author_catalogue):
        funzione.cache_clear()


@lru_cache(maxsize=1)
def load_author_catalogue() -> pd.DataFrame:
    """The author-level catalogue (GLAUx and anything shaped like it)."""
    frames = [_read_csv(data_dir() / filename) for filename in AUTHOR_CATALOGUE_FILES.values()]
    live = [frame for frame in frames if not frame.empty]
    if not live:
        return pd.DataFrame()
    return pd.concat(live, ignore_index=True)




# ---------------------------------------------------------------------------
# Identity from the data, not from the file name
# ---------------------------------------------------------------------------
#
# A treebank file names its own text. Gorman writes a CTS URN on every sentence
# (``urn:cts:greekLit:tlg0026.tlg001.perseus-grc1``), Pedalion the compact
# ``0059-003``. ``xmlio`` reads that identifier into the ``tlg_author`` and
# ``tlg_work`` columns, and those two columns are the only attribution in the
# whole pipeline that is not a guess.
#
# The name of the file is not used at all, not even as a last resort, and a
# file that carries no identifier (papyri under a Trismegistos number, the
# Septuagint under "Genesis") is attributed only if the catalogue of a
# recognised resource or the user's catalogue has a row for it. Every enriched
# token carries a ``fonte_metadati`` column saying how its attribution was
# reached. The distinction matters — "aesch" is the standard abbreviation of
# Aeschylus, not of Aeschines, and a program that resolves it silently is one
# bad file name away from attributing tragedy to an orator.

#: How a record was reached, from most to least trustworthy.
SOURCE_URN = "URN in the file"
SOURCE_AUTHOR_ONLY = "author only (work not identified)"
SOURCE_MIXED = "author from the URN, work from the resource catalogue"
SOURCE_NONE = "unresolved"
SOURCE_BUNDLED = "shipped catalogue of the recognised resource"
SOURCE_USER = "catalogue loaded by the user"
SOURCE_GLAUX = "GLAUx catalogue (metadata.txt)"


@lru_cache(maxsize=1)
def load_tlg_authors() -> pd.DataFrame:
    """The author table, keyed on the TLG author identifier."""
    return _read_csv(data_dir() / "tlg_authors.csv")


@lru_cache(maxsize=1)
def load_tlg_works() -> pd.DataFrame:
    """The work table, keyed on TLG author + work identifier."""
    return _read_csv(data_dir() / "tlg_works.csv")


@lru_cache(maxsize=1)
def load_glaux_catalogue() -> pd.DataFrame:
    """GLAUx's own catalogue of its 1,421 texts.

    GLAUx ships ``metadata.txt``, one row per text with author, title, genre,
    dialect and a date range. The program carries a copy of it, translated
    into the vocabulary the rest of the catalogue uses, because the curated
    tables cover only the authors of Gorman and Pedalion — and the GLAUx
    sample was chosen so as to share no author with either of them. Without
    this file every GLAUx text would come out as "Unknown".

    Two remarks on the source. One row is an exact duplicate (0593-002,
    Gorgias, *Testimonia*): the copy is dropped, so 1,422 rows give 1,421
    texts. The period is derived from the midpoint of the date range, because
    GLAUx dates a text by the author's floruit and several ranges straddle a
    conventional boundary.
    """
    return _read_csv(data_dir() / "glaux_metadata.csv")


@lru_cache(maxsize=1)
def _glaux_tables() -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    by_document: dict[str, dict] = {}
    by_identifier: dict[tuple[str, str], dict] = {}
    for record in load_glaux_catalogue().to_dict("records"):
        document = str(record.get("document_id", "")).strip().lower()
        if document:
            by_document[document] = record
        key = (str(record.get("tlg_author", "")).strip().lower(),
               str(record.get("tlg_work", "")).strip().lower())
        if key[0] and key[1]:
            by_identifier.setdefault(key, record)
    return by_document, by_identifier


def _glaux_record(record: dict) -> dict[str, object]:
    """A GLAUx catalogue row in the shape the rest of the program expects."""
    return {
        "filename": "", "corpus": "glaux",
        "author_it": record.get("author_it") or UNKNOWN,
        "author_en": record.get("author_en") or "Unknown",
        "tlg_author_id": str(record.get("tlg_author", "")).strip().lower(),
        "work_it": record.get("work_en") or UNKNOWN,
        "work_en": record.get("work_en") or "Unknown",
        "date_start": record.get("date_start", pd.NA),
        "date_end": record.get("date_end", pd.NA),
        "date_label": record.get("date_label", ""),
        "century": record.get("century") or UNKNOWN,
        "period": record.get("period") or UNKNOWN,
        "dialect": record.get("dialect") or UNKNOWN,
        "genre": record.get("genre") or UNKNOWN,
        "origin": "",
        "note": "", "metadata_source": SOURCE_GLAUX,
    }


def resolve_glaux(document_id: object = None,
                  tlg_author: object = None,
                  tlg_work: object = None) -> dict[str, object] | None:
    """Metadata for a GLAUx text, by document identifier or by TLG pair."""
    by_document, by_identifier = _glaux_tables()
    key = str(document_id or "").strip().lower()
    if key:
        record = by_document.get(key)
        if record is not None:
            return _glaux_record(record)
    pair = (str(tlg_author or "").strip().lower(),
            str(tlg_work or "").strip().lower())
    if pair[0] and pair[1]:
        record = by_identifier.get(pair)
        if record is not None:
            return _glaux_record(record)
    return None


@lru_cache(maxsize=1)
def _tlg_tables() -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    authors = {}
    for record in load_tlg_authors().to_dict("records"):
        key = str(record.get("tlg_author", "")).strip().lower()
        if key:
            authors[key] = record
    works = {}
    for record in load_tlg_works().to_dict("records"):
        key = (str(record.get("tlg_author", "")).strip().lower(),
               str(record.get("tlg_work", "")).strip().lower())
        if key[0] and key[1]:
            works[key] = record
    return authors, works


def resolve_by_identifier(tlg_author: object, tlg_work: object) -> dict[str, object] | None:
    """Metadata for a text that named itself. Returns ``None`` when it did not.

    The work fields stay empty when the work identifier is absent or unknown,
    rather than borrowing the title of some other text by the same author:
    an attribution the program cannot support is worse than no attribution,
    because the reader has no way to tell the two apart.
    """
    author_key = str(tlg_author or "").strip().lower()
    if not author_key:
        return None
    authors, works = _tlg_tables()
    author = authors.get(author_key)
    if author is None:
        # The curated tables cover the authors of Gorman and Pedalion only.
        # GLAUx names itself the same way, so its catalogue answers here.
        return resolve_glaux(tlg_author=tlg_author, tlg_work=tlg_work)

    work_key = str(tlg_work or "").strip().lower()
    work = works.get((author_key, work_key)) if work_key else None

    record = {
        "filename": "", "corpus": "",
        "author_it": author.get("author_it", UNKNOWN),
        "author_en": author.get("author_en", "Unknown"),
        "tlg_author_id": author_key,
        "work_it": work.get("work_it", "") if work else UNKNOWN,
        "work_en": work.get("work_en", "") if work else "Unknown",
        "date_start": author.get("date_start", pd.NA),
        "date_end": author.get("date_end", pd.NA),
        "date_label": author.get("date_label", ""),
        "century": author.get("century", UNKNOWN),
        "period": author.get("period", UNKNOWN),
        "dialect": author.get("dialect", UNKNOWN),
        "genre": work.get("genre", UNKNOWN) if work else UNKNOWN,
        "origin": author.get("origin", ""),
        "note": work.get("note", "") if work else "",
        "metadata_source": SOURCE_URN if work else SOURCE_AUTHOR_ONLY,
    }
    return record



def catalogue_summary() -> dict[str, int]:
    files = load_file_catalogue()
    authors = load_author_catalogue()
    return {
        "file_catalogati": int(len(files)),
        "autori_file": int(files["author_it"].nunique()) if not files.empty else 0,
        "autori_glaux": int(len(authors)),
    }


# ---------------------------------------------------------------------------
# Key normalisation
# ---------------------------------------------------------------------------

def _ascii_fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_key(value: object) -> str:
    """The comparison key of a file name: lower case, without extension.

    It does not remove digits and does not remove punctuation. Removing them would let
    two files that differ by a number — ``lysias-14-bu1`` and ``lysias_14_bu1`` — end up
    on the same key and receive different works depending on which row the dictionary
    met last. A number inside the name of a treebank file is almost always the book or
    the speech: removing it to find a match means deliberately looking for a wider one.
    """
    if not isinstance(value, str):
        return ""
    return _ascii_fold(Path(value).stem.strip().lower())


@lru_cache(maxsize=1)
def _lookup_tables() -> tuple[dict[str, dict], dict[str, dict]]:
    """The per-file catalogue, indexed on the exact name and on the exact stem.

    There is no “per author” table built from the alphabetic prefix of file names and a
    hand-written list of aliases, which would produce invented attributions:
    ``medea.xml`` becoming Euripides, ``hdt-appunti.xml`` becoming Herodotus, and a file
    that the catalogue did not contain receiving a plausible author and title anyway.
    The name of a file is not a source.
    """
    by_filename: dict[str, dict] = {}
    by_stem: dict[str, dict] = {}
    for record in load_file_catalogue().to_dict("records"):
        filename = str(record.get("filename", "")).strip()
        if not filename:
            continue
        by_filename.setdefault(filename.lower(), record)
        by_stem.setdefault(normalize_key(filename), record)
    return by_filename, by_stem


#: The keys that a metadata record always carries, even when nothing is known. A schema
#: that changes shape depending on where the record was found is a trap: ``work_it``
#: would be missing when the match came from the catalogue of authors, and whoever read
#: it would get a KeyError.
SCHEMA_RECORD: tuple[str, ...] = (
    "filename", "corpus", "author_it", "author_en", "tlg_author_id",
    "work_it", "work_en", "date_start", "date_end", "date_label",
    "century", "period", "dialect", "genre", "origin", "note",
    "metadata_source",
)

#: The fields that stay empty instead of saying “Unknown”: they are not missing
#: descriptions, they are fields that often do not exist at all.
_CAMPI_VUOTI = frozenset({"filename", "corpus", "tlg_author_id", "date_label",
                          "origin", "note", "metadata_source"})


def record_completo(record: "dict | None" = None, *, filename: str = "") -> dict:
    """A record with all the expected keys, “Unknown” where nothing is known."""
    completo: dict[str, object] = {}
    for chiave in SCHEMA_RECORD:
        valore = (record or {}).get(chiave)
        if valore is None or (isinstance(valore, str) and not valore.strip()):
            valore = "" if chiave in _CAMPI_VUOTI else UNKNOWN
        completo[chiave] = valore
    for chiave in ("date_start", "date_end"):
        completo[chiave] = (record or {}).get(chiave, pd.NA)
    if filename and not str(completo.get("filename", "")).strip():
        completo["filename"] = filename
    if str(completo.get("author_en", "")) == UNKNOWN:
        completo["author_en"] = "Unknown"
    if str(completo.get("work_en", "")) == UNKNOWN:
        completo["work_en"] = "Unknown"
    return completo


def _blank_record(filename: str) -> dict[str, object]:
    """Nothing at all, declared.

    ``work_it`` is not the name of the file. A file name is not the title of a work: a
    work column showing “anonimo-0” would look like data. The file name stays where it
    is — in ``source_file`` — and the work says that it is not known.
    """
    return record_completo({"filename": filename,
                            "metadata_source": SOURCE_NONE})


def resolve_document(filename: object, document_id: object = None) -> dict[str, object]:
    """The per-file catalogue record, looked up by exact name and nothing else.

    Only two routes, both by equality: the name of the file as it is written, and the
    name without extension. No prefixes, no aliases, no abbreviations, no identifiers
    searched inside the name. If the catalogue does not contain that file, the record is
    empty and says so.
    """
    by_filename, by_stem = _lookup_tables()
    candidati = [valore for valore in (filename, document_id)
                 if isinstance(valore, str) and valore.strip()]
    for candidato in candidati:
        record = by_filename.get(candidato.strip().lower())
        if record:
            return record_completo(record, filename=str(candidato))
    for candidato in candidati:
        record = by_stem.get(normalize_key(candidato))
        if record:
            return record_completo(record, filename=str(candidato))
    return _blank_record(str(candidati[0]) if candidati else "")


ENRICHED_COLUMNS = [
    "autore", "autore_en", "tlg", "opera", "opera_en",
    "data_inizio", "data_fine", "datazione", "secolo", "periodo",
    "dialetto", "genere", "provenienza",
    "fonte_metadati", "nota_metadati",
]


def dataset_attivo(tokens: "pd.DataFrame | None" = None,
                   *, user_metadata: "pd.DataFrame | None" = None) -> dict:
    """Which set of metadata applies to this corpus, and where it comes from.

    Only one, never two mixed. The user's CSV, if present, *replaces* the series
    catalogue instead of completing it field by field: a field-by-field merge would be
    invisible and would produce rows with the author from the user and the century from
    GCP, without anything saying so.
    """
    if user_metadata is None:
        user_metadata = installed_user_catalogue()
    if user_metadata is not None and not user_metadata.empty:
        return {"origine": ORIGINE_UTENTE, "nome": USER_CATALOGUE_FILE,
                "chiave_join": "document_id", "tabella": user_metadata,
                "risorsa": None}
    risorsa = riconosci_risorsa(tokens)
    if risorsa is not None:
        return {"origine": ORIGINE_SERIE, "nome": str(risorsa["file_metadati"]),
                "chiave_join": str(risorsa["chiave_join"]),
                "tabella": load_bundled_catalogue(risorsa["file_metadati"]),
                "risorsa": risorsa}
    return {"origine": ORIGINE_NESSUNA, "nome": "", "chiave_join": "",
            "tabella": pd.DataFrame(), "risorsa": None}


def _indice_dataset(dataset: dict) -> dict[str, dict]:
    """The active dataset indexed on its key, by exact equality."""
    tabella = dataset.get("tabella")
    if tabella is None or tabella.empty:
        return {}
    chiave = dataset.get("chiave_join") or "document_id"
    colonne = [c for c in (chiave, "filename", "document_id", "source_file")
               if c in tabella.columns]
    if not colonne:
        return {}
    indice: dict[str, dict] = {}
    for record in tabella.to_dict("records"):
        for colonna in colonne:
            valore = str(record.get(colonna, "")).strip().lower()
            if valore:
                indice.setdefault(valore, record)
                indice.setdefault(Path(valore).stem, record)
    return indice


def enrich_tokens(
    tokens: pd.DataFrame,
    *,
    user_metadata: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach author, work, date, dialect and genre to a table of tokens.

    Three sources, in this order, and no fourth.

    1. **What the file declares about itself.** The TLG identifier that ``xmlio``
       read from the XML, looked up by equality in the catalogue of authors and
       works. It comes from the file and cannot be wrong about who wrote the
       text.
    2. **The active dataset**, looked up by equality on its key: the catalogue of
       a resource recognised by its fingerprint, or the CSV that the user has
       loaded. Never both.
    3. **Nothing**, and then ``Unknown``.

    The file name is not a source. Attributions such as ``medea.xml`` → Euripides
    or ``hdt-appunti.xml`` → Herodotus, and a plausible title for files that the
    catalogue did not contain at all, are exactly what this rule rules out.

    The resolution runs once per document and not once per token.
    """
    if tokens is None or tokens.empty:
        return tokens.copy() if tokens is not None else pd.DataFrame()

    work = tokens.copy()
    source = work["source_file"] if "source_file" in work.columns else pd.Series("", index=work.index)
    document = work["document_id"] if "document_id" in work.columns else pd.Series("", index=work.index)

    def _column(name: str) -> pd.Series:
        if name in work.columns:
            return work[name].astype("string").fillna("")
        return pd.Series("", index=work.index, dtype="string")

    pairs = pd.DataFrame({"_src": source.astype("string").fillna(""),
                          "_doc": document.astype("string").fillna(""),
                          "_aut": _column("tlg_author"),
                          "_opr": _column("tlg_work")}).drop_duplicates()

    dataset = dataset_attivo(tokens, user_metadata=user_metadata)
    indice = _indice_dataset(dataset)
    fonte_dataset = (SOURCE_USER if dataset["origine"] == ORIGINE_UTENTE
                     else SOURCE_BUNDLED)

    resolved: dict[tuple[str, str], dict[str, object]] = {}
    for src, doc, aut, opr in zip(pairs["_src"], pairs["_doc"],
                                  pairs["_aut"], pairs["_opr"]):
        dal_dataset = None
        for candidato in (doc, src, Path(str(src)).stem):
            if candidato:
                dal_dataset = indice.get(str(candidato).strip().lower())
                if dal_dataset is not None:
                    break

        if dataset["origine"] == ORIGINE_UTENTE and dal_dataset is not None:
            # The user's CSV is the authority: its row is valid in full, and the fields
            # it does not declare remain unknown. They are not completed with those of
            # GCP, which would be an invisible merge.
            record = dict(dal_dataset)
            record["metadata_source"] = SOURCE_USER
        else:
            record = resolve_by_identifier(aut, opr)
            if record is not None and record.get("metadata_source") == SOURCE_AUTHOR_ONLY:
                # The file has named its author but not its work (Pedalion writes
                # “0096-00#” when the work is unclear). The title may come from the
                # active dataset, and the mixed provenance is declared.
                if dal_dataset and str(dal_dataset.get("work_it", "")).strip():
                    for campo in ("work_it", "work_en", "genre"):
                        if str(dal_dataset.get(campo, "")).strip():
                            record[campo] = dal_dataset[campo]
                    record["metadata_source"] = SOURCE_MIXED
            if record is None and dal_dataset is not None:
                record = dict(dal_dataset)
                record["metadata_source"] = fonte_dataset
        if record is None:
            record = _blank_record(str(src))
        record = record_completo(record, filename=str(src))
        resolved[(src, doc)] = record

    def _pick(field: str, fallback: object = UNKNOWN):
        return [
            (resolved.get((src, doc), {}) or {}).get(field) or fallback
            for src, doc in zip(pairs["_src"], pairs["_doc"])
        ]

    lookup = pd.DataFrame({
        "_src": pairs["_src"].values,
        "_doc": pairs["_doc"].values,
        "autore": _pick("author_it"),
        "autore_en": _pick("author_en", "Unknown"),
        "tlg": _pick("tlg_author_id", ""),
        "opera": _pick("work_it"),
        "opera_en": _pick("work_en", ""),
        "data_inizio": [(resolved.get((s, d), {}) or {}).get("date_start")
                        for s, d in zip(pairs["_src"], pairs["_doc"])],
        "data_fine": [(resolved.get((s, d), {}) or {}).get("date_end")
                      for s, d in zip(pairs["_src"], pairs["_doc"])],
        "datazione": _pick("date_label", ""),
        "secolo": _pick("century"),
        "periodo": _pick("period"),
        "dialetto": _pick("dialect"),
        "genere": _pick("genre"),
        "provenienza": _pick("origin", ""),
        "fonte_metadati": _pick("metadata_source", SOURCE_NONE),
        "nota_metadati": _pick("note", ""),
    })

    work["_src"] = source.astype("string").fillna("")
    work["_doc"] = document.astype("string").fillna("")
    # A table that has already been enriched is re-enriched, not doubled. Without
    # this the merge would produce “author_x” and “author_y” and the “author”
    # column would disappear: whoever read it would get a KeyError on a corpus that
    # had been saved after the enrichment.
    work = work.drop(columns=[c for c in ENRICHED_COLUMNS if c in work.columns])
    merged = work.merge(lookup, on=["_src", "_doc"], how="left")
    merged = merged.drop(columns=["_src", "_doc"])
    for column in ENRICHED_COLUMNS:
        if column in merged.columns:
            merged[column] = merged[column].fillna(UNKNOWN if column not in
                                                   ("tlg", "provenienza",
                                                    "datazione", "opera_en")
                                                   else "")
    return merged


def provenienza_metadati(tokens: "pd.DataFrame | None",
                         *, user_metadata: "pd.DataFrame | None" = None) -> dict:
    """Where the metadata of this corpus come from, and how much of it they cover.

    This is what the manifest writes: without it, an analysis “by author” cannot be
    repeated, because it is not known with which attribution it was made.
    """
    vuoto = {
        "metadata_present": False, "metadata_origin": ORIGINE_NESSUNA,
        "dataset": "", "versione": "", "chiave_join": "",
        "risorsa": "", "impronta_risorsa": "",
        "documenti_totali": 0, "documenti_con_metadati": 0,
        "documenti_senza_metadati": 0, "righe_metadati_non_associate": 0,
        "righe_non_associate_sono": RIGHE_NESSUNA,
    }
    if tokens is None or getattr(tokens, "empty", True):
        return vuoto

    dataset = dataset_attivo(tokens, user_metadata=user_metadata)
    arricchiti = enrich_tokens(tokens, user_metadata=user_metadata)
    documenti = arricchiti.drop_duplicates(
        subset=[c for c in ("source_file", "document_id")
                if c in arricchiti.columns])
    con = int((documenti["autore"].astype(str) != UNKNOWN).sum()) \
        if "autore" in documenti.columns else 0

    chiavi_corpus = set()
    for colonna in ("source_file", "document_id"):
        if colonna in documenti.columns:
            for valore in documenti[colonna].astype(str):
                chiavi_corpus.add(valore.strip().lower())
                chiavi_corpus.add(Path(valore.strip().lower()).stem)
    tabella = dataset.get("tabella")
    orfane = 0
    if tabella is not None and not tabella.empty:
        chiave = dataset.get("chiave_join") or "document_id"
        colonne = [c for c in (chiave, "filename", "document_id", "source_file")
                   if c in tabella.columns]
        for record in tabella.to_dict("records"):
            valori = {str(record.get(c, "")).strip().lower() for c in colonne}
            valori |= {Path(v).stem for v in valori if v}
            if not (valori & chiavi_corpus):
                orfane += 1

    # Rows that do not find a document do not mean the same thing in the two
    # cases, and presenting them in the same way would be a false alarm. A row of
    # the user's CSV without a document is probably a mistake: the user wrote it
    # for a file that is not in the corpus. A row of a series catalogue without a
    # document is instead the normal case: ``glaux_metadata.csv`` describes all
    # 1,421 texts of GLAUx, and a sample loads eighteen of them.
    if not orfane:
        significato = RIGHE_NESSUNA
    elif dataset["origine"] == ORIGINE_UTENTE:
        significato = RIGHE_DA_CONTROLLARE
    else:
        significato = RIGHE_CATALOGO_PIU_AMPIO

    risorsa = dataset.get("risorsa") or {}
    return {
        "righe_non_associate_sono": significato,
        "metadata_present": dataset["origine"] != ORIGINE_NESSUNA,
        "metadata_origin": dataset["origine"],
        "dataset": dataset["nome"],
        "versione": str(risorsa.get("versione", "")),
        "chiave_join": dataset["chiave_join"],
        "risorsa": str(risorsa.get("risorsa", "")),
        "impronta_risorsa": str(risorsa.get("impronta", "")),
        "documenti_totali": int(len(documenti)),
        "documenti_con_metadati": con,
        "documenti_senza_metadati": int(len(documenti) - con),
        "righe_metadati_non_associate": orfane,
    }


def document_catalogue(tokens: pd.DataFrame) -> pd.DataFrame:
    """One row per document, with its metadata and its size.

    This is the table the "corpus" tab shows: sortable by author, by date, by
    dialect, by number of tokens — the thing a user reaches for first when they
    want to know what is actually in the corpus they just loaded.
    """
    if tokens is None or tokens.empty:
        return pd.DataFrame()
    enriched = tokens if "autore" in tokens.columns else enrich_tokens(tokens)

    aggregation = {
        "token": ("form", "size"),
        "frasi": ("sentence_index", "nunique"),
        "forme_uniche": ("form", "nunique"),
        "lemmi_unici": ("lemma", "nunique"),
    }
    grouped = enriched.groupby(
        ["source_file", "document_id", "autore", "opera",
         "datazione", "data_inizio", "secolo", "periodo", "dialetto",
         "genere", "provenienza"],
        dropna=False, sort=False,
    ).agg(**aggregation).reset_index()

    return grouped.sort_values(["autore", "opera"]).reset_index(drop=True)


def author_catalogue(tokens: pd.DataFrame) -> pd.DataFrame:
    """One row per author: dates, dialect, genre, and how much text there is."""
    if tokens is None or tokens.empty:
        return pd.DataFrame()
    enriched = tokens if "autore" in tokens.columns else enrich_tokens(tokens)

    grouped = enriched.groupby(
        ["autore", "autore_en", "tlg", "datazione", "data_inizio", "data_fine",
         "secolo", "periodo", "dialetto", "genere", "provenienza"],
        dropna=False, sort=False,
    ).agg(
        opere=("opera", "nunique"),
        documenti=("document_id", "nunique"),
        frasi=("sentence_index", "nunique"),
        token=("form", "size"),
        forme_uniche=("form", "nunique"),
        lemmi_unici=("lemma", "nunique"),
    ).reset_index()

    return grouped.sort_values("token", ascending=False).reset_index(drop=True)


def unmatched_documents(tokens: pd.DataFrame) -> pd.DataFrame:
    """Documents the catalogue could not identify — shown, never hidden."""
    if tokens is None or tokens.empty:
        return pd.DataFrame(columns=["source_file", "document_id", "token"])
    enriched = tokens if "autore" in tokens.columns else enrich_tokens(tokens)
    unknown = enriched[enriched["autore"] == UNKNOWN]
    if unknown.empty:
        return pd.DataFrame(columns=["source_file", "document_id", "token"])
    return (unknown.groupby(["source_file", "document_id"], sort=False)
            .size().reset_index(name="token")
            .sort_values("token", ascending=False).reset_index(drop=True))


def period_sort_key(period: object) -> int:
    try:
        return PERIOD_ORDER.index(str(period))
    except ValueError:
        return len(PERIOD_ORDER)


def full_catalogue_frame() -> pd.DataFrame:
    """The whole shipped catalogue, for the 'which corpora do you know?' view."""
    files = load_file_catalogue()
    if files.empty:
        return pd.DataFrame()
    columns = [column for column in METADATA_COLUMNS if column in files.columns]
    renamed = {
        "filename": "file", "corpus": "corpus", "author_it": "autore",
        "author_en": "author", "tlg_author_id": "TLG", "work_it": "opera",
        "work_en": "work", "date_label": "datazione",
        "century": "secolo", "period": "periodo", "dialect": "dialetto",
        "genre": "genere", "origin": "provenienza",
    }
    return files[columns].rename(columns=renamed)
