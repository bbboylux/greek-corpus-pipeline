"""Run Stanza and UDPipe over a corpus that is already tokenised.

Designed for machines with little memory.  Three things would otherwise make a
laptop stop responding while a model is running, and the module avoids all of
them:

1. **Sending the whole corpus to the model in one call.** Stanza would build a
   single ``Document`` holding 625,176 words, and UDPipe would receive one
   CoNLL-U string of 625,176 lines.  Both work in batches of sentences, so peak
   memory is proportional to the batch, not to the corpus.

2. **One Python dict per token.** Calling
   ``rows.append({**ref_row.to_dict(), ...})`` once per token would build
   625,176 dicts, each a full copy of a fifteen-column row, and then a
   DataFrame out of them.  The module collects two flat lists — lemma and tag —
   and attaches them as columns to a slice of the reference table.  That alone
   is the difference between gigabytes and megabytes.

3. **Letting Torch take every core.** With all cores busy the interface would
   have none left and Windows would show the window as unresponsive.  One core
   is left free.

A fourth point is not about speed but about the person watching: the model
stage reports progress after every batch, so the bar keeps moving and the run
can be followed.
"""
from __future__ import annotations

import os
import time
import warnings
from io import StringIO
from pathlib import Path
from typing import Callable, Iterator

import numpy as np
import pandas as pd

from .model_eval import prepare_model_input
from .units import SENTENCE_ORDER


def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text, in the language of the interface, with English as the fallback.

    These two messages end up before the eyes of whoever opens the models step, so they
    follow the chosen language; the fallback exists because the module must also work
    without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    testo = tr(key, *args)
    return fallback if testo == key else testo

# How many sentences go to the model at a time.
#
# The batch size is not only a matter of memory: it is the duration of a single
# call to the library, and therefore the duration of the interface freeze.
# ``ufal.udpipe`` **does not release the GIL** while it works —
# measured: an observer thread beating every 0.05 s receives exactly two
# beats around a call of 500 sentences, and its maximum delay is equal to the
# whole duration of the call (0.90 s for 100 sentences, 4.06 s for 500, 17.18 s
# for 2,000). As long as the call lasts, no other Python thread can run: not
# even that of the interface, although the work sits in a QThread.
#
# The small batch costs very little — 2,000 sentences in 16.89 s in batches
# of 500 and in 17.82 s in batches of 25, that is 5.5% more — and it reduces
# the freeze thirteenfold, from 4.91 s to 0.38 s. And it does not change the
# result: form, lemma and tag of the 47,485 rows produced are identical at
# every batch size tried (500, 200, 100, 50, 25, 10); only the number of
# ``# newdoc`` / ``# newpar`` comment lines changes, which the reader discards.
SENTENCE_BATCH = 500

#: The UDPipe batch, chosen on the measurement of the freeze (see above).
UDPIPE_SENTENCE_BATCH = 25

#: The pause between one batch and the next, in seconds.
#:
#: The small batch shortens the single call; this pause guarantees that between
#: one call and the next the interface thread **receives** the GIL instead of
#: having to seize it. ``time.sleep`` releases it and the operating system can
#: advance the other thread; without it, on a machine with few processors the
#: working thread takes it straight back and the window may stay frozen even
#: with short batches. The cost is a few milliseconds per batch and nothing more.
PAUSA_FRA_LOTTI = 0.005

#: The Stanza batch. Here the freeze has not been measured — the library is not
#: installed on the test machine — but the structure is the same: the sentences
#: arrive already segmented (``tokenize_pretokenized=True``) and are analysed
#: one by one, so the batch size cannot change the analysis of any sentence.
#: The value is cautious.
STANZA_SENTENCE_BATCH = 100

ProgressCallback = Callable[[int, int], None]


# ─────────────────────────────────────────────────────────── shared helpers ── The
# cleaning of the form lives in ``sanitize_model_form`` of ``model_eval``; this module
# does not keep a second name for it.


def _model_input(tokens: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    """Sort the tokens the way a model must see them and index the sentences.

    Returns the sorted table, an array of positions at which each sentence
    starts (with the total length appended), and the list of surface forms.
    Working with positions instead of a list of small DataFrames is what keeps
    the alignment cheap: no per-sentence object is ever created.
    """
    work = tokens
    if not {"_sentenza", "_posizione", "_model_form"} <= set(work.columns):
        # The caller has not prepared the input: it is prepared here, with the same
        # function, so that the definition of what the model receives lives in one place
        # only.
        work = prepare_model_input(work)
    else:
        work = work.sort_values(list(SENTENCE_ORDER)).reset_index(drop=True)

    if work.empty:
        return work, np.array([0]), []

    keys = work["_sentenza"].to_numpy()
    changed = keys[1:] != keys[:-1]
    starts = np.concatenate(([0], np.flatnonzero(changed) + 1, [len(work)]))
    return work, starts, work["_model_form"].tolist()


def _batches(starts: np.ndarray, size: int) -> Iterator[tuple[int, int, int, int]]:
    """Yield (first sentence, last sentence, first token, last token) per batch."""
    n_sentences = len(starts) - 1
    for first in range(0, n_sentences, size):
        last = min(first + size, n_sentences)
        yield first, last, int(starts[first]), int(starts[last])


def _limit_threads() -> None:
    """The ceiling on computing threads, as far as it can still be set.

    The policy lives in :mod:`greek_corpus_pipeline.cpu` and applies to the whole
    program. The call is repeated here because the analyser may also be used
    outside the interface, but **environment variables written at this point no
    longer affect BLAS**: numpy is already imported and its pool is already
    sized. The right place is the start of the program, in ``app_qt.py``; this
    remains the safety net for whoever imports the module from a script.

    On torch, instead, the limit can still be set at run time, and it is the one
    that matters most: it is the only one of the libraries involved that opens
    two pools.
    """
    from .cpu import limita_thread, limita_torch
    limita_thread()
    limita_torch()


def _assemble(work: pd.DataFrame, lemmas: list, postags: list, kept: list,
              analyzer: str, original_columns) -> pd.DataFrame:
    """Attach the model's two columns to the reference rows it covered.

    *kept* is a boolean per row: False marks a token inside a sentence the model
    re-segmented. Those rows are dropped; the alignment of every other row is
    guaranteed by construction rather than by a running counter.
    """
    covered = len(lemmas)
    out = work.iloc[:covered].copy()
    out["analyzer"] = analyzer
    out["lemma"] = lemmas
    out["postag"] = postags
    out = out.loc[np.asarray(kept, dtype=bool)]
    # The two alignment columns travel with the predictions: without them the comparison
    # would go back to looking for the correspondence on the form.
    keep = [c for c in original_columns if c != "_model_form"]
    keep = list(keep) + [c for c in ("_sentenza", "_posizione") if c not in keep]
    return out.loc[:, [c for c in keep if c in out.columns]].reset_index(drop=True)


def check_stanza_available() -> tuple[bool, str]:
    try:
        import stanza  # noqa: F401
    except ImportError:
        return (
            False,
            _t("models.err.stanza_missing",
               "Stanza is not installed. Add it with `pip install -e \".[models]\"`, or "
               "on its own with `pip install stanza`."),
        )
    return True, ""


def check_udpipe_available() -> tuple[bool, str]:
    try:
        from ufal import udpipe  # noqa: F401
    except ImportError:
        return (
            False,
            _t("models.err.udpipe_missing",
               "UDPipe is not installed. Add it with `pip install -e \".[models]\"`, or "
               "on its own with `pip install ufal.udpipe`."),
        )
    return True, ""


# ────────────────────────────────────────────────────────────────── Stanza ──
def run_stanza_analysis(
    tokens: pd.DataFrame,
    model_dir: str | None = None,
    progress: ProgressCallback | None = None,
    batch_size: int = STANZA_SENTENCE_BATCH,
) -> pd.DataFrame:
    """Run Stanza on a pre-tokenised corpus, a batch of sentences at a time.

    A sentence whose token count Stanza does not reproduce is filled with empty
    values rather than dropped, so the output stays row-aligned with the input
    and the caller can always merge on the token key.
    """
    available, message = check_stanza_available()
    if not available:
        raise RuntimeError(message)

    _limit_threads()
    import stanza

    work, starts, forms = _model_input(tokens)
    if work.empty:
        raise ValueError("No non-empty token forms are available for Stanza analysis.")

    pipeline = stanza.Pipeline(
        "grc",
        processors="tokenize,pos,lemma",
        tokenize_pretokenized=True,
        use_gpu=False,
        model_dir=model_dir,
        logging_level="WARN",
    )

    n_sentences = len(starts) - 1
    lemmas: list[str] = []
    postags: list[str] = []
    kept: list[bool] = []
    mismatched = 0

    for first, last, token_from, token_to in _batches(starts, batch_size):
        sentences = [forms[int(starts[s]):int(starts[s + 1])] for s in range(first, last)]
        document = pipeline(sentences)

        for offset, sentence in enumerate(document.sentences):
            expected = int(starts[first + offset + 1]) - int(starts[first + offset])
            words = sentence.words
            if len(words) != expected:
                mismatched += 1
                lemmas.extend([""] * expected)
                postags.extend([""] * expected)
                kept.extend([False] * expected)
                continue
            for word in words:
                lemmas.append(word.lemma or "")
                postags.append(word.xpos or word.upos or "")
            kept.extend([True] * expected)

        # A batch that produced fewer sentences than asked: pad to stay aligned.
        produced = len(document.sentences)
        for missing in range(produced, last - first):
            expected = int(starts[first + missing + 1]) - int(starts[first + missing])
            mismatched += 1
            lemmas.extend([""] * expected)
            postags.extend([""] * expected)
            kept.extend([False] * expected)

        del document
        if progress is not None:
            progress(last, n_sentences)
        time.sleep(PAUSA_FRA_LOTTI)

    if mismatched:
        warnings.warn(
            f"Stanza re-segmented {mismatched} sentence(s) out of {n_sentences}; "
            "those tokens are left blank instead of being misaligned.")

    return _assemble(work, lemmas, postags, kept, "stanza", tokens.columns)


# ────────────────────────────────────────────────────────────────── UDPipe ──


def _horizontal_batch(forms: list[str], starts: np.ndarray, first: int, last: int) -> str:
    """Generate input in the “horizontal” format for UDPipe.

    One sentence per line, tokens separated by spaces. Much simpler than CoNLL-U, and it
    does not trigger the infinite loop observed with the “_” fields of our pre-tokenised
    input.

    Spaces inside a single form are replaced with NBSP (U+00A0) so that UDPipe does not
    split it into several tokens.
    """
    return "\n".join(_righe_di_frase(forms, starts, first, last)) + "\n"


def _righe_di_frase(forms: list[str], starts: np.ndarray,
                    first: int = 0, last: int | None = None) -> list[str]:
    """One line per sentence, the tokens separated by spaces.

    This is the single definition of what UDPipe receives, and both routes use it — the
    in-process one and the separate-process one — because two definitions of the same
    line are two chances for the two results to diverge.
    """
    if last is None:
        last = len(starts) - 1
    righe: list[str] = []
    for frase in range(first, last):
        inizio, fine = int(starts[frase]), int(starts[frase + 1])
        token = [forms[i].replace(" ", " ") for i in range(inizio, fine)]
        righe.append(" ".join(token))
    return righe


def _read_conllu_batch(text: str, expected: list[int]) -> tuple[list[str], list[str], list[bool], int]:
    """Read one batch of CoNLL-U back, keeping the row alignment intact."""
    lemmas: list[str] = []
    postags: list[str] = []
    kept: list[bool] = []
    mismatched = 0
    sentence = 0
    current_lemmas: list[str] = []
    current_postags: list[str] = []

    def close() -> None:
        nonlocal sentence, mismatched, current_lemmas, current_postags
        if sentence >= len(expected):
            current_lemmas, current_postags = [], []
            return
        want = expected[sentence]
        if len(current_lemmas) == want:
            lemmas.extend(current_lemmas)
            postags.extend(current_postags)
            kept.extend([True] * want)
        else:
            mismatched += 1
            lemmas.extend([""] * want)
            postags.extend([""] * want)
            kept.extend([False] * want)
        sentence += 1
        current_lemmas, current_postags = [], []

    for raw in StringIO(text):
        line = raw.strip()
        if not line:
            if current_lemmas:
                close()
            continue
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if "-" in fields[0] or "." in fields[0]:
            continue
        current_lemmas.append(fields[2])
        current_postags.append(fields[4] if len(fields) > 4 and fields[4] != "_"
                               else (fields[3] if len(fields) > 3 else ""))
    if current_lemmas:
        close()

    while sentence < len(expected):          # UDPipe stopped early: pad
        mismatched += 1
        lemmas.extend([""] * expected[sentence])
        postags.extend([""] * expected[sentence])
        kept.extend([False] * expected[sentence])
        sentence += 1

    return lemmas, postags, kept, mismatched


def _leggi_lotti(lotti: list[str], starts, batch_size: int,
                 n_sentences: int, progress) -> tuple[list, list, list, int]:
    """From a list of CoNLL-U texts, one per batch, to the three aligned columns.

    This is the second half of the UDPipe pass, identical for both routes: what changes
    between a separate process and a direct call is **how** those texts are obtained,
    not what is done with them.
    """
    lemmas: list[str] = []
    postags: list[str] = []
    kept: list[bool] = []
    mismatched = 0
    for indice, (first, last, _da, _a) in enumerate(_batches(starts, batch_size)):
        expected = [int(starts[s + 1]) - int(starts[s]) for s in range(first, last)]
        prodotto = lotti[indice] if indice < len(lotti) else ""
        if not prodotto.strip():
            token_count = sum(expected)
            mismatched += len(expected)
            lemmas.extend([""] * token_count)
            postags.extend([""] * token_count)
            kept.extend([False] * token_count)
        else:
            batch_lemmas, batch_postags, batch_kept, batch_mismatched = \
                _read_conllu_batch(prodotto, expected)
            lemmas.extend(batch_lemmas)
            postags.extend(batch_postags)
            kept.extend(batch_kept)
            mismatched += batch_mismatched
        if progress is not None:
            progress(last, n_sentences)
    return lemmas, postags, kept, mismatched


def udpipe_nel_processo_dell_interfaccia() -> bool:
    """Does UDPipe run inside this process? Normally not, and for a reason.

    ``ufal.udpipe`` does not release the GIL: calling it here stops the
    interface thread for the whole duration of every call, model loading
    included. The normal route is the separate process.

    An explicit way out remains, ``GCP_UDPIPE_IN_PROCESS=1``, for whoever finds
    themselves in an environment where child processes cannot be launched — a
    strict antivirus, a session without permissions. It is not an automatic
    fallback: if the separate process does not start, the program says so
    instead of degrading silently, because a window that freezes for no
    apparent reason is worse than a readable error.
    """
    return os.environ.get("GCP_UDPIPE_IN_PROCESS", "").strip() in ("1", "yes", "true")


def run_udpipe_analysis(
    tokens: pd.DataFrame,
    model_path: str | Path,
    progress: ProgressCallback | None = None,
    batch_size: int = UDPIPE_SENTENCE_BATCH,
    *,
    in_processo: bool | None = None,
    annullato=None,
    fase=None,
) -> pd.DataFrame:
    """UDPipe on an already tokenised corpus, one batch of sentences at a time.

    The model is loaded and runs in a **separate process** (see
    :mod:`greek_corpus_pipeline.udpipe_processo`). The reason is measured:
    ``ufal.udpipe`` does not release the GIL, so in a thread it would block
    the interface for the whole duration of every call. The sentences, their
    order and the size of the batches do not change, and neither does the
    CoNLL-U produced: only who produces it changes.

    A sentence for which UDPipe does not reproduce the number of tokens is
    filled with empty values instead of being discarded, so that the output
    stays aligned row by row with the input.
    """
    available, message = check_udpipe_available()
    if not available:
        raise RuntimeError(message)

    _limit_threads()

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"UDPipe model not found: {path}")

    work, starts, forms = _model_input(tokens)
    if work.empty:
        raise ValueError("No non-empty token forms are available for UDPipe analysis.")
    n_sentences = len(starts) - 1

    dentro = udpipe_nel_processo_dell_interfaccia() if in_processo is None else in_processo
    if dentro:
        lotti = _lotti_qui(forms, starts, path, batch_size, n_sentences, progress)
    else:
        from .udpipe_processo import analizza_frasi

        lotti, avvisi = analizza_frasi(
            _righe_di_frase(forms, starts), path, lotto=batch_size,
            progresso=(lambda fatte, totale: progress(fatte, totale))
            if progress is not None else None,
            fase=fase, annullato=annullato)
        for avviso in avvisi:
            warnings.warn(f"UDPipe: {avviso}")
        progress = None            # the progress has already been reported by the child

    lemmas, postags, kept, mismatched = _leggi_lotti(
        lotti, starts, batch_size, n_sentences, progress)

    if mismatched:
        warnings.warn(
            f"UDPipe: {mismatched} sentence(s) out of {n_sentences} were "
            "skipped (re-segmentation or error); those tokens are blank.")

    return _assemble(work, lemmas, postags, kept, "udpipe", tokens.columns)


def _lotti_qui(forms, starts, path: Path, batch_size: int, n_sentences: int,
               progress) -> list[str]:
    """The CoNLL-U texts produced by calling UDPipe **inside this process**.

    It serves two purposes and no other: the explicit way out of
    ``GCP_UDPIPE_IN_PROCESS``, and the test that compares the two routes row by row on
    the same input.
    """
    from ufal.udpipe import Model, Pipeline, ProcessingError

    model = Model.load(str(path))
    if model is None:
        raise RuntimeError(f"UDPipe: cannot load the model from {path}")
    pipeline = Pipeline(model, "horizontal", Pipeline.DEFAULT,
                        Pipeline.DEFAULT, "conllu")

    lotti: list[str] = []
    for first, last, _da, _a in _batches(starts, batch_size):
        text = _horizontal_batch(forms, starts, first, last)
        error = ProcessingError()
        produced = pipeline.process(text, error)
        if error.occurred():
            warnings.warn(f"UDPipe: error in batch {first}-{last}: {error.message}")
            produced = ""
        lotti.append(produced)
        time.sleep(PAUSA_FRA_LOTTI)
    return lotti
