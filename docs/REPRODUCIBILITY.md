# Reproducibility

What the program counts, with which parameters, and how to check that the numbers are
still the same. This document contains no new analysis: it restates the definitions of
the supplementary materials of the article (sections S4, S5, S8 and S11) and says where
they sit in the code and in this package. The tools for repeating the measurements are in
the folder [`reproducibility/`](../reproducibility/README.md).

Version described: **GCP 3.1.0**.

---

## 1. The five counting units

The risk, in a program that counts words, is that the same word means different things on
different pages. `src/greek_corpus_pipeline/units.py` defines five units, once only, and
every number shown by the interface declares underneath which one it is using (S11.1).

| unit | what it is |
|---|---|
| `imported_records` | the `word` elements of the XML files whose identifier is an integer (elements whose identifier is not an integer are not imported), punctuation and technical nodes included |
| `active_records` | the imported records that remain after the filters chosen by the user. In the study the filter excludes the technical records and excludes neither punctuation nor non-Greek forms |
| `words` | the imported records that are neither technical nor punctuation: no punctuation, no placeholders written `[n]`, no elliptic or technical nodes |
| `analyzable_links` | the dependencies that start from an active record and have as head an active record of the same sentence: `head` greater than zero, and the pair (sentence key, head) among the pairs (sentence key, identifier) of the active records |
| `analyzable_sentences` | the sentences with a usable structure: a single root that is not structural punctuation (head 0 and a relation other than AuxG, AuxK, AuxX) and no arc pointing to an identifier absent from the sentence; computed on the imported records |

The article and its supplementary materials call the first two units *imported tokens* and
*active tokens*; the program calls the same objects *records* (`imported_records`,
`active_records`, in the interface and in the manifest). The other three names are the same
everywhere.

A record is **technical** when it meets at least one of five criteria, each sufficient on
its own: the attribute `artificial` is filled in; the form is a placeholder consisting of a
number in square brackets such as `[0]` (the filter accepts any number; the largest in the
data is `[16]`); the form is the lacuna marker `G` or `G?` (a lower-case `g` is also
accepted but does not occur); form and morphological tag are both empty; the tag begins with
`z`. **Punctuation** has two tests and the tag takes precedence: (1) the tag begins with `u`;
(2) the relation is AuxG, AuxK or AuxX and the tag says nothing usable (it does not have nine
characters, or its first position carries no interpretable value of the inventory; the
documented local extensions such as `b` count as interpretable).

Two properties to keep in mind when reading a count:

- `active_records` **depends on the filters**. If the user switches the exclusion of technical
  records off, the elliptic nodes come back in, and rightly so: the structural diagnosis
  needs them.
- `words` **does not depend on the filters**. Being a word of the text is a property of the
  record, not a display preference. With the filter of the study the words are therefore the
  active records minus the punctuation among them: 616,646 − 67,734 = 548,912 in Gorman and
  274,609 − 36,196 = 238,413 in Pedalion.

The **analysable sentences** are not the “sentences with at least one evaluated arc” of
Table 2 of the article (the denominator of the sentence-level measure of non-projectivity):
the two count different sets (25,994 and 18,235 against 26,377 and 17,984 in Gorman and
Pedalion). A sentence with a single broken arc drops out of the first and stays in the
second. The first unit does not test acyclicity or connectivity.

The **sentence key** is not `sentence_id`, which in Gorman takes 564 distinct values over
26,616 sentences because it numbers the sentence inside its own file. The key is
`units.sentence_key`, the concatenation of source file, document and sentence index.

`tests/test_units.py` checks the definitions — the elementary predicates, the sentence key,
the fact that `words` does not move when the filters change — on a minimal corpus built on
purpose, which contains one instance of every borderline case. The values on the real corpora
are those of the table in § 4, which `reproducibility/scripts/recompute_units.py` recomputes
from the `tokens.parquet` of a run.

---

## 2. The nine numerical parameters

The nine values chosen by the authors (§ 4.3 of the article, Table S4.1) turn a general
criterion into an applicable rule. They do not come from a source. They are written in the
code, not in a configuration file: changing them changes a scientific result, and must leave
a trace.

| parameter | value | module | check |
|---|---|---|---|
| `RARE_RELATION_MIN_SUPPORT` | 200 | `agreement.py` | `rare-relation-for-lemma-and-pos` |
| `RARE_RELATION_MAX_SHARE` | 0.01 | `agreement.py` | `rare-relation-for-lemma-and-pos` |
| `min_form_total` | 25 | `lemma.py` | `lemma-rare-for-form` |
| `max_rare` | 1 | `lemma.py` | `lemma-rare-for-form` |
| `min_major_share` | 0.95 | `lemma.py` | `lemma-rare-for-form` |
| `WHOLE_CORPUS_ENCODING` | 0.50 | `orthography.py` | `corpus-not-nfc` |
| `INDECLINABLE_MINIMUM` | 5 | `postag.py` | `uninflected-lemma` |
| `BARE_RELATION_MINIMUM` | 20 | `syntax.py` | `relation-bare-convention`, `relation-truncated-or-foreign` |
| `BARE_RELATION_SPREAD` | 0.90 | `syntax.py` | `relation-bare-convention`, `relation-truncated-or-foreign` |

The nine values serve **six checks**: `lemma-rare-for-form` uses three of them;
`rare-relation-for-lemma-and-pos`, `relation-bare-convention` and
`relation-truncated-or-foreign` two each; `corpus-not-nfc` and `uninflected-lemma` one each.
The two thresholds of the bare relation label belong to both twin checks, because they decide,
token by token, which of the two fires.

What the parameters decide:

- `rare-relation-for-lemma-and-pos` (universe: words; group: lemma and part of speech; relation
  in its base form). A group enters the check if it has at least 200 occurrences; within an
  eligible group a relation is reported if it accounts for at most 1% of the occurrences of the
  group.
- `lemma-rare-for-form` (universe: words; key: form and part of speech). The pair enters the
  check if it has at least 25 occurrences; it is reported if one lemma occurs **once only**
  against a majority lemma covering at least 95% of the occurrences. `max_rare = 1` is not a
  statistical threshold but **the definition of the check**: varying it would not widen a
  window, it would ask another question.
- A label written without the function that should precede it, such as `CO`, is treated as a
  systematic fact of the resource if it occurs at least 20 times and in at least 90% of the
  documents (`relation-bare-convention`, a case to check, no proposed correction); below
  either threshold it is reported by `relation-truncated-or-foreign` as a verifiable violation.
- `corpus-not-nfc` reports once the encoding of the whole resource when at least half of the
  active tokens are not in NFC; `uninflected-lemma` reports once per lemma the nominal lemmas
  that never carry a case, from five occurrences upwards.

Besides the nine parameters, a few fixed limits in the code decide which strings or structures
a check considers at all (Table S4.2 of the supplement). They are not parameters, are not
varied and are not attributed to an authority.

---

## 3. The sensitivity analysis (S5)

Four parameters of two checks were varied: the minimum support and the maximum share of
`rare-relation-for-lemma-and-pos`, and the minimum support and the minimum majority of
`lemma-rare-for-form`. Fifteen configurations, the adopted ones included, were evaluated on
the six strata, for 90 evaluations. **No official parameter was changed as a consequence.**
The evaluations were obtained by calling the two checks with alternative arguments, in memory;
the two adopted configurations reproduce exactly the findings of the two checks in the six runs.
A finding is identified by source file, document, sentence index and token index.

**`rare-relation-for-lemma-and-pos`: support 100 or 200 × share 0.5%, 1%, 2%** (36 evaluations,
Table S5.1). Nesting holds along both axes: at fixed support, share 0.5% is contained in 1% and
1% in 2%; at fixed share, support 200 is contained in support 100. The more permissive
configurations keep 100% of the adopted findings; the more restrictive ones keep between 24.5%
and 73% of them. The share decides and the support adjusts. At support 200 Gorman gives 1,047,
1,548, 1,810, 2,765, 3,263, 3,462, 5,327, 6,194 and 8,808 findings at shares of 0.25%, 0.5%,
0.75%, 1%, 1.25%, 1.5%, 2%, 2.5% and 3%.

**`lemma-rare-for-form`: support 15, 25 or 50 × majority 90%, 95%, 98%** (54 evaluations,
Table S5.2). `max_rare` is fixed at one. Nesting holds along each axis. Only one evaluation both
loses and adds findings — support 50 with majority 90% on Gorman, 42 lost and 5 new — and in
it the two parameters pull in opposite directions. Since at most one rare occurrence is allowed,
every finding is a single token: the 102 findings of Gorman are 102 distinct cases. Three strata
give zero in all nine configurations: the automatic strata of the two samples and the manual
stratum of the confirmation sample.

**Why share and support must be declared together.** The share alone implies a minimum support,
and the declared support matters only when it exceeds it. In `rare-relation-for-lemma-and-pos`
a relation seen once is rare if 1/total ≤ share, that is, total ≥ 1/share: share 0.5% implies a
support of 200, which is why the two supports give identical rows in Table S5.1; share 1% implies
100, so that the adopted support of 200 is binding. In `lemma-rare-for-form` with `max_rare = 1`
a pair of total *T* has at most *T* − 1 occurrences of the majority lemma, and (*T* − 1)/*T* ≥
share gives *T* ≥ 1/(1 − share): majority 98% implies a support of 50, which is why the three
supports give identical rows at 98% in Table S5.2.

The other parameters were not varied. `max_rare` is a definition; the four remaining ones — the
50% share of `corpus-not-nfc`, the five occurrences of `uninflected-lemma` and the two diffusion
thresholds of the bare label — separate two qualitative situations and decide which of two twin
checks fires; their sensitivity has not been measured. In neither analysis do the verifiable
violations move: the two checks varied are cases to check.

To repeat the analysis: `reproducibility/scripts/sensitivity_analysis.py` (see
[`reproducibility/README.md`](../reproducibility/README.md)).

---

## 4. The reference results

Six strata, with the filter configuration adopted in the study: technical records excluded,
punctuation and non-Greek forms included (Table S11.1 of the supplement). The column “active
checks” gives the number of checks that produce at least one finding in the stratum, not the
number of checks applied, which is 77 throughout.

| stratum | `imported_records` | `active_records` | `words` | `analyzable_links` | `analyzable_sentences` | findings | active checks | nuclei | findings fingerprint |
|---|---|---|---|---|---|---|---|---|---|
| Gorman | 625,176 | 616,646 | 548,912 | 513,369 | 25,994 | 101,047 | 56 | 33,652 | `971c8056de40` |
| Pedalion | 281,245 | 274,609 | 238,413 | 213,144 | 18,235 | 29,515 | 51 | 13,848 | `a037eae69887` |
| GLAUx automatic | 300,292 | 292,567 | 251,994 | 223,872 | 17,982 | 13,168 | 22 | 11,347 | `6560da673493` |
| GLAUx manual | 21,652 | 21,107 | 17,834 | 16,713 | 1,745 | 2,400 | 20 | 996 | `e9c9e830c5b6` |
| GLAUx confirmation automatic | 273,354 | 267,313 | 231,725 | 206,955 | 13,227 | 11,259 | 20 | 11,051 | `a3efc2fa2260` |
| GLAUx confirmation manual | 28,666 | 28,143 | 24,351 | 21,769 | 1,979 | 3,188 | 20 | 1,041 | `771c3f3dbedd` |

The findings are **160,577** in all, produced by the **77 checks** of the catalogue
(`data/catalogo_controlli.csv`; the reference texts are 77 in `data/canonical_check_texts.json`).
Machine-readable copies of these and of the following tables are in `reproducibility/reference/`.

The shares of findings that are verifiable violations — 1.9% in Gorman (1,914 of 101,047) and
4.6% in Pedalion (1,361 of 29,515) — are shares **of the findings**, not of the records: the
denominator is the number of findings of the stratum.

**Variation nuclei, by level** (Table S8.1). A nucleus is a shared context that receives
different annotations in different occurrences.

| stratum | morphology | tag positions | context | dependencies | lemmas | total |
|---|---|---|---|---|---|---|
| Gorman | 6,159 | 8,259 | 3,526 | 13,416 | 2,292 | **33,652** |
| Pedalion | 3,427 | 4,534 | 735 | 4,432 | 720 | **13,848** |
| GLAUx automatic | 2,956 | 3,600 | 586 | 4,158 | 47 | **11,347** |
| GLAUx manual | 382 | 495 | 3 | 98 | 18 | **996** |
| GLAUx confirmation automatic | 2,554 | 3,284 | 580 | 4,623 | 10 | **11,051** |
| GLAUx confirmation manual | 297 | 345 | 22 | 372 | 5 | **1,041** |

---

## 5. The fingerprints

The word “fingerprint” names four different objects, which are not comparable with one another
(S11.3):

- The **findings fingerprint** of a stratum is the first twelve hexadecimal characters of the MD5
  of a list of lines, one per finding, each made of four fields separated by the character
  U+241F (`␟`): the identifier of the check, the document, the identifier of the sentence and
  the identifier of the token in the XML file (`rule_id · document_id · sentence_id ·
  token_id`). The lines are sorted as strings, duplicates included, and joined by a line break,
  without a final line break; the procedure is that of the function `_impronta` of
  `tests/test_diagnosi.py`. It identifies which check reported which position, independently of
  the order in which the findings are output and of the text with which they are described. It
  does not cover the values diagnosed, the parameters of the diagnosis, the proposed corrections
  or the severity, nor the descriptive columns (`anomaly_name`, `anomaly_description`, `issue`):
  in the tables that a run writes these columns are in Italian whatever the language of the
  interface, and the interface shows them in its current language.
- The **input fingerprint** of a stratum identifies the XML files that the run read: the first
  sixteen hexadecimal characters of the SHA-256 of a list of lines “file name:SHA-256 of the
  file”, one per XML file, sorted and joined by a line break. The values are given in
  `reproducibility/reference/inputs.csv`; `reproducibility/scripts/input_fingerprint.py`
  recomputes them.
- The **corpus fingerprint** (sixteen characters) identifies the text supplied to a model, up to
  Unicode normalisation, and the **fingerprint of the model's resources** the names and sizes of
  the files of the model (Table S10.1 of the supplement).
- A fifth fingerprint is used only internally, to recognise the resources for which the program
  distributes metadata (`data/liste/risorse-con-metadati.json`).

---

## 6. The corpora and the models are not in this package

**No corpus and no model is distributed with the program.** The six strata measured above come
from public resources of third parties, each with its own licence, its own authors and its own
history of revisions: Gorman Trees, Pedalion Trees and the GLAUx corpus. Those resources
**continue to be revised by their authors**: a version downloaded today may differ from the one
measured here, and a fingerprint makes it possible to verify the identity of a copy, not to
recover a version that is no longer available. Where to obtain the exact files — repository,
commit, archive checksum, destination folder — and under which licence, is written in
[`reproducibility/ACQUISITION.md`](../reproducibility/ACQUISITION.md).

The program does not perform the draw of the two GLAUx samples: it reads its result, the list of
the forty texts in `data/glaux_sample.csv`, which is also the list of the files it downloads. The
procedure is declared in the docstring of `src/greek_corpus_pipeline/glaux_sample.py` and in S9 of the
supplement (a pool of 338 texts taken from `data/glaux_metadata.csv`; `random.seed(20260814)` and
`random.sample` of twenty texts; then `random.seed(20260815)` and twenty texts out of the 318 that
remain, sorted by TLG identifier). `reproducibility/scripts/glaux_sample_draw.py` repeats it with the
standard library alone and compares the result with `data/glaux_sample.csv`; only the sequence of
`random()` is guaranteed to be the same across versions of Python, not that of `sample()`, so the
script prints the version it ran under.

---

## 7. The environment of the measurements

The six runs of the study were carried out on a Windows machine with Python 3.14.6, pandas
3.0.5, NumPy 2.5.3 and PyArrow 25.0.1, with version 3.1.0 of the program. They were repeated on a
Linux system with the same versions and the same XML files: the repetition reproduces cell by
cell the tokens, the findings with their proposals, the arcs and the tables of the variation
nuclei of all six strata and, with Stanza 1.14.0 (PyTorch 2.14.0), UDPipe 1.4.0.1 and the model
files listed in `reproducibility/ACQUISITION.md`, the four comparison tables and their
evaluations (S11.2).

---

## 8. Running the tests

```bash
.venv/bin/pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q -rs
```

Most of the tests run on synthetic data and on hand-written fragments and pass without
downloading anything: they are the ones that verify the behaviour of the program. On Linux, with
Python 3.14.6 and pandas 3.0.5 and without the optional model libraries, the suite ends with
**775 passed, 24 skipped** (about three minutes on two processor cores). The tests that skip
themselves do so saying why (`-rs`): they need the six frozen corpora (`GCP_CORPORA`), the
UDPipe model (`GCP_UDPIPE_MODEL`) and the library `ufal.udpipe`, or a quiet machine on which to
measure timings (`GCP_RESPONSIVENESS_TEST=1`, to be run alone).

The folder indicated by `GCP_CORPORA` must have this shape:

```
<GCP_CORPORA>/
  runs/
    run-gorman/tokens.parquet
    run-pedalion/tokens.parquet
    run-glaux_auto/tokens.parquet
    run-glaux_man/tokens.parquet
    run-glaux_conf_auto/tokens.parquet
    run-glaux_conf_man/tokens.parquet
  giro/
    findings-gorman.parquet
    findings-pedalion.parquet
    findings-glaux_auto.parquet
    findings-glaux_man.parquet
    findings-glaux_conf_auto.parquet
    findings-glaux_conf_man.parquet
```

`runs/` holds the prepared token table of each stratum, as the program writes it in
`workspace/runs/<run>/tokens.parquet`. `giro/` (the name is the one the tests use; it is the
folder of the detection round) holds the findings of the detection step **as the checks produce
them**, that is, before the last step of `run_detection`, the function `proposte.allinea_proposte`,
which removes the suggested corrections of the checks whose treatment is manual and restores only
the verified repairs. The tests that look at what a check itself produces — for instance that
`lemma-rare-for-form` names the majority lemma — need that raw output; the `findings.parquet` of a
run is the aligned one and is not what they expect.

`reproducibility/scripts/build_gcp_corpora_folder.py` builds the folder from a re-run:

```bash
python reproducibility/scripts/build_gcp_corpora_folder.py --workspace W --output C
export GCP_CORPORA=C        # Windows: set GCP_CORPORA=C
QT_QPA_PLATFORM=offscreen python -m pytest tests -q -rs
```

where `W` is the workspace given to `rerun_diagnosis.py` (§ 9). With the folder in place the tests
that need the six corpora run instead of skipping.

---

## 9. Repeating the measurements

The order of the steps, the commands and the files to compare are in
[`reproducibility/README.md`](../reproducibility/README.md); the mapping between each claim of the
article and of the supplement and the way to verify it is in
[`reproducibility/REVIEWER_GUIDE.md`](../reproducibility/REVIEWER_GUIDE.md). In short: acquire the
XML files (ACQUISITION.md), run the diagnosis and the variation analysis on each stratum
(`rerun_diagnosis.py`), and compare with the tables of § 4 with `compare_with_reference.py`. A copy of
the study's runs is not needed to check the units, the findings, the nuclei or the fingerprints,
only the XML files. What cannot be checked without the runs of the study is the statement of S11.2
that a repetition reproduces them **cell by cell**: the reference tables hold the numbers, the
fingerprints and the four-field key of every finding, not the tables of the runs, which reproduce the
annotated text of the corpora and are not distributed.
