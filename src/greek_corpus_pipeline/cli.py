"""Command line interface, for batch work and for reproducibility.

Everything the graphical program does can be done from here, which matters for
two reasons: a result reported in an article should be reproducible with one
command, and processing forty treebanks should not require forty sessions of
clicking.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _english(label: object) -> str:
    """The English reading of a column or key that the analysis names in Italian.

    The analysis names its tables in Italian and the interface translates the names at
    the moment they are drawn (``gui_qt.i18n.data_label``). The command line does the
    same, with the English entries, so that its output is in English whatever the
    interface language is set to.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from gui_qt import i18n                          # noqa: PLC0415

    entry = i18n._STRINGS.get("column." + str(label))
    return str(label) if entry is None else entry[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greek-corpus-cli",
        description="Diagnosis, correction and statistics for Ancient Greek AGDT treebanks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:

  # load a corpus and print its basic counts
  greek-corpus-cli --source ./xml --corpus-name gorman

  # load, check, correct and export the corrected XML
  greek-corpus-cli --source ./xml --corpus-name gorman --detect --correct --export-xml

  # download from GitHub and run everything, figures included
  greek-corpus-cli \\
      --source https://github.com/perseids-publications/gorman-trees/tree/master/public/xml \\
      --corpus-name gorman --detect --correct --stats --figures ./figures
""")
    parser.add_argument("--source", required=True,
                        help="folder with the XML files, or a GitHub address")
    parser.add_argument("--corpus-name", default="corpus",
                        help="name under which this load is saved")
    parser.add_argument("--workspace", default="workspace",
                        help="folder where the results are saved (default: ./workspace)")

    parser.add_argument("--detect", action="store_true",
                        help="runs the diagnostic checks")
    parser.add_argument("--variation", action="store_true",
                        help="includes the check for inconsistencies between similar passages (slow)")
    parser.add_argument("--correct", action="store_true",
                        help="applies the automatic corrections")
    parser.add_argument("--stats", action="store_true",
                        help="prints the statistical profile of the corpus")

    parser.add_argument("--export-csv", action="store_true",
                        help="exports one CSV per sentence")
    parser.add_argument("--export-xml", action="store_true",
                        help="exports the corrected AGDT XML")
    parser.add_argument("--export-conllu", action="store_true",
                        help="exports the corpus in CoNLL-U format (AGDT annotation "
                             "kept: relation in DEPREL, nine-character tag in "
                             "XPOS, expanded morphology in FEATS)")
    parser.add_argument("--figures", metavar="FOLDER",
                        help="generates all the figures at 300 dpi in the given folder")

    parser.add_argument("--keep-placeholders", action="store_true",
                        help="do not exclude the placeholders of elliptical nodes")
    parser.add_argument("--quiet", action="store_true", help="less output")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    from . import corpus_metadata, stats as statistics
    from .rule_catalog import auto_applicable_rule_ids
    from .storage import (
        artifact_exists, create_run_id, load_dataframe, save_metadata,
    )

    # The worker functions are shared with the graphical program, so that the
    # two cannot drift apart: one implementation, two front ends.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from gui_qt.workers import (                     # noqa: PLC0415
        apply_corrections, export_figures, prepare_corpus, run_detection,
    )

    workspace = Path(arguments.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    def progress(step: int, total: int, message: str) -> None:
        if not arguments.quiet:
            print(f"[{step}/{total}] {message}")

    def log(message: str) -> None:
        if not arguments.quiet:
            print(f"    {message}")

    source = arguments.source
    mode = "github" if source.startswith(("http://", "https://")) else "folder"

    run_id = create_run_id(arguments.corpus_name)
    save_metadata(workspace, run_id, {
        "run_id": run_id, "corpus_name": arguments.corpus_name,
        "source_mode": mode, "source_value": source, "stages": {},
    })
    print(f"Corpus: {arguments.corpus_name}\nRun identifier: {run_id}\n")

    filters = {"exclude_placeholders": not arguments.keep_placeholders,
               "exclude_non_greek": False, "exclude_punctuation": False}

    prepare_corpus(workspace, run_id, mode, source, arguments.corpus_name, progress, log)

    if arguments.detect:
        print()
        run_detection(workspace, run_id, {
            "morphology": True, "lemma": True, "syntax": True,
            "text": True, "agreement": True, "variation": arguments.variation,
        }, filters, progress, log)

    if arguments.correct:
        print()
        apply_corrections(
            workspace, run_id, set(auto_applicable_rule_ids()),
            pd.DataFrame(), pd.DataFrame(), filters,
            arguments.export_csv, arguments.export_xml, progress, log,
            export_conllu_flag=arguments.export_conllu)
    elif arguments.export_csv or arguments.export_xml:
        print("\n[warning] --export-csv and --export-xml also require --correct.")

    tokens = load_dataframe(workspace, run_id, "tokens")
    enriched = corpus_metadata.enrich_tokens(tokens)

    if arguments.stats:
        print("\n── Basic counts ───────────────────────────────────────")
        for label, value in statistics.basic_counts(enriched).items():
            print(f"  {_english(label):32s} {value}")
        print("\n── Morphological profile ──────────────────────────────")
        for label, value in statistics.morphological_profile(enriched).items():
            print(f"  {_english(label):38s} {value}")
        table = statistics.counts_by_group(enriched, "autore")
        if not table.empty:
            print("\n── By author ──────────────────────────────────────────")
            print(table.rename(columns=_english).head(25).to_string(index=False))

    if arguments.figures:
        print()
        export_figures(workspace, run_id, arguments.figures, progress, log)

    if arguments.detect and artifact_exists(workspace, run_id, "findings"):
        findings = load_dataframe(workspace, run_id, "findings")
        if not findings.empty:
            print("\n── Findings by check ──────────────────────────────────")
            # From the code of the rule, not from the column written during the
            # analysis: the catalogue is the source of the name, always.
            from .rule_catalog import rule_name
            counts = (findings["rule_id"].astype(str).map(lambda rid: rule_name(rid, "en"))
                      .value_counts().head(25))
            for name, count in counts.items():
                print(f"  {int(count):>9,}  {name}")

    print(f"\nResults saved in: {workspace / 'runs' / run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
