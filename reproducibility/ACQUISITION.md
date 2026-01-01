# Acquiring the corpora and the models

This package contains **no corpus, no model, no output of a model and no run of the
study**. The corpora and the models belong to other projects and carry their own licences,
and the runs reproduce the annotated text of the corpora. What the package contains instead
is what is needed to recognise the right copy of each resource and to compare a new run
with the study: the sizes and SHA-256 of every file the study read
([`reference/inputs_files.csv`](reference/inputs_files.csv)), the identifier of each archive
and model file (below), and the reference values of the supplement
([`reference/`](reference/)).

This page says, for each external resource, what it is, where it is, which version the
study used, how to check that you have that version, where to put it, under which licence it
is distributed and what part of the checking needs it. The licence statements are taken from
Supplement S11.4 and from the pages of the projects; they are not legal advice, and a
reader who redistributes anything must read them again at the source.

## 1. Summary

| Resource | Needed for | Version of the study | How to recognise it |
|---|---|---|---|
| Gorman Trees | stratum `gorman` (every number reported on it) | commit `83d93a554a46ff6e9a34a15a9e0be2dff270a612` of the `master` branch; 158 XML files, 70,735,878 bytes | input fingerprint `dad905a69a0848cb` |
| Pedalion Trees | stratum `pedalion` (every number reported on it) | commit `112c106b86b865ddde4be7e5f3e409d9c42689f9` of the `master` branch; 40 XML files, 40,811,672 bytes | input fingerprint `1b799d2b82395412` |
| GLAUx, forty texts | the four `glaux_*` strata; S9 | files of the `main` branch named in `data/glaux_sample.csv` (a moving branch: see § 4) | per-file SHA-256 in `reference/inputs_files.csv`; four fingerprints |
| Stanza `grc` models | S10 (comparison with Stanza) | Stanza 1.14.0, five files | size and SHA-256 (§ 5) |
| UDPipe model | S10 (comparison with UDPipe) | `ancient_greek-perseus-ud-2.4-190531.udpipe` | size and SHA-256 (§ 6) |
| `UD_Ancient_Greek-Perseus` | S10.14 and Tables S10.12–S10.13 only | release 2.4 (tag `r2.4`): the forms of the sentences | three files, size and SHA-256 (§ 7) |

The other numbers of the supplement are checked either with the reference tables of this
package alone or with the three public corpora (see [`REVIEWER_GUIDE.md`](REVIEWER_GUIDE.md)).

## 2. Gorman Trees and Pedalion Trees

**Where.** Gorman Trees: GitHub repository `perseids-publications/gorman-trees`, folder
`public/xml`. Pedalion Trees: `perseids-publications/pedalion-trees`, folder `public/xml`.
The two buttons of the program (step 1) point at exactly these folders.

**Which version.** The program downloads the archive of the `master` branch
(`https://codeload.github.com/<owner>/<repository>/zip/refs/heads/master`) at the moment of
each run. The ZIP comment of such an archive is the commit it was made from. The archives
read by the six runs of the study were:

| Archive | Commit (ZIP comment) | SHA-256 of the archive | Size |
|---|---|---|---|
| `gorman-trees-master.zip` | `83d93a554a46ff6e9a34a15a9e0be2dff270a612` | `89285eae23ba026d23db417b461f9f021489efa94a079f042883a559f80a9592` | 16,432,909 bytes |
| `pedalion-trees-master.zip` | `112c106b86b865ddde4be7e5f3e409d9c42689f9` | `d7ed7ccdeb5aef09ed0f5c509a7e9fce264dc5a93bf59799b8de6c0fc1e69973` | 13,035,055 bytes |

(Table S11.3, in section S11.4 of the supplement, gives the commit and the SHA-256; the sizes were measured on the
archives.)
To get the same files, clone the repository and check out that commit, or download the archive
of that commit.
The SHA-256 of an archive that GitHub generates again need not be the one above, because the
archive of a commit and the archive of a branch have different folder names; the identity of
the *files* is what matters, and it is checked by the next paragraph.

**How to check.** Extract the archive, and run

```bash
python reproducibility/scripts/input_fingerprint.py <extracted>/public/xml --stratum gorman --diff
```

It prints the number of XML files, their total size and the input fingerprint (the first
sixteen hexadecimal characters of the SHA-256 of the sorted lines `file name:SHA-256 of the
file`, Table S11.2), says whether it is the fingerprint of the study and, if not, lists the
files that are missing, extra or different.

**Where to put it.** Anywhere. Give the folder to `rerun_diagnosis.py`
(`--gorman <extracted>/public/xml`, `--pedalion <extracted>/public/xml`). Point at
`public/xml` and not at the root of the repository: the program reads **every** file `*.xml`
under the folder it is given, subfolders included, and the study read the 158 and the 40
files of that folder and nothing else.

**What the program accepts (inclusion and exclusion).** A folder of XML files in AGDT
format (`treebank` → `sentence` → `word`, attributes `form`, `lemma`, `postag`,
`relation`, `head`). A file that cannot be parsed is skipped and the program warns,
naming it; none of the files of the study was skipped. The placeholder records of
elliptical nodes are imported but left out of the active records by the default filter of
the study (Table S11.1 gives the imported and the active records of every stratum).

**Licences.** For Gorman Trees the file `TREEBANK_LICENSE` declares CC BY-SA 4.0, while the
README of the repository and Gorman (2020) declare CC0 1.0: the two statements disagree
(Supplement S11.4 records the disagreement). Pedalion Trees:
the file `TREEBANK_LICENSE` declares CC BY-SA 4.0; the older repository `pedalion/treebanks`
states in its README, as the page shows, that the authors will assign a Creative Commons
licence, most likely CC BY-SA 4.0, and that the treebanks have moved to the
`perseids-publications` organisation.

## 3. The input fingerprints of the six strata

`reference/inputs.csv` gives, for each stratum, the number of XML files, their total size and
the input fingerprint of the study; `reference/inputs_files.csv` gives the name, size and
SHA-256 of each of the 238 files.

| Stratum | XML files | Bytes | Input fingerprint |
|---|---:|---:|---|
| `gorman` | 158 | 70,735,878 | `dad905a69a0848cb` |
| `pedalion` | 40 | 40,811,672 | `1b799d2b82395412` |
| `glaux_auto` | 18 | 47,167,010 | `fcbad2724b8b6290` |
| `glaux_man` | 2 | 3,580,782 | `ddcfd293d1908680` |
| `glaux_conf_auto` | 17 | 44,514,557 | `b03f5a325a2a8e6c` |
| `glaux_conf_man` | 3 | 4,532,597 | `a4ac3b46084fdcaf` |

## 4. GLAUx

**Where.** GitHub repository `alekkeersmaekers/glaux`, `main` branch, folder `xml`. The
forty texts are listed in [`data/glaux_sample.csv`](../data/glaux_sample.csv) (column `percorso`
is the path inside the repository, for instance `xml/0011-004.xml`); the program downloads
each of them from
`https://raw.githubusercontent.com/alekkeersmaekers/glaux/main/<path>` when the corresponding
button is pressed, and reuses a file that is already in the download folder. The DOI of GLAUx,
`10.5281/zenodo.10948374`, designates the whole series of its versions, not one of them.

**Which version: the point that cannot be settled from the package.** The `main` branch of
GLAUx moves, and the program records neither the date of the download nor the commit. The
files of the study are identified by SHA-256 only. A file downloaded today may therefore
differ from the one the study read; if it does, the counts of that stratum may legitimately
differ and the comparison script says so. The copy of the files that the study read is not
distributed here (Section 1).

**How to check.** Put the XML files anywhere under one folder (all forty can share it, and so can
a copy of the whole `xml` folder of GLAUx) and run

```bash
python reproducibility/scripts/input_fingerprint.py <folder> --stratum glaux_auto --diff
```

and likewise for `glaux_man`, `glaux_conf_auto` and `glaux_conf_man`, with the same folder. For a GLAUx
stratum the script takes from the folder only the files that stratum reads (the ones that
`reference/inputs_files.csv` lists for it) and says how many other XML files it left out; so a file of another
stratum is not reported as an extra file. If a file is missing,
`rerun_diagnosis.py --glaux <folder>` makes the program download it from the repository, and
reports which of the files it copied or downloaded have a SHA-256 different from the study.

**Licence.** According to the README of GLAUx the data are generally available under
CC BY-SA 4.0, but some texts, and possibly some manual annotations, have a more restrictive
licence, indicated text by text in the metadata file of the repository (Supplement S11.4).
The package does not redistribute any text of GLAUx. The file `data/glaux_metadata.csv`
lists, for each text, the identifier, author, work, genre, dialect, dates and declared
number of tokens, as the program uses them to group statistics.

## 5. Stanza models

The study used Stanza 1.14.0 (PyTorch 2.14.0) with the Ancient Greek package `perseus` and
the processors tokenize, pos and lemma. The program fetches them with
`stanza.download("grc", model_dir=…, processors="tokenize,pos,lemma")` on first use of step 9.
According to the code of Stanza 1.14.0 (`stanza/resources/common.py`), that call downloads
`resources_1.14.0.json` from the `stanfordnlp/stanza-resources` repository on GitHub
(saved as `resources.json`) and the model files from the repository
`stanfordnlp/stanza-grc` on Hugging Face, version `v1.14.0`.

The files of the study (Table S11.3), in the layout the program uses
(`workspace/models/stanza/…`) and the layout `rerun_model_comparison.py` expects
(`<models>/stanza/…`):

| File | Bytes | SHA-256 |
|---|---:|---|
| `resources.json` | 457,371 | `4e41c1df152146fa26ed0c006a08feea7a60bb3414bb6d57dbda24ad2e3cb99c` |
| `grc/tokenize/perseus.pt` | 643,313 | `9e1cb98d39fa21dc543c1028d8d4fb6a534e2187051b15264b37498f9f06abb3` |
| `grc/pos/perseus_nocharlm.pt` | 18,372,328 | `3ede3a6c272fa9219066a6089846e6ac77fcc2ecfd729348a674cc544a5092d1` |
| `grc/lemma/perseus_nocharlm.pt` | 2,595,726 | `f905663df890b4bf418dfde1212ed9f6bf6b096c8d93dfc669d7b44d28449dfb` |
| `grc/pretrain/conll17.pt` | 19,844,392 | `3bd32434b47d7c060036da42070f9cf2709e1e9dd315d045027bc69806317807` |

`rerun_model_comparison.py` checks every one of them before it runs and says `same` or
`DIFFERENT`. This package does not redistribute the models and makes no claim about their
licence: they were trained on the Perseus treebank of Universal Dependencies (§ 7), which is
distributed under CC BY-NC-SA 2.5, and the terms of the model repository must be read at the
source before any redistribution.

## 6. UDPipe model

The study used UDPipe 1.4.0.1 (Python binding `ufal.udpipe` 1.4.0.1) with the model
`ancient_greek-perseus-ud-2.4-190531.udpipe`, 20,492,125 bytes, SHA-256
`b85df6199730506b33cf8aa99f5a02b63bcbaaae94f78fc4c1f5f0bdd6235505` (Table S11.3).

**Official source.** The *Universal Dependencies 2.4 Models for UDPipe (2019-05-31)* in the
LINDAT/CLARIAH-CZ repository, `http://hdl.handle.net/11234/1-2998` (the reference given in
the article). **What the program downloads.** For convenience it takes the file from a
public mirror, `https://raw.githubusercontent.com/jwijffels/udpipe.models.ud.2.4/master/inst/udpipe-ud-2.4-190531/ancient_greek-perseus-ud-2.4-190531.udpipe`
(`DEFAULT_UDPIPE_MODEL_URL` in `src/greek_corpus_pipeline/model_support.py`), and it does not
verify the file (`_UDPIPE_MODEL_SHA256` is `None` there). Whoever fetches the model by either
route should therefore compare its size and SHA-256 with the values above;
`rerun_model_comparison.py` does it.

**Licence.** The UDPipe 1 models are distributed under CC BY-NC-SA (non-commercial,
share-alike), as the page of the UDPipe models states; the program does not redistribute
them.

## 7. Universal Dependencies, Ancient Greek Perseus

Needed only for Supplement S10.14 and Tables S10.12 and S10.13 (the overlap of Gorman and
Pedalion with the training, development and test sets of the two models). GitHub repository
`UniversalDependencies/UD_Ancient_Greek-Perseus`; the files are
`grc_perseus-ud-train.conllu`, `grc_perseus-ud-dev.conllu` and `grc_perseus-ud-test.conllu`.
The supplement says that the forms of the sentences were taken from release 2.4 (the one on
which the UDPipe model was trained) and that they are identical in every release from 2.4 to
2.18. The metadata block of the repository states the licence CC BY-NC-SA 2.5.

The files of release 2.4 are the ones at the tag `r2.4` of the repository (commit
`76715655e8d2976c757da10d8f92452845528dd9`). The copies with which
`overlap_with_ud_perseus.py` was tested are identified by:

| File | Bytes | SHA-256 |
|---|---:|---|
| `grc_perseus-ud-train.conllu` | 14,836,468 | `2704888e619a8a6657ca6d4f46436420a26bf5f18f54f96f71ec81ebae11953d` |
| `grc_perseus-ud-dev.conllu` | 2,081,842 | `c64b2f54432aaa267dee81918168e7cee70702d6c5389540bdee216fe743bf5d` |
| `grc_perseus-ud-test.conllu` | 1,980,003 | `4341babdbb8d5ff6af948a8eb251cda1667a20ba4829fea2cf57a59e90103323` |

(These SHA-256 values were computed for this package; the supplement does not give any.)

The program does not contain the overlap analysis. `overlap_with_ud_perseus.py` performs the
method that Section S10.14 describes (normalisation of the forms, five-word matching,
assignment to the training set first) on the comparison tables of a run of Gorman and
Pedalion, and compares the result with Tables S10.12 and S10.13 and with the figures of the
text of S10.14 (`reference/s10_overlap.csv`: 241 values). It needs the three files above
and the comparison tables written by `rerun_model_comparison.py`; with the study's own
comparison tables it reproduces the 241 values.

## 8. Where the scripts expect things

| Script | Reads | Writes |
|---|---|---|
| `input_fingerprint.py FOLDER --stratum S` | the XML files under `FOLDER` | nothing |
| `rerun_diagnosis.py --gorman G --pedalion P --glaux X --workspace W` | the XML folders | `W/runs/rerun-<stratum>/`, `W/reproduction/` |
| `rerun_model_comparison.py --workspace W --models M` | `W/runs/rerun-gorman`, `rerun-pedalion`; the model files in `M` | `stanza_comparison.parquet`, `udpipe_comparison.parquet` and the two `*_evaluation.json` in those run folders |
| `recompute_model_counts.py --workspace W` | the two comparison tables of each of the two runs | nothing |
| `overlap_with_ud_perseus.py --ud U --workspace W` | the two comparison tables of each of the two runs; the three UD files in `U` | nothing |
| `build_gcp_corpora_folder.py --workspace W --output C` | `W/runs/rerun-<stratum>/tokens.parquet` | `C/runs/…`, `C/giro/…` (the folder named by `GCP_CORPORA`) |

`W` is a workspace you create (an empty folder); it is where the program writes its runs.
Nothing in this package writes outside the folders you name.
