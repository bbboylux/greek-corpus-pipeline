"""Where morphology and syntax must agree — and where they demonstrably don't.

Two kinds of check live here.

**Agreement and case.**  An attribute agrees with its head in gender, number and case.
Here the machine must be careful, because Greek has legitimate ways of leaving
two adjacent words unmatched, and each of them had to be recognised or the
check drowns in false positives: the adnominal genitive, the indeclinable
cardinals, the dual standing beside a plural, and the quantifiers and
distributives (εἷς, ἕκαστος, ἄμφω) that Greek uses substantivally, where they
are the attribute of nothing.  Those are excluded by name, not silenced by a
threshold.  The case of a subject and of an object is checked against the
constructions in which Greek allows it (``case-subject``, ``case-object``).

Three checks that look like natural candidates are deliberately absent.
*Subject and verb disagreeing in number* would fire on constructions Greek
allows and on subjects that are not the subject of the verb they hang from, and
no whitelist makes the remainder trustworthy.  *Predicate nominal in an
unexpected case* rests on a generalisation that is not true of Greek: with an
infinitive, a participle, an accusative-with-infinitive, an implicit copula or a
verb of naming, the predicate nominal is legitimately in almost any case, and
"PNOM is nominative" describes a textbook rather than a corpus.  *Internally
inconsistent tag* measures the difference between two defensible tagging
conventions, not a defect.

**Relations measured on the corpus.**  Instead of hard-coding which relations
a word may carry, the module *measures* them: for every pair of lemma and part
of speech with at least two hundred words in the run it builds the observed
distribution of the base relations, and reports the words whose relation has a
share of at most 1% of the pair (``rare-relation-for-lemma-and-pos``).  This is
the generalisation Boyd, Dickinson and Meurers list as future work — "encoding
a combination of the lemma and morphological information or part of speech"
(2008, authors' preprint: 24).  Rarity is not error: the check is a case to
verify and proposes no correction.
"""
from __future__ import annotations

import unicodedata as _unicodedata

import numpy as np
import pandas as pd

from .agdt_schema import (
    CASE_SLOT,
    POSITION_VALUES,
    GENDER_SLOT,
    MOOD_SLOT,
    NUMBER_SLOT,
    POS_SLOT,
    TAG_LENGTH,
    base_relation,
    elliptic_token_mask,
    is_indeclinable_numeral,
    is_non_agreeing_quantifier,
)
from . import issue_testi
from .fastmap import build_frame, map_unique, mask_unique
from .normalise import nfc
from .units import is_word
from .rule_catalog import default_auto_apply, rule_description, rule_name, rule_severity
from .syntax import build_effective_head_index, build_head_index

#: Impersonal verbal adjectives in -τέος: γραπτέον, ἀποκριτέον, φροντιστέον. They are
#: neuter nominatives by construction and govern their own clause, so an OBJ in the
#: nominative on one of these says nothing about case.
_VERBAL_ADJECTIVE_ENDINGS = ("τέον", "τέος", "τέα", "τέου", "τέῳ", "τέων")


def _is_verbal_adjective(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = _unicodedata.normalize("NFC", value.strip())
    return len(text) > 4 and text.endswith(_VERBAL_ADJECTIVE_ENDINGS)


POS_VALUES = set(POSITION_VALUES[0])

FINDINGS_COLUMNS = [
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


def empty_findings() -> pd.DataFrame:
    return pd.DataFrame(columns=FINDINGS_COLUMNS)


def _make(
    subset: pd.DataFrame,
    rule_id: str,
    issue_params: "object | pd.Series" = None,
    *,
    issue_key: "str | pd.Series | None" = None,
    suggested_postag: object = pd.NA,
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
    columns["suggested_postag"] = suggested_postag
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


def _discordanze(chiave: object) -> str:
    """From “6:m:f;2:s:p;” to the parameters of the finding.

    The key is built with vectorised operations over the whole column; here it is read
    once per distinct combination, and there are only a few hundred.
    """
    voci = []
    for pezzo in str(chiave or "").split(";"):
        if not pezzo:
            continue
        campi = pezzo.split(":")
        if len(campi) != 3:
            continue
        voci.append({"slot": int(campi[0]), "modificatore": campi[1],
                     "testa": campi[2]})
    return issue_testi.serializza({"discordanze": voci})


def _slots(tokens: pd.DataFrame) -> pd.DataFrame:
    """Explode the tag into nine string columns, once, for everything below.

    "Usable" means nine characters *and* a first character drawn from the part
    of speech inventory.  The length test alone is not enough: the literal
    string ``undefined`` is exactly nine characters long and occurs in real
    corpora, and without this guard it would be read as a tag whose every slot
    is invalid — one malformed value manufacturing nine findings.

    Which character sits in which slot depends on the tag and on nothing else,
    and the Gorman corpus spells 625,176 tokens with 1,185 distinct tags: slicing
    and masking the whole column nine times over asked the same question five
    hundred times.  Answering it once per distinct tag and gathering the answers
    back takes this from 0.32 s to 0.03 s, and five different checks call it.
    """
    tags = tokens["postag"].astype("string")
    codes, uniques = pd.factorize(tags, use_na_sentinel=False)
    distinct = uniques.to_numpy()
    usable = np.fromiter(
        (isinstance(tag, str) and len(tag) == TAG_LENGTH and tag[0] in POS_VALUES
         for tag in distinct),
        dtype=bool, count=len(distinct))

    # ``take`` on the small array, rather than building the full column and
    # asking pandas to validate 625,176 elements it has already seen.
    data: dict[str, object] = {"_ok": pd.array(usable, dtype="boolean").take(codes)}
    for index in range(TAG_LENGTH):
        characters = [tag[index] if ok else "" for tag, ok in zip(distinct, usable)]
        data[f"s{index}"] = pd.array(characters, dtype="string").take(codes)
    return pd.DataFrame(data, index=tokens.index)


# ---------------------------------------------------------------------------
# 1. Agreement
# ---------------------------------------------------------------------------

def check_agreement(tokens: pd.DataFrame) -> pd.DataFrame:
    """Attribute↔head and subject↔verb agreement, with the Greek exceptions."""
    needed = {"postag", "relation", "token_id", "head"}
    if tokens.empty or not needed <= set(tokens.columns):
        return empty_findings()

    work = tokens.copy()
    work["_sent"] = (work["source_file"].astype("string").fillna("") + "␟"
                     + work["document_id"].astype("string").fillna("") + "␟"
                     + work["sentence_index"].astype("string").fillna(""))
    work["_tid"] = pd.to_numeric(work["token_id"], errors="coerce")
    work["_head"] = pd.to_numeric(work["head"], errors="coerce")
    # Look through coordinators, appositions, prepositions and subordinating
    # conjunctions: a conjunct agrees with what the coordination depends on,
    # not with the coordinator.
    structural_index = build_head_index(work)
    head_index = build_effective_head_index(work, structural_index)

    slots = _slots(work).reset_index(drop=True)
    work = work.reset_index(drop=True)
    head_index = head_index.reset_index(drop=True)
    structural_index = structural_index.reset_index(drop=True)

    # Nine of these, each walking the 625,176 head positions in Python and
    # reading a slot column one element at a time, would be slow: a single numpy
    # gather answers them.  Five of the nine ask for a slot already computed.
    head_rows = head_index.to_numpy()
    structural_rows = structural_index.to_numpy()
    gathered: dict[int, pd.Series] = {}
    gathered_structural: dict[int, pd.Series] = {}

    def _structural_slot(index: int) -> pd.Series:
        """The slot of the *written* head, without looking through anything.

        The subject-case check needs both. The effective head is right for
        agreement — a conjunct agrees with what the coordination depends on —
        but wrong here: in φησὶ τὸν ἄνδρα ἐλθεῖν καὶ ἰδεῖν the accusative
        subject hangs from the coordination of the two infinitives, and looking
        through the coordinator lands on the matrix indicative. The
        construction is a perfectly regular accusative-with-infinitive, and the
        check called it an error six hundred times on Gorman for that reason.
        """
        ready = gathered_structural.get(index)
        if ready is None:
            column = slots[f"s{index}"].to_numpy()
            ready = pd.Series(
                np.where(structural_rows >= 0, column[structural_rows], ""),
                index=work.index, dtype="string")
            gathered_structural[index] = ready
        return ready

    def _head_slot(index: int) -> pd.Series:
        ready = gathered.get(index)
        if ready is None:
            column = slots[f"s{index}"].to_numpy()
            ready = pd.Series(
                np.where(head_rows >= 0, column[head_rows], ""),
                index=work.index, dtype="string")
            gathered[index] = ready
        return ready

    relations = work["relation"].astype("string").fillna("")
    base = map_unique(relations, base_relation)
    parts: list[pd.DataFrame] = []

    # ── Attribute agreement ───────────────────────────────────────────────
    # Articles, adjectives, participles and numerals functioning as ATR agree
    # with a nominal head — when Greek asks them to.  Four constructions in
    # which it does not are excluded below, and each of them was measured on
    # Gorman and Pedalion before being written in.
    modifier = (
        slots["_ok"]
        & slots["s0"].isin(set("altm"))
        & (base == "ATR")
    )
    head_pos = _head_slot(POS_SLOT)
    modifier &= head_pos.isin(set("np"))
    # (i) The adnominal genitive is a different construction, not a failure.
    adnominal_genitive = slots[f"s{CASE_SLOT}"] == "g"
    modifier &= ~adnominal_genitive

    if "lemma" in work.columns:
        lemmas = work["lemma"].astype("string").fillna("")
        head_lemmas = pd.Series(
            np.where(head_rows >= 0, lemmas.to_numpy()[head_rows], ""),
            index=work.index, dtype="string")
        # (ii) The indeclinable cardinals — δύο, πέντε, εἴκοσι, ἑκατόν … — have
        # no number, gender or case to agree in, so asking them to agree is
        # asking a question the language does not have.  160 of the 754
        # findings on the two corpora, all of them correct annotation.  The
        # head is exempted too: an article attached to δύο cannot match a
        # number δύο does not carry.
        indeclinable = (mask_unique(lemmas, is_indeclinable_numeral)
                        | mask_unique(head_lemmas, is_indeclinable_numeral))
        # (iii) Quantifiers and distributives used substantivally: εἷς, ἕκαστος,
        # ἑκάτερος, ἄμφω.  ἑνὶ … ὄνομα is not an article in the wrong case, it
        # is εἷς standing on its own with an elided noun; καθ᾽ ἕκαστον is the
        # attribute of nothing.  See the note in ``agdt_schema``.
        substantival = mask_unique(lemmas, is_non_agreeing_quantifier)
        modifier &= ~(indeclinable | substantival)

    # (iv) An elliptic node is a word the annotator supplied because the text
    # does not have it.  Its tag is a reconstruction and its attachment is a
    # convention, so a disagreement with it says nothing about the corpus.
    elliptic = pd.Series(elliptic_token_mask(work), index=work.index)
    elliptic_head = pd.Series(
        np.where(head_rows >= 0, elliptic.to_numpy()[head_rows], False),
        index=work.index)
    modifier &= ~(elliptic | elliptic_head)

    if modifier.any():
        head_gender = _head_slot(GENDER_SLOT)
        head_number = _head_slot(NUMBER_SLOT)
        head_case = _head_slot(CASE_SLOT)
        problems = pd.Series("", index=work.index, dtype="string")
        for slot_index, head_values in (
            (GENDER_SLOT, head_gender),
            (NUMBER_SLOT, head_number),
            (CASE_SLOT, head_case),
        ):
            own = slots[f"s{slot_index}"]
            # 'c' (common gender) agrees with masculine and feminine alike.
            compatible = (
                (own == head_values)
                | (own == "-") | (head_values == "-") | (head_values == "")
                | ((slot_index == GENDER_SLOT) & ((own == "c") | (head_values == "c")))
            )
            if slot_index == NUMBER_SLOT:
                # (v) The dual keeps company with the plural: ἄμφω (dual) with
                # τὰ ἔθνη (plural) is ordinary Greek, not a mistake, and the
                # two forms alternate inside a single sentence in Attic prose.
                compatible = compatible | (
                    ((own == "d") & (head_values == "p"))
                    | ((own == "p") & (head_values == "d"))
                )
            bad = modifier & ~compatible
            # The key carries the number of the slot, not its name: the Italian or
            # English name is written by whoever displays the sentence.
            detail = (str(slot_index) + ":" + own.fillna("-") + ":"
                      + head_values.fillna("-") + ";")
            problems = problems.mask(bad, problems.fillna("") + detail)
        flagged = modifier & (problems.fillna("").str.len() > 0)
        if flagged.any():
            # The distinct combinations of disagreements are two hundred over ten
            # thousand rows: the parameters are written once per combination.
            params = map_unique(problems[flagged], _discordanze)
            parts.append(_make(work[flagged], "agreement-modifier",
                               params, severity="sospetto"))

    # ── Case licensed by the syntactic function ───────────────────────────
    nominal = slots["_ok"] & slots["s0"].isin(set("naplm"))
    case = slots[f"s{CASE_SLOT}"]

    # A subject is nominative — except where the AGDT 2.0 guidelines themselves
    # say otherwise. § 3.2 SBJ lists them: the subject is a noun or equivalent
    # "bearing the nominative case, or the genitive case (in the genitive
    # absolute), or the accusative (in the infinitive clause or with the
    # supplementary participle)". Three consequences for this check.
    #
    # (i) The licence for a participial head is not limited to the genitive and
    #     the accusative absolute. A supplementary participle governs its
    #     subject in whatever case the participle itself stands in, and the
    #     dative is ordinary Greek — συνῄδει αὐτῷ ποιοῦντι. Asking only about
    #     the genitive and the accusative left sixteen dative subjects under a
    #     dative participle in the results, all of them correct annotation. The
    #     test is therefore "the head is a participle and the two agree in
    #     case", which subsumes the genitive absolute and the accusative
    #     absolute instead of listing them.
    #
    # (ii) Gorman pads unused tag positions with ``_`` rather than ``-``. The
    #      case slot of an indeclinable was therefore read as a case, and 77
    #      findings on Gorman were tokens with no case at all.
    #
    # (iii) What is left is not an error but a place to look. The guidelines
    #       license genitive and accusative subjects; when one turns up outside
    #       the construction that licenses it, either the case is wrong or the
    #       head is — and the second is at least as likely as the first. Dative
    #       and vocative subjects are a different matter: the guidelines admit
    #       neither, so those are reported as unlicensed by the scheme.
    not_a_case = {"n", "-", "_", "", None}

    def _licensed_by(mood: pd.Series, head_case: pd.Series) -> pd.Series:
        aci = (mood == "n") & (case == "a")
        participial = (mood == "p") & (case == head_case) & ~case.isin(not_a_case)
        return aci | participial

    licensed = (
        _licensed_by(_head_slot(MOOD_SLOT), _head_slot(CASE_SLOT))
        | _licensed_by(_structural_slot(MOOD_SLOT), _structural_slot(CASE_SLOT))
    )

    # (iv) When the governing verb is coordinated, neither head answers. The
    #      subject hangs from the coordinator, so the structural head is καί and
    #      has no mood at all, while the effective head looks *through* the
    #      coordination and lands on whatever the coordination itself depends
    #      on — the matrix indicative. The verbs that actually govern the
    #      subject are the conjuncts: τῶν δὲ πρεσβευτῶν εὐδοκουμένων … καὶ
    #      φασκόντων is a genitive absolute with two participles, and τοὺς
    #      ἡγεμόνας … διαπέμπεσθαι … καὶ ἥξειν an infinitive clause with two
    #      infinitives. Both were counted as errors. The licence is therefore
    #      extended to the _CO children of the written head.
    conjunct = relations.str.endswith("_CO", na=False).to_numpy()
    parent_rows = structural_rows
    mood_all = slots[f"s{MOOD_SLOT}"].fillna("").to_numpy()
    case_all = slots[f"s{CASE_SLOT}"].fillna("").to_numpy()

    def _codepoints(values) -> np.ndarray:
        text = np.asarray(values, dtype="U1")
        return text.view(np.int32).reshape(len(text), -1)[:, 0] if len(text) else \
            np.zeros(0, dtype=np.int32)

    usable_conjunct = conjunct & (parent_rows >= 0)
    infinitive_parents = np.unique(
        parent_rows[usable_conjunct & (mood_all == "n")])
    participial = usable_conjunct & (mood_all == "p") & (case_all != "")
    participial_codes = np.unique(
        parent_rows[participial].astype("int64") * 256
        + _codepoints(case_all[participial]).astype("int64"))

    own_codes = (parent_rows.astype("int64") * 256
                 + _codepoints(case_all).astype("int64"))
    coordinated = pd.Series(
        ((case == "a").to_numpy(dtype=bool) & np.isin(parent_rows, infinitive_parents))
        | (np.isin(own_codes, participial_codes) & ~case.isin(not_a_case).to_numpy(dtype=bool)),
        index=work.index)
    licensed = licensed | coordinated

    # (v) A head that carries no tag settles nothing. The subject of a genitive
    #     absolute whose participle was elided hangs from an elliptic node —
    #     [0], [2] — and there is no mood there to read. Flagging those asks the
    #     reader to adjudicate a construction the corpus has deliberately left
    #     implicit.
    head_pos_slot = _head_slot(POS_SLOT)
    structural_pos = _structural_slot(POS_SLOT)
    headless = (head_pos_slot.fillna("") == "") & (structural_pos.fillna("") == "")

    admitted_by_scheme = case.isin({"g", "a"})
    bad_subject = (
        nominal & (base == "SBJ")
        & ~case.isin(not_a_case)
        & ~licensed
        & ~headless
    )
    if bad_subject.any():
        # Two different explanations, two keys: the case allowed in one of the three
        # constructions and the case that the scheme does not provide at all. The
        # observed case is not among the parameters: it is the eighth slot of the tag.
        unlicensed = ~admitted_by_scheme[bad_subject]
        chiave = pd.Series("case-subject.tre-costruzioni",
                           index=work.index[bad_subject], dtype="string")
        chiave = chiave.mask(unlicensed, "case-subject.mai-previsto")
        parts.append(_make(work[bad_subject], "case-subject",
                           issue_key=chiave, severity="sospetto"))

    # The predicate nominal is not checked here: the rule that PNOM is
    # nominative outside an infinitive or a participle is not true of Greek.  The
    # accusative-with-infinitive, the implicit copula, verbs of naming and
    # calling (καλοῦσιν αὐτὸν βασιλέα) and every predicative under a governed
    # noun put the predicate nominal in a case that check would call
    # impossible, and there is no defensible way to separate the few real
    # errors from them.

    # ── OBJ in the nominative or the vocative ────────────────────────────────
    #
    # The rule says “direct object in the nominative: Greek governs the
    # accusative, genitive or dative”, and the premise is false. The guidelines
    # define OBJ as “any dependent which is taken to be an argument of
    # the verb, adjective, or adverb (excluding, of course, arguments which are
    # captured by other labels, such as SBJ)” (AGDT 2.0, § 3.3): not “the direct
    # object”, and not necessarily a noun. Under OBJ the same guidelines put the
    # infinitive, the supplementary participle, the complement clause, the
    # substantivised relative clause and the prepositional phrase, and the head
    # of a clause carries the case that belongs to it on its own account.
    #
    # Three classes of false positives are excluded:
    #
    #   * impersonal verbal adjectives in -τέος -τέον -τέα, which are neuter
    #     nominatives by definition — γραπτέον, ᾀστέον, ἀποκριτέον,
    #     φροντιστέον — and which govern their clause instead of being governed;
    #   * clause heads, recognisable because they have a subject or an
    #     object of their own among their children;
    #   * on Gorman, the underscore: the rule asked for a case “other than
    #     a, g, d, -” and the character “_” of the convention of that corpus
    #     fell within the condition, for 72 findings that are the same thing
    #     already counted by underscore-person-number.
    #
    # What remains is an indicative check, not proof of error, and its class
    # reflects that.
    verbal_adjective = mask_unique(
        work["form"] if "form" in work.columns else pd.Series("", index=work.index),
        _is_verbal_adjective)
    lemma_adjective = mask_unique(
        work["lemma"] if "lemma" in work.columns else pd.Series("", index=work.index),
        _is_verbal_adjective)
    clause_head = np.zeros(len(work), dtype=bool)
    if len(work):
        argument_child = np.asarray(base.isin({"SBJ", "OBJ", "PNOM"}), dtype=bool)
        parents = head_index.to_numpy()
        rows = np.nonzero(argument_child & (parents >= 0))[0]
        clause_head[parents[rows]] = True
    bad_object = (
        nominal & (base == "OBJ") & case.isin({"n", "v"})
        & ~pd.Series(verbal_adjective, index=work.index).fillna(False)
        & ~pd.Series(lemma_adjective, index=work.index).fillna(False)
        & ~pd.Series(clause_head, index=work.index)
    )
    if bad_object.any():
        parts.append(_make(work[bad_object], "case-object"))

    return _concat(parts)


#: How many occurrences a (lemma, PoS) pair must have for the proportion of its
#: relations to mean anything. Two hundred is the threshold declared in the
#: article; the sensitivity analysis (supplement S5) compares it with 100 and
#: shows that at a share of 1% the support matters — Gorman gives 2,950 findings
#: at 100 and 2,765 at 200 — while at a share of 0.5% it makes no difference at
#: all. The two parameters must therefore always be declared together.
RARE_RELATION_MIN_SUPPORT = 200

#: Below which share of the occurrences of the group a relation is “rare”. A fraction,
#: not a percentage.
RARE_RELATION_MAX_SHARE = 0.01


def rare_relation_profile(
    words: pd.DataFrame,
    *,
    min_support: int = RARE_RELATION_MIN_SUPPORT,
) -> pd.DataFrame:
    """For each (lemma, PoS) pair, which base relations it carries and how often.

    The group is ``(lemma, part of speech)`` and the outcome is the **base
    relation**, that is, the label without the ``_CO`` and ``_AP`` suffixes.
    Keeping the suffixes would double the count — 5,842 findings against 2,765 in
    Gorman — and what it added would be noise: a rare ``ATR_CO`` says nothing
    about the label, it says that the lemma is seldom found inside a
    coordination.

    The universe is the ``words``. With the active records, that is, with the
    punctuation included, the largest rare combination in Gorman would be
    ``punc1 / u / AuxG``, 602 occurrences: a punctuation mark, not a fact of
    the language.

    There is no restriction on part of speech. Building the profile on particles,
    conjunctions and adverbs only and then looking for rare pairs in *all* the
    tokens would put findings on prepositions, whose behaviour would never have
    been profiled. Profile and domain coincide by construction, because the key
    of the profile is also the key of the search.
    """
    colonne = ["lemma", "pos", "relazione", "occorrenze", "totale", "%"]
    needed = {"lemma", "relation"}
    if words is None or words.empty or not needed <= set(words.columns):
        return pd.DataFrame(columns=colonne)

    slots = _slots(words)
    pos = slots["s0"].astype("string").fillna("")
    lemma = map_unique(words["lemma"].astype("string").fillna(""), nfc)
    relation = map_unique(words["relation"].astype("string").fillna(""), base_relation)

    usable = np.asarray((lemma != "") & (pos != "") & (relation != ""), dtype=bool)
    if not usable.any():
        return pd.DataFrame(columns=colonne)

    frame = pd.DataFrame({
        "lemma": lemma.to_numpy()[usable],
        "pos": pos.to_numpy()[usable],
        "relazione": relation.to_numpy()[usable],
    })
    counts = frame.groupby(["lemma", "pos", "relazione"], sort=False).size()
    counts = counts.reset_index(name="occorrenze")
    totals = counts.groupby(["lemma", "pos"])["occorrenze"].transform("sum")
    counts["totale"] = totals
    counts["%"] = counts["occorrenze"] / totals
    counts = counts[counts["totale"] >= min_support]
    return counts.sort_values(["totale", "lemma", "occorrenze"],
                              ascending=[False, True, False]).reset_index(drop=True)


def check_rare_relation(
    words: pd.DataFrame,
    *,
    min_support: int = RARE_RELATION_MIN_SUPPORT,
    max_share: float = RARE_RELATION_MAX_SHARE,
) -> pd.DataFrame:
    """A relation that this (lemma, PoS) pair almost never carries.

    It queries the three-way table *lemma × PoS × relation* and asks one
    question: given the (lemma, PoS) pair, is this relation rare?  The question
    is asked for every part of speech, not only for particles, conjunctions and
    adverbs.

    What it finds that would otherwise go unseen: in Gorman the article <span>ὁ</span>
    carries the relation ``ADV`` 684 times out of 76,301, 0.90%. This is the
    largest case in the corpus, and a check restricted to particles would not
    look for it because the article is not a particle.

    Rarity does not mean error: a construction can be rare and correct, and
    the absolute number says how much the percentage weighs. The check is
    declared a case to verify and proposes no correction.
    """
    profile = rare_relation_profile(words, min_support=min_support)
    if profile.empty:
        return empty_findings()
    rare = profile[profile["%"] <= max_share]
    if rare.empty:
        return empty_findings()

    slots = _slots(words)
    pos = slots["s0"].astype("string").fillna("")
    lemma = map_unique(words["lemma"].astype("string").fillna(""), nfc)
    relation = map_unique(words["relation"].astype("string").fillna(""), base_relation)

    # The question is the membership of a triple in a set, and the distinct triples are
    # a few tens of thousands against six hundred thousand records: it is asked once per
    # distinct triple and not once per record.
    keys = set(zip(rare["lemma"], rare["pos"], rare["relazione"]))
    triple = pd.Series(list(zip(lemma.to_numpy(), pos.to_numpy(), relation.to_numpy())),
                       index=words.index)
    distinte = triple.drop_duplicates()
    appartiene = {value: value in keys for value in distinte}
    mask = triple.map(appartiene).fillna(False).astype(bool)
    if not mask.any():
        return empty_findings()

    quota = {(l, p, r): (int(n), int(t), float(s))
             for l, p, r, n, t, s in zip(rare["lemma"], rare["pos"], rare["relazione"],
                                         rare["occorrenze"], rare["totale"], rare["%"])}
    subset = words[mask]
    dettaglio = [quota.get(value, (0, 0, 0.0)) for value in triple[mask]]
    quante = pd.Series([d[0] for d in dettaglio], index=subset.index).astype("Int64")
    totali = pd.Series([d[1] for d in dettaglio], index=subset.index).astype("Int64")
    percentuali = pd.Series([round(100.0 * d[2], 2) for d in dettaglio], index=subset.index)

    # The relation cited is the *base* one: out of the 3,683 findings of Gorman and
    # Pedalion it differs from the ``relation`` column in 354, where the corpus writes
    # PNOM_CO and the statistic is computed on PNOM. It is the key of the aggregate, not the label of the token, and
    # for this reason it is among the parameters.
    return _make(subset, "rare-relation-for-lemma-and-pos",
                 issue_testi.parametri(
                     relazione_base=relation[mask].astype("string").fillna(""),
                     occorrenze=quante, totale=totali,
                     percentuale=percentuali),
                 severity="sospetto")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_agreement(
    tokens: pd.DataFrame,
    *,
    words: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The checks on agreement and on the distribution of relations.

    *words* is the universe of the rare-relation check, which by methodological
    decision is the ``words`` unit and not the active records: punctuation
    must not enter a profile of lemmas. If it is passed ``None`` it is derived
    from *tokens*, which is correct but does the work twice if the caller
    already has it.

    The agreement check receives *tokens*, the active records: its universe is
    a different decision from that of the rare-relation check.
    """
    if tokens is None or tokens.empty:
        return empty_findings()
    if words is None:
        words = tokens[np.asarray(is_word(tokens), dtype=bool)]
    return _concat([
        check_agreement(tokens),
        check_rare_relation(words),
    ])
