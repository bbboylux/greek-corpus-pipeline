# -*- coding: utf-8 -*-
"""The script that recomputes the counting units and the figures of S11.1
(``reproducibility/scripts/recompute_units.py``).

S11.1 states, for Pedalion, that 28 analysable sentences have tokens whose chain of heads does not reach the
root, that in nine of them the chain contains a cycle, and that in eight it does so when the technical tokens
are left out. The script computes the two cycle counts; this module makes sure that it also *verifies* both
against the stated values (a number that is only printed is not a check), and that the function that follows
the chains tells a cycle from a chain that ends nowhere, with and without the technical records.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducibility" / "scripts" / "recompute_units.py"

# pandas 2.2.0 (the lowest version the package admits) warns, when it reads a parquet file written with pyarrow 14, about a
# call that pyarrow itself makes ("Passing a BlockManager to DataFrame is deprecated"): it is the libraries' business, not
# the program's, and later versions of pandas do not say it. Only that message is ignored.
pytestmark = pytest.mark.filterwarnings("ignore:Passing a BlockManager to DataFrame:DeprecationWarning")

ALL = "analysable sentences with a cycle among all the records"
ACTIVE = "analysable sentences with a cycle among the active records"
NO_ROOT = "analysable sentences with a chain that reaches no head 0"


@pytest.fixture(scope="module")
def tool():
    pytest.importorskip("pyarrow")
    spec = importlib.util.spec_from_file_location("recompute_units_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def word(sentence: str, token_id: int, head: int, *, artificial: str = "", form: str = "λόγος") -> dict:
    return dict(source_file=f"{sentence}.xml", document_id=sentence, sentence_index=1, sentence_id="1",
                token_id=token_id, head=head, form=form, lemma="λόγος", postag="n-s---mn-",
                relation="SBJ" if head else "PRED", artificial=artificial)


def corpus() -> pd.DataFrame:
    """Four sentences, each with a single root and with every head present in the sentence (so all analysable)."""
    rows = [
        # alfa: two active words that depend on each other: a cycle, with or without the technical records
        word("alfa", 1, 0), word("alfa", 2, 3), word("alfa", 3, 2),
        # beta: the cycle passes through a technical record: a cycle among all the records; once that record is
        # left out, the chain of the word that depended on it ends nowhere and there is no cycle
        word("beta", 1, 0), word("beta", 2, 3), word("beta", 3, 2, artificial="elliptic", form="ἐστιν"),
        # gamma: a sound tree
        word("gamma", 1, 0), word("gamma", 2, 1), word("gamma", 3, 1),
        # delta: a word that is its own head (a cycle of one)
        word("delta", 1, 0), word("delta", 2, 2),
    ]
    return pd.DataFrame(rows)


# -- the function that follows the chains ----------------------------------------------------------------

def test_a_cycle_is_told_from_a_chain_that_ends_nowhere_with_and_without_the_technical_records(tool):
    tokens = corpus()
    analysable = tool.U.analyzable_sentence_keys(tokens)
    assert len(analysable) == 4
    # all the records: alfa, beta and delta have a cycle; gamma has none
    assert tool.chains(tokens, analysable, False) == (3, 3)
    # the technical record of beta is not in the graph: its dependant's chain ends nowhere, which is not a cycle
    assert tool.chains(tokens, analysable, True) == (3, 2)


# -- the stated values -------------------------------------------------------------------------------------

def test_the_two_cycle_counts_of_pedalion_and_the_chains_are_stated_values(tool):
    """S11.1: 28 chains that reach no root in Pedalion and 16 in Gorman; nine cycles, eight without the technical tokens."""
    pedalion, gorman = tool.STATED["pedalion"], tool.STATED["gorman"]
    assert pedalion[NO_ROOT] == 28 and gorman[NO_ROOT] == 16
    assert pedalion[ALL] == 9
    assert pedalion[ACTIVE] == 8


def reproduced(tool, tmp_path, capsys, monkeypatch, **changes) -> tuple[int, str]:
    """Run the script on a folder that the script takes for the Pedalion run, with the measures that it states."""
    folder = tmp_path / "rerun-pedalion"
    folder.mkdir(exist_ok=True)
    measured = dict(tool.STATED["pedalion"], **changes)
    monkeypatch.setattr(tool, "measure", lambda run: measured)
    status = tool.main([str(folder)])
    return status, capsys.readouterr().out


def test_the_stated_values_are_reproduced_when_all_of_them_are(tool, tmp_path, capsys, monkeypatch):
    status, out = reproduced(tool, tmp_path, capsys, monkeypatch)
    assert status == 0, out
    assert "RESULT: every stated value is reproduced" in out
    assert "DIFFERENT" not in out
    cycle_line = next(line for line in out.splitlines() if ALL in line)
    assert cycle_line.split()[-2:] == ["9", "same"]


@pytest.mark.parametrize("name, wrong", [(ALL, 10), (ALL, 8), (ACTIVE, 9), (ACTIVE, 7), (NO_ROOT, 27)])
def test_a_cycle_count_that_is_not_the_stated_one_is_a_difference(tool, tmp_path, capsys, monkeypatch, name, wrong):
    """The nine on all the records is checked, not only printed: a different number is a difference."""
    status, out = reproduced(tool, tmp_path, capsys, monkeypatch, **{name: wrong})
    assert status == 1, out
    assert "RESULT: some stated value is not reproduced" in out
    line = next(line for line in out.splitlines() if name in line)
    assert line.rstrip().endswith("DIFFERENT")


# -- the measure on a run folder ------------------------------------------------------------------------

def test_the_measures_of_a_run_folder_give_both_cycle_counts(tool, tmp_path):
    folder = tmp_path / "rerun-gamma"
    folder.mkdir()
    corpus().to_parquet(folder / "tokens.parquet")
    result = tool.measure(folder)
    assert result[ALL] == 3
    assert result[ACTIVE] == 2
    assert result[NO_ROOT] == 3
