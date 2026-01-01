"""Export to CoNLL-U, the format Universal Dependencies uses.

Two conversions are possible, and they are not the same thing.

**Format conversion** (:func:`export_conllu`, the one that the interface and the
command line use) rewrites an AGDT treebank
as a CoNLL-U file *without touching the annotation*: the AGDT relation goes in
DEPREL as it stands, the nine-character tag goes in XPOS untouched, the
morphology it encodes is spelled out in FEATS, and UPOS is filled from the
first character. Nothing is invented and nothing is lost — the original tag can
be read straight back out of XPOS. This is what most people actually want,
because it lets the whole UD toolchain (validators, viewers, converters,
``udapi``) operate on AGDT data.

**Scheme conversion** is a different and much harder operation: Universal
Dependencies analyses coordination, prepositions and copulas the other way round
from the Prague tradition AGDT follows, so a real conversion has to rebuild parts
of the tree. The program does not implement it and does not offer it: no page and
no option of the command line performs it. :func:`convert_with_udapi`, which only
code can call, delegates it to ``udapi-agldt`` when that package is installed.

Output from Stanza and UDPipe is already UD-annotated, so for those the format
conversion *is* the whole job.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from .agdt_schema import (
    CASE_SLOT,
    DEGREE_SLOT,
    GENDER_SLOT,
    MOOD_SLOT,
    NUMBER_SLOT,
    PERSON_SLOT,
    POS_SLOT,
    TAG_LENGTH,
    TENSE_SLOT,
    VOICE_SLOT,
)


def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text, in the language of the interface, with English as the fallback.

    This message ends up in a warning window, so it follows the chosen language; the
    fallback exists because the module must also work without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:
        return fallback.format(*args) if args else fallback
    return text


#: AGDT part of speech (first character) -> UPOS.
#:
#: Two mappings deserve a note. AGDT ``l`` is the article, which UD calls DET.
#: AGDT ``g`` is the particle, for which UD has no dedicated tag: PART is the
#: closest, and it is what the existing AGDT-to-UD conversions use.
UPOS_BY_POS = {
    "n": "NOUN", "v": "VERB", "t": "VERB", "a": "ADJ", "d": "ADV",
    "l": "DET", "g": "PART", "c": "CCONJ", "r": "ADP", "p": "PRON",
    "m": "NUM", "i": "INTJ", "e": "INTJ", "u": "PUNCT", "x": "X",
}

FEATURE_MAPS: dict[int, tuple[str, dict[str, str]]] = {
    PERSON_SLOT: ("Person", {"1": "1", "2": "2", "3": "3"}),
    NUMBER_SLOT: ("Number", {"s": "Sing", "p": "Plur", "d": "Dual"}),
    TENSE_SLOT: ("Tense", {"p": "Pres", "i": "Imp", "r": "Perf", "l": "Pqp",
                           "t": "Perf", "f": "Fut", "a": "Past"}),
    VOICE_SLOT: ("Voice", {"a": "Act", "p": "Pass", "m": "Mid", "e": "MidPass"}),
    GENDER_SLOT: ("Gender", {"m": "Masc", "f": "Fem", "n": "Neut"}),
    CASE_SLOT: ("Case", {"n": "Nom", "g": "Gen", "d": "Dat", "a": "Acc",
                         "v": "Voc", "l": "Loc"}),
    DEGREE_SLOT: ("Degree", {"c": "Cmp", "s": "Sup"}),
}

#: Mood is special: AGDT puts infinitive and participle in the mood slot, where
#: UD puts them in VerbForm and leaves Mood empty. Splitting them here keeps
#: the output valid rather than merely plausible.
MOOD_VALUES = {"i": ("Mood", "Ind"), "s": ("Mood", "Sub"), "o": ("Mood", "Opt"),
               "m": ("Mood", "Imp"), "n": ("VerbForm", "Inf"),
               "p": ("VerbForm", "Part"), "d": ("VerbForm", "Ger")}


def features_from_postag(postag: object) -> str:
    """The FEATS column for one AGDT tag, or ``_`` when it encodes nothing."""
    if not isinstance(postag, str) or len(postag) != TAG_LENGTH:
        return "_"
    features: list[tuple[str, str]] = []
    for index, (name, table) in FEATURE_MAPS.items():
        value = table.get(postag[index])
        if value:
            features.append((name, value))
    mood = MOOD_VALUES.get(postag[MOOD_SLOT])
    if mood:
        features.append(mood)
    if postag[POS_SLOT] in {"v", "t"} and not any(n == "VerbForm" for n, _ in features):
        features.append(("VerbForm", "Fin"))
    if not features:
        return "_"
    return "|".join(f"{name}={value}" for name, value in sorted(features))


def upos_from_postag(postag: object) -> str:
    if not isinstance(postag, str) or not postag:
        return "X"
    return UPOS_BY_POS.get(postag[0], "X")


def _field(value: object) -> str:
    """A CoNLL-U field: never empty, never containing a tab or a newline."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "_"
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return "_"
    return text.replace("\t", " ").replace("\n", " ")


def _misc_value(value: object) -> str:
    """A value safe inside MISC, whose separators are ``|`` and ``=``.

    AGDT ``ref`` attributes routinely contain pipes ("Leuven|0059-003|1|1"),
    which would silently split one MISC attribute into four malformed ones and
    make the file fail validation. Escaping is not optional here.
    """
    text = _field(value)
    if text == "_":
        return "_"
    return (text.replace("\\", "/").replace("|", ",").replace("=", "-")
            .replace(" ", "_"))


def sentence_to_conllu(sentence: pd.DataFrame, *, sentence_id: str,
                       text: str = "", extra: dict[str, str] | None = None) -> str:
    """One sentence as CoNLL-U text, comments included.

    Token identifiers are renumbered 1..n. AGDT identifiers are not always a
    clean sequence — elliptic nodes and multiword expressions interrupt it —
    and CoNLL-U requires one, so the original id travels in MISC as
    ``AGDTId=`` and the head is remapped through the same table. Nothing about
    the tree changes; only the numbering does.
    """
    lines: list[str] = [f"# sent_id = {sentence_id}"]
    if text:
        lines.append(f"# text = {text}")
    for key, value in (extra or {}).items():
        lines.append(f"# {key} = {value}")

    # Columns are pulled out as plain lists once: walking the frame with
    # ``iterrows()`` would rebuild a Series per row, and the export would take
    # longer than the diagnosis that produced the data.
    def _column(name: str) -> list:
        if name in sentence.columns:
            return sentence[name].tolist()
        return [None] * len(sentence)

    original_ids = [str(value) for value in sentence["token_id"]]
    forms = _column("form")
    lemmas = _column("lemma")
    postags = _column("postag")
    heads = _column("head")
    relations = _column("relation")
    refs = _column("ref")
    renumbered = {old: position for position, old in enumerate(original_ids, start=1)}

    for position in range(1, len(original_ids) + 1):
        index = position - 1
        postag = postags[index]
        head_raw = heads[index]
        head = "0"
        unresolved = False
        if head_raw is not None and not pd.isna(head_raw):
            key = str(int(head_raw)) if isinstance(head_raw, float) else str(head_raw)
            if key in {"0", "0.0"}:
                head = "0"
            elif key in renumbered:
                head = str(renumbered[key])
            else:
                # A head we cannot resolve is a defect the diagnostic side
                # reports; here we must still emit a valid file, so the token
                # is attached to the root and the fact is recorded in MISC.
                head = "0"
                unresolved = True

        misc = [f"AGDTId={_misc_value(original_ids[index])}"]
        # ``if refs[index]`` would not do: when a reference is missing pandas returns NA,
        # whose truth value is not defined, and the test would raise TypeError. The value
        # is first tested for presence.
        reference = refs[index]
        if reference is not None and not pd.isna(reference) and str(reference).strip():
            misc.append(f"Ref={_misc_value(reference)}")
        if unresolved:
            misc.append("UnresolvedHead=Yes")

        lines.append("\t".join([
            str(position),
            _field(forms[index]),
            _field(lemmas[index]),
            upos_from_postag(postag),
            _field(postag),
            features_from_postag(postag),
            head,
            _field(relations[index]),
            "_",
            "|".join(misc),
        ]))
    return "\n".join(lines) + "\n"


def tokens_to_conllu(tokens: pd.DataFrame, *, corpus_name: str = "") -> str:
    """A whole token table as one CoNLL-U document."""
    if tokens is None or tokens.empty:
        return ""
    keys = [key for key in ("source_file", "document_id", "sentence_index")
            if key in tokens.columns]
    chunks: list[str] = []
    for name, sentence in tokens.groupby(keys, sort=False):
        values = name if isinstance(name, tuple) else (name,)
        parts = [str(value) for value in values]
        sentence_key = "-".join(parts)
        text = " ".join(str(value) for value in sentence["form"]
                        if isinstance(value, str) and value.strip())
        extra = {}
        if corpus_name:
            extra["corpus"] = corpus_name
        if "sentence_id" in sentence.columns:
            first = sentence["sentence_id"].iloc[0]
            if _field(first) != "_":
                extra["agdt_sentence_id"] = _field(first)
        if "cts_urn" in sentence.columns:
            urn = _field(sentence["cts_urn"].iloc[0])
            if urn != "_":
                extra["cts_urn"] = urn
        chunks.append(sentence_to_conllu(sentence, sentence_id=sentence_key,
                                         text=text, extra=extra))
    return "\n".join(chunks)


def export_conllu(tokens: pd.DataFrame, output_path: str | Path, *,
                  corpus_name: str = "", per_file: bool = False) -> list[Path]:
    """Write CoNLL-U. One document, or one file per source file."""
    target = Path(output_path)
    if not per_file:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(tokens_to_conllu(tokens, corpus_name=corpus_name),
                          encoding="utf-8")
        return [target]

    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source_file, chunk in tokens.groupby("source_file", sort=True):
        name = Path(str(source_file)).stem + ".conllu"
        path = target / name
        path.write_text(tokens_to_conllu(chunk, corpus_name=corpus_name),
                        encoding="utf-8")
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# The real scheme conversion, when the reference implementation is available
# ---------------------------------------------------------------------------

def udapi_available() -> bool:
    """Is Mambrini's ``udapi-agldt`` importable?"""
    return (importlib.util.find_spec("udapi") is not None
            and importlib.util.find_spec("udapi_agldt") is not None)


def convert_with_udapi(xml_paths: list[str | Path], output_dir: str | Path,
                       *, reader: str = "agldt") -> list[Path]:
    """Complete conversion from AGDT to Universal Dependencies, delegated to udapi.

    **It is not part of the interface flow, and it is not a function that the
    program promises.** No page calls it and it does not appear in ``__all__``:
    it can be reached only from code, by importing it. The CoNLL-U export that
    GCP really offers is :func:`export_gold_conllu`, which converts the
    *format* while keeping the AGDT annotation and requires nothing external.

    **It requires two external components that GCP does not install and does not
    declare among its dependencies**: ``udapi`` and ``udapi_agldt`` (the
    AGDT/GLAUx reader). If they are missing, :func:`udapi_available` returns
    ``False`` and this function raises ``RuntimeError`` with a message that says
    so. Declaring them among the optional dependencies would mean promising a
    conversion that the interface does not offer.

    *reader* is ``"agldt"`` for Gorman and Perseus AGDT files, ``"glaux"`` for
    the Leuven ones. ``fix_cycles=True`` is passed because the reader cannot
    build a UD tree from a cyclic graph and several files in both corpora
    contain one — which is, incidentally, one of the things the diagnostic side
    of this program reports.
    """
    if not udapi_available():
        raise RuntimeError(_t(
            "conllu.err.udapi",
            "Converting to the Universal Dependencies scheme needs the udapi-agldt "
            "package, which does not appear to be installed. Export to CoNLL-U with the "
            "original AGDT annotation is available anyway and needs nothing."))

    from udapi.core.document import Document  # noqa: PLC0415
    if reader == "glaux":
        from udapi_agldt.read.glaux import Glaux as Reader  # noqa: PLC0415
    else:
        from udapi_agldt.read.agldt import Agldt as Reader  # noqa: PLC0415

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for xml_path in xml_paths:
        path = Path(xml_path)
        document = Document()
        Reader(str(path), fix_cycles=True).apply_on_document(document)
        out = destination / (path.stem + ".conllu")
        document.store_conllu(str(out))
        written.append(out)
    return written
