"""The catalogue of diagnostic checks: what each one looks for, and what can be done about it.

Every check the program can fire is declared here with

* a bilingual name and a bilingual explanation written for a reader who is a
  philologist, not a programmer;
* the **family** it belongs to (morphology, lemma, syntax, text, agreement) —
  *where* the problem is, and how the interface groups the results;
* its **diagnostic class** — *what kind of finding* it is;
* its **treatment** — *what may be done* about it.

Class and treatment are two questions, not one, and keeping them apart is the
point of this design. A missing syntactic relation is a certain violation of
the scheme and cannot be repaired automatically, because there is no way to
guess which relation belonged there; a lemma with a tool's numbering appended
is not an error at all and can be normalised without thinking.

The three classes:

``violazione``  The data breaks an explicit rule of the annotation scheme, or a
                required field is absent. Verifiable without interpreting the
                text: a nine-character tag that is eight characters long, a
                value outside the declared inventory, a token with no head, a
                sentence with no root.

``variante``    A systematic variant records an annotation convention or an
                admissible representational choice that differs from GCP's
                declared operational reference profile without necessarily
                violating the underlying annotation scheme.

                The word *declared* carries weight. GCP's reference profile is
                not the bare minimum AGDT prescribes: it is deliberately
                richer, because the point of the program is to compare
                resources that were built to different conventions. So a variant is not always a departure
                from the scheme — it can be a departure from the richer profile
                while conforming to the scheme perfectly. The person left
                unmarked on a personal pronoun is exactly that case: AGDT 2.0
                does not ask for it, and GCP reports its absence because the
                information is useful downstream, not because anything was
                broken.

                This class therefore covers, coherently: the tool numbering on
                lemmas, NFD encoding, alternative character encodings, documented
                local extensions such as Pedalion's ``b``, and the omission of
                optional information. Mapping any of them onto the reference is
                a decision about what the corpus will be used for, so the
                program reports and the reader decides.

``verifica``    The check has found a place worth looking at, but only the
                context settles whether anything is wrong. Disagreement between
                a modifier and its head, a subject in an unexpected case, a
                particle in an unusual relation, a rare form one character away
                from a frequent one. These are never counted as errors.

The three treatments:

``automatica``       One right answer, known in advance; the program can write
                     it and the reader can undo it.
``normalizzazione``  A mapping onto the reference scheme that the reader has to
                     choose, because it costs something.
``manuale``          No automatic action is possible or defensible.

Every check that carries the class ``violazione`` is a genuine violation, but
that says nothing about whether it can be repaired: the two axes cross freely,
and the catalogue below contains every combination that occurs.
"""
from __future__ import annotations

# Families, used to group rules in the interface.
FAMILY_MORPHOLOGY = "morfologia"
FAMILY_LEMMA = "lemma"
FAMILY_SYNTAX = "sintassi"
FAMILY_TEXT = "testo"
FAMILY_AGREEMENT = "accordo"

FAMILY_LABELS: dict[str, tuple[str, str]] = {
    FAMILY_MORPHOLOGY: ("Morfologia (PoS-tag)", "Morphology (PoS-tag)"),
    FAMILY_LEMMA: ("Lemmatizzazione", "Lemmatisation"),
    FAMILY_SYNTAX: ("Struttura sintattica", "Syntactic structure"),
    FAMILY_TEXT: ("Testo e codifica", "Text and encoding"),
    FAMILY_AGREEMENT: ("Accordo e reggenza", "Agreement and government"),
}

# ── Diagnostic class: what kind of finding this is ───────────────────────
#: The data breaks an explicit rule of the scheme, or a required field is
#: absent. Checkable without interpreting the text.
VIOLAZIONE = "violazione"

#: Systematic, coherent, and different from the reference scheme. Not
#: necessarily an error; normalising it is a decision, and it costs something.
VARIANTE = "variante"

#: A place worth looking at. Only the context decides. Never counted as errors.
VERIFICA = "verifica"

CLASS_ORDER = (VIOLAZIONE, VARIANTE, VERIFICA)

CLASS_LABELS: dict[str, tuple[str, str]] = {
    VIOLAZIONE: ("1 — Violazione verificabile", "1 — Verifiable violation"),
    VARIANTE: ("2 — Variante sistematica", "2 — Systematic variant"),
    VERIFICA: ("3 — Caso da verificare", "3 — Case to check"),
}

CLASS_SHORT: dict[str, tuple[str, str]] = {
    VIOLAZIONE: ("Violazione", "Violation"),
    VARIANTE: ("Variante", "Variant"),
    VERIFICA: ("Da verificare", "To check"),
}

# ── Treatment: what may be done about it ─────────────────────────────────
#: One right answer, known in advance. The program can write it.
T_AUTO = "automatica"

#: A mapping onto the reference scheme that the reader has to choose.
T_NORM = "normalizzazione"

#: No automatic action is possible or defensible.
T_MANU = "manuale"

TREATMENT_ORDER = (T_AUTO, T_NORM, T_MANU)

TREATMENT_LABELS: dict[str, tuple[str, str]] = {
    T_AUTO: ("Correzione automatica", "Automatic correction"),
    T_NORM: ("Normalizzazione su scelta", "Normalisation on request"),
    T_MANU: ("Revisione manuale", "Manual review"),
}

#: The severity that each finding of a check receives.
#:
#: A violation is an error; a variant and a case to verify are suspects, that is,
#: points to look at and not mistakes. The table is read by :func:`_rule`, which
#: writes the severity into the catalogue entry, and is then read by
#: :func:`rule_severity`: the class remains the only source.
CLASS_SEVERITY: dict[str, str] = {
    VIOLAZIONE: "errore",
    VARIANTE: "sospetto",
    VERIFICA: "sospetto",
}


#: The lexical repairs, a single table.
#:
#: Each row says: which form, with which wrong tag, becomes which tag. The program
#: applies them by reading from here, and the description of each rule in the catalogue
#: is generated from the same row: table and catalogue cannot diverge. ``auto`` set to
#: ``False`` means that the proposal is shown but not applied by itself.
#:
#: Every ``suggest`` of this table is passed, in ``tests/test_pipeline_base.py``, through
#: the same checks that the program applies to the tags of the corpus: a proposal that
#: the program itself would flag is a defect.
LEXICAL_REPAIRS: list[dict[str, object]] = [
    # πότʼ and πόθʼ are in a single row, because they are the same anomaly on the same
    # word: the interrogative adverb, elided, marked as an adjective.
    {"rule_id": "pot-anomaly",      "forms": ("πότʼ", "πόθʼ"), "postag_startswith": "a", "suggest": "d--------", "auto": False},
    {"rule_id": "deina-anomaly",    "form": "δεῖνʼ",          "postag_eq": "p-_---__-",  "suggest": "p-s---ma-", "auto": False},
    {"rule_id": "tan-anomaly",      "form": "τάν",            "postag_eq": "n-_---__-",  "suggest": "i--------", "auto": False},
    # ὀσφράνθητι is the second singular of the aorist passive imperative of ὀσφραίνομαι.
    # Every proposal of this table is passed through analyze_postags in the tests: an
    # automatic correction that introduces violations is not a correction.
    {"rule_id": "osfranthiti-anomaly", "form": "ὀσφράνθητι", "postag_eq": None,          "suggest": "v2samp---"},
    # ── Numeral anomalies ──────────────────────────────────────────────────────
    {"rule_id": "numeral-generic-m",      "form": None,              "postag_eq": "m-_---__-",  "suggest": "m--------"},
    # The two spellings of the numeral “fourteen”, Ionic and Attic, with any tag that is
    # not already that of a numeral.
    {"rule_id": "tessereskaideka-anomaly","forms": ("τεσσερεσκαίδεκα", "τεσσαρεσκαίδεκα"), "postag_not_startswith": "m", "suggest": "m--------"},
    # ── Nominal anomalies ──────────────────────────────────────────────────────
    {"rule_id": "san-anomaly",            "form": "σὰν",             "postag_eq": "n-_---n_-",  "suggest": "n-s---na-", "auto": False},
    {"rule_id": "creon-anomaly",          "form": "χρεὼν",           "postag_eq": "n-_---n_-",  "suggest": "n-s---nn-", "auto": False},
    # ── Verbal adjective (g in mood slot) → adjective reclassification ─────────
]


#: The repairs checked by hand on a single occurrence.
#:
#: A correction reconstructed by reading a sentence holds for that sentence. The same
#: form with the same tag, in another passage or in another corpus, may require a
#: different analysis: τὸν δεῖνʼ is accusative masculine singular there, not everywhere.
#: The proposal therefore appears only if all the identification data coincide: corpus,
#: document, work, sentence, token identifier, form, lemma and tag. A single different
#: field and the finding remains without a proposal.
VERIFIED_REPAIRS: tuple[dict[str, object], ...] = (

    # ── creon-anomaly ─────────────────────────────────────────────
    {"rule_id": 'creon-anomaly', "corpus": 'gorman',
     "document_id": 'thuc-3-21-40-bu1', "cts_urn": 'tlg0003.tlg001',
     "sentence_id": '135', "token_id": '10',
     "form": 'χρεὼν', "lemma": 'χρεὼν',
     "postag": 'n-_---n_-', "suggest": 'n-s---nn-'},

    # ── deina-anomaly ─────────────────────────────────────────────
    {"rule_id": 'deina-anomaly', "corpus": 'gorman',
     "document_id": 'demosthenes-4-phil1-bu1', "cts_urn": 'tlg0014.tlg004',
     "sentence_id": '144', "token_id": '7',
     "form": 'δεῖνʼ', "lemma": 'δεῖνα',
     "postag": 'p-_---__-', "suggest": 'p-s---ma-'},
    {"rule_id": 'deina-anomaly', "corpus": 'gorman',
     "document_id": 'demosthenes-4-phil1-bu1', "cts_urn": 'tlg0014.tlg004',
     "sentence_id": '144', "token_id": '11',
     "form": 'δεῖνʼ', "lemma": 'δεῖνα',
     "postag": 'p-_---__-', "suggest": 'p-s---ma-'},

    # ── leading-t ─────────────────────────────────────────────────
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen12-20-29-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '44', "token_id": '14',
     "form": 'ἐλθόντες', "lemma": 'ἔρχομαι',
     "postag": 't-papamn-', "suggest": 'v-papamn-'},
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen12-30-39-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '26', "token_id": '16',
     "form": 'ὄντες', "lemma": 'εἰμί',
     "postag": 't-pppamn-', "suggest": 'v-pppamn-'},
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen12-60-69-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '127', "token_id": '14',
     "form": 'εἰπών', "lemma": 'εἶπον',
     "postag": 't-sapamn-', "suggest": 'v-sapamn-'},
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen12-70-81-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '180', "token_id": '18',
     "form": 'γράφων', "lemma": 'γράφω',
     "postag": 't-sppamn-', "suggest": 'v-sppamn-'},
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen13-1-9-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '137', "token_id": '8',
     "form": 'γήμας', "lemma": 'γαμέω',
     "postag": 't-sapamn-', "suggest": 'v-sapamn-'},
    {"rule_id": 'leading-t', "corpus": 'gorman',
     "document_id": 'athen13-10-19-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '56', "token_id": '4',
     "form": 'Ἀποκοπτομένῳ', "lemma": 'ἀποκόπτω',
     "postag": 't-sppemd-', "suggest": 'v-sppemd-'},

    # ── leading-x-lexical ─────────────────────────────────────────
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'appian-bc-1-11-14-bu1', "cts_urn": 'tlg0551.tlg017',
     "sentence_id": '199', "token_id": '20',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'athen13-70-79-2019', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '45', "token_id": '3',
     "form": 'τέκμαρ', "lemma": 'τέκμαρ',
     "postag": 'x-s---na-', "suggest": 'n-s---na-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'athen13-70-79-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '45', "token_id": '3',
     "form": 'τέκμαρ', "lemma": 'τέκμαρ',
     "postag": 'x-s---na-', "suggest": 'n-s---na-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'athen13-80-89-2019', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '169', "token_id": '17',
     "form": "η'", "lemma": "η'",
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'athen13-80-89-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '169', "token_id": '17',
     "form": "η'", "lemma": "η'",
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'demosthenes-18-276-324-bu1', "cts_urn": 'tlg0014.tlg018',
     "sentence_id": '124', "token_id": '4',
     "form": 'τᾶν', "lemma": 'τᾶν',
     "postag": 'x--------', "suggest": 'i--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'diodsic11-41-60-bu1', "cts_urn": 'tlg0060.tlg001',
     "sentence_id": '48', "token_id": '24',
     "form": 'τὰ', "lemma": 'τίς',
     "postag": 'x-p---nn-', "suggest": 'l-p---nn-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-100-119-bu3-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '54', "token_id": '5',
     "form": 'σπάκα', "lemma": 'σπάκα',
     "postag": 'x--------', "suggest": 'n-s---fa-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-120-149-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '180', "token_id": '3',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-120-149-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '204', "token_id": '5',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-170-189-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '103', "token_id": '13',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-190-216-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '19', "token_id": '1',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'hdt-1-40-59-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '53', "token_id": '25',
     "form": 'δυώδεκα', "lemma": 'δυώδεκα',
     "postag": 'x--------', "suggest": 'm--------'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'lysias-14-bu1', "cts_urn": 'tlg0540.tlg014',
     "sentence_id": '17', "token_id": '3',
     "form": 'τίνες', "lemma": 'τίς',
     "postag": 'x-p---mn-', "suggest": 'p-p---mn-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'polybius-10-1-10-bu1', "cts_urn": 'tlg0543.tlg001',
     "sentence_id": '35', "token_id": '43',
     "form": 'ὕπαρ', "lemma": 'ὕπαρ',
     "postag": 'x-----n--', "suggest": 'n-----n--'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'polybius-9-1-20-bu1', "cts_urn": 'tlg0543.tlg001',
     "sentence_id": '160', "token_id": '1',
     "form": 'τί', "lemma": 'τίς',
     "postag": 'x-s---na-', "suggest": 'p-s---na-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'polybius-9-21-33-bu1', "cts_urn": 'tlg0543.tlg001',
     "sentence_id": '106', "token_id": '64',
     "form": 'τίς', "lemma": 'τίς',
     "postag": 'x-s---mn-', "suggest": 'p-s---mn-'},
    {"rule_id": 'leading-x-lexical', "corpus": 'gorman',
     "document_id": 'thuc-1-61-80-bu3', "cts_urn": 'tlg0003.tlg001',
     "sentence_id": '44', "token_id": '3',
     "form": 'τί', "lemma": 'τίς',
     "postag": 'x-s---na-', "suggest": 'p-s---na-'},

    # ── participle-mood-g ─────────────────────────────────────────
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-40-49-2019', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '41', "token_id": '29',
     "form": 'ἔχων', "lemma": 'ἔχω',
     "postag": 'v-spgamn-', "suggest": 'v-sppamn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-40-49-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '41', "token_id": '29',
     "form": 'ἔχων', "lemma": 'ἔχω',
     "postag": 'v-spgamn-', "suggest": 'v-sppamn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-60-69-2019', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '50', "token_id": '14',
     "form": 'ἔχων', "lemma": 'ἔχω',
     "postag": 'v-spgamn-', "suggest": 'v-sppamn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-60-69-2019', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '57', "token_id": '15',
     "form": 'οὖσα', "lemma": 'εἰμί',
     "postag": 'v-spgafn-', "suggest": 'v-sppafn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-60-69-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '50', "token_id": '14',
     "form": 'ἔχων', "lemma": 'ἔχω',
     "postag": 'v-spgamn-', "suggest": 'v-sppamn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'athen13-60-69-jan-15', "cts_urn": 'tlg0008.tlg001',
     "sentence_id": '57', "token_id": '15',
     "form": 'οὖσα', "lemma": 'εἰμί',
     "postag": 'v-spgafn-', "suggest": 'v-sppafn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'hdt-1-120-149-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '159', "token_id": '3',
     "form": 'ἀκούσας', "lemma": 'ἀκούω',
     "postag": 'v-sagamn-', "suggest": 'v-sapamn-'},
    {"rule_id": 'participle-mood-g', "corpus": 'gorman',
     "document_id": 'plutarch-lycurgus-16-31-bu2', "cts_urn": 'tlg0007.tlg004',
     "sentence_id": '109', "token_id": '10',
     "form": 'παρόντων', "lemma": 'πάρειμι1',
     "postag": 'v-ppgamg-', "suggest": 'v-pppamg-'},

    # ── pot-anomaly ───────────────────────────────────────────────
    {"rule_id": 'pot-anomaly', "corpus": 'gorman',
     "document_id": 'demosthenes-4-phil1-bu1', "cts_urn": 'tlg0014.tlg004',
     "sentence_id": '23', "token_id": '1',
     "form": 'πότʼ', "lemma": 'πότε',
     "postag": 'a-_---___', "suggest": 'd--------'},
    {"rule_id": 'pot-anomaly', "corpus": 'gorman',
     "document_id": 'demosthenes-4-phil1-bu1', "cts_urn": 'tlg0014.tlg004',
     "sentence_id": '23', "token_id": '8',
     "form": 'πόθʼ', "lemma": 'πότε',
     "postag": 'a-_---___', "suggest": 'd--------'},

    # ── san-anomaly ───────────────────────────────────────────────
    {"rule_id": 'san-anomaly', "corpus": 'gorman',
     "document_id": 'hdt-1-120-149-bu2-2019', "cts_urn": 'tlg0016.tlg001',
     "sentence_id": '147', "token_id": '20',
     "form": 'σὰν', "lemma": 'σὰν',
     "postag": 'n-_---n_-', "suggest": 'n-s---na-'},
)


#: The parentheses of Pedalion left written as a breathing, one by one.
#:
#: Twenty-nine records out of thirty-one. The direction of the substitution is not
#: a conjecture: the resource already contains 73 records with form “(” and lemma
#: U+0314 and 73 with form “)” and lemma U+0313, and none of the opposite
#: correspondence. The two records excluded, “Leuven|PaeanBrev|5|28” and
#: “Leuven|PaeanBrev|10|12”, are not parentheses: they are the fragment of a word
#: split into two records, and are recognised because the following token begins
#: with the apostrophe (ʼλυμπιάδος for Ὀλυμπιάδος, ʼν for ἦν). They stay flagged and
#: without a proposal.
#:
#: The list is closed: an isolated sign that appeared tomorrow in another
#: passage, or in another corpus, is flagged and nothing more.
PARENTHESIS_REPAIRS: tuple[dict[str, object], ...] = (
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0557-001|85|5', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0557-001|85|11', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0557-001|154|20', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0557-001|154|25', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|14|9', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|14|12', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|146|3', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|146|8', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|273|9', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|274|8', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|484|7', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|484|16', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|540|7', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0006-003|541|6', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|Genesis_deel2|248|13', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|Genesis_deel2|248|17', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|Genesis_deel2|274|21', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|Genesis_deel2|274|25', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0561-001|34|5', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|0561-001|34|9', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|28|11', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|75|1', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|104|14', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|151|32', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|151|37', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|203|14', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|203|29', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|351|15', "form": '̔',
     "lemma": '̔', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": '('},
    {"rule_id": "isolated-breathing", "corpus": "pedalion",
     "ref": 'Leuven|PaeanBrev|352|11', "form": '̓',
     "lemma": '̓', "postag": 'u--------',
     "relation": 'AuxG',
     "campo": "form", "suggest": ')'},
)

#: The fields that must all coincide for a verified repair to apply. The fields that do
#: not identify the occurrence: all the others must coincide for the proposal to appear.
VERIFIED_META: frozenset[str] = frozenset({"rule_id", "campo", "suggest"})


def verified_repairs() -> tuple[dict[str, object], ...]:
    """All the verified repairs, the morphological ones and the parentheses."""
    return tuple(VERIFIED_REPAIRS) + tuple(PARENTHESIS_REPAIRS)


#: The lexical source of each repair, in Italian and in English.
LEXICAL_SOURCES: dict[str, tuple[str, str]] = {
    "pot-anomaly": (
        "La forma elisa πότʼ sta per l'interrogativo πότε o per l'indefinito "
        "ποτέ. Sono due parole diverse, ma tutte e due avverbi, quindi la parte "
        "del discorso non è in dubbio e l'etichetta di aggettivo è sbagliata in "
        "ogni caso. La proposta cambia solo quella, senza leggere la frase.",
        "The elided form πότʼ stands either for the interrogative πότε or for the "
        "indefinite ποτέ. They are two different words, but both adverbs, so the "
        "part of speech is not in doubt and the adjective tag is wrong either "
        "way. The proposal changes that alone, without reading the sentence."),
    "deina-anomaly": (
        "δεῖνʼ è l'elisione del pronome δεῖνα, «il tale», da non confondere con "
        "l'infinito δεῖν. Resta un pronome, e la proposta non tocca la prima "
        "posizione. Cambia i trattini bassi con cui l'etichetta scrive le "
        "caselle che non si applicano, ed è la stessa normalizzazione che il "
        "catalogo tratta altrove.",
        "δεῖνʼ is the elision of the pronoun δεῖνα, 'so-and-so', not to be "
        "confused with the infinitive δεῖν. It stays a pronoun, and the proposal "
        "does not touch slot one. It changes the underscores with which the tag "
        "writes the slots that do not apply, the same normalisation the "
        "catalogue treats elsewhere."),
    "numeral-generic-m": (
        "La prima posizione dice già numerale. La proposta cambia soltanto i "
        "trattini bassi in trattini, come la regola generale sul trattino "
        "basso.",
        "Slot one already says numeral. The proposal changes only the "
        "underscores into dashes, like the general underscore rule."),
    "tessereskaideka-anomaly": (
        "τεσσερεσκαίδεκα, «quattordici», è un numerale indeclinabile (LSJ s.v. "
        "τεσσαρεσκαίδεκα, con la grafia ionica in -ερε-). L'etichetta lo dà come "
        "aggettivo di grado superlativo, che per un numerale non esiste.",
        "τεσσερεσκαίδεκα, 'fourteen', is an indeclinable numeral (LSJ s.v. "
        "τεσσαρεσκαίδεκα, with the Ionic spelling in -ερε-). The tag gives it as "
        "a superlative adjective, which for a numeral does not exist."),
    "san-anomaly": (
        "σάν è il nome della lettera ϻ, e i nomi delle lettere greche non si "
        "declinano (LSJ s.v. σάν). La proposta lascia sostantivo e genere e "
        "cambia i trattini bassi in trattini.",
        "σάν is the name of the letter ϻ, and the names of the Greek letters do "
        "not decline (LSJ s.v. σάν). The proposal leaves the noun and the gender "
        "and changes the underscores into dashes."),
    "creon-anomaly": (
        "χρεών, «ciò che è necessario», è un neutro indeclinabile (LSJ s.v. "
        "χρεών). Anche qui la proposta tocca soltanto i trattini bassi.",
        "χρεών, 'that which is necessary', is an indeclinable neuter (LSJ s.v. "
        "χρεών). Here too the proposal touches the underscores only."),
    "osfranthiti-anomaly": (
        "ὀσφράνθητι è la seconda persona singolare dell'imperativo aoristo "
        "passivo di ὀσφραίνομαι. La proposta, «v2samp---», scrive persona, "
        "numero, tempo, modo e diatesi e lascia vuote le caselle di genere, caso "
        "e grado, che a un verbo di modo finito non spettano. Ogni proposta di "
        "questa tabella passa per gli stessi controlli che il programma applica "
        "al corpus, e i test verificano che non ne violi nessuno.",
        "ὀσφράνθητι is the second person singular of the aorist passive "
        "imperative of ὀσφραίνομαι. The proposal, 'v2samp---', writes person, "
        "number, tense, mood and voice and leaves the slots of gender, case and "
        "degree empty, which a verb in a finite mood does not have. Every "
        "proposal in this table is passed through the same controls that the "
        "program applies to the corpus, and the tests check that it violates "
        "none of them."),
}

def _rule(
    name_it: str, name_en: str,
    description_it: str, description_en: str,
    *, family: str, klass: str, treatment: str,
) -> dict[str, object]:
    return {
        "name": name_it,
        "name_en": name_en,
        "description": description_it,
        "description_en": description_en,
        "family": family,
        "class": klass,
        "treatment": treatment,
        # Derived, not declared: only a check whose treatment is "automatica"
        # may write into the corpus by itself. Keeping this as a computed
        # property removes the possibility of the two disagreeing.
        "default_auto_apply": treatment == T_AUTO,
        "severity": CLASS_SEVERITY.get(klass, "sospetto"),
    }


#: Repairs that have a hand-written entry further on in the catalogue, because they are
#: not corrections but cases to read.
_RIPARAZIONI_DESCRITTE_A_PARTE = frozenset({
    "tan-anomaly", "pot-anomaly", "deina-anomaly", "osfranthiti-anomaly",
    "numeral-generic-m", "tessereskaideka-anomaly", "san-anomaly",
    "creon-anomaly",
})

_NOMI_RIPARAZIONI = {
    "pot-anomaly": ("πότʼ marcato come aggettivo", "πότʼ tagged as an adjective"),
    "deina-anomaly": ("δεῖνʼ con trattini bassi nell'etichetta",
                      "δεῖνʼ with underscores in the tag"),
    "numeral-generic-m": ("Numerale con trattini bassi nell'etichetta",
                          "Numeral with underscores in the tag"),
    "tessereskaideka-anomaly": ("τεσσερεσκαίδεκα marcato come aggettivo superlativo",
                                "τεσσερεσκαίδεκα tagged as a superlative adjective"),
    "san-anomaly": ("σὰν con trattini bassi al posto dei trattini",
                    "σὰν with underscores instead of dashes"),
    "creon-anomaly": ("χρεὼν con trattini bassi al posto dei trattini",
                      "χρεὼν with underscores instead of dashes"),
    "osfranthiti-anomaly": ("ὀσφράνθητι marcato con un'etichetta non imperativa",
                            "ὀσφράνθητι tagged with a non-imperative tag"),
}


def _lexical_name_it(riga: dict) -> str:
    return _NOMI_RIPARAZIONI.get(str(riga["rule_id"]), (str(riga["rule_id"]), ""))[0]


def _lexical_name_en(riga: dict) -> str:
    coppia = _NOMI_RIPARAZIONI.get(str(riga["rule_id"]))
    return coppia[1] if coppia else str(riga["rule_id"])


def _lexical_description(riga: dict, lingua: str) -> str:
    """The description of a repair, written from the row that carries it out."""
    rid = str(riga["rule_id"])
    forma = riga.get("form")
    condizione = riga.get("postag_eq") or riga.get("postag_startswith")
    fonte = LEXICAL_SOURCES.get(rid, ("", ""))[0 if lingua == "it" else 1]
    if lingua == "it":
        quale = (f"sulla forma «{forma}»" if forma else "su qualunque forma")
        come = (f"con l'etichetta «{condizione}»" if riga.get("postag_eq")
                else f"la cui etichetta comincia per «{condizione}»" if condizione
                else "")
        return (f"Riparazione su una forma sola, scritta per intero. Scatta "
                f"{quale} {come} e propone «{riga['suggest']}». Non tocca "
                f"nessun'altra casella e non vale per altre parole.\n{fonte}")
    quale = (f"the form '{forma}'" if forma else "any form")
    come = (f"carrying the tag '{condizione}'" if riga.get("postag_eq")
            else f"whose tag begins with '{condizione}'" if condizione else "")
    return (f"A point lexical repair, and the table writes it out in full: it fires on "
            f"{quale} {come}, and proposes '{riga['suggest']}'. It holds for this form "
            f"with this tag only, it is not a generalisation, and no other slot is "
            f"touched. {fonte}")


RULE_CATALOG: dict[str, dict[str, object]] = {

    # ── Morphology: shape of the nine-character tag ───────────────────────
    "missing-postag": _rule(
        'PoS tag assente', 'PoS tag missing',
        "Nel file XML il token non presenta l'attributo postag, oppure "
        'l\'attributo è presente ma vuoto (postag=""). Il PoS tag deve '
        'essere ricostruito a partire da forma, lemma e contesto.',
        'In the XML file the token has no postag attribute, or the '
        'attribute is present but empty (postag=""). The PoS tag must be '
        'reconstructed from the form, the lemma and the context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),


    # invalid-length was one rule with one "safe to apply" flag for two different
    # situations: in Pedalion 75 of its 108 findings were tags padded with dashes
    # and 33 were tags of one or two characters, which no mechanical repair can
    # reach.  One flag cannot describe both.
    "invalid-length-padding": _rule(
        'Etichetta composta da soli trattini con lunghezza errata', 'Label consisting only of hyphens with an incorrect length',
        'Il PoS tag contiene una parte del discorso valida nella prima '
        'posizione e soltanto trattini nelle posizioni successive, ma non '
        'ha i nove caratteri previsti. Poiché non sono presenti altri '
        'valori morfologici, il programma aggiunge o elimina i soli '
        "trattini terminali necessari. Un'etichetta già lunga nove "
        'caratteri non viene modificata.',
        'The PoS tag contains a valid part of speech in the first slot '
        'and only hyphens in the following slots, but it does not have '
        'the nine characters required. Since no other morphological '
        'values are present, the program adds or removes only the '
        'trailing hyphens needed. A label that is already nine characters '
        'long is not modified.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    "invalid-length-broken": _rule(
        'Etichetta di lunghezza errata da ricostruire nel contesto', 'Label of incorrect length to be reconstructed in context',
        'Il PoS tag non ha i nove caratteri previsti e contiene, oltre al '
        'codice della parte del discorso, almeno un altro valore '
        'informativo. Il carattere mancante o eccedente può alterare '
        "l'interpretazione delle posizioni successive; l'intera etichetta "
        'deve quindi essere ricostruita nel contesto.',
        'The PoS tag does not have the nine characters required and '
        'contains, besides the part of speech code, at least one other '
        'informative value. The missing or extra character may alter the '
        'interpretation of the following slots; the whole label must '
        'therefore be reconstructed in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "invalid-character": _rule(
        'Carattere non ammesso nella posizione morfologica', 'Character not allowed in the morphological slot',
        'Una posizione del postag contiene un carattere non previsto '
        "dall'inventario AGDT 2.0 per quella posizione. Il valore "
        "corretto dipende dall'analisi morfologica della forma e deve "
        'essere verificato nel contesto.',
        'A slot of the postag contains a character not provided for by '
        'the AGDT 2.0 inventory for that slot. The correct value depends '
        'on the morphological analysis of the form and must be checked in '
        'context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "case-letter-l": _rule(
        'Locativo, valore ammesso ma raro', 'Locative, an allowed but rare value',
        "L'ottava posizione del postag contiene l, valore previsto per il "
        'locativo ma raro nel corpus. La segnalazione non implica un '
        'errore: il caso deve essere verificato nel contesto senza una '
        'correzione predefinita.',
        'The eighth slot of the postag contains l, the value provided for '
        'the locative but rare in the corpus. The finding does not imply '
        'an error: the case must be checked in context, without a '
        'predefined correction.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "grade-p": _rule(
        'Grado positivo marcato con p', 'Positive degree marked with p',
        'La nona posizione del postag contiene p per indicare il grado '
        'positivo, ma la codifica adottata usa il trattino quando il '
        'grado non è comparativo o superlativo. Il programma sostituisce '
        'p con - nella nona posizione.',
        'The ninth slot of the postag contains p to indicate the positive '
        'degree, but the encoding adopted uses the hyphen when the degree '
        'is neither comparative nor superlative. The program replaces p '
        'with - in the ninth slot.',
        family=FAMILY_MORPHOLOGY, klass=VARIANTE, treatment=T_AUTO),

    "degree-underscore": _rule(
        'Trattino basso nella posizione del grado', 'Underscore in the degree slot',
        'La nona posizione del postag contiene _ al posto di -. Il '
        'programma sostituisce il trattino basso con il trattino '
        'previsto, evitando che etichette equivalenti siano contate come '
        'valori diversi.',
        'The ninth slot of the postag contains _ instead of -. The '
        'program replaces the underscore with the required hyphen, '
        'preventing equivalent labels from being counted as different '
        'values.',
        family=FAMILY_MORPHOLOGY, klass=VARIANTE, treatment=T_AUTO),

    "underscore-person-number": _rule(
        'Trattino basso nelle posizioni morfologiche 2-8', 'Underscore in morphological slots 2-8',
        'Il postag contiene _ in una delle posizioni dalla seconda '
        "all'ottava, nelle quali la codifica adottata usa - per un tratto "
        'non applicabile o non valorizzato. Il programma sostituisce _ '
        'con -; eventuali incoerenze morfologiche residue vanno '
        'controllate separatamente.',
        'The postag contains _ in one of the slots from the second to the '
        'eighth, where the encoding adopted uses - for a feature that '
        'does not apply or is left unfilled. The program replaces _ with '
        '-; any remaining morphological inconsistencies must be checked '
        'separately.',
        family=FAMILY_MORPHOLOGY, klass=VARIANTE, treatment=T_AUTO),

    "mediopassive-d": _rule(
        'Diatesi d non prevista', 'Voice d not provided for',
        'La sesta posizione del postag contiene d, valore non previsto '
        'dalla codifica AGDT 2.0 adottata per il greco. Può trattarsi di '
        'una convenzione importata o locale, per esempio per i deponenti; '
        "l'interpretazione e la correzione devono essere verificate nel "
        'contesto.',
        'The sixth slot of the postag contains d, a value not provided '
        'for by the AGDT 2.0 encoding adopted for Greek. This may be an '
        'imported or local convention, for example for deponents; the '
        'interpretation and the correction must be checked in context.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "leading-t": _rule(
        'PoS non ammesso in prima posizione (t)', 'PoS not allowed in slot one (t)',
        'La prima posizione del postag contiene t, valore non previsto '
        "dall'inventario morfologico AGDT 2.0. La parte del discorso "
        'corretta deve essere determinata in base alla forma e al '
        'contesto.',
        'The first slot of the postag contains t, a value not provided '
        'for by the AGDT 2.0 morphological inventory. The correct part of '
        'speech must be determined from the form and the context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "punctuation-leading-e": _rule(
        'PoS e su un segno di punteggiatura', 'PoS e on a punctuation mark',
        'La forma è un segno di punteggiatura, ma la prima posizione del '
        'postag contiene e. Per la punteggiatura la codifica adottata usa '
        'u; il programma sostituisce quindi e-------- con u-------- '
        'quando la corrispondenza è univoca.',
        'The form is a punctuation mark, but the first slot of the postag '
        'contains e. For punctuation the encoding adopted uses u; the '
        'program therefore replaces e-------- with u-------- when the '
        'correspondence is unambiguous.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    "leading-x-lexical": _rule(
        'PoS x su un record lessicale', 'PoS x on a lexical record',
        'La prima posizione del postag contiene x, ma il record '
        'rappresenta una parola effettivamente presente nel testo e non è '
        'classificato come nodo ellittico. La parte del discorso corretta '
        'deve essere determinata nel contesto.',
        'The first slot of the postag contains x, but the record '
        'represents a word actually present in the text and is not '
        'classified as an elliptic node. The correct part of speech must '
        'be determined in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),


    # ── The shape of the tag, class by class ──────────────────────────────
    "slot-forbidden": _rule(
        'Tratto non ammesso per la parte del discorso', 'Feature not allowed for the part of speech',
        'Il PoS tag valorizza un tratto che la parte del discorso non '
        'ammette, per esempio un tempo su un sostantivo o un caso su un '
        'verbo di modo finito. Il tratto o la parte del discorso devono '
        'essere verificati nel contesto.',
        'The PoS tag fills a feature that the part of speech does not '
        'allow, for example a tense on a noun or a case on a verb in a '
        'finite mood. The feature or the part of speech must be checked '
        'in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "slot-missing": _rule(
        'Tratto morfologico obbligatorio non valorizzato', 'Required morphological feature left unfilled',
        'Nel PoS tag manca un tratto richiesto per quella forma, per '
        'esempio il genere di un sostantivo o la persona di un verbo '
        "finito. Gli altri tratti sono presenti, ma l'analisi risulta "
        'incompleta e deve essere completata nel contesto.',
        'The PoS tag lacks a feature required for that form, for example '
        'the gender of a noun or the person of a finite verb. The other '
        'features are present, but the analysis is incomplete and must be '
        'completed in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "slot-missing-bare": _rule(
        'Sostantivo privo di tratti morfologici (n--------)', 'Noun with no morphological features (n--------)',
        'Il postag identifica il token come sostantivo ma non valorizza '
        "numero, genere e caso. L'etichetta è formalmente ben formata, ma "
        "l'analisi morfologica è incompleta; i tratti devono essere "
        'ricostruiti nel contesto, salvo nomi indeclinabili o convenzioni '
        'dichiarate della risorsa.',
        'The postag identifies the token as a noun but does not fill '
        'number, gender and case. The label is formally well formed, but '
        'the morphological analysis is incomplete; the features must be '
        'reconstructed in context, except for indeclinable nouns or '
        'declared conventions of the resource.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "uninflected-lemma": _rule(
        'Lemma nominale senza caso in tutte le occorrenze', 'Nominal lemma without case in all its occurrences',
        'Un lemma nominale attestato almeno cinque volte non presenta mai '
        'un valore di caso. Il comportamento può dipendere dalla natura '
        'indeclinabile o straniera del lemma, da una convenzione della '
        'risorsa o da una lacuna sistematica di annotazione e deve essere '
        'valutato a livello del lemma.',
        'A nominal lemma attested at least five times never has a case '
        'value. This behaviour may be due to the indeclinable or foreign '
        'nature of the lemma, to a convention of the resource or to a '
        'systematic gap in the annotation, and must be assessed at the '
        'level of the lemma.',
        family=FAMILY_LEMMA, klass=VERIFICA, treatment=T_MANU),

    # The rule is not relative to the corpus: it reports pronouns without person
    # everywhere, and its class is “systematic variant”. On four corpora out of six the
    # count is unaffected, and on the two automatic strata of GLAUx — which never mark
    # person — the check gives 1,773 and 1,451 findings. This is intended: it is a
    # declarable convention, and it is exactly what a systematic variant records.
    "personal-pronoun-person": _rule(
        'Persona non annotata nel pronome personale',
        'Person not annotated on a personal pronoun',
        'Il record è un pronome personale, ma il postag non specifica la '
        "persona. AGDT 2.0 non richiede questo tratto per i pronomi, quindi la "
        "sua assenza non è una violazione dello schema. GCP la registra come "
        'variante perché il profilo operativo che adotta è deliberatamente più '
        "ricco del minimo prescritto: l'informazione serve a chi voglia "
        "un'annotazione completa, armonizzata e confrontabile fra risorse. "
        'Nessuna correzione viene proposta, e la persona non viene dedotta.',
        'The record is a personal pronoun, but the postag does not specify the '
        'person. AGDT 2.0 does not require this feature for pronouns, so its '
        'absence is not a violation of the scheme. GCP records it as a variant '
        'because the operational profile it adopts is deliberately richer than '
        'the prescribed minimum: the information serves anyone wanting a '
        'complete, harmonised and comparable annotation. No correction is '
        'proposed, and the person is not inferred.',
        family=FAMILY_MORPHOLOGY, klass=VARIANTE, treatment=T_MANU),

    # One rule covers every verb form that carries the mood “g” in the mood slot —
    # ἔχων, οὖσα, ἀκούσας, παρόντων — and not one rule per word: the question does not
    # need the word.
    "participle-mood-g": _rule(
        'Valore non ammesso nella posizione del modo (g)', 'Value not allowed in the mood slot (g)',
        'La quinta posizione del postag contiene g, valore non previsto '
        "per il modo verbale nell'inventario AGDT 2.0. Il valore corretto "
        "dipende dall'analisi della forma.",
        'The fifth slot of the postag contains g, a value not provided '
        'for verbal mood in the AGDT 2.0 inventory. The correct value '
        'depends on the analysis of the form.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "tan-anomaly": _rule(
        'τάν/τᾶν, forma lessicalmente ambigua', 'τάν/τᾶν, a lexically ambiguous form',
        'Le forme normalizzate τάν e τᾶν possono appartenere a una '
        "formula allocutiva oppure corrispondere all'accusativo femminile "
        "singolare dell'articolo o pronome in varietà che conservano ᾱ. "
        "La forma grafica non consente una scelta univoca e l'analisi "
        'deve essere verificata nel contesto.',
        'The normalised forms τάν and τᾶν may belong to an address '
        'formula or correspond to the feminine singular accusative of the '
        'article or pronoun in varieties that preserve ᾱ. The written '
        'form does not allow an unambiguous choice and the analysis must '
        'be checked in context.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    # The name does not carry the name of a corpus. The phenomenon is general — a value
    # outside the inventory that the project declares as its own convention — even though
    # today the only value recognised in this way is the “b” of Pedalion. It is not merged with common gender “c”: it stands in a
    # different position of the tag, concerns different morphological information, and
    # does not have the same documentary basis.
    "pedalion-b-pos": _rule(
        'PoS extra-schema usato come estensione locale (b)',
        'Extra-scheme POS used as a local extension (b)',
        'La prima posizione del postag contiene b, valore non documentato '
        "nell'inventario AGDT 2.0 ma usato dalla risorsa come convenzione "
        'locale. Una conversione può essere proposta soltanto se il profilo '
        'della specifica risorsa e versione dichiara una corrispondenza '
        'univoca.',
        'The first slot of the postag contains b, a value not documented in '
        'the AGDT 2.0 inventory but used by the resource as a local '
        'convention. A conversion can be proposed only if the profile of the '
        'specific resource and version declares an unambiguous '
        'correspondence.',
        family=FAMILY_MORPHOLOGY, klass=VARIANTE, treatment=T_MANU),

    "common-gender-c": _rule(
        'Valore c extra-schema nella posizione del genere',
        'Extra-scheme value c in the gender slot',
        'La settima posizione del postag contiene c, valore non previsto '
        "dall'inventario AGDT 2.0 per il genere. Nelle risorse analizzate il "
        'valore ricorre soprattutto con pronomi e alcuni nomi e la sua '
        'distribuzione è compatibile con una convenzione locale per il genere '
        'comune, ma questa interpretazione non è documentata nelle risorse '
        'disponibili. Il valore deve quindi essere verificato nel profilo '
        'della singola risorsa e nel contesto; il programma non propone alcuna '
        'conversione automatica.',
        'The seventh slot of the postag contains c, a value the AGDT 2.0 '
        'inventory does not provide for gender. In the resources examined the '
        'value occurs mostly with pronouns and some nouns, and its '
        'distribution is compatible with a local convention for the common '
        'gender, but this reading is not documented in the resources '
        'available. The value must therefore be checked against the profile '
        'of the individual resource and in context; the program proposes no '
        'automatic conversion.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "nonlexical-z-pos": _rule(
        'PoS extra-schema su un record non lessicale (z)', 'PoS outside the scheme on a non-lexical record (z)',
        'La prima posizione del postag contiene z, valore non documentato '
        "nell'inventario AGDT 2.0. Se, nella specifica risorsa e "
        'versione, il valore ricorre esclusivamente su record non '
        'lessicali, deve essere trattato come indicatore tecnico locale '
        'senza dedurre automaticamente una parte del discorso '
        'sostitutiva.',
        'The first slot of the postag contains z, a value not documented '
        'in the AGDT 2.0 inventory. If, in the specific resource and '
        'version, the value occurs exclusively on non-lexical records, it '
        'must be treated as a local technical marker without '
        'automatically inferring a replacement part of speech.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "dein-participle-disputed": _rule(
        "δεῖν participiale da verificare sul passo",
        "Participial δεῖν to be checked against the passage",
        "La forma δεῖν porta un'etichetta di participio in un caso che il "
        "programma non corregge senza verifica. Ciò avviene quando il luogo è "
        "fra le attestazioni che il LSJ, s.v. δεῖ, IV, segnala come dubbie e "
        "la pipeline può identificarlo dalla citazione della risorsa, oppure "
        "quando le informazioni disponibili non permettono di escludere con "
        "sufficiente sicurezza che l'occorrenza appartenga a uno di questi "
        "luoghi. In questi casi il programma non propone alcuna correzione: "
        "l'analisi deve essere verificata sul passo e sulla tradizione "
        "testuale. La regola resta separata da quella che corregge le altre "
        "occorrenze di δεῖν annotate come participio.",
        "The form δεῖν carries a participle tag in a case the program does "
        "not correct without verification. This happens when the locus is "
        "among the attestations LSJ, s.v. δεῖ, IV, marks as dubious and the "
        "pipeline can identify it from the citation of the resource, or when "
        "the information available does not allow the occurrence to be ruled "
        "out of those loci with sufficient confidence. In these cases the "
        "program proposes no correction: the analysis must be checked against "
        "the passage and the textual tradition. The rule is kept apart from "
        "the one that repairs the other occurrences of δεῖν annotated as a "
        "participle.",
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    "dein-participle": _rule(
        'δεῖν con modo participiale', 'δεῖν with participial mood',
        'La forma δεῖν è annotata con p nella posizione del modo, cioè '
        'come participio. Nelle occorrenze non controverse, δεῖν è '
        "l'infinito di δεῖ e richiede n.",
        'The form δεῖν is annotated with p in the mood slot, that is, as '
        'a participle. In uncontroversial occurrences, δεῖν is the '
        'infinitive of δεῖ and requires n.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    # ── The lexical repairs, described by the table that carries them out ───
    #
    # Each description writes both the starting tag and the proposed one, reading them
    # from LEXICAL_REPAIRS, and adds the lexical source from LEXICAL_SOURCES.
    **{
        str(riga["rule_id"]): _rule(
            _lexical_name_it(riga), _lexical_name_en(riga),
            _lexical_description(riga, "it"), _lexical_description(riga, "en"),
            family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE,
            treatment=T_AUTO if riga.get("auto", True) else T_MANU)
        for riga in LEXICAL_REPAIRS
        if str(riga["rule_id"]) not in _RIPARAZIONI_DESCRITTE_A_PARTE
    },

    "pot-anomaly": _rule(
        'Forme elise πότʼ/πόθʼ con PoS aggettivale', 'Elided forms πότʼ/πόθʼ with an adjectival PoS',
        'Le forme πότʼ e πόθʼ, nelle occorrenze validate nella tabella di '
        "riferimento, sono forme elise dell'avverbio interrogativo πότε "
        '«quando?», ma recano il postag aggettivale a-_---___. In πότʼ '
        "cade la ε finale davanti a vocale; in πόθʼ l'elisione si "
        'accompagna al passaggio di τ a θ davanti allo spirito aspro. Il '
        'valore d-------- può essere applicato automaticamente soltanto '
        'alle occorrenze già validate; eventuali nuove occorrenze '
        'richiedono controllo contestuale.',
        'The forms πότʼ and πόθʼ, in the occurrences validated in the '
        'reference table, are elided forms of the interrogative adverb '
        "πότε 'when?', but they carry the adjectival postag a-_---___. In "
        'πότʼ the final ε is dropped before a vowel; in πόθʼ the elision '
        'is accompanied by the change of τ to θ before the rough '
        'breathing. The value d-------- can be applied automatically only '
        'to occurrences that have already been validated; any new '
        'occurrences require a check in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "deina-anomaly": _rule(
        'δεῖνʼ pronominale con PoS incompleto', 'Pronominal δεῖνʼ with an incomplete PoS',
        'La forma elisa δεῖνʼ, quando rappresenta il pronome δεῖνα, '
        'presenta un postag incompleto e contenente trattini bassi. '
        "Un'etichetta completa può essere proposta soltanto se genere, "
        'numero e caso sono ricavabili univocamente dal contesto o se '
        "l'occorrenza è già stata validata.",
        'The elided form δεῖνʼ, when it stands for the pronoun δεῖνα, has '
        'an incomplete postag containing underscores. A complete label '
        'can be proposed only if gender, number and case can be recovered '
        'unambiguously from the context or if the occurrence has already '
        'been validated.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "osfranthiti-anomaly": _rule(
        'ὀσφράνθητι con analisi morfologica incompatibile', 'ὀσφράνθητι with an incompatible morphological analysis',
        'La forma ὀσφράνθητι presenta un postag che non la identifica '
        "come seconda persona singolare dell'imperativo aoristo passivo. "
        'Il valore corretto v2samp--- è proposto dal programma '
        'automaticamente. La correzione riguarda esclusivamente il postag '
        'e non modifica né certifica il lemma, la relazione sintattica o '
        'la testa.',
        'The form ὀσφράνθητι has a postag that does not identify it as '
        'the second person singular of the aorist passive imperative. The '
        'correct value v2samp--- is proposed automatically by the '
        'program. The correction concerns the postag alone and does not '
        'modify or certify the lemma, the syntactic relation or the head.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    "numeral-generic-m": _rule(
        'Numerale con trattini bassi nel PoS tag', 'Numeral with underscores in the PoS tag',
        'Un token riconosciuto come numerale presenta trattini bassi '
        'nelle posizioni non applicabili del postag. Quando la parte del '
        'discorso è già determinata in modo univoco, il programma '
        "sostituisce l'etichetta con m--------.",
        'A token recognised as a numeral has underscores in the slots of '
        'the postag that do not apply. When the part of speech is already '
        'determined unambiguously, the program replaces the label with '
        'm--------.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    "tessereskaideka-anomaly": _rule(
        'τεσσερεσκαίδεκα con PoS non numerale', 'τεσσερεσκαίδεκα with a non-numeral PoS',
        'Le forme τεσσερεσκαίδεκα e τεσσαρεσκαίδεκα, quando indicano il '
        'numerale indeclinabile «quattordici», sono annotate con una '
        'parte del discorso diversa da numerale. Il valore m-------- è '
        'proposto automaticamente dal programma.',
        'The forms τεσσερεσκαίδεκα and τεσσαρεσκαίδεκα, when they denote '
        "the indeclinable numeral 'fourteen', are annotated with a part "
        'of speech other than numeral. The value m-------- is proposed '
        'automatically by the program.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_AUTO),

    "san-anomaly": _rule(
        'σὰν come nome di lettera con PoS incompleto', 'σὰν as a letter name with an incomplete PoS',
        'La forma σὰν, quando indica il nome della lettera ϻ, presenta un '
        'postag incompleto. Il valore n-s---na- può essere proposto '
        "soltanto se il contesto conferma l'analisi come nome neutro "
        'singolare accusativo.',
        'The form σὰν, when it denotes the name of the letter ϻ, has an '
        'incomplete postag. The value n-s---na- can be proposed only if '
        'the context confirms the analysis as a neuter singular '
        'accusative noun.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "creon-anomaly": _rule(
        'χρεὼν nominale con PoS incompleto', 'Nominal χρεὼν with an incomplete PoS',
        "La forma χρεὼν presenta un'analisi nominale incompleta. Il "
        'valore n-s---nn- può essere proposto soltanto per occorrenze '
        'validate come nome neutro singolare nominativo; analisi verbali '
        'o letture diverse richiedono una revisione contestuale.',
        'The form χρεὼν has an incomplete nominal analysis. The value n-s '
        '---nn- can be proposed only for occurrences validated as a '
        'neuter singular nominative noun; verbal analyses or different '
        'readings require review in context.',
        family=FAMILY_MORPHOLOGY, klass=VIOLAZIONE, treatment=T_MANU),

    "verbal-adjective-g": _rule(
        'Valore locale g per aggettivi verbali in -τέος', 'Local value g for verbal adjectives in -τέος',
        'La risorsa usa g nella posizione del modo come codice locale per '
        'aggettivi verbali in -τέος. Questa codifica non appartiene ad '
        'AGDT 2.0, che tratta queste forme come aggettivi. Il programma '
        'mostra il corrispondente postag aggettivale, ma non lo applica '
        'automaticamente. Ogni occorrenza deve essere verificata nel '
        'contesto, perché alcuni tratti non sono ricavabili dalla sola '
        'forma: in particolare, nei neutri in -τέον, come ποιητέον, il '
        'caso può essere nominativo oppure accusativo e deve quindi '
        'essere stabilito manualmente.',
        'The resource uses g in the mood slot as a local code for verbal '
        'adjectives in -τέος. This encoding does not belong to AGDT 2.0, '
        'which treats these forms as adjectives. The program shows the '
        'corresponding adjectival postag, but does not apply it '
        'automatically. Every occurrence must be checked in context, '
        'because some features cannot be recovered from the form alone: '
        'in particular, in the neuters in -τέον, such as ποιητέον, the '
        'case may be either nominative or accusative and must therefore '
        'be established manually.',
        family=FAMILY_MORPHOLOGY, klass=VERIFICA, treatment=T_MANU),

    # ── Lemma ─────────────────────────────────────────────────────────────
    "missing-lemma": _rule(
        'Lemma assente', 'Lemma missing',
        'Il campo lemma è assente o vuoto. Il lemma corretto deve essere '
        'stabilito a partire dalla forma e dal contesto e non può essere '
        'ricostruito in modo sicuro con una sostituzione meccanica.',
        'The lemma field is missing or empty. The correct lemma must be '
        'established from the form and the context and cannot be '
        'reconstructed safely by a mechanical substitution.',
        family=FAMILY_LEMMA, klass=VIOLAZIONE, treatment=T_MANU),

    # normalized-lemma was one rule doing three jobs, and on the Gorman corpus of
    # the time it alone was more than half the whole diagnosis under a single
    # name.  The three jobs differ in how sure they are: dropping
    # a digit an annotation tool appended is mechanical, choosing between two
    # real spellings is a decision, and re-encoding in NFC is an encoding matter
    # that unicode-not-nfc already reports by name.
    "lemma-tool-numbering": _rule(
        'Numero finale nel lemma', 'Final number in the lemma',
        'Il campo lemma termina con una cifra usata dalla risorsa o '
        "dall'analizzatore per distinguere voci omografe. La rimozione "
        'può fondere identificatori lessicali distinti; la pipeline deve '
        'quindi applicarla soltanto secondo la politica di '
        'normalizzazione dichiarata.',
        'The lemma field ends with a digit used by the resource or by the '
        'analyser to distinguish homographic entries. Removing it may '
        'merge distinct lexical identifiers; the pipeline must therefore '
        'apply it only in accordance with the declared normalisation '
        'policy.',
        family=FAMILY_LEMMA, klass=VARIANTE, treatment=T_MANU),

    "lemma-graphic-variant": _rule(
        'Varianti grafiche concorrenti dello stesso lemma', 'Competing graphic variants of the same lemma',
        'Il corpus usa, per la stessa voce, due o più grafie ammesse '
        'incluse in un elenco configurabile di equivalenze. La regola si '
        'attiva soltanto quando più varianti coesistono nella risorsa; la '
        'scelta della forma canonica è una decisione di normalizzazione.',
        'For the same entry the corpus uses two or more admissible '
        'spellings included in a configurable list of equivalences. The '
        'rule applies only when several variants coexist in the resource; '
        'the choice of the canonical form is a normalisation decision.',
        family=FAMILY_LEMMA, klass=VARIANTE, treatment=T_MANU),


    # The two questions — is the relation rare given the pair, is the part of speech
    # rare given the relation? — query the same three-way table (lemma by part of speech
    # by relation) from two sides. A single check, with a single pair of thresholds,
    # answers both, and builds its profile on all the tokens, so that no part of speech
    # goes unprofiled.
    "rare-relation-for-lemma-and-pos": _rule(
        'Relazione rara per lemma e PoS', 'Rare relation for lemma and POS',
        'Per ogni coppia di lemma e parte del discorso attestata almeno '
        'duecento volte fra le parole del testo, il programma calcola come si '
        'distribuiscono le relazioni sintattiche di base, cioè le etichette '
        'private dei suffissi _CO e _AP. Le occorrenze la cui relazione copre '
        "al massimo l'uno per cento di quella coppia vengono segnalate. La "
        'rarità non dimostra un errore: una costruzione può essere rara e '
        'corretta, e il numero assoluto dice quanto pesa la percentuale.',
        'For every pair of lemma and part of speech attested at least two '
        'hundred times among the words of the text, the program computes how '
        'the base syntactic relations are distributed, that is the labels '
        'stripped of the suffixes _CO and _AP. Occurrences whose relation '
        'covers at most one per cent of that pair are reported. Rarity does '
        'not demonstrate an error: a construction may be rare and correct, and '
        'the absolute number says how much the percentage weighs.',
        family=FAMILY_AGREEMENT, klass=VERIFICA, treatment=T_MANU),

    "lemma-suspicious-characters": _rule(
        'Caratteri anomali nel lemma', 'Anomalous characters in the lemma',
        "Il campo lemma contiene trattini, parentesi o cifre all'interno "
        'della parola. Questi caratteri possono dipendere da convenzioni '
        'della risorsa di provenienza (es. περι-κεῖμαι, Ἰων(ν)ης); la '
        'forma canonica deve essere scelta in base alla politica '
        'lessicografica adottata.',
        'The lemma field contains hyphens, brackets or digits inside the '
        'word. These characters may be due to conventions of the source '
        'resource (e.g. περι-κεῖμαι, Ἰων(ν)ης); the canonical form must '
        'be chosen according to the lexicographical policy adopted.',
        family=FAMILY_LEMMA, klass=VARIANTE, treatment=T_MANU),

    "lemma-rare-for-form": _rule(
        'Lemma raro per forma e PoS', 'Rare lemma for form and POS',
        'Una combinazione di forma e PoS attestata almeno venticinque volte '
        'è ricondotta una sola volta a un lemma diverso da quello che copre '
        'almeno il 95% delle sue occorrenze. Il caso può essere corretto o '
        'anomalo; il programma mostra come possibile alternativa il lemma di '
        'maggioranza, ma non applica automaticamente alcuna correzione.',
        'A combination of form and POS attested at least twenty-five times is '
        'traced on a single occasion to a lemma other than the one that '
        'covers at least 95% of its occurrences. The case may be correct or '
        'anomalous; the program shows the majority lemma as a possible '
        'alternative, but applies no correction automatically.',
        family=FAMILY_LEMMA, klass=VERIFICA, treatment=T_MANU),

    # ── Syntactic structure ───────────────────────────────────────────────
    # The four rules below are one check split in four.  A single
    # ``relation-damaged`` check would report together four accidents that share
    # only the symptom ("this label is not in the inventory") and differ in
    # cause, in repair and in what the repair costs, and it would be
    # auto-applicable for all four — rewriting CO as COORD and Aux as AuxY,
    # which the trees of both corpora contradict.
    "relation-greek-lookalike": _rule(
        "Carattere greco confondibile nell'etichetta sintattica", 'Look-alike Greek character in the syntactic label',
        'Il campo relation contiene un carattere greco graficamente '
        'identico al carattere latino previsto, per esempio zeta greco al '
        'posto di Z in AuxZ. Il programma sostituisce il carattere con il '
        'corrispondente latino.',
        'The relation field contains a Greek character graphically '
        'identical to the Latin character required, for example Greek '
        'zeta in place of Z in AuxZ. The program replaces the character '
        'with its Latin counterpart.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_AUTO),

    "relation-typo": _rule(
        "Refuso univoco nell'etichetta sintattica", 'Unambiguous typo in the syntactic label',
        "Il campo relation differisce per un solo carattere da un'unica "
        'etichetta ammessa dallo schema. Quando la corrispondenza è '
        "univoca, il programma sostituisce il valore con l'etichetta "
        'riconosciuta.',
        'The relation field differs by a single character from exactly '
        'one label allowed by the scheme. When the correspondence is '
        'unambiguous, the program replaces the value with the recognised '
        'label.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_AUTO),

    "relation-bare-convention": _rule(
        'Etichetta extra-schema usata sistematicamente dal corpus', 'Label outside the scheme used systematically by the corpus',
        "Una relazione non prevista dall'inventario AGDT 2.0 ricorre "
        'almeno venti volte e in almeno il 90% dei documenti della stessa '
        'risorsa e versione. La distribuzione suggerisce una convenzione '
        'locale, ma non consente di espandere automaticamente il valore '
        'in una relazione AGDT.',
        'A relation not provided for by the AGDT 2.0 inventory occurs at '
        'least twenty times and in at least 90% of the documents of the '
        'same resource and version. The distribution suggests a local '
        'convention, but it does not allow the value to be expanded '
        'automatically into an AGDT relation.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    "relation-truncated-or-foreign": _rule(
        'Relazione non AGDT riconducibile a una convenzione nota', 'Non-AGDT relation traceable to a known convention',
        "Il campo relation contiene un'etichetta non riconosciuta da AGDT "
        "2.0 ma riconducibile a un'abbreviazione, a una convenzione "
        'precedente o a un altro schema noto, per esempio Aux, AUX, CO o '
        'CONJ. Il programma segnala il caso, ma non propone una '
        'correzione automatica: la relazione corretta deve essere scelta '
        'leggendo la frase e controllando l’albero.',
        'The relation field contains a label not recognised by AGDT 2.0 '
        'but traceable to an abbreviation, to an earlier convention or to '
        'another known scheme, for example Aux, AUX, CO or CONJ. The '
        'program reports the case, but does not propose an automatic '
        'correction: the correct relation must be chosen by reading the '
        'sentence and checking the tree.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "relation-nil-placeholder": _rule(
        'Segnaposto nil al posto della relazione', 'The placeholder nil in place of the relation',
        "Il campo relation contiene nil, segnaposto che indica l'assenza "
        "dell'analisi e non una relazione sintattica AGDT. La relazione "
        "corretta deve essere stabilita controllando la frase e l'albero.",
        'The relation field contains nil, a placeholder that indicates '
        'the absence of the analysis and not an AGDT syntactic relation. '
        'The correct relation must be established by checking the '
        'sentence and the tree.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "head-dangling": _rule(
        'Testa inesistente', 'Non-existent head',
        'Il campo head del token contiene un numero diverso da 0. Il '
        'programma cerca nella stessa frase un token il cui id '
        'corrisponda a quel numero; se non lo trova, il collegamento '
        'sintattico punta a una testa inesistente e non è valido. '
        "L'albero deve quindi essere ricostruito manualmente.",
        'The head field of the token contains a number other than 0. The '
        'program looks in the same sentence for a token whose id matches '
        'that number; if it does not find one, the syntactic link points '
        'to a non-existent head and is not valid. The tree must therefore '
        'be reconstructed manually.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "sentence-not-annotated": _rule(
        'Nessuna testa dichiarata nella frase', 'No head declared in the sentence',
        'Tutti i token della frase hanno il campo head vuoto, quindi la '
        'frase non contiene collegamenti sintattici dichiarati. Il '
        "programma genera una sola segnalazione per l'intera frase; "
        "l'albero deve essere ricostruito o recuperato manualmente.",
        'All the tokens in the sentence have an empty head field, so the '
        'sentence contains no declared syntactic links. The program '
        'produces a single finding for the whole sentence; the tree must '
        'be reconstructed or recovered manually.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "head-missing": _rule(
        'Testa sintattica non dichiarata', 'Syntactic head not declared',
        'Il campo head del token è vuoto (non è quindi indicato l’id '
        'della parola da cui il token dipende), mentre almeno un altro '
        'token della frase dichiara una testa. La testa corretta deve '
        'essere indicata manualmente.',
        'The head field of the token is empty (the id of the word on '
        'which the token depends is therefore not given), while at least '
        'one other token in the sentence declares a head. The correct '
        'head must be supplied manually.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),


    "head-cycle": _rule(
        'Ciclo nelle teste', 'Cycle in the heads',
        'Seguendo i valori head, il programma torna a un token già '
        'incontrato. Il ciclo può dipendere da un token che indica se '
        'stesso come testa oppure da più dipendenze circolari; in '
        'entrambi i casi la struttura non è un albero valido.',
        'Following the head values, the program returns to a token '
        'already encountered. The cycle may be due to a token that gives '
        'itself as its head or to several circular dependencies; in '
        'either case the structure is not a valid tree.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "sentence-no-root": _rule(
        'Frase senza radice', 'Sentence without a root',
        'Nessun token della frase ha head="0". La struttura non possiede '
        'quindi una radice dichiarata e può contenere un ciclo, una testa '
        'mancante o un collegamento danneggiato.',
        'No token in the sentence has head="0". The structure therefore '
        'has no declared root and may contain a cycle, a missing head or '
        'a damaged link.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "sentence-many-roots": _rule(
        'Frase con più radici', 'Sentence with several roots',
        'Più di un token della stessa frase ha head="0". Una frase AGDT '
        'deve avere una sola radice; il caso può indicare un errore '
        'strutturale o una segmentazione della frase da rivedere.',
        'More than one token in the same sentence has head="0". An AGDT '
        'sentence must have a single root; the case may indicate a '
        'structural error or a sentence segmentation that needs review.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    "token-id-duplicate": _rule(
        'Identificatore duplicato', 'Duplicate identifier',
        'Due o più token della stessa frase hanno lo stesso '
        'identificatore. Ogni rimando a quel valore diventa ambiguo e gli '
        'identificatori o i collegamenti devono essere corretti '
        'manualmente.',
        'Two or more tokens in the same sentence have the same '
        'identifier. Every reference to that value becomes ambiguous and '
        'the identifiers or the links must be corrected manually.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "relation-unknown": _rule(
        'Relazione fuori schema', 'Relation outside the scheme',
        "Il campo relation contiene un'etichetta non appartenente "
        "all'inventario AGDT 2.0 e non riconducibile a nessuno dei casi "
        'specifici gestiti dalle altre regole. La relazione corretta deve '
        'essere scelta nel contesto.',
        'The relation field contains a label that does not belong to the '
        'AGDT 2.0 inventory and cannot be traced to any of the specific '
        'cases handled by the other rules. The correct relation must be '
        'chosen in context.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "relation-missing": _rule(
        'Relazione assente', 'Relation missing',
        'Il campo relation è assente o vuoto. La funzione sintattica del '
        "token deve essere determinata controllando la frase e l'albero.",
        'The relation field is missing or empty. The syntactic function '
        'of the token must be determined by checking the sentence and the '
        'tree.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "coord-suffix-orphan": _rule(
        'Suffisso _CO senza nodo coordinante', 'The suffix _CO without a coordinating node',
        'Il suffisso _CO indica che il token è membro di una '
        'coordinazione. Risalendo lungo le teste non viene però trovato '
        'un nodo con relazione COORD, direttamente o attraverso una '
        'parola funzionale, come una preposizione AuxP o una congiunzione '
        'subordinante AuxC; il suffisso e i collegamenti devono essere '
        'verificati.',
        'The suffix _CO indicates that the token is a member of a '
        'coordination. Going up through the heads, however, no node with '
        'the relation COORD is found, either directly or through a '
        'function word such as an AuxP preposition or an AuxC '
        'subordinating conjunction; the suffix and the links must be '
        'checked.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "apos-suffix-orphan": _rule(
        'Suffisso _AP senza apposizione', 'The suffix _AP without an apposition',
        'Il token porta _AP o _AP_CO: l’etichetta dichiara che questa '
        'parola e un’altra espressione indicano la stessa persona o cosa, '
        'come «Socrate, il filosofo». Il programma risale lungo le teste '
        'fino alla radice. Se non trova APOS o APOS_CO, segnala il caso: '
        'il suffisso dichiara un’apposizione, ma nell’albero manca il '
        'collegamento che la rappresenta e il caso deve essere '
        'verificato.',
        'The token carries _AP or _AP_CO: the label declares that this '
        'word and another expression denote the same person or thing, as '
        "in 'Socrates, the philosopher'. The program goes up through the "
        'heads as far as the root. If it does not find APOS or APOS_CO, '
        'it reports the case: the suffix declares an apposition, but the '
        'tree lacks the link that represents it and the case must be '
        'checked.',
        family=FAMILY_SYNTAX, klass=VIOLAZIONE, treatment=T_MANU),

    "coord-discordant-conjuncts": _rule(
        'Funzioni diverse nella stessa coordinazione', 'Different functions within the same coordination',
        'Più membri della stessa coordinazione, riconosciuti dal suffisso '
        '_CO e collegati allo stesso nodo coordinante, presentano '
        'funzioni di base diverse. L’asimmetria può essere corretta '
        'oppure dipendere da un’annotazione incoerente; il programma '
        'segnala il caso senza proporre una correzione.',
        'Several members of the same coordination, identified by the '
        'suffix _CO and attached to the same coordinating node, have '
        'different basic functions. The asymmetry may be correct or may '
        'be due to inconsistent annotation; the program reports the case '
        'without proposing a correction.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    "aux-governs-conjuncts": _rule(
        'Nodo non COORD che regge più congiunti _CO', 'Non-COORD node governing several _CO conjuncts',
        'Più token marcati con _CO dipendono dallo stesso nodo, ma il '
        "nodo non porta la relazione COORD. La struttura dell'albero e le "
        'etichette forniscono quindi indicazioni incompatibili e devono '
        'essere verificate nel contesto.',
        'Several tokens marked with _CO depend on the same node, but the '
        'node does not carry the relation COORD. The structure of the '
        'tree and the labels therefore give incompatible indications and '
        'must be checked in context.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    "aux-finite-verb": _rule(
        'Verbo finito con relazione AuxY o AuxZ', 'Finite verb with the relation AuxY or AuxZ',
        'Il postag identifica un verbo di modo finito, ma il campo '
        'relation contiene AuxY o AuxZ, funzioni non normalmente '
        'assegnate a un verbo finito nello schema AGDT 2.0. Il caso può '
        'riflettere un uso parentetico o avverbiale e deve essere '
        'valutato nel contesto.',
        'The postag identifies a verb in a finite mood, but the relation '
        'field contains AuxY or AuxZ, functions not normally assigned to '
        'a finite verb in the AGDT 2.0 scheme. The case may reflect a '
        'parenthetical or adverbial use and must be assessed in context.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    "aux-governor-without-child": _rule(
        'AuxP o AuxC senza dipendente', 'AuxP or AuxC without a dependent',
        'Un token con relazione AuxP o AuxC non ha dipendenti. '
        'Normalmente da questi nodi dipende il complemento o la testa '
        'della subordinata, ma il dipendente può mancare per ellissi, '
        'lacuna o testo interrotto; il caso deve essere verificato senza '
        'correzione automatica.',
        'A token with the relation AuxP or AuxC has no dependents. '
        'Normally the complement or the head of the subordinate clause '
        'depends on these nodes, but the dependent may be absent because '
        'of ellipsis, a lacuna or interrupted text; the case must be '
        'checked without an automatic correction.',
        family=FAMILY_SYNTAX, klass=VERIFICA, treatment=T_MANU),

    # ── Agreement and government ──────────────────────────────────────────
    "agreement-modifier": _rule(
        'Possibile mancato accordo del modificatore', 'Possible failure of agreement in the modifier',
        'Un articolo, un aggettivo o un participio attributivo non '
        'concorda con la propria testa in genere, numero o caso. Il '
        'controllo confronta soltanto i tratti presenti in entrambi i PoS '
        "tag e non si applica alle teste ellittiche; l'errore può "
        'trovarsi nel modificatore o nella testa.',
        'An article, an adjective or an attributive participle does not '
        'agree with its own head in gender, number or case. The check '
        'compares only the features present in both PoS tags and does not '
        'apply to elliptic heads; the error may lie in the modifier or in '
        'the head.',
        family=FAMILY_AGREEMENT, klass=VERIFICA, treatment=T_MANU),

    "case-subject": _rule(
        'Soggetto in caso inatteso per il contesto', 'Subject in a case unexpected for the context',
        'Un token con relazione SBJ presenta un caso diverso dal '
        'nominativo. Il valore può essere giustificato da costruzioni '
        'specifiche, come infinitive, assoluti, participi supplementari o '
        'attrazione; in assenza di tali condizioni devono essere '
        'controllati caso, relazione e testa.',
        'A token with the relation SBJ has a case other than the '
        'nominative. The value may be justified by specific '
        'constructions, such as infinitive clauses, absolutes, '
        'supplementary participles or attraction; in the absence of such '
        'conditions the case, the relation and the head must be checked.',
        family=FAMILY_AGREEMENT, klass=VERIFICA, treatment=T_MANU),

    "case-object": _rule(
        'Oggetto in caso inatteso', 'Object in an unexpected case',
        'Un nome, pronome o aggettivo sostantivato con relazione OBJ è '
        'marcato come nominativo o vocativo. Poiché OBJ può indicare '
        'diversi argomenti richiesti dal reggente, devono essere '
        'verificati congiuntamente caso, relazione e testa.',
        'A noun, pronoun or substantivised adjective with the relation '
        'OBJ is marked as nominative or vocative. Since OBJ may indicate '
        'different arguments required by the governor, the case, the '
        'relation and the head must be checked together.',
        family=FAMILY_AGREEMENT, klass=VERIFICA, treatment=T_MANU),


    # ── Text and encoding ─────────────────────────────────────────────────
    "corpus-not-nfc": _rule(
        'Corpus prevalentemente in NFD', 'Corpus predominantly in NFD',
        'La quota di valori testuali codificati in forma Unicode NFD '
        'supera la soglia definita per il corpus (50%). Il programma '
        'converte globalmente i valori in NFC secondo la politica di '
        'normalizzazione dichiarata, senza modificare il contenuto '
        'grafico.',
        'The proportion of text values encoded in Unicode NFD form '
        'exceeds the threshold defined for the corpus (50%). The program '
        'converts the values globally into NFC in accordance with the '
        'declared normalisation policy, without altering the graphic '
        'content.',
        family=FAMILY_TEXT, klass=VARIANTE, treatment=T_AUTO),

    "unicode-not-nfc": _rule(
        'Codifica non normalizzata in NFC', 'Encoding not normalised to NFC',
        'Uno o più valori testuali non sono in forma Unicode NFC, mentre '
        'il corpus nel suo insieme usa prevalentemente NFC. Il programma '
        'normalizza i valori interessati, evitando che stringhe '
        'graficamente identiche siano contate come diverse.',
        'One or more text values are not in Unicode NFC form, while the '
        'corpus as a whole predominantly uses NFC. The program normalises '
        'the values concerned, preventing graphically identical strings '
        'from being counted as different.',
        family=FAMILY_TEXT, klass=VARIANTE, treatment=T_AUTO),

    "apostrophe-mixed": _rule(
        'Apostrofi di elisione codificati con caratteri diversi', 'Elision apostrophes encoded with different characters',
        'Nel corpus coesistono più code point usati come apostrofo di '
        'elisione. Il programma propone di convertirli tutti in ʼ '
        '(U+02BC), adottato come carattere canonico secondo la '
        'convenzione seguita da Celano 2025. La sostituzione uniforma la '
        'codifica, ma non costituisce un requisito universale dello '
        'schema AGDT e viene applicata soltanto se l’utente accetta la '
        'proposta.',
        'Several code points used as an elision apostrophe coexist in the '
        'corpus. The program proposes to convert them all into ʼ '
        '(U+02BC), adopted as the canonical character following the '
        'convention used by Celano 2025. The substitution makes the '
        'encoding uniform, but it is not a universal requirement of the '
        'AGDT scheme and is applied only if the user accepts the '
        'proposal.',
        family=FAMILY_TEXT, klass=VARIANTE, treatment=T_AUTO),

    "mixed-script": _rule(
        'Lettere latine confondibili in una parola greca', 'Look-alike Latin letters in a Greek word',
        'Il campo form mescola caratteri greci e latini e i caratteri '
        'latini hanno corrispondenti greci graficamente equivalenti. Il '
        'programma sostituisce i caratteri latini con i corrispondenti '
        'greci, rendendo possibile il confronto esatto tra stringhe.',
        'The form field mixes Greek and Latin characters and the Latin '
        'characters have graphically equivalent Greek counterparts. The '
        'program replaces the Latin characters with their Greek '
        'counterparts, making exact comparison between strings possible.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_AUTO),

    "mixed-script-unrepairable": _rule(
        'Lettere latine non confondibili in una parola greca', 'Latin letters that are not look-alikes in a Greek word',
        'Il campo form contiene caratteri greci e latini e almeno un '
        'carattere latino non ha un corrispondente greco graficamente '
        'equivalente. Può trattarsi di un segno editoriale o di un errore '
        'di codifica; il programma segnala il caso senza proporre una '
        'sostituzione automatica.',
        'The form field contains Greek and Latin characters and at least '
        'one Latin character has no graphically equivalent Greek '
        'counterpart. This may be an editorial sign or an encoding error; '
        'the program reports the case without proposing an automatic '
        'substitution.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "isolated-breathing": _rule(
        'Spirito isolato nella forma', 'Isolated breathing in the form',
        'La forma è costituita soltanto da U+0314 o U+0313. Nei casi '
        'verificati il segno può rappresentare una parentesi rimasta '
        'codificata come spirito oppure un frammento staccato da una parola '
        'danneggiata. Per le occorrenze già validate il programma può '
        'mostrare una proposta di sostituzione ricavata da una tabella chiusa '
        'di corrispondenze; la proposta non viene mai applicata '
        'automaticamente. Le altre occorrenze devono essere ricostruite '
        'manualmente nel contesto.',
        'The form consists of U+0314 or U+0313 alone. In the verified cases '
        'the sign may stand for a bracket left encoded as a breathing, or for '
        'a fragment detached from a damaged word. For occurrences that have '
        'already been validated the program can show a replacement proposal '
        'drawn from a closed table of correspondences; the proposal is never '
        'applied automatically. The other occurrences must be reconstructed '
        'by hand in context.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "beta-code-form": _rule(
        'Residui di beta code nella forma', 'Beta code residues in the form',
        'Il campo form contiene simboli riconducibili alla '
        'traslitterazione beta code. La conversione in Unicode può essere '
        'incompleta o ambigua e deve essere verificata manualmente.',
        'The form field contains symbols traceable to beta code '
        'transliteration. The conversion into Unicode may be incomplete '
        'or ambiguous and must be checked manually.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "beta-code-lemma": _rule(
        'Residui di beta code nel lemma', 'Beta code residues in the lemma',
        'Il campo lemma contiene simboli riconducibili alla '
        'traslitterazione beta code. La conversione in Unicode può essere '
        'incompleta o ambigua e deve essere verificata manualmente.',
        'The lemma field contains symbols traceable to beta code '
        'transliteration. The conversion into Unicode may be incomplete '
        'or ambiguous and must be checked manually.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "breathing-impossible": _rule(
        'Apostrofo di elisione codificato come spirito', 'Elision apostrophe encoded as a breathing',
        'In posizione finale compare un carattere di spirito usato come '
        "segno autonomo di elisione, invece dell'apostrofo adottato dal "
        'profilo di normalizzazione. Il programma sostituisce il '
        'carattere soltanto quando non funziona come diacritico della '
        'vocale e la trasformazione è univoca.',
        'In final position a breathing character appears, used as an '
        'independent sign of elision instead of the apostrophe adopted by '
        'the normalisation profile. The program replaces the character '
        'only when it does not function as a diacritic on the vowel and '
        'the transformation is unambiguous.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_AUTO),

    "double-accent": _rule(
        'Due accenti sulla stessa parola', 'Two accents on the same word',
        'Il campo form contiene due accenti al di fuori dei contesti in '
        "cui una parola può ricevere l'accento di un'enclitica. Il caso "
        'deve essere verificato nel contesto.',
        'The form field contains two accents outside the contexts in '
        'which a word may receive the accent of an enclitic. The case '
        'must be checked in context.',
        family=FAMILY_TEXT, klass=VERIFICA, treatment=T_MANU),

    "final-sigma-inside": _rule(
        "Sigma finale all'interno della parola", 'Final sigma inside the word',
        'Il carattere ς compare in una posizione interna del campo form, '
        'dove è atteso σ. Il programma sostituisce automaticamente il '
        'sigma finale con il sigma non finale.',
        'The character ς appears in a word-internal position of the form '
        'field, where σ is expected. The program automatically replaces '
        'the final sigma with the non-final sigma.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_AUTO),

    "invisible-char-form": _rule(
        "Caratteri di formato nella forma", "Format characters in the form",
        'Il campo form contiene uno dei caratteri di formato Unicode '
        'esplicitamente riconosciuti dalla pipeline (U+200B, U+200C, U+200D, '
        'U+2060 o U+FEFF). Questi caratteri non hanno funzione ortografica '
        'nella rappresentazione del greco adottata dal corpus e possono '
        'interrompere il confronto fra stringhe graficamente equivalenti. Il '
        'programma propone la loro rimozione. Gli spazi e gli altri '
        'separatori sono gestiti da controlli distinti.',
        'The form field contains one of the Unicode format characters the '
        'pipeline explicitly recognises (U+200B, U+200C, U+200D, U+2060 or '
        'U+FEFF). These characters have no orthographic function in the '
        'representation of Greek the corpus adopts and can break the '
        'comparison between graphically equivalent strings. The program '
        'proposes their removal. Spaces and other separators are handled by '
        'separate checks.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_AUTO),

    "invisible-char-lemma": _rule(
        "Caratteri di formato nel lemma", "Format characters in the lemma",
        'Il campo lemma contiene uno dei caratteri di formato Unicode '
        'esplicitamente riconosciuti dalla pipeline (U+200B, U+200C, U+200D, '
        'U+2060 o U+FEFF). Questi caratteri non hanno funzione ortografica '
        'nella rappresentazione del greco adottata dal corpus e possono '
        'interrompere il confronto fra lemmi graficamente equivalenti. Il '
        'programma propone la loro rimozione. Gli spazi e gli altri '
        'separatori sono gestiti da controlli distinti.',
        'The lemma field contains one of the Unicode format characters the '
        'pipeline explicitly recognises (U+200B, U+200C, U+200D, U+2060 or '
        'U+FEFF). These characters have no orthographic function in the '
        'representation of Greek the corpus adopts and can break the '
        'comparison between graphically equivalent lemmas. The program '
        'proposes their removal. Spaces and other separators are handled by '
        'separate checks.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_AUTO),

    "whitespace-in-form": _rule(
        'Separatore interno nella forma', 'Internal separator in the form',
        'Il campo form contiene uno spazio, una tabulazione o un ritorno '
        'a capo. Il record può contenere più token oppure una '
        'segmentazione danneggiata; la semplice eliminazione del '
        'separatore non è una correzione sicura e la tokenizzazione deve '
        'essere rivista manualmente.',
        'The form field contains a space, a tab or a line break. The '
        'record may contain more than one token or a damaged '
        'segmentation; simply deleting the separator is not a safe '
        'correction and the tokenisation must be reviewed manually.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "whitespace-in-lemma": _rule(
        'Separatore interno nel lemma', 'Internal separator in the lemma',
        'Il campo lemma contiene uno o più separatori interni. Il valore '
        'può rappresentare un lemma pluriverbale, una tokenizzazione '
        'errata o una convenzione lessicografica della risorsa; il '
        'programma non elimina automaticamente i separatori.',
        'The lemma field contains one or more internal separators. The '
        'value may represent a multi-word lemma, an incorrect '
        'tokenisation or a lexicographical convention of the resource; '
        'the program does not delete the separators automatically.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

    "annotator-note-in-relation": _rule(
        "Appunto dell'annotatore nel campo relation", "Annotator's note in the relation field",
        'Il campo relation contiene una nota di lavorazione insieme a una '
        'possibile etichetta sintattica. Il valore non è una relazione '
        "valida e la nota può contraddire l'etichetta riportata; la "
        'relazione corretta deve essere stabilita controllando la frase e '
        "l'albero.",
        'The relation field contains a working note together with a '
        'possible syntactic label. The value is not a valid relation and '
        'the note may contradict the label given; the correct relation '
        'must be established by checking the sentence and the tree.',
        family=FAMILY_TEXT, klass=VIOLAZIONE, treatment=T_MANU),

}


_FALLBACK: dict[str, object] = {
    "name": "",
    "name_en": "",
    "description": "Nessuna descrizione disponibile per questo controllo.",
    "description_en": "No description is available for this check yet.",
    "family": FAMILY_MORPHOLOGY,
    "class": VERIFICA,
    "treatment": T_MANU,
    "default_auto_apply": False,
    "severity": "sospetto",
}


def get_rule_metadata(rule_id: str) -> dict[str, object]:
    entry = RULE_CATALOG.get(rule_id)
    if entry is not None:
        return entry
    pretty = rule_id.replace("-", " ").capitalize()
    return {**_FALLBACK, "name": pretty, "name_en": pretty}


def rule_name(rule_id: str, lang: str = "it") -> str:
    metadata = get_rule_metadata(rule_id)
    key = "name" if lang == "it" else "name_en"
    return str(metadata.get(key) or metadata.get("name") or rule_id)


def rule_description(rule_id: str, lang: str = "it") -> str:
    metadata = get_rule_metadata(rule_id)
    key = "description" if lang == "it" else "description_en"
    return str(metadata.get(key) or metadata.get("description") or "")


def rule_family(rule_id: str) -> str:
    return str(get_rule_metadata(rule_id).get("family", FAMILY_MORPHOLOGY))


def rule_class(rule_id: str) -> str:
    """``violazione``, ``variante`` or ``verifica`` — see the module docstring."""
    return str(get_rule_metadata(rule_id).get("class", VERIFICA))


def rule_treatment(rule_id: str) -> str:
    """``automatica``, ``normalizzazione`` or ``manuale``."""
    return str(get_rule_metadata(rule_id).get("treatment", T_MANU))


def rule_severity(rule_id: str) -> str:
    """The severity of a check, which comes from its class and from nothing else.

    The catalogue entry already carries it, written there by :func:`_rule` reading
    ``CLASS_SEVERITY``: nothing is decided here, it is only read.
    """
    return str(get_rule_metadata(rule_id).get("severity", "sospetto"))


def rule_ids_in_class(klass: str) -> list[str]:
    return sorted(rule_id for rule_id, metadata in RULE_CATALOG.items()
                  if metadata.get("class") == klass)


def check_only_rule_ids() -> list[str]:
    """The checks whose output is a list of places to look, not of errors.

    Everything outside class ``violazione``: a variant is not a mistake, and a
    case to check is not one either until somebody has read the passage. No
    figure in this program that says "the corpus contains N errors" may count
    them.
    """
    return sorted(rule_id for rule_id, metadata in RULE_CATALOG.items()
                  if metadata.get("class") != VIOLAZIONE)


def default_auto_apply(rule_id: str) -> bool:
    return bool(get_rule_metadata(rule_id).get("default_auto_apply"))


def auto_applicable_rule_ids() -> list[str]:
    return sorted(
        rule_id for rule_id, metadata in RULE_CATALOG.items()
        if metadata.get("default_auto_apply")
    )


def normalisable_rule_ids() -> list[str]:
    """Checks the reader may choose to normalise, one family at a time."""
    return sorted(rule_id for rule_id, metadata in RULE_CATALOG.items()
                  if metadata.get("treatment") == T_NORM)


def rules_by_family() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for rule_id, metadata in RULE_CATALOG.items():
        grouped.setdefault(str(metadata.get("family", FAMILY_MORPHOLOGY)), []).append(rule_id)
    for rule_ids in grouped.values():
        rule_ids.sort()
    return grouped


def catalog_frame(lang: str = "it"):
    """The whole catalogue as a table, for the 'what does it check?' tab."""
    import pandas as pd

    index = 0 if lang == "it" else 1
    rows = []
    for rule_id, metadata in sorted(RULE_CATALOG.items()):
        family = str(metadata.get("family", FAMILY_MORPHOLOGY))
        klass = str(metadata.get("class", VERIFICA))
        treatment = str(metadata.get("treatment", T_MANU))
        rows.append({
            "id": rule_id,
            "famiglia" if lang == "it" else "family":
                FAMILY_LABELS.get(family, (family, family))[index],
            "classe" if lang == "it" else "class":
                CLASS_LABELS.get(klass, (klass, klass))[index],
            "trattamento" if lang == "it" else "treatment":
                TREATMENT_LABELS.get(treatment, (treatment, treatment))[index],
            "controllo diagnostico" if lang == "it" else "diagnostic check":
                rule_name(rule_id, lang),
            "che cosa controlla" if lang == "it" else "what it checks":
                rule_description(rule_id, lang),
        })
    return pd.DataFrame(rows)
