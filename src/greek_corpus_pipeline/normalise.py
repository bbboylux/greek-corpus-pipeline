"""The normalisations, one function per purpose.

Normalising to search, normalising to count and modifying the corpus are
three different things, and this module exists so that they stop being done
by the same function.

The case that made it necessary is ``normalize_lemma``: it did three jobs in
one — NFC, cutting of the Perseus digits, map of canonical variants — and the
check that must *see* those digits, ``lemma-tool-numbering``, could not use
it. Whoever wanted NFC carried along the cutting of the digits; whoever wanted
the cutting of the digits carried along the map of variants. Changing one for
a caller changed it for all.

The second case is ``strip_diacritics``: key of the orthographic variation
nuclei, key of the buckets in a check on typos, and key of the search box at
every keystroke. Three purposes with three different requirements: search
wants to be generous — whoever writes ``anthropos`` must find ἄνθρωπος —
while grouping wants to be strict, because a generous key merges words that
are not the same.

**None of these functions modifies the corpus.** They return a comparison key;
the original form and lemma stay in the data as they are written in the file.
"""
from __future__ import annotations

import re
import unicodedata

from . import resources

__all__ = [
    "canonical_variant",
    "nfc",
    "search_key",
    "skeleton",
    "without_lemma_numbering",
    "LEMMA_VARIANTS",
]


# ---------------------------------------------------------------------------
# 1. NFC — Unicode identity, nothing else
# ---------------------------------------------------------------------------

def nfc(text: object) -> str:
    """The NFC-normalised form of a string.

    It serves one purpose only: to make two writings of the same string the same
    string. GLAUx writes 47,840 of its 48,513 distinct forms in NFD, Pedalion
    1,112 out of 45,445 — and in Pedalion 280 of those are duplicates that without
    NFC the program counts as two different forms.

    It cuts nothing and maps nothing. Whoever wants the cutting of the digits as
    well composes: ``without_lemma_numbering(nfc(value))``.
    """
    if not isinstance(text, str):
        return ""
    return unicodedata.normalize("NFC", text)


# ---------------------------------------------------------------------------
# 2. The numbering of lemmas
# ---------------------------------------------------------------------------

#: The digits that Perseus appends to the lemma to distinguish homographs: θεῖος1,
#: θεῖος2. The cutting is to be applied **only** where it is necessary to
#: recognise that θεῖος1 and θεῖος are the same base lemma — the comparison
#: between corpora, the statistics that aggregate by lemma — and **never** in
#: ``lemma-tool-numbering``, which exists to flag those digits and needs to see
#: them.
_TRAILING_DIGITS = re.compile(r"\d+$")


def without_lemma_numbering(lemma: object) -> str:
    """The lemma without the Perseus numbering of homographs.

    ``θεῖος1`` → ``θεῖος``. Gorman carries this numbering on 72,836 records and
    Pedalion on 311; it is a declared convention, not a defect, and the cutting
    serves to be able to count together records that the two corpora write
    differently.

    It is not applied automatically to all counts: a lemma that *ends* with a
    digit and is not numbered — a numeral written in digits, say — would be
    mutilated, and the count by lemma must be made on the lemma as it is in the
    file unless the contrary is declared.
    """
    if not isinstance(lemma, str) or not lemma:
        return ""
    stripped = _TRAILING_DIGITS.sub("", lemma)
    return stripped or lemma


# ---------------------------------------------------------------------------
# 3. The canonical variant
# ---------------------------------------------------------------------------

#: The spellings that the corpora use for the same lemma, and the form on which
#: they align when compared with each other.
#:
#: **It comes from the data resource, not from here.** An invented lexical list
#: inside a scientific module is exactly the defect that versioned resources
#: exist to make impossible. The real table is in
#: ``data/liste/varianti-canoniche-di-lemma.json``, comes from the survey of the
#: corpora, and can be inspected.
LEMMA_VARIANTS: dict[str, str] = dict(resources.entries("varianti-canoniche-di-lemma"))


def canonical_variant(lemma: object, *, table: dict[str, str] | None = None) -> str:
    """The canonical spelling of a lemma, when the corpora use more than one.

    It is applied after :func:`nfc` and after :func:`without_lemma_numbering`, and only
    where the comparison between resources requires it methodologically.
    """
    if not isinstance(lemma, str) or not lemma:
        return ""
    mapping = LEMMA_VARIANTS if table is None else table
    return mapping.get(lemma, lemma)


# ---------------------------------------------------------------------------
# 4. The graphic skeleton
# ---------------------------------------------------------------------------

#: The combining marks to remove in order to obtain the skeleton. Built once:
#: the function runs on every distinct form and lemma of the corpus, and a
#: C-level ``str.translate`` costs half of a comprehension that rebuilds a list
#: of characters and then joins it again.
_COMBINING = {code: None for code in range(0x0300, 0x0370)}
_COMBINING.update({code: None for code in range(0x1DC0, 0x1E00)})
_COMBINING.update({code: None for code in range(0x20D0, 0x2100)})


def skeleton(text: object) -> str:
    """Lower case, without diacritic marks, recomposed.

    This is the **grouping key**: two spellings of the same word collapse onto a
    single key and the set of spellings becomes the label whose variation is
    sought. Strict by construction — it does not transliterate, does not touch the
    final sigma, does not merge different vowels — because a generous key merges
    words that are not the same and the variation nucleus becomes false.

    For searching the opposite is needed: :func:`search_key`.
    """
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return unicodedata.normalize("NFC", decomposed.translate(_COMBINING))


# ---------------------------------------------------------------------------
# 5. The search key
# ---------------------------------------------------------------------------

#: The Latin transliteration, for whoever types from a keyboard without Greek.
#: The digraphs must be resolved before the single letters, otherwise “th”
#: becomes “tη” instead of “θ”.
#:
#: An isolated ``h`` is not a letter: it is the rough breathing, and
#: :func:`skeleton` has already removed it from the Greek side, so it must be
#: removed here too. Mapping it to η — as some keyboard conventions do — would
#: break ὁδός: “hodos” would become ηοδοσ against οδοσ.
_TRANSLITERATION: tuple[tuple[str, str], ...] = (
    ("th", "θ"), ("ph", "φ"), ("ch", "χ"), ("ps", "ψ"),
    ("ks", "ξ"), ("rh", "ρ"),
    ("a", "α"), ("b", "β"), ("g", "γ"), ("d", "δ"), ("e", "ε"),
    ("z", "ζ"), ("h", ""), ("i", "ι"), ("k", "κ"), ("l", "λ"),
    ("m", "μ"), ("n", "ν"), ("x", "ξ"), ("o", "ο"), ("p", "π"),
    ("r", "ρ"), ("s", "σ"), ("t", "τ"), ("u", "υ"), ("y", "υ"),
    ("f", "φ"), ("w", "ω"), ("c", "κ"), ("v", "β"), ("q", "κ"),
    ("j", "ι"),
)

#: The equivalences that the search absorbs and the grouping does not.
#:
#: The two lines that matter are η→ε and ω→ο, and they are the price of
#: transliteration: the Latin alphabet does not distinguish the long vowel from
#: the short, so whoever writes “anthropos” cannot say whether they mean ο or
#: ω. For the three search modes to find the same word, the distinction must be
#: dissolved **on both sides**, Greek included. The cost is that whoever searches
#: for ὄνος also finds ὦνος; the gain is that whoever has no Greek keyboard finds
#: something. It is a search key, and for this reason it counts for nothing.
_SEARCH_FOLDING = str.maketrans({
    "ς": "σ",            # final sigma and medial sigma are the same letter
    "ϲ": "σ", "Ϲ": "σ",   # lunate sigma
    "ϐ": "β", "ϑ": "θ", "ϕ": "φ", "ϖ": "π", "ϰ": "κ", "ϱ": "ρ",
    "η": "ε", "ω": "ο",  # vowel quantity: Latin does not write it
    "ͅ": None,       # iota subscript, already removed by skeleton but not always
    "'": None, "’": None, "ʼ": None, "᾽": None,
    "-": None, "‐": None, "‑": None,
})


def search_key(text: object) -> str:
    """The key with which one searches, not the one with which one counts.

    It must make whoever writes ``ἄνθρωπος``, ``ανθρωπος`` or ``anthropos`` find
    the same word, in NFC as in NFD, with or without breathings, accents, iota
    subscript and diaeresis, and without distinguishing the final sigma.

    It is deliberately **generous**, and for this reason must never be used for a
    scientific count: merging ``ἀλλά`` and ``ἄλλα`` is what one wants when
    searching and an error when counting. For counting there is
    :func:`skeleton`, and for identity there is :func:`nfc`.
    """
    if not isinstance(text, str) or not text:
        return ""
    value = skeleton(text)
    # Transliteration applies only if the text is entirely Latin: whoever writes in
    # Greek does not want their ρ to become something else, and a mixed string is almost
    # always a typing error whose intention cannot be guessed.
    if all(char.isascii() for char in value):
        for latin, greek in _TRANSLITERATION:
            value = value.replace(latin, greek)
    # The folding comes after the transliteration, so that the two routes — Greek and
    # Latin — arrive at the same key: ω and ο become ο from whichever side one started.
    return value.translate(_SEARCH_FOLDING)


#: The Unicode normalisation forms that the program can name. The order matters:
#: NFC before NFD, because the normal corpus is NFC and the exception is the
#: second.
_UNICODE_FORMS = ("NFC", "NFD", "NFKC", "NFKD")


def unicode_form(text: object) -> str:
    """The name of the normalisation form in which the string already is.

    It returns ``""`` if the string is in none of the four forms (it happens: a mixed
    sequence of composed and decomposed is normalised in none), and otherwise the name
    of the first form that it satisfies.
    """
    if not isinstance(text, str) or not text:
        return ""
    for form in _UNICODE_FORMS:
        if unicodedata.is_normalized(form, text):
            return form
    return ""


def disambiguate_spellings(spellings: "list[str]") -> "list[str]":
    """Make visible the difference between spellings that are identical on screen.

    Two spellings may differ in their code points and not in the drawn shape:
    ``ἄνθρωπος`` written in NFC and the same written in NFD are two different
    strings and the same word on the screen. A column that puts them side by side
    without saying anything seems to repeat the same thing twice, and whoever
    reads concludes that the program counts wrongly.

    Here the spellings that coincide after NFC are marked with the name of their
    Unicode form — ``ἄνθρωπος (NFC)``, ``ἄνθρωπος (NFD)`` — and when the form has
    no name it is marked with the length in code points, which is the difference
    that is always seen. The spellings that are already different to the eye are
    not touched: adding a label where it is not needed is noise.
    """
    normalizzate: dict[str, int] = {}
    for grafia in spellings:
        chiave = nfc(grafia)
        normalizzate[chiave] = normalizzate.get(chiave, 0) + 1
    fuori = []
    for grafia in spellings:
        if normalizzate.get(nfc(grafia), 0) < 2:
            fuori.append(grafia)
            continue
        marca = unicode_form(grafia) or f"{len(grafia)} code point"
        fuori.append(f"{grafia} ({marca})")
    return fuori
