"""The form dictionary: what the program accepts, and what it does with it.

This module exists for a question that the user asked while looking at the
field “Form dictionary”: *which file does it want as input?* The answer was
only in the code — two columns, ``form`` and ``lemma`` — and code is not a
place where one goes to look. Here the format is declared once, so that the
interface can show it, the downloadable template can be generated from it,
and the reader can accept exactly what is written on the screen.

The format, in full:

* a CSV with a **header**, separated by comma, semicolon or tab, in UTF-8
  (also with BOM: this is what Excel writes);
* column ``form`` — **required**: the form as it appears in the corpus;
* column ``postag`` — optional: the morphological tag to assign;
* column ``lemma`` — optional: the lemma to assign;
* at least one of ``postag`` and ``lemma`` must be present, otherwise the
  file says nothing and is rejected with an explanation;
* an empty cell **leaves the value as it is**: it does not delete it;
* rows without a form, or without anything to assign, are skipped and counted;
* if the same form appears twice, the last row prevails;
* entries that find no form in the corpus are not an error: they are
  ignored and counted, so that the user knows how much of the dictionary was
  actually used.

The comparison between the form of the dictionary and the form of the corpus
is **exact**: accents, breathings and capitals count (ἄνδρες, Ἄνδρες and
ανδρες are three different entries). The only thing the program normalises is
the Unicode composition — the same character can be written precomposed or as
a letter plus a diacritic — because two forms that look identical must match
even when they were typed on two different keyboards.

The two-column file ``form,lemma`` keeps working without changes: it is the
special case in which ``postag`` is missing.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

#: The canonical names of the columns, in the order in which they are read.
FORM_COLUMN = "form"
POSTAG_COLUMN = "postag"
LEMMA_COLUMN = "lemma"
DICTIONARY_COLUMNS = (FORM_COLUMN, POSTAG_COLUMN, LEMMA_COLUMN)

#: The columns that carry a value to assign. At least one must be present.
VALUE_COLUMNS = (POSTAG_COLUMN, LEMMA_COLUMN)

#: Accepted headers, in Italian and in English. A file written by hand calls “forma” what
#: the program calls ``form``, and rejecting it for this would be pedantry: the
#: comparison ignores capitals, spaces and BOM.
HEADER_SYNONYMS: dict[str, str] = {
    "form": FORM_COLUMN,
    "forma": FORM_COLUMN,
    "parola": FORM_COLUMN,
    "word": FORM_COLUMN,
    "token": FORM_COLUMN,
    "surface": FORM_COLUMN,
    "surface_form": FORM_COLUMN,

    "postag": POSTAG_COLUMN,
    "pos_tag": POSTAG_COLUMN,
    "pos-tag": POSTAG_COLUMN,
    "tag": POSTAG_COLUMN,
    "etichetta": POSTAG_COLUMN,
    "postag_corretto": POSTAG_COLUMN,
    "corrected_postag": POSTAG_COLUMN,
    "postag_gold": POSTAG_COLUMN,
    "nuovo_postag": POSTAG_COLUMN,
    "new_postag": POSTAG_COLUMN,

    "lemma": LEMMA_COLUMN,
    "lemme": LEMMA_COLUMN,
    "lemma_corretto": LEMMA_COLUMN,
    "corrected_lemma": LEMMA_COLUMN,
    "lemma_gold": LEMMA_COLUMN,
    "nuovo_lemma": LEMMA_COLUMN,
    "new_lemma": LEMMA_COLUMN,
    "headword": LEMMA_COLUMN,
}

#: The encodings tried, in order. utf-8-sig comes first because it is what Excel writes
#: when asked for “CSV UTF-8”, and it is the most common case.
_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "cp1253")


def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text in the language of the interface, with English as the fallback.

    Same reason as in :mod:`greek_corpus_pipeline.gold`: these messages end up in a
    warning window and must follow the chosen language, but the module must remain
    usable without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:
        return fallback.format(*args) if args else fallback
    return text


# ────────────────────────────────────────────────────────── the key ──
def match_key(value: object) -> str:
    """The form reduced to the key with which the corpus is searched.

    Nothing linguistic is removed: accents, breathings and capitals stay. Only the space
    around the cell is removed and a Unicode composition is chosen, because ``ά``
    written in one piece and ``ά`` written as alpha plus acute are the same word for the
    reader and two different strings for the computer.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def _text_series(values: pd.Series) -> pd.Series:
    """Any column as text, without NaN and without spaces at the edges."""
    return values.astype("string").fillna("").astype(str).str.strip()


def keys_of(forms: pd.Series) -> pd.Series:
    """The keys of a column of forms, normalising only the distinct forms.

    On Gorman the column has 625,176 rows and 69,461 different forms: normalising row by
    row means calling :func:`unicodedata.normalize` 625,176 times to obtain 69,461
    answers. The distinct forms are normalised and mapped back, which is the same thing
    in a fraction of the time.
    """
    text = forms.astype("string").fillna("").astype(str)
    lookup = {value: match_key(value) for value in text.unique()}
    return text.map(lookup)


# ────────────────────────────────────────────────── what was read ──
@dataclass(frozen=True)
class DictionaryReport:
    """What the program has understood of the file, in numbers.

    It serves to answer on screen — before touching the corpus — the question “what will
    this file do?”. A dictionary that has found no form is a piece of information, not
    an error, and must be said before and not after.
    """

    rows_read: int = 0
    entries: int = 0
    with_lemma: int = 0
    with_postag: int = 0
    skipped_no_form: int = 0
    skipped_no_value: int = 0
    duplicate_forms: int = 0
    columns_found: tuple[str, ...] = field(default_factory=tuple)
    path: str = ""

    @property
    def skipped_rows(self) -> int:
        return self.skipped_no_form + self.skipped_no_value


@dataclass(frozen=True)
class DictionaryCoverage:
    """How much of this dictionary actually touches the loaded corpus."""

    entries: int = 0
    matched_entries: int = 0
    unmatched_entries: int = 0
    tokens_matched: int = 0
    tokens_lemma_changed: int = 0
    tokens_postag_changed: int = 0


def empty_dictionary() -> pd.DataFrame:
    """An empty dictionary with the right columns."""
    return pd.DataFrame({name: pd.Series(dtype=str) for name in DICTIONARY_COLUMNS})


def _canonical_headers(frame: pd.DataFrame) -> dict[object, str]:
    """The headers of the file translated into the three canonical names."""
    renamed: dict[object, str] = {}
    for column in frame.columns:
        key = str(column).replace("﻿", "").strip().lower().replace(" ", "_")
        canonical = HEADER_SYNONYMS.get(key)
        if canonical and canonical not in renamed.values():
            renamed[column] = canonical
    return renamed


# ─────────────────────────────────────────────────────────── reading ──
def normalise_form_dictionary(
    frame: pd.DataFrame | None,
) -> tuple[pd.DataFrame, DictionaryReport]:
    """Bring any dictionary to the canonical form ``form, postag, lemma``.

    This is the part that does not touch the disk, so that the format can be tested
    without writing a file. It raises ``ValueError`` — with an explanation, not with a
    list of columns — when the form is missing or when there is nothing to assign.
    """
    if frame is None or frame.empty:
        return empty_dictionary(), DictionaryReport()

    renamed = _canonical_headers(frame)
    found = tuple(renamed.values())

    if FORM_COLUMN not in found:
        raise ValueError(_t(
            "review.dict.err.no_form",
            "The file has no «form» column: without the form the program does not know "
            "what to apply the correction to. The columns found are: {0}.", ", ".join(str(c) for c in frame.columns)))
    if not any(name in found for name in VALUE_COLUMNS):
        raise ValueError(_t(
            "review.dict.err.no_value",
            "The file has a «form» column but neither «postag» nor «lemma»: there is "
            "nothing to assign. The columns found are: {0}.",
            ", ".join(str(c) for c in frame.columns)))

    working = frame.rename(columns=renamed)
    entries = pd.DataFrame(index=working.index)
    for name in DICTIONARY_COLUMNS:
        entries[name] = (_text_series(working[name]) if name in working.columns
                         else "")

    rows_read = int(len(entries))
    no_form = entries[FORM_COLUMN].eq("")
    skipped_no_form = int(no_form.sum())
    entries = entries[~no_form]

    no_value = entries[POSTAG_COLUMN].eq("") & entries[LEMMA_COLUMN].eq("")
    skipped_no_value = int(no_value.sum())
    entries = entries[~no_value]

    # Same form twice: the last row prevails, which is the least surprising rule for
    # whoever corrected the file by hand from top to bottom.
    keys = entries[FORM_COLUMN].map(match_key)
    duplicates = int(keys.duplicated(keep="last").sum())
    entries = entries[~keys.duplicated(keep="last")].reset_index(drop=True)

    report = DictionaryReport(
        rows_read=rows_read,
        entries=int(len(entries)),
        with_lemma=int(entries[LEMMA_COLUMN].ne("").sum()),
        with_postag=int(entries[POSTAG_COLUMN].ne("").sum()),
        skipped_no_form=skipped_no_form,
        skipped_no_value=skipped_no_value,
        duplicate_forms=duplicates,
        columns_found=found,
    )
    return entries, report


def read_form_dictionary(
    path: str | Path,
) -> tuple[pd.DataFrame, DictionaryReport]:
    """Read the user's CSV and return its canonical form plus the report.

    The separator is recognised automatically — comma, semicolon or tab — because an
    Italian spreadsheet saves with a semicolon without asking anyone. Rows that begin
    with ``#`` are comments: this is what makes the downloadable template harmless until
    the user fills it in.
    """
    source = Path(path)
    if not source.exists():
        raise ValueError(_t(
            "review.dict.err.missing", "That file does not exist: {0}", str(source)))

    last_error: Exception | None = None
    parsed: list[pd.DataFrame] = []
    for encoding in _ENCODINGS:
        for options in ({"sep": None, "engine": "python"}, {"sep": ","},
                        {"sep": ";"}, {"sep": "\t"}):
            try:
                raw = pd.read_csv(
                    source, dtype=str, keep_default_na=False, comment="#",
                    encoding=encoding, **options)
            except Exception as error:                 # noqa: BLE001
                last_error = error
                continue
            if not len(raw.columns):
                continue
            # Automatic separator detection fails on single-column files — on “form” it
            # chose the “r” — and the proof that it failed is that no header is
            # recognised any more. In that case the file is not rejected: the next
            # reading is tried.
            if FORM_COLUMN in _canonical_headers(raw).values():
                entries, report = normalise_form_dictionary(raw)
                return entries, DictionaryReport(
                    rows_read=report.rows_read,
                    entries=report.entries,
                    with_lemma=report.with_lemma,
                    with_postag=report.with_postag,
                    skipped_no_form=report.skipped_no_form,
                    skipped_no_value=report.skipped_no_value,
                    duplicate_forms=report.duplicate_forms,
                    columns_found=report.columns_found,
                    path=str(source),
                )
            parsed.append(raw)
    if parsed:
        # No reading found the form column: the file must be rejected, but with the
        # right explanation and not with a CSV error.
        normalise_form_dictionary(parsed[0])
    raise ValueError(_t(
        "review.dict.err.unreadable",
        "The file cannot be read as a CSV: {0}", str(last_error)))


# ─────────────────────────────────────────────────────────── the template ──
TEMPLATE_ROWS = (
    ("στρατιῶται", "n-p---mn-", "στρατιώτης"),
    ("ἄνδρες", "n-p---mn-", "ἀνήρ"),
)


def form_dictionary_template() -> str:
    """The text of the example CSV, with the right header and the instructions inside.

    The example rows are commented out: whoever downloads the template and applies it
    without touching it changes nothing in their corpus, which is the only acceptable
    behaviour for an example file.
    """
    lines = [
        "# Form dictionary — Greek Corpus Pipeline",
        "#",
        "# form   = the form as it appears in the corpus (required)",
        "# postag = morphological tag to assign (optional)",
        "# lemma  = lemma to assign (optional)",
        "#",
        "# At least one of postag and lemma must be filled in.",
        "# An empty cell leaves the value as it is.",
        "# Lines starting with # are comments.",
        "#",
        ",".join(DICTIONARY_COLUMNS),
    ]
    lines += ["# " + ",".join(row) for row in TEMPLATE_ROWS]
    return "\n".join(lines) + "\n"


def write_form_dictionary_template(path: str | Path) -> Path:
    """Write the template where the user has chosen, and return its path."""
    target = Path(path)
    if target.suffix.lower() != ".csv":
        target = target.with_suffix(".csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(form_dictionary_template(), encoding="utf-8-sig")
    return target


def write_form_dictionary(entries: pd.DataFrame, path: str | Path) -> Path:
    """Write a dictionary in the form that this same module reads back.

    It serves the return trip: decisions taken case by case can come out as a
    dictionary, be corrected in a spreadsheet and come back in.
    """
    target = Path(path)
    if target.suffix.lower() != ".csv":
        target = target.with_suffix(".csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = entries if entries is not None else empty_dictionary()
    for name in DICTIONARY_COLUMNS:
        if name not in frame.columns:
            frame = frame.assign(**{name: ""})
    frame.loc[:, list(DICTIONARY_COLUMNS)].to_csv(
        target, index=False, encoding="utf-8-sig")
    return target


# ──────────────────────────────────────────── applying the corrections ──
def _value_map(entries: pd.DataFrame, column: str) -> dict[str, str]:
    if entries is None or entries.empty or column not in entries.columns:
        return {}
    keys = entries[FORM_COLUMN].map(match_key)
    values = _text_series(entries[column])
    return {key: value for key, value in zip(keys, values) if key and value}


def apply_form_dictionary(
    tokens: pd.DataFrame,
    entries: pd.DataFrame,
) -> pd.DataFrame:
    """Assign to every occurrence of a form the lemma and the tag of the dictionary.

    The starting corpus is not touched: what comes back is a copy. The empty cells of
    the dictionary delete nothing, the forms that the corpus does not have do nothing,
    and the two flags ``lemma_corrected`` and ``postag_corrected`` stay true where
    something has changed, because it is from those that the rest of the program knows
    what to look at.
    """
    corrected = tokens.copy()
    if entries is None or entries.empty or "form" not in corrected.columns:
        return corrected

    keys = keys_of(corrected["form"])
    for column, flag in ((LEMMA_COLUMN, "lemma_corrected"),
                         (POSTAG_COLUMN, "postag_corrected")):
        mapping = _value_map(entries, column)
        if not mapping or column not in corrected.columns:
            continue
        replacement = keys.map(mapping)
        mask = replacement.notna()
        if not mask.any():
            continue
        if flag not in corrected.columns:
            corrected[flag] = False
        corrected.loc[mask, column] = replacement[mask]
        corrected.loc[mask, flag] = True
    return corrected


def dictionary_coverage(
    tokens: pd.DataFrame,
    entries: pd.DataFrame,
) -> DictionaryCoverage:
    """How many entries actually touch this corpus, and how many words would change.

    This is the answer to the question “and the rows that match nothing?”, given before
    pressing the button and not after.
    """
    if entries is None or entries.empty:
        return DictionaryCoverage()
    total = int(len(entries))
    if tokens is None or tokens.empty or "form" not in tokens.columns:
        return DictionaryCoverage(entries=total, unmatched_entries=total)

    token_keys = keys_of(tokens["form"])
    present = set(token_keys)
    keys = entries[FORM_COLUMN].map(match_key)
    matched = keys.isin(present)

    lemma_map = _value_map(entries, LEMMA_COLUMN)
    postag_map = _value_map(entries, POSTAG_COLUMN)

    def _changed(column: str, mapping: dict[str, str]) -> int:
        if not mapping or column not in tokens.columns:
            return 0
        replacement = token_keys.map(mapping)
        hit = replacement.notna()
        if not hit.any():
            return 0
        current = _text_series(tokens.loc[hit, column])
        return int((current != replacement[hit].astype(str)).sum())

    touched = token_keys.isin(set(lemma_map) | set(postag_map))
    return DictionaryCoverage(
        entries=total,
        matched_entries=int(matched.sum()),
        unmatched_entries=int((~matched).sum()),
        tokens_matched=int(touched.sum()),
        tokens_lemma_changed=_changed(LEMMA_COLUMN, lemma_map),
        tokens_postag_changed=_changed(POSTAG_COLUMN, postag_map),
    )
