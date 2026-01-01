# -*- coding: utf-8 -*-
"""Regenerates data/catalogo_controlli.csv from the catalogue.

The CSV is a view, not a source: it is regenerated, not edited by hand. If it
were maintained by hand it could state a number of checks different from the one
the program runs, which is the reason why this script exists.

    python tools_regenerate_catalogue.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from greek_corpus_pipeline.rule_catalog import RULE_CATALOG  # noqa: E402

DESTINAZIONE = Path(__file__).parent / "data" / "catalogo_controlli.csv"
COLONNE = ["id", "nome", "name_en", "famiglia", "classe", "trattamento",
           "gravita", "correzione_automatica_predefinita",
           "descrizione", "description_en"]


def righe():
    for identificatore in sorted(RULE_CATALOG):
        regola = RULE_CATALOG[identificatore]
        yield {
            "id": identificatore,
            "nome": regola["name"],
            "name_en": regola["name_en"],
            "famiglia": regola["family"],
            "classe": regola["class"],
            "trattamento": regola["treatment"],
            "gravita": regola["severity"],
            "correzione_automatica_predefinita":
                "sì" if regola["default_auto_apply"] else "no",
            "descrizione": regola["description"],
            "description_en": regola["description_en"],
        }


def main() -> int:
    with DESTINAZIONE.open("w", encoding="utf-8-sig", newline="") as uscita:
        scrittore = csv.DictWriter(uscita, fieldnames=COLONNE, delimiter=";",
                                   quoting=csv.QUOTE_MINIMAL)
        scrittore.writeheader()
        for riga in righe():
            scrittore.writerow(riga)
    print(f"{DESTINAZIONE.name}: {len(RULE_CATALOG)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
