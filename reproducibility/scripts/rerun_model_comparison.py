#!/usr/bin/env python
"""Re-run the comparison with Stanza and UDPipe (Supplement S10) on the runs of Gorman and Pedalion.

The comparison is made by the two functions that the graphical interface calls in step 9
(``gui_qt.workers.run_stanza`` and ``gui_qt.workers.run_udpipe``), on the token table of a
run that ``rerun_diagnosis.py`` has written (``W/runs/rerun-gorman``, ``W/runs/rerun-pedalion``).
Each model writes into the run folder its comparison table (``stanza_comparison.parquet``,
``udpipe_comparison.parquet``) and its evaluation (``stanza_evaluation.json``,
``udpipe_evaluation.json``). Then ``recompute_model_counts.py`` recomputes from the two
tables the counts of S10.

The models are those of the study (Table S11.3). Put them in a folder M laid out as the
program lays out its own ``workspace/models``:

    M/stanza/resources.json
    M/stanza/grc/tokenize/perseus.pt
    M/stanza/grc/pos/perseus_nocharlm.pt
    M/stanza/grc/lemma/perseus_nocharlm.pt
    M/stanza/grc/pretrain/conll17.pt
    M/udpipe/ancient_greek-perseus-ud-2.4-190531.udpipe

and install the libraries (``pip install -e ".[models]"``: Stanza 1.14.0 with PyTorch, and
``ufal.udpipe`` 1.4.0.1). Before anything is run the script compares the size and the SHA-256
of each model file with Table S11.3 and says whether it is the file of the study. A file that
is absent is NOT downloaded unless you give ``--download``: the program would then fetch it
from its own sources (see ``reproducibility/ACQUISITION.md``, which says where those are and
what their licences are). A model file different from the one of the study may legitimately
give different counts.

usage:
    python rerun_model_comparison.py --workspace W --models M
    python rerun_model_comparison.py --workspace W --models M --strata gorman --only udpipe
    python rerun_model_comparison.py --workspace W --models M --download

Time: on a Linux machine with two processor cores and no graphics card the four runs took between
about one and a half and five minutes each (UDPipe: Gorman 239 s, Pedalion 101 s; Stanza: Gorman
309 s, Pedalion 128 s), about thirteen minutes in all with the check of the model files; it depends
on the machine. The logs are written to ``W/reproduction/``.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import STRATA  # noqa: F401  (puts src/ and the package root on sys.path)
from rerun_diagnosis import FILTERS

MODEL_STRATA = ("gorman", "pedalion")

#: The model files of the study, as Table S11.3 gives them: path inside M, bytes, SHA-256.
STUDY_MODEL_FILES = {
    "stanza": [
        ("stanza/resources.json", 457371,
         "4e41c1df152146fa26ed0c006a08feea7a60bb3414bb6d57dbda24ad2e3cb99c"),
        ("stanza/grc/tokenize/perseus.pt", 643313,
         "9e1cb98d39fa21dc543c1028d8d4fb6a534e2187051b15264b37498f9f06abb3"),
        ("stanza/grc/pos/perseus_nocharlm.pt", 18372328,
         "3ede3a6c272fa9219066a6089846e6ac77fcc2ecfd729348a674cc544a5092d1"),
        ("stanza/grc/lemma/perseus_nocharlm.pt", 2595726,
         "f905663df890b4bf418dfde1212ed9f6bf6b096c8d93dfc669d7b44d28449dfb"),
        ("stanza/grc/pretrain/conll17.pt", 19844392,
         "3bd32434b47d7c060036da42070f9cf2709e1e9dd315d045027bc69806317807"),
    ],
    "udpipe": [
        ("udpipe/ancient_greek-perseus-ud-2.4-190531.udpipe", 20492125,
         "b85df6199730506b33cf8aa99f5a02b63bcbaaae94f78fc4c1f5f0bdd6235505"),
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_models(models: Path, which: list[str]) -> list[str]:
    """Print the state of each model file against Table S11.3; return the missing ones."""
    missing = []
    for model in which:
        for relative, size, digest in STUDY_MODEL_FILES[model]:
            path = models / relative
            if not path.is_file():
                print(f"  MISSING    {relative}")
                missing.append(relative)
            elif path.stat().st_size != size:
                print(f"  DIFFERENT  {relative}: {path.stat().st_size:,} bytes, the study has {size:,}")
            elif sha256(path) != digest:
                print(f"  DIFFERENT  {relative}: same size, SHA-256 is not the one of Table S11.3")
            else:
                print(f"  same       {relative}  ({size:,} bytes, SHA-256 of Table S11.3)")
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, required=True,
                        help="the workspace given to rerun_diagnosis.py")
    parser.add_argument("--models", type=Path, required=True, help="the folder M described above")
    parser.add_argument("--strata", nargs="+", choices=MODEL_STRATA, default=list(MODEL_STRATA))
    parser.add_argument("--only", choices=("stanza", "udpipe"), help="run one model only")
    parser.add_argument("--download", action="store_true",
                        help="let the program download the model files that are absent")
    arguments = parser.parse_args(argv)
    which = [arguments.only] if arguments.only else ["udpipe", "stanza"]

    for stratum in arguments.strata:
        if not (arguments.workspace / "runs" / f"rerun-{stratum}" / "tokens.parquet").is_file():
            parser.error(f"no run for {stratum} in {arguments.workspace}: run rerun_diagnosis.py first")

    print("Model files against Table S11.3:")
    missing = check_models(arguments.models, which)
    if missing and not arguments.download:
        parser.error("model files are missing (see above); put them there, or give --download")

    from gui_qt import workers

    udpipe_file = arguments.models / "udpipe" / "ancient_greek-perseus-ud-2.4-190531.udpipe"
    reproduction = arguments.workspace / "reproduction"
    reproduction.mkdir(parents=True, exist_ok=True)
    for stratum in arguments.strata:
        run_id = f"rerun-{stratum}"
        for model in which:
            lines: list[str] = []
            started = time.time()
            print(f"\n{model} on {stratum} ...", flush=True)
            if model == "udpipe":
                workers.run_udpipe(arguments.workspace, run_id, str(udpipe_file), str(udpipe_file),
                                   FILTERS, lambda *a: None, lines.append)
            else:
                workers.run_stanza(arguments.workspace, run_id, str(arguments.models / "stanza"),
                                   FILTERS, lambda *a: None, lines.append)
            (reproduction / f"log-{model}-{stratum}.txt").write_text("\n".join(map(str, lines)) + "\n",
                                                                     encoding="utf-8")
            print(f"{model} on {stratum}: done in {time.time() - started:.0f} s", flush=True)
    print("\nNow run:  python recompute_model_counts.py --workspace", arguments.workspace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
