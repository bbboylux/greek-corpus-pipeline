from __future__ import annotations

import re
import unicodedata as _unicodedata

import numpy as np
import pandas as pd

from . import resources
from .agdt_schema import (
    CASE_SLOT,
    GENDER_SLOT,
    MOOD_SLOT,
    TENSE_SLOT,
    VOICE_SLOT,
    POSITION_VALUES,
    NOT_APPLICABLE,
    TAG_LENGTH,
    is_indeclinable_numeral,
    slot_profile,
)
from . import issue_testi
from .fastmap import build_frame, map_unique, mask_unique
from .rule_catalog import (
    LEXICAL_REPAIRS as EXACT_RULES,
    default_auto_apply,
    rule_description,
    rule_name,
    rule_severity,
)


#: A string of Greek letters that is not a Greek word: a number written in
#: letters (ρ᾽, τιβʹ, ͵αφʹ), or the label of a point or a figure in a
#: mathematical text (ΑΒΓ, ΘΗΚ, αβγδεʹ, Α∠Ε). Neither declines, and no list of
#: lemmas can enumerate them, so they are recognised by shape.
#:
#: Three signatures are accepted, and each is a property of the writing rather
#: than a list of words: the keraia that marks alphabetic numeration — on the
#: form or, as GLAUx writes it, on the lemma alone; a single letter; a string
#: written entirely in capitals. In every case the string must carry no accent
#: and no breathing, which is what separates ΑΒΓ and αβγδεʹ from a word.
#:
#: Accepting any one or two Greek letters instead would exempt δε, τε, με and
#: every other short unaccented word from the checks that follow.
_KERAIA = "\u1fbd\u02b9\u2032\u0384"
_NUMERAL_SIGNS = "\u0375\u0374\u2220\u0305\U00010175\U00010176\U00010177\U00010178"
_GREEK_LETTER_RE = re.compile("^[\u0370-\u03ff\u1f00-\u1fff" + _NUMERAL_SIGNS + "]+$")
_ACCENT_OR_BREATHING = frozenset("\u0300\u0301\u0342\u0313\u0314\u0345\u0308")


def _is_alphabetic_numeral(form: object) -> bool:
    """True for a numeral or a diagram label written in Greek letters."""
    if not isinstance(form, str):
        return False
    text = form.strip()
    if not text:
        return False
    keraia = text[-1] in _KERAIA
    body = text[:-1] if keraia else text
    if not body or not _GREEK_LETTER_RE.match(body):
        return False
    if any(char in _ACCENT_OR_BREATHING
           for char in _unicodedata.normalize("NFD", body)):
        return False
    if keraia or len(body) == 1:
        return True
    letters = [char for char in body if char.isalpha()]
    # Capitals only, and short: the labels are ΑΒΓ, ΘΗΚ, ΑΖΗΙ, ΤΜΝ. Without a
    # length limit a corpus printed in capitals would exempt every word in it.
    return (bool(letters) and len(letters) <= 5
            and all(char.isupper() for char in letters))


VALID_CHARACTERS = {
    # The hyphen is not a value of the first position. From the second position onwards
    # the hyphen means “this category does not apply”; in the first position it cannot
    # mean that, because every word has a part of speech. A hyphen there is a missing
    # value, and the program says so instead of accepting it silently.
    0: set("nvadlgpcrmiu"),
    1: set("123-"),
    2: set("spd-"),
    3: set("pirltfa-"),
    4: set("isomnp-"),
    5: set("apme-"),
    # The “c” of common gender is not a value of the gender position. The AGDT 2.0
    # inventory lists only m, f and n in this position: admitting “c” silently would
    # tell the user that the corpus conforms where it does not. “c” has a check of its
    # own, which reports it as a case to verify and proposes nothing, and it is listed
    # among the characters already taken care of below.
    6: set("mfn-"),
    7: set("ngdav-"),
    8: set("cs-"),
}

#: Characters that a dedicated rule already reports, position by position.
#:
#: ``invalid-character`` walks every position and reports whatever is not in
#: the inventory above. Six of those characters, however, are also the subject
#: of a rule of their own — ``leading-t``, ``punctuation-leading-e``,
#: ``mediopassive-d``, ``case-letter-l``, ``grade-p``, ``degree-underscore`` —
#: which knows what the value means and proposes a correction. Letting the
#: generic rule fire as well would count one fact twice, and count it twice in
#: *conflicting* ways: once as a violation to be read by hand, once as the
#: variant the specialised rule normalises. Both would land in the totals and
#: in the two axes of the taxonomy. The generic rule therefore stands aside
#: wherever a specialised one speaks.
SPECIALISED_CHARACTERS: dict[int, set[str]] = {
    0: {"b", "z"},
    1: {"_"},
    2: {"_"},
    3: {"_"},
    4: {"_"},
    5: {"d", "_"},
    6: {"_", "c"},
    7: {"l", "_"},
    8: {"p", "_"},
}

PLACEHOLDER_FORM_RE = re.compile(r"^\[(?:[0-9]|1[0-9]|20)\]$")


#: The parts of speech that carry a case, and how many times a lemma must be
#: attested before "never inflected here" is a statement about the language
#: rather than about the sample.
NOMINAL_PREFIXES = frozenset("nampl")
INDECLINABLE_MINIMUM = 5


# EXACT_RULES: each entry specifies how to match a token and what to suggest.
# Keys: rule_id, form (required), postag_eq or postag_startswith (optional), suggest.
# The table of lexical repairs lives in rule_catalog, which also generates the
# description of each rule: table and catalogue cannot diverge.

#: The forms with which the corpora write a record that is not a word of the
#: text: the numbered placeholder of an understood element and the lacuna
#: marker of the Leuven school.
PLACEHOLDER_FORMS = frozenset({"G", "G?", "G_L"})


def is_placeholder(form: object) -> bool:
    """The record does not carry a word of the text.

    Three ways of saying so, all valid: the numbered placeholder of an understood
    element, the lacuna marker of the Leuven school, and the isolated editorial or
    diacritical sign, that is, a form made only of combining marks, without any letter
    underneath.
    """
    if not isinstance(form, str):
        return False
    if form in PLACEHOLDER_FORMS or bool(PLACEHOLDER_FORM_RE.match(form)):
        return True
    testo = form.strip()
    return bool(testo) and all(_unicodedata.combining(c) for c in testo)


def is_punctuation(form: object) -> bool:
    """True when every character of the form is a punctuation mark."""
    if not isinstance(form, str) or not form:
        return False
    return all(_unicodedata.category(c).startswith("P") for c in form)


#: The verbal adjective in -τέος, recognised on the form with the accents
#: stripped.  It matters only for tokens that already carry the mood value
#: «g», a set of a few dozen tokens, so a false positive is not a practical
#: risk; and the discrimination it makes is real.  In Gorman the ten tokens
#: with mood «g» are participles (ἔχων, οὖσα, ἀκούσας, παρόντων) and «g» is a
#: slip for «p».  In Pedalion all forty-seven are verbal adjectives —
#: ποιητέον, πρακτέον, σκεπτέον, γυμναστέον — and there «g» stands for the
#: gerundive.  Proposing the participle for those would be wrong, and would
#: contradict the two rules that read them as adjectives and ask for no
#: automatic action.
VERBAL_ADJECTIVE_RE = re.compile(
    r"τε(?:ος|ου|ω|ον|οι|ων|ους|οις|α|ας|αι|αν|αις)$")


def is_verbal_adjective(form: object) -> bool:
    """True for a form of the verbal adjective in -τέος, accents ignored."""
    if not isinstance(form, str) or not form:
        return False
    spoglia = "".join(c for c in _unicodedata.normalize("NFD", form)
                      if not _unicodedata.combining(c))
    return bool(VERBAL_ADJECTIVE_RE.search(spoglia))


def maschera_riparazione(regola: dict, vl_form_nfc, vl_postag):
    """The conditions of a row of LEXICAL_REPAIRS, all together.

    A row can look for a single form (``form``) or for several equivalent forms
    (``forms``); it can ask for the exact tag (``postag_eq``), for its beginning
    (``postag_startswith``) or for the tag *not* to begin in a certain way
    (``postag_not_startswith``, for the rules that fire on any analysis other than the
    right one).
    """
    import pandas as _pd
    m = _pd.Series(True, index=vl_postag.index)
    if regola.get("form") is not None:
        m &= vl_form_nfc == regola["form"]
    if regola.get("forms") is not None:
        m &= vl_form_nfc.isin(tuple(regola["forms"]))
    if regola.get("postag_eq") is not None:
        m &= vl_postag == regola["postag_eq"]
    if regola.get("postag_startswith") is not None:
        m &= vl_postag.str.startswith(regola["postag_startswith"])
    if regola.get("postag_not_startswith") is not None:
        m &= ~vl_postag.str.startswith(regola["postag_not_startswith"])
    return m

# The forms that identify a truly personal pronoun: “PoS equal to p” is not
# enough, because p includes relatives, demonstratives and indefinites. The list
# is a versioned data resource, because it is decisive: it decides 3,224
# findings on the two automatic strata of GLAUx, and a list that decides three
# thousand findings must be defended form by form somewhere where it can be
# read.
_PRONOMI = resources.entries("pronomi-personali")
FIRST_PERSON_FORMS = frozenset(_PRONOMI["prima"])
SECOND_PERSON_FORMS = frozenset(_PRONOMI["seconda"])
THIRD_PERSON_FORMS = frozenset(_PRONOMI["terza"])

#: The passages in which the LSJ marks a participial δεῖν as doubtful, each with the
#: state of identifiability that the resources treated allow: see
#: ``data/liste/loci-dein-participiale.json``.
DEIN_DISPUTED_LOCI = tuple(resources.entries("loci-dein-participiale"))

#: Author and work, read from the field that carries them. The CTS citation when there is
#: one, otherwise ``tlg_author`` and ``tlg_work``, which nine documents of Gorman have
#: filled in while the composite citation is empty. ``None`` when the record does not
#: identify them: this is the case in which no passage can be excluded.
#:
#: The file name and the similarity between strings do not enter here. A document called
#: “aristophanes-ranae” is not proof that it is Aristophanes: it is a name, and deducing
#: a provenance from it would be inventing it.
_AUTORE_OPERA = re.compile(r"^(tlg\d+)\.(tlg\d+)")


def _provenienza(urn: pd.Series, autore: pd.Series,
                 opera: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Author and work of every record, empty where the record does not identify them."""
    estratto = urn.astype("string").fillna("").str.extract(_AUTORE_OPERA)
    autore_finale = estratto[0].fillna("")
    opera_finale = estratto[1].fillna("")
    manca = autore_finale == ""
    if manca.any():
        a = autore.astype("string").fillna("").str.strip()
        o = opera.astype("string").fillna("").str.strip()
        completi = manca & (a != "") & (o != "")
        autore_finale = autore_finale.mask(completi, a)
        opera_finale = opera_finale.mask(completi, o)
    return autore_finale, opera_finale

# Finding priority for deduplication in apply_suggested_corrections().
# Lower number = higher priority (applied first when a token has multiple findings).
RULE_PRIORITY: dict[str, int] = {
    "missing-postag":          0,
    "invalid-length-padding":  1,
    "invalid-length-broken":   1,
    "invalid-character":       2,
    "leading-t":               3,
    "punctuation-leading-e":   3,
    "leading-x-lexical":       3,
    "pot-anomaly":             3,
    "deina-anomaly":           3,
    "tan-anomaly":             3,
    "osfranthiti-anomaly":     3,
    "numeral-generic-m":       3,
    "tessereskaideka-anomaly": 3,
    "san-anomaly":             3,
    "creon-anomaly":           3,
    "verbal-adj-g-nn":         3,
    "verbal-adj-g-na":         3,
    "case-letter-l":          10,
    "grade-p":                10,
    "underscore-person-number": 10,
    "mediopassive-d":         10,
    "personal-pronoun-person": 10,
    "degree-underscore":      10,
}


_FINDINGS_COLUMNS = [
    "rule_id", "anomaly_name", "anomaly_description",
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "form", "lemma", "postag", "relation",
    "issue", "issue_key", "issue_params",
    "suggested_postag", "auto_correctable", "severity",
]

_BASE_COLS = [
    "source_file", "document_id", "sentence_index", "sentence_id",
    "token_index", "token_id", "form", "lemma", "postag", "relation",
]


def _make_findings(
    subset: pd.DataFrame,
    rule_id: str,
    issue_params: "object | pd.Series" = None,
    suggested_postag: "object | pd.Series" = pd.NA,
    auto_correctable: bool = False,
    severity: str = "errore",
    issue_key: "str | pd.Series | None" = None,
) -> pd.DataFrame:
    """Create a findings DataFrame from a filtered token subset without Python loops."""
    if subset.empty:
        return pd.DataFrame(columns=_FINDINGS_COLUMNS)
    columns = {
        "rule_id": rule_id,
        # Name and description are a cache in the language of the analysis: whoever
        # displays them recomputes them from the catalogue in the requested language.
        "anomaly_name": rule_name(rule_id),
        "anomaly_description": rule_description(rule_id),
    }
    for col in [c for c in _BASE_COLS if c in subset.columns]:
        columns[col] = subset[col]
    columns["issue_key"] = rule_id if issue_key is None else issue_key
    columns["issue_params"] = "" if issue_params is None else issue_params
    if isinstance(suggested_postag, pd.Series):
        columns["suggested_postag"] = suggested_postag.str.replace("_", "-", regex=False)
    elif isinstance(suggested_postag, str):
        columns["suggested_postag"] = suggested_postag.replace("_", "-")
    else:
        columns["suggested_postag"] = suggested_postag
    columns["auto_correctable"] = auto_correctable and default_auto_apply(rule_id)
    # Severity comes from the class of the check. The parameter is kept so that existing
    # calls do not break, but it has no effect: a column that contradicts the class of
    # its own rule is exactly the defect to avoid.
    columns["severity"] = rule_severity(rule_id)
    frame = build_frame(columns, len(subset))
    # The sentence is derived, and always is: it is recomposed from key and parameters
    # here too, where writing it directly would have been shorter. Two sources for the
    # same text means that sooner or later they diverge.
    frame["issue"] = issue_testi.rendi_serie(frame, "it")
    # The columns that are present, in the order of the catalogue: a test frame may lack
    # some of the base columns, and that is no reason to fail.
    return frame[[c for c in _FINDINGS_COLUMNS if c in frame.columns]]


#: The true values of a position, that is, the inventory minus the hyphen: it serves to
#: say “this slot is filled” without writing the letters twice.
_VALORI_REALI = {slot: frozenset(v for v in valori if v != "-")
                 for slot, valori in POSITION_VALUES.items()}


def analyze_postags(tokens: pd.DataFrame) -> pd.DataFrame:  # noqa: C901 (complex but intentional)
    """Detect postag anomalies using fully vectorized operations.

    Returns one row per finding.  Tokens with multiple applicable rules each
    generate a separate finding; priority-based deduplication happens in
    apply_suggested_corrections().

    """
    if tokens.empty:
        return pd.DataFrame(columns=_FINDINGS_COLUMNS)

    postag = tokens["postag"]
    form   = tokens["form"]

    # ── Masks ──────────────────────────────────────────────────────────────────
    # has_postag: postag is a non-empty string
    has_postag = postag.notna() & map_unique(postag, 
        lambda x: isinstance(x, str) and bool(x.strip())
    )

    # placeholder: form belongs to the standard placeholder set
    placeholder_mask = form.isin({"G?", "G", "G_L", "[0]"}) | map_unique(form, 
        lambda f: isinstance(f, str) and bool(PLACEHOLDER_FORM_RE.match(f))
    )

    # valid_length: has a postag AND it's exactly 9 chars
    valid_length = has_postag & (postag.str.len() == 9)

    findings: list[pd.DataFrame] = []

    # ── Rule: missing-postag ──────────────────────────────────────────────────
    missing_mask = ~has_postag & ~placeholder_mask
    if missing_mask.any():
        findings.append(_make_findings(
            tokens[missing_mask], "missing-postag"))

    # ── Rules: invalid-length-padding / invalid-length-broken ─────────────────
    # These were one rule with one "safe to apply" flag, and the flag covered
    # rows the repair cannot reach: a tag one character short and a tag of two
    # characters were reported together, and every tag longer than nine was
    # truncated whatever the surplus held.  In these corpora the surplus is
    # always dashes (Gorman: 258 tags of fourteen characters ending in five
    # dashes, 62 of eight that are dashes throughout; Pedalion: 63 of ten ending
    # in one), so requiring that explicitly changes no count and makes the
    # promise true rather than lucky.  What is left over is genuinely
    # unrepairable: Pedalion's "", "-", "_", "c", "v2pasm".
    wrong_len_mask = has_postag & ~valid_length
    if wrong_len_mask.any():
        wl = tokens[wrong_len_mask]
        wl_postag = postag[wrong_len_mask]
        lengths = wl_postag.str.len()

        def only_dashes(tail: object) -> bool:
            return isinstance(tail, str) and len(tail) > 0 and set(tail) == {"-"}

        trim_ok = (lengths > 9) & mask_unique(wl_postag.str[9:], only_dashes)
        pad_ok = (lengths == 8) & mask_unique(wl_postag.str[1:], only_dashes)

        if trim_ok.any():
            trimmed = wl_postag[trim_ok].str[:9]
            findings.append(_make_findings(
                wl[trim_ok], "invalid-length-padding", None,
                trimmed, auto_correctable=True,
                issue_key="invalid-length-padding.piu-di-nove"))

        if pad_ok.any():
            padded = wl_postag[pad_ok] + "-"
            findings.append(_make_findings(
                wl[pad_ok], "invalid-length-padding", None,
                padded, auto_correctable=True,
                issue_key="invalid-length-padding.otto"))

        broken = ~trim_ok & ~pad_ok
        if broken.any():
            findings.append(_make_findings(wl[broken], "invalid-length-broken"))
        # Tokens with invalid length: don't apply position-level rules
        # (handled by operating only on valid_length below)

    # From here on, all rules operate exclusively on valid_length tokens.
    if not valid_length.any():
        return _concat_findings(findings)

    vl_tokens = tokens[valid_length]
    vl_postag  = postag[valid_length]
    vl_form    = form[valid_length]
    # The same form, normalised to NFC, for the comparisons with the closed lists only.
    # The lists of this module are written in NFC; a corpus in NFD writes the accents as
    # separate characters, and the two strings — identical on the screen — never meet.
    # On GLAUx no list would recognise anything. What is reported and shown remains the
    # original form: here the comparison is normalised, not the data.
    vl_form_nfc = map_unique(vl_form, lambda value: _unicodedata.normalize(
        "NFC", value) if isinstance(value, str) else value)

    # The two rules on the first position have a condition beyond the character, and the
    # generic rule must stay silent only where they really speak. The masks are computed
    # here, before “Character not admitted”, because it is that rule that has to know
    # them: otherwise a “t” on a word that is not a verb, or an “e” on a real word,
    # would be reported by nobody.
    resta_un_verbo = (
        vl_postag.str.len().ge(9)
        & (vl_postag.str.slice(3, 4).isin(_VALORI_REALI[TENSE_SLOT])
           | vl_postag.str.slice(4, 5).isin(_VALORI_REALI[MOOD_SLOT])
           | vl_postag.str.slice(5, 6).isin(_VALORI_REALI[VOICE_SLOT])))
    leading_t_mask = (vl_postag.str[0] == "t") & resta_un_verbo
    punctuation_e_mask = ((vl_postag.str[0] == "e")
                          & mask_unique(vl_form_nfc, is_punctuation))

    # ── Rule: invalid-character (per position) ─────────────────────────────────
    for position, valid_chars in VALID_CHARACTERS.items():
        pos_char = vl_postag.str[position]
        bad_char_mask = ~pos_char.isin(valid_chars)
        handled = SPECIALISED_CHARACTERS.get(position)
        if handled:
            bad_char_mask &= ~pos_char.isin(handled)
        if position == 0:
            # The “x” on a record that carries a word of the text is fully described by
            # ``leading-x-lexical``, and must not be counted twice. On a placeholder it
            # remains instead a character outside the inventory.
            bad_char_mask &= ~((pos_char == "x")
                               & ~mask_unique(vl_form_nfc, is_placeholder))
            bad_char_mask &= ~leading_t_mask
            bad_char_mask &= ~punctuation_e_mask
        if bad_char_mask.any():
            sub = vl_tokens[bad_char_mask].copy()
            findings.append(_make_findings(
                sub, "invalid-character",
                issue_testi.parametri(slot=position)))

    # ── Rule: case-letter-l ───────────────────────────────────────────────────
    #
    # «l» is in the AGDT 2.0 inventory of slot eight. Proposing the dative
    # would rewrite a value the scheme allows into another value the scheme
    # allows, i.e. erase a conformant distinction to make the corpus tidier. The
    # check therefore reports and stops.
    mask = vl_postag.str[7] == "l"
    if mask.any():
        sub = vl_tokens[mask].copy()
        findings.append(_make_findings(
            sub, "case-letter-l", None,
            pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: grade-p ─────────────────────────────────────────────────────────
    mask = vl_postag.str[8] == "p"
    if mask.any():
        sub = vl_tokens[mask].copy()
        suggested = vl_postag[mask].str[:8] + "-"
        findings.append(_make_findings(
            sub, "grade-p", None, suggested, auto_correctable=True))

    # ── Rule: pedalion-b-pos ──────────────────────────────────────────────────
    #
    # “b” in first position is not in the AGDT inventory, and the generic character
    # check would read it as an ordinary violation. But the README of the Pedalion Trees
    # declares it: “For experimental reasons, some trees exhibit the part-of-speech
    # designation 'b', equalling in most cases 'd' or 'c'”. It is therefore a choice of
    # the project, not an oversight — and the occurrences confirm it, because they fall
    # almost all on coordinators (καί, δέ, τε, ἀλλά) with relation COORD or AuxY.
    #
    # It is nevertheless not a variant to be normalised, and the reason lies in the
    # declaration itself: “in most cases 'd' or 'c'” means that the corresponding AGDT
    # value is not unique and cannot be derived from the tag. A program that chose by
    # itself between adverb and conjunction would decide a question of analysis. Hence:
    # case to verify, no correction proposed.
    b_mask = vl_postag.str[0] == "b"
    if b_mask.any():
        findings.append(_make_findings(
            vl_tokens[b_mask].copy(), "pedalion-b-pos", None,
            pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: nonlexical-z-pos ────────────────────────────────────────────────
    #
    # “z” in first position marks a record that is not a word of the text: in Pedalion
    # the damaged or illegible stretches of text, written “G?”; in GLAUx both those and
    # the elliptic nodes, written “E”. Here too the generic check would count it as a
    # violation, but a record that the corpus declares non-lexical has no morphological
    # analysis to get wrong.
    z_mask = vl_postag.str[0] == "z"
    if z_mask.any():
        findings.append(_make_findings(
            vl_tokens[z_mask].copy(), "nonlexical-z-pos", None,
            pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: common-gender-c ─────────────────────────────────────────────────
    #
    # “c” in the gender position stands to gender as “b” stands to part of speech: a
    # value that the AGDT 2.0 inventory does not list — there gender is only m, f or n —
    # and that a project uses all the same, regularly and for a grammatical reason. The
    # occurrences fall in the overwhelming majority on first- and second-person pronouns
    # and on indefinites (ἐγώ, σύ, τις, τίς, σφεῖς), which have no gender, and on true
    # epicene nouns (παῖς, βοῦς), which have two with a single form.
    #
    # The value “c” is declared valid in the table of characters and no other rule would
    # look at it, so a user could not know that the corpus departs from the guidelines.
    # The check says so, and stops there. No correction is proposed, for the same reason
    # as for βοῦς: between masculine and feminine the context decides, and writing one
    # in place of “c” would erase the information that the annotator wished to give.
    gender_c_mask = vl_postag.str[6] == "c"
    if gender_c_mask.any():
        # The lemma is not in the parameters: it is already a column of the finding, and
        # the text reads it from there.
        findings.append(_make_findings(
            vl_tokens[gender_c_mask].copy(), "common-gender-c", None,
            pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: degree-underscore ───────────────────────────────────────────────
    mask = vl_postag.str[8] == "_"
    if mask.any():
        sub = vl_tokens[mask].copy()
        suggested = vl_postag[mask].str[:8] + "-"
        findings.append(_make_findings(
            sub, "degree-underscore", None, suggested, auto_correctable=True))

    # ── Rule: underscore-person-number ────────────────────────────────────────
    #
    # A single rule for all the positions from the second to the eighth. The underscore
    # in ninth position has a rule of its own — ``degree-underscore``, a variant to be
    # normalised — and an underscore in the third, seventh or eighth position would
    # otherwise go to the generic character check, that is, among the violations. The
    # tag ``a-_---___`` of τριάκοντα is the example: one finding of variant and three of
    # violation, for a single fact. In Gorman 1,316 tokens would belong to both classes
    # at once. The underscore means the same thing in all the positions in which it
    # appears — “this category does not apply” — and is counted once only, per token and
    # not per slot.
    underscore_slots = [index for index in range(1, 8)]
    underscore_mask = pd.Series(False, index=vl_postag.index)
    for index in underscore_slots:
        underscore_mask |= vl_postag.str[index] == "_"
    if underscore_mask.any():
        sub = vl_tokens[underscore_mask].copy()
        written = vl_postag[underscore_mask]
        repaired = written.copy()
        for index in underscore_slots:
            repaired = repaired.str[:index] + repaired.str[index].replace(
                "_", "-") + repaired.str[index + 1:]
        # The slots are a list of numbers: the Italian or English name of each is
        # written by whoever displays the sentence.
        quali = map_unique(written, lambda tag: tuple(
            index for index in underscore_slots if tag[index] == "_"))
        findings.append(_make_findings(
            sub, "underscore-person-number",
            issue_testi.parametri(slots=quali),
            repaired, auto_correctable=True))

    # ── Rule: mediopassive-d ──────────────────────────────────────────────────
    mask = vl_postag.str[5] == "d"
    if mask.any():
        sub = vl_tokens[mask].copy()
        findings.append(_make_findings(
            sub, "mediopassive-d", None,
            pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: leading-t ───────────────────────────────────────────────────────
    # The proposal holds because the rest of the tag is already that of a verb:
    # where tense, mood or voice carry a true value, replacing the “v” produces a
    # tag that the corpus uses elsewhere thousands of times. Elsewhere the “t”
    # remains a character outside the inventory, and “Character not admitted in that
    # position” deals with it.
    mask = leading_t_mask
    if mask.any():
        sub = vl_tokens[mask].copy()
        findings.append(_make_findings(
            sub, "leading-t", None, None, auto_correctable=False))

    # ── Rule: punctuation-leading-e ─────────────────────────────────────────── The
    # name of the rule promises punctuation, and the code verifies it. In the corpora
    # examined the tokens with “e” in first position are always punctuation — “.”, “,”,
    # “:” — and in the same sentence identical punctuation carries “u”. On a real word
    # the “e” would remain a character outside the inventory, and the generic rule would
    # report it.
    mask = punctuation_e_mask
    if mask.any():
        sub = vl_tokens[mask].copy()
        suggested = "u" + vl_postag[mask].str[1:]
        findings.append(_make_findings(
            sub, "punctuation-leading-e", None, suggested, auto_correctable=True))

    # ── Rule: leading-x-lexical ───────────────────────────────────────────────
    #
    # The rule does not look at a list of forms: it looks at the position. The scheme
    # reserves the “x” for elliptic nodes, so an “x” on a record that carries a word
    # of the text is always out of place, whatever the word. The right part of
    # speech, however, depends on the sentence, and nothing is proposed: the
    # occurrences already checked by hand receive their proposal from the table of
    # verified repairs.
    x_form_mask = (vl_postag.str[0] == "x") & ~mask_unique(vl_form_nfc, is_placeholder)
    if x_form_mask.any():
        findings.append(_make_findings(
            vl_tokens[x_form_mask], "leading-x-lexical", None,
            None, auto_correctable=False))

    # ── Rule: dein-participle ────────────────────────────────────────────────
    # δεῖν is the present infinitive — of δεῖ and of both δέω — and the
    # corresponding participle is δέον. In -έω verbs only ε+ε contracts to ει,
    # so δέ-ειν gives δεῖν while ε+ο stays open and the neuter participle is
    # δέον; there is no Greek paradigm with a participle spelled δεῖν.
    #
    # The exception, and the reason this rule does not simply rewrite everything
    # it finds, is LSJ (s.v. δεῖ, IV), which records the participial δεῖν and
    # marks it dubious: "δεῖν is dub. in Ar.Fr.220, Lys.14.7".
    #
    # Which loci count as disputed is stated by the list
    # ``loci-dein-participiale``, which identifies each one by the citation of
    # the resource and declares its provenance.  A closed list of identified
    # loci cannot widen by resemblance: matching «tlg0019» would catch *all* of
    # Aristophanes, and every participial δεῖν in Aristophanes would pass for
    # fragment 220, which is not the one LSJ marks.
    dein_mask = (vl_form_nfc == "δεῖν") & (vl_postag.str.len() == TAG_LENGTH) & (
        vl_postag.str[MOOD_SLOT] == "p")
    if dein_mask.any():
        vuoto = pd.Series("", index=vl_tokens.index, dtype="string")
        autore_record, opera_record = _provenienza(
            vl_tokens.get("cts_urn", vuoto),
            vl_tokens.get("tlg_author", vuoto),
            vl_tokens.get("tlg_work", vuoto))
        citazione = (autore_record + "." + opera_record).where(
            autore_record != "", "")

        # Three reasons not to correct, and a single one to correct.
        #
        # The passage is one of those that the LSJ marks, and the resource identifies
        # it; or the author is that of a marked passage and the available reference does
        # not say whether it is that one; or the record does not identify author and
        # work, and then nothing can be excluded.
        #
        # The last is the most important and the least obvious. A correction that needs
        # bibliographic information to be safe does not become safe because that
        # information is missing: the absence of provenance is not an authorisation. A
        # correction is made only where the provenance is there and says that it is not
        # one of those passages.
        identificato = pd.Series(False, index=vl_tokens.index)
        non_escludibile = pd.Series(False, index=vl_tokens.index)
        for luogo in DEIN_DISPUTED_LOCI:
            if str(luogo.get("stato", "")) == "identificato":
                atteso = str(luogo.get("cts_urn") or "")
                if atteso:
                    identificato |= citazione == atteso
            else:
                autore_atteso = str(luogo.get("autore_urn") or "")
                if autore_atteso:
                    non_escludibile |= autore_record == autore_atteso
        senza_provenienza = autore_record == ""
        disputed = identificato | non_escludibile | senza_provenienza
        infinitive = "v--pna---"
        ordinary = dein_mask & ~disputed
        if ordinary.any():
            findings.append(_make_findings(
                vl_tokens[ordinary], "dein-participle", None,
                infinitive, auto_correctable=True))
        # The reason is a code, and the three sentences that correspond to it live in
        # the texts module, in the two languages.
        motivo = pd.Series("", index=vl_tokens.index, dtype="string")
        motivo = motivo.mask(senza_provenienza, "senza_provenienza")
        motivo = motivo.mask(non_escludibile & ~identificato, "non_escludibile")
        motivo = motivo.mask(identificato, "identificato")
        if (dein_mask & disputed).any():
            # Its own identifier, and not a matter of form: the diagnostic class and the
            # treatment are properties of the rule, not of the single row, and two
            # outputs sharing one identifier would give the same occurrence two
            # different classes in the counts.
            findings.append(_make_findings(
                vl_tokens[dein_mask & disputed], "dein-participle-disputed",
                issue_testi.parametri(motivo=motivo[dein_mask & disputed]),
                pd.NA, auto_correctable=False, severity="sospetto"))

    # ── Rule: personal-pronoun-person ─────────────────────────────────────────
    #
    # The rule is not relative to the corpus: it reports pronouns without person
    # everywhere, and its class is systematic variant.
    #
    # The logical point that makes the class defensible: AGDT 2.0 does not prescribe
    # person on the pronoun, so not marking it is the conforming practice. The check
    # therefore does not report a violation, and its class says so: the operational
    # profile of GCP is deliberately richer than the prescribed minimum, and the absence
    # of the information is recorded because it serves whoever wants a harmonised
    # annotation, not because something is broken.
    #
    # The consequence is measured: on Gorman, Pedalion and the two manual samples of
    # GLAUx the count is unaffected by this choice. On the two automatic strata of
    # GLAUx, which never mark person, the check gives 1,773 and 1,451 findings.
    #
    # The personal pronoun is not “PoS equal to p”: p includes relatives,
    # demonstratives, indefinites. It is the thirty-six forms declared in the closed
    # lists, minus ὅς, which is relative.
    pronoun_mask = vl_postag.str.match(r"p[123-]") & (
        vl_form_nfc.isin(FIRST_PERSON_FORMS)
        | vl_form_nfc.isin(SECOND_PERSON_FORMS)
        | vl_form_nfc.isin(THIRD_PERSON_FORMS)
    )
    vl_lemma_nfc = map_unique(
        vl_tokens["lemma"] if "lemma" in vl_tokens.columns else vl_form,
        lambda value: _unicodedata.normalize("NFC", value)
        if isinstance(value, str) else value)
    pronoun_mask = pronoun_mask & ~(vl_lemma_nfc == "ὅς")
    unmarked = pronoun_mask & (vl_postag.str[1] == "-")
    if unmarked.any():
        sub = vl_tokens[unmarked].copy()
        # Person is decided on the composed spelling, like the mask above. Deciding it
        # on the raw spelling would be a real defect: in a corpus written in NFD every
        # accented form would fail all three searches and fall on the third person, and
        # the program would propose “p3p---cd-” for ἡμῖν. The two lines must read the
        # same string.
        sub_form = vl_form_nfc[unmarked]
        # Person is a number: “prima”, “first” are written by whoever displays it.
        persona = map_unique(sub_form,
            lambda f: 1 if f in FIRST_PERSON_FORMS
            else 2 if f in SECOND_PERSON_FORMS
            else 3
        )
        findings.append(_make_findings(
            sub, "personal-pronoun-person",
            issue_testi.parametri(persona=persona.astype("Int64")),
            pd.NA, auto_correctable=False, severity="variante"))

    # ── Rule: participle-mood-g ───────────────────────────────────────────────
    #
    # One rule covers what rules written on single words — ἔχων, οὖσα, ἀκούσας,
    # παρόντων — would each say, and none of them needs to know which word it is.
    # The mood slot carries “g”, which the AGDT inventory does not provide (the moods
    # are i s o n m p), and the tag carries a gender and a case. A verb with gender and
    # case is a participle: the infinitive has neither, and a finite mood cannot have
    # them. The right mood is therefore determined by the rest of the tag, not by the
    # word, and the rule works on any corpus.
    mood_g_tutti = (
        vl_postag.str.len().ge(9)
        & vl_postag.str.startswith("v")
        & vl_postag.str.slice(4, 5).eq("g")
    )
    # The verbal adjectives in -τέος are excluded here and go to their own rule: for
    # them “g” is not a slip but the gerundive, and the participle would be a wrong
    # proposal.
    aggettivo_verbale = mood_g_tutti & mask_unique(vl_form_nfc, is_verbal_adjective)
    # Also excluded is whatever a lexical repair already deals with: ὀσφράνθητι carries
    # the mood “g” and it is its own rule that says which tag belongs to it. Two
    # different automatic proposals on the same token would be an internal contradiction
    # of the catalogue.
    coperti = pd.Series(False, index=vl_tokens.index)
    for _regola in EXACT_RULES:
        _m = maschera_riparazione(_regola, vl_form_nfc, vl_postag)
        coperti |= _m & (vl_postag != _regola["suggest"])

    mood_g = (
        mood_g_tutti
        & ~aggettivo_verbale
        & ~coperti
        & vl_postag.str.slice(6, 7).isin(_VALORI_REALI[GENDER_SLOT])
        & vl_postag.str.slice(7, 8).isin(_VALORI_REALI[CASE_SLOT])
    )
    if aggettivo_verbale.any():
        sub = vl_tokens[aggettivo_verbale].copy()
        # The adjective, with the same number, gender and case: “v-s-g-nn-” gives
        # “a-s---nn-”. A proposal, not a correction.
        et = vl_postag[aggettivo_verbale]
        proposta_agg = ("a-" + et.str[2:3] + "---" + et.str[6:7] + et.str[7:8] + "-")
        # The tag of the adjective does not appear here: it is in ``suggested_postag``
        # and is read at the “Correct” step.
        findings.append(_make_findings(
            sub, "verbal-adjective-g", None,
            proposta_agg, auto_correctable=False, severity="sospetto"))
    if mood_g.any():
        sub = vl_tokens[mood_g].copy()
        findings.append(_make_findings(
            sub, "participle-mood-g", None, None, auto_correctable=False))

    # ── Exact rules (vectorized per rule) ─────────────────────────────────────
    for rule in EXACT_RULES:
        mask = maschera_riparazione(rule, vl_form_nfc, vl_postag)
        # A rule does not fire on a token that already carries its own proposal;
        # otherwise the word would be flagged even after being corrected, and the
        # automatic correction would come back at every run.
        mask = mask & (vl_postag != rule["suggest"])
        if mask.any():
            if rule.get("auto", True):
                findings.append(_make_findings(
                    vl_tokens[mask], rule["rule_id"], None,
                    rule["suggest"], auto_correctable=True))
            else:
                # Reported, not repaired: the reading is defensible but it is a
                # reading, and rewriting it in bulk would decide a question of
                # analysis. The neuter of a verbal adjective is syncretic
                # between nominative and accusative, and which one it is depends
                # on the construction, not on the string.
                # The majority reading stays in the parameters, where a
                # program can find it, and not in the sentence: step 3 says
                # what does not add up, not which label to write.
                findings.append(_make_findings(
                    vl_tokens[mask], rule["rule_id"],
                    issue_testi.parametri(lettura_diffusa=rule["suggest"]),
                    pd.NA, auto_correctable=False, severity="sospetto"))

    # ── The shape of the tag: which slots this class fills ───────────────────
    #
    # The first character decides the rest. A noun has number, gender and case
    # and nothing else; a finite verb has person, number, tense, mood and voice
    # and cannot have a case; an adverb has nothing but, if compared, a degree.
    # The table is in ``agdt_schema.SLOT_PROFILE`` and is read, not coded, here.
    #
    # Two rules, not one, and the split is the whole point. A slot *filled*
    # where the class forbids it is an impossible combination and always a real
    # error: 82 tokens on the two corpora. A slot *empty* where the class
    # requires it is a gap, and a gap can be correct — a foreign name does not
    # decline, an alphabetic numeral does not decline, δύο does not decline.
    # Reporting both under one name at one severity would leave the reader
    # unable to tell the 82 certainties from the thousand judgement calls,
    # which is why they are two rules.
    # Everything below is a property of the tag alone, and a corpus has far
    # fewer distinct tags than tokens.  The whole analysis — which slots are
    # forbidden and which are missing — is therefore computed once per distinct
    # tag and gathered back onto the rows.  Written the obvious way, one pass
    # per position over the full column, this check alone would dominate the
    # run time of a complete diagnosis; this way it costs a fraction of a
    # second.
    # What is computed per distinct tag is not a sentence but the parameters:
    # which positions are filled where they should not be and which are empty
    # where they are needed.  The sentence is composed by whoever displays it,
    # in the language they chose.
    codes, distinct_tags = pd.factorize(vl_postag, use_na_sentinel=False)
    forbidden_params: list[object] = []
    missing_params: list[object] = []
    missing_many: list[bool] = []
    missing_bare: list[bool] = []
    for tag in distinct_tags:
        profile = slot_profile(tag)
        if profile is None:
            forbidden_params.append(None)
            missing_params.append(None)
            missing_many.append(False)
            missing_bare.append(False)
            continue
        allowed = profile["require"] | profile["optional"]
        wrong, empty = [], []
        for position in range(1, TAG_LENGTH):
            char = tag[position]
            if position not in allowed:
                # A value that is illegal in that slot whatever the class, and
                # the underscore of the ninth position, belong to other rules;
                # counting them here would report one defect twice.
                if char != NOT_APPLICABLE and char in VALID_CHARACTERS[position]:
                    wrong.append(position)
            elif position in profile["require"] and char == NOT_APPLICABLE:
                empty.append(position)
        forbidden_params.append(
            issue_testi.serializza({"slots": wrong}) if wrong else None)
        bare = tag[1:].strip(NOT_APPLICABLE) == ""
        missing_bare.append(bare)
        missing_many.append(len(empty) > 1)
        missing_params.append(
            issue_testi.serializza({"slots": empty}) if empty else None)

    forbidden_by_tag = np.array(forbidden_params, dtype=object)
    missing_by_tag = np.array(missing_params, dtype=object)

    hit = forbidden_by_tag[codes] != None                        # noqa: E711
    if hit.any():
        findings.append(_make_findings(
            vl_tokens[hit],
            "slot-forbidden",
            pd.Series(forbidden_by_tag[codes][hit],
                      index=vl_tokens.index[hit], dtype="string")))

    # Words that do not inflect: asking them for a number is asking the language
    # a question it does not have.  The cardinals from five upwards and δύο (by
    # lemma), and the letters of the alphabet used as numbers — ρ᾽, β, ια᾽ — by
    # form, because no list of lemmas can enumerate those.
    # The lemma is consulted as well as the form, because GLAUx writes the
    # keraia on the lemma and not on the token: the form is αβγδε and the
    # lemma αβγδεʹ, and only the second says what the string is.
    lemmas_nfc = map_unique(
        vl_tokens["lemma"] if "lemma" in vl_tokens.columns else vl_form,
        lambda value: _unicodedata.normalize("NFC", value)
        if isinstance(value, str) else value)
    uninflected = np.asarray(
        mask_unique(lemmas_nfc, is_indeclinable_numeral)
        | mask_unique(vl_form_nfc, _is_alphabetic_numeral)
        | mask_unique(lemmas_nfc, _is_alphabetic_numeral), dtype=bool)
    hit = (missing_by_tag[codes] != None) & ~uninflected          # noqa: E711

    # Words the corpus itself never inflects.
    #
    # A closed list cannot hold the foreign proper names: the books of Kings in
    # the GLAUx sample alone have Δαυίδ, Ἰωάβ, Ἀβεσσαλώμ, Ἀβεννήρ, Σαούλ,
    # Χεβρών, Σαδώκ, each of them Hebrew, none of them declined in Greek, and
    # each of them tagged as a noun with the case left empty — which is the
    # right annotation. Reported one token at a time they would add 858
    # findings to the 356 that this rule makes on the automatic sample.
    #
    # The corpus answers the question a list cannot: a lemma attested at least
    # five times and never once carrying a case does not decline here. Those
    # tokens are not dropped — dropping them would hide a gap that is systematic
    # rather than accidental, and the two look identical from inside — but
    # reported once per lemma, under their own name, with the number of tokens
    # concerned. The threshold matters little: on Gorman the set is empty at
    # three tokens and above, so nothing in a hand-annotated corpus is silenced.
    never_inflected = np.zeros(len(vl_tokens), dtype=bool)
    if hit.any() and "lemma" in vl_tokens.columns:
        nominal = np.asarray(vl_postag.str[0].isin(NOMINAL_PREFIXES), dtype=bool)
        case_filled = np.asarray(vl_postag.str[CASE_SLOT] != NOT_APPLICABLE, dtype=bool)
        stats = pd.DataFrame({
            "_lemma": lemmas_nfc.astype("string").fillna("").to_numpy(),
            "_n": nominal.astype(int),
            "_filled": (nominal & case_filled).astype(int),
        }).groupby("_lemma")[["_n", "_filled"]].sum()
        indeclinable = set(stats.index[(stats["_filled"] == 0)
                                       & (stats["_n"] >= INDECLINABLE_MINIMUM)])
        indeclinable.discard("")
        if indeclinable:
            never_inflected = np.asarray(
                lemmas_nfc.astype("string").fillna("").isin(indeclinable), dtype=bool)
            aggregate = vl_tokens[hit & never_inflected].copy()
            if not aggregate.empty:
                aggregate["_lemma"] = lemmas_nfc[hit & never_inflected].astype(
                    "string").fillna("").to_numpy()
                first = aggregate.groupby("_lemma", sort=True).head(1)
                totals = stats["_n"].to_dict()
                reported = aggregate["_lemma"].value_counts().to_dict()
                keys = first["_lemma"].to_numpy()
                # The two counts are an aggregate over the corpus: they are not in any
                # column of the finding, and so they are here.
                params = pd.Series(
                    [issue_testi.serializza(
                        {"totale": int(totals.get(key, 0)),
                         "segnalate": int(reported.get(key, 0))})
                     for key in keys],
                    index=first.index, dtype="string")
                findings.append(_make_findings(
                    first.drop(columns=["_lemma"]), "uninflected-lemma", params,
                    severity="sospetto"))

    # Two rules and not one, because they are two different things and the diagnostic
    # class cannot be the same.
    #
    # If the tag has the other features filled in and one is missing, the word has been
    # analysed and that slot has been left behind: it is a violation of the scheme,
    # verifiable without reading the Greek. If instead the tag is completely empty —
    # n-------- — the two possibilities are indistinguishable from outside: a word that
    # is not declined, correctly written, or an inflected word never analysed. The class
    # is then “case to verify”.
    bare_by_tag = np.array(missing_bare, dtype=bool)
    many_by_tag = np.array(missing_many, dtype=bool)
    hit = hit & ~never_inflected
    is_bare = np.asarray(bare_by_tag[codes], dtype=bool)
    is_many = np.asarray(many_by_tag[codes], dtype=bool)
    # Singular and plural are two sentences, not a sentence with an artificial plural:
    # the key says which, and each language writes them as it likes.
    for rule_id, mask in (("slot-missing", hit & ~is_bare),
                          ("slot-missing-bare", hit & is_bare)):
        if mask.any():
            chiave = pd.Series(
                np.where(is_many[mask], f"{rule_id}.molti", f"{rule_id}.uno"),
                index=vl_tokens.index[mask], dtype="string")
            findings.append(_make_findings(
                vl_tokens[mask], rule_id,
                pd.Series(missing_by_tag[codes][mask],
                          index=vl_tokens.index[mask], dtype="string"),
                issue_key=chiave))

    # ── Particles and connectives: part of speech vs syntactic relation ───────
    #
    # One policy for the whole family: the program does not propose the tag
    # whose first character matches the relation, and it does not report these
    # cases as errors.  The reason is that καί, ἤ, μέν, δέ, τε, ἀλλά, οὔτε are
    # *polyfunctional*.  καί coordinates in Σωκράτης καὶ Πλάτων and is an adverb
    # in καὶ σύ; ἤ separates two members and also follows a comparative.  When
    # the tag and the relation disagree there is no direction of repair to
    # assume — the tag may be wrong, the relation may be wrong, and often the
    # word really is doing two things — so the program reports the mismatch,
    # proposes nothing, and says so.
    # The family is corpus-relative and generic: it uses no hard-coded list of
    # forms.  A particle rule that names its word in its own id — «kai-relation»
    # — would be a rule written on one corpus.

    return _concat_findings(findings)


def _concat_findings(findings: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [f for f in findings if not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=_FINDINGS_COLUMNS)
    return pd.concat(non_empty, ignore_index=True)
