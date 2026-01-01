# Greek Corpus Pipeline

Greek Corpus Pipeline (GCP) 3.1.0 is a desktop application for checking and working with
Ancient Greek treebanks in the AGDT 2.0 format, the XML of the Ancient Greek Dependency
Treebank (`treebank` → `sentence` → `word`, with the attributes `form`, `lemma`, `postag`,
`relation` and `head`). It runs 77 diagnostic checks on the annotation, shows every finding
inside its sentence, lets you decide case by case what to correct, and offers search,
statistics, a variation n-gram analysis and export to AGDT XML, CSV and CoNLL-U. A comparison
with two automatic analysers, Stanza and UDPipe, is optional.

**Where the data are processed and kept.** Everything is computed on your computer. The
desktop application writes into a `workspace/` folder next to `app_qt.py`: the loaded corpus,
the findings, your decisions and the revised version, one folder per run in
`workspace/runs/`. The command line writes into `./workspace` unless you give `--workspace`.
The XML files you load are never modified, and nothing is uploaded anywhere. A connection is
needed only to install the program and its libraries, to download a corpus from a GitHub
address or with one of the ready-made buttons, and to download the Stanza and UDPipe model
files the first time the comparison with the models is run. Loading a folder from your disk,
the diagnosis, the corrections, search, statistics, charts and exports work offline.

## What it does

### 77 checks, three diagnostic classes

The checks cover five families: morphology (31 checks), syntactic structure (20), text and
encoding (16), lemmatisation (6), agreement and government (4). Every finding carries a
diagnostic class, which says what kind of finding it is:

| Diagnostic class | Checks | What it means |
|---|---:|---|
| Verifiable violation | 45 | The data break an explicit rule of the scheme, or a required field is empty. It can be checked without interpreting the text. |
| Systematic variant | 11 | A convention that the resource applies consistently and that differs from the reference scheme. It is not an error. |
| Case to check | 21 | A place worth reading. Only the context decides. |

Every check also has a treatment, which says what can be done about it: 19 checks have an
automatic correction (the program writes a proposed value), 58 call for manual review. The
catalogue, with the name and description of every check in English and Italian, is
[`data/catalogo_controlli.csv`](data/catalogo_controlli.csv); the specification of each check
is in Supplement S2.

### From a finding to a decision

An example from the Gorman corpus, document `athen12-1-9-2019`, sentence 102:

> φυλάσσουσί τε αὐτὸν καὶ τριακόσιαι γυναῖκες , ὡς ἱστορεῖ ὁ Κυμαῖος Ἡρακλείδης ἐν **α᾽** Περσικῶν .

The numeral α᾽ (book 1 of the *Persika*) has the tag `m-_---__-`. The check
`numeral-generic-m`, *Numeral with underscores in the PoS tag*, reports it as a verifiable
violation: the underscore is not a value of the AGDT 2.0 inventory. It proposes `m--------`.

1. In step 3, **Diagnostic findings**, the finding is a row of the list. Selecting it shows the
   sentence with the word marked, what the check looks for, what does not add up in this
   occurrence and the proposed correction.
2. In step 5, **Correct**, the same case appears with the current value and the proposed one
   side by side. You choose **Accept this proposal** or **Reject**, or you write a correction
   yourself and press **Save this correction**. The fields **Decided by** and **Reason** are
   optional.
3. Every decision, accepted or rejected, is written to `correzioni_manuali.csv` in the folder
   of the run: the position of the word, the previous and the new value, the check that raised
   the case, who decided, when (UTC), why, the status of the decision and the version of the
   program.
4. **Apply the decisions I took** builds a second version of the corpus. The original stays as
   it was; step 10, **Revised corpus**, shows what changed and exports it.

### Corrections: interface, bulk operations and the command line

* **Interface.** The program changes nothing by itself: every proposal is accepted or rejected
  one case at a time. The only correction applied in bulk is a form dictionary, a CSV file
  that you write and load yourself in step 5 (a template can be downloaded there): it assigns a
  lemma, a tag or both to every occurrence of a form.
* **Command line.** Without `--correct`, `greek-corpus-cli` corrects nothing. With
  `--correct` it applies, without review, the proposals of the 19 checks with automatic
  correction, and the conversion of the whole corpus to NFC when the corpus is published in
  decomposed form; the result is a separate corrected version in the run folder, and the XML
  files you loaded are not touched. `--export-xml`, `--export-csv` and `--export-conllu`
  write that corrected version, so they act only together with `--correct`.

### Search

Forms and lemmas are searched separately, each with its own button. You can type Greek with
accents (ἄνθρωπος), Greek without accents or breathings (ανθρωπος), or Latin letters
(anthropos), with the modes *exact*, *starts with* and *contains*. The result is the list of
every occurrence with its sentence; choosing a row shows its morphology, syntactic function,
lemma, the lemma of its head and its author.

### Statistics and charts

The **Statistics** step has four tabs: *Morphology* (the distributions of the morphological
categories, each on the denominator that fits it), *Syntax*, *Frequency lists* (with four
stopword profiles, one of them a list you can edit, export and import) and *Lemma profile*.
Each can be computed on the whole corpus, by document and, when the corpus carries metadata,
by author, work, period, genre or dialect. The **Charts** step draws six charts from the
counts already computed (findings by family, by diagnostic class and by check, density by
document, and, once both models have been run, agreement with the models and the three-way
comparison); **Export all charts** writes these and further figures that describe the corpus
(cases, moods, tenses, syntactic relations, sentence length, dependency distance and, when the
corpus carries metadata, a profile by period) at 300 dpi, as PNG and PDF, with their captions.

### Variation n-gram

Following the variation n-gram method of Dickinson and Meurers and of Boyd, Dickinson and
Meurers, step 4 groups the places where the same material receives more than one annotation
in the corpus, on five planes: morphology, tag slots, context, dependencies and lemmas. A
nucleus with several annotations is a place to read, not an error.

### Export

| Where | What | Formats |
|---|---|---|
| Step 10, **Revised corpus** | your revised corpus, never the original | AGDT XML, CSV, CoNLL-U; **Save to disk** also keeps the revised version and the decisions that produced it in one `.zip`, which **Load a saved version** reads back |
| Step 2, **Overview** | the corpus as loaded | CoNLL-U; a manifest (JSON) with the version, the corpus fingerprint, the filters, the counting units and the denominators |
| Step 8, **Charts** | the figures | PNG and PDF at 300 dpi, with captions |
| Command line | the corrected version (with `--correct`); the figures | `--export-xml`, `--export-csv` (one CSV per sentence), `--export-conllu`; `--figures FOLDER` |

The CoNLL-U export converts the **format, not the annotation scheme**: the AGDT relation goes
into DEPREL unchanged, the nine-character tag into XPOS, the morphology it encodes is spelled
out in FEATS and UPOS is derived from the first character of the tag. Tokens are renumbered
1…n as CoNLL-U requires, and the original AGDT id is kept in MISC (`AGDTId=`). The tree is not
converted to Universal Dependencies.

### Language

The interface is available in English and Italian. English is the default; the language is
changed from the menu at the top right and takes effect at once, without restarting and
without losing the work.

The documentation and the comments of the code are in English. Some names stay Italian on
purpose, because they are the names under which the program stores its data and which the
supplementary materials cite: the names of some saved files and of some of their columns and
values (for example `variation_morfologia.parquet` with the columns `nucleo` and `etichette`,
`correzioni_manuali.csv` with the statuses `accettata`, `proposta` and `respinta`, and the keys
of the manifest), the catalogue `catalogo_controlli.csv` with its Italian columns (`nome` and
`descrizione`, next to `name_en` and `description_en`), `glaux_sample.csv`, the lists in
`data/liste/`, and the Italian form of the names of authors and works in the metadata
(`author_it` and `work_it`, next to `author_en` and `work_en`). The descriptive text of each
finding in the tables that a run writes (the columns `anomaly_name`, `anomaly_description` and
`issue`, and the values of `severity`) is in Italian whatever the language of the interface, as
in the runs of the study, and is translated only when it is shown on the screen.

## Quick start

GCP needs **Python 3.11 or later**. `pyproject.toml` declares five dependencies, installed
automatically: pandas ≥ 2.2, NumPy ≥ 1.26, PyArrow ≥ 14.0, PyQt6 ≥ 6.5 and Matplotlib ≥ 3.8.
The optional extras are `models` (Stanza ≥ 1.10 and `ufal.udpipe` ≥ 1.3.1.1) and `dev`
(pytest, psutil, threadpoolctl and hatchling, for the tests).

### Windows

1. Install Python 3.11 or later from <https://www.python.org/downloads/>, ticking
   **Add Python to PATH**.
2. Extract the folder and double-click **`setup.bat`**. It creates `.venv` and installs the
   program; at the end it asks whether to install Stanza and UDPipe as well (Enter means no).
3. Double-click **`run.bat`** to start the program.

From a Command Prompt opened in the program folder, the same steps are:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python app_qt.py
```

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python app_qt.py
```

### Checking the installation

`CHECK_INSTALL.py` (on Windows, double-click `CHECK_INSTALL.bat`) reports which Python and
which libraries are running, whether the code comes from this folder, whether the catalogue of
the code is the one shipped in `data/` and, once a corpus has been analysed, how long this
machine takes on the latest saved run. When everything is in order it ends with "No problem:
the program is running the code of this folder, version 3.1.0."; it writes the same text to
`CHECK_INSTALL_result.txt` and waits for Enter before closing.

```bash
python CHECK_INSTALL.py
```

### Platforms

The verification of this package (installation, test suite, command line, wheel and the
repetition of the study) was carried out on Linux x86-64 with Python 3.11, 3.13 and 3.14. The
runs of the study were made on Windows (Supplement S11.2). The Windows launchers of this
package were checked only by the static tests of their text, and macOS was not tested: for
both, the instructions above are provided but were not run.

### Load a folder, run the diagnosis, find the results

1. Start the program. In step 1, **Load a corpus**, choose **Folder on this computer**, then
   **Choose folder…**, and pick the folder of the AGDT XML files; subfolders are read too.
   A **GitHub address** of a folder of XML files works the same way. Give the corpus a name
   and press **Load the corpus**. By default the elliptic nodes are left out of the analysis
   and punctuation and words without Greek letters are kept, as in the study.
2. In step 3, **Diagnostic findings**, press **Run the check**. The findings appear as a list;
   selecting a row shows it in its sentence.
3. The results are saved in `workspace/runs/<date>-<time>-<name>/`: among others
   `tokens.parquet` (the corpus as loaded), `findings.parquet` (the findings) and `arcs.parquet`
   (the dependency arcs); after step 5, `correzioni_manuali.csv` and the revised corpus. Step 1
   lists the saved runs and opens them again.

The same from the command line, which also prints how many findings the most frequent checks
gave:

```bash
greek-corpus-cli --source path/to/xml --corpus-name mycorpus --detect
```

`--variation` adds the variation n-gram (slower), `--stats` prints the statistical profile,
`--figures FOLDER` writes the figures; `greek-corpus-cli --help` lists every option.

## Corpora and study data

The study behind GCP 3.1.0 applies the 77 checks to six strata of three treebanks (§§ 3, 6 of
the article; Tables S11.1 and S11.2):

| Stratum | What it is | XML files | Imported tokens | Active tokens |
|---|---|---:|---:|---:|
| Gorman | whole corpus (Gorman Trees), annotation revised by hand | 158 | 625,176 | 616,646 |
| Pedalion | whole corpus (Pedalion Trees), annotation revised by hand | 40 | 281,245 | 274,609 |
| GLAUx automatic | first sample, automatically annotated texts | 18 | 300,292 | 292,567 |
| GLAUx manual | first sample, texts annotated by hand | 2 | 21,652 | 21,107 |
| GLAUx confirmation automatic | confirmation sample, automatically annotated texts | 17 | 273,354 | 267,313 |
| GLAUx confirmation manual | confirmation sample, texts annotated by hand | 3 | 28,666 | 28,143 |

Gorman and Pedalion are used whole: every XML file of the `public/xml` folder of their
repositories at the commits of Table S11.3. GLAUx has about twenty million tokens, mostly
annotated automatically, and is represented by two samples of twenty texts each, drawn at
random with declared seeds from the texts of 5,000 to 60,000 declared tokens whose authors are
not in Gorman or Pedalion (§ 6.2, S9); the texts annotated by hand are analysed separately from
the automatic ones. The first sample contributed to the formulation of four checks (§ 4.4), so
it is not an independent validation. The confirmation sample is a second sample drawn in the
same way, with a different seed, from the texts left by the first; it checks that the results
of the first do not depend on a fortunate choice of texts, but it too was analysed while the
catalogue was still being revised, so it is not a test set kept apart. The forty texts are
listed in [`data/glaux_sample.csv`](data/glaux_sample.csv). In the interface, six ready-made
buttons in step 1 download and load these strata from their repositories, as they are today
(the first sample is called there the *declared sample*); whether a download is still the
version of the study is checked with the input fingerprints described in ACQUISITION.md.

The main results (Table 7 of the article and Table S1.2):

| Stratum | Findings | Verifiable violations | Share of the findings | Violations per 10,000 active tokens |
|---|---:|---:|---:|---:|
| Gorman | 101,047 | 1,914 | 1.9% | 31.0 |
| Pedalion | 29,515 | 1,361 | 4.6% | 49.6 |
| GLAUx automatic | 13,168 | 378 | 2.9% | 12.9 |
| GLAUx manual | 2,400 | 41 | 1.7% | 19.4 |
| GLAUx confirmation automatic | 11,259 | 172 | 1.5% | 6.4 |
| GLAUx confirmation manual | 3,188 | 15 | 0.5% | 5.3 |

The share is computed on the findings of the stratum, the rate on its active tokens. The
findings include systematic variants and cases to check, which are not errors: a different
rate is not by itself a difference of quality between corpora (§ 6.4).

**What is distributed and what is not.** This package contains the program, the catalogue of
the checks, the ten closed lists (`data/liste/`), the list of the forty GLAUx texts, the
metadata of the three corpora used to group the statistics, and the reference values of the
study (`reproducibility/reference/`). It contains no corpus, no model and no output of a run:
the corpora are downloaded from their repositories (step 1, or as described in
[`reproducibility/ACQUISITION.md`](reproducibility/ACQUISITION.md)), the models on first use.
ACQUISITION.md gives, for every resource, the version used by the study, how to recognise it
and what its licence says.

## Optional model comparison

Stanza and UDPipe are needed only by step 9, **Compare the models**. Install them with the
`models` extra (on Windows, `setup.bat` offers it at the end):

```bash
pip install -e ".[models]"
```

This installs Stanza, with PyTorch, and `ufal.udpipe`. The first time each model is run the
program downloads its files into `workspace/models/`: for Stanza the Ancient Greek `perseus`
package (tokenizer, tagger, lemmatiser and pretrained vectors) with its index `resources.json`,
about 42 MB in all; for UDPipe the model `ancient_greek-perseus-ud-2.4-190531.udpipe`, about
20 MB. The files used by the study
are identified by size and SHA-256 in Table S11.3 and in ACQUISITION.md.

Without the models everything else works: the comparison page says that they are not
installed and its buttons stay disabled. UDPipe runs in a separate process, so that the window
keeps responding; `GCP_UDPIPE_IN_PROCESS=1` runs it inside the program instead.

The comparison lines up, word by word, the corpus, Stanza and UDPipe on the lemma and on the
morphological tag, and step 10 measures the models against the revised corpus as well as the
original. Neither model is treated as a reference: agreement and disagreement help to find
places to re-read. A disagreement with a model is a signal worth looking at, not proof that
the annotation is wrong.

## Documentation and reproducibility

| File | What it contains |
|---|---|
| [`GUIDE.md`](GUIDE.md) | the user guide, every step of the program explained; also as Word, [`docs/GCP_user_guide.docx`](docs/GCP_user_guide.docx) |
| [`docs/GCP_metadata_guide.docx`](docs/GCP_metadata_guide.docx) | where author, work, date, period, dialect and genre come from, and how to supply your own metadata ([`data/user_metadata_EXAMPLE.csv`](data/user_metadata_EXAMPLE.csv)) |
| [`INSTRUCTIONS.md`](INSTRUCTIONS.md) | installation, with Windows in detail, and what to do if something does not work |
| [`reproducibility/ACQUISITION.md`](reproducibility/ACQUISITION.md) | the corpora and the models: versions, identifiers, licences |
| [`reproducibility/README.md`](reproducibility/README.md) | how to repeat the analyses of the article and of the supplement, level by level |
| [`reproducibility/REVIEWER_GUIDE.md`](reproducibility/REVIEWER_GUIDE.md) | where each element of the article and of the supplement is, how it was checked and with what outcome |
| [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) | counting units, parameters, sensitivity analysis, fingerprints, environment of the measurements |
| [`supplementary_materials/`](supplementary_materials/) | the supplementary materials (PDF) |
| [`INVENTORY.md`](INVENTORY.md), [`SHA256SUMS`](SHA256SUMS) | every file with its SHA-256; `python reproducibility/scripts/verify_sha256sums.py` checks them |

To run the tests:

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen python -m pytest tests -q -rs
```

On Windows, set `QT_QPA_PLATFORM=offscreen` with `set` before running pytest.

With Python 3.14.6, pandas 3.0.5, NumPy 2.5.3 and PyArrow 25.0.1 on Linux, without the model
libraries, the six frozen corpora and the UDPipe model, the suite ends with **775 passed,
24 skipped**, also when the tests run in the reverse order. Each skipped test says why (`-rs`):
11 need the six frozen corpora (`GCP_CORPORA`), 9 the UDPipe model (`GCP_UDPIPE_MODEL`), 3 the
library `ufal.udpipe`, and one measures times and must run alone on a quiet machine
(`GCP_RESPONSIVENESS_TEST=1`). With the corpora, the model and the library every test runs
except that one, which passes when it is run alone. How to point the suite at them is in
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md); the record of every run, with its
environment and time, is section 5 of
[`reproducibility/REVIEWER_GUIDE.md`](reproducibility/REVIEWER_GUIDE.md).

## Citation and licence

[`CITATION.cff`](CITATION.cff) gives the title, the version (3.1.0) and the licence; the
authors are withheld for the double-blind review.

The program is distributed under the MIT licence ([`LICENSE`](LICENSE); the name of the
copyright holder is withheld for the review), with its source code, the catalogue of the
checks, the ten closed lists and the list of the forty GLAUx texts (Supplement S11.5); the
metadata catalogues in `data/` are distributed under the same licence and describe resources
of third parties, whose own licences apply to the data they describe. The corpora, the models
and the other external resources are not distributed and keep their own licences, as recorded
in [`reproducibility/ACQUISITION.md`](reproducibility/ACQUISITION.md):

| Resource | Licence as declared by the resource |
|---|---|
| Gorman Trees | CC BY-SA 4.0 in `TREEBANK_LICENSE`, CC0 1.0 in the README: the two declarations disagree (S11.4) |
| Pedalion Trees | CC BY-SA 4.0 (`TREEBANK_LICENSE`) |
| GLAUx | generally CC BY-SA 4.0; some texts have a more restrictive licence, indicated text by text |
| UDPipe 1 models for UD 2.4 | CC BY-NC-SA |
| UD_Ancient_Greek-Perseus (used only for S10.14) | CC BY-NC-SA 2.5 |
| Stanza models | no claim is made here: they are trained on UD_Ancient_Greek-Perseus, and their terms must be read at the source |

These are summaries, not legal advice: whoever redistributes a resource must read its licence
at the source.
