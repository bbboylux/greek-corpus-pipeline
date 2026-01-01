"""Greek Corpus Pipeline — diagnosis and analysis of Ancient Greek treebanks.

The package is divided by level of analysis, not by processing stage:

``agdt_schema``      the AGDT scheme, declared as data
``xmlio``            reading and writing the XML files
``postag``           anomalies of the morphological tag
``lemma``            anomalies of lemmatisation
``syntax``           structure of the dependency tree
``orthography``      Unicode, diacritics, encoding
``agreement``        grammatical agreement and government
``variation``        inconsistencies between similar passages (variation n-grams)
``search``           search engine and concordances
``stats``            lexical, morphological and syntactic statistics
``modelcmp``         comparison between the corpus and the automatic models
``corpus_metadata``  author, work, date, dialect, genre
``figures``          charts and export of figures
``analysis``         application of corrections and comparison with the models
``gold``             the gold standard corrected by the user: saving,
                     export, comparison with the models
``storage``          persistence of the results
"""
# The number of threads of the numerical libraries is fixed here and nowhere else.
#
# OpenBLAS, OpenMP and MKL size their pool when they are imported, reading the
# environment, and never read it again. The line below —
# ``from .analysis import ...`` — pulls in pandas and numpy, so the limit
# has to be set before it. Setting it in ``app_qt.py`` was not enough: to call
# it, ``app_qt.py`` writes ``from greek_corpus_pipeline.cpu import
# limita_thread``, and that import runs this file first, that is, it imports
# numpy before the limit has been set. Here, instead, every route into the
# package — the application, CHECK_INSTALL.py, the tests, the UDPipe child
# process — finds the limit already applied.
from .cpu import limita_thread as _limita_thread

_limita_thread()

from .analysis import (
    apply_form_corrections,
    apply_manual_corrections,
    apply_suggested_corrections,
    build_confusion_matrix,
    compare_annotation_sets,
    compute_token_diff,
    run_pipeline,
    summarize_corpus,
)
from .github import download_github_tree, parse_github_tree_url
from .gold import (
    GoldState,
    export_gold_conllu,
    export_gold_csv,
    export_gold_xml,
    gold_state,
    load_gold_bundle,
    model_reference_table,
    read_gold_meta,
    read_manual_corrections,
    rescore_model,
    save_gold_bundle,
)
from .model_support import (
    default_stanza_model_dir,
    default_udpipe_model_path,
    ensure_stanza_resources,
    ensure_udpipe_model,
)
from .xmlio import (
    export_corrected_xml,
    export_sentence_csvs,
    load_corpus_from_directory,
    parse_treebank_xml,
)

__version__ = "3.1.0"

__all__ = [
    "__version__",
    "apply_form_corrections",
    "apply_manual_corrections",
    "apply_suggested_corrections",
    "build_confusion_matrix",
    "compare_annotation_sets",
    "compute_token_diff",
    "default_stanza_model_dir",
    "default_udpipe_model_path",
    "download_github_tree",
    "export_gold_conllu",
    "export_gold_csv",
    "export_gold_xml",
    "gold_state",
    "GoldState",
    "load_gold_bundle",
    "model_reference_table",
    "read_gold_meta",
    "read_manual_corrections",
    "rescore_model",
    "save_gold_bundle",
    "ensure_stanza_resources",
    "ensure_udpipe_model",
    "export_corrected_xml",
    "export_sentence_csvs",
    "load_corpus_from_directory",
    "parse_github_tree_url",
    "parse_treebank_xml",
    "run_pipeline",
    "summarize_corpus",
]
