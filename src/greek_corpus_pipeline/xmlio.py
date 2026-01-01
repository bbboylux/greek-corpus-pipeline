from __future__ import annotations

import re

import warnings
import xml.parsers.expat
from pathlib import Path
from typing import Iterable

import pandas as pd


# "head" contains the per-sentence token-ID of the syntactic head (0 = root).
# "token_id" is the per-sentence token-ID taken directly from the XML @id attribute.
# "token_index" is the 1-based sequential position within the sentence (for ordering).
#: "urn:cts:greekLit:tlg0026.tlg001.perseus-grc1" -> ("0026", "001")
_CTS_URN_RE = re.compile(r"tlg(\d{4})\.tlg(\d{3})")
#: Pedalion's compact form: "0059-003", and "0096-00#" when the work is unclear.
_COMPACT_ID_RE = re.compile(r"(\d{4})-(\d{2}[\d#x])")

TOKEN_COLUMNS = [
    "corpus",
    "analyzer",
    "source_file",
    "document_id",
    "sentence_index",
    "sentence_id",
    "token_index",
    "token_id",
    "head",
    "ref",
    "form",
    "lemma",
    "postag",
    "relation",
    # ``artificial="elliptic"``: the node stands in for a word the author left
    # out.  Both corpora write those after the terminal punctuation of the
    # sentence, and three checks would read that placement as a defect, so the
    # attribute is kept rather than dropped.  Tables that do not have it — a
    # CoNLL import, a gold file — are handled by ``elliptic_token_mask``, which
    # recognises the same nodes from the shape of the sentence.
    "artificial",
    # ``analysis="manual"`` / ``analysis="auto"`` on the sentence. Gorman and
    # Pedalion do not write it: everything in them was annotated by a person, so
    # there was nothing to distinguish. GLAUx does write it, because it mixes
    # the two: about a tenth of it is manual annotation inherited from other
    # treebank projects, the rest is the output of a parser. A diagnosis that
    # cannot tell the two apart is unreadable on such a corpus — a rule firing
    # on machine output means something different from the same rule firing on
    # a human's work — so the declaration is carried through to the findings.
    "annotation_mode",
    "tlg_author",
    "tlg_work",
    "cts_urn",
]


def empty_token_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=TOKEN_COLUMNS)


def discover_xml_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    return sorted(path for path in root_path.rglob("*.xml") if path.is_file())


def _int_or_na(value: object) -> object:
    if value is None:
        return pd.NA
    try:
        return int(value)
    except (ValueError, TypeError):
        return pd.NA


# ── Version detection ─────────────────────────────────────────────────────────

def _detect_agdt_version(treebank: dict) -> str:
    """Return '2.0' for AGDT 2.x treebanks, '1.1' for everything else."""
    raw = treebank.get("@version", "")
    if isinstance(raw, str) and raw.startswith("2"):
        return "2.0"
    return "1.1"


# ── Main parser ───────────────────────────────────────────────────────────────

class _TreebankReader:
    """Collect the token table straight off the XML event stream.

    Loading a corpus is the first thing the user waits for, so the reader does
    not build a nested dictionary for every element and attribute in the file —
    hundreds of thousands of elements for a corpus the size of Pedalion — and
    then copy that dictionary into one row dictionary per token, which pandas
    would copy again into columns.

    Driving expat directly skips both copies: the handlers below append to one
    list per column and never materialise a row.  Expat is created without a
    namespace separator and no character-data handler is installed, so tag
    names arrive exactly as they are written in the file and text nodes are
    never assembled.

    The element grammar is this: ``sentence`` is read only as a direct child of
    a ``treebank`` root, ``word`` only as a direct child of such a ``sentence``,
    and everything else is ignored.
    """

    __slots__ = (
        "corpus", "source_file", "document_id", "depth", "in_treebank",
        "in_sentence", "agdt2", "sentence_index", "sentence_id", "token_index",
        "sentence_indices", "sentence_ids", "token_indices", "token_ids",
        "heads", "refs", "forms", "lemmas", "postags", "relations",
        "artificials", "annotation_mode", "annotation_modes",
        "tlg_author", "tlg_work", "cts_urn",
    )

    def __init__(self, corpus: str, source_file: str, document_id: str) -> None:
        self.corpus = corpus
        self.source_file = source_file
        self.document_id = document_id
        self.depth = -1
        self.in_treebank = False
        self.in_sentence = False
        self.agdt2 = False
        self.sentence_index = 0
        self.sentence_id = ""
        self.token_index = 0
        self.annotation_mode: object = pd.NA
        # Identity of the text, as the file itself declares it. Gorman writes a
        # CTS URN on every sentence ("urn:cts:greekLit:tlg0026.tlg001..."),
        # Pedalion a bare "0026-001". Both name the TLG author and work, which
        # is the only attribution in the file that is not a guess.
        self.tlg_author = ""
        self.tlg_work = ""
        self.cts_urn = ""
        self.sentence_indices: list[int] = []
        self.sentence_ids: list[str] = []
        self.token_indices: list[int] = []
        self.token_ids: list[int] = []
        self.heads: list[object] = []
        self.refs: list[object] = []
        self.forms: list[object] = []
        self.lemmas: list[object] = []
        self.postags: list[object] = []
        self.relations: list[object] = []
        self.artificials: list[object] = []
        self.annotation_modes: list[object] = []

    def start(self, name: str, attributes: dict) -> None:
        self.depth += 1
        if self.depth == 0:
            self.in_treebank = name == "treebank"
            if self.in_treebank:
                self.agdt2 = _detect_agdt_version(
                    {"@version": attributes.get("version", "")}) == "2.0"
            return
        if not self.in_treebank:
            return
        if self.depth == 1:
            self.in_sentence = name == "sentence"
            if self.in_sentence:
                self.sentence_index += 1
                self.sentence_id = str(
                    attributes.get("id") or attributes.get("subdoc") or self.sentence_index)
                self.token_index = 0
                mode = attributes.get("analysis")
                self.annotation_mode = (
                    (mode.strip().lower() or pd.NA) if mode is not None else pd.NA)
                if not self.tlg_author:
                    self._read_identity(attributes)
            return
        if self.depth == 2 and self.in_sentence and name == "word":
            self._word(attributes)

    def _read_identity(self, attributes: dict) -> None:
        """Pull the TLG author/work identifier out of the sentence attributes.

        Read once per file, from the first sentence that carries it. Two
        serialisations are in the wild and both are handled: the Perseids CTS
        URN, and the compact "author-work" form used by Pedalion. Everything
        else — Trismegistos numbers for papyri, project-local labels like
        "Genesis" — is left alone: an identifier we cannot parse is better
        recorded as absent than mapped onto a plausible-looking author.
        """
        for key in ("document_id", "subdoc"):
            raw = str(attributes.get(key) or "")
            if not raw:
                continue
            urn = _CTS_URN_RE.search(raw)
            if urn:
                self.tlg_author = f"tlg{urn.group(1)}"
                self.tlg_work = f"tlg{urn.group(2)}"
                self.cts_urn = urn.group(0)
                return
            compact = _COMPACT_ID_RE.fullmatch(raw.strip())
            if compact:
                self.tlg_author = f"tlg{compact.group(1)}"
                work = compact.group(2)
                self.tlg_work = f"tlg{work}" if work.isdigit() else ""
                self.cts_urn = ""
                return

    def end(self, name: str) -> None:
        self.depth -= 1

    def _word(self, attributes: dict) -> None:
        raw_id = attributes.get("id")
        if self.agdt2:
            # Multiword surface token or empty node — skip
            raw_id = str(raw_id if raw_id is not None else "")
            if "-" in raw_id or "." in raw_id:
                return
        token_id = _int_or_na(raw_id)
        if token_id is pd.NA:
            return
        self.token_index += 1
        self.sentence_indices.append(self.sentence_index)
        self.sentence_ids.append(self.sentence_id)
        self.token_indices.append(self.token_index)
        self.token_ids.append(int(token_id))
        self.heads.append(_int_or_na(attributes.get("head")))
        # The text normalisation written out in full: an expat attribute is either a
        # string or absent, so the type check that would be needed in the general case
        # is not needed here, and this runs five times per token — a million calls over
        # 27 files.
        ref = attributes.get("ref")
        form = attributes.get("form")
        lemma = attributes.get("lemma")
        postag = attributes.get("postag")
        relation = attributes.get("relation")
        artificial = attributes.get("artificial")
        self.artificials.append(
            (artificial.strip() or pd.NA) if artificial is not None else pd.NA)
        self.annotation_modes.append(self.annotation_mode)
        self.refs.append((ref.strip() or pd.NA) if ref is not None else pd.NA)
        self.forms.append((form.strip() or pd.NA) if form is not None else pd.NA)
        self.lemmas.append((lemma.strip() or pd.NA) if lemma is not None else pd.NA)
        self.postags.append((postag.strip() or pd.NA) if postag is not None else pd.NA)
        self.relations.append((relation.strip() or pd.NA) if relation is not None else pd.NA)

    def frame(self) -> pd.DataFrame:
        total = len(self.token_ids)
        if not total:
            return empty_token_frame()
        return pd.DataFrame({
            "corpus": [self.corpus] * total,
            "analyzer": ["corpus"] * total,
            "source_file": [self.source_file] * total,
            "document_id": [self.document_id] * total,
            "sentence_index": self.sentence_indices,
            "sentence_id": self.sentence_ids,
            "token_index": self.token_indices,
            "token_id": self.token_ids,
            "head": self.heads,
            "ref": self.refs,
            "form": self.forms,
            "lemma": self.lemmas,
            "postag": self.postags,
            "relation": self.relations,
            "artificial": self.artificials,
            "annotation_mode": self.annotation_modes,
            "tlg_author": self.tlg_author,
            "tlg_work": self.tlg_work,
            "cts_urn": self.cts_urn,
        }, columns=TOKEN_COLUMNS)


def parse_treebank_xml(xml_path: str | Path, corpus_name: str | None = None) -> pd.DataFrame:
    path = Path(xml_path)
    with path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    reader = _TreebankReader(
        corpus=corpus_name or path.parent.name or "corpus",
        source_file=path.name,
        document_id=path.stem,
    )
    parser = xml.parsers.expat.ParserCreate()
    parser.StartElementHandler = reader.start
    parser.EndElementHandler = reader.end
    parser.Parse(text, True)
    return reader.frame()


def load_corpus_from_directory(root: str | Path, corpus_name: str | None = None) -> pd.DataFrame:
    xml_files = discover_xml_files(root)
    if not xml_files:
        return empty_token_frame()

    frames: list[pd.DataFrame] = []
    failed: list[tuple[Path, Exception]] = []
    for path in xml_files:
        try:
            frames.append(parse_treebank_xml(path, corpus_name=corpus_name))
        except Exception as exc:
            failed.append((path, exc))

    if failed:
        names = ", ".join(p.name for p, _ in failed)
        warnings.warn(
            f"{len(failed)} XML file(s) could not be parsed and were skipped: {names}. "
            f"First error: {failed[0][1]}"
        )

    if not frames:
        return empty_token_frame()
    return pd.concat(frames, ignore_index=True)


def _as_int_column(values: pd.Series) -> pd.Series:
    """Return *values* as a nullable-integer Series.

    Token ids and syntactic heads are integers, but a parquet round-trip turns
    them into float64 as soon as a single value is missing.  Casting back to
    ``Int64`` keeps ``<NA>`` for missing values while rendering 20 as ``20``
    instead of ``20.0``.
    """
    return pd.to_numeric(values, errors="coerce").astype("Int64")


def export_sentence_csvs(tokens: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    grouped = tokens.sort_values(["source_file", "sentence_index", "token_index"]).groupby(
        ["source_file", "sentence_index"], sort=True
    )

    sentence_offsets: dict[str, int] = {}
    for (source_file, _sentence_index), sentence_df in grouped:
        document_dir = output_root / source_file
        document_dir.mkdir(parents=True, exist_ok=True)
        next_offset = sentence_offsets.get(source_file, 0)

        csv_dict: dict = {
            "@id": _as_int_column(sentence_df["token_id"]).tolist(),
            "@form": sentence_df["form"].tolist(),
            "@lemma": sentence_df["lemma"].tolist(),
            "@postag": sentence_df["postag"].tolist(),
            "@relation": sentence_df["relation"].tolist(),
            "@head": (_as_int_column(sentence_df["head"]).tolist()
                      if "head" in sentence_df.columns else [pd.NA] * len(sentence_df)),
        }
        csv_df = pd.DataFrame(csv_dict)

        if "ref" in sentence_df.columns and sentence_df["ref"].notna().any():
            csv_df["@ref"] = sentence_df["ref"].tolist()

        target_path = document_dir / f"{next_offset}.csv"
        csv_df.to_csv(target_path, index=False)
        written_paths.append(target_path)
        sentence_offsets[source_file] = next_offset + 1

    return written_paths


def sentence_groups(tokens: pd.DataFrame) -> Iterable[tuple[tuple[str, int], pd.DataFrame]]:
    grouped = tokens.sort_values(["source_file", "sentence_index", "token_index"]).groupby(
        ["source_file", "sentence_index"], sort=True
    )
    for key, sentence_df in grouped:
        yield key, sentence_df.reset_index(drop=True)


def export_corrected_xml(
    tokens: pd.DataFrame,
    output_dir: str | Path,
    version: str = "1.1",
) -> list[Path]:
    """Export corrected tokens as AGDT-format XML files, one per source document.

    Reproduces the standard AGDT treebank structure::

        <treebank version="1.1">
          <sentence id="1">
            <word id="1" form="..." lemma="..." postag="..." relation="..." head="..."/>
          </sentence>
        </treebank>

    Each unique ``document_id`` produces one ``.xml`` file named
    ``<document_id>.xml``.  Returns the list of written paths.
    """
    import math

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def _attr(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        s = str(value).strip()
        return s if s and s.lower() not in {"nan", "<na>", "none"} else None

    def _int_attr(value: object) -> str | None:
        """Render an integer-valued attribute (id / head) without a decimal part.

        Parquet round-trips store ``head`` as float64 (because missing heads are
        NaN), so ``str(row["head"])`` would emit ``"20.0"`` instead of ``"20"``
        and produce XML that AGDT tools reject.
        """
        s = _attr(value)
        if s is None:
            return None
        try:
            return str(int(float(s)))
        except (TypeError, ValueError):
            return s

    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
        )

    sorted_tokens = tokens.sort_values(["document_id", "sentence_index", "token_index"])

    for doc_id, doc_df in sorted_tokens.groupby("document_id", sort=True):
        header = '<?xml version="1.0" encoding="UTF-8"?>'
        tb_open = '<treebank version="' + _esc(version) + '">'
        lines: list[str] = [header, tb_open]

        for _sent_idx, sent_df in doc_df.groupby("sentence_index", sort=True):
            sent_df = sent_df.sort_values("token_index")
            sent_id = (
                sent_df["sentence_id"].iloc[0]
                if "sentence_id" in sent_df.columns
                else str(int(_sent_idx))
            )
            sent_open = '  <sentence id="' + _esc(str(sent_id)) + '"'
            # Written back out for the same reason it is read in: a corpus that
            # declares which sentences a person checked must not lose that
            # declaration by passing through the program.
            if "annotation_mode" in sent_df.columns:
                mode = _attr(sent_df["annotation_mode"].iloc[0])
                if mode:
                    sent_open += ' analysis="' + _esc(mode) + '"'
            lines.append(sent_open + '>')

            for _, row in sent_df.iterrows():
                attrs: list[str] = []
                tok_id = _int_attr(row.get("token_id"))
                if tok_id:
                    attrs.append('id="' + _esc(str(tok_id)) + '"')
                for field, xml_attr in [
                    ("form",     "form"),
                    ("lemma",    "lemma"),
                    ("postag",   "postag"),
                    ("relation", "relation"),
                    ("head",     "head"),
                    ("ref",      "ref"),
                    # Written back out: an exported file that loses it turns
                    # every supplied word into a word of the text.
                    ("artificial", "artificial"),
                ]:
                    # head is an integer token-ID: never write it as "20.0"
                    val = (_int_attr(row.get(field)) if field == "head"
                           else _attr(row.get(field)))
                    if val is not None:
                        attrs.append(xml_attr + '="' + _esc(str(val)) + '"')
                lines.append('    <word ' + ' '.join(attrs) + '/>')

            lines.append('  </sentence>')

        lines.append('</treebank>')
        out_path = output_root / (str(doc_id) + '.xml')
        out_path.write_text('\n'.join(lines), encoding='utf-8')
        written.append(out_path)

    return written
