# Inventory of the package

Greek Corpus Pipeline 3.1.0, review package. This file lists every file of the package (except itself and `SHA256SUMS`) with its size, its SHA-256 and what it is. `SHA256SUMS` lists the SHA-256 of every file except itself, in the format of the `sha256sum` program.

To check that nothing has been changed or lost on the way:

```
python reproducibility/scripts/verify_sha256sums.py
```

The package has **199 files** (these 197, this inventory and `SHA256SUMS`).

## Top level

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `.gitattributes` | 392 | `1f51a280598eca7dc07035528ad0da384d1798b0b04989d952e89952726c87ea` | Tells git not to convert line endings, so that every file keeps the bytes (and the SHA-256) that SHA256SUMS lists. |
| `.gitignore` | 97 | `46ce01db03b3280b475c39a03ac679ba1a7a24cbd3c2ce7d7327fd29b2cbb7c8` | Patterns of the files that a version-control system should not track (caches, the workspace the program creates, logs). |
| `CHECK_INSTALL.bat` | 244 | `de38268ed186275232eebbba6264e8b98dbd5e9f1f066a7f8b7cb8a941dcedb8` | Windows launcher of CHECK_INSTALL.py: checks that the installation works. |
| `CHECK_INSTALL.py` | 12,252 | `479ba1693b54d66b3c2f254e5de5311a18938bd9de2875f43ce3df024f89a37f` | Reports what the computer is really running (Python, libraries, Qt) and whether the program can start; writes CHECK_INSTALL_result.txt. |
| `CITATION.cff` | 666 | `bba15a537008209be68c3dcec4c238c714a84743fbee2bf25ec9d837efc6b2f9` | Citation metadata of the software; the authors are withheld during the double-blind review. |
| `GUIDE.md` | 49,285 | `6e245563e898261f6bcd0eb06f388a28dd251b716f66f29d48dbae6841debd84` | The user guide: every page of the program explained from the beginning, with no assumed background. |
| `INSTRUCTIONS.md` | 4,574 | `7eac42dc0a59c74e657c59d0ed356c8efbe244ddc2497b11a9273fd5863a6b53` | How to install the program on Windows and start it for the first time. |
| `LICENSE` | 1,397 | `01d5ee6c2b5a582ec28fd1812bba573bf09403761421c4c47c1f0aac882b00cf` | MIT licence of the program; the name of the copyright holder is withheld during the review. |
| `README.md` | 21,439 | `028f29262ba9b7533e5d99e73da39b5f58c6d79969a0898ef261c42f5950f701` | Overview of the program: what it does, quick start, corpora and study data, the optional comparison with the models, documentation and reproducibility, citation and licence. |
| `app_qt.py` | 6,478 | `b304f5f18e6cae031dffa43f349d47467d59ad9f428e6a7137aff3257db16713` | Entry point of the desktop application (PyQt6). |
| `pyproject.toml` | 2,046 | `40db0a94b027bff538f7435e2592a862d22d191e32df0967d892a5f2641adb32` | Build and dependency declaration (hatchling; Python 3.11 or later; the extras `models`, `dev`, `all`). |
| `requirements.txt` | 450 | `460a098103c3368a422f9018fab988f12800b86889ed6b5f947d1d9f2eebea4f` | The minimum dependencies, for `pip install -r requirements.txt`. |
| `run.bat` | 804 | `3c8279362a7c8d0da3ab0cc896c275c30d300095721cbf7d52a569cd9a048936` | Windows launcher of the application. |
| `setup.bat` | 7,200 | `dcd1f7abb366d505a674de939021026900bb232cce7d1f03c616108a1152a498` | Windows installer: creates the virtual environment and installs the dependencies, optionally also Stanza and UDPipe. |
| `tools_regenerate_catalogue.py` | 1,927 | `4ae93d46a50c18954c54e203188627494eff03c31ec00036837ae3bfd79ef950` | Rewrites data/catalogo_controlli.csv from the catalogue in src/greek_corpus_pipeline/rule_catalog.py. |

## `data/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `canonical_check_texts.json` | 29,663 | `f8e19c51133535c5e1ebcc6248e3ba66e6e50f48d4e6eb3067b8e336dfa8f99e` | Reference texts of the checks (Italian), against which tests/test_canonical_texts.py guards the wording. |
| `catalogo_controlli.csv` | 52,113 | `4c6844d5c7e1cc0064f52f2f96cf7b1f353958852d26c5b687c0aa3f2e5359f4` | The catalogue of the 77 checks: identifier, names and descriptions in Italian and English, family, class, treatment, severity. Cited by name in Supplement S1. |
| `glaux_authors.csv` | 41,855 | `c98240d01d1ae3b9925e81eba91874d19bbbecb7b9dcb46ebc1bf1241161d4f6` | Metadata of the authors of GLAUx (TLG identifier, dates, period, dialect, genre, origin); names in Italian and English. |
| `glaux_metadata.csv` | 203,879 | `bf5b720f6d260cc4ff8525de5ca9b2d58077e63fcc50c55047e2783ce11a08dc` | Metadata of the texts of GLAUx (document identifier, author, work, genre, dialect, dates, declared tokens). |
| `glaux_sample.csv` | 4,879 | `ad3603e1260653a0d2003fa6fdc86ba2e536ccec0af8b17b4295c7d921288b66` | The declared GLAUx sample: the forty texts of the two draws with stratum, seed, path in the GLAUx repository and declared size. Cited by name in Supplement S9. |
| `gorman_metadata.csv` | 31,976 | `65b8fddbd46966b71a46174e41606f394d7d6995fa7eb3492f77334639d6c473` | Metadata of the 158 files of Gorman Trees (author, work, locus, dates, period, dialect, genre, origin, editor). |
| `pedalion_metadata.csv` | 10,409 | `4616683bb4abfee85a3f178c0449df10039defbb2094a314eef88b8c1d3f0b4a` | Metadata of the 40 files of Pedalion Trees (same columns as gorman_metadata.csv). |
| `tlg_authors.csv` | 5,063 | `46beb980abe3624b7e240a28538c434417e2248d5afeeb160e944b09569c1bce` | Authors identified by a TLG number, with dates, period, dialect and origin; used to fill the metadata of corpora that name only the TLG identifier. |
| `tlg_works.csv` | 5,203 | `e5233c11243f7061f7bd3c10b844fa216baf1f766f4bee302a79206434454bd5` | Works identified by a TLG number, with titles and genre. |
| `user_metadata_EXAMPLE.csv` | 419 | `fff484bf779dbeeed4bd162b6f45c80ef8969b51a28371cb8b33ad7104e03cfc` | Template of the metadata file that a user can supply for a corpus of their own (two example rows). |

## `data/liste/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `enclitiche.json` | 1,602 | `9ee57299c638645d409477f1d0ce6c49554d797fda81c59aeaee9ca41a426159` | Closed list: the enclitic forms (Table S6.1 of Supplement S6). |
| `estensioni-locali-di-pos.json` | 1,166 | `72c815da5d8e1a669d2e0d8453f70dea885019ace8a75e14d07edd12ec50a80f` | Closed list: local extensions of the part-of-speech repertoire of the scheme. |
| `lemmi-grammaticali.json` | 2,726 | `bb1f0c158a37445cecf1aea365e4dc3d9a75b323b0c6c352e7ce63710b2a32c0` | Closed list: grammatical lemmas (the grammatical-word filter of the statistics). |
| `lemmi-particella.json` | 1,217 | `e857692769f1d614a46c375256c35e3a79a486aa8f07613070aa92ba9c3eab79` | Closed list: particle lemmas. |
| `loci-dein-participiale.json` | 3,682 | `76a132d04acc4085a8725eecaba932358d4b25528c5ae446f48afb6699e4fe0f` | Closed list: the passages where δεῖν is read as a participle. |
| `numerali-indeclinabili.json` | 1,808 | `2e384bccec2042b53d0e0454b523c6302d255269fe17fdb1d1348b6ae28826ea` | Closed list: indeclinable numerals. |
| `pronomi-personali.json` | 1,330 | `cd93149ae8f080e7f5eeeca0252f36320a304d50675ee88388d9cf87ae554a75` | Closed list: personal pronouns. |
| `quantificatori-non-concordanti.json` | 638 | `8bccdb22778ae4f6c724aa8cbeba15544ad92c545d09b506e0a44c7d4c88cc4d` | Closed list: quantifiers that do not agree with their noun. |
| `risorse-con-metadati.json` | 2,752 | `dfc4b80cbdd620395cc2ed596b50435c04540203bf02960dc84b5345a8c9fe7f` | The list of the lists: each resource with its version, source and fingerprint. |
| `varianti-canoniche-di-lemma.json` | 971 | `67def129de797de2524f96249b9fe965713721dfc41c600c95a94c898fbe41b9` | Closed list: canonical variants of lemmas. |

## `docs/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `GCP_metadata_guide.docx` | 16,132 | `44e63161f9348ce2004d02ba309e50f0163f7e4a83e0fdfae91bf2ec00906b1d` | Word guide to the metadata: where the program gets author, work, date, period, dialect and genre, and how to write a metadata file of your own. |
| `GCP_user_guide.docx` | 35,700 | `4902b96f03311db0d65ac6b478fba6e60731be6cd42ce408655eeda9c1049194` | Word version of GUIDE.md, laid out for printing. |
| `REPRODUCIBILITY.md` | 21,027 | `cded9eccd92b0d4a3dc28b24a74c241c4825475c559959da44cf025f6a054ecf` | The five counting units, the nine numerical parameters, the sensitivity analysis, the reference results, the fingerprints, the environment of the measurements, how to run the tests and repeat the measurements. |

## `gui_qt/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `__init__.py` | 46 | `ce474342e692abea5b80739ae1e4f1be406f67ea142949502df46a6998426860` | Package marker of the interface. |
| `chart_view.py` | 9,770 | `13799ad9149ee5d321658b62fa983a37b58a1ae021c3baf006f8a11c87927630` | A matplotlib figure inside a Qt page, with a save button that works. |
| `df_model.py` | 14,733 | `a4daa3c403b995f23d0eb98c6cb94361720ad1503ea7c605c3a548e8e72d9296` | PandasTableModel — the bridge between a DataFrame and a QTableView. |
| `i18n.py` | 163,178 | `3120ce3c579aab4acab44c140f05d06ba5399949cfab0f0ed6daf23e1c7047e7` | Every visible string, in Italian and English, in one place. |
| `i18n_cerca.py` | 6,625 | `67450652e0fc0606487b6747198fbf24a57509114cc5e1a4653fc54baf2e8fe8` | The entries of the “Search the corpus” tab. |
| `i18n_correggi.py` | 22,259 | `7dd6246f329c194f2bbaa27b7beceb21dd3365ce304bfc74ea7fc3cd3f2099c0` | The entries of the “Correct” tab and of the “Revised corpus” tab. |
| `i18n_panoramica.py` | 27,791 | `578a915c1f7cd12da45f686791c71ab72001a662b59a34e7e774aee89433a970` | The entries of the overview and of the statistics, in Italian and in English. |
| `i18n_struttura.py` | 35,217 | `ef31329a25797bdad7818dbb2e4024f0a61ac96d7b7540d0dc077088b0050bed` | The entries of the page on the AGDT 2.0 scheme, in Italian and in English. |
| `main_window.py` | 35,030 | `72db76c40346dafc83306782ad2a585c548156c8396a2df7085071b61f7df666` | The application shell: a numbered rail on the left, one page at a time. |
| `style.py` | 15,716 | `f07f3dc4cf1c6e24ca93ad504ea156e74ab9c9165b48ed10551447ab9c76ad8f` | The look of the application: a palette, and the rules that use it. |
| `variazione_testi.py` | 3,912 | `d193836ae47cb1024a929da83324d89897a4c3907462627554cd83cdd88e6035` | Headers and explanations of the tables of the cores, plane by plane. |
| `widgets.py` | 37,246 | `5c4ef435123dfd29120dd848c908aea6b4d2724f125be1211bcda3a2cd2fe99e` | Reusable pieces of interface, built once and used by every page. |
| `workers.py` | 45,937 | `a4aba63bcfc64098375c8e32b1ef2fe17da64e6d6a43d99829bdae8f118926f9` | Background work. |

## `gui_qt/assets/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `check.svg` | 220 | `355891003c41ad6c8f342264e2caf91c6fc6d0480e12626ba5914fa5c5363939` | Icon: tick mark. |
| `chevron.svg` | 213 | `98e1e0202b9d203650bd3f617c85621a965761789fbe1ed2fe7192cfa35bbb90` | Icon: chevron. |
| `done.svg` | 214 | `101671c3b4d56682b1ecea2d543d5a1fa60d61d3ad1ae5f78583d3551a1afe51` | Icon: step done. |
| `radio.svg` | 135 | `22709843308e71d623db51c4dc2985492e9de1c13a0312f8377fa523e0b6bc92` | Icon: radio button. |
| `search.svg` | 255 | `d3b3d06b6c4bb0f39026aca9a03834b4eb630963458e2ee55ff5bb97c70d9f93` | Icon: search. |
| `sort-down.svg` | 133 | `33c1055e920407b7b2502e4b5d3d326aec6a2cca5489e96dac1c86b4f3430519` | Icon: sort descending. |
| `sort-up.svg` | 133 | `9c707ce25e5446cd42eb661d726a02b7aea2ab698e0d63d7f501c1c4fe7cbcc2` | Icon: sort ascending. |

## `gui_qt/pages/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `__init__.py` | 334 | `f37bf8ec184f56209e36474cb6f2e72eea9d99cbe3612b4dd33721787652c928` | One module per step of the workflow. |
| `base.py` | 17,450 | `013534acf3b055382eaabe42db278860eaf69c182b8952c49b563832d1e13890` | The shared shape of a page, and the state every page reads from. |
| `charts_page.py` | 28,144 | `1df0444294dcbe2712642edc2baf622f56055dbf1ca73611fc4606fc1f0e7a24` | Step 8 — the charts, and the one button that exports all of them. |
| `errors_page.py` | 44,329 | `01c14476989a42a2405c45dd8b43cf08cf66eeb789e78b921d5b98e231c7f2c7` | Step 3 — run the diagnostic checks and read the results. |
| `gold_page.py` | 20,755 | `228820918664736ca815f2921dfee390cb1abd915dedfdaaeed9ce0353732050` | Step 10 — the gold standard corrected by the user: the result only. |
| `load_page.py` | 21,098 | `ba5ce580aed2a1cb57b1e903a267e0e891876e12ba9d72cae566008e590bcf86` | Step 1 — put a corpus into the program. |
| `models_page.py` | 27,296 | `45e9a9e25b4eda73069949766dc364965ce47e512cb12104fa97b1b750b5fd0e` | Step 9 — Stanza and UDPipe against the corpus, and against each other. |
| `overview_page.py` | 16,407 | `46d8fede76e49b7de95af0efd346e9cbb78ad5636dd9cfdac9601b4026045ed9` | Step 2 — what is actually in the corpus that was just loaded. |
| `review_page.py` | 51,242 | `82cb7612036c0e6349c9f2cbeb58da22a26bb7fb960c2f9946694c8078b9a282` | Step 5 — deciding what to correct, one case at a time. |
| `rules_page.py` | 17,722 | `0f159d81cb75107ce6e22b9e5b891b44c86ffe178dc0e4a8e960c1334e42056a` | The last step: the AGDT 2.0 scheme, explained from the beginning. |
| `search_page.py` | 23,896 | `e713c32d406b020e972e33ba1d8819b1e38e49f5ea43a8b543b3db1a79b9ef16` | Step 6 — searching the corpus: the occurrences first, the analysis after. |
| `stats_page.py` | 32,196 | `d28301824c75ce66337b2834f3db80d6542aab3726d59cefe8b91b03f5dd800f` | Step 7 — the corpus in numbers. |
| `variation_page.py` | 7,542 | `8d5ef9423b6ff652a3a9fb408910ab9347d2d2516815d7fabbca4d942f25c4fa` | The variation cores: the same thing annotated in two ways. |

## `reproducibility/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `ACQUISITION.md` | 14,835 | `af3e8829fccab0d393b0888a29c81f8a077bf5d16b203d59c341e2c778d18939` | Where to obtain each corpus and model the study used, which version, how to recognise it, where to put it, under which licence. |
| `README.md` | 19,797 | `721bfe42621bacfedfa36d9b04f448a94d5d43bc0ca36901e37a801c10aed7da` | The reproducibility kit: levels of checking, scripts, what each one reproduces, and what it cannot. |
| `REVIEWER_GUIDE.md` | 48,472 | `7e6899cf41583bd19854bf999f79b0dd6c823858ff469f3b2ae66dd2b0317c7d` | Matrix that links every promise of the article and of the supplementary materials to a file of this package, a command, and the outcome of running it. |

## `reproducibility/reference/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `checks_overview.csv` | 8,209 | `e2d2cded5065bec3d2cc99d6a0b839a7e43546f851b24fc0f51f887f6df37402` | Per check: identifier, name, family, class, treatment, severity and findings in each of the six strata (Table S1.1). |
| `findings_by_class.csv` | 295 | `e0ddade451e75c7ec3e236edf6e4cd7dfdad9bf01a8f32c5ea4de1efd42f3163` | Findings by diagnostic class and stratum (Table S1.2). |
| `inputs.csv` | 281 | `a4e007cae93d079b69e800e494df1381fbdd4427f06f4b7c85512a6ffff69588` | The six strata with the number of input files and the input fingerprint (Table S11.2). |
| `inputs_files.csv` | 24,145 | `9befc38f6bcb6a60dacf00adfbbb882eeb58dd55ce1f0d7b65f278b567e2f352` | Every input file of the study with its size and SHA-256. |
| `s10_model_counts.csv` | 12,932 | `64180c331f89700707b49fba21f672cdcf0bd50116bfb2ba1b8860ea094c253e` | Reference counts of the comparison with the models (Supplement S10). |
| `s10_overlap.csv` | 31,282 | `e9942ccbca7731d3cd9d6d2457ebce10eb87fcf06c036117d2481e100b7e6bb8` | Overlap of the corpora with the training data of the models (Tables S10.12 and S10.13). |
| `table_S10_1_provenance.csv` | 331 | `499668b58fe4bf3a35c4a6d0e6f6e2ff34d17802b2026bb95aaea0a160b1d4cc` | Provenance of the model comparison (Table S10.1). |
| `table_S11_1_units_and_findings.csv` | 667 | `e7f0f8578a771df617345be6a1d8058635ad8f9d9d3d9752c0db081d7dc59b07` | Counting units and findings of the six strata (Table S11.1). |
| `table_S5_1_rare_relation.csv` | 2,292 | `0d724eea99059ba32925e992bc6691f36b35548c85cb84e89c06f3547a93358a` | Sensitivity analysis of the check on rare relations (Table S5.1). |
| `table_S5_2_rare_lemma.csv` | 2,560 | `e70b86d6d92755489ee7e5cc8b3e73944bc9e6cd75393c4149d91b9b6212085e` | Sensitivity analysis of the check on rare lemmas (Table S5.2). |
| `table_S8_1_nuclei_by_level.csv` | 400 | `1446f771b2d56d4f20dd7bbcba4d69e14a2ec41a04d466a0ef6c5ec9892fbf7d` | Variation nuclei by level of the five planes (Table S8.1). |

## `reproducibility/reference/finding_keys/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `glaux_auto.csv.gz` | 74,743 | `159cb0f9bccefde158047080fccc2883ab4ef85fa6992bc996a034958db1024e` | Sorted keys (rule, document, sentence, token) of the findings of the stratum GLAUx automatic, first sample. |
| `glaux_conf_auto.csv.gz` | 66,291 | `983235e9306d2f3be72916db3421f462f12272f03fd4c4691279cccd95ad1607` | Sorted keys of the findings of the stratum GLAUx automatic, confirmation sample. |
| `glaux_conf_man.csv.gz` | 15,415 | `9beb8c5efc306ad7d1d2d940783079f25c93e8122f81ea5b63d5506af6b3ea9a` | Sorted keys of the findings of the stratum GLAUx manual, confirmation sample. |
| `glaux_man.csv.gz` | 12,400 | `8dba2becbc92407a27285c2473e9372c6042b3c38406a227a892fe86ac7175d9` | Sorted keys of the findings of the stratum GLAUx manual, first sample. |
| `gorman.csv.gz` | 345,650 | `b2f2eece1e8bfcac6fcc02f73a82ecadc68273f0d19e2000be8e53ee450f2b86` | Sorted keys of the findings of the stratum Gorman. |
| `pedalion.csv.gz` | 105,390 | `c5d6135c8cc8302f91ac84a0c095e8ab827403e9793d54ac2b8b318e34ff64bf` | Sorted keys of the findings of the stratum Pedalion. |

## `reproducibility/scripts/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `build_gcp_corpora_folder.py` | 4,484 | `550457f80f5bcf21945c7c0e1f550dc0292c260e720bddb554ba09d187023df9` | Build the folder that the test suite reads from ``GCP_CORPORA``, from a re-run. |
| `check_claims_from_reference.py` | 25,883 | `c91171639e271243322d9c48f62680fa8a2aefe91caddfb7768bb56a99f51b1f` | Check the aggregate figures of the article and of the supplement against the reference tables. |
| `compare_run_folders.py` | 19,435 | `7cc14d0ff6f183d13f360603dc4db4602271b4260f5c780c8a707edf950d550c` | Compare two run folders cell by cell (the repetition that Supplement S11.2 describes). |
| `compare_with_reference.py` | 14,596 | `6a4e0f8d276a03e27b810862587a61ed5916da1721797f96b4acc3a05aa1860e` | Compare a re-run (``rerun_diagnosis.py``) with the reference values of the study. |
| `glaux_sample_draw.py` | 5,756 | `955baf173c544afdddc4ebe7f990a477437c83b994270fa56dd2d030f74dafe1` | Redo the two GLAUx draws of Supplement S9 and compare them with ``data/glaux_sample.csv``. |
| `input_fingerprint.py` | 6,285 | `0a0bba3a962c193c7a0e388678a40525c66f4793d878d1967c5ad24721251380` | Fingerprint of the XML files that a run reads (Table S11.2 of the supplement). |
| `make_reference_tables.py` | 4,270 | `d0eaf0c72438e911a4d26d30b160446567151294b4fe153ed2929344455519f3` | Rebuild the machine-readable reference tables from the runs of the study. |
| `overlap_with_ud_perseus.py` | 14,940 | `f785c915f4162062c99d8335d7ba5aaf734b39d600bcf768319241ab822a871d` | Redo the overlap analysis of Supplement S10.14 and compare it with Tables S10.12 and S10.13. |
| `recompute_case_studies.py` | 18,337 | `dfe74f5a6e99698aaf5293c227ddca9ebca5946de01898bb7bac67f322cdf889` | Recompute the figures of the ten case studies of Supplement S7 (and the tokens touched by the findings, S1) that are not simple counts per check. |
| `recompute_fixed_limits.py` | 15,770 | `a08746379ed4e860c970e877861ab28b6e17dfad2d201b3b8ad277a8ce213aaf` | Redo what Table S4.2 of Supplement S4 states about the fixed limits of the code. |
| `recompute_list_alignment.py` | 17,180 | `8dc27c79f6714eabe2e0fdd29a64628e02462329f21966716301ac29dfe32781` | Redo Table S6.2 of Supplement S6: what changes when a closed list is aligned with Smyth (1920). |
| `recompute_model_counts.py` | 15,852 | `16211d7076ed332b983160d4cedf962ad68bde66e8ca904034684bb7da9fe183` | Recompute, from the comparison tables of Stanza and UDPipe, the counts of Supplement S10. |
| `recompute_model_tables.py` | 30,061 | `9a4292dcb28748bf25afaa0c6d9a2ba70867c7595c591fde1d6117661fdfbd7b` | Recompute the tables of Supplement S10 that ``recompute_model_counts.py`` does not cover. |
| `recompute_table2.py` | 7,181 | `ccaaee15043aae3e3afb6b38f370b61987ef7ba7a49bbbecd3a7bf7a229b48df` | Recompute Table 2 of the article (the size and the shape of Gorman and Pedalion). |
| `recompute_units.py` | 9,758 | `85e9e1fc59ddf7300ae5c5af14e3f251ea7452b919aab0d9b1c56d7c494d1ec4` | Recompute the counting units of Supplement S11.1 and the figures quoted in its text. |
| `recompute_variation_concentration.py` | 11,674 | `0c2d87d0f8c288fb1ddf3148226c000a01d124c99e6a7f1beb3c834dff43e666` | Recompute the concentration test of Supplement S8.1 (Tables S8.2 and S8.3, and § 6.1 of the article). |
| `repro_common.py` | 5,982 | `a002126e5232a1485933d3cb3417f06ec05d1032b431c26f08c35b48790f5038` | Helpers shared by the reproducibility scripts. This module is not run on its own. |
| `rerun_diagnosis.py` | 10,798 | `2c9c5c394e2cb6021a27cb736fb4c15d48bbccd3bb8b7e1e98a6b4d74f505c28` | Re-run the diagnosis of the six strata of the study with the program of this package. |
| `rerun_model_comparison.py` | 7,206 | `e0b6d22686bbde6c2fd6e45b51e87dc3ec5d5e5dfb92c284f1a290d177d40feb` | Re-run the comparison with Stanza and UDPipe (Supplement S10) on the runs of Gorman and Pedalion. |
| `sensitivity_analysis.py` | 5,966 | `23d0699e3572eb55435b4e86615cf81704acedb110d9d732a81d9ff3dfdcdce7` | Redo the sensitivity analysis of Supplement S5 on the runs of the six strata. |
| `verify_sha256sums.py` | 4,477 | `61f51d24c5d3fbfc0a6e848603f1c11ab3b1683c2cb5e6ae0737bbde4e11f239` | Check the files of this package against the list of SHA-256 sums that came with it. |

## `src/greek_corpus_pipeline/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `__init__.py` | 3,636 | `eaf3d238c28d6e8d1e3d95bdb41c10be06dd1d8f31d80b75ddbbbe0df2e2367d` | Greek Corpus Pipeline — diagnosis and analysis of Ancient Greek treebanks. |
| `agdt_schema.py` | 37,540 | `dee0458fed9ba25a5479a827751c4ec51d241cbd96643805bbbc7f35e2cfde0c` | The AGDT annotation scheme, declared as data rather than hard-coded logic. |
| `agreement.py` | 32,584 | `f7d26feca7c77249a699e46631396038ae1832042408fe9ca1350ff0b569c86e` | Where morphology and syntax must agree — and where they demonstrably don't. |
| `analysis.py` | 48,068 | `8b2ebbc12196aed6ff615ae459d2528ea08195de37500b367245f76981ea3996` | The tables behind the interface and the exports: summaries by author, rule, lemma, with the per-distinct-value optimisations. |
| `analyzers.py` | 21,232 | `ae698105fdb3f75790ad54e30626d8cb0733da069d3df81087d7e0a841d77d25` | Run Stanza and UDPipe over a corpus that is already tokenised. |
| `cli.py` | 8,208 | `027099b878f957bacfd7d8403b92d983fa1064fb60d7fc063b1106c149605f2b` | Command line interface, for batch work and for reproducibility. |
| `conllu.py` | 13,821 | `0c30da2b06b0a3181f0ce1c109cfdcd0b2182126661e6bfea2d14bbe7375a21a` | Export to CoNLL-U, the format Universal Dependencies uses. |
| `corpus_metadata.py` | 40,334 | `dfce2c7cc705391c559a7229c7732c85d1f8d0163a6cea152fd99740cd24d5da` | Who wrote what, when, where and in which dialect. |
| `corrections.py` | 18,910 | `e7e370e6d698cc8cd745d84d1ff3f8b0dba4c5e0006d7b49631700ef94d8b94c` | The form dictionary: what the program accepts, and what it does with it. |
| `cpu.py` | 3,426 | `5e20fdbea2650f4f110f9607f0ee88896bab42f4926c6a6ad876f205440c9065` | How many processors the program takes, and when it decides. |
| `evidence.py` | 3,702 | `22657a110f110de935f9f9f852521607e0edbf41a6313494a082beb0459d3421` | The occurrences behind a type-level finding. |
| `fastmap.py` | 6,249 | `3af1082f5474a918750cb5fc9eaa22ea564d39f2b984868062a580b66c0959a1` | Apply a Python function once per *distinct* value instead of once per row. |
| `figures.py` | 42,247 | `0c46ded9ca7e76ce6e611553e74d9e78acde34184a3f37b529f24be129b01d27` | Every chart the program can draw, and the export of all of them at once. |
| `github.py` | 6,248 | `98b0654e23326da4f71918efb397847a6ed8f5d60d03d58b00219166b9ca27d5` | Downloads a folder of a public GitHub repository (archive of the branch) into the workspace. |
| `glaux_sample.py` | 6,048 | `41a3d556ef3f0f13b733101cb5c1203dc7bce24dd5bfcc1f68cf8ef7a39ea652` | The declared sample of GLAUx, and how to download it. |
| `gold.py` | 18,542 | `05463de6ca055407addf86d162b1b392353f8af2ef7775c52bf98bee3157bc8f` | The gold standard corrected by the user: how it is built, saved and exported. |
| `issue_testi.py` | 91,039 | `d62860cbd76bdcda2a5e137f8cda74953c8f75e70a12207d75c1642632dc31c8` | The texts of the individual findings, kept apart from the code that finds them. |
| `lemma.py` | 21,141 | `7ba87a275b6c93d591d3aa3ad7103ce1eb8112b9a62889574cad0eebe660af44` | Lemma-level diagnostics (the six checks of the lemma family). |
| `manifest.py` | 7,965 | `402025d4b65ef67a75bf6396bbb9083b23d0d316e8c65d2e979e538bd5b2aebe` | The provenance of a result, in a single file. |
| `model_eval.py` | 26,248 | `865ea4f592fe884261b915fd61d5fe73c0581db312d19b345197c2fbcd05290f` | The comparison between the annotation of the corpus and that of a model. |
| `model_support.py` | 5,890 | `6cafca089494d7de52b3fe66b10a2c9449a1f230f0601c36b6d8290fe1ee9531` | Locating, downloading and verifying the Stanza and UDPipe model files. |
| `modelcmp.py` | 22,275 | `da23a9ca6c2f5aa70236e72c6bef8a52d3d529587eef003f8131d05a47dafd04` | Comparing annotations — corpus against models, and models against each other. |
| `normalise.py` | 12,162 | `d2ac41cbb4e6b4c1f77f34e56355ad09d8c88f3113f9432bd8a277a4ac7850a2` | The normalisations, one function per purpose. |
| `orthography.py` | 50,903 | `abd6b55331d7ec222c56fd6ed25d4e999626ddc88a2837c5260705a1788a0f10` | Text-level diagnostics: Unicode, diacritics, script mixing, encoding residue. |
| `postag.py` | 53,908 | `f27eccbbe7eb1def04cb89fcdda8b151508f7860370efe089b7e6a1d80737a76` | Morphological diagnostics on the nine-slot tag (the morphology family) and the repairs they propose. |
| `proposte.py` | 8,254 | `9eb869a43d4f9703c43ffc480119561a0c57f1659b73445583c4dcd201eb8477` | Who proposes a correction, and who must propose nothing. |
| `resources.py` | 6,371 | `82c1b54d192a8c2a106a09aafee00bfbcbc91e8784ba80d8d3368c7b8ea4c61e` | The lists that decide a scientific result, kept out of the code. |
| `rule_catalog.py` | 110,649 | `926ec264e796557f290fecf9a726c37b8cff6c3193a977796fbfe01cd2597cc2` | The catalogue of diagnostic checks: what each one looks for, and what can be done about it. |
| `search.py` | 54,502 | `7d8c2eeefff4852dd3d7b780d8231a752bc82845b60727d477a26bb98a4a9142` | Searching a treebank the way a philologist actually searches. |
| `stats.py` | 60,774 | `f7e20e8a9b4a9860a89739655667285a4845beaa064fed6ad9341a4de7e694b7` | Statistics a classicist recognises. |
| `storage.py` | 9,304 | `21c4ea4b23e041eea17a2f5acedbe6d5a39de0d97defd50d750825de0cb9fe41` | Reading and writing the files of a run (tables, statistics, evaluations) in the workspace. |
| `syntax.py` | 49,135 | `126a7c1d78ede9789d863b2e257d7b900be9bd4fefc07fdeebc55246c008ba1f` | Structural diagnostics on the dependency layer of an AGDT treebank. |
| `udpipe_processo.py` | 14,897 | `1ee8214127ac2083ebb3f85d079314326e3dc070b0fe89d1cf45a174e84c5daa` | UDPipe in a process of its own, because a thread is not enough. |
| `units.py` | 26,490 | `13c45e56c6ec5860952db20a887fb76665db66fa65c91952c22b945d5c510a67` | The counting units, defined once for the whole program. |
| `variation.py` | 32,585 | `3d6d1cbb60b16dcf6d99b309c99a993e413e7df110efeffe36154a9f5950d149` | Variation cores: five planes, and the attribution of each. |
| `xmlio.py` | 19,193 | `a394e7e3f5c9dfec08398b22182997dd2b4bf4d2487b6b4f80943639c771c6c6` | Reading AGDT XML into the tables of tokens and arcs. |

## `supplementary_materials/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `GCP_Supplementary_Materials_Anonymous.pdf` | 1,156,680 | `b5baf7c99baec46e809fd8d1995da4dc8b2902a0d55f85e8abcb35d42f86e444` | The anonymous supplementary materials, byte for byte as submitted with the article (a copy, for cross-reference; no script reads it). |

## `tests/`

| File | Bytes | SHA-256 | What it is |
|---|---:|---|---|
| `conftest.py` | 7,500 | `9c3f7a66cc29df5c2a21e03d84bba84945b3d9a9fedbb92a2ac99f749d617131` | Test module: A minimal but real AGDT corpus, and its tables, for the tests. |
| `real_startup.py` | 6,826 | `63078145f3c3ee81e8074cad899a53ea5acb455c1f66bd13a77caf5b37f40e98` | Test module: Starts the real application and walks the flow from beginning to end. |
| `test_canonical_texts.py` | 4,828 | `59572a7ae3f6fa38f94d09d6af708130e99370fc11d8d63f80e708a9ec015b6a` | Test module: The reference texts of the checks are not rewritten by accident. |
| `test_chiave_di_ricerca_unica.py` | 14,939 | `59ce2018cc2fad5130355c828aa36ef5c7ab452ba55e3a67d729a1753059fd5d` | Test module: One word, written in every way, and the same answer everywhere. |
| `test_ciclo_di_vita_modelli.py` | 38,578 | `c1c8d9bb5f08c3c1f9fe934fbf178a0f21d431be6102d98fc410138c85718e71` | Test module: The life cycle of the models step, from start to return to idle. |
| `test_cinque_controlli.py` | 15,982 | `b8f3760c1a8045cebe899d9ab16a10b3d711c25b58ec391053d76e822aa98a30` | Test module: Checks whose canonical text makes a promise, held to it. |
| `test_comandi_cliccabili.py` | 19,358 | `8cf65039a1e67ed30577ff305d8052498ae540dfc5cb541921a0c81baec7710d` | Test module: Every command that looks pressable must really do something. |
| `test_compare_run_folders.py` | 18,091 | `ce9bf1cbfc941410bedf4bb075f8e4797b84cccde640f2aff5b4d416057636fd` | Test module: the run-folder comparison of the reproducibility kit (a missing value against a number, a left that became a right, a table in only one folder, the two label columns). |
| `test_compare_with_reference.py` | 12,383 | `24d1be86ecdccf0dce2f33e13b92df1a9371ab5bca6c52e5917e8e2ed4c46e03` | Test module: The script that compares a re-run with the reference values of the study (``reproducibility/scripts/compare_with_reference.py``). |
| `test_confronto_modelli_schema_reale.py` | 13,433 | `4cd704ad5d5ab0ea076052cf737dd4e6c55eddde04ce4977e737676273c05473` | Test module: The comparison between the models, on the schema the program really writes. |
| `test_diagnosi.py` | 28,953 | `be6dba5babd455406659365f1c0c55f7c189147033da389ecda7561e2c6a14a9` | Test module: The diagnosis of a finding: key, parameters, and the sentence that comes out. |
| `test_elenco_e_pannello.py` | 8,503 | `6ea19b38a3e0b7b48236feeece3d55ca4b7772fcc7a24d0bec4be6c30a9dcc20` | Test module: The list of findings and the right-hand panel, as they appear. |
| `test_famiglie_intatte.py` | 5,245 | `06f767a200b793ef8a44bf9f6e1a80ad1266944ee83bcd0556aabdd5cb553928` | Test module: The five families of checks must keep running in full. |
| `test_flusso_gold_gui.py` | 19,301 | `8a3a6cb704b00ccbb2193e7a94757cdb5c534f1d6df57b5c763740787e6cd7d8` | Test module: The gold flow really walked through, inside the application. |
| `test_forma_e_nfc.py` | 12,139 | `aac2f2b4a5f887cc81babe89466218c1470e725aca9f46fe57a2c4441854c8be` | Test module: The correction of the form and the conversion of the corpus to NFC. |
| `test_gold.py` | 8,923 | `e48323766f13f819ca01dd59f60df595b24b0f167d485aaa01ec3b3c31ea6af7` | Test module: The gold standard corrected by the user: saving, exporting, comparing. |
| `test_input_fingerprint.py` | 8,505 | `20ef6144b5c47aa03c7acbce07944454cf55cdf947756e5f95dcaa4423cd691d` | Test module: the input-fingerprint script (the four GLAUx strata read by file name from one shared folder, Gorman and Pedalion as a whole folder, the two reference tables agree). |
| `test_installed_layout.py` | 9,392 | `9ddae1bd6d08240acd1a7885f06d82640bde8cc0e4debe791649a4d7c06fd62d` | Test module: the program in the layout of an installed wheel, as a copy and as the wheel built from pyproject.toml (where the lists and data are found, the command line, the error log). |
| `test_invariante_stato.py` | 5,909 | `15fd194b55aa548ab73de099f2cb23040b4ae9fadbd8ae586856d0c50d5e31ed` | Test module: No corpus loaded, no corpus data visible. |
| `test_lingua.py` | 11,057 | `b2ec495506aa92355ea4d0fd69373116ca7806cc616e0c27332bfb398ca607be` | Test module: The change of language must reach the dropdowns and the charts. |
| `test_lingua_completa.py` | 10,033 | `799f49ca51e2bbfd6220cf5fb260691c012658c5028cd724b70c8b17d0a72346` | Test module: With English chosen, not one Italian word must remain in the whole window. |
| `test_manifest.py` | 4,098 | `0469e0aeee058586c6ee63564b27a8a274d6e38f9008fc29896018c864e8ad0d` | Test module: The provenance of a result, and the check that it is the real one. |
| `test_metadati.py` | 24,373 | `5775b6cac0252b4a1d8bbdf876f7e5a40d6b01a67f0013fb4804017bc2e9e1c7` | Test module: Metadata are not invented, and are not needed to analyse a corpus. |
| `test_model_eval.py` | 11,995 | `ab17f2612c7a915ba6102d7760cac142c2843fbab16531e507f86b9ea66f3265` | Test module: The comparison with a model: what it receives, on what it is measured. |
| `test_modelli_non_bloccano.py` | 11,696 | `6122eaa6683a22a7e0e733a6c2e1c6e4ef6cee74ac0ec4bc4af75cc732fdf06c` | Test module: The long work stays outside the interface thread, and it shows. |
| `test_modelli_primo_giro.py` | 13,640 | `612c7338542c081ed846b3693a6f90fadb59fde85be8817bcdf5f0ab5706d5ca` | Test module: The first comparison on a new run, when nothing is saved yet. |
| `test_modelli_provenienza_gui.py` | 4,963 | `d3b3ee130a98b97d1ecf9ba488d6fdd4051e74fa27d120b7a3a728a2f5ce8cc0` | Test module: A saved comparison does not belong to whoever finds it, but to whoever produced it. |
| `test_navigazione.py` | 7,471 | `545c0221f13002531f2988771d16962f9073dc86dd11d2c869915282edc50b78` | Test module: The names of the sidebar, frozen. |
| `test_normalise.py` | 9,288 | `7ef0f80827f25c2e4e483247a64d82d648d52b68673862e95b47fa943e182d14` | Test module: The five normalisations: each does its own job and no other. |
| `test_pipeline_base.py` | 45,658 | `e9ff603699b6cc470138e1135839bfb5a141ac02894b7c36534661e9c8c0463c` | Test module: The basic functions: reading, diagnosis, correction, exports. |
| `test_profilo_parola_gui.py` | 3,049 | `7a5f6c597b530756f37c569a367cadda654900872512748059c2ea54f9f19a04` | Test module: The “Lemma profile” card, really pressed. |
| `test_recompute_units.py` | 6,197 | `c03965c1aec32e2b9185b97d7eaa86848626cb9199d3afaf3bd36093b1f59d30` | Test module: The script that recomputes the counting units and the figures of S11.1 (``reproducibility/scripts/recompute_units.py``). |
| `test_rerun_diagnosis.py` | 3,828 | `0af90b554cdfd390df832c9d8f81933e35abc6496bad9398c48265c37fc199e5` | Test module: The script that repeats the diagnosis of a stratum (``reproducibility/scripts/rerun_diagnosis.py``). |
| `test_resources.py` | 8,964 | `43bc96b8a777efb8f6b3dde44fb904dac5107770caf9195154224e950a13b07b` | Test module: The scientific lists as versioned data resources. |
| `test_ricerca.py` | 17,591 | `5e67c0d391b9ec20d503d6de5170987d68bbdc231ebef07d11c8ab341f9078f7` | Test module: Searching the corpus: type the word, find it, read what it is. |
| `test_ricostruzione_widget.py` | 3,707 | `e1419226aea64b86bb779500813fea601940171005b12108b5ffab2446e7d227` | Test module: A rebuilt widget must not leave the previous version lying around. |
| `test_selettore_lingua.py` | 4,475 | `72870b81bfab59e86401eca060788cb55377b6aa1b641b855042c75064189476` | Test module: The language menu must show the language that the interface is written in, from the moment the window opens. |
| `test_setup_windows.py` | 12,069 | `7171f30f1c1838dd11ad155feb880cc274b2a182cd8f45fd60827f375316ae4a` | Test module: The Windows setup in front of an incomplete virtual environment. |
| `test_spiegazioni_variazione.py` | 9,286 | `b5af267a139bc53ce31c6d0815188726200f7c0df295cf0df83a34c8c47fb232` | Test module: The explanations of the nuclei tables: one per column, in two languages. |
| `test_spirito_e_segni.py` | 15,405 | `c98a87b2ba57e28d7d3eff5a0adc477e7fd54ebd68204a02d243078835aa4dc6` | Test module: The breathing that is an apostrophe, and the sign that is not a word. |
| `test_statistiche.py` | 13,853 | `996fe7e2a1923a9aac7b0be0daf5685064a1549fbb2b4ca3b9a18dc0d1b0d893` | Test module: The Statistics page: what it shows, and what is not invented. |
| `test_udpipe_processo_separato.py` | 15,862 | `c56b85c2becbafc4a99c54e572fafaf1926ca9c703c325a697e00f8508ba6211` | Test module: UDPipe in a process of its own: it starts, it ends, and it leaves nothing. |
| `test_ui_contro_backend.py` | 6,607 | `ecb112741151b7ec2da43869007e470c0e3d8ecb78bb20672a32226dbea66775` | Test module: The interface says what the backend says, and not a number of its own. |
| `test_units.py` | 15,635 | `3e890e9d3e70ef504a8d3b1585a12ae62f0d8d9f228a1566cfa6d4e5174ab32e` | Test module: The five units, the sentence key and the structure of the measure. |
| `test_variazione_contesto.py` | 6,981 | `26336d955ef43fbfd8f6b91036b186a0bfe2345e5b4f52c8f03adb8d53780b4c` | Test module: The trigram plane, aligned with the other four. |
| `test_variazione_pagina.py` | 4,729 | `ba531854068dc97c71ba113347cdf5564a4134a6df4fabf16b2b39577b67a915` | Test module: The count of the nuclei comes from the backend, never from the cap on the rows shown. |
| `test_verify_sha256sums.py` | 5,129 | `0feadc14d626f1bdf35df0f40eab531ba4392cc6c7fbb3c356dcd1426dba3da7` | Test module: The script that checks the files of the package against ``SHA256SUMS`` (``reproducibility/scripts/verify_sha256sums.py``). |
| `test_word_sketch.py` | 12,418 | `4c8a9095617d098e80b8984a02958ff27eb6b64758ca293bc155da4aecf99c85` | Test module: The syntactic profile of a word, and the units from which its numbers come. |
