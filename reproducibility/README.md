# Reproducibility kit

This folder holds what is needed to check, one by one, the numbers and the procedures of the article
and of its supplementary materials (S1–S11): scripts, reference tables, and two guides.

| File | What it is |
|---|---|
| **README.md** (this file) | how to run the checks, at four levels, with the commands |
| **[REVIEWER_GUIDE.md](REVIEWER_GUIDE.md)** | the matrix: every element that the article and the supplement promise, where it is in this package or how to obtain it, how it is checked, and what the check gave |
| **[ACQUISITION.md](ACQUISITION.md)** | where the corpora, the models and the UD files come from (source, version, files, destination, checksum, licence), because they are not distributed here |
| `scripts/` | the scripts (listed in section 3) |
| `reference/` | the values of the study, as machine-readable tables (section 4) |

The inventory of the whole package, with a SHA-256 for every file, is [`../INVENTORY.md`](../INVENTORY.md) and
[`../SHA256SUMS`](../SHA256SUMS).

## 1. Four levels

The checks are graded by what they need. Start from level 0: it needs nothing.

| Level | Needs | What it shows | Scripts |
|---|---|---|---|
| **0** | Python 3.11 or later, nothing else (standard library only) | that the aggregate figures of the article and of the supplement (sums, percentages, rates, the 77 checks, the nine parameters, the two GLAUx draws) are consistent with the reference tables of the study | `check_claims_from_reference.py`, `glaux_sample_draw.py` |
| **1** | the program installed, and the XML files of the corpora (public, downloaded by you) | that a new run of the program on the same files gives the same units, findings, nuclei and tables, and the same statistics | `input_fingerprint.py`, `rerun_diagnosis.py`, `compare_with_reference.py`, `recompute_units.py`, `recompute_table2.py`, `recompute_case_studies.py`, `recompute_variation_concentration.py`, `sensitivity_analysis.py`, `recompute_list_alignment.py`, `recompute_fixed_limits.py` |
| **2** | level 1, plus Stanza and UDPipe and their model files | that the comparison with the two models gives the counts of S10 | `rerun_model_comparison.py`, `recompute_model_counts.py`, `recompute_model_tables.py` |
| **3** | level 2, plus the CoNLL-U files of UD_Ancient_Greek-Perseus, release 2.4 | the overlap with the training data (S10.14) | `overlap_with_ud_perseus.py` |

Every script prints each figure next to the value that the article or the supplement states, ends with a line
`RESULT: …`, and exits with status 0 when everything it compared is reproduced and 1 otherwise. A script that has
nothing to compare says so and exits with 1: silence is never a pass.

## 2. Quick start

The commands are written for a terminal opened in the folder where this package was extracted (the one that
holds `app_qt.py`). On Windows use PowerShell; where a path has the form `X/Y`, `X\Y` works as well.

### Level 0 (no installation)

```
python reproducibility/scripts/check_claims_from_reference.py
python reproducibility/scripts/glaux_sample_draw.py
```

On Windows the interpreter may be called `py` instead of `python`. The first script prints 210 figures and
`RESULT: 210 figures compared, all obtained`; the second prints the two draws of S9 and `RESULT: …` in the same way.
Their output is also the quickest way to see what the article and the supplement claim, and where.

### Installation for levels 1–3

```
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"            # Linux, macOS
.venv\Scripts\python.exe -m pip install -e ".[dev]"    # Windows
```

The versions of the study are Python 3.14.6, pandas 3.0.5, NumPy 2.5.3 and PyArrow 25.0.1 (S11.2). The program
requires Python 3.11 or later and pandas 2.2 or later; if you want exactly the versions of the study, install them
first (`pip install pandas==3.0.5 numpy==2.5.3 pyarrow==25.0.1`). The versions used in the tests of this package, and
what each gave, are in REVIEWER_GUIDE.md (section 5); if you use other versions, report them together with any
difference you find. Use the interpreter of the virtual environment (`.venv/bin/python`) in all the commands that
follow.

### Level 1: the diagnosis, the units and the statistics

1. Get the inputs as [ACQUISITION.md](ACQUISITION.md) says: the XML files of Gorman and Pedalion (an archive of a
   branch of each repository, downloaded by you) and the forty GLAUx files (the program can download them).
2. Check that you have the files of the study (a few seconds):

   ```
   python reproducibility/scripts/input_fingerprint.py GORMAN_XML --stratum gorman --diff
   python reproducibility/scripts/input_fingerprint.py PEDALION_XML --stratum pedalion --diff
   python reproducibility/scripts/input_fingerprint.py GLAUX_FOLDER --stratum glaux_auto --diff
   ```

   and likewise for `glaux_man`, `glaux_conf_auto` and `glaux_conf_man`, with the same `GLAUX_FOLDER`. `--diff` lists the
   files that are missing, extra or different. For Gorman and Pedalion the folder must be the XML folder itself: the
   program reads all of it, so the fingerprint is that of every XML file under it. For GLAUx the program reads only the
   files that `data/glaux_sample.csv` names for the stratum, so one folder (the forty files together, or a copy of the whole
   `xml` folder of GLAUx) serves the four strata: the script takes from it only the files of the stratum and says how
   many others it left out. If a fingerprint is not the one of the study the resource has changed since the study, and
   differences in what follows are expected (section 5).
3. Run the program on the six strata (about two minutes in all on two processor cores: under a minute for Gorman,
   about twenty seconds for Pedalion and for each of the two larger GLAUx strata; the times measured in the tests of
   this package are in REVIEWER_GUIDE.md, section 5):

   ```
   python reproducibility/scripts/rerun_diagnosis.py --gorman GORMAN_XML --pedalion PEDALION_XML --glaux GLAUX_FOLDER --workspace W
   python reproducibility/scripts/compare_with_reference.py W
   ```

   `W` is an empty folder in which the runs are written. `--glaux` is optional: without it the program downloads the
   forty files from the GLAUx repository. `compare_with_reference.py` compares Table S11.1 (units, findings, active
   checks, nuclei, fingerprint of the findings), the nuclei of each level (Table S8.1), the four-field key of every
   finding as a multiset, the number of findings of each of the 77 checks (Table S1.1) and the split into classes.
   By default it compares all six strata: a stratum that is missing from `W`, or whose input files are not those of
   the study, is a failure, and the result line says so. `--strata` restricts the comparison to the strata you name;
   a re-run made with `rerun_diagnosis.py --no-variation` has no nuclei, and is compared with `--skip-variation`.
4. The other recomputations, all on the same workspace:

   ```
   python reproducibility/scripts/recompute_units.py --workspace W
   python reproducibility/scripts/recompute_table2.py --workspace W
   python reproducibility/scripts/recompute_case_studies.py --workspace W
   python reproducibility/scripts/recompute_variation_concentration.py --workspace W
   python reproducibility/scripts/sensitivity_analysis.py --workspace W
   python reproducibility/scripts/recompute_list_alignment.py --workspace W
   python reproducibility/scripts/recompute_fixed_limits.py --workspace W
   ```

   They recompute, in this order: the counting units of S11.1; Table 2 of the article; the figures of the ten case
   studies (S7), of S1 and of § 5.1; the concentration test of S8.1 (Tables S8.2 and S8.3, hypergeometric tail and
   Holm correction); the sensitivity analysis of S5 (90 evaluations); Table S6.2 (the closed lists aligned with
   Smyth); and the effect of the fixed limits of the code (Table S4.2).
5. The test suite of the program on the six strata (otherwise those tests are skipped):

   ```
   python reproducibility/scripts/build_gcp_corpora_folder.py --workspace W --output C
   GCP_CORPORA=C QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q -rs            # Linux, macOS
   $env:GCP_CORPORA="C"; $env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python.exe -m pytest tests -q -rs   # Windows
   ```

### Level 2: Stanza and UDPipe

```
.venv/bin/python -m pip install -e ".[models]"
python reproducibility/scripts/rerun_model_comparison.py --workspace W --models M
python reproducibility/scripts/recompute_model_counts.py --workspace W
python reproducibility/scripts/recompute_model_tables.py --workspace W
```

`M` is a folder that holds the model files of the study under the layout shown in the docstring of
`rerun_model_comparison.py` (the same layout as the `workspace/models` folder of the program); the script compares the
size and the SHA-256 of every file with Table S11.3 before using it, and does not download anything unless you
give `--download`. Where the files come from, and under which licence, is in [ACQUISITION.md](ACQUISITION.md). The
time that each model takes on each corpus, as measured in the tests of this package, is in REVIEWER_GUIDE.md, section 5.
The two `recompute_` scripts read only the comparison tables that the first script writes (or those of the study, if you
have them) and take less than a minute.

### Level 3: overlap with the training data

```
python reproducibility/scripts/overlap_with_ud_perseus.py --ud UD_FOLDER --workspace W
```

`UD_FOLDER` holds `grc_perseus-ud-train.conllu`, `-dev.conllu` and `-test.conllu` of release 2.4; the script checks the
number of sentences of the three files (11,476, 1,137 and 1,306) before it counts anything.

### Comparing two runs cell by cell

S11.2 states that a repetition on a second machine reproduces the tokens, the findings with their proposals, the arcs
and the tables of the variation nuclei cell by cell. If you have run folders to compare (two runs of your own, or
the run folders of the study, if the authors supply them), `compare_run_folders.py` makes that statement testable:

```
python reproducibility/scripts/compare_run_folders.py RUN_A RUN_B
python reproducibility/scripts/compare_run_folders.py --study-runs STUDY_RUNS_FOLDER --workspace W
```

The script reports each table as *identical* or *different*, says which tables are in only one of the two folders (a
failure) or in neither (not a failure: a run writes no table when it would be empty), and ends with a `RESULT:` line. The
exit status is 0 only when at least one table was compared, all the tables compared are identical and none is in only one
folder. A missing value is equal to a missing value and to nothing else: it is not equal to the number 5, nor to an empty
text. The wording of two label columns may differ (section 5, "Labels in the tables of a run"); add `--exact` to forbid
it. The two model tables are written only by the runs that compared the models: if only one of the two runs did, the
script fails, and `--skip-models` says that the models are not what you are comparing (the result line then says that
they were not looked at).

## 3. The scripts

| Script | Level | Reads | Writes | Checks |
|---|---|---|---|---|
| `check_claims_from_reference.py` | 0 | `reference/`, `data/catalogo_controlli.csv`, `data/liste/`, the source of five modules | nothing | 210 aggregate figures: catalogue, findings by stratum and class, rates, where the checks fire, the abstract, § 5.1, § 6.3–6.4, the nine parameters, the ten closed lists, the positional scheme of Table 1 |
| `glaux_sample_draw.py` | 0 | `data/glaux_metadata.csv`, `data/glaux_sample.csv`, `tests/test_pipeline_base.py` | nothing | the two draws of S9 (seeds 20260814 and 20260815) and the forty texts |
| `input_fingerprint.py` | 1 | an XML folder | nothing | the input fingerprint of a stratum (Table S11.2) and, with `--diff`, which files differ; for the four GLAUx strata one folder serves all |
| `rerun_diagnosis.py` | 1 | the XML folders | `W/runs/rerun-<stratum>/`, `W/reproduction/` | runs the program on the six strata |
| `compare_with_reference.py` | 1 | `W`, `reference/` | `W/reproduction/comparison.txt` | Tables S11.1, S8.1, S1.1 and the classes of S6, finding by finding |
| `recompute_units.py` | 1 | run folders | nothing | the five units and the figures of the text of S11.1 |
| `recompute_table2.py` | 1 | run folders | nothing | the 22 indicators of Table 2, Gorman and Pedalion |
| `recompute_case_studies.py` | 1 | run folders | nothing | the figures of the running text of S7.1–S7.10 that are not counts per check; the tokens that carry findings (S1, § 5.1 of the article); one figure of S9 |
| `recompute_variation_concentration.py` | 1 | run folders | nothing | Tables S8.2 and S8.3: N, K, n, k, expected value, ratio, exact hypergeometric tail, Holm correction |
| `sensitivity_analysis.py` | 1 | run folders, `reference/table_S5_*.csv` | nothing | the 90 evaluations of S5 (Tables S5.1 and S5.2) |
| `recompute_list_alignment.py` | 1 | run folders, `src`, `gui_qt`, `data` | nothing (temporary copies only) | Table S6.2 and the statements of S6 about the closed lists |
| `recompute_fixed_limits.py` | 1 | run folders, `src`, `gui_qt`, `data` | nothing (temporary copies only) | Table S4.2: the effect of each fixed limit of the code on the six strata, and the largest placeholder form of the data |
| `build_gcp_corpora_folder.py` | 1 | `W` | the folder `C` | the layout that the test suite reads from `GCP_CORPORA` |
| `rerun_model_comparison.py` | 2 | run folders, the model folder | the comparison tables and evaluations in each run | runs Stanza and UDPipe as step 9 of the program does |
| `recompute_model_counts.py` | 2 | run folders, `reference/` | nothing | the provenance of Table S10.1; the eight measures of Table S10.3 and Table 9 of the article; the three-way comparison of Table S10.8; the degree paragraph of S10.6; the substitutions of S10.9 (the 2,735 and the 2,778 of the particle `g`) |
| `recompute_model_tables.py` | 2 | run folders | nothing | the denominators of Table S10.2 and the elliptic nodes (S10.11); the malformed predictions (Table S10.4); the agreement by position (Table S10.5) and the paragraph on person; by part of speech (Tables S10.6 and S10.7); the comparison key of S10.8; the classification of the lemma substitutions (Tables S10.10 and S10.11) |
| `overlap_with_ud_perseus.py` | 3 | run folders, the UD files | nothing | Tables S10.12 and S10.13 and the figures of S10.14 |
| `compare_run_folders.py` | — | two run folders | nothing | cell-by-cell identity of the tables of two runs (S11.2); a table in only one folder, a missing value against a number, a left that became a right are failures |
| `make_reference_tables.py` | — | the study's own run folders | `reference/` | how the reference tables were written; needs runs that are not distributed |
| `repro_common.py` | — | — | — | helpers shared by the scripts |

## 4. The reference tables

`reference/` holds the values of the study, one row per fact, so that nothing has to be copied from a PDF.

| File | Content |
|---|---|
| `table_S11_1_units_and_findings.csv` | the six rows of Table S11.1 |
| `table_S8_1_nuclei_by_level.csv` | the nuclei of each of the five levels (Table S8.1) |
| `checks_overview.csv` | the 77 checks with family, class, treatment, severity and the findings in each stratum (Table S1.1) |
| `findings_by_class.csv` | findings, violations, cases to check and variants per stratum |
| `finding_keys/<stratum>.csv.gz` | the four-field key of every finding (160,577 lines in all); the findings fingerprint is computed on it |
| `inputs.csv`, `inputs_files.csv` | the input fingerprint of each stratum, and the name, size and SHA-256 of each of the 238 XML files (Table S11.2) |
| `table_S5_1_rare_relation.csv`, `table_S5_2_rare_lemma.csv` | the 90 evaluations of the sensitivity analysis (Tables S5.1 and S5.2) |
| `table_S10_1_provenance.csv` | the four comparisons: model, version, corpus and resource fingerprints, tokens supplied (Table S10.1) |
| `s10_model_counts.csv` | every count of S10.3–S10.11 that the supplement states, with the section where it appears |
| `s10_overlap.csv` | the figures of Tables S10.12 and S10.13 and of the text of S10.14 |

The reference tables were written from the runs of the study. They are what the article and the supplement are
compared with; they are not an independent measurement, and agreement with them shows consistency with those
runs, not correctness of the runs. What shows that the program gives the same results again is level 1.

## 5. When a difference is not a failure

* **The inputs moved.** Gorman and Pedalion are downloaded as the archive of the current state of a branch, and the
  GLAUx files from a branch that keeps changing. The input fingerprint tells whether you have the files of the study;
  if it differs, `input_fingerprint.py --diff` says which files differ, and the numbers downstream may legitimately
  differ. Only a difference with the same input fingerprint is a discrepancy.
* **The models.** The counts of S10 are those of the model files of Table S11.3. Other files of the same models, or
  other releases of the libraries, may predict differently. `rerun_model_comparison.py` says which of the files it
  uses are the ones of the study.
* **Labels in the tables of a run.** The descriptive texts of the findings (the columns `anomaly_name`,
  `anomaly_description` and `issue`) are written by the program in Italian whatever the language of the interface, as in
  the tables of the study; they are translated only when shown on the screen, and the English wording of each check is in
  `data/catalogo_controlli.csv` (`name_en`, `description_en`) and in `reference/checks_overview.csv`. Two other columns
  carry a word and not a result, and their wording differs from the study's tables: `arcs.direction` says
  `head to the left` or `head to the right` here and `testa a sinistra`, `testa a destra` in the study's tables, and
  `tokens.corpus` is the name given to the corpus (the GLAUx strata have other names here: `rerun_diagnosis.py` uses its
  own). `compare_run_folders.py` reads the direction of an arc as *left* or *right* in the four known wordings and compares the
  two tables on that, row by row (so a left that has become a right is a difference); it accepts a different name of the
  corpus only when each of the two tables holds a single name; it says when it has accepted a different wording, and with
  `--exact` it accepts none. The fingerprint of the findings does not depend on any of these columns (S11.3).
* **The version of Python.** The draw of the GLAUx samples uses `random.sample`, whose sequence is guaranteed to be the
  same for the same seed only for `random()`, not for `sample()`; the script prints the version of Python.
* **Time.** The times in REVIEWER_GUIDE.md were measured in the tests of this package, on one machine; yours will differ.

## 6. What this kit does not show

* The run folders of the study (tokens, arcs, findings, nuclei and comparison tables) are not distributed, because they
  contain the annotated text of corpora with their own licences (S11.4). Statements about them are therefore checked
  against the reference tables (level 0) and by repeating the runs (levels 1–3), not by opening the study's own files.
* The authority attributed to each check (S3, Table 4), the reasons for the classification (S2, S7) and the choice of
  the sources are arguments, not computations; REVIEWER_GUIDE.md marks them as documentary.
* The Windows launchers (`setup.bat`, `run.bat`, `CHECK_INSTALL.bat`) are checked by static tests of their text; the
  tests of this package ran on Linux (REVIEWER_GUIDE.md, section 5).
