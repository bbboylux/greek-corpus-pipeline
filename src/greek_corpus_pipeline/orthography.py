"""Text-level diagnostics: Unicode, diacritics, script mixing, encoding residue.

These are the cheapest checks in the whole program and among the most
productive, because they catch damage that happened *before* anyone looked at
the linguistics.  The literature documents the exact failure modes:

* an elision apostrophe silently converted into a smooth breathing, so that
  ``ἀλλ'`` becomes a lambda wearing a spirit (Kostkan et al. 2023: 129);
* roughly fifty thousand heterogeneous apostrophe characters that had to be
  unified to U+02BC before the AGDT/Gorman/Pedalion aggregate could be used
  (Celano 2025: 50);
* Latin homoglyphs inside Greek words — the article's own inventory records
  ``κακῶv`` with a Latin *v* for a nu;
* mixed NFC/NFD normalisation, which is invisible on screen but splits one
  string into two as far as every ``groupby`` is concerned.

That last one is why this module runs *before* the variation n-gram engine:
two graphically identical tokens normalised differently never collapse into
the same nucleus, so the inconsistency they encode is silently invisible.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from . import issue_testi, resources
from .agdt_schema import elliptic_token_mask
from .fastmap import build_frame, map_unique, mask_unique
from .rule_catalog import default_auto_apply, rule_description, rule_name, rule_severity

# ---------------------------------------------------------------------------
# Character inventories
# ---------------------------------------------------------------------------

GREEK_RANGES = (
    (0x0370, 0x03FF),   # Greek and Coptic
    (0x1F00, 0x1FFF),   # Greek Extended
)

#: Every codepoint that has been used, somewhere, to mean "elision apostrophe".
APOSTROPHES = {
    "'": "APOSTROPHE (ASCII)",
    "’": "RIGHT SINGLE QUOTATION MARK",
    "ʼ": "MODIFIER LETTER APOSTROPHE",
    "᾽": "GREEK KORONIS",
    "᾿": "GREEK PSILI",
    "´": "ACUTE ACCENT",
    "ʹ": "MODIFIER LETTER PRIME",
    "′": "PRIME",
    "`": "GREEK VARIA",
}
#: The character Celano (2025: 50) normalises everything to.
CANONICAL_APOSTROPHE = "ʼ"

COMBINING_ACUTE = "́"
COMBINING_GRAVE = "̀"
COMBINING_CIRCUMFLEX = "͂"
COMBINING_SMOOTH = "̓"
COMBINING_ROUGH = "̔"
COMBINING_DIAERESIS = "̈"
COMBINING_IOTA = "ͅ"
COMBINING_MACRON = "̄"
COMBINING_BREVE = "̆"

ACCENTS = {COMBINING_ACUTE, COMBINING_GRAVE, COMBINING_CIRCUMFLEX}
BREATHINGS = {COMBINING_SMOOTH, COMBINING_ROUGH}
ALL_DIACRITICS = ACCENTS | BREATHINGS | {
    COMBINING_DIAERESIS, COMBINING_IOTA, COMBINING_MACRON, COMBINING_BREVE,
}

GREEK_VOWELS = set("αεηιουωΑΕΗΙΟΥΩ")
GREEK_RHO = {"ρ", "Ρ"}

#: Latin letters that are visually identical to a Greek letter.
LATIN_HOMOGLYPHS = {
    "A": "Α", "B": "Β", "E": "Ε", "H": "Η", "I": "Ι", "K": "Κ", "M": "Μ",
    "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ", "Y": "Υ", "Z": "Ζ",
    "a": "α", "e": "ε", "o": "ο", "p": "ρ", "v": "ν", "u": "υ", "i": "ι",
    "c": "ς", "y": "υ", "n": "η", "w": "ω",
}

#: Residual beta code markers: TLG-style transliteration that never made it
#: through the Unicode conversion.
BETA_CODE_RE = re.compile(r"[*()\\/|+=]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"[0-9]")
#: Invisible characters fall into two groups, and the group is decided by the Unicode
#: category, not by appearance.
#:
#: Format characters have category ``Cf``: they are not text, have no rendering and
#: separate nothing. Removing them does not change a letter of what is read, and removes
#: one cause of broken comparisons between graphically equal strings. The list is closed
#: and written here one by one: five code points, all verified ``Cf``. It is not extended
#: by analogy.
#:
#: Separators have category ``Zs`` or are line controls: a space, a tab, a line break.
#: Inside a token they may be the sign that tokenisation has joined two words, and
#: removing them would hide the problem instead of solving it. Those are flagged and
#: nothing more.
#:
#: U+00A0 NO-BREAK SPACE belongs to the second group. Its Unicode category is ``Zs``, the
#: same as U+0020: it is a space that does not break the line, not a format character.
#: Deleting it automatically while an ordinary space goes to manual review would be a
#: difference of treatment without a difference in the data.
FORMAT_CHARS: tuple[str, ...] = ("​", "‌", "‍", "⁠", "﻿")
FORMAT_CHARS_RE = re.compile("[" + "".join(FORMAT_CHARS) + "]")
SEPARATOR_CHARS: tuple[str, ...] = ("\t", "\r", "\n", " ", " ")
WHITESPACE_INSIDE_RE = re.compile("[" + "".join(SEPARATOR_CHARS) + "]")
# Format characters and separators are two different things — a space inside a token
# says that tokenisation has joined two words, a format character does not — and
# therefore have two expressions and two checks.
PLACEHOLDER_RE = re.compile(r"^\[(?:[0-9]|1[0-9]|20)\]$")

#: Enclitics: a host word legitimately carries a second accent before one.
#:
#: Attic first, then the Ionic and epic forms — the Gorman corpus contains
#: Herodotus, and σφι, μευ, κω and their kin are enclitic exactly as σφισι, μου
#: and που are.  The list is written with the accents and breathings the words
#: are printed with, and reduced to comparison keys below.
ENCLITICS = resources.entries("enclitiche")

FINDINGS_COLUMNS = [
    "rule_id", "anomaly_name", "anomaly_description",
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "form", "lemma", "postag", "relation",
    "issue", "issue_key", "issue_params",
    "suggested_form", "suggested_lemma", "auto_correctable", "severity",
]

_BASE_COLS = [
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "form", "lemma", "postag", "relation",
]


def empty_findings() -> pd.DataFrame:
    return pd.DataFrame(columns=FINDINGS_COLUMNS)


def _make(
    subset: pd.DataFrame,
    rule_id: str,
    issue_params: "object | pd.Series" = None,
    *,
    issue_key: "str | pd.Series | None" = None,
    suggested_form: object = pd.NA,
    suggested_lemma: object = pd.NA,
    severity: str = "errore",
    auto_correctable: bool = False,
) -> pd.DataFrame:
    if subset is None or subset.empty:
        return empty_findings()
    columns = {
        "rule_id": rule_id,
        "anomaly_name": rule_name(rule_id),
        "anomaly_description": rule_description(rule_id),
    }
    for column in _BASE_COLS:
        columns[column] = subset[column] if column in subset.columns else pd.NA
    columns["issue_key"] = rule_id if issue_key is None else issue_key
    columns["issue_params"] = "" if issue_params is None else issue_params
    columns["suggested_form"] = suggested_form
    columns["suggested_lemma"] = suggested_lemma
    columns["auto_correctable"] = bool(auto_correctable) and default_auto_apply(rule_id)
    # Severity comes from the class of the check. The parameter is kept so that existing
    # calls do not break, but it has no effect: a column that contradicts the class of
    # its own rule is exactly the defect to avoid.
    columns["severity"] = rule_severity(rule_id)
    frame = build_frame(columns, len(subset))
    frame["issue"] = issue_testi.rendi_serie(frame, "it")
    return frame[FINDINGS_COLUMNS]


def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
    live = [part for part in parts if part is not None and not part.empty]
    return pd.concat(live, ignore_index=True) if live else empty_findings()


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def is_greek_char(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in GREEK_RANGES)


#: The same removals as ``ALL_DIACRITICS``, in the form ``str.translate`` wants.
_DIACRITIC_DELETIONS = {ord(mark): None for mark in ALL_DIACRITICS}

#: ``LATIN_HOMOGLYPHS`` in the form ``str.translate`` wants.
_HOMOGLYPH_TABLE = {ord(latin): greek for latin, greek in LATIN_HOMOGLYPHS.items()}


def strip_diacritics(text: object) -> str:
    """Lowercase, decompose, drop every combining mark, recompose.

    Used as the key for orthographic variation nuclei: two spellings of the
    same word collapse onto one key, and the *set* of spellings becomes the
    label whose variation we look for.

    The filtering is a ``str.translate``, not a comprehension: this runs on
    every distinct form and every distinct lemma of the corpus and, through the
    search tab, on every keystroke, and building a Python list of characters to
    join back together cost twice what the C-level deletion does.
    """
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return unicodedata.normalize("NFC", decomposed.translate(_DIACRITIC_DELETIONS))


#: The comparison key of an enclitic: lower-case, no diacritics.
#:
#: The token that follows is compared after ``strip_diacritics``, so the set of
#: enclitics must be reduced in the same way before the membership test:
#: ``ENCLITICS`` is written with breathings, and ``εστι`` would otherwise be
#: compared against ``ἐστι`` and never match.  Every enclitic carrying a
#: breathing would escape the test, and the most frequent of all is ἐστί(ν):
#: ἄξιός ἐστι, δίκαιόν ἐστι, οὗτός ἐστι.
_ENCLITIC_KEYS = frozenset(strip_diacritics(word) for word in ENCLITICS)

#: Elided enclitics — μ᾽ for με, γ᾽ for γε, ποτ᾽ for ποτε — accented their host
#: before they lost their vowel, and the corpora write them with an apostrophe.
_ELIDED_ENCLITIC_KEYS = frozenset(
    key[:-1] for key in _ENCLITIC_KEYS if len(key) > 1 and key[-1] in "εα")

#: Enclitics written as part of the host word: Ἐλευσῖνάδε, οἷόνπερ, ὥστε.  The
#: second accent is the enclitic's own and the word is spelled correctly.
_ENCLITIC_SUFFIXES = ("δε", "περ", "γε", "τε", "ποτε", "που", "πω", "θι")

_APOSTROPHE_CHARS = "".join(APOSTROPHES)


def followed_by_enclitic(value: object) -> bool:
    """Is this token an enclitic, in any of the shapes the corpora write it in?"""
    if not isinstance(value, str) or not value:
        return False
    key = strip_diacritics(value)
    bare = key.rstrip(_APOSTROPHE_CHARS)
    if bare in _ENCLITIC_KEYS:
        return True
    return bare != key and bare in _ELIDED_ENCLITIC_KEYS


def carries_enclitic_suffix(value: object) -> bool:
    """Does the word end in an enclitic written as part of it?"""
    if not isinstance(value, str) or not value:
        return False
    bare = strip_diacritics(value).rstrip(_APOSTROPHE_CHARS)
    return any(bare.endswith(suffix) and len(bare) > len(suffix) + 2
               for suffix in _ENCLITIC_SUFFIXES)


def normalize_apostrophes(text: object) -> str:
    if not isinstance(text, str):
        return ""
    result = text
    for variant in APOSTROPHES:
        if variant != CANONICAL_APOSTROPHE:
            result = result.replace(variant, CANONICAL_APOSTROPHE)
    return result


def count_accents(text: str) -> int:
    # Three C-level counts beat one Python loop over the characters.
    decomposed = unicodedata.normalize("NFD", text)
    return sum(decomposed.count(accent) for accent in ACCENTS)


def fix_homoglyphs(text: str) -> str:
    """Replace Latin letters by their Greek look-alikes."""
    return text.translate(_HOMOGLYPH_TABLE)


def script_profile(text: object) -> set[str]:
    """Which alphabets a string draws on: {'GREEK'}, {'GREEK','LATIN'}, …

    Decided by codepoint block, not by Unicode character name.  The name-based
    version looks tempting and is wrong: U+02BC MODIFIER LETTER APOSTROPHE —
    the canonical elision apostrophe of the AGDT corpora — reports ``isalpha()``
    as True and a name beginning with "MODIFIER", so every elided word in the
    corpus would be reported as mixed-script. Twenty thousand false positives
    from one wrong predicate.
    """
    if not isinstance(text, str):
        return set()
    scripts: set[str] = set()
    # The two Greek blocks are spelled out rather than looped over: the
    # ``any(...)`` generator was built once per character, 2.5 million times on
    # this corpus, for a test that is two integer comparisons.
    for char in text:
        code = ord(char)
        if (0x0370 <= code <= 0x03FF) or (0x1F00 <= code <= 0x1FFF):
            scripts.add("GREEK")
        elif ("a" <= char <= "z") or ("A" <= char <= "Z"):
            scripts.add("LATIN")
        elif 0x0400 <= code <= 0x04FF:
            scripts.add("CYRILLIC")
    return scripts


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

#: Above this share of the records, a non-composed encoding is the corpus's
#: own and is reported once rather than token by token.
WHOLE_CORPUS_ENCODING = 0.50


def check_normalization(tokens: pd.DataFrame) -> pd.DataFrame:
    """Fields that are not in NFC — the silent killer of every groupby.

    One finding per *token*, not per field.  The form and the lemma of a token
    are usually damaged together — the lemma is copied from the form — and two
    rules reporting the same accident on the same token would count it twice.
    The row names the fields it concerns and carries a correction for each of
    them, so nothing is lost by merging.
    """
    columns = [column for column in ("form", "lemma") if column in tokens.columns]
    repairs: dict[str, pd.Series] = {}
    for column in columns:
        values = tokens[column]
        is_text = mask_unique(values, lambda value: isinstance(value, str) and bool(value))
        if not is_text.any():
            continue
        subset_values = values[is_text]
        normalized = map_unique(subset_values, lambda value: unicodedata.normalize("NFC", value))
        differs = normalized != subset_values
        if differs.any():
            repairs[column] = normalized[differs]

    if not repairs:
        return empty_findings()

    affected = repairs.get("form", pd.Series(dtype=object)).index
    for column in repairs:
        affected = affected.union(repairs[column].index)

    # When most of the corpus is decomposed, this is not an accident that
    # happened to some tokens: it is how the resource is distributed, and one
    # finding per token says the same thing a quarter of a million times.
    #
    # GLAUx is published in NFD: of the 300,292 records of the automatic sample,
    # 252,418 have a form or a lemma that is not in NFC. One finding per record
    # would be true every time and informative none: a reader scrolling that
    # list learns the encoding on the first line and cannot reach anything
    # else. Pedalion is the opposite case and the reason the per-token report is
    # kept — 4,007 active records out of 274,609, a real inconsistency inside a
    # corpus that is otherwise composed.
    #
    # So the two are separated by what they are. Above half the corpus the
    # finding is made once, on the first record, and it counts the rest.
    share = len(affected) / max(len(tokens), 1)
    if share >= WHOLE_CORPUS_ENCODING:
        rows = tokens.loc[affected[:1]]
        return _make(rows, "corpus-not-nfc",
                     issue_testi.parametri(decomposti=len(affected),
                                           totale=len(tokens)),
                     auto_correctable=False)

    rows = tokens.loc[affected]

    # Which fields are decomposed: two codes, not two Italian words.
    campi = pd.Series([() for _ in affected], index=affected, dtype="object")
    for column, values in repairs.items():
        touched = pd.Series(False, index=affected)
        touched.loc[values.index] = True
        campi = campi.mask(touched, campi.map(lambda voci: voci + (column,)))

    def _suggestion(column: str) -> object:
        if column not in repairs:
            return pd.NA
        return repairs[column].reindex(affected)

    return _make(rows, "unicode-not-nfc",
                 issue_testi.parametri(campi=campi),
                 suggested_form=_suggestion("form"),
                 suggested_lemma=_suggestion("lemma"),
                 auto_correctable=True)


def check_apostrophes(tokens: pd.DataFrame) -> pd.DataFrame:
    """Files that mix several apostrophe codepoints."""
    if "form" not in tokens.columns:
        return empty_findings()
    forms = tokens["form"].astype("string").fillna("")
    used = map_unique(forms, lambda value: frozenset(char for char in value if char in APOSTROPHES))
    has_any = used.map(bool)
    if not has_any.any():
        return empty_findings()

    per_file: dict[object, set[str]] = {}
    for source_file, variants in zip(tokens.loc[has_any, "source_file"], used[has_any]):
        per_file.setdefault(source_file, set()).update(variants)
    mixed_files = {name for name, variants in per_file.items() if len(variants) > 1}
    if not mixed_files:
        return empty_findings()

    # Only the tokens that would actually change.  A file that mixes three
    # apostrophe characters also contains tokens already written with the
    # canonical one, and reporting those offered them their own spelling as a
    # correction: 322 identical "corrections" in Gorman and 191 in Pedalion,
    # which on application become that many entries in the log saying nothing
    # happened.  The file is still described in the message; the report lands
    # on the tokens that carry one of the other encodings.
    mask = (has_any & tokens["source_file"].isin(mixed_files)
            & mask_unique(tokens["form"],
                          lambda value: normalize_apostrophes(value) != value))
    if not mask.any():
        return empty_findings()
    subset = tokens[mask]
    # The code points, not the names: the name of the character is written by whoever
    # displays it.
    punti = used[mask].map(
        lambda variants: tuple(sorted(f"U+{ord(char):04X}" for char in variants)))
    suggested = map_unique(subset["form"], normalize_apostrophes)
    return _make(subset, "apostrophe-mixed",
                 issue_testi.parametri(codepoints=punti),
                 suggested_form=suggested, auto_correctable=True, severity="sospetto")


def check_mixed_script(tokens: pd.DataFrame) -> pd.DataFrame:
    """Latin (or Cyrillic) letters hiding inside a Greek word."""
    if "form" not in tokens.columns:
        return empty_findings()
    forms = tokens["form"]
    # One pass per distinct form: the predicate composes both steps, so the
    # intermediate set never has to be hashed or stored per token.  It also
    # profiles the string once instead of twice, instead of scanning all 69,461
    # distinct forms character by character a second time.
    def _is_mixed(value: object) -> bool:
        scripts = script_profile(value)
        return "GREEK" in scripts and len(scripts) > 1

    mixed = map_unique(forms, _is_mixed)
    mixed = mixed.fillna(False).astype(bool)
    if not mixed.any():
        return empty_findings()
    subset = tokens[mixed]
    intruders = map_unique(subset["form"],
        lambda value: "".join(sorted({
            char for char in value
            if (("a" <= char <= "z") or ("A" <= char <= "Z"))})))
    suggested = map_unique(subset["form"], fix_homoglyphs)

    # A Latin letter with no Greek look-alike — the ``G`` that stands for a
    # lacuna in the papyri of Pedalion — comes back from ``fix_homoglyphs``
    # unchanged, and the rule then offered the word it was already looking at
    # as its own correction: eleven of the twelve findings were an identity.
    # A proposal that changes nothing is not a proposal, so those rows keep the
    # report and lose both the suggestion and the auto-correctable flag.
    repairable = np.asarray(suggested != subset["form"], dtype=bool)
    parts: list[pd.DataFrame] = []
    if repairable.any():
        parts.append(_make(subset[repairable], "mixed-script",
                           issue_testi.parametri(intrusi=intruders[repairable]),
                           suggested_form=suggested[repairable], auto_correctable=True))
    if (~repairable).any():
        parts.append(_make(subset[~repairable], "mixed-script-unrepairable",
                           issue_testi.parametri(intrusi=intruders[~repairable])))
    return _concat(parts)


def check_beta_code_residue(tokens: pd.DataFrame) -> pd.DataFrame:
    """Leftover TLG beta-code markers in form or lemma."""
    parts: list[pd.DataFrame] = []
    for column, rule_id in (("form", "beta-code-form"), ("lemma", "beta-code-lemma")):
        if column not in tokens.columns:
            continue
        values = tokens[column].astype("string").fillna("")
        # Two things are deliberately not beta code, and both occur in the
        # thousands:
        #   · placeholders like [0], a documented annotation device;
        #   · a token consisting *only* of brackets or slashes, which is an
        #     editorial sign the corpus tokenised — a lone "(" is a parenthesis,
        #     not a failed transliteration.
        # Residue means a beta-code marker *mixed with letters*.
        is_placeholder = values.str.match(PLACEHOLDER_RE).fillna(False)
        only_marks = values.str.fullmatch(r"[*()\\/|+=\[\]<>{}·.,;:'’\-—…]+").fillna(False)
        has_letters = values.str.contains(r"[A-Za-zΑ-ωἀ-ῼ]", regex=True).fillna(False)
        suspicious = (values.str.contains(BETA_CODE_RE, regex=True).fillna(False)
                      & has_letters & ~is_placeholder & ~only_marks)
        if suspicious.any():
            parts.append(_make(tokens[suspicious], rule_id))
    return _concat(parts)


def _spirito_finale_autonomo(value: object) -> bool:
    """The smooth breathing attached at the end of a word, in place of the apostrophe.

    This is the case of δ̓ for δʼ: the elision apostrophe has been written with the
    character of the smooth breathing, U+0313. Three conditions, and all three are
    needed.

    The sign must be the **smooth** breathing: the rough one has never been an
    apostrophe, and replacing it would decide a question of reading.

    It must be the **last** character of the decomposed form, and the character that
    precedes it must be neither a vowel nor a rho. In Ἵππων the breathing is where it
    should be, over the initial vowel, and the form does not end with it: it is not
    touched.

    And underneath there must be a **word**. A record whose form is the sign alone, like
    the thirty-one editorial signs of Pedalion, is not a word with the wrong apostrophe:
    it is a non-lexical record, and the rule of the same name deals with that.
    """
    if not isinstance(value, str) or not value:
        return False
    decomposed = unicodedata.normalize("NFD", value)
    if decomposed[-1] != COMBINING_SMOOTH:
        return False
    if all(unicodedata.combining(carattere) for carattere in decomposed):
        return False
    base = decomposed[-2] if len(decomposed) > 1 else ""
    # A Greek consonant, and not the rho: these are the two things that a breathing
    # cannot bear. On a vowel the sign does its job, and οὐ written in NFD ends
    # precisely with the breathing over the upsilon.
    return (is_greek_char(base) and base not in GREEK_VOWELS
            and base not in GREEK_RHO)


def check_breathings(tokens: pd.DataFrame) -> pd.DataFrame:
    """The elision apostrophe written with the character of the breathing."""
    if "form" not in tokens.columns:
        return empty_findings()

    mask = mask_unique(tokens["form"], _spirito_finale_autonomo)
    if not mask.any():
        return empty_findings()

    # Flagging and proposing are two different things. That a smooth breathing at
    # the end of a consonant is not a diacritic is shown by the position; that it is
    # an elision apostrophe, and not another fault, is shown by the word. The
    # automatic replacement therefore applies only to the signature checked by
    # hand: the form δ̓ with the lemma δέ, nineteen times in Gorman. Every other
    # form is flagged and read by whoever corrects.
    lemma = (tokens["lemma"] if "lemma" in tokens.columns
             else pd.Series("", index=tokens.index))
    firma = mask & (
        tokens["form"].map(lambda f: isinstance(f, str)
                           and unicodedata.normalize("NFD", f) == "δ" + COMBINING_SMOOTH)
        & lemma.map(lambda l: isinstance(l, str)
                    and unicodedata.normalize("NFC", l) == "δέ"))
    proposta = pd.Series(pd.NA, index=tokens.index, dtype="object")
    proposta[firma] = "δ" + CANONICAL_APOSTROPHE
    # Two diagnoses, two keys: the signature checked by hand and everything else.
    chiave = pd.Series("breathing-impossible", index=tokens.index, dtype="string")
    chiave[firma] = "breathing-impossible.delta-elisa"
    return _make(tokens[mask], "breathing-impossible", issue_key=chiave[mask],
                 suggested_form=proposta[mask], auto_correctable=True)


def _solo_spirito(value: object) -> bool:
    """The form is a breathing sign and nothing else."""
    return isinstance(value, str) and value.strip() in (COMBINING_SMOOTH, COMBINING_ROUGH)


def check_isolated_breathing(tokens: pd.DataFrame) -> pd.DataFrame:
    """The form consists of a breathing only.

    In Pedalion there are thirty-one records, with tag “u--------” and relation AuxG.
    Twenty-nine are a parenthesis left encoded as a breathing, and the resource itself
    shows it: it already contains 73 records with form “(” and lemma “U+0314”, and 73
    with form “)” and lemma “U+0313”, without a single case of the opposite
    correspondence. Where the conversion was done, the lemma kept the starting sign;
    here the conversion was not done and the sign remained in the form too.

    The other two are not parentheses: they are the fragment of a word split into two
    records, and are recognised because the token that follows begins with the
    apostrophe, that is, it has lost its own initial letter. They stay flagged and must
    be reconstructed by hand together with the following token.

    The check proposes nothing by itself: the proposals come from the table of verified
    repairs, occurrence by occurrence.
    """
    if "form" not in tokens.columns:
        return empty_findings()
    mask = mask_unique(tokens["form"], _solo_spirito)
    if not mask.any():
        return empty_findings()
    return _make(tokens[mask], "isolated-breathing")


def check_accents(tokens: pd.DataFrame) -> pd.DataFrame:
    """Two accents on one word outside an enclitic context, and final sigma misuse."""
    parts: list[pd.DataFrame] = []
    if "form" not in tokens.columns:
        return empty_findings()

    forms = tokens["form"]
    two_accents = mask_unique(
        forms, lambda value: isinstance(value, str) and count_accents(value) > 1)

    # Everything below is asked of the words that carry two accents and of no
    # others — 2,832 of the 625,176 Gorman tokens — so the questions are asked
    # on a slice instead of on the column.
    candidates = np.flatnonzero(two_accents.to_numpy())
    if candidates.size:
        keep = np.ones(candidates.size, dtype=bool)

        # A host word takes a second accent when followed by an enclitic, so
        # look at the next token — but only when there is one and it belongs to
        # the same sentence.
        following = candidates + 1
        inside_corpus = following < len(tokens)
        neighbour = np.where(inside_corpus, following, candidates)
        # ``column.iloc[rows]`` and not ``column.to_numpy()[rows]``: an
        # Arrow-backed string column materialises 625,176 Python objects on the
        # way out, and this needs 2,832 of them.
        same_sentence = inside_corpus.copy()
        for column in ("sentence_index", "source_file", "document_id"):
            if column in tokens.columns:
                values = tokens[column]
                same_sentence &= (values.iloc[neighbour].to_numpy()
                                  == values.iloc[candidates].to_numpy())

        next_words = forms.iloc[neighbour].reset_index(drop=True)
        enclitic = np.array(mask_unique(next_words, followed_by_enclitic), dtype=bool)
        if "lemma" in tokens.columns:
            next_lemmas = tokens["lemma"].iloc[neighbour].reset_index(drop=True)
            enclitic |= np.asarray(
                mask_unique(next_lemmas, followed_by_enclitic), dtype=bool)
        keep &= ~(enclitic & same_sentence)

        # The word may carry the enclitic inside itself (Ἐλευσῖνάδε, οἷόνπερ),
        # and an elided-word placeholder carries the accent of the place it was
        # copied from rather than of the place it is parked in: εἶναί φημι is
        # annotated once in the text and once more after the full stop, where
        # no enclitic follows it.
        own_words = forms.iloc[candidates].reset_index(drop=True)
        keep &= ~np.asarray(mask_unique(own_words, carries_enclitic_suffix), dtype=bool)
        keep &= ~elliptic_token_mask(tokens)[candidates]

        if keep.any():
            parts.append(_make(tokens.iloc[candidates[keep]], "double-accent",
                               severity="sospetto"))

    # ``ς`` inside a word is a real slip — προςαγαγών for προσαγαγών — but two
    # of the four occurrences in these corpora were not words at all: ςΖ in
    # Heron is the label of a geometric point (ς is the numeral stigma) and
    # GGαGρωςGG in the papyri has the sigma at the end, followed by the ``G``
    # that marks a lacuna.  A token that mixes in non-Greek letters, and a
    # one- or two-letter sigla, are excluded for that reason.
    def _sigma_problem(value: object) -> bool:
        if not isinstance(value, str) or len(value) < 2:
            return False
        core = value.rstrip(_APOSTROPHE_CHARS + ".,;·:")
        if len(core) <= 2:
            return False
        if any(char.isalpha() and not is_greek_char(char) for char in core):
            return False
        return "ς" in core[:-1]

    def _sigma_corretto(value: object) -> str:
        """The final sigma that stands in the middle becomes the ordinary sigma."""
        if not isinstance(value, str) or len(value) < 2:
            return value if isinstance(value, str) else ""
        coda = len(value) - len(value.rstrip(_APOSTROPHE_CHARS + ".,;·:"))
        nucleo = value[:len(value) - coda] if coda else value
        return nucleo[:-1].replace("ς", "σ") + nucleo[-1:] + (value[-coda:] if coda else "")

    sigma = mask_unique(forms, _sigma_problem)
    if sigma.any():
        proposta = map_unique(tokens["form"][sigma], _sigma_corretto)
        parts.append(_make(
            tokens[sigma], "final-sigma-inside",
            suggested_form=proposta, auto_correctable=True))

    return _concat(parts)


def check_invisible_characters(tokens: pd.DataFrame) -> pd.DataFrame:
    """Format characters and separators inside a token, kept separate.

    The criterion is the Unicode category. ``Cf`` on one side — invisible, with no
    orthographic function, removable; ``Zs`` and the line controls on the other —
    separators, which inside a token may be the sign of two words joined and must be
    looked at by hand.
    """
    # The two branches are two different checks, because a check cannot have two
    # treatments: the treatment is an axis of the taxonomy and ends up in the counts.
    # “Automatic correction” holds for the format characters and not for real spaces,
    # which the program flags and nothing more. There are now two distinct checks per
    # field.
    parts: list[pd.DataFrame] = []
    for column, rule_id, rule_id_spazi in (
            ("form", "invisible-char-form", "whitespace-in-form"),
            ("lemma", "invisible-char-lemma", "whitespace-in-lemma")):
        if column not in tokens.columns:
            continue
        values = tokens[column].astype("string").fillna("")
        spazi = values.str.contains(WHITESPACE_INSIDE_RE, regex=True).fillna(False)
        formato = (values.str.contains(FORMAT_CHARS_RE, regex=True).fillna(False)
                   & ~spazi)
        if formato.any():
            cleaned = tokens.loc[formato, column].map(
                lambda value: FORMAT_CHARS_RE.sub("", value)
                if isinstance(value, str) else value)
            parts.append(_make(
                tokens[formato], rule_id,
                suggested_form=cleaned if column == "form" else pd.NA,
                suggested_lemma=cleaned if column == "lemma" else pd.NA,
                auto_correctable=True))
        if spazi.any():
            parts.append(_make(tokens[spazi], rule_id_spazi,
                               severity="sospetto"))
    return _concat(parts)


#: A relation field that is really a working note: a run of two or more marker
#: characters used as a flag, or a phrase in a modern language.  ``%`` sits next
#: to ``!`` and ``?`` because Pedalion flags two tokens with ``%%%SBJ``, which
#: is the same gesture with a different key; a narrower pattern would miss them and
#: they would end up filed as unknown labels, which is not what they are.
ANNOTATOR_NOTE_RE = r"[!?%]{2,}|[a-z]{4,}\s"


def relation_is_annotator_note(relations: pd.Series) -> pd.Series:
    """Which relation values are working notes rather than labels.

    Lives here, next to the rule that owns the phenomenon, and is imported by
    ``syntax.py``: the same forty-three Pedalion tokens were being reported both
    as an annotator's note and as an unknown relation, and one predicate in one
    place is the only way to keep the two answers from drifting apart.
    """
    values = pd.Series(relations).astype("string").fillna("")
    return values.str.contains(ANNOTATOR_NOTE_RE, regex=True).fillna(False)


def check_annotator_notes(tokens: pd.DataFrame) -> pd.DataFrame:
    """Working notes the annotators left in the relation field.

    Pedalion ships tokens whose relation reads ``!!!!!!ATR`` — six exclamation
    marks as a reminder to re-check — and, in one file of Lucian, Dutch revision
    notes such as ``!!!congruentiefout geslacht?!!!OBJ``.  Nobody's fault; but
    exactly the residue a diagnosis must catch before it reaches a training set.
    """
    if "relation" not in tokens.columns:
        return empty_findings()
    relations = tokens["relation"].astype("string").fillna("")
    mask = relation_is_annotator_note(relations)
    if not mask.any():
        return empty_findings()
    # The note is the relation itself, cut: the cutting is done by whoever displays it.
    return _make(tokens[mask], "annotator-note-in-relation")


def similar_forms(
    tokens: pd.DataFrame,
    *,
    max_rare: int = 2,
    min_frequent: int = 25,
) -> pd.DataFrame:
    """Graphically similar forms: a rare one a character away from a frequent one.

    **An exploratory tool, not a diagnostic check.** It produces no findings, does
    not enter the totals, does not appear in the percentages by class or in the
    rates per ten thousand records.

    The reason lies in the measurement, not in the idea. The idea — the *scribal
    distance* of Cowen-Breen et al. (2023: 172–174) — is good: a form attested once
    or twice that differs by one character from one attested dozens of times is
    either a true rarity or a typo. But the lexical version, without the confidence
    model that that work uses, does not have enough information to tell them
    apart. Among the twenty pairs with the most frequent neighbour in the three main
    corpora there is not one that is a typo: τοῖος and τοῖς, αὐλῷ and αὐτῷ, πηρός
    and πρός, καθά and κατά, ὅθι and ὅτι are all correct Greek words, and the
    neighbour is more frequent because it is an article or a preposition, not
    because it is the right reading. Requiring compatibility of part of speech as
    well halves the pairs but does not remove these.

    It remains available to whoever wants to look, because looking costs nothing
    and the list is well ordered. And the warning of the tradition remains:
    corrupt readings tend to *banalise* the text, so the frequent neighbour is not
    automatically the right reading.
    """
    vuoto = pd.DataFrame(columns=["forma", "occorrenze", "vicina",
                                  "occorrenze_vicina", "documento"])
    if "form" not in tokens.columns or tokens.empty:
        return vuoto

    counts = tokens["form"].value_counts()
    rare = counts[counts <= max_rare]
    frequent = counts[counts >= min_frequent]
    if rare.empty or frequent.empty:
        return vuoto

    # Bucket by skeleton (unaccented, sorted length) so we only compare
    # plausible neighbours instead of the full N×M cartesian product.
    buckets: dict[tuple[int, str], list[str]] = {}
    for form in frequent.index:
        if not isinstance(form, str):
            continue
        skeleton = strip_diacritics(form)
        for length in (len(form) - 1, len(form), len(form) + 1):
            buckets.setdefault((length, skeleton[:1]), []).append(form)

    # Even inside a bucket a plain scan is quadratic in practice: 50,307 rare forms
    # against a mean of 41 bucket-mates is 2,054,100 character-by-character
    # comparisons, which would be the largest single cost of the whole module.
    #
    # A second index cuts the comparisons without touching the candidate set.
    # Two strings within one edit always share a member of their *deletion
    # neighbourhood* — the string itself plus every copy with one character
    # removed — so only bucket-mates that share one need to be looked at at all.
    # The neighbourhood test admits a few extra pairs (a transposition shares a
    # neighbour without being one edit away), so ``_within_one`` still decides,
    # and the survivors are visited in the original bucket order: same
    # candidates, same verdicts, same tie-break, a twentieth of the work.
    def _deletions(word: str) -> set[str]:
        return {word}.union(word[:index] + word[index + 1:] for index in range(len(word)))

    neighbourhoods: dict[tuple[int, str], dict[str, list[int]]] = {}
    for key, members in buckets.items():
        index: dict[str, list[int]] = {}
        for position, form in enumerate(members):
            for variant in _deletions(form):
                index.setdefault(variant, []).append(position)
        neighbourhoods[key] = index

    def _within_one(a: str, b: str) -> bool:
        if abs(len(a) - len(b)) > 1:
            return False
        if len(a) == len(b):
            diffs = sum(1 for x, y in zip(a, b) if x != y)
            return diffs == 1
        shorter, longer = (a, b) if len(a) < len(b) else (b, a)
        i = j = 0
        skipped = False
        while i < len(shorter) and j < len(longer):
            if shorter[i] != longer[j]:
                if skipped:
                    return False
                skipped = True
                j += 1
                continue
            i += 1
            j += 1
        return True

    suggestions: dict[str, str] = {}
    for form in rare.index:
        if not isinstance(form, str) or len(form) < 4:
            continue
        skeleton = strip_diacritics(form)
        key = (len(form), skeleton[:1])
        candidates = buckets.get(key, ())
        if not candidates:
            continue
        index = neighbourhoods[key]
        reachable: set[int] = set()
        for variant in _deletions(form):
            hits = index.get(variant)
            if hits:
                reachable.update(hits)
        best, best_count = None, 0
        for position in sorted(reachable):
            candidate = candidates[position]
            if candidate == form:
                continue
            if _within_one(form, candidate) and int(frequent[candidate]) > best_count:
                best, best_count = candidate, int(frequent[candidate])
        if best is not None:
            suggestions[form] = best

    if not suggestions:
        return empty_findings()

    # Two filters, and both remove pairs that are not pairs at all.
    #
    # ·  The corpus assigns both spellings to the same lemma.  Then they are
    #    two forms of one word — ἡσυχία and ἡσυχίαν, βουλόμεναι and βουλόμενοι,
    #    ὥρης beside ὥρας in Ionic — and the rare one is rare because that case
    #    is rare, not because anybody mistyped it.  68% of the Gorman pairs and
    #    65% of the Pedalion ones.
    # ·  The two spellings differ only in a diacritic.  That difference is
    #    almost always grammar: the accent an enclitic adds to its host
    #    (ἄνθρωπός τις), a crasis (κᾆτ᾽ for καὶ εἶτ᾽), a grave for an acute
    #    before punctuation.  A further 24% and 21%.
    #
    # What survives — 513 pairs in Gorman, 130 in Pedalion — is still mostly
    # two different real words one letter apart (πολιάς/πολλάς, τέκτων/τέκνων,
    # λαχόντα/λαβόντα), which is why the rule is declared exploratory in the
    # catalogue rather than counted among the diagnoses.
    lemma_of_form: dict[object, set] = {}
    if "lemma" in tokens.columns:
        # Only the forms that are actually part of a pair need their lemmas
        # looked up — a few thousand of the 69,461 — so the table is narrowed
        # before it is walked.
        wanted = set(suggestions) | set(suggestions.values())
        pairs = tokens.loc[tokens["form"].isin(wanted), ["form", "lemma"]].dropna()
        for form, lemma in zip(pairs["form"].to_numpy(), pairs["lemma"].to_numpy()):
            lemma_of_form.setdefault(form, set()).add(lemma)

    suggestions = {
        form: neighbour for form, neighbour in suggestions.items()
        if not (lemma_of_form.get(form, set()) & lemma_of_form.get(neighbour, set()))
        and strip_diacritics(form) != strip_diacritics(neighbour)
    }
    if not suggestions:
        return pd.DataFrame(columns=["forma", "occorrenze", "vicina",
                                     "occorrenze_vicina", "documento"])

    mask = tokens["form"].isin(suggestions)
    subset = tokens[mask]
    suggested = subset["form"].map(suggestions)
    # A table, not a table of findings: the columns say what is being looked at, and
    # none of them is a rule_id.
    return pd.DataFrame({
        "forma": subset["form"].to_numpy(),
        "occorrenze": subset["form"].map(counts).astype("Int64").to_numpy(),
        "vicina": suggested.to_numpy(),
        "occorrenze_vicina": suggested.map(counts).astype("Int64").to_numpy(),
        "documento": (subset["document_id"].astype("string").fillna("").to_numpy()
                      if "document_id" in subset.columns else ""),
    }).drop_duplicates(subset=["forma", "vicina"]).reset_index(drop=True)


def orthographic_variation(tokens: pd.DataFrame, min_occurrences: int = 2) -> pd.DataFrame:
    """Same word, same lemma, different accentuation across the corpus.

    A variation nucleus built on the *unaccented* form: when one skeleton maps
    to several spellings that share a lemma, at least one spelling is usually
    wrong. This is the orthographic transposition of Dickinson & Meurers
    (2003: 46) and it is the single most productive check for encoding damage.
    """
    if tokens.empty or "form" not in tokens.columns:
        return pd.DataFrame(columns=[
            "chiave", "lemma", "varianti", "n_varianti", "occorrenze", "dettaglio"])

    work = tokens[tokens["form"].notna()].copy()
    work["_key"] = map_unique(work["form"], strip_diacritics)
    work = work[work["_key"].str.len() >= 2]
    if work.empty:
        return pd.DataFrame(columns=[
            "chiave", "lemma", "varianti", "n_varianti", "occorrenze", "dettaglio"])

    if "lemma" in work.columns:
        work["_lemma"] = work["lemma"].astype("string").fillna("")
    else:
        work["_lemma"] = ""

    # Counting the spellings of each (skeleton, lemma) pair is one grouped
    # count, not one Python visit per pair: pandas materialises a Series — a
    # block slice, an index, a string array — for every group handed to a Python
    # loop, and only a small part of the pairs survives the filter. Grouping
    # once and visiting only the survivors is an order of magnitude faster,
    # which matters because the detection worker runs it on load.
    key_codes, key_values = pd.factorize(work["_key"], sort=False)
    lemma_codes, lemma_values = pd.factorize(work["_lemma"], sort=False)
    combined = key_codes.astype("int64") * len(lemma_values) + lemma_codes
    pair_codes, pair_values = pd.factorize(combined, sort=False)

    forms = work["form"].to_numpy()
    counts = (pd.DataFrame({"_pair": pair_codes, "_form": forms})
              .groupby(["_pair", "_form"], sort=False).size().reset_index(name="_n"))
    per_pair = counts.groupby("_pair", sort=False)
    variants = per_pair.size().sort_index().to_numpy()
    totals = per_pair["_n"].sum().sort_index().to_numpy()
    # Factorisation numbers the pairs in order of first appearance, so ascending
    # code order is the order the group loop visited them in.
    kept = np.flatnonzero((variants >= 2) & (totals >= min_occurrences))

    rows: list[dict[str, object]] = []
    if len(kept):
        live = counts[np.isin(counts["_pair"].to_numpy(), kept)]
        spelling_lists: dict[int, list[tuple[object, int]]] = {}
        for pair, form, count in zip(live["_pair"].to_numpy(),
                                     live["_form"].to_numpy(),
                                     live["_n"].to_numpy()):
            spelling_lists.setdefault(int(pair), []).append((form, int(count)))
        width = len(lemma_values)
        for pair in kept:
            spellings = spelling_lists[int(pair)]
            # groupby(sort=False) yielded the spellings in order of first
            # appearance, which is the order a Counter would hold them in, so a
            # stable sort by count reproduces ``most_common``.
            ranked = sorted(spellings, key=lambda item: item[1], reverse=True)
            origin = pair_values[pair]
            rows.append({
                "chiave": key_values[origin // width],
                "lemma": lemma_values[origin % width],
                "varianti": " | ".join(sorted(form for form, _ in spellings)),
                "n_varianti": len(spellings),
                "occorrenze": int(sum(count for _, count in spellings)),
                "dettaglio": " · ".join(f"{form} ({count})" for form, count in ranked),
            })
    if not rows:
        return pd.DataFrame(columns=[
            "chiave", "lemma", "varianti", "n_varianti", "occorrenze", "dettaglio"])
    return (pd.DataFrame(rows)
            .sort_values(["n_varianti", "occorrenze"], ascending=False)
            .reset_index(drop=True))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_orthography(tokens: pd.DataFrame) -> pd.DataFrame:
    """The checks on text and encoding, in a single table.

    It does not include “Rare form one character from a frequent one”: that is
    not a diagnostic check but :func:`similar_forms`, an exploratory tool that
    produces no findings and does not enter any total.
    """
    if tokens is None or tokens.empty:
        return empty_findings()
    return _concat([
        check_isolated_breathing(tokens),
        check_normalization(tokens),
        check_apostrophes(tokens),
        check_mixed_script(tokens),
        check_beta_code_residue(tokens),
        check_breathings(tokens),
        check_accents(tokens),
        check_invisible_characters(tokens),
        check_annotator_notes(tokens),
    ])


def encoding_report(tokens: pd.DataFrame) -> pd.DataFrame:
    """Per-file summary of encoding hygiene, for the overview tab."""
    if tokens is None or tokens.empty or "source_file" not in tokens.columns:
        return pd.DataFrame()

    # Five questions about the spelling of a word, asked once per distinct form
    # rather than once per token — the corpus has 69,461 of the former and
    # 625,176 of the latter, and one of the five already knew that.
    forms = tokens["form"].astype("string").fillna("")
    frame = pd.DataFrame({
        "source_file": tokens["source_file"],
        "token": 1,
        "non_nfc": map_unique(
            forms, lambda value: value != unicodedata.normalize("NFC", value)).astype(int),
        "apostrofi": map_unique(
            forms, lambda value: len({char for char in value if char in APOSTROPHES})).astype(int),
        "latino": map_unique(
            forms, lambda value: bool(LATIN_LETTER_RE.search(value))).astype(int),
        "cifre": map_unique(forms, lambda value: bool(DIGIT_RE.search(value))).astype(int),
        "senza_accento": map_unique(
            forms, lambda value: bool(value) and count_accents(value) == 0).astype(int),
    })
    summary = frame.groupby("source_file", sort=True).agg(
        token=("token", "sum"),
        token_non_NFC=("non_nfc", "sum"),
        token_con_latino=("latino", "sum"),
        token_con_cifre=("cifre", "sum"),
        token_senza_accento=("senza_accento", "sum"),
    ).reset_index()

    # How many *distinct* apostrophe characters a file uses, which is the number
    # that matters. Taking the maximum of a per-token count instead answers a
    # different question — "does any single token contain two apostrophes" —
    # and reports 1 for a file that mixes three encodings across its tokens.
    # Same trick, and then only the tokens that carry an apostrophe at all are
    # visited: the rest contributed an empty set to a dictionary update.
    used = map_unique(
        forms, lambda value: frozenset(char for char in value if char in APOSTROPHES))
    carries = used.astype(bool)
    variants: dict[object, set[str]] = {}
    for source_file, found in zip(tokens.loc[carries, "source_file"], used[carries]):
        variants.setdefault(source_file, set()).update(found)
    summary["varianti_apostrofo"] = summary["source_file"].map(
        lambda name: len(variants.get(name, ()))).astype(int)
    summary["% senza accento"] = (
        summary["token_senza_accento"] / summary["token"] * 100).round(1)
    return summary.sort_values("token", ascending=False).reset_index(drop=True)
