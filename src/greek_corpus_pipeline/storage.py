from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import unicodedata
import warnings

import pandas as pd


RUNS_DIRNAME = "runs"

#: Artifacts with a fixed, documented filename.
#:
#: Anything not listed here still gets saved — under ``<name>.parquet`` — so
#: that adding a new kind of result (a new variation table, for instance) does
#: not require editing this dictionary. The explicit entries exist
#: for the artifacts other tools read, whose names are therefore a contract.
ARTIFACT_FILENAMES = {
    "tokens": "tokens.parquet",
    "findings": "findings.parquet",
    "arcs": "arcs.parquet",
    "postag_findings": "postag_findings.parquet",
    "lemma_findings": "lemma_findings.parquet",
    "corrected_tokens": "corrected_tokens.parquet",
    "token_diff": "token_diff.parquet",
    "lemma_inventory": "lemma_inventory.parquet",
    "spelling_variation": "spelling_variation.parquet",
    "stanza_tokens": "stanza_tokens.parquet",
    "stanza_comparison": "stanza_comparison.parquet",
    "udpipe_tokens": "udpipe_tokens.parquet",
    "udpipe_comparison": "udpipe_comparison.parquet",
}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")

_GREEK_TRANSLITERATION: dict[str, str] = {
    "\u03b1": "a", "\u03b2": "b", "\u03b3": "g", "\u03b4": "d", "\u03b5": "e", "\u03b6": "z",
    "\u03b7": "e", "\u03b8": "th", "\u03b9": "i", "\u03ba": "k", "\u03bb": "l", "\u03bc": "m",
    "\u03bd": "n", "\u03be": "x", "\u03bf": "o", "\u03c0": "p", "\u03c1": "r", "\u03c3": "s",
    "\u03c2": "s", "\u03c4": "t", "\u03c5": "y", "\u03c6": "ph", "\u03c7": "ch", "\u03c8": "ps",
    "\u03c9": "o",
}


def runs_root(workspace: str | Path) -> Path:
    root = Path(workspace) / RUNS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify(value: str) -> str:
    """Convert an arbitrary string (including Greek) into a safe ASCII slug."""
    nfkd = unicodedata.normalize("NFKD", value.strip())
    parts: list[str] = []
    for char in nfkd:
        lower = char.lower()
        if lower in _GREEK_TRANSLITERATION:
            parts.append(_GREEK_TRANSLITERATION[lower])
        elif unicodedata.category(char) == "Mn":
            pass  # skip combining diacritics
        else:
            parts.append(char)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", "".join(parts)).strip("-").lower()
    return slug or "run"


def create_run_id(corpus_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{slugify(corpus_name)}"


def run_dir(workspace: str | Path, run_id: str) -> Path:
    return runs_root(workspace) / run_id


def metadata_path(workspace: str | Path, run_id: str) -> Path:
    return run_dir(workspace, run_id) / "metadata.json"


def stats_path(workspace: str | Path, run_id: str, name: str) -> Path:
    return run_dir(workspace, run_id) / f"{name}.json"


def report_dir(workspace: str | Path, run_id: str) -> Path:
    target = run_dir(workspace, run_id) / "reports"
    target.mkdir(parents=True, exist_ok=True)
    return target


def artifact_path(workspace: str | Path, run_id: str, artifact_name: str) -> Path:
    filename = ARTIFACT_FILENAMES.get(artifact_name)
    if filename is None:
        filename = _SAFE_NAME_RE.sub("_", artifact_name) + ".parquet"
    return run_dir(workspace, run_id) / filename


def save_metadata(workspace: str | Path, run_id: str, metadata: dict[str, object]) -> Path:
    target = metadata_path(workspace, run_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return target


def load_metadata(workspace: str | Path, run_id: str) -> dict[str, object]:
    target = metadata_path(workspace, run_id)
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_stats(workspace: str | Path, run_id: str, name: str, stats: dict[str, object]) -> Path:
    """Writes a statistics file, completely or not at all.

    Two things are guaranteed. The folder of the run is created the way
    :func:`save_metadata` and :func:`save_dataframe` create it, because a save that
    fails only for a missing folder would raise the same ``FileNotFoundError`` as a
    missing file, and the two problems would become indistinguishable when the
    error is read.

    And the write goes through a temporary file in the same folder, moved into place
    only at the end: a write interrupted halfway would leave a truncated JSON with
    the right name, which at the next run exists, can be read and cannot be opened.
    A half-written result is worse than an absent one, because the program already
    knows how to handle absence. It is the same device that
    :func:`~greek_corpus_pipeline.model_support.ensure_udpipe_model` uses for the
    download of the model.
    """
    target = stats_path(workspace, run_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = target.with_name(target.name + ".tmp")
    try:
        with temporaneo.open("w", encoding="utf-8") as handle:
            json.dump(stats, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporaneo, target)
    except BaseException:
        temporaneo.unlink(missing_ok=True)
        raise
    return target


def load_stats(workspace: str | Path, run_id: str, name: str) -> dict[str, object]:
    """The statistics saved under *name*. Raises if there are none.

    For callers that require the file. Whoever is asking *whether* anything has been
    saved uses :func:`load_stats_if_present`, which is the only place where the
    program decides what “absent” means.
    """
    target = stats_path(workspace, run_id, name)
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_stats_if_present(workspace: str | Path, run_id: str, name: str) -> dict[str, object]:
    """The statistics saved under *name*, or ``{}`` if there are none.

    It exists because “nothing has been saved” is a question that the program asks
    often — a model cache, the statistics of a reopened run — and every place that
    answered it by itself would answer it a little differently. The risk is
    concrete: a caller that wrote ``load_stats(...) or {}``, believing that a
    missing file returns empty, would fail with ``FileNotFoundError`` on the first
    comparison of a new run, before even starting the model, because
    :func:`load_stats` raises.

    A missing file and an unreadable file give the same answer, and for the same
    reason: neither is a result. The second, however, is not normal, so it is
    reported; and the file stays where it is, because deleting the evidence of a
    fault is not a way of repairing it.
    """
    target = stats_path(workspace, run_id, name)
    if not target.exists():
        return {}
    try:
        with target.open("r", encoding="utf-8") as handle:
            salvato = json.load(handle)
    except (OSError, ValueError) as exc:
        warnings.warn(f"Unreadable statistics in '{target.name}': {exc}")
        return {}
    return salvato if isinstance(salvato, dict) else {}


def save_dataframe(workspace: str | Path, run_id: str, artifact_name: str, frame: pd.DataFrame) -> Path:
    target = artifact_path(workspace, run_id, artifact_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target, index=False)
    return target


def load_dataframe(workspace: str | Path, run_id: str, artifact_name: str) -> pd.DataFrame:
    target = artifact_path(workspace, run_id, artifact_name)
    return pd.read_parquet(target)


def artifact_exists(workspace: str | Path, run_id: str, artifact_name: str) -> bool:
    return artifact_path(workspace, run_id, artifact_name).exists()


def stats_exist(workspace: str | Path, run_id: str, name: str) -> bool:
    return stats_path(workspace, run_id, name).exists()


def list_runs(workspace: str | Path) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for directory in sorted(runs_root(workspace).iterdir(), reverse=True):
        if not directory.is_dir():
            continue
        meta_file = directory / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            metadata = load_metadata(workspace, directory.name)
        except Exception as exc:
            warnings.warn(f"Could not read metadata for run '{directory.name}': {exc}")
            continue
        runs.append({"run_id": directory.name, **metadata})
    return runs


def update_stage_status(
    workspace: str | Path,
    run_id: str,
    stage: str,
    status: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = load_metadata(workspace, run_id)
    stages = metadata.setdefault("stages", {})
    stage_record: dict[str, object] = dict(stages.get(stage, {}))
    stage_record["status"] = status
    stage_record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    if extra:
        stage_record.update(extra)
    stages[stage] = stage_record
    save_metadata(workspace, run_id, metadata)
    return metadata
