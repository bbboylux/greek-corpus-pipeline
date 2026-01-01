"""Background work.

Every operation that touches the corpus runs on a worker thread. That is not a
performance nicety: a Qt window that stops repainting for eight seconds looks
broken, and a user who thinks the program has crashed closes it.

Two shapes are used. :class:`PipelineWorker` runs a function that reports
progress and writes its results to disk — loading, analysing, correcting,
running a model. :class:`ResultWorker` runs a function that simply computes and
returns something — a search, a statistics table, a chart. The distinction
matters because the first kind must be serialised (only one at a time, since
they write to the same run directory) while the second can be cancelled and
restarted freely as the user types.
"""
from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path
from typing import Callable

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from greek_corpus_pipeline.units import build_units, is_technical_record

from .i18n import counted, decimal, number, tr

# In a source tree the error log sits at the root of the project, next to ``app_qt.py`` (``.gitignore``
# names it). An installed copy (``pip install .``) must not write into ``site-packages``, so there the
# log goes to the folder the program is run from; if that cannot be written either, errors go to stderr.
_root = Path(__file__).resolve().parent.parent
_log_path = (_root if (_root / "pyproject.toml").is_file() else Path.cwd()) / "pipeline_errors.log"
try:
    logging.basicConfig(
        filename=str(_log_path),
        level=logging.ERROR,
        format="%(asctime)s  %(levelname)s  %(message)s",
        encoding="utf-8",
    )
except OSError:
    logging.basicConfig(level=logging.ERROR, format="%(asctime)s  %(levelname)s  %(message)s")


class PipelineWorker(QThread):
    """Runs a pipeline function that reports progress and saves its output."""

    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, function: Callable, *args, **kwargs) -> None:
        super().__init__()
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            extra = dict(self._kwargs)
            # Interruption is offered only to those who know how to use it.  Adding it
            # to all the long functions would break them all; looking at the signature
            # is explicit and breaks nothing.
            try:
                import inspect
                if "annullato" in inspect.signature(self._function).parameters:
                    extra.setdefault("annullato", self.isInterruptionRequested)
            except (TypeError, ValueError):
                pass
            self._function(*self._args, self.progress.emit, self.log.emit, **extra)
            self.finished_ok.emit()
        except BaseException as exception:            # noqa: BLE001 — reported, not swallowed
            message = f"{type(exception).__name__}: {exception}\n{traceback.format_exc()}"
            logging.error(message)
            self.error.emit(message)


class ResultWorker(QThread):
    """Runs a pure function and hands back whatever it returns."""

    done = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, function: Callable, *args, **kwargs) -> None:
        super().__init__()
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            self.done.emit(self._function(*self._args, **self._kwargs))
        except BaseException as exception:            # noqa: BLE001
            message = f"{type(exception).__name__}: {exception}\n{traceback.format_exc()}"
            logging.error(message)
            self.error.emit(message)


# ---------------------------------------------------------------------------
# Token filtering
# ---------------------------------------------------------------------------

import re as _re

_GREEK_RE = _re.compile(r"[Ͱ-Ͽἀ-῿]")


def _elliptic_mask(tokens: pd.DataFrame) -> pd.Series:
    """The technical records: elliptic nodes, lacunae, placeholders, unannotated.

    The recognition lives in
    :func:`greek_corpus_pipeline.units.is_technical_record` and nowhere else: the
    statistics, the script of the article and the three analysis pages all need it,
    and separate copies would diverge. A copy that counted among the elliptic nodes
    only those declared in the ``artificial`` attribute, while the filter recognises
    five kinds, would give two different numbers on four corpora out of six.

    The name is kept so as not to break the callers; the definition is a single one.
    """
    return is_technical_record(tokens)


def _non_greek_mask(tokens: pd.DataFrame) -> pd.Series:
    """Records whose form carries no letter of the Greek alphabet."""
    if tokens.empty or "form" not in tokens.columns:
        return pd.Series(False, index=tokens.index)
    has_greek = tokens["form"].map(
        lambda value: isinstance(value, str) and bool(_GREEK_RE.search(value)))
    return ~has_greek.fillna(False).astype(bool)


def _punctuation_mask(tokens: pd.DataFrame) -> pd.Series:
    """Records the treebank tags as punctuation — the ``u`` slot value."""
    if tokens.empty or "postag" not in tokens.columns:
        return pd.Series(False, index=tokens.index)
    is_punctuation = tokens["postag"].map(
        lambda value: isinstance(value, str) and value.startswith("u"))
    return is_punctuation.fillna(False).astype(bool)


#: The three inclusion choices of the load page, each with the option that
#: switches it and the test that recognises its records. One list, read both by
#: the filter and by the count the overview shows, so that the two can never
#: come to disagree — which is the whole point of showing the count.
EXCLUSION_KINDS: tuple[tuple[str, str, Callable[[pd.DataFrame], pd.Series]], ...] = (
    ("elliptic", "exclude_placeholders", _elliptic_mask),
    ("punctuation", "exclude_punctuation", _punctuation_mask),
    ("non_greek", "exclude_non_greek", _non_greek_mask),
)


def filter_tokens(tokens: pd.DataFrame, options: dict) -> tuple[pd.DataFrame, int]:
    """Apply the user's inclusion choices. Returns (kept, number removed)."""
    if tokens.empty:
        return tokens, 0
    keep = pd.Series(True, index=tokens.index)
    for _name, option, recognise in EXCLUSION_KINDS:
        if options.get(option):
            keep &= ~recognise(tokens)
    removed = int((~keep).sum())
    return tokens[keep].reset_index(drop=True), removed


def excluded_counts(tokens: pd.DataFrame, options: dict | None = None) -> dict:
    """How many records each of the three inclusion choices concerns.

    The overview shows these three numbers whether or not the corresponding
    filter is on: switched off, the number says how many such records there are
    and stay in; switched on, it says how many are being left out. A silent
    zero would say neither.

    The categories overlap — an empty elliptic node has no Greek letter in it,
    and neither has a comma — so each is counted in full, on its own, and the
    three do not add up. ``removed`` is the one number that does: the union of
    the categories actually switched on, computed the way
    :func:`filter_tokens` computes it.
    """
    options = options or {}
    counts: dict[str, object] = {"total": int(0 if tokens is None else len(tokens))}
    if tokens is None or tokens.empty:
        for name, option, _recognise in EXCLUSION_KINDS:
            counts[name] = 0
            counts[f"{name}_active"] = bool(options.get(option))
        counts["removed"] = 0
        return counts

    keep = pd.Series(True, index=tokens.index)
    for name, option, recognise in EXCLUSION_KINDS:
        mask = recognise(tokens)
        counts[name] = int(mask.sum())
        counts[f"{name}_active"] = bool(options.get(option))
        if options.get(option):
            keep &= ~mask
    counts["removed"] = int((~keep).sum())
    return counts


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def prepare_corpus(
    workspace: Path,
    run_id: str,
    source_mode: str,
    source_value: str,
    corpus_name: str,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
) -> None:
    """Read a folder (or download a repository) and build the token table."""
    from greek_corpus_pipeline.analysis import summarize_corpus
    from greek_corpus_pipeline.github import download_github_tree
    from greek_corpus_pipeline.storage import save_dataframe, save_stats, update_stage_status
    from greek_corpus_pipeline.xmlio import load_corpus_from_directory

    total = 4
    update_stage_status(workspace, run_id, "prepare", "running")

    progress_cb(1, total, tr("work.source"))
    if source_mode == "glaux-sample":
        # The whole of GLAUx is three gigabytes and twenty million records: downloading
        # it all to inspect it serves nobody. Only the files of the declared sample are
        # downloaded, forty of them, listed in data/glaux_sample.csv. ``source_value``
        # is "sample/stratum".
        from greek_corpus_pipeline import glaux_sample
        campione, _, strato = source_value.partition("/")
        campione = campione or "principale"
        strato = strato or "automatico"
        testi = glaux_sample.select(campione, strato)
        log_cb(tr("work.glaux_sample", campione, strato, len(testi),
                  number(sum(t.token_dichiarati for t in testi))))
        source_root = glaux_sample.download(
            workspace / "downloads", campione, strato,
            progress=lambda i, n, nome: progress_cb(
                1, total, tr("work.downloading_one", nome, i, n)))
    elif source_mode == "github":
        log_cb(tr("work.downloading", source_value))
        source_root = download_github_tree(source_value, workspace / "downloads")
    else:
        source_root = Path(source_value).resolve()

    progress_cb(2, total, tr("work.reading_xml", source_root))
    started = time.perf_counter()
    tokens = load_corpus_from_directory(source_root, corpus_name=corpus_name)
    elapsed = time.perf_counter() - started

    if tokens.empty:
        raise ValueError(tr("work.no_xml"))

    documents = tokens["document_id"].nunique()
    sentences = tokens[["document_id", "sentence_index"]].drop_duplicates().shape[0]
    progress_cb(3, total, tr(
        "work.read_done", number(len(tokens)), documents,
        number(sentences), f"{elapsed:.1f}"))

    save_dataframe(workspace, run_id, "tokens", tokens)
    save_stats(workspace, run_id, "stats_before", summarize_corpus(tokens))
    update_stage_status(workspace, run_id, "prepare", "complete", {
        "details": f"{len(tokens)} tokens", "source_root": str(source_root),
        "documents": int(documents), "sentences": int(sentences),
        "tokens": int(len(tokens)),
    })
    progress_cb(4, total, "Corpus loaded.")


def run_detection(
    workspace: Path,
    run_id: str,
    families: dict[str, bool],
    filter_options: dict,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
) -> None:
    """Run every selected family of checks and save the findings."""
    from greek_corpus_pipeline import agreement, orthography, syntax, variation
    from greek_corpus_pipeline.lemma import analyze_lemmas
    from greek_corpus_pipeline.postag import analyze_postags
    from greek_corpus_pipeline.storage import (
        load_dataframe, save_dataframe, update_stage_status,
    )

    steps = 2 + sum(1 for value in families.values() if value)
    step = 0
    update_stage_status(workspace, run_id, "detection", "running")

    # How many checks of the catalogue each family covers.  It serves to tell whoever
    # waits how far the count has got — “51 checks run out of 77” — instead of an
    # ellipsis that does not say how much is left.
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG, rule_family
    _per_famiglia: dict[str, int] = {}
    for regola in RULE_CATALOG:
        _per_famiglia[rule_family(regola)] = _per_famiglia.get(rule_family(regola), 0) + 1
    _catalogo = len(RULE_CATALOG)
    #: The names with which the interface calls the families and those of the catalogue.
    _NOMI = {"morphology": "morfologia", "lemma": "lemma", "syntax": "sintassi",
             "text": "testo", "agreement": "accordo"}
    _fatti = 0

    def _avanzamento(chiave: str, testo: str) -> str:
        """The status text, with the count of the checks already run."""
        nonlocal _fatti
        _fatti += _per_famiglia.get(_NOMI.get(chiave, ""), 0)
        return (f"{testo} — "
                f"{tr('work.checks_done', number(_fatti), number(_catalogo))}")

    step += 1
    progress_cb(step, steps, tr("work.loading_tokens_table"))
    complete = load_dataframe(workspace, run_id, "tokens")
    tokens, removed = filter_tokens(complete, filter_options)
    if removed:
        log_cb(tr("work.filtered_out", number(removed)))

    # Structural checks run on the *complete* table, filters or no filters.
    #
    # This is not an optimisation, it is a correctness requirement. An elliptic
    # placeholder is frequently the syntactic head of real words: in the opening
    # of Epicurus' letter the whole greeting hangs from a `[0]` standing in for
    # the elided verb. Remove the placeholder first and every one of its
    # dependents becomes a "dangling head" and its sentence a "sentence with no
    # root" — hundreds of findings manufactured by the filter itself.
    #
    # It is also the treatment the literature prescribes. Dickinson & Meurers
    # exclude null elements from being variation nuclei (2003b: 53–54); Boyd,
    # Dickinson & Meurers add the other half — the unannotated nodes are
    # ignored "in the determination of the variation nuclei" but "still play a
    # role as context words" (2008, authors' preprint: 21). Findings that land
    # on a filtered-out token are dropped afterwards, so the filter still does
    # what the user asked.
    excluded_keys: set[tuple[str, str, str]] = set()
    if removed:
        key_columns = ["document_id", "sentence_id", "token_id"]
        if all(column in complete.columns for column in key_columns):
            kept = set(map(tuple, tokens[key_columns].astype(str).to_numpy()))
            everything = set(map(tuple, complete[key_columns].astype(str).to_numpy()))
            excluded_keys = everything - kept

    def _drop_excluded(findings: pd.DataFrame) -> pd.DataFrame:
        if findings.empty or not excluded_keys:
            return findings
        key_columns = ["document_id", "sentence_id", "token_id"]
        if not all(column in findings.columns for column in key_columns):
            return findings
        keys = map(tuple, findings[key_columns].astype(str).to_numpy())
        return findings[[key not in excluded_keys for key in keys]]

    collected: list[pd.DataFrame] = []
    arcs = pd.DataFrame()

    # The five canonical units, computed once and passed to whoever asks for them. Each
    # analysis takes the unit that concerns it instead of rebuilding the universe with
    # its own filter lines.
    unita = build_units(complete, filters=filter_options, active=tokens)

    if families.get("morphology"):
        step += 1
        progress_cb(step, steps, _avanzamento("morphology", tr("work.check_morphology")))
        findings = analyze_postags(tokens)
        log_cb(tr("work.found_morphology", number(len(findings))))
        collected.append(findings)

    if families.get("lemma"):
        step += 1
        progress_cb(step, steps, _avanzamento("lemma", tr("work.check_lemma")))
        findings = analyze_lemmas(tokens)
        log_cb(tr("work.found_lemma", number(len(findings))))
        collected.append(findings)

    if families.get("syntax"):
        step += 1
        progress_cb(step, steps, _avanzamento("syntax", tr("work.check_syntax")))
        findings, arcs = syntax.analyze_syntax(complete)
        findings = _drop_excluded(findings)
        log_cb(tr("work.found_syntax", number(len(findings))))
        collected.append(findings)
        if not arcs.empty:
            save_dataframe(workspace, run_id, "arcs", arcs)

    if families.get("text"):
        step += 1
        progress_cb(step, steps, _avanzamento("text", tr("work.check_text")))
        findings = orthography.analyze_orthography(tokens)
        log_cb(tr("work.found_text", number(len(findings))))
        collected.append(findings)
        spellings = orthography.orthographic_variation(tokens)
        if not spellings.empty:
            save_dataframe(workspace, run_id, "spelling_variation", spellings)

    if families.get("agreement"):
        step += 1
        progress_cb(step, steps, _avanzamento("agreement", tr("work.check_agreement")))
        # The two questions of this family have different universes, and must have them.
        # Agreement is measured on the imported records. Relation rarity is measured on
        # the “words”: with punctuation inside, the most numerous rare combination of
        # Gorman would be “punc1 / u / AuxG”, 602 occurrences, which is a punctuation
        # mark and not a fact of the language.
        findings = _drop_excluded(
            agreement.analyze_agreement(complete, words=unita.words))
        log_cb(tr("work.found_agreement", number(len(findings))))
        collected.append(findings)

    if families.get("variation"):
        step += 1
        progress_cb(step, steps, tr("work.check_variation"))
        # The NIL cores are not part of the official results, and there is no parameter
        # to switch them on: see variation.dependency_variation_with_nil.
        suite = variation.run_variation_suite(tokens)
        piani = len(suite)
        for indice, (name, table) in enumerate(suite.items(), start=1):
            progress_cb(step, steps,
                        f"{tr('work.check_variation')} — "
                        f"{tr('work.planes_done', number(indice), number(piani))}")
            if not table.empty:
                save_dataframe(workspace, run_id, f"variation_{name}", table)
                log_cb(tr("work.found_variation", name,
                          number(len(table))))

    step += 1
    progress_cb(step, steps, tr("work.gathering"))

    live = [frame for frame in collected if frame is not None and not frame.empty]
    if live:
        columns: list[str] = []
        for frame in live:
            for column in frame.columns:
                if column not in columns:
                    columns.append(column)
        aligned = [frame.reindex(columns=columns) for frame in live]
        all_findings = pd.concat(aligned, ignore_index=True)
    else:
        all_findings = pd.DataFrame(columns=["rule_id", "anomaly_name", "issue"])

    # Severity comes from the class of the check, always, and overrides whatever the
    # module that emitted the finding had written. If every module wrote it by hand,
    # with “errore” (error) as the fallback, whoever looked at the list would read “3 —
    # Case to verify” beside “error”. Two columns that contradict each other take
    # credibility away from all the others.
    from greek_corpus_pipeline.rule_catalog import rule_severity
    all_findings["severity"] = all_findings["rule_id"].map(rule_severity)

    # Who proposes and who stays silent is decided by the treatment declared in the
    # catalogue, at a single point and at the end: a manual check leaves no proposals,
    # and the occurrences already checked by hand recover theirs.
    from greek_corpus_pipeline.proposte import allinea_proposte
    nome_corpus = ""
    try:
        nome_corpus = str(complete["corpus"].iloc[0]) if "corpus" in complete.columns and len(complete) else ""
    except Exception:
        nome_corpus = ""
    all_findings = allinea_proposte(all_findings, complete, nome_corpus)

    save_dataframe(workspace, run_id, "findings", all_findings)
    update_stage_status(workspace, run_id, "detection", "complete", {
        "details": f"{len(all_findings)} findings",
        "findings": int(len(all_findings)),
        "families": [name for name, value in families.items() if value],
    })
    progress_cb(steps, steps,
                tr("work.detection_done", counted("segnalazione", len(all_findings))))


def apply_corrections(
    workspace: Path,
    run_id: str,
    enabled_rules: set[str],
    manual_corrections: pd.DataFrame,
    form_corrections: pd.DataFrame,
    filter_options: dict,
    export_csv: bool,
    export_xml: bool,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
    export_conllu_flag: bool = False,
) -> None:
    """Apply automatic, form-level and manual corrections, in that order."""
    from greek_corpus_pipeline.analysis import (
        apply_form_corrections, apply_manual_corrections,
        apply_suggested_corrections, compute_token_diff,
        normalise_corpus_to_nfc, summarize_corpus,
    )
    from greek_corpus_pipeline.proposte import AZIONI_SUL_CORPUS
    from greek_corpus_pipeline.lemma import build_lemma_inventory
    from greek_corpus_pipeline.storage import (
        artifact_exists, load_dataframe, report_dir, save_dataframe, save_stats,
        update_stage_status,
    )

    total = 5 + int(export_csv) + int(export_xml)
    update_stage_status(workspace, run_id, "corrections", "running")

    progress_cb(1, total, tr("work.loading_findings"))
    tokens = load_dataframe(workspace, run_id, "tokens")
    tokens, removed = filter_tokens(tokens, filter_options)
    if removed:
        log_cb(tr("work.filtered", number(removed)))

    findings = (load_dataframe(workspace, run_id, "findings")
                if artifact_exists(workspace, run_id, "findings") else pd.DataFrame())
    if findings.empty:
        raise RuntimeError(tr("work.no_findings_saved"))

    postag_findings = findings[findings.get("suggested_postag").notna()] \
        if "suggested_postag" in findings.columns else pd.DataFrame()
    lemma_findings = findings[findings.get("suggested_lemma").notna()] \
        if "suggested_lemma" in findings.columns else pd.DataFrame()
    form_findings = findings[findings.get("suggested_form").notna()] \
        if "suggested_form" in findings.columns else pd.DataFrame()
    for frame in (postag_findings, lemma_findings, form_findings):
        if not frame.empty and "auto_correctable" not in frame.columns:
            frame["auto_correctable"] = True

    progress_cb(2, total, tr("work.applying_auto"))
    corrected = apply_suggested_corrections(
        tokens,
        postag_findings if not postag_findings.empty else _empty_postag_findings(),
        lemma_findings if not lemma_findings.empty else _empty_lemma_findings(),
        enabled_rule_ids=enabled_rules,
        form_findings=form_findings,
    )
    log_cb(tr("work.active_rules", len(enabled_rules)))

    # The actions that apply to the whole corpus and not to a token: the conversion to
    # NFC of a resource published in decomposed form. The check declares it, and without
    # this step nobody would perform it.
    presenti = set(findings["rule_id"]) if "rule_id" in findings.columns else set()
    for regola in sorted(AZIONI_SUL_CORPUS & presenti & set(enabled_rules)):
        if regola == "corpus-not-nfc":
            corrected, quanti = normalise_corpus_to_nfc(corrected)
            if quanti:
                log_cb(tr("work.nfc_applied",
                          number(quanti)))

    progress_cb(3, total, tr("work.applying_dictionary"))
    if form_corrections is not None and not form_corrections.empty:
        corrected = apply_form_corrections(corrected, form_corrections)
        log_cb(tr("work.dictionary_entries",
                  number(len(form_corrections))))

    if manual_corrections is not None and not manual_corrections.empty:
        corrected = apply_manual_corrections(corrected, manual_corrections)
        log_cb(tr("work.manual_applied",
                  number(len(manual_corrections))))

    progress_cb(4, total, tr("work.computing_diff"))
    save_dataframe(workspace, run_id, "corrected_tokens", corrected)
    difference = compute_token_diff(tokens, corrected)
    save_dataframe(workspace, run_id, "token_diff", difference)
    save_stats(workspace, run_id, "stats_after", summarize_corpus(corrected))
    log_cb(tr("work.changed_tokens", number(len(difference))))

    progress_cb(5, total, tr("work.lemma_inventory"))
    save_dataframe(workspace, run_id, "lemma_inventory", build_lemma_inventory(corrected))

    step = 5
    if export_csv:
        step += 1
        progress_cb(step, total, tr("work.export_sentence_csv"))
        from greek_corpus_pipeline.xmlio import export_sentence_csvs
        target = report_dir(workspace, run_id) / "sentence_csvs"
        export_sentence_csvs(corrected, target)
        log_cb(tr("work.csv_written", target))
    if export_xml:
        step += 1
        progress_cb(step, total, tr("work.export_xml"))
        from greek_corpus_pipeline.xmlio import export_corrected_xml
        target = report_dir(workspace, run_id) / "corrected_xml"
        written = export_corrected_xml(corrected, target)
        log_cb(tr("work.xml_written", len(written), target))

    if export_conllu_flag:
        step += 1
        progress_cb(step, total, tr("work.export_conllu"))
        from greek_corpus_pipeline.conllu import export_conllu

        # CoNLL-U carries the tree, so it must be written from the *complete*
        # table. Exporting the filtered one silently orphans every dependent of
        # an elliptic placeholder: in Plato's Crito, three tokens that depend on
        # a "[0]" node came out attached to the root with UnresolvedHead=Yes.
        # The filters exist to keep placeholders out of the *diagnostics*, not
        # out of the corpus.
        export_source = corrected
        if removed:
            complete_tokens = load_dataframe(workspace, run_id, "tokens")
            key = [column for column in
                   ("source_file", "document_id", "sentence_index", "token_id")
                   if column in complete_tokens.columns and column in corrected.columns]
            # A duplicated token id inside one sentence is itself something the
            # program reports, so the join key is not guaranteed unique and an
            # index-based merge raises. Position within the sentence is unique
            # by construction, so the corrections are carried over by a plain
            # left merge on it.
            # Duplicated token ids exist (the program reports eight of them in
            # Pedalion) and must not cost the whole export: the few ambiguous
            # rows keep their first occurrence, everything else merges cleanly.
            if key:
                corrected = corrected.drop_duplicates(subset=key, keep="first")
                complete_tokens = complete_tokens.drop_duplicates(
                    subset=key, keep="first")
                changed_columns = [column for column in
                                   ("form", "lemma", "postag", "relation", "head")
                                   if column in corrected.columns]
                merged = complete_tokens.merge(
                    corrected[key + changed_columns], on=key, how="left",
                    suffixes=("", "_corrected"))
                for column in changed_columns:
                    patched = column + "_corrected"
                    if patched in merged.columns:
                        merged[column] = merged[patched].combine_first(merged[column])
                        merged = merged.drop(columns=patched)
                export_source = merged
            else:
                log_cb(tr("work.conllu_fallback"))

        target = report_dir(workspace, run_id) / "conllu"
        files = export_conllu(export_source, target, corpus_name=run_id, per_file=True)
        log_cb(tr("work.conllu_written", len(files), target,
                  number(len(export_source))))

    update_stage_status(workspace, run_id, "corrections", "complete", {
        "details": f"{len(difference)} tokens changed",
        "changed": int(len(difference)),
    })
    progress_cb(total, total, "Corrections applied.")


def _empty_postag_findings() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "rule_id", "document_id", "sentence_id", "token_id",
        "suggested_postag", "auto_correctable"])


def _empty_lemma_findings() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "rule_id", "document_id", "sentence_id", "token_id",
        "suggested_lemma", "auto_correctable"])


class InterruzioneRichiesta(RuntimeError):
    """The work was stopped by whoever asked for it, and it is not a fault."""


def _solo_la_definizione_e_cambiata(salvata: dict, adesso: dict) -> bool:
    """Everything matches except the version number of the definition.

    It serves to tell “this result comes from another corpus, another model or other
    filters” — and then the model must be run again — from “this result comes from the
    same predictions, counted with another rule”, which is fixed by recounting.
    """
    from greek_corpus_pipeline.model_eval import CACHE_FIELDS

    vecchia = (salvata or {}).get("provenienza") if "provenienza" in (salvata or {}) else salvata
    if not isinstance(vecchia, dict) or not vecchia:
        return False
    if vecchia.get("definizione_valutazione") == adesso.get("definizione_valutazione"):
        return False
    return all(vecchia.get(campo) == adesso.get(campo)
               for campo in CACHE_FIELDS
               if campo != "definizione_valutazione")


def _previsioni_salvate(tabella) -> "pd.DataFrame | None":
    """The predictions of the model, taken back from the saved comparison table.

    The saved table is the result of the alignment: it carries the alignment columns
    and the two columns of the model with the suffix ``_modello`` (“_model”).  Here
    we go back to the form that ``evaluate_predictions`` expects.
    """
    from greek_corpus_pipeline.model_eval import ALIGNMENT_COLUMNS

    if tabella is None or tabella.empty:
        return None
    servono = list(ALIGNMENT_COLUMNS) + ["lemma_modello", "postag_modello"]
    if any(colonna not in tabella.columns for colonna in servono):
        return None
    return tabella[servono].rename(columns={"lemma_modello": "lemma",
                                            "postag_modello": "postag"})


def _salva_confronto(workspace, run_id, etichetta, provenienza, esito,
                     log_cb, progress_cb) -> None:
    """Writes the comparison and its evaluation, and says so.  A single place."""
    from greek_corpus_pipeline.storage import (
        save_dataframe, save_stats, update_stage_status,
    )

    save_dataframe(workspace, run_id, f"{etichetta}_comparison", esito.tabella)
    save_stats(workspace, run_id, f"{etichetta}_evaluation",
               {"provenienza": provenienza, **esito.as_dict()})
    update_stage_status(workspace, run_id, etichetta, "complete",
                        {"details": f"{esito.parole} words evaluated",
                         "lemma": esito.lemma.as_dict(),
                         "postag": esito.postag.as_dict()})

    log_cb(tr("work.model_done", etichetta,
              decimal(f"{esito.lemma.quota:.1f}"),
              decimal(f"{esito.lemma.copertura:.1f}")))
    if esito.postag.sospesa:
        log_cb(tr("work.model_postag_suspended", etichetta, esito.postag.sospesa))
    else:
        log_cb(tr("work.model_postag", etichetta,
                  decimal(f"{esito.postag.quota:.1f}")))
    progress_cb(500, 500, tr("work.model_finished", etichetta))


def _confronto_con_modello(
    workspace: Path,
    run_id: str,
    filters: dict,
    *,
    etichetta: str,
    prepara,
    esegui,
    identita,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
    annullato=None,
) -> None:
    """The comparison with a model, on the corpus loaded now.

    A single path for Stanza and for UDPipe, because the scientific part is the same
    and writing it twice is how two numbers for the same thing come to diverge.
    What changes between the two lies in the three arguments ``prepara`` (prepare),
    ``esegui`` (run) and ``identita`` (identity).

    The saved result carries its own provenance with it, and is reused **only** if
    corpus, filters, version of the program, model, version of the model, its
    resources and definition of the evaluation all match.  A comparison produced by
    an earlier run is not an old result to be updated: it is the result of another
    question.
    """
    from greek_corpus_pipeline import __version__, model_eval
    from greek_corpus_pipeline.units import build_units
    from greek_corpus_pipeline.storage import (
        artifact_exists, load_dataframe, load_stats_if_present, save_dataframe,
        save_stats, update_stage_status,
    )

    # The bar goes from 0 to 500 instead of from 0 to 5, so that the model phase — which
    # is the only long one — can really move instead of standing still at 60% for its
    # whole duration.
    def _fermarsi() -> bool:
        return bool(annullato and annullato())

    progress_cb(100, 500, tr("work.model_prepare", etichetta))
    if _fermarsi():
        raise InterruzioneRichiesta(tr("work.model_cancelled", etichetta))
    risorse = prepara()

    progress_cb(200, 500, tr("work.model_tokens"))
    completo = load_dataframe(workspace, run_id, "tokens")
    attivi, _ = filter_tokens(completo, filters)
    superficie = model_eval.prepare_model_input(attivi)
    unita = build_units(completo, filters=filters, active=attivi)
    universo = model_eval.evaluation_universe(unita.words, superficie)

    versione_modello, impronta_risorse = identita(risorse)
    provenienza = model_eval.provenance(
        surface=superficie, gcp_version=__version__, filtri=filters,
        modello=etichetta, modello_versione=versione_modello,
        risorse_modello=impronta_risorse, run_id=run_id)

    # Asking “is there already a saved comparison?” must not be able to fail because
    # the answer is no.  A call written as ``load_stats(...) or {}`` would presume that
    # a missing file returns empty while it raises: the first comparison on a new run
    # would die on ``stanza_evaluation.json`` three steps before starting the model.
    salvata = load_stats_if_present(
        workspace, run_id, f"{etichetta}_evaluation").get("provenienza")
    riusabile, motivo = model_eval.provenance_matches(salvata, provenienza)
    if riusabile and artifact_exists(workspace, run_id, f"{etichetta}_comparison"):
        log_cb(tr("work.model_cached", etichetta))
        progress_cb(500, 500, tr("work.model_cached", etichetta))
        return

    # A case apart, and worth hours of computation: everything matches except the
    # definition of the evaluation.  The saved predictions are still the right ones —
    # this model produced them on this corpus — and what changes is only the way of
    # counting them.  Running the model again to redo a sum would be a waste: the
    # table is reread and the predictions are recounted.
    if (salvata and _solo_la_definizione_e_cambiata(salvata, provenienza)
            and artifact_exists(workspace, run_id, f"{etichetta}_comparison")):
        log_cb(tr("work.model_recount", etichetta))
        progress_cb(400, 500, tr("work.model_recount", etichetta))
        vecchia = load_dataframe(workspace, run_id, f"{etichetta}_comparison")
        previsioni = _previsioni_salvate(vecchia)
        if previsioni is not None:
            esito = model_eval.evaluate_predictions(universo, previsioni,
                                                    modello=etichetta)
            _salva_confronto(workspace, run_id, etichetta, provenienza, esito,
                             log_cb, progress_cb)
            return
        log_cb(tr("work.model_stale", etichetta, motivo))

    if salvata:
        log_cb(tr("work.model_stale", etichetta, motivo))

    totale = number(len(superficie))
    progress_cb(300, 500, tr("work.model_running", etichetta.capitalize(), totale))

    # The model works in batches, and with small batches the batches are many: without
    # a brake, every batch would send a signal to the interface thread.  One every
    # 150 ms is enough to show that it is moving, and the last one always goes
    # through.
    ultimo_segnale = [0.0]

    def _tick(done: int, total: int) -> None:
        adesso = time.monotonic()
        if done < total and adesso - ultimo_segnale[0] < 0.15:
            return
        ultimo_segnale[0] = adesso
        quota = done / total if total else 0
        progress_cb(300 + int(100 * quota), 500,
                    tr("work.model_sentence", etichetta.capitalize(),
                       number(done), number(total), f"{quota:.0%}"))

    if _fermarsi():
        raise InterruzioneRichiesta(tr("work.model_cancelled", etichetta))
    previsioni = esegui(superficie, risorse, _tick)
    if _fermarsi():
        raise InterruzioneRichiesta(tr("work.model_cancelled", etichetta))

    progress_cb(400, 500, tr("work.model_comparing", etichetta))
    esito = model_eval.evaluate_predictions(universo, previsioni, modello=etichetta)
    _salva_confronto(workspace, run_id, etichetta, provenienza, esito,
                     log_cb, progress_cb)


def run_stanza(
    workspace: Path,
    run_id: str,
    model_dir: str,
    filters: dict,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
    annullato=None,
) -> None:
    from greek_corpus_pipeline.analyzers import run_stanza_analysis
    from greek_corpus_pipeline.model_support import ensure_stanza_resources, stanza_identity

    _confronto_con_modello(
        workspace, run_id, filters, etichetta="stanza",
        prepara=lambda: ensure_stanza_resources(model_dir),
        esegui=lambda superficie, risorse, tick: run_stanza_analysis(
            superficie, model_dir=str(risorse), progress=tick),
        identita=stanza_identity,
        progress_cb=progress_cb, log_cb=log_cb, annullato=annullato)


def run_udpipe(
    workspace: Path,
    run_id: str,
    model_path: str,
    default_path: str,
    filters: dict,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
    annullato=None,
) -> None:
    from greek_corpus_pipeline.analyzers import run_udpipe_analysis
    from greek_corpus_pipeline.model_support import ensure_udpipe_model, udpipe_identity

    scelto = (model_path or "").strip() or default_path

    def prepara():
        ensure_udpipe_model(scelto)
        return scelto

    def fase(nome: str) -> None:
        if nome == "carico":
            log_cb(tr("work.udpipe_subprocess"))
        elif nome == "pronto":
            log_cb(tr("work.udpipe_subprocess_ready"))

    _confronto_con_modello(
        workspace, run_id, filters, etichetta="udpipe",
        prepara=prepara,
        esegui=lambda superficie, risorse, tick: run_udpipe_analysis(
            superficie, model_path=risorse, progress=tick,
            annullato=annullato, fase=fase),
        identita=udpipe_identity,
        progress_cb=progress_cb, log_cb=log_cb, annullato=annullato)


def export_figures(
    workspace: Path,
    run_id: str,
    output_dir: str,
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
) -> None:
    """Render the figures of the run at 300 dpi into a folder."""
    from greek_corpus_pipeline import corpus_metadata, figures, stats
    from greek_corpus_pipeline.storage import artifact_exists, load_dataframe

    def _load(name: str) -> pd.DataFrame:
        return (load_dataframe(workspace, run_id, name)
                if artifact_exists(workspace, run_id, name) else pd.DataFrame())

    progress_cb(1, 20, tr("work.preparing"))
    tokens = corpus_metadata.enrich_tokens(_load("tokens"))
    arcs = _load("arcs")
    sentence_metrics = stats.tree_metrics(tokens, arcs) if not tokens.empty else pd.DataFrame()

    index = figures.export_article_figures(
        output_dir,
        tokens=tokens,
        findings=_load("findings"),
        arcs=arcs,
        sentence_metrics=sentence_metrics,
        stanza_comparison=_load("stanza_comparison"),
        udpipe_comparison=_load("udpipe_comparison"),
        corrected=_load("corrected_tokens"),
        progress=lambda done, total, message: progress_cb(done, total, message),
    )
    log_cb(tr("work.figures_written", len(index), output_dir))
    progress_cb(20, 20, tr("work.figures_done"))


# ---------------------------------------------------------------------------
# Loading a saved run back into the interface
# ---------------------------------------------------------------------------

def _drop_withdrawn_rules(findings) -> pd.DataFrame:
    """Findings of rules that are not in the catalogue, removed.

    A findings table is a *record* of a past run: it stores the rule's name and
    explanation as they read on the day it was produced. A run saved with another
    catalogue would show rules that this program does not have, under the names it
    gave them, with no indication that the catalogue is different. Re-running the
    detection fixes it, but the user should not have to know that. So the
    filter is applied when the run is read, not when it is written.
    """
    if not isinstance(findings, pd.DataFrame) or findings.empty:
        return findings if isinstance(findings, pd.DataFrame) else pd.DataFrame()
    if "rule_id" not in findings.columns:
        return findings
    from greek_corpus_pipeline.rule_catalog import RULE_CATALOG

    known = findings["rule_id"].astype("string").isin(set(RULE_CATALOG)).fillna(False)
    if bool(known.all()):
        return findings
    logging.info("Discarded %d findings of rules that are not in the catalogue: %s",
                 int((~known).sum()),
                 ", ".join(sorted(set(findings.loc[~known, "rule_id"].astype(str)))))
    return findings[known].reset_index(drop=True)


class RunLoader(QThread):
    """Reads everything a run has produced, off the UI thread."""

    done = pyqtSignal(dict)
    error = pyqtSignal(str)

    #: The tables that are loaded together with the run.
    #:
    #: The comparisons with the models are **not** there, and it is deliberate.  A
    #: ``stanza_comparison`` table saved in this folder may come from an earlier run,
    #: produced with other units, other filters or another version of the model;
    #: loading it here would put it beside the numbers of now as if it were theirs.
    #: Only its provenance is loaded, which is small, and the table is requested from
    #: :meth:`AppState.model_comparison`, which gives it only if the provenance matches
    #: the corpus loaded now.
    ARTIFACTS = [
        "tokens", "findings", "arcs", "corrected_tokens", "token_diff",
        "lemma_inventory", "spelling_variation",
        "variation_morfologia", "variation_posizioni", "variation_contesto",
        "variation_dipendenze", "variation_lemmi",
    ]

    #: The saved statistics that are loaded together with the run.  The evaluations of
    #: the models are not there: they are read when they are needed, so that the folder
    #: of the run remains the only thing that says what it contains.
    STATISTICHE = ["stats_before", "stats_after"]

    def __init__(self, workspace: Path, run_id: str, parent=None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.run_id = run_id

    def run(self) -> None:
        try:
            from greek_corpus_pipeline import corpus_metadata
            from greek_corpus_pipeline.storage import (
                artifact_exists, load_dataframe, load_metadata, load_stats_if_present,
            )

            data: dict[str, object] = {"run_id": self.run_id}
            for name in self.ARTIFACTS:
                data[name] = (load_dataframe(self.workspace, self.run_id, name)
                              if artifact_exists(self.workspace, self.run_id, name)
                              else pd.DataFrame())

            tokens = data.get("tokens")
            if isinstance(tokens, pd.DataFrame) and not tokens.empty:
                # Author, date, dialect and genre are attached once, here, so
                # that every page downstream can group by them without knowing
                # that a catalogue exists.
                data["tokens"] = corpus_metadata.enrich_tokens(tokens)

            # Findings saved with a different catalogue can name rules that this
            # catalogue does not contain, and they carry the name and the
            # explanation of those rules baked into the row: reopening such a run
            # would show rules that this program does not have, and nothing would
            # say so. They are dropped here, once, at the door.
            data["findings"] = _drop_withdrawn_rules(data.get("findings"))

            for name in self.STATISTICHE:
                data[name] = load_stats_if_present(self.workspace, self.run_id, name)
            try:
                data["metadata"] = load_metadata(self.workspace, self.run_id)
            except Exception:
                data["metadata"] = {}

            self.done.emit(data)
        except BaseException as exception:            # noqa: BLE001
            message = f"{type(exception).__name__}: {exception}\n{traceback.format_exc()}"
            logging.error(message)
            self.error.emit(message)
