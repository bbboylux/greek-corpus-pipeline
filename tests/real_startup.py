# -*- coding: utf-8 -*-
"""Starts the real application and walks the flow from beginning to end.

It is not a pytest test: it is the equivalent of sitting in front of the program
and going through the steps. It is launched with
    QT_QPA_PLATFORM=offscreen python3 tests/real_startup.py
"""
from __future__ import annotations

import os, shutil, sys, tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
for c in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(c))

import pandas as pd
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from gui_qt.style import APP_STYLE
from tests.conftest import XML

def report(step, ok): print(f"  {'OK ' if ok else '!! '}{step}")

scratch = Path(tempfile.mkdtemp())
corpus = scratch / "xml"; corpus.mkdir()
(corpus / "test-doc.xml").write_text(XML, encoding="utf-8")
workspace = scratch / "workspace"; workspace.mkdir()

app = QApplication(sys.argv)
app.setApplicationName("Greek Corpus Pipeline")
app.setStyle("Fusion"); app.setFont(QFont("Segoe UI", 10))
app.setStyleSheet(APP_STYLE)

from gui_qt.main_window import MainWindow
window = MainWindow(workspace)
window.show()
print("\n1. The application starts")
report(f"window open, {len(window._pages)} steps in the bar", True)
report("the step «gold» is there", "gold" in window._pages)

print("\n2. I load the original corpus in AGDT XML")
from gui_qt.workers import prepare_corpus, run_detection, apply_corrections
from greek_corpus_pipeline.storage import create_run_id, run_dir, save_metadata
run_id = create_run_id("prova")
save_metadata(workspace, run_id, {"run_id": run_id, "corpus_name": "prova", "stages": {}})
prepare_corpus(workspace, run_id, "folder", str(corpus), "prova",
               lambda *a: None, lambda *a: None)
tokens = pd.read_parquet(run_dir(workspace, run_id) / "tokens.parquet")
report(f"{len(tokens)} words read", len(tokens) == 9)
original = (run_dir(workspace, run_id) / "tokens.parquet").read_bytes()

print("\n3. I find the findings")
FAMILIES = {"morphology": True, "lemma": True, "syntax": True,
            "text": True, "agreement": True}
run_detection(workspace, run_id, FAMILIES, {"exclude_placeholders": False},
              lambda *a: None, lambda *a: None)
findings = pd.read_parquet(run_dir(workspace, run_id) / "findings.parquet")
report(f"{len(findings)} findings from {findings['rule_id'].nunique()} checks", len(findings) > 0)

print("\n4. I correct two words by hand and apply")
manual = pd.DataFrame([
    {"document_id": "test-doc", "sentence_id": "1", "token_id": "5",
     "form": "στρατιῶται", "corrected_lemma": "στρατιώτης",
     "corrected_postag": "", "corrected_relation": ""},
    {"document_id": "test-doc", "sentence_id": "2", "token_id": "3",
     "form": "ἄνδρες", "corrected_lemma": "",
     "corrected_postag": "n-p---mn-", "corrected_relation": ""},
])
manual.to_csv(run_dir(workspace, run_id) / "correzioni_manuali.csv",
              index=False, encoding="utf-8-sig")
apply_corrections(workspace, run_id, set(), manual, pd.DataFrame(),
                  {"exclude_placeholders": False}, False, False,
                  lambda *a: None, lambda *a: None)
diff = pd.read_parquet(run_dir(workspace, run_id) / "token_diff.parquet")
report(f"{len(diff)} words changed", len(diff) >= 2)

print("\n5. The original corpus has remained intact")
report("tokens.parquet identical", (run_dir(workspace, run_id) / "tokens.parquet").read_bytes() == original)

print("\n6. The window reads the run again and moves to the gold")
from gui_qt.workers import RunLoader
loader = RunLoader(workspace, run_id)
collected = {}
loader.done.connect(lambda d: collected.update(d))
loader.run()                           # synchronous: we are already outside the interface
for key, value in collected.items():
    if hasattr(window.state, key): setattr(window.state, key, value)
window.state.run_id = run_id; window.state.corpus_name = "prova"
report(f"{len(collected)} entries read again from the saved run", bool(collected))
page = window._pages["gold"]; page.refresh()
report(f"changed words shown: {page._gold_state().changed_tokens}",
       page._gold_state().changed_tokens >= 2)
report("the three buttons are enabled",
       page._export_xml.isEnabled() and page._export_csv.isEnabled()
       and page._export_conllu.isEnabled())

print("\n7. I export the gold in the three formats")
from greek_corpus_pipeline.gold import (
    export_gold_xml, export_gold_csv, export_gold_conllu, save_gold_bundle,
    load_gold_bundle, model_reference_table)
corrected = window.state.corrected_tokens
out = scratch / "output"; out.mkdir()
xml_written = export_gold_xml(corrected, out / "xml")
text = Path(xml_written[0]).read_text(encoding="utf-8")
report(f"XML: {len(xml_written)} file, it contains the corrected lemma",
       'lemma="στρατιώτης"' in text and 'lemma="στρατιώτης1"' not in text)
csv_written = export_gold_csv(corrected, out / "gold.csv")
table = pd.read_csv(csv_written)
report(f"CSV: {len(table)} rows, corrected tag",
       table.loc[table["form"] == "ἄνδρες", "postag"].iloc[0] == "n-p---mn-")
conllu = export_gold_conllu(corrected, out / "gold.conllu", corpus_name="prova")
report("CoNLL-U written without the uncorrected lemma",
       "στρατιώτης1" not in Path(conllu[0]).read_text(encoding="utf-8"))

print("\n8. I save the gold, delete it, load it again")
bundle = save_gold_bundle(out / "mine", corrected, manual, diff,
                          corpus_name="prova", run_id=run_id)
(run_dir(workspace, run_id) / "corrected_tokens.parquet").unlink()
meta = load_gold_bundle(bundle, run_dir(workspace, run_id))
reloaded = pd.read_parquet(run_dir(workspace, run_id) / "corrected_tokens.parquet")
report(f"gold loaded again ({meta['changed_tokens']} words changed), lemma kept",
       reloaded.loc[reloaded["form"] == "στρατιῶται", "lemma"].iloc[0] == "στρατιώτης")

print("\n9. I compare the models against the original and against the gold")
fake = tokens[["document_id","sentence_id","token_id","form","lemma","postag"]].copy()
fake = fake.rename(columns={"lemma":"lemma_reference","postag":"postag_reference"})
fake["lemma_stanza"] = fake["lemma_reference"]; fake["postag_stanza"] = fake["postag_reference"]
fake.loc[fake["form"]=="στρατιῶται","lemma_stanza"] = "στρατιώτης"
fake.loc[fake["form"]=="ἄνδρες","postag_stanza"] = "n-p---mn-"
comparison = model_reference_table(tokens, reloaded, fake, None)
print(comparison.to_string(index=False))
report("the agreement moves when the reference changes",
       (comparison["differenza"] > 0).all())

shutil.rmtree(scratch, ignore_errors=True)
print("\nThe whole flow went through without errors.\n")
