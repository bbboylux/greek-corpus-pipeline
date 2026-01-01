# Reviewer guide

This guide has one table. Each row is something that a reader needs in order to check an analysis of the article or of
its supplementary materials (S1–S11): the program, the 77 checks, the corpora and the models, a table, a fingerprint.
For every row it says where the article or the supplement declares the element, where it is in this package or how to
obtain it, how it was checked, and what the check gave. Nothing in the column "Outcome" was written from memory: each
outcome is the last line of a script, or a count, from the tests described in section 5.

How to run the scripts is in [README.md](README.md) (this folder). Where the corpora and the models come from is in
[ACQUISITION.md](ACQUISITION.md). Every file of the package, with its SHA-256, is in [`../INVENTORY.md`](../INVENTORY.md).

## Status codes

| Code | Meaning |
|---|---|
| **R0** | recomputed by a script that needs nothing but Python (standard library); level 0 of README.md |
| **R1** | recomputed by running the program on the public XML files; level 1 |
| **R2** | recomputed with Stanza and UDPipe and their model files; level 2 |
| **R3** | recomputed with the CoNLL-U files of UD_Ancient_Greek-Perseus 2.4; level 3 |
| **T** | covered by the test suite of the program (`tests/`) |
| **S** | static: checked by reading the files (that a file exists, what a constant is, what a sentence says) |
| **D** | documentary: an argument, a source or a licence; nothing can recompute it, and the file indicated is the evidence |
| **X** | not in this package: the row says what is needed and where to obtain it |

An outcome is **reproduced** when the script compared every value that the text states and every one matched (the number
of values is given); **not reproduced** when at least one differed (the difference is then given); **not run** when the
check could not be carried out (the reason is then given).

## 1. The package at a glance

| Path | What it holds |
|---|---|
| `src/greek_corpus_pipeline/`, `gui_qt/`, `app_qt.py` | the program (Greek Corpus Pipeline 3.1.0): the checks, the units, the statistics, the comparison with the models, the graphical interface |
| `data/` | the catalogue of the 77 checks (`catalogo_controlli.csv`), the ten closed lists (`liste/`), the list of the forty GLAUx texts (`glaux_sample.csv`) and the metadata of the three corpora |
| `tests/` | the automated tests of the program |
| `docs/` | the two user guides (Word) and `REPRODUCIBILITY.md`, the guide to the figures of the program |
| `reproducibility/` | this kit: scripts, reference tables, README.md, this guide, ACQUISITION.md |
| `supplementary_materials/` | the supplementary materials as submitted (PDF), for reading next to this guide |
| `README.md`, `INSTRUCTIONS.md`, `GUIDE.md` | introduction, short instructions and the full manual of the program |
| `setup.bat`, `run.bat`, `CHECK_INSTALL.bat`, `CHECK_INSTALL.py` | the Windows launchers and the check of the installation |
| `pyproject.toml`, `requirements.txt` | the package definition and the dependencies |
| `LICENSE`, `CITATION.cff` | the licence (MIT) and the citation file; the names of the authors are withheld for the review |
| `INVENTORY.md`, `SHA256SUMS` | every file of the package with its SHA-256; `reproducibility/scripts/verify_sha256sums.py` checks them |

## 2. The matrix

### A. The program and its environment

| # | Element | Declared in | In this package, or how to obtain it | How checked | Outcome |
|---|---|---|---|---|---|
| A1 | The program that produced the results: Greek Corpus Pipeline 3.1.0 | article § 8.1; S11 (opening), S11.2, S11.5 | `src/greek_corpus_pipeline/`, `gui_qt/`, `app_qt.py`, `pyproject.toml`. How this copy differs from the release is in section 6 | S, T, R1 | installs as a package in a clean environment: `pip install -e ".[dev]"` with the versions of the study pinned (Python 3.14.6, pandas 3.0.5, NumPy 2.5.3, PyArrow 25.0.1; E1): installed; `CHECK_INSTALL.py` ends with "No problem: the program is running the code of this folder, version 3.1.0" ; `pip install -e ".[dev]"` (Python 3.13.16, pandas 3.1.1, NumPy 2.5.4, PyArrow 26.0.1; E2): installed; `CHECK_INSTALL.py` ends with "No problem: the program is running the code of this folder, version 3.1.0" ; built as a wheel and installed in a new environment (E5), its command line, run from a folder that is not the project's, gives the run of Pedalion of the study: 9 tables compared, all identical; 2 model table(s) not looked at (--skip-models) |
| A2 | Versions of the study: Python 3.14.6, pandas 3.0.5, NumPy 2.5.3, PyArrow 25.0.1; Stanza 1.14.0 with PyTorch 2.14.0; UDPipe 1.4.0.1 | S11.2 | minimum versions in `pyproject.toml`; the exact versions are given in README.md for `pip install` | R1, R2 | the tests of section 5 ran with the exact versions of the study (environment E1) and with the current ones (E2); what each gave is in section 5 |
| A3 | Python 3.11 or later; Stanza and UDPipe optional (extra `models`) | S11.5 | `pyproject.toml` (`requires-python`, extra `models`) | S | `requires-python = ">=3.11"` and the lowest versions of the dependencies declared (pandas >=2.2, NumPy >=1.26, PyArrow >=14.0, PyQt6 >=6.5, Matplotlib >=3.8): the test suite ran on Python 3.11.17 with pandas 2.2.0, NumPy 1.26.0, PyArrow 14.0.0, PyQt6 6.5.0, Matplotlib 3.8.0 (E4): 775 passed, 24 skipped, none failed; and on Python 3.13.16 (E2) and 3.14.6 (E1) |
| A4 | Windows launchers and instructions | the study ran on Windows (S11.2) | `setup.bat`, `run.bat`, `CHECK_INSTALL.bat`, `CHECK_INSTALL.py`, `INSTRUCTIONS.md`, `README.md` | T (`tests/test_setup_windows.py` reads the text of the launchers) | **not run on Windows**: no Windows machine was available; the launchers are checked only by the static tests, which pass (29 tests of `tests/test_setup_windows.py`) but do not run a launcher |
| A5 | Licence of the program: MIT, with source code, catalogue, closed lists and GLAUx list | S11.5 | `LICENSE` | S | MIT text present; the name of the copyright holder is withheld for the review (section 6) |
| A6 | A suite of automated tests, most of them on synthetic data, a minority needing the six strata, the UDPipe model or an idle machine, skipped with the reason stated | S11.5 | `tests/`; the six strata for the tests are laid out by `reproducibility/scripts/build_gcp_corpora_folder.py` (variable `GCP_CORPORA`) | T | without the six strata: 775 passed, 24 skipped in 2 min 55 s (E1); 775 passed, 24 skipped, 9 warnings in 2 min 51 s (E2); 775 passed, 24 skipped in 3 min 00 s (E4) ; with them: 786 passed, 13 skipped in 3 min 06 s (E1, folder `GCP_CORPORA` built by `build_gcp_corpora_folder.py`); with the UDPipe model and `ufal.udpipe` as well: 798 passed, 1 skipped in 3 min 49 s; the one test left, which measures times, passes when it is run alone (1 passed in 5 s) ; the skipped tests and their reasons are listed in section 5 |
| A7 | User guides | — | `docs/GCP_user_guide.docx`, `docs/GCP_metadata_guide.docx`, `GUIDE.md`, `docs/REPRODUCIBILITY.md` | S, T (`tests/test_resources.py` reads the Word guide) | present, in English; the Word files carry no author in their properties |

### B. The 77 checks

| # | Element | Declared in | In this package, or how to obtain it | How checked | Outcome |
|---|---|---|---|---|---|
| B1 | The catalogue: 77 checks with identifier, name, family (31 morphology, 20 syntax, 16 text, 6 lemma, 4 agreement), class (45 violations, 21 cases to check, 11 variants) and treatment (19 automatic, 58 manual) | article § 4.1, Table 3; S1, Tables S1.1–S1.3 | `data/catalogo_controlli.csv`, `src/greek_corpus_pipeline/rule_catalog.py`, `reproducibility/reference/checks_overview.csv` | R0 | 210 figures compared, all obtained |
| B2 | The specification of each check: the five fields of S2 (Table S2.1) | S2 | the text of each check in `data/catalogo_controlli.csv` (`name_en`, `description_en`) and the module that implements it: `postag.py`, `orthography.py`, `syntax.py`, `agreement.py`, `lemma.py`, `variation.py` | D, T (the tests of each family) | documentary: a specification is an argument; the code that implements it is the thing to read |
| B3 | The authority on which each check rests (five authorities; Tables S3.1 and S3.2, Table 4 of the article) | article § 4.2, Table 4; S3 | none: the sources are the works cited in the references (grammars, guidelines, treebank documentation) | D | documentary; the attribution of an authority to a check is an interpretation and is not recomputed |
| B4 | The nine numerical parameters of six checks (Table S4.1) | article § 4.3; S4 | constants and defaults in `agreement.py`, `lemma.py`, `orthography.py`, `postag.py`, `syntax.py` | R0 (the values are read from the source files without importing the program) | included in the 210 figures of B1: 210 figures compared, all obtained |
| B5 | The fixed limits of the code that delimit the scope of some checks, and their effects (Table S4.2) | S4 | the same modules; `reproducibility/scripts/recompute_fixed_limits.py` takes each limit away in a copy of the program and runs the checks again | R1 | 14 values compared, all reproduced |
| B6 | The sensitivity analysis of the two parameterised checks: 15 configurations × 6 strata = 90 evaluations (Tables S5.1 and S5.2) | article § 4.3; S5 | `reproducibility/scripts/sensitivity_analysis.py`, `reproducibility/reference/table_S5_1_rare_relation.csv`, `table_S5_2_rare_lemma.csv` | R1 | 90 evaluations compared, all identical to the supplement |
| B7 | The ten closed lists: size, the checks that read each, source (Table S6.1) | article § 4.3; S6 | `data/liste/*.json` (each file also declares its source) | R0 for sizes, readers and NFC; D for the sources | included in B1: 210 figures compared, all obtained ; the sources are documentary |
| B8 | What changes when four lists are aligned with Smyth (Table S6.2) | S6 | `reproducibility/scripts/recompute_list_alignment.py` | R1 | 97 values compared, all reproduced |
| B9 | The eleven systematic variants: what each resource writes and the reference with which the program compares it (Table S1.4) | S1 | the 11 checks of class variant in the catalogue; some of the cases are developed in S7 | R0 (count), D (descriptions) | the count is part of B1; the descriptions are documentary |
| B10 | Findings of each of the 77 checks in each stratum (Table S1.1), 160,577 in all, and the key of every finding | S1, S11.1 | `reproducibility/scripts/rerun_diagnosis.py`, `compare_with_reference.py`; `reproducibility/reference/checks_overview.csv`, `finding_keys/` | R1 | 120 values compared in the six strata (units, nuclei, findings, checks, classes, and the fingerprint of the findings): all identical to the study; no finding present in only one of the two |
| B11 | The positional scheme of the AGDT tag (Table 1 of the article) and the one value that the program adds (c at the position of gender, S10.3) | article § 2, Table 1; S10.3 | `src/greek_corpus_pipeline/agdt_schema.py` | R0 | included in B1: 210 figures compared, all obtained |

### C. Corpora, inputs and models

| # | Element | Declared in | In this package, or how to obtain it | How checked | Outcome |
|---|---|---|---|---|---|
| C1 | Gorman Trees: 158 XML files, folder `public/xml` of the master branch; Table S11.3 gives the commit and the SHA-256 of the archive | article, Data availability; S11.2–S11.4 | not distributed: ACQUISITION.md says where to obtain them, the commit and the checksum; the name, size and SHA-256 of every file are in `reproducibility/reference/inputs_files.csv`; `reproducibility/scripts/input_fingerprint.py` checks a folder | R1 | 158 files, 70,735,878 bytes, fingerprint dad905a69a0848cb: the one of Table S11.2 (`MATCH`); the archive that the study had downloaded has the SHA-256 of Table S11.3. The files used were those of the study, not downloaded again |
| C2 | Pedalion Trees: 40 XML files, folder `public/xml` of the master branch; commit and archive checksum in Table S11.3 | same | same | R1 | 40 files, 40,811,672 bytes, fingerprint 1b799d2b82395412: the one of Table S11.2 (`MATCH`); the archive that the study had downloaded has the SHA-256 of Table S11.3. The files used were those of the study, not downloaded again |
| C3 | GLAUx: forty texts in four strata (18, 2, 17 and 3 files), identified by the DOI of the resource and by the SHA-256 of each file (Table S9.1) | article § 6.2, Data availability; S9, S11.4 | the list of the forty texts is `data/glaux_sample.csv`; the program downloads them on request from the GLAUx repository (ACQUISITION.md); `reference/inputs_files.csv` holds their checksums | R1 | the four strata have the fingerprints of Table S11.2 (`MATCH`): `glaux_auto` 18 files and fcbad2724b8b6290; `glaux_man` 2 files and ddcfd293d1908680; `glaux_conf_auto` 17 files and b03f5a325a2a8e6c; `glaux_conf_man` 3 files and a4ac3b46084fdcaf. One folder holding the forty files served the four strata, each taking only its own files. The files were those that the study had downloaded; the GLAUx repository was not queried again, so that a change of the branch since the study is not tested |
| C4 | The draw of the GLAUx samples: the pool, the seeds (20260814 and 20260815), the strata and the forty texts | article § 6.2; S9 | `data/glaux_metadata.csv` (1,421 rows), `data/glaux_sample.csv`, `reproducibility/scripts/glaux_sample_draw.py` | R0 | everything is as S9 states |
| C5 | The inclusion and exclusion criteria and the five counting units (imported tokens, active tokens, words, analysable links, analysable sentences) | article § 3.1; S11.1 | `src/greek_corpus_pipeline/units.py`; the filters of the study are those of `reproducibility/scripts/rerun_diagnosis.py` | R1 | 32 values that the supplement states (in the strata where its text states them) compared, all reproduced; the other figures of the log have no stated counterpart and are only printed; the five units of each of the six strata are compared in B10 |
| C6 | The file manifests and the input fingerprints of the six runs (Table S11.2) | S11.2, S11.4 | `reproducibility/reference/inputs.csv`, `inputs_files.csv` (238 files) | R1 | same as C1–C3 |
| C7 | The model files of Stanza (tokenizer, tagger, lemmatiser, pretrained vectors) and the UDPipe model, with sizes and SHA-256 (Table S11.3) | S10.1, S10.13, S11.3 | not distributed: ACQUISITION.md; `reproducibility/scripts/rerun_model_comparison.py` compares size and SHA-256 of each file with Table S11.3 before using it | R2 | the six files (the UDPipe model and five Stanza files) have the size and the SHA-256 of Table S11.3 |
| C8 | UD_Ancient_Greek-Perseus, release 2.4 (training, development and test sets) | S10.14 | not distributed: ACQUISITION.md; `reproducibility/scripts/overlap_with_ud_perseus.py` | R3 | 241 stated values compared, all reproduced |
| C9 | The licences of the corpora and of the models | S11.4; article, Data availability | ACQUISITION.md records, for each resource, what its official page says, the page and the date on which it was read; the corpora and the models are not redistributed | D | documentary; the conditions are not uniform (Gorman: two declarations that disagree; GLAUx: some texts more restrictive) and are stated in ACQUISITION.md |

### D. Tables, figures and statements

| # | Element | Declared in | In this package | How checked | Outcome |
|---|---|---|---|---|---|
| D1 | Table 2: the 22 indicators of Gorman and Pedalion (units, links, sentences, non-projectivity) | article § 3.1 | `reproducibility/scripts/recompute_table2.py` | R1 | 44 values of Table 2 compared, all reproduced |
| D2 | Tables 3, 5, 6, 7 and 8; Fig. 1; the abstract and § 5.1; Tables S1.1–S1.3 | article §§ 4.1, 5.1, 6.4, 6.5, abstract; S1 | `reproducibility/scripts/check_claims_from_reference.py` | R0, then R1 for the findings behind them (B10) | 210 figures compared, all obtained |
| D3 | Table 4: the five authorities | article § 4.2 | — | D | documentary |
| D4 | The ten case studies and the figures quoted in their text (S7.1–S7.10); the tokens that carry findings (S1, § 5.1); the first sample of GLAUx and the text 0527-012 (S9, § 6.4) | S7; article §§ 5.1, 5.2, 6.4 | `reproducibility/scripts/recompute_case_studies.py` (S7, S1, one figure of S9); `check_claims_from_reference.py` (§ 6.3–6.4) | R1, R0 | 89 stated figures compared, all reproduced |
| D5 | The variation n-gram: the nuclei by level (Table S8.1) and the concentration test with the Holm correction (Tables S8.2 and S8.3) | article § 6.1; S8 | `reproducibility/scripts/compare_with_reference.py` (S8.1); `recompute_variation_concentration.py` (S8.2 and S8.3) | R1 | 70 values compared, all reproduced |
| D6 | The model comparison in the article (Table 9, § 7) and its supplement: provenance, denominators, main measures, malformed predictions, positions, parts of speech, three-way comparison, substitutions, lemma | article § 7, Table 9; S10.1–S10.13 | `reproducibility/scripts/recompute_model_counts.py` (Tables S10.1, S10.3, S10.8, S10.9, the degree paragraph of S10.6 and Table 9) and `recompute_model_tables.py` (Tables S10.2, S10.4–S10.7, S10.10, S10.11, the comparison key of S10.8, the person paragraph of S10.6); the predictions are produced by `rerun_model_comparison.py` | R2 | 154 stated values compared (provenance and counts), all reproduced ; 305 values compared, all reproduced |
| D7 | The overlap of the corpora with the training data of the models (S10.14, Tables S10.12 and S10.13; article § 7.3) | S10.14 | `reproducibility/scripts/overlap_with_ud_perseus.py` | R3 | 241 stated values compared, all reproduced |
| D8 | The five counting units and the frozen results of the six strata (Tables S11.1 and S11.2) | S11.1, S11.2 | `recompute_units.py`, `compare_with_reference.py`, `reference/table_S11_1_units_and_findings.csv` | R1 | 32 values that the supplement states (in the strata where its text states them) compared, all reproduced; the other figures of the log have no stated counterpart and are only printed ; 120 values compared in the six strata (units, nuclei, findings, checks, classes, and the fingerprint of the findings): all identical to the study; no finding present in only one of the two |
| D9 | The repetition reproduces "cell by cell" the tokens, the findings with their proposals, the arcs and the tables of the variation nuclei, and the four comparison tables with their evaluations | S11.2 | `reproducibility/scripts/compare_run_folders.py` compares two run folders table by table | R1, R2 | 58 tables of the six runs compared cell by cell with the run folders of the study, among them the four comparison tables of Gorman and Pedalion: all identical. A missing value counts as different from any value, a table that is in only one folder fails, and two label columns may be worded differently (the direction of an arc is compared as left or right, row by row: section 6) . The folders of the study's own runs are not distributed (they contain the annotated text of the corpora); the comparison is possible against any other run folders (section 6) |
| D10 | The four fingerprints: findings (12 hexadecimal characters of an MD5 of the sorted keys), input (16 of a SHA-256 of "name:SHA-256" lines), corpus and resource fingerprints of the models | S11.3, S10.1 | findings: `compare_with_reference.py` and `reference/finding_keys/`; input: `input_fingerprint.py`; corpus and resource: `rerun_model_comparison.py` and `recompute_model_counts.py` (provenance block) | R1, R2 | findings and input: see C1–C3 and B10; corpus and resource: the version of each library, the fingerprint of the corpus and of the resources of each model, and the number of tokens given to it (Table S10.1) were compared in the 154 values of D6 (16 of them): all the same |

### E. Reference outputs

| # | Element | Declared in | In this package | How checked | Outcome |
|---|---|---|---|---|---|
| E1 | Reference values of the study as machine-readable tables: Table S11.1, the nuclei by level, the 77 checks by stratum, the keys of the 160,577 findings, the inputs, the provenance of the models, the 90 evaluations, every count of S10, the overlap | S11.2, S11.5 | `reproducibility/reference/` (list in README.md, section 4) | S, R0 | the reference tables were written from the runs of the study; they are what the text is compared with, not an independent measurement. Agreement with them shows that the text is consistent with the runs; what shows that a new run gives the same results is level 1 |
| E2 | Intermediate files of a run (tokens, arcs, findings, nuclei, comparison tables), for comparing a new run | S11.4, S11.5 | **not distributed**, because they reproduce the annotated text of corpora with their own licences (S11.4); a run writes them in `workspace/runs/<run>/`, and `compare_run_folders.py` compares any two such folders | X | a reviewer who has the study's run folders can compare them with a new run; otherwise the comparison with the reference tables of E1 is what is available |
| E3 | The supplementary materials, against which this guide was written | — | `supplementary_materials/` | S | the PDF of the supplementary materials in the version submitted for review; its SHA-256 is in `../INVENTORY.md`. It is a convenience copy and can be removed without effect on anything else |

## 3. Which denominator each figure uses

| Figure | Numerator ÷ denominator | Values |
|---|---|---|
| Share of violations among the findings (abstract, § 5.1, Table 5) | violations ÷ all findings of the corpus (not ÷ tokens) | Gorman 1,914 ÷ 101,047 = 1.9%; Pedalion 1,361 ÷ 29,515 = 4.6% |
| Rate of a class per 10,000 active tokens (Tables 5–7) | findings of the class × 10,000 ÷ active tokens | active tokens: Gorman 616,646; Pedalion 274,609; GLAUx automatic 292,567; manual 21,107; confirmation automatic 267,313; manual 28,143 |
| Imported, active tokens and words (Table S11.1) | the three nested units of § 3.1 | Gorman 625,176 imported, 616,646 active, 548,912 words; Pedalion 281,245, 274,609, 238,413 |
| Agreement of a model on the lemma (Table 9, S10.3) | agreements ÷ words with a reference lemma | Gorman 548,803; Pedalion 238,389 |
| Agreement of a model on the tag | agreements ÷ words with a nine-character tag; a prediction that cannot be read counts as a disagreement | Gorman 548,593; Pedalion 238,311 |
| Agreement at one position of the tag (Table S10.5) | agreements ÷ eligible words in which the corpus fills the position | one denominator per position and corpus |
| Agreement by part of speech (Tables S10.6, S10.7) | agreements ÷ words of that part of speech in the corpus (classes of at least 200 words) | one denominator per class, for the lemma and for the tag |
| Three-way comparison (Table S10.8) | the five outcomes ÷ eligible words of the field | lemma 548,803 and 238,389; tag 548,593 and 238,311 |
| Overlap with the training data (S10.14) | words that overlap ÷ words of the corpus | 548,912 and 238,413 |

## 4. Statements that look alike and are not the same

* **2,735 and 2,778 (Gorman, particle g; article § 7.5, S10.9).** The two models write a tag that begins with g on the
  same word 3,013 times, always with identical tags. In 2,735 of them the corpus tag is exactly `d--------`: this is
  the substitution of the complete tag `d--------` by `g--------` of Table S10.9. In 2,778 the corpus tag begins with
  d: this is the pair d→g of the first position, in the list of twelve pairs of S10.9. The 43 words of difference
  have the corpus tag `d-------_` (underscore at the ninth position). `recompute_model_counts.py` prints both values
  and the difference, for each corpus. In Pedalion the two coincide (4,113). The 2,735 of § 7.5 and of Table S10.9 are
  therefore the words whose corpus tag is exactly `d--------`; the words annotated d at the first position, whatever
  the rest of the tag, are 2,778. The number 2,735 also appears in S10.6
  as the disagreements of UDPipe in the ninth position in Pedalion (3,354 − 619); it is the same number by chance.
* **Nine and eight (Pedalion, cycles; S11.1).** S11.1 states that, among the analysable sentences of Pedalion, the
  chain of heads contains a cycle in nine, and in eight when the technical tokens are left out. The nine are counted on
  all the records, the eight on the active records, the graph that the program works on. `recompute_units.py`
  computes both and compares both with the text. The 16 (Gorman) and 28 (Pedalion) analysable sentences in which a
  chain of heads reaches no token with head 0 are counted on all the records.
* **2,630, 1,311 and 2,011 (Pedalion, degree; S10.6).** The corpus fills the ninth position in 3,354 words: 270
  with the underscore, 454 with p and 2,630 with c or s. The 1,311 and the 2,011 are the words among the 2,630 on
  which Stanza and UDPipe, respectively, do not agree; in all of them the model leaves the position empty (the
  hyphen). `recompute_model_counts.py` prints both the disagreements on the 2,630 and the subset in which the model
  writes the hyphen.
* **Tables and sections of S10 are numbered in two separate series.** For example, section S10.6 contains Table S10.5.
  The scripts name both.
* **The share of violations is a share of the findings, not of the tokens.** Compare Table 5 (shares) and
  Table 7 (rates per 10,000 active tokens).

## 5. Verification record

These are the runs that produced the outcomes above. The scripts print every figure next to the value that the text
states; the logs are summarised here. The record was written last. The archive that was run differs from the one you
hold in four files and in no others: this guide, `INVENTORY.md` and `SHA256SUMS`, which can only be written after the
runs, and the `README.md` of the package folder, which was rewritten after them. None of the four is read by the
program or by the scripts that compare the results; the tests use `README.md` only as the description of the package
when they build the wheel, and `verify_sha256sums.py` checks this guide, `INVENTORY.md` and `README.md` against
`SHA256SUMS`, which lists every file but itself.

All the runs were made on one machine (Linux x86-64, two processor cores, about 8 GB of memory, no graphics card), from a fresh extraction of the archive, in the environments below, following INSTRUCTIONS.md and README.md as a reviewer would.

**Environments.** E1, E2 and E4 were created with `python -m venv` (E4 with `uv venv` and `uv pip install --resolution lowest-direct -e ".[dev]"`) and `pip install -e ".[dev]"`; E1 with the versions of pandas, NumPy and PyArrow of the study pinned. E3 is the environment of the comparison with the models. E5 was created with `python -m venv` and holds the wheel built from `pyproject.toml`, not an editable installation.

| Code | Python | pandas | NumPy | PyArrow | PyQt6 | Matplotlib | pytest | Other |
|---|---|---|---|---|---|---|---|---|
| E1 | 3.14.6 | 3.0.5 | 2.5.3 | 25.0.1 | 6.12.0 | 3.11.2 | 9.2.0 | the versions of Python, pandas, NumPy and PyArrow of the study (S11.2); `ufal.udpipe` 1.4.0.1 was installed after the first test run, for the tests with the UDPipe model |
| E2 | 3.13.16 | 3.1.1 | 2.5.4 | 26.0.1 | 6.12.0 | 3.11.2 | 9.2.0 | the latest releases of the dependencies when the tests were run |
| E3 | 3.14.6 | 3.0.5 | 2.5.3 | 25.0.1 | 6.11.0 | — | — | Stanza 1.14.0, PyTorch 2.14.0, `ufal.udpipe` 1.4.0.1: the versions of S11.2; used only to produce the predictions of the models |
| E4 | 3.11.17 | 2.2.0 | 1.26.0 | 14.0.0 | 6.5.0 | 3.8.0 | 8.0.0 | the lowest versions that `pyproject.toml` admits, on the lowest Python it admits; `psutil` 5.9.0, `threadpoolctl` 3.1.0 |
| E5 | 3.13.16 | 3.1.1 | 2.5.4 | 26.0.1 | 6.12.0 | 3.11.2 | — | a virtual environment that holds only the wheel (`pip install` of the file), with the dependencies as pip resolved them on the day of the tests |

**Runs.** `W` is the workspace of `rerun_diagnosis.py`, `C` the folder that `build_gcp_corpora_folder.py` writes, `M` the UDPipe model. The times are those of one run.

| Step | Command | Env | Outcome | Time |
|---|---|---|---|---|
| Integrity of the archive | `python reproducibility/scripts/verify_sha256sums.py` | — | 198 files listed in `SHA256SUMS`: all present and identical, nothing unlisted |  |
| Installation | `python -m venv .venv`, `pip install -e ".[dev]"` | E1, E2, E4 | installed without error |  |
| Check of the installation | `python CHECK_INSTALL.py` | E1, E2 | ends with "No problem: the program is running the code of this folder, version 3.1.0" |  |
| Installation as a wheel | `python -m hatchling build -t wheel`, then `pip install` of the wheel in a new virtual environment | E5 | `greek_corpus_pipeline-3.1.0-py3-none-any.whl` (94 files) built and installed without error |  |
| Command line installed from the wheel | `greek-corpus-cli --source PEDALION_XML --corpus-name pedalion --workspace W5 --detect --variation`, from a folder that is not the project's, with no `PYTHONPATH`; its run compared with the study's run of Pedalion by `compare_run_folders.py --skip-models` | E5 | ends normally; 9 tables compared, all identical; 2 model table(s) not looked at (--skip-models) | 21 s |
| Test suite | `python -m pytest tests -q -rs` | E1 | 775 passed, 24 skipped | 2 min 55 s |
|  |  | E2 | 775 passed, 24 skipped, 9 warnings | 2 min 51 s |
|  |  | E4 | 775 passed, 24 skipped, none failed | 3 min 00 s |
| Test suite, six corpora | `GCP_CORPORA=C python -m pytest tests -q -rs` | E1 | 786 passed, 13 skipped | 3 min 06 s |
| Test suite, six corpora and UDPipe model | `GCP_CORPORA=C GCP_UDPIPE_MODEL=M python -m pytest tests -q -rs` | E1 + `ufal.udpipe` | 798 passed, 1 skipped | 3 min 49 s |
| Responsiveness test, alone | `GCP_RESPONSIVENESS_TEST=1 GCP_UDPIPE_MODEL=M python -m pytest tests/test_ciclo_di_vita_modelli.py -q -k reattivita` | E1 + `ufal.udpipe` | 1 passed | 5 s |
| Test suite, every test in the reverse order | `python -m pytest tests -q -rs`, with a pytest plugin of one line outside the package that reverses the collected tests | E1 | 775 passed, 24 skipped: the same as in the default order | 2 min 58 s |
| The ten test modules that change the language of the interface | the same modules in the given order and in the reverse order (modules and tests) | E1 | 120 passed in both orders |  |
| Tests of the installed layout and of the wheel | `python -m pytest tests/test_installed_layout.py -q -rs` | E1 | 7 passed, none skipped (the wheel is built with hatchling and installed) |  |
| Command line | `greek-corpus-cli --help` | E1, E2 | ends normally and lists the options |  |
| The window | `python app_qt.py` with `QT_QPA_PLATFORM=offscreen`, stopped after 20 s | E1 | still running after 20 s, no error |  |
| Level 0 | `check_claims_from_reference.py` | E1 | 210 figures compared, all obtained |  |
|  | `glaux_sample_draw.py` | E1 | everything is as S9 states |  |
| Inputs | `input_fingerprint.py FOLDER --stratum S --diff` (six strata; one folder for the four GLAUx strata) | E1 | the six fingerprints match Table S11.2 |  |
| Level 1: the six runs | `rerun_diagnosis.py --gorman G --pedalion P --glaux X --workspace W` | E1 | the six strata give the findings, the units and the fingerprints of Table S11.1 | 1 min 49 s |
|  | `compare_with_reference.py W` | E1 | 120 values compared, all identical to the study | 1 s |
|  | `recompute_units.py --workspace W` | E1 | 32 stated values compared, all reproduced | 35 s |
|  | `recompute_table2.py --workspace W` | E1 | 44 values of Table 2 compared, all reproduced | 23 s |
|  | `recompute_case_studies.py --workspace W` | E1 | 89 stated figures compared, all reproduced | 9 s |
|  | `recompute_variation_concentration.py --workspace W` | E1 | 70 values compared, all reproduced | 37 s |
|  | `sensitivity_analysis.py --workspace W` | E1 | 90 evaluations compared, all identical to the supplement | 54 s |
|  | `recompute_list_alignment.py --workspace W` | E1 | 97 values compared, all reproduced | 4 min 48 s |
|  | `recompute_fixed_limits.py --workspace W` | E1 | 14 values compared, all reproduced | 6 min 47 s |
| Level 2: the models | `rerun_model_comparison.py --workspace W --models M` | E3 | udpipe on gorman 4 min 29 s; stanza on gorman 4 min 45 s; udpipe on pedalion 1 min 36 s; stanza on pedalion 1 min 58 s; the predictions are written in the run folders | 13 min 02 s |
|  | `recompute_model_counts.py --workspace W` | E1 | 154 stated values compared (provenance and counts), all reproduced | 4 s |
|  | `recompute_model_tables.py --workspace W` | E1 | 305 values compared, all reproduced | 13 s |
|  | `compare_run_folders.py --study-runs DIR --workspace W` | E1 | 58 tables compared, all identical |  |
| Level 3 | `overlap_with_ud_perseus.py --ud UD --workspace W` | E1 | 241 stated values compared, all reproduced | 9 s |

**Skipped tests.** The default run skips 24 tests, always for a stated reason, the same in the three environments: 11 need the six corpora (`GCP_CORPORA`), 9 need the UDPipe model (`GCP_UDPIPE_MODEL`), 3 need the library `ufal.udpipe`, and 1 measures times and must be run alone on a quiet machine. With the six corpora the 11 of the first group run (786 passed, 13 skipped); with the UDPipe model and the library the other 12 run too (798 passed, 1 skipped); the test of times, run alone, passes. So all 799 tests of the suite pass, in one run or another.

**Warnings.** In E2 (pandas 3.1.1) the suite gives 9 `Pandas4Warning`, all for the same line, `gui_qt/pages/review_page.py` (`keys.map(decisions).fillna("")`, in the page where the user's corrections are reviewed): pandas announces that a later version will refuse a string as the fill value of a column of numbers. It is a warning for a future version, not a failure, and the line is not part of the diagnosis; E1 gives none. E4, the oldest libraries, gives 146 warnings, all of the libraries themselves and none a failure: 60 `FutureWarning` of pandas 2.2.0 on the downcasting of object columns by `fillna`, 37 `DeprecationWarning` of PyQt6 6.5.0, 36 of pandas 2.2.0 (a `BlockManager` passed to a `DataFrame`) and 13 of pyparsing, through Matplotlib 3.8.0.

**Not run.** The program was not started on Windows, and its windows were not opened on a screen: the interface was exercised by the tests and by starting the application, always with `QT_QPA_PLATFORM=offscreen`. The wheel was installed and its command line run on Linux only. The GLAUx files were not downloaded again (C3).


## 6. Limits of the verification, and how this copy relates to the release

* **Windows.** The study ran on Windows; the tests of this package ran on Linux. The Windows launchers were checked
  only by the static tests of their text (A4).
* **The study's own run folders** are not part of this package (E2). Level 0 compares the text with the reference tables;
  level 1 compares a new run with the same reference tables and, through `compare_run_folders.py`, with any run
  folder one has.
* **The resources move.** Gorman and Pedalion are downloaded as the archive of the master branch, and GLAUx from a
  branch that keeps changing. The input fingerprint (C1–C3) tells whether you hold the files of the study; only a
  difference with the same fingerprint is a discrepancy.
* **The models.** The counts of S10 are those of the model files of Table S11.3. The Stanza files are published on a
  server that was not reachable from the environment of the tests; the files used were those of the study's model
  folder, whose size and SHA-256 were compared with Table S11.3 (C7).
* **What is documentary.** The specification of the checks (B2), their authorities (B3, D3), the sources of the closed
  lists (B7), the descriptions of the variants (B9) and the licences (C9) are arguments or readings of sources. They
  cannot be recomputed.
* **This copy and the release.** The program is release 3.1.0, the one that produced the results, with the
  differences listed in the next subsection and no others. The list was made by comparing the two trees file by file
  and, for the Python files, by comparing the syntax trees with strings, docstrings and comments left out, and then the
  string literals. In short: the identity of the authors, the address of the project and the files about the publication
  of the repository are withheld; the documentation, the comments and the messages are in English, and the comments
  and docstrings describe the code as it is; one computation was changed (a copy of an array, for pandas 3.1 and
  later); data and entries of the translation table that nothing used were removed; two defects of the interface were
  corrected (a catalogue of metadata installed by the user was never read, and the language menu did not show, at
  start-up, the language of the interface); the reproducibility kit and the supplementary materials were added. The six
  runs of this package reproduce, cell by cell, the tables of the study (D9), which shows that the differences do not
  change any of them.
* **Language.** The identifiers that the supplement cites by name are kept as they are, even where they are Italian
  (the names of the closed lists such as `enclitiche`, the columns `eleggibile_lemma` and `accordo_postag`, the test
  file `tests/test_diagnosi.py`). The program keeps an Italian and an English text for each check and for the
  elements of its interface, and shows the English one by default; the Italian ones are program data, not
  documentation. The tables that a run writes carry the descriptive texts of the findings (`anomaly_name`,
  `anomaly_description`, `issue`) in Italian whatever the language of the interface, as the runs of the study do. Two
  label columns are worded differently from the study's tables: `arcs.direction` (`head to the left` and `head to the right`
  here, `testa a sinistra` and `testa a destra` there; `compare_run_folders.py` reads them as left and right and compares
  them row by row) and, for the four GLAUx strata, the name of the corpus in `tokens.corpus` (one name in each table)
  (README.md, section 5; D9).
* **Not verified.** That this archive is identical to the public repository of the program: the address of the
  repository is withheld for the review, and the files of this package are listed with
  their SHA-256 so that a reader who has the repository can compare them.

### The differences from the release

Of the 151 files of the release, 11 are identical (`data/catalogo_controlli.csv`, `data/glaux_sample.csv`, the two
`__init__.py` of `gui_qt` and the seven icons of `gui_qt/assets/`), 124 are changed in place, 5 were removed and 11 were
renamed; this package adds 53 files (the reproducibility kit, the supplementary materials, `INVENTORY.md`, `SHA256SUMS`,
`.gitattributes` and eight test modules). Of the 105 Python files of the release, 69 have the same syntax tree here
(with strings, docstrings and comments ignored). Eleven of the modules that implement the checks and the units
(`lemma.py`, `agreement.py`, `orthography.py`, `xmlio.py`, `normalise.py`, `agdt_schema.py`, `stats.py`, `manifest.py`,
`fastmap.py`, `modelcmp.py`, `issue_testi.py`) also have the same string literals as the release. `rule_catalog.py` has
the same syntax tree, and among its string literals differs only in the sentence on the lexical source with which the
description of two checks ends (`numeral-generic-m`, `osfranthiti-anomaly`): it describes the proposal that the check
writes, the one given in S2. `postag.py` and `evidence.py` differ only by unused data, removed (table below). What these modules test is
unchanged. The 36 files whose syntax tree differs, 17 of the program and 19 of the tests, are these.

| File | What differs from the release | Can it change a result of the article? |
|---|---|---|
| `src/greek_corpus_pipeline/syntax.py` | `build_head_index` copies the array it receives (`to_numpy(..., copy=True)`), because pandas 3.1 and later hand it over read-only and the release stops with those versions; the two labels written in `arcs.direction` are in English (`head to the left`, `head to the right`; the release writes `testa a sinistra`, `testa a destra`). This is the only change in the computation of the analysis | No. The copy does not change a value; with pandas 3.0.5, which the release accepts, the runs of this package give the tables of the study (D9). The labels are text; no code reads the column, and `compare_run_folders.py` reads the old and the new wording as left or right and compares the two tables on that, row by row |
| `src/greek_corpus_pipeline/corpus_metadata.py` | the catalogue of metadata that a user installs from the interface is now read by the enrichment (`installed_user_catalogue`; in the release the interface installed the file and the enrichment never read it); two unused constants removed; the labels (periods, `Unknown`, the sources of an attribution) and the values of `data/*_metadata.csv` are in English; the module text describes the code as it is | No. No check, unit or table of the article reads the enrichment (it feeds the by-author and by-period views and the `metadata` block of the manifest), and without a user's catalogue installed the behaviour is that of the release. A test was added for it |
| `src/greek_corpus_pipeline/figures.py`, `gui_qt/i18n.py`, `gui_qt/pages/stats_page.py`, `gui_qt/pages/models_page.py`, `gui_qt/df_model.py`, and in `gui_qt/workers.py` the formatting of the messages | display only: the decimal separator and the thousands separator of a figure label or of a message follow the language of the interface (the release always wrote the Italian ones); a function that gives the English name of an AGDT position or value; two more columns whose values are translated for display; the interface starts in English (the release starts in Italian); 22 entries of the translation table for elements that the interface does not have were dropped, and 42 entries that were written twice (in `i18n.py` and, with the text that is shown, in one of the four modules of page entries, or twice in `i18n.py`) are written once | No |
| `gui_qt/main_window.py` | at start-up the language menu shows the language in which the interface starts (`_select_language`, called when the menu is built, with its signals blocked); without it the menu of this copy showed its first entry, Italian, while the interface was in English | No. A test was added (`tests/test_selettore_lingua.py`) |
| `src/greek_corpus_pipeline/resources.py`, `gui_qt/workers.py` (the places where they look for files), `pyproject.toml` | the folder of the ten closed lists is looked for in the project (`data/liste` at its root) and, when it is not there, inside the installed package (`greek_corpus_pipeline/data/liste`, where the wheel puts it); the error log `pipeline_errors.log` is written in the project folder when the program runs from it and in the current folder otherwise (and the program goes on logging to the screen if that file cannot be opened); the wheel carries the package `gui_qt`, which the command line imports, besides the library and its data (in the release the wheel lacked it and stopped at import: the installed command line did not run); the extra `dev` lists `psutil`, `threadpoolctl` and `hatchling`, which the tests use | No. In the source tree, which is what the study ran, the folder found is the same as in the release; only an installed copy behaves differently, and in the tests of section 5 the command line installed from the wheel gives the tables of the study (D9). The tests of the installed layout are `tests/test_installed_layout.py` |
| `src/greek_corpus_pipeline/postag.py`, `src/greek_corpus_pipeline/evidence.py`, `src/greek_corpus_pipeline/gold.py` | `postag.py`: a set of ten forms that no code read, which documented a check that is not in the catalogue, is removed; `evidence.py`: the identifier of a check that is not in the catalogue is removed from the set of checks whose findings are grouped by lemma; `gold.py`: the constant that holds the seven base columns of the file of manual corrections is called `BASE_MANUAL_COLUMNS` (`LEGACY_MANUAL_COLUMNS` in the release) | No. No code read the set of forms, and no finding carries the identifier removed; a file of corrections with the seven base columns is read as before (`tests/test_pipeline_base.py`) |
| `src/greek_corpus_pipeline/cli.py`, `src/greek_corpus_pipeline/corrections.py`, `src/greek_corpus_pipeline/analyzers.py`, `CHECK_INSTALL.py` | the output of the command line, the template CSV of the dictionary of forms and the messages of the check of the installation are in English; the environment variable `GCP_UDPIPE_IN_PROCESS` replaces `GCP_UDPIPE_IN_PROCESSO` and accepts `1`, `yes`, `true`; the check of the installation compares the identifiers of the catalogue of the code with those of `data/catalogo_controlli.csv`, instead of looking for six identifiers that the program must not contain | No |
| `tests/conftest.py`, `tests/test_ciclo_di_vita_modelli.py`, `tests/test_diagnosi.py`, `tests/test_elenco_e_pannello.py`, `tests/test_famiglie_intatte.py`, `tests/test_flusso_gold_gui.py`, `tests/test_lingua.py`, `tests/test_metadati.py`, `tests/test_pipeline_base.py`, `tests/test_profilo_parola_gui.py`, `tests/test_resources.py`, `tests/test_ricerca.py`, `tests/test_setup_windows.py`, `tests/test_spiegazioni_variazione.py`, `tests/test_spirito_e_segni.py`, `tests/test_statistiche.py`, `tests/test_udpipe_processo_separato.py`, `tests/test_testi_canonici.py` (now `tests/test_canonical_texts.py`), `tests/avvio_reale.py` (now `tests/real_startup.py`, the manual script that starts the application and walks the flow) | messages in English; the tests of the Windows launchers follow the launchers rewritten in English (two tests added), and one more checks that the three launchers end their lines with CR LF; one test added for the user's catalogue; one test of the release is dropped (it checked that each canonical text changed since the baseline states why, in editorial notes of the data file that are not kept); the tests whose names or assertions spoke of functions, pages, statistics or check identifiers that the program does not have are renamed or dropped, and tests of what it has take their place (the identifiers of the catalogue are those of `reproducibility/reference/checks_overview.csv`; the steps of the bar; every exported figure has its caption; the names of the files of a run that other tools read; the headings of the Word guide are those of `GUIDE.md`); `conftest.py` sets the language of the interface at the start of each module, and the tests that read the Italian texts set it themselves, so that no test depends on the order in which the modules run; eight modules are added, `tests/test_input_fingerprint.py`, `tests/test_compare_run_folders.py`, `tests/test_compare_with_reference.py`, `tests/test_recompute_units.py`, `tests/test_rerun_diagnosis.py`, `tests/test_verify_sha256sums.py`, `tests/test_installed_layout.py` and `tests/test_selettore_lingua.py`, for the scripts of the reproducibility kit, the installed layout and the language menu | The tests do not enter the results. This package has 799 tests (775 passed and 24 skipped in the default run) |

The other 69 Python files are identical to the release's or differ from them only in their comments, docstrings,
messages and display labels. The data
files that differ do so in descriptive text and nowhere else: in `data/*_metadata.csv` and `data/tlg_*.csv`, the columns
that describe a text (dates, century, period, dialect, genre, origin, notes; the names of third-party editors are
kept) are in English, and the columns that identify it (file names, TLG identifiers, document identifiers) are
identical; in `data/liste/*.json` the fields that describe a list (`fonte`, `funzione`, `usata_da`) and, in three of
the ten lists, descriptive text of the entries (`nota`; `autore`, `opera`, `granularita`, `verificato_su`; `risorsa`,
`versione`) are in English, while the words of the seven closed lists of forms and lemmas, and the fields that the
code reads (`stato`, `cts_urn`, `autore_urn`, `locus`, `impronta`, `file_metadati`, `chiave_join`), are identical to the
release's. The Word guides, `GUIDE.md` and `INSTRUCTIONS.md` are translations into English of the guides of the
release, with the names of the authors removed; the `README.md` of the package folder was written for this copy.
