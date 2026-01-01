#!/usr/bin/env python
"""Check the aggregate figures of the article and of the supplement against the reference tables.

Level 0: no installation, no download, no corpus. Only the Python standard library is used. The reference
tables of ``reproducibility/reference/`` hold, for the six strata of the study, the number of
findings of each of the 77 checks (``checks_overview.csv``), the units of Table S11.1, and the key of
every finding (``finding_keys/``). From them this script recomputes the figures that the article and the
supplement derive by adding up and dividing, and prints each next to the value the text states:

  * the catalogue: 77 checks, their classes, treatments and families (Table 3, S1), and the agreement
    of ``data/catalogo_controlli.csv`` with the reference table;
  * the findings per stratum and in all (Table S1.1: 160,577), by class (Tables S1.2, 5, 6 and 7), with
    the percentages and the rates per 10,000 active tokens;
  * where the checks fire (Table S1.3 = Table 8, and the sentences of § 6.5: 56, 51, 29 and 21);
  * the abstract: 101,047 and 29,515 findings, 1.9% and 4.6% of them violations;
  * the weight of the five most productive checks (89.9% and 81.8%), the two they share, and the
    shares of lemma-tool-numbering, pedalion-b-pos and common-gender-c (§ 5.1);
  * the tokens that carry findings (98,440 in Gorman; tokens with findings of more than one check),
    counted on the finding keys;
  * the concentration of the violations of the first GLAUx sample in the text 0527-012 (253 of 378);
  * the nine numerical parameters (S4, Table S4.1): the value written in the source code of the
    program, read without importing it, next to the value of the table; the six checks that use them;
  * the ten closed lists (S6, Table S6.1): the number of entries of each file of ``data/liste``, the checks
    that the file names as its readers, and the statement that all the entries are in NFC;
  * the positional scheme (Table 1 of the article; S10.3): the values that ``agdt_schema.py`` admits at each
    of the nine positions, read without importing it, next to the values of the table.

What this does and does not show. The reference tables were written from the runs of the study, so
agreement means that the text of the article and of the supplement is consistent with those runs. It
does not show that a new run gives the same findings: that is what ``rerun_diagnosis.py`` and
``compare_with_reference.py`` do.

usage:
    python check_claims_from_reference.py

The exit status is 0 when every stated figure is obtained.
"""
from __future__ import annotations

import ast
import csv
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_common import EN_CLASS, EN_FAMILY, EN_TREATMENT, PACKAGE, REFERENCE, STRATA

CLASSES = ("violation", "variant", "case_to_check")
LABEL = {"gorman": "Gorman", "pedalion": "Pedalion", "glaux_auto": "GLAUx automatic",
         "glaux_man": "GLAUx manual", "glaux_conf_auto": "GLAUx confirmation automatic",
         "glaux_conf_man": "GLAUx confirmation manual"}


#: Table S4.1: parameter -> (value, module, checks that use it).
PARAMETERS = {
    "RARE_RELATION_MIN_SUPPORT": (200, "agreement.py", ("rare-relation-for-lemma-and-pos",)),
    "RARE_RELATION_MAX_SHARE": (0.01, "agreement.py", ("rare-relation-for-lemma-and-pos",)),
    "min_form_total": (25, "lemma.py", ("lemma-rare-for-form",)),
    "max_rare": (1, "lemma.py", ("lemma-rare-for-form",)),
    "min_major_share": (0.95, "lemma.py", ("lemma-rare-for-form",)),
    "WHOLE_CORPUS_ENCODING": (0.50, "orthography.py", ("corpus-not-nfc",)),
    "INDECLINABLE_MINIMUM": (5, "postag.py", ("uninflected-lemma",)),
    "BARE_RELATION_MINIMUM": (20, "syntax.py", ("relation-bare-convention", "relation-truncated-or-foreign")),
    "BARE_RELATION_SPREAD": (0.90, "syntax.py", ("relation-bare-convention", "relation-truncated-or-foreign")),
}


#: Table S6.1: list -> (entries, the checks that read it). For a list written as groups the entries are the
#: groups (``pronomi-personali`` has 3 groups and 36 forms; ``varianti-canoniche-di-lemma`` 12 lemmas).
LISTS = {
    "enclitiche": (82, ("double-accent",)),
    "estensioni-locali-di-pos": (1, ()),
    "loci-dein-participiale": (2, ("dein-participle", "dein-participle-disputed")),
    "numerali-indeclinabili": (47, ("slot-missing", "slot-missing-bare", "uninflected-lemma", "agreement-modifier")),
    "pronomi-personali": (3, ("personal-pronoun-person",)),
    "quantificatori-non-concordanti": (4, ("agreement-modifier",)),
    "lemmi-grammaticali": (136, ()),
    "lemmi-particella": (56, ()),
    "risorse-con-metadati": (6, ()),
    "varianti-canoniche-di-lemma": (12, ("lemma-graphic-variant",)),
}


#: Table 1 of the article: position -> the values written in the table (the hyphen, which marks a position
#: that is not filled, is not listed). S10.3 adds that the program also admits c at the position of gender.
TABLE_1 = {1: ("part of speech", "navdlgcrpmiux"), 2: ("person", "123"), 3: ("number", "spd"),
           4: ("tense", "pirltfa"), 5: ("mood", "isonmp"), 6: ("voice", "apme"), 7: ("gender", "mfn"),
           8: ("case", "ngdavl"), 9: ("degree", "cs")}


def inventory(module: Path) -> dict[int, set[str]]:
    """The values that the program admits at each position (1 to 9), the hyphen left out."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "POSITION_VALUES":
            table = ast.literal_eval(node.value)
            return {position + 1: set(values) - {"-"} for position, values in table.items()}
    raise SystemExit("POSITION_VALUES is not assigned in agdt_schema.py")


def value_in_source(module: Path, name: str):
    """The value that the source file gives to a parameter, without importing the program.

    The parameter is either a constant at the top level of the module (``NAME = value``) or the
    default of an argument of a function (``def f(..., name: int = value)``). Returns ``None`` if it
    is neither, and the list of the values if the file offers more than one.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            found.append(ast.literal_eval(node.value))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional = node.args.posonlyargs + node.args.args
            for argument, default in zip(positional[len(positional) - len(node.args.defaults):], node.args.defaults):
                if argument.arg == name:
                    found.append(ast.literal_eval(default))
            for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if argument.arg == name and default is not None:
                    found.append(ast.literal_eval(default))
    return found[0] if len(found) == 1 else (found or None)


def rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def rounded(value: Decimal | float, places: int = 1) -> float:
    """Round half up, as a table written by hand would."""
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def share(part: int, whole: int, places: int = 1) -> float:
    return rounded(Decimal(100 * part) / Decimal(whole), places)


def per_10000(part: int, whole: int) -> float:
    return rounded(Decimal(10000 * part) / Decimal(whole), 1)


class Report:
    def __init__(self) -> None:
        self.compared = 0
        self.different = 0

    def group(self, title: str) -> None:
        print(f"\n== {title} ==")
        print(f"  {'where':<12} {'what':<74} {'stated':>12} {'obtained':>12}")

    def line(self, where: str, what: str, stated, obtained) -> None:
        same = (abs(float(stated) - float(obtained)) < 1e-9 if not isinstance(stated, (str, set, frozenset))
                else stated == obtained)
        self.compared += 1
        self.different += not same

        def show(value) -> str:
            if isinstance(value, (set, frozenset)):
                return ", ".join(sorted(value))
            return f"{value:,}" if isinstance(value, int) else str(value)
        print(f"  {where:<12} {what[:74]:<74} {show(stated):>12} {show(obtained):>12}"
              f"{'' if same else '   DIFFERENT'}")


def main() -> int:
    overview = rows(REFERENCE / "checks_overview.csv")
    units = {r["stratum"]: r for r in rows(REFERENCE / "table_S11_1_units_and_findings.csv")}
    catalogue = rows(PACKAGE / "data" / "catalogo_controlli.csv", delimiter=";")
    report = Report()

    by_class = {s: Counter() for s in STRATA}
    totals = Counter()
    for row in overview:
        for s in STRATA:
            by_class[s][row["class"]] += int(row[s])
            totals[s] += int(row[s])
    active = {s: int(units[s]["active_records"]) for s in STRATA}

    # ---- the catalogue
    report.group("The catalogue (S1, Table 3 of the article)")
    classes = Counter(r["class"] for r in overview)
    families = Counter(r["family"] for r in overview)
    treatments = Counter(r["treatment"] for r in overview)
    report.line("S1", "checks in the catalogue", 77, len(overview))
    report.line("S1", "checks in data/catalogo_controlli.csv", 77, len(catalogue))
    for name, stated in (("violation", 45), ("variant", 11), ("case_to_check", 21)):
        report.line("S1, Table 3", f"checks of class {name}", stated, classes[name])
    for name, stated in (("automatic", 19), ("manual", 58)):
        report.line("S1, Table 3", f"checks with treatment {name}", stated, treatments[name])
    for name, stated in (("morphology", 31), ("syntax", 20), ("text", 16), ("lemma", 6), ("agreement", 4)):
        report.line("S1", f"checks of family {name}", stated, families[name])
    cross = Counter((r["class"], r["treatment"]) for r in overview)
    for klass, automatic, manual in (("violation", 13, 32), ("variant", 6, 5), ("case_to_check", 0, 21)):
        report.line("Table 3", f"{klass}: automatic correction", automatic, cross[(klass, "automatic")])
        report.line("Table 3", f"{klass}: manual review", manual, cross[(klass, "manual")])
    in_overview = {r["rule_id"]: r for r in overview}
    differences = 0
    for entry in catalogue:
        other = in_overview.get(entry["id"])
        if other is None or (entry["name_en"], EN_FAMILY[entry["famiglia"]], EN_CLASS[entry["classe"]],
                             EN_TREATMENT[entry["trattamento"]]) != (
                other["name_en"], other["family"], other["class"], other["treatment"]):
            differences += 1
    report.line("S1", "checks on which the CSV and the reference table disagree", 0,
                differences + len(set(in_overview) - {e["id"] for e in catalogue}))

    # ---- findings
    report.group("Findings per stratum (Table S1.1) and per class (Tables S1.2, 5, 6, 7)")
    stated_total = {"gorman": 101047, "pedalion": 29515, "glaux_auto": 13168, "glaux_man": 2400,
                    "glaux_conf_auto": 11259, "glaux_conf_man": 3188}
    for s in STRATA:
        report.line("S1.1", f"findings, {LABEL[s]}", stated_total[s], totals[s])
        report.line("S11.1", f"findings, {LABEL[s]}, Table S11.1", int(units[s]["findings"]), totals[s])
    report.line("S1", "findings in all six strata", 160577, sum(totals.values()))
    s12 = {  # stratum: (violations, %, variants, %, cases to check, %)
        "gorman": (1914, 1.9, 91913, 91.0, 7220, 7.1),
        "pedalion": (1361, 4.6, 16584, 56.2, 11570, 39.2),
        "glaux_auto": (378, 2.9, 1784, 13.5, 11006, 83.6),
        "glaux_man": (41, 1.7, 1409, 58.7, 950, 39.6),
        "glaux_conf_auto": (172, 1.5, 1461, 13.0, 9626, 85.5),
        "glaux_conf_man": (15, 0.5, 2136, 67.0, 1037, 32.5),
    }
    for s, (v, vp, t, tp, c, cp) in s12.items():
        for klass, count, pct in (("violation", v, vp), ("variant", t, tp), ("case_to_check", c, cp)):
            report.line("S1.2", f"{LABEL[s]}: {klass}", count, by_class[s][klass])
            report.line("S1.2", f"{LABEL[s]}: {klass}, per cent", pct, share(by_class[s][klass], totals[s]))
    table5 = {"gorman": [(31.0, "violation"), (1490.5, "variant"), (117.1, "case_to_check")],
              "pedalion": [(49.6, "violation"), (603.9, "variant"), (421.3, "case_to_check")]}
    for s, expected in table5.items():
        for rate, klass in expected:
            report.line("Table 5", f"{LABEL[s]}: {klass} per 10,000 active tokens", rate,
                        per_10000(by_class[s][klass], active[s]))
        report.line("Table 5", f"{LABEL[s]}: all findings per 10,000 active tokens",
                    {"gorman": 1638.7, "pedalion": 1074.8}[s], per_10000(totals[s], active[s]))
        report.line("Table 5", f"{LABEL[s]}: active tokens", {"gorman": 616646, "pedalion": 274609}[s], active[s])
    table6 = {"glaux_auto": [(12.9, "violation"), (61.0, "variant"), (376.2, "case_to_check")],
              "glaux_conf_auto": [(6.4, "violation"), (54.7, "variant"), (360.1, "case_to_check")]}
    for s, expected in table6.items():
        for rate, klass in expected:
            report.line("Table 6", f"{LABEL[s]}: {klass} per 10,000 active tokens", rate,
                        per_10000(by_class[s][klass], active[s]))
        report.line("Table 6", f"{LABEL[s]}: all findings per 10,000 active tokens",
                    {"glaux_auto": 450.1, "glaux_conf_auto": 421.2}[s], per_10000(totals[s], active[s]))
    table7 = {"gorman": (616646, 31.0), "pedalion": (274609, 49.6), "glaux_auto": (292567, 12.9),
              "glaux_man": (21107, 19.4), "glaux_conf_auto": (267313, 6.4), "glaux_conf_man": (28143, 5.3)}
    for s, (tokens, rate) in table7.items():
        report.line("Table 7", f"{LABEL[s]}: active tokens", tokens, active[s])
        report.line("Table 7", f"{LABEL[s]}: violations per 10,000 active tokens", rate,
                    per_10000(by_class[s]["violation"], active[s]))

    # ---- where the checks fire
    report.group("Where the checks fire (Table S1.3 = Table 8, § 6.5, abstract)")
    fires = {s: {r["rule_id"] for r in overview if int(r[s]) > 0} for s in STRATA}
    glaux = set().union(*(fires[s] for s in STRATA[2:]))
    for s in STRATA:
        report.line("S11.1", f"checks that fire in {LABEL[s]}", int(units[s]["active_checks"]), len(fires[s]))
    report.line("§ 6.5", "checks that fire in Gorman", 56, len(fires["gorman"]))
    report.line("§ 6.5", "checks that fire in Pedalion", 51, len(fires["pedalion"]))
    report.line("§ 6.5", "checks that fire in at least one stratum of GLAUx", 29, len(glaux))
    distribution = Counter()
    for r in overview:
        g, p, x = r["rule_id"] in fires["gorman"], r["rule_id"] in fires["pedalion"], r["rule_id"] in glaux
        place = ("Gorman, Pedalion and GLAUx" if g and p and x else
                 "only Gorman and/or Pedalion" if (g or p) and not x else
                 "GLAUx and only one of the two" if x and (g or p) else
                 "only GLAUx" if x else "no corpus")
        distribution[(place, r["class"])] += 1
    s13 = [("Gorman, Pedalion and GLAUx", 6, 3, 12), ("only Gorman and/or Pedalion", 33, 6, 5),
           ("GLAUx and only one of the two", 3, 1, 2), ("only GLAUx", 0, 1, 1), ("no corpus", 3, 0, 1)]
    for place, v, t, c in s13:
        for klass, stated in (("violation", v), ("variant", t), ("case_to_check", c)):
            report.line("Table S1.3", f"{place}: {klass}", stated, distribution[(place, klass)])
        report.line("Table S1.3", f"{place}: total", v + t + c, sum(distribution[(place, k)] for k in CLASSES))
    report.line("abstract", "checks that fire in all three treebanks", 21,
                sum(distribution[("Gorman, Pedalion and GLAUx", k)] for k in CLASSES))
    silent = {r["rule_id"] for r in overview if all(int(r[s]) == 0 for s in STRATA)}
    report.line("S1", "checks with no finding in any stratum (names)",
                {"beta-code-form", "invisible-char-form", "invisible-char-lemma", "nonlexical-z-pos"}, silent)

    # ---- the abstract and § 5.1
    report.group("The abstract and § 5.1 of the article")
    report.line("abstract", "findings in Gorman", 101047, totals["gorman"])
    report.line("abstract", "findings in Pedalion", 29515, totals["pedalion"])
    report.line("abstract", "per cent of them that are violations, Gorman", 1.9,
                share(by_class["gorman"]["violation"], totals["gorman"]))
    report.line("abstract", "per cent of them that are violations, Pedalion", 4.6,
                share(by_class["pedalion"]["violation"], totals["pedalion"]))
    top = {s: sorted(overview, key=lambda r: -int(r[s]))[:5] for s in ("gorman", "pedalion")}
    report.line("§ 5.1", "five most productive checks: share of the findings, Gorman", 89.9,
                share(sum(int(r["gorman"]) for r in top["gorman"]), totals["gorman"]))
    report.line("§ 5.1", "five most productive checks: share of the findings, Pedalion", 81.8,
                share(sum(int(r["pedalion"]) for r in top["pedalion"]), totals["pedalion"]))
    report.line("§ 5.1", "checks among the five of both corpora (names)",
                {"apostrophe-mixed", "rare-relation-for-lemma-and-pos"},
                {r["rule_id"] for r in top["gorman"]} & {r["rule_id"] for r in top["pedalion"]})
    gorman_numbering = int(in_overview["lemma-tool-numbering"]["gorman"])
    report.line("§ 5.1", "lemma-tool-numbering: findings in Gorman", 72836, gorman_numbering)
    report.line("§ 5.1", "  per cent of all the findings of Gorman", 72.1, share(gorman_numbering, totals["gorman"]))
    report.line("§ 5.1", "  per cent of the systematic variants of Gorman", 79.2,
                share(gorman_numbering, by_class["gorman"]["variant"]))
    pedalion_b = int(in_overview["pedalion-b-pos"]["pedalion"])
    pedalion_c = int(in_overview["common-gender-c"]["pedalion"])
    report.line("§ 5.1", "pedalion-b-pos: findings in Pedalion", 8555, pedalion_b)
    report.line("§ 5.1", "  per cent of all the findings of Pedalion", 29.0, share(pedalion_b, totals["pedalion"]))
    report.line("§ 5.1", "  per cent of the systematic variants of Pedalion", 51.6,
                share(pedalion_b, by_class["pedalion"]["variant"]))
    report.line("§ 5.1", "common-gender-c: findings in Pedalion", 8256, pedalion_c)
    report.line("§ 5.1", "  per cent of all the findings of Pedalion", 28.0, share(pedalion_c, totals["pedalion"]))
    report.line("§ 5.1", "  per cent of the cases to check of Pedalion", 71.4,
                share(pedalion_c, by_class["pedalion"]["case_to_check"]))
    report.line("§ 6", "imported tokens of the four strata of GLAUx", 623964,
                sum(int(units[s]["imported_records"]) for s in STRATA[2:]))

    # ---- the finding keys
    report.group("Counted on the keys of the findings (document, sentence, token identifier)")
    keys: dict[str, list[tuple[str, ...]]] = {}
    for s in STRATA:
        with gzip.open(REFERENCE / "finding_keys" / f"{s}.csv.gz", "rt", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            next(reader)
            keys[s] = [tuple(row) for row in reader]
    report.line("§ 5.1", "Gorman: distinct tokens that carry a finding", 98440,
                len({(d, sn, t) for _, d, sn, t in keys["gorman"]}))
    per_token = {s: Counter((d, sn, t) for rid, d, sn, t in set(keys[s])) for s in ("gorman", "pedalion")}
    report.line("§ 5.1", "Gorman: tokens that carry findings of more than one check", 2474,
                sum(1 for n in per_token["gorman"].values() if n > 1))
    report.line("§ 5.1", "Pedalion: tokens that carry findings of more than one check", 1684,
                sum(1 for n in per_token["pedalion"].values() if n > 1))
    pedalion_distinct = len({(d, sn, t) for _, d, sn, t in keys["pedalion"]})
    print(f"  (information) Pedalion: distinct (document, sentence, token identifier) triples: "
          f"{pedalion_distinct:,}. The text states 27,709 tokens, counted by position in the file; the\n"
          f"  keys cannot tell apart two tokens of one sentence that share an XML identifier (S11.3: "
          f"seven sentences, 17 findings),\n  so a smaller number here is expected. The figure of the "
          f"text is recomputed on a run by recompute_case_studies.py.")
    violations = [k for k in keys["glaux_auto"] if in_overview[k[0]]["class"] == "violation"]
    by_document = Counter(d for _, d, _, _ in violations)
    top_document, top_count = by_document.most_common(1)[0]
    report.line("§ 6.4", "GLAUx, first sample: violations", 378, len(violations))
    report.line("§ 6.4", "  violations that come from one text (the text is 0527-012)", 253, top_count)
    report.line("§ 6.4", "  the text", "0527-012", top_document)
    report.line("§ 6.4", "  of them, from the check slot-missing", 253,
                sum(1 for rid, d, _, _ in violations if d == "0527-012" and rid == "slot-missing"))
    report.line("§ 6.4", "  violations per 10,000 active tokens without that text (20,238 tokens)", 4.6,
                per_10000(378 - 253, active["glaux_auto"] - 20238))
    for stratum, stated_findings, stated_documents in (("glaux_auto", 2239, 18), ("glaux_conf_auto", 1782, 17)):
        found = [k for k in keys[stratum] if k[0] == "relation-bare-convention"]
        report.line("§ 6.3, S7.7", f"relation-bare-convention, {LABEL[stratum]}: findings", stated_findings, len(found))
        report.line("§ 6.3, S7.7", f"  documents in which they occur", stated_documents, len({d for _, d, _, _ in found}))

    # ---- the nine parameters
    report.group("The nine numerical parameters (S4, Table S4.1; § 4.3 of the article)")
    source = PACKAGE / "src" / "greek_corpus_pipeline"
    for name, (stated, module, _) in PARAMETERS.items():
        found = value_in_source(source / module, name)
        report.line("Table S4.1", f"{name} in {module}", stated, found if isinstance(found, (int, float)) else float("nan"))
    served = Counter(check for _, _, checks in PARAMETERS.values() for check in checks)
    report.line("S4", "numerical parameters", 9, len(PARAMETERS))
    report.line("S4", "checks that use them", 6, len(served))
    for check, stated in (("lemma-rare-for-form", 3), ("rare-relation-for-lemma-and-pos", 2),
                          ("relation-bare-convention", 2), ("relation-truncated-or-foreign", 2),
                          ("corpus-not-nfc", 1), ("uninflected-lemma", 1)):
        report.line("S4", f"parameters of {check}", stated, served[check])
    report.line("S4", "checks of Table S4.1 that are in the catalogue", len(served),
                len(set(served) & set(in_overview)))

    # ---- the ten closed lists
    report.group("The ten closed lists (S6, Table S6.1)")
    resources = {}
    for path in sorted((PACKAGE / "data" / "liste").glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            resource = json.load(handle)
        resources[resource["id"]] = resource
    report.line("S6", "closed lists distributed with the program", 10, len(resources))
    rule_ids = {row["rule_id"] for row in overview}
    for name, (stated_entries, stated_readers) in LISTS.items():
        resource = resources[name]
        report.line("Table S6.1", f"entries of {name}", stated_entries, len(resource["voci"]))
        named = {w for w in re.findall(r"[a-z0-9-]+", " ".join(resource["usata_da"])) if w in rule_ids}
        if name == "estensioni-locali-di-pos":
            # the file names pedalion-b-pos only to say that the value b is written in its code
            named -= {"pedalion-b-pos"}
        report.line("Table S6.1", f"checks that read {name}", set(stated_readers) or {"none"}, named or {"none"})
    report.line("Table S6.1", "forms of pronomi-personali (3 groups)", 36,
                sum(len(forms) for forms in resources["pronomi-personali"]["voci"].values()))
    report.line("S6", "lists read by diagnostic checks", 6, sum(1 for _, readers in LISTS.values() if readers))

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    report.line("S6", "entries of the lists that are not in NFC", 0,
                sum(1 for r in resources.values() for text in strings(r["voci"])
                    if unicodedata.normalize("NFC", text) != text))

    # ---- the positional scheme
    report.group("The positional scheme (Table 1 of the article; S10.3)")
    admitted = inventory(source / "agdt_schema.py")
    for position, (feature, values) in TABLE_1.items():
        extra = "c" if position == 7 else ""
        report.line("Table 1", f"position {position}, {feature}: values admitted by the program"
                    + (" (Table 1 and c, S10.3)" if extra else ""),
                    "".join(sorted(values + extra)), "".join(sorted(admitted[position])))
    report.line("Table 1", "positions of the tag", 9, len(admitted))

    print(f"\nRESULT: {report.compared} figures compared, "
          + ("all obtained" if not report.different else f"{report.different} not obtained"))
    return 0 if not report.different else 1


if __name__ == "__main__":
    sys.exit(main())
