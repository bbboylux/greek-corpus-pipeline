"""The AGDT annotation scheme, declared as data rather than hard-coded logic.

Everything the diagnostic engines need to know about the Ancient Greek
Dependency Treebank scheme lives here: the nine positional slots of the
morphological tag, the value inventory of each slot, the syntactic relation
set, and the human-readable (Italian / English) label of every single value.

Keeping the scheme in one declarative place has three consequences that matter
for the rest of the program:

1. a user can *read* what the validator validates against, and disagree with it;
2. adding a value (say, a corpus that marks the dual with ``2``) is a one-line
   edit, not a code change;
3. the interface can render ``a-s---mn-`` as "adjective, singular, masculine,
   nominative" without any tab knowing how the tag is built.

Reference: Celano (2014), *Guidelines for the Annotation of the Ancient Greek
Dependency Treebank 2.0*, § 2 "Morphological layer"; Bamman & Crane (2008).
"""
from __future__ import annotations

from . import resources

import unicodedata

from typing import Iterable

# ---------------------------------------------------------------------------
# The nine positions
# ---------------------------------------------------------------------------

#: 0-based index -> (italian name, english name)
POSITION_NAMES: dict[int, tuple[str, str]] = {
    0: ("Parte del discorso", "Part of speech"),
    1: ("Persona", "Person"),
    2: ("Numero", "Number"),
    3: ("Tempo", "Tense"),
    4: ("Modo", "Mood"),
    5: ("Diatesi", "Voice"),
    6: ("Genere", "Gender"),
    7: ("Caso", "Case"),
    8: ("Grado", "Degree"),
}

TAG_LENGTH = 9
NOT_APPLICABLE = "-"


#: 0-based position -> {character: (italian label, english label)}
#: The dash is documented once here and implied everywhere else.
POSITION_VALUES: dict[int, dict[str, tuple[str, str]]] = {
    0: {
        "n": ("sostantivo", "noun"),
        "v": ("verbo", "verb"),
        "a": ("aggettivo", "adjective"),
        "d": ("avverbio", "adverb"),
        "l": ("articolo", "article"),
        "g": ("particella", "particle"),
        "c": ("congiunzione", "conjunction"),
        "r": ("preposizione", "preposition"),
        "p": ("pronome", "pronoun"),
        "m": ("numerale", "numeral"),
        "i": ("interiezione", "interjection"),
        "u": ("punteggiatura", "punctuation"),
        "x": ("nodo ellittico / non assegnato", "elliptic node / unassigned"),
        "-": ("non applicabile", "not applicable"),
    },
    1: {
        "1": ("prima persona", "first person"),
        "2": ("seconda persona", "second person"),
        "3": ("terza persona", "third person"),
        "-": ("non applicabile", "not applicable"),
    },
    2: {
        "s": ("singolare", "singular"),
        "p": ("plurale", "plural"),
        "d": ("duale", "dual"),
        "-": ("non applicabile", "not applicable"),
    },
    3: {
        "p": ("presente", "present"),
        "i": ("imperfetto", "imperfect"),
        "r": ("perfetto", "perfect"),
        "l": ("piuccheperfetto", "pluperfect"),
        "t": ("futuro anteriore", "future perfect"),
        "f": ("futuro", "future"),
        "a": ("aoristo", "aorist"),
        "-": ("non applicabile", "not applicable"),
    },
    4: {
        "i": ("indicativo", "indicative"),
        "s": ("congiuntivo", "subjunctive"),
        "o": ("ottativo", "optative"),
        "n": ("infinito", "infinitive"),
        "m": ("imperativo", "imperative"),
        "p": ("participio", "participle"),
        "-": ("non applicabile", "not applicable"),
    },
    5: {
        "a": ("attivo", "active"),
        "p": ("passivo", "passive"),
        "m": ("medio", "middle"),
        "e": ("medio-passivo", "medio-passive"),
        "-": ("non applicabile", "not applicable"),
    },
    6: {
        "m": ("maschile", "masculine"),
        "f": ("femminile", "feminine"),
        "n": ("neutro", "neuter"),
        # 'c' (common gender) is absent from the published guidelines, which
        # list only m, f and n.  It is kept here so that a tag carrying it can
        # still be read out loud -- Pedalion uses it 8,256 times and GLAUx
        # 11,034 (in the active records), on genderless pronouns and on epicene
        # nouns, while Gorman never does.  Being readable is not being
        # conformant: the departure is reported by ``common-gender-c``, which
        # proposes nothing.
        "c": ("comune", "common"),
        "-": ("non applicabile", "not applicable"),
    },
    7: {
        "n": ("nominativo", "nominative"),
        "g": ("genitivo", "genitive"),
        "d": ("dativo", "dative"),
        "a": ("accusativo", "accusative"),
        "v": ("vocativo", "vocative"),
        "l": ("locativo", "locative"),
        "-": ("non applicabile", "not applicable"),
    },
    8: {
        "c": ("comparativo", "comparative"),
        "s": ("superlativo", "superlative"),
        "-": ("non applicabile / grado positivo", "not applicable / positive"),
    },
}


def valid_characters(position: int) -> set[str]:
    """The set of characters admitted at *position* (0-based)."""
    return set(POSITION_VALUES.get(position, {}))


#: Backwards-compatible view used by postag.py
VALID_CHARACTERS: dict[int, set[str]] = {
    index: valid_characters(index) for index in POSITION_VALUES
}


def describe_value(position: int, char: str, lang: str = "it") -> str:
    """Human label for one character in one slot ('a' at slot 0 -> 'aggettivo')."""
    entry = POSITION_VALUES.get(position, {}).get(char)
    if entry is None:
        # An unlisted character is itself a finding; render it so it reads as
        # one instead of as a mysterious glyph in the middle of a table.
        shown = char if char and char.strip() else "vuoto"
        return (f"valore non previsto ({shown})" if lang == "it"
                else f"value not in the scheme ({shown})")
    return entry[0] if lang == "it" else entry[1]


def describe_postag(postag: object, lang: str = "it") -> str:
    """Render a 9-character tag as a readable gloss.

    ``a-s---mn-`` -> "aggettivo · singolare · maschile · nominativo".
    Slots holding ``-`` are omitted, because "not applicable" nine times is
    noise, not information.  Malformed tags are returned as-is with a marker.
    """
    if not isinstance(postag, str) or not postag.strip():
        return "—"
    tag = postag.strip()
    if len(tag) != TAG_LENGTH:
        suffix = " (lunghezza anomala)" if lang == "it" else " (bad length)"
        return tag + suffix
    parts: list[str] = []
    for index, char in enumerate(tag):
        if char == NOT_APPLICABLE:
            continue
        parts.append(describe_value(index, char, lang))
    return " · ".join(parts) if parts else tag


# ---------------------------------------------------------------------------
# Syntactic relations
# ---------------------------------------------------------------------------

#: relation -> (italian gloss, english gloss)
RELATIONS: dict[str, tuple[str, str]] = {
    "PRED":  ("predicato", "predicate"),
    "SBJ":   ("soggetto", "subject"),
    "OBJ":   ("oggetto / complemento retto", "object"),
    "ATR":   ("attributo", "attribute"),
    "ADV":   ("avverbiale", "adverbial"),
    "PNOM":  ("nome del predicato", "predicate nominal"),
    "OCOMP": ("complemento dell'oggetto", "object complement"),
    "ATV":   ("participio predicativo (concordato)", "predicative participle"),
    "AtvV":  ("participio predicativo (col verbo)", "predicative participle (verbal)"),
    "COORD": ("coordinante", "coordinator"),
    "APOS":  ("apposizione (nodo)", "apposition node"),
    "ExD":   ("dipendente da testa elisa", "externally dependent"),
    # Documented in the AGDT 2.0 guidelines and used 121 times in Pedalion.
    # Its absence here made every one of those a "relation outside the
    # inventory": a false positive against a label the scheme defines.
    "MWE":   ("espressione polirematica", "multi-word expression"),
    "AuxP":  ("preposizione", "preposition"),
    "AuxC":  ("congiunzione subordinante", "subordinating conjunction"),
    "AuxR":  ("riflessivo passivo", "reflexive passive"),
    "AuxV":  ("verbo ausiliare", "auxiliary verb"),
    "AuxX":  ("virgola", "comma"),
    "AuxG":  ("punteggiatura interna", "bracketing punctuation"),
    "AuxK":  ("punteggiatura finale", "terminal punctuation"),
    "AuxY":  ("avverbio/particella di frase", "sentence adverbial / particle"),
    "AuxZ":  ("particella enfatica", "emphasising particle"),
    "UNDEFINED": ("non definita", "undefined"),
}

#: Suffixes AGDT attaches to a base relation inside coordination / apposition.
#: They stack: ``ADV_AP_CO`` and ``SBJ_CO_CO_CO`` both occur in Gorman.
RELATION_SUFFIXES = ("_CO", "_AP")

#: The ``_ExD<n>_`` infix marks a node standing in for an elided head, and the
#: label after it names the function of the missing element.  Prague-school
#: notation inherited by AGDT: ``SBJ_ExD0_ADV`` is a subject whose (elided)
#: head would have been an adverbial.  The infix has to be stripped before any
#: comparison, or every elliptic construction manufactures its own label.
_EXD_INFIX_RE = __import__("re").compile(r"_ExD\d*_.*$")

#: Relations attached to punctuation tokens.
PUNCTUATION_RELATIONS = {"AuxK", "AuxX", "AuxG"}

#: Auxiliary relations that normally label leaves (they govern nothing).
#:
#: Kept as a description of the *usual* shape, not as a constraint: the AGDT
#: and PDT guidelines nowhere require AuxY and AuxZ to be childless, and
#: particle chains (οὐ μόνον, οὐ μὴν ἀλλά, τοῦτο μέν) have internal structure
#: by design.  Measured on Gorman: of the 1,636 tokens with one of these labels
#: and at least one child, most are particle chains and 286 (17%) are
#: parenthetical finite verbs — only 42 (2.6%) govern conjuncts, a coordinator
#: wearing the wrong label.  See ``syntax.check_auxiliaries``, which reports
#: those two groups and not the shape.
LEAF_RELATIONS = {"AuxK", "AuxX", "AuxG", "AuxY", "AuxZ"}

#: Pairs whose confusion the AGDT guidelines explicitly leave to the annotator.
#: Flagging them as errors would be a category mistake (cf. Boyd et al. 2008, preprint: 20;
#: Keersmaekers et al. 2019: 4 on the "often fluid" argument/adjunct line).
LEGITIMATE_VARIATION: tuple[frozenset[str], ...] = (
    frozenset({"ADV", "ATR"}),
    frozenset({"OBJ", "ADV"}),
    frozenset({"AuxY", "AuxZ"}),
    frozenset({"ATV", "AtvV"}),
)


# ---------------------------------------------------------------------------
# Elliptic (artificial) nodes
# ---------------------------------------------------------------------------
# Both corpora supply the words an author left out as extra ``<word>`` elements
# carrying ``artificial="elliptic"``, and both park them *after* the terminal
# punctuation of the sentence: the node is part of the tree but has no place in
# the text.  Read naively, that convention looks like three defects — the
# placeholder sits far from its head (a "non-projective outlier"), it comes
# after the full stop (an "AuxK not final"), and the accent it inherited from
# its original context has no enclitic after it (a "double accent").
#
# The attribute itself is not in every token table (a CoNLL import or a gold
# file has no ``artificial`` column), so the convention is recognised from the
# shape of the sentence, and the column is used when it happens to be there.
# Measured against the attribute on the 23 available Gorman files and the whole
# of Pedalion: recall 0.987 / 0.999, precision 0.999 / 0.992.

#: Form of a node standing in for an elided word: ``[0]`` … ``[20]``.
ELLIPTIC_PLACEHOLDER_RE = __import__("re").compile(r"^\[(?:[0-9]|1[0-9]|20)\]$")


def elliptic_token_mask(
    tokens,
    sentence_codes=None,
    positions=None,
):
    """Which tokens are elided-word placeholders parked outside the text.

    Returns a plain numpy boolean array aligned with *tokens*.  A token counts
    as elliptic when the file says so (``artificial``), when its form is a
    ``[n]`` placeholder, or when it sits after the last ``AuxK`` of its
    sentence.  *sentence_codes* and *positions* may be passed in when the
    caller has already built them, which every caller in the package has.
    """
    import numpy as np
    import pandas as pd

    total = len(tokens)
    if total == 0:
        return np.zeros(0, dtype=bool)

    mask = np.zeros(total, dtype=bool)

    if "artificial" in getattr(tokens, "columns", ()):
        declared = tokens["artificial"].astype("string").fillna("")
        mask |= np.asarray(declared.str.strip() != "", dtype=bool)

    if "form" in getattr(tokens, "columns", ()):
        forms = tokens["form"].astype("string").fillna("")
        mask |= np.asarray(
            forms.str.match(ELLIPTIC_PLACEHOLDER_RE).fillna(False), dtype=bool)

    columns = set(getattr(tokens, "columns", ()))
    if "relation" not in columns:
        return mask
    if sentence_codes is None and "sentence_index" not in columns:
        return mask
    if positions is None and "token_index" not in columns:
        return mask

    if sentence_codes is None:
        # Numbered rather than spelled out: pasting three string columns
        # together and factorising the result costs 0.25 s on 625,176 rows,
        # against 0.04 s for the same identity built out of integer codes.
        combined = pd.to_numeric(
            tokens["sentence_index"], errors="coerce").fillna(-1).to_numpy().astype("int64")
        for column in ("source_file", "document_id"):
            if column in tokens.columns:
                codes = pd.factorize(tokens[column], sort=False)[0].astype("int64")
                combined = combined * (int(codes.max()) + 2) + codes
        sentence_codes = pd.factorize(combined, sort=False)[0]
    sentence_codes = np.asarray(sentence_codes)
    if positions is None:
        positions = pd.to_numeric(tokens["token_index"], errors="coerce").to_numpy()
    positions = np.asarray(positions, dtype="float64")

    terminal = np.asarray(
        tokens["relation"].astype("string").fillna("") == "AuxK", dtype=bool)
    if not terminal.any():
        return mask
    width = int(sentence_codes.max()) + 1 if len(sentence_codes) else 0
    last_stop = np.full(width, -1.0, dtype="float64")
    np.maximum.at(last_stop, sentence_codes[terminal], positions[terminal])
    reference = last_stop[sentence_codes]
    return mask | ((reference > 0) & (positions > reference))


# ---------------------------------------------------------------------------
# Indeclinable cardinals
# ---------------------------------------------------------------------------
# The cardinals from five upwards do not inflect, and neither do the compounds
# built on them; δύο keeps one form in Attic prose outside the (rare) δυοῖν.
# A tag that leaves their number and case slots empty is therefore *correct*,
# and the intra-tag check must not ask for a value the language does not have.
# Measured: these lemmas account for 460 of the 810 intra-tag findings in Gorman
# and 432 of the 783 in Pedalion — δύο 82/73, εἴκοσι 49/29, πεντήκοντα 35/21,
# δέκα 34/40, τριάκοντα 34/38, ἑκατόν 33/36 and so on.
#
# The list is closed and only holds forms that never inflect.  εἷς, τρεῖς,
# τέτταρες, the hundreds (διακόσιοι …), χίλιοι and μύριοι are deliberately left
# out: they *do* decline, so a missing case on them is a real gap.  Both the
# Attic and the Ionic spellings are listed, because the Gorman corpus contains
# Herodotus (δυώδεκα, τεσσεράκοντα) beside the Attic orators.
INDECLINABLE_NUMERAL_LEMMAS = resources.entries("numerali-indeclinabili")

# ---------------------------------------------------------------------------
# Quantifiers and distributives used on their own
# ---------------------------------------------------------------------------
# These words are attributive often enough, and then they agree.  But Greek
# also uses them *substantivally* and *appositionally*, and there they do not:
#
#   ἑνὶ … ὄνομα         — "to one [deed] the name …": εἷς stands on its own
#                          with an elided noun, and the annotator, having no
#                          elliptic node to hand, attached it to ὄνομα.
#   καθ' ἕκαστον        — distributive, adverbial: the attribute of nothing.
#   ἄμφω … τὰ ἔθνη      — partitive apposition, and a dual beside a plural.
#
# In every one of those the tree says ATR and the morphology says otherwise,
# and the morphology is right.  Since the same lemma alternates freely between
# the two uses inside a single author, no tree-shaped test separates them, and
# the honest thing is to leave the lemma out of the agreement check rather than
# to report a construction of the language as an error of the corpus.
NON_AGREEING_QUANTIFIER_LEMMAS = resources.entries("quantificatori-non-concordanti")

#: Grave accents are a positional variant of the acute: the same word is
#: written ἑπτά in isolation and ἑπτὰ before another word, and treebank lemma
#: fields record whichever the text had.  Comparing lemmas without normalising
#: this would make ἓξ, ἑπτὰ and ἑκατὸν miss the indeclinable-numeral list they
#: belong to.
_GRAVE_TO_ACUTE = str.maketrans({
    "ὰ": "ά", "ὲ": "έ", "ὴ": "ή", "ὶ": "ί", "ὸ": "ό", "ὺ": "ύ", "ὼ": "ώ",
    "ἃ": "ἅ", "ἓ": "ἕ", "ἣ": "ἥ", "ἳ": "ἵ", "ὃ": "ὅ", "ὓ": "ὕ", "ὣ": "ὥ",
    "ἂ": "ἄ", "ἒ": "ἔ", "ἢ": "ἤ", "ἲ": "ἴ", "ὂ": "ὄ", "ὒ": "ὔ", "ὢ": "ὤ",
    "Ἃ": "Ἅ", "Ἓ": "Ἕ", "Ἣ": "Ἥ", "Ἳ": "Ἵ", "Ὃ": "Ὅ", "Ὣ": "Ὥ",
    "Ἂ": "Ἄ", "Ἒ": "Ἔ", "Ἢ": "Ἤ", "Ἲ": "Ἴ", "Ὂ": "Ὄ", "Ὢ": "Ὤ",
})


def normalize_lemma_accent(lemma: object) -> str:
    """A lemma with its grave accents written as acutes, for set membership.

    Also normalised to NFC, for a reason that has cost hundreds of false positives. The
    closed lists of this module — the indeclinable numerals, the quantifiers that do not
    agree — are written in NFC, as Gorman and Pedalion are written. GLAUx is written in
    NFD: every accent is a character of its own. The two strings look identical on
    screen and are not equal under any comparison, so on an NFD corpus none of these
    lists recognised anything: ὀκτώ was not found to be an indeclinable numeral and was
    reported because “the gender is missing”, which an indeclinable Greek numeral does
    not lack — it does not have one.
    """
    if not isinstance(lemma, str):
        return ""
    return unicodedata.normalize("NFC", lemma.strip()).translate(_GRAVE_TO_ACUTE)


def is_indeclinable_numeral(lemma: object) -> bool:
    """Is this an indeclinable cardinal, however its accent happens to be written?"""
    return normalize_lemma_accent(lemma) in INDECLINABLE_NUMERAL_LEMMAS


def is_non_agreeing_quantifier(lemma: object) -> bool:
    """A quantifier or distributive Greek regularly uses without agreement."""
    return normalize_lemma_accent(lemma) in NON_AGREEING_QUANTIFIER_LEMMAS


def base_relation(relation: object) -> str:
    """Reduce a decorated AGDT label to its bare syntactic function.

    ``OBJ_CO`` → ``OBJ``, ``ADV_AP_CO`` → ``ADV``, ``SBJ_ExD0_ADV`` → ``SBJ``.
    Without this the same function shows up under a dozen spellings and every
    comparison — variation nuclei, agreement, statistics — silently fragments.
    """
    if not isinstance(relation, str):
        return ""
    value = _EXD_INFIX_RE.sub("", relation.strip())
    changed = True
    while changed:
        changed = False
        for suffix in RELATION_SUFFIXES:
            if value.endswith(suffix):
                value = value[: -len(suffix)]
                changed = True
    return value


# ---------------------------------------------------------------------------
# Damaged relation labels
# ---------------------------------------------------------------------------
# A label that is not in the inventory can be damaged in four ways that have
# nothing in common but the symptom.  They are kept apart here, because the
# repair differs: two of them have exactly one possible intended value, and two
# have none that can be read off the string.

#: Greek capitals pixel-identical to the Latin letters the scheme uses.  A label
#: typed with the keyboard left in Greek looks correct on screen and is a
#: brand-new label to every program: Gorman has ``AuxΖ`` (zeta, U+0396) eight
#: times and ``AuxΚ`` (kappa, U+039A) twice.
GREEK_LOOKALIKES: dict[str, str] = {
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K",
    "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
    "ο": "o", "ν": "v", "ρ": "p",
}

#: Misspellings with one possible target: a wrong letter (``AucZ`` for AuxZ, the
#: only one attested), a doubled one, or the right label in the wrong case.  The
#: label stays identifiable, so the repair can be proposed.
RELATION_TYPOS: dict[str, str] = {
    "AucZ": "AuxZ", "AucY": "AuxY", "AuxZZ": "AuxZ",
    "Coord": "COORD", "coord": "COORD",
    "Pred": "PRED", "Sbj": "SBJ", "Obj": "OBJ", "Atr": "ATR", "Adv": "ADV",
}

#: Labels that are not AGDT and whose intended value cannot be read off the
#: string.  They are not rewritten silently — ``CO``→COORD, ``Aux``→AuxY —
#: because the trees show that such a rewriting would be wrong.  Of the eleven
#: Gorman tokens labelled ``CO``, exactly one governs ``_CO`` conjuncts: for the
#: other ten (Μελιτέα, ἀστῆς, γένος …) ``CO`` is a conjunct's suffix that lost
#: its function, so the missing part is SBJ/OBJ/ADV, not COORD.  Conversely
#: seven of the eight labelled ``Aux`` (καί, δέ, ἀλλ᾽) do govern ``_CO``
#: conjuncts, so they are COORD and not AuxY; the eighth is an open bracket,
#: i.e. AuxG.  Reported, never repaired.
UNRECOVERABLE_RELATIONS: frozenset[str] = frozenset({"CO", "CONJ", "Aux"})

#: Explicit "nothing here" markers: the field is filled, but what it holds is
#: the statement that no analysis was made (Gorman writes ``nil`` on three
#: section letters α/β with an empty tag).  Pedalion writes ``_`` once for the
#: same purpose; that one is a CoNLL convention and is left to relation-unknown,
#: one token being too thin a basis to widen the rule.
NIL_RELATIONS: frozenset[str] = frozenset({"nil", "NIL"})

#: The four kinds of damage, one rule each in the catalogue.
DAMAGE_GREEK_LOOKALIKE = "greek-lookalike"
DAMAGE_TYPO = "typo"
DAMAGE_TRUNCATED_OR_FOREIGN = "truncated-or-foreign"
DAMAGE_NIL_PLACEHOLDER = "nil-placeholder"


def fold_greek_lookalikes(relation: object) -> str:
    """Replace every Greek character of *relation* with the Latin twin."""
    if not isinstance(relation, str):
        return ""
    return "".join(GREEK_LOOKALIKES.get(char, char) for char in relation.strip())


def greek_lookalike_pairs(relation: object) -> list[tuple[str, str]]:
    """The ``(greek, latin)`` character pairs that make a label look right.

    Returned as data rather than as a sentence, so that the diagnostic modules
    can spell out the codepoints in their own words: on screen the two
    characters are the same picture, and a message that does not name them
    leaves the reader staring at a label that looks perfectly correct.
    """
    if not isinstance(relation, str):
        return []
    seen: list[tuple[str, str]] = []
    for char in relation.strip():
        latin = GREEK_LOOKALIKES.get(char)
        if latin is not None and (char, latin) not in seen:
            seen.append((char, latin))
    return seen


def normalize_relation_text(relation: object) -> str:
    """Repair the mechanical damage a relation label can suffer.

    Two things happen to these labels in real corpora: Greek capitals
    substituted for Latin ones (``AuxΖ`` with a zeta, ``AuxΚ`` with a kappa) and
    typing slips (``AucZ``).  Both leave exactly one possible intended value, so
    this maps the label onto it.  Anything else — a bare ``CO``, a truncated
    ``Aux``, a ``nil`` placeholder, a label from another scheme — comes back
    unchanged: see :data:`UNRECOVERABLE_RELATIONS` for why guessing there does
    more harm than good.
    """
    folded = fold_greek_lookalikes(relation)
    return RELATION_TYPOS.get(folded, folded)


def classify_relation_damage(relation: object) -> str:
    """Which of the four kinds of damage a label has suffered (``""`` if none).

    The four answers are mutually exclusive and cover, between them, exactly the
    labels that a single ``relation-damaged`` rule would report.
    """
    if not isinstance(relation, str):
        return ""
    value = relation.strip()
    folded = fold_greek_lookalikes(value)
    # The explicit lists come first: a label spelled with a Greek letter *and*
    # listed as unrecoverable stays unrecoverable, because folding the letter
    # back does not tell us which relation was meant.
    if folded in NIL_RELATIONS:
        return DAMAGE_NIL_PLACEHOLDER
    if folded in UNRECOVERABLE_RELATIONS:
        return DAMAGE_TRUNCATED_OR_FOREIGN
    if folded in RELATION_TYPOS:
        return DAMAGE_TYPO
    if folded != value and is_known_relation(folded):
        return DAMAGE_GREEK_LOOKALIKE
    return ""


def describe_relation(relation: object, lang: str = "it") -> str:
    base = base_relation(relation)
    entry = RELATIONS.get(base)
    if entry is None:
        return str(relation) if relation is not None else "—"
    gloss = entry[0] if lang == "it" else entry[1]
    if isinstance(relation, str) and relation.endswith("_CO"):
        gloss += " (coordinato)" if lang == "it" else " (coordinated)"
    elif isinstance(relation, str) and relation.endswith("_AP"):
        gloss += " (apposto)" if lang == "it" else " (apposed)"
    return gloss


VALID_RELATIONS: set[str] = set(RELATIONS)


def is_known_relation(relation: object) -> bool:
    return base_relation(relation) in VALID_RELATIONS


# ---------------------------------------------------------------------------
# Intra-tag consistency constraints
# ---------------------------------------------------------------------------
# Each constraint states, for one part of speech, which slots MUST carry a
# value and which MUST be empty.  These are hard grammatical facts about the
# scheme, not statistics: a finite verb cannot have a case, a noun cannot have
# a tense.  Violations are always real errors.

#: pos char -> {"require": (slot, ...), "forbid": (slot, ...), "label": (it, en)}
INTRA_TAG_CONSTRAINTS: list[dict[str, object]] = [
    {
        "id": "finite-verb-shape",
        "pos": "v",
        "when_mood": set("isom"),
        "require": (1, 2, 3, 4, 5),
        "forbid": (6, 7, 8),
        "label": ("Verbo finito con genere/caso valorizzati",
                  "Finite verb carrying gender or case"),
    },
    {
        "id": "infinitive-shape",
        "pos": "v",
        "when_mood": {"n"},
        "require": (3, 4, 5),
        "forbid": (1, 2, 6, 7, 8),
        "label": ("Infinito con persona, numero, genere o caso",
                  "Infinitive carrying person, number, gender or case"),
    },
    {
        "id": "participle-shape",
        "pos": "v",
        "when_mood": {"p"},
        "require": (2, 3, 4, 5, 6, 7),
        "forbid": (1,),
        "label": ("Participio senza caso/genere, o con persona",
                  "Participle lacking case/gender, or carrying person"),
    },
    {
        # Pronouns are deliberately absent from this constraint: a personal
        # pronoun legitimately carries a person (p1s---mn- is ἐγώ, correctly
        # tagged), and forbidding the slot here would contradict the rule that
        # fills it in elsewhere.
        "id": "nominal-shape",
        "pos": set("nalm"),
        "require": (2, 7),
        "forbid": (1, 3, 4, 5),
        "label": ("Nominale con tratti verbali o senza caso/numero",
                  "Nominal with verbal features or missing case/number"),
    },
    {
        "id": "pronoun-shape",
        "pos": "p",
        "require": (2, 7),
        "forbid": (3, 4, 5),
        "label": ("Pronome con tratti verbali o senza caso/numero",
                  "Pronoun with verbal features or missing case/number"),
    },
    {
        "id": "indeclinable-shape",
        "pos": set("drcigu"),
        "require": (),
        "forbid": (1, 2, 3, 4, 5, 6, 7),
        "label": ("Indeclinabile con tratti flessivi",
                  "Indeclinable carrying inflectional features"),
    },
    {
        "id": "degree-shape",
        "pos": set("nvplmrcigu"),
        "require": (),
        "forbid": (8,),
        "label": ("Grado marcato su una categoria che non lo ammette",
                  "Degree marked on a category that cannot take it"),
    },
]


# ---------------------------------------------------------------------------
# Convenience accessors used across the analysis modules
# ---------------------------------------------------------------------------

POS_SLOT, PERSON_SLOT, NUMBER_SLOT, TENSE_SLOT = 0, 1, 2, 3
MOOD_SLOT, VOICE_SLOT, GENDER_SLOT, CASE_SLOT, DEGREE_SLOT = 4, 5, 6, 7, 8

# ---------------------------------------------------------------------------
# Which slots each part of speech fills
# ---------------------------------------------------------------------------
# The first character of the tag decides which of the other eight may, must and
# must not carry a value.  A noun has number, gender and case and nothing else;
# a finite verb has person, number, tense, mood and voice and cannot have a
# case; an adverb has nothing except, if it is compared, a degree.  This is the
# grammar of the *scheme*, and it is written here as a table rather than as
# code so that a reader can check it against the guidelines line by line and
# disagree with a single cell.
#
# Three categories, not two, and the third is what keeps the check honest:
#
#   require   the slot must carry a value; empty is a defect
#   optional  the slot may carry a value or not, and neither is a defect
#   (rest)    anything not listed is forbidden: a value there is impossible
#
# Every "optional" below is a fact about Greek that cost us a false positive
# when it was missing.  The degree of an adverb (ταχέως → ταχύτερον) is real
# inflection; the person of a pronoun is written on personal pronouns and left
# empty on the others, and a separate rule proposes it where the form settles
# it; the gender of a pronoun is genuinely absent from the interrogatives in
# both corpora; the number of an article is required but its gender is written
# by Gorman and sometimes not by Pedalion.
SLOT_PROFILE: dict[str, dict[str, frozenset[int]]] = {
    # ── nominals ─────────────────────────────────────────────────────────
    "n": {"require": frozenset({NUMBER_SLOT, GENDER_SLOT, CASE_SLOT}),
          "optional": frozenset()},
    "a": {"require": frozenset({NUMBER_SLOT, GENDER_SLOT, CASE_SLOT}),
          "optional": frozenset({DEGREE_SLOT})},
    # “The article is annotated for gender, number, and case” (AGDT 2.0). Gender is
    # required, and there is no reason for it to be optional: in the three corpora
    # examined the articles without gender are nine in all, all in Gorman.
    "l": {"require": frozenset({NUMBER_SLOT, GENDER_SLOT, CASE_SLOT}),
          "optional": frozenset()},
    # The numeral requires nothing, because the guidelines do not require anything of
    # it. For the noun they say that “in AG the noun/substantive (henceforth simply
    # "noun") is inflected and so annotated for gender, number, and case”; for the
    # numeral they say only that “the part of speech "numeral" is used for numeral
    # adjectives, nouns, and adverbs” (AGDT 2.0, § 2). Under a single letter there are
    # therefore three different things, and one of the three — the adverbial numeral,
    # δίς, τρίς — is not declined at all; to these are added the cardinals from five
    # upwards, which are indeclinable in Greek. Requiring number, gender and case of
    # every “m” would be a rule of our own presented as a rule of the scheme, and
    # exemptions by lemma and by form could not repair it: no list closes the set. The
    # numerals that are declined remain covered by the agreement checks, which look at
    # them in relation to their head instead of on their own.
    "m": {"require": frozenset(),
          "optional": frozenset({NUMBER_SLOT, GENDER_SLOT, CASE_SLOT,
                                 DEGREE_SLOT})},
    # “The pronoun is annotated for gender, number, and case” (AGDT 2.0): this is the
    # same sentence on which the catalogue argues that person is NOT prescribed for the
    # pronoun, and the same sentence prescribes gender. Keeping gender optional would be
    # inconsistent with that argument.
    "p": {"require": frozenset({NUMBER_SLOT, GENDER_SLOT, CASE_SLOT}),
          "optional": frozenset({PERSON_SLOT})},
    # ── indeclinables ────────────────────────────────────────────────────
    # The adverb keeps the degree slot: θᾶσσον and τάχιστα are inflected forms
    # of an adverb, and the scheme records them there.
    "d": {"require": frozenset(), "optional": frozenset({DEGREE_SLOT})},
    "g": {"require": frozenset(), "optional": frozenset()},
    "c": {"require": frozenset(), "optional": frozenset()},
    "r": {"require": frozenset(), "optional": frozenset()},
    "i": {"require": frozenset(), "optional": frozenset()},
    "u": {"require": frozenset(), "optional": frozenset()},
    # ── the elliptic placeholder ─────────────────────────────────────────
    # x marks a node the annotator supplied because the text has no word there.
    # Whatever it carries is a reconstruction, so nothing is required and
    # nothing is impossible.
    "x": {"require": frozenset(), "optional": frozenset(range(1, TAG_LENGTH))},
}

#: The verb is the one class whose profile depends on another slot: the mood
#: decides whether the form has a person or a case.  Keys are the characters of
#: the mood slot; ``None`` is the profile for a verb whose mood is not written.
VERB_SLOT_PROFILE: dict[object, dict[str, frozenset[int]]] = {
    # indicative, subjunctive, optative, imperative
    "i": {"require": frozenset({PERSON_SLOT, NUMBER_SLOT, TENSE_SLOT,
                                MOOD_SLOT, VOICE_SLOT}),
          "optional": frozenset()},
    # infinitive: no person, no number, no gender, no case
    "n": {"require": frozenset({TENSE_SLOT, MOOD_SLOT, VOICE_SLOT}),
          "optional": frozenset()},
    # participle: declined like an adjective, but never carries a person
    "p": {"require": frozenset({NUMBER_SLOT, TENSE_SLOT, MOOD_SLOT, VOICE_SLOT,
                                GENDER_SLOT, CASE_SLOT}),
          "optional": frozenset({DEGREE_SLOT})},
    # a verb whose mood slot is empty: we can require nothing, because we do not
    # know which of the three shapes above it should have.
    None: {"require": frozenset(), "optional": frozenset(range(1, TAG_LENGTH))},
}
for _mood in "som":                              # subjunctive, optative, imperative
    VERB_SLOT_PROFILE[_mood] = VERB_SLOT_PROFILE["i"]
VERB_SLOT_PROFILE["d"] = VERB_SLOT_PROFILE["p"]  # gerundive, where a corpus uses it


def slot_profile(postag: object) -> "dict[str, frozenset[int]] | None":
    """Which slots this tag's part of speech requires and allows.

    ``None`` when the first character is not a part of speech of the scheme —
    that is a different defect, reported by its own rule, and this check must
    not pile a second finding on top of it.
    """
    if not isinstance(postag, str) or len(postag) != TAG_LENGTH:
        return None
    part = postag[POS_SLOT]
    if part == "v":
        mood = postag[MOOD_SLOT]
        return VERB_SLOT_PROFILE.get(mood if mood != NOT_APPLICABLE else None,
                                     VERB_SLOT_PROFILE[None])
    return SLOT_PROFILE.get(part)

FINITE_MOODS = set("isom")
NOMINAL_POS = set("naplm")
CONTENT_POS = set("nvad")

#: The four aspectual stems, grouped from the tense slot.
ASPECT_GROUPS: dict[str, tuple[str, ...]] = {
    "presente": ("p", "i"),
    "aoristo": ("a",),
    "perfetto": ("r", "l", "t"),
    "futuro": ("f",),
}


def slot(postag: object, index: int) -> str:
    """Character at *index*, or ``''`` when the tag is unusable."""
    if isinstance(postag, str) and len(postag) == TAG_LENGTH:
        return postag[index]
    return ""


def slot_series(postags, index: int):
    """Vectorised :func:`slot` over a pandas Series (returns a string Series)."""
    import pandas as pd

    values = pd.Series(postags).astype("string")
    ok = values.str.len() == TAG_LENGTH
    out = values.str[index : index + 1]
    return out.where(ok, "")


def iter_positions() -> Iterable[tuple[int, str, str]]:
    """Yield ``(index, italian_name, english_name)`` for the nine slots."""
    for index, (it_name, en_name) in POSITION_NAMES.items():
        yield index, it_name, en_name
