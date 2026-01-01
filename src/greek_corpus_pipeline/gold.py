"""The gold standard corrected by the user: how it is built, saved and exported.

The program ships with no gold standard. There is only one, and it arises from the
corrections that the user makes on their own computer: the original corpus stays intact
in ``tokens.parquet``, the decisions accumulate in ``correzioni_manuali.csv``, and the
result of applying them is ``corrected_tokens.parquet``. This module is the bridge
between those three files and the three things the user wants to do with them: save it
to resume tomorrow, export it in a format that other tools read, and measure what
changes when an automatic model is evaluated against the revised version instead of the
original one.

On saving. A gold standard scattered over three files inside the working folder is not
something one sends to a colleague. ``save_gold_bundle`` makes a single .zip file that
contains the revised version, the decisions that produced it and an identity card;
``load_gold_bundle`` puts it back into a run folder. The decisions travel together with
the result because without them the revised version is a datum whose provenance nobody
can discuss any more.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BUNDLE_SUFFIX = ".gcpgold"
BUNDLE_VERSION = 1

_META_NAME = "gold_meta.json"
_CORRECTED_NAME = "corrected_tokens.parquet"
_MANUAL_NAME = "correzioni_manuali.csv"
_DIFF_NAME = "token_diff.parquet"

#: What a decision must say about itself.
#:
#: The first seven columns are the original ones: where the word is and what it becomes.
#: By themselves they say *what* was changed and nothing else — not when, not why, not by
#: whom, and not even what one started from. For work by a single hand this may be
#: enough; for a revision that two people must be able to discuss, it is not. The columns
#: added afterwards answer those questions, and they are written once only, here, so that
#: ``ensure_manual_columns`` can update files already saved without breaking them.

def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text, in the language of the interface, with English as the fallback.

    These messages end up in a warning window, so they follow the chosen language; the
    fallback exists because the module must also work without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:
        return fallback.format(*args) if args else fallback
    return text


MANUAL_COLUMNS = [
    "document_id", "sentence_id", "token_id", "form",
    "corrected_lemma", "corrected_postag", "corrected_relation",
    "previous_lemma", "previous_postag", "previous_relation",
    "rule_id", "decided_by", "decided_at", "reason", "status",
    "program_version",
]

#: The seven columns of the base format. A file that has only these is readable:
#: the others are added empty.
BASE_MANUAL_COLUMNS = MANUAL_COLUMNS[:7]

#: States that a decision can have. The default is “accettata” (accepted) because at
#: present the interface saves only decisions that have been taken; the other two exist
#: because a multi-hand workflow needs them and because a file that contains them must be
#: readable without changes to the program.
DECISION_STATES = ("accettata", "proposta", "respinta")


def ensure_manual_columns(manual: pd.DataFrame | None) -> pd.DataFrame:
    """Bring a register of decisions to the current form.

    A file written with seven columns is completed with the others, empty, instead of
    being rejected. The order of the columns is that of :data:`MANUAL_COLUMNS`, and the
    columns that the user may have added on their own stay at the end.
    """
    if manual is None or (hasattr(manual, "empty") and manual.empty
                          and not len(getattr(manual, "columns", []))):
        return pd.DataFrame(columns=MANUAL_COLUMNS)
    frame = manual.copy()
    for column in MANUAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    extra = [c for c in frame.columns if c not in MANUAL_COLUMNS]
    return frame[MANUAL_COLUMNS + extra]


def manual_record(
    row: dict,
    *,
    lemma: str = "",
    postag: str = "",
    relation: str = "",
    decided_by: str = "",
    reason: str = "",
    status: str = "accettata",
    timestamp: str | None = None,
) -> pd.DataFrame:
    """A register row with everything needed to read it again tomorrow.

    ``row`` is the finding being worked on, so that the starting value and the rule that
    raised the case end up in the register without the user having to copy them.
    """
    from . import __version__

    def value(name: str) -> str:
        """The starting value as text, and empty as empty.

        A finding that does not concern the relation carries ``NaN`` in that column, and
        ``str(NaN)`` is the string “nan”: in the register of decisions it must not
        appear as if somebody had written that word.
        """
        got = row.get(name, "")
        if got is None:
            return ""
        if not isinstance(got, str):
            try:
                if pd.isna(got):
                    return ""
            except (TypeError, ValueError):            # noqa: BLE001
                pass
        return str(got)

    return pd.DataFrame([{
        "document_id": value("document_id"),
        "sentence_id": value("sentence_id"),
        "token_id": value("token_id"),
        "form": value("form"),
        "corrected_lemma": lemma,
        "corrected_postag": postag,
        "corrected_relation": relation,
        "previous_lemma": value("lemma"),
        "previous_postag": value("postag"),
        "previous_relation": value("relation"),
        "rule_id": value("rule_id"),
        "decided_by": decided_by,
        "decided_at": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
        "status": status if status in DECISION_STATES else "accettata",
        "program_version": __version__,
    }])


# ─────────────────────────────────────────────────────── state of the gold ──
@dataclass(frozen=True)
class GoldState:
    """How much work there is inside the gold standard, in three numbers and a judgement."""

    manual_corrections: int
    changed_tokens: int
    total_tokens: int

    @property
    def has_corrections(self) -> bool:
        return self.changed_tokens > 0 or self.manual_corrections > 0

    @property
    def changed_share(self) -> float:
        return (self.changed_tokens / self.total_tokens) if self.total_tokens else 0.0


def manual_corrections_path(run_directory: str | Path) -> Path:
    return Path(run_directory) / _MANUAL_NAME


def read_manual_corrections(run_directory: str | Path) -> pd.DataFrame:
    """The decisions taken so far, or an empty table with the right columns."""
    path = manual_corrections_path(run_directory)
    if not path.exists():
        return pd.DataFrame(columns=MANUAL_COLUMNS)
    try:
        return ensure_manual_columns(
            pd.read_csv(path, dtype=str, keep_default_na=False))
    except Exception:
        return pd.DataFrame(columns=MANUAL_COLUMNS)


def gold_state(
    tokens: pd.DataFrame,
    corrected: pd.DataFrame,
    manual: pd.DataFrame,
    token_diff: pd.DataFrame | None = None,
) -> GoldState:
    """How many corrections there are, counted on the data and not on the intention.

    The count of changed rows comes from ``token_diff`` when it exists, and is otherwise
    recomputed: the gold standard is the revised version, not the file of decisions, and
    the two can diverge if the user has written corrections and has not yet applied
    them.
    """
    if token_diff is None or token_diff.empty:
        if corrected is None or corrected.empty or tokens is None or tokens.empty:
            changed = 0
        else:
            from .analysis import compute_token_diff
            changed = len(compute_token_diff(tokens, corrected))
    else:
        changed = len(token_diff)
    return GoldState(
        manual_corrections=0 if manual is None else len(manual),
        changed_tokens=int(changed),
        total_tokens=0 if tokens is None else len(tokens),
    )


# ────────────────────────────────────────────────────── saving and resuming ──
def save_gold_bundle(
    target_path: str | Path,
    corrected: pd.DataFrame,
    manual: pd.DataFrame,
    token_diff: pd.DataFrame | None = None,
    *,
    corpus_name: str = "",
    run_id: str = "",
    timestamp: str | None = None,
) -> Path:
    """Write the revised version, the decisions and the card into a single .gcpgold file."""
    target = Path(target_path)
    if target.suffix.lower() != BUNDLE_SUFFIX:
        target = target.with_suffix(BUNDLE_SUFFIX)
    target.parent.mkdir(parents=True, exist_ok=True)

    if corrected is None or corrected.empty:
        raise ValueError(_t(
            "gold.err.nothing_to_save",
            "There is no revised corpus to save. Apply the corrections in the «Correct» "
            "step first."))

    manual = manual if manual is not None else pd.DataFrame(columns=MANUAL_COLUMNS)
    meta = {
        "format_version": BUNDLE_VERSION,
        "corpus_name": corpus_name,
        "run_id": run_id,
        "created_at_utc": timestamp or datetime.now(timezone.utc).isoformat(),
        "tokens": int(len(corrected)),
        "manual_corrections": int(len(manual)),
        "changed_tokens": int(0 if token_diff is None else len(token_diff)),
    }

    scratch = target.parent / f".{target.stem}.tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        corrected_file = scratch / _CORRECTED_NAME
        corrected.to_parquet(corrected_file, index=False)
        manual_file = scratch / _MANUAL_NAME
        manual.to_csv(manual_file, index=False, encoding="utf-8-sig")
        members = [(corrected_file, _CORRECTED_NAME), (manual_file, _MANUAL_NAME)]
        if token_diff is not None and not token_diff.empty:
            diff_file = scratch / _DIFF_NAME
            token_diff.to_parquet(diff_file, index=False)
            members.append((diff_file, _DIFF_NAME))

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(_META_NAME, json.dumps(meta, ensure_ascii=False, indent=2))
            for source, name in members:
                archive.write(source, name)
    finally:
        for leftover in scratch.glob("*"):
            leftover.unlink(missing_ok=True)
        scratch.rmdir()
    return target


def read_gold_meta(bundle_path: str | Path) -> dict:
    """The identity card of the gold standard, without reading the corpus."""
    with zipfile.ZipFile(Path(bundle_path)) as archive:
        if _META_NAME not in archive.namelist():
            raise ValueError(_t(
                "gold.err.not_a_bundle",
                "This file does not look like a bundle produced by GCP: {0} is missing.", _META_NAME))
        return json.loads(archive.read(_META_NAME).decode("utf-8"))


def load_gold_bundle(
    bundle_path: str | Path,
    run_directory: str | Path,
) -> dict:
    """Put the gold standard back into a run folder, and return its card.

    The original corpus is not touched: only the corrected corpus, the decisions and the
    table of differences are written. On reopening the program on that run, the gold
    standard is there again.
    """
    bundle = Path(bundle_path)
    destination = Path(run_directory)
    destination.mkdir(parents=True, exist_ok=True)
    meta = read_gold_meta(bundle)

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        if _CORRECTED_NAME not in names:
            raise ValueError(_t(
                "gold.err.incomplete",
                "The file does not hold the revised corpus: the bundle is incomplete."))
        for name in (_CORRECTED_NAME, _MANUAL_NAME, _DIFF_NAME):
            if name in names:
                (destination / name).write_bytes(archive.read(name))
    return meta


# ────────────────────────────────────────────────────────────────── exports ──
def export_gold_xml(corrected: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    """AGDT XML, one file per document, for those who stay within the Perseus tradition."""
    from .xmlio import export_corrected_xml
    return export_corrected_xml(corrected, output_dir)


def export_gold_csv(corrected: pd.DataFrame, output_path: str | Path) -> Path:
    """A single table, one row per word, openable in a spreadsheet."""
    target = Path(output_path)
    if target.suffix.lower() != ".csv":
        target = target.with_suffix(".csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    preferred = ["document_id", "source_file", "sentence_id", "sentence_index",
                 "token_id", "token_index", "form", "lemma", "postag",
                 "relation", "head", "artificial"]
    columns = [name for name in preferred if name in corrected.columns]
    columns += [name for name in corrected.columns
                if name not in columns and not name.startswith("_")]
    frame = corrected.loc[:, columns]
    sort_by = [c for c in ("source_file", "sentence_index", "token_index") if c in frame.columns]
    if sort_by:
        frame = frame.sort_values(sort_by)
    frame.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def export_gold_conllu(
    corrected: pd.DataFrame,
    output_path: str | Path,
    *,
    corpus_name: str = "",
) -> list[Path]:
    """CoNLL-U, for those who work with the Universal Dependencies tools."""
    from .conllu import export_conllu
    target = Path(output_path)
    if target.suffix.lower() != ".conllu":
        target = target.with_suffix(".conllu")
    return export_conllu(corrected, target, corpus_name=corpus_name)


# ──────────────────────────────────────── the models against both references ──
KEY_COLUMNS = ["document_id", "sentence_id", "token_id"]


def rescore_model(
    reference: pd.DataFrame,
    model_comparison: pd.DataFrame,
    label: str,
) -> dict:
    """Recount the agreement of a model against any reference.

    The comparison table saved when the model was run already carries, word by word,
    what the model wrote. To know how much it agrees with the revised version there is
    no need to run the model again — which on Gorman costs twenty minutes — it is enough
    to join those two columns to the corrected corpus on the token key. This is why the
    comparison with the gold standard is immediate.
    """
    empty = {"aligned_tokens": 0, "lemma_matches": 0, "postag_matches": 0,
             "lemma_match_rate": None, "postag_match_rate": None}
    if (reference is None or reference.empty
            or model_comparison is None or model_comparison.empty):
        return empty

    lemma_column = f"lemma_{label}"
    postag_column = f"postag_{label}"
    if lemma_column not in model_comparison.columns or postag_column not in model_comparison.columns:
        return empty

    keys = [column for column in KEY_COLUMNS
            if column in reference.columns and column in model_comparison.columns]
    if not keys:
        return empty

    left = reference[keys + ["lemma", "postag"]].copy()
    right = model_comparison[keys + [lemma_column, postag_column]].copy()
    for column in keys:
        left[column] = left[column].astype(str)
        right[column] = right[column].astype(str)
    merged = left.merge(right, on=keys, how="inner")
    if merged.empty:
        return empty

    lemma_match = merged["lemma"].astype("string").fillna("") == \
        merged[lemma_column].astype("string").fillna("")
    postag_match = merged["postag"].astype("string").fillna("") == \
        merged[postag_column].astype("string").fillna("")
    return {
        "aligned_tokens": int(len(merged)),
        "lemma_matches": int(lemma_match.sum()),
        "postag_matches": int(postag_match.sum()),
        "lemma_match_rate": round(float(lemma_match.mean()) * 100, 2),
        "postag_match_rate": round(float(postag_match.mean()) * 100, 2),
    }


def model_reference_table(
    tokens: pd.DataFrame,
    corrected: pd.DataFrame,
    stanza_comparison: pd.DataFrame | None = None,
    udpipe_comparison: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Each model against the original corpus and against the gold standard, on the same
    row.

    The difference column is the only thing this table really says: by how much the
    agreement moves when the reference changes. It does not say that the model has
    improved — the model has not changed at all — but that the yardstick with which we
    measure it is no longer the same.
    """
    rows: list[dict] = []
    for label, comparison in (("Stanza", stanza_comparison), ("UDPipe", udpipe_comparison)):
        if comparison is None or comparison.empty:
            continue
        key = label.lower()
        against_original = rescore_model(tokens, comparison, key)
        against_gold = rescore_model(corrected, comparison, key) \
            if corrected is not None and not corrected.empty else None
        for field, readable in (("lemma", "lemma"), ("postag", "etichetta")):
            original_rate = against_original.get(f"{field}_match_rate")
            gold_rate = against_gold.get(f"{field}_match_rate") if against_gold else None
            rows.append({
                "modello": label,
                "campo": readable,
                "token confrontati": against_original.get("aligned_tokens", 0),
                "accordo con l'originale %": original_rate,
                "accordo con il gold %": gold_rate,
                "differenza": (None if original_rate is None or gold_rate is None
                               else round(gold_rate - original_rate, 2)),
            })
    return pd.DataFrame(rows)
