"""backend/scripts/evaluate_foodplan.py

Dieses Skript bewertet einen (angereicherten) Speiseplan gegen ein Regel-Set.

Eingaben:
- `foodplan.enriched.json` (Enrichment bedeutet: Items haben `links.food_group` und/oder `tags`)
- `rules/dge_lunch_rules.json` (Regeln im JSON-Format)

Wichtiges Konzept: "dual" Plan
- Der Plan enthält pro Tag mehrere Menüs.
- `menu.menu_type` kennzeichnet, zu welcher "Linie" das Menü gehört:
  - "mischkost"     -> Diet "mixed"
  - "vegetarisch"   -> Diet "ovo_lacto_vegetarian"
  - "dessert"       -> Diet "shared" (zählt für beide)

Output:
- Für jede Diet wird ein Report erzeugt:
  - Summary (Score, passed/applicable)
  - Counts (food_groups, tags)
  - Regeln inkl. erwarteter/ist-Wert und Evidence-Samples

CLI Nutzung (Beispiel):
  python3 backend/scripts/evaluate_foodplan.py \
    --plan backend/instance/testdata/foodplan.enriched.json \
    --rules backend/rules/dge_lunch_rules.json \
    --out backend/instance/testdata/report.dual.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


# -----------------------------
# Helpers: JSON lesen/schreiben
# -----------------------------

def load_json(path: Path) -> dict:
    """Liest JSON von `path` und gibt ein Python-dict zurück."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    """Schreibt `data` als pretty JSON nach `path` (Ordner wird ggf. erzeugt)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -----------------------------
# Mapping: menu_type -> diet
# -----------------------------

def diet_from_menu_type(menu_type: str) -> str:
    """Mappt die menu_type-Bezeichnung aus dem Plan auf unsere Diet-Keys.

    - "mischkost"     -> "mixed"
    - "vegetarisch"   -> "ovo_lacto_vegetarian"
    - "dessert"       -> "shared" (Sonderfall)

    Alles Unbekannte behandeln wir ebenfalls als "shared",
    damit diese Items nicht komplett aus der Auswertung fallen.
    """

    mt = (menu_type or "").strip().lower()

    if mt == "mischkost":
        return "mixed"
    if mt == "vegetarisch":
        return "ovo_lacto_vegetarian"
    if mt == "dessert":
        return "shared"

    return "shared"


def menu_included_for_diet(menu_type: str, selected_diet: str) -> bool:
    """Entscheidet, ob ein Menü für die gewählte Diet ausgewertet werden soll."""

    d = diet_from_menu_type(menu_type)

    # Shared (z.B. dessert) zählt immer für beide Reports.
    if d == "shared":
        return True

    # Sonst: nur Menüs der gewählten Linie zählen.
    return d == selected_diet


# -----------------------------
# Iteration über Items im Plan
# -----------------------------

def iter_items(plan: dict):
    """Generator über alle Items im Plan.

    Liefert Tupel:
      (weekday, menu_type, item)

    Dabei wird keine Diet gefiltert (das passiert später).
    """

    for day in plan.get("days", []) or []:
        weekday = day.get("weekday")
        for menu in day.get("menus", []) or []:
            menu_type = menu.get("menu_type")  # "mischkost" | "vegetarisch" | "dessert"
            for item in menu.get("items", []) or []:
                yield weekday, menu_type, item


# -----------------------------
# Counts + Evidence sammeln
# -----------------------------

def collect_counts_and_evidence(plan: dict, selected_diet: str) -> Tuple[
    Dict[str, int], Dict[str, int], Dict[str, List[dict]], Dict[str, List[dict]]
]:
    """Aggregiert Counts und Evidence für eine Diet.

    Counts:
    - `group_counts[group]`: wie oft kam `links.food_group == group` vor?
    - `tag_counts[tag]`:     wie oft kam ein Tag in `item.tags` vor?

    Evidence:
    - Für Debug/Erklärbarkeit sammeln wir Beispiel-Items (abgeschnitten auf später max. 10).
      - evidence_groups[group] -> [{weekday, menu_type, raw_text}, ...]
      - evidence_tags[tag]     -> [{weekday, menu_type, raw_text}, ...]
    """

    group_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    evidence_groups: Dict[str, List[dict]] = {}
    evidence_tags: Dict[str, List[dict]] = {}

    for weekday, menu_type, item in iter_items(plan):
        # Diet-Filter: zähle nur Menüs, die zur Diet gehören
        if not menu_included_for_diet(menu_type, selected_diet):
            continue

        # raw_text ist ein "Beleg" für den Nutzer (welches Gericht/Item war das?)
        raw_text = item.get("raw_text")

        # Enrichment-Links (z.B. food_group, später evtl. Food-IDs)
        links = item.get("links") or {}
        group = links.get("food_group")

        # --- food_group zählen --------------------------------------------------
        if group:
            group_counts[group] = group_counts.get(group, 0) + 1
            evidence_groups.setdefault(group, []).append(
                {"weekday": weekday, "menu_type": menu_type, "raw_text": raw_text}
            )

        # --- tags zählen --------------------------------------------------------
        tags = item.get("tags") or []
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
            evidence_tags.setdefault(t, []).append(
                {"weekday": weekday, "menu_type": menu_type, "raw_text": raw_text}
            )

    return group_counts, tag_counts, evidence_groups, evidence_tags


# -----------------------------
# Regeln: gilt die Regel?
# -----------------------------

def rule_applies(rule: dict, selected_diet: str) -> bool:
    """Prüft, ob eine Regel für die ausgewählte Diet gilt.

    rule.diet:
      - "all": gilt immer
      - "mixed": nur im mixed report
      - "ovo_lacto_vegetarian": nur im veggie report
    """

    d = rule.get("diet", "all")
    if d == "all":
        return True
    return d == selected_diet


def evaluate_operator(actual: int, operator: str, threshold: int) -> bool:
    """Wendet den Operator einer Regel an (min/max/equals)."""

    if operator == "min":
        return actual >= threshold
    if operator == "max":
        return actual <= threshold
    if operator == "equals":
        return actual == threshold
    raise ValueError(f"Unsupported operator: {operator}")


def as_list(value):
    """Normalisiert `value` zu einer Liste.

    In rules.json kann target.value entweder ein String oder eine Liste sein.
    """

    return value if isinstance(value, list) else [value]


def build_rule_result(
    rule: dict,
    selected_diet: str,
    group_counts: dict,
    tag_counts: dict,
    evidence_groups: dict,
    evidence_tags: dict,
) -> dict:
    """Berechnet das Ergebnis einer einzelnen Regel.

    Steps:
    - target lesen (count_by + values)
    - Ist-Wert (actual) durch Summieren der Counts bestimmen
    - passed = Operator(actual, threshold)
    - expected als Text ("mind.", "max.", "genau") für die UI erzeugen
    - eine Evidence-Sample-Liste anhängen (für Debug/Erklärbarkeit)
    """

    target = rule.get("target") or {}
    count_by = target.get("count_by")  # "food_group" oder "tag"
    value = target.get("value")
    values = as_list(value)

    operator = rule.get("operator")
    threshold = int(rule.get("threshold", 0))

    actual = 0
    evidence: List[dict] = []

    if count_by == "food_group":
        for v in values:
            actual += int(group_counts.get(v, 0))
            evidence.extend((evidence_groups.get(v) or [])[:10])
    elif count_by == "tag":
        for v in values:
            actual += int(tag_counts.get(v, 0))
            evidence.extend((evidence_tags.get(v) or [])[:10])
    else:
        raise ValueError(f"Unsupported target.count_by: {count_by}")

    passed = evaluate_operator(actual, operator, threshold)

    # expected als menschenlesbarer Text
    if operator == "min":
        expected_text = f"mind. {threshold}"
    elif operator == "max":
        expected_text = f"max. {threshold}"
    elif operator == "equals":
        expected_text = f"genau {threshold}"
    else:
        expected_text = f"{operator} {threshold}"

    return {
        "id": rule.get("id"),
        "label": rule.get("label"),
        "diet": rule.get("diet"),
        "applies": rule_applies(rule, selected_diet),
        "target": target,
        "operator": operator,
        "threshold": threshold,
        "expected": expected_text,
        "actual": actual,
        "passed": passed,
        "notes": rule.get("notes"),
        "evidence_sample": evidence[:10],
    }


def evaluate_plan_for_diet(plan: dict, rules_doc: dict, selected_diet: str) -> dict:
    """Erzeugt den Report für eine Diet (mixed oder ovo_lacto_vegetarian)."""

    group_counts, tag_counts, evidence_groups, evidence_tags = collect_counts_and_evidence(
        plan, selected_diet
    )

    rule_results: List[dict] = []
    applicable = 0
    passed = 0

    # Regeln durchlaufen und nacheinander bewerten
    for rule in rules_doc.get("rules", []) or []:
        res = build_rule_result(
            rule, selected_diet, group_counts, tag_counts, evidence_groups, evidence_tags
        )

        # Score nur aus Regeln berechnen, die für diese Diet gelten
        if res["applies"]:
            applicable += 1
            if res["passed"]:
                passed += 1

        rule_results.append(res)

    # Score ist Anteil bestandener Regeln (0..1)
    score = round(passed / applicable, 3) if applicable else 0.0

    return {
        "schema_version": "1.0",
        "diet": selected_diet,
        "scope": rules_doc.get("scope"),
        "summary": {
            "applicable_rules": applicable,
            "passed_rules": passed,
            "score": score,
        },
        "counts": {"food_groups": group_counts, "tags": tag_counts},
        "rules": rule_results,
    }


def main():
    """CLI Entry-Point: Einlesen -> Evaluieren -> Report speichern."""

    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="Pfad zu foodplan.enriched.json")
    ap.add_argument("--rules", required=True, help="Pfad zu dge_lunch_rules.json")
    ap.add_argument("--out", required=True, help="Pfad für report.dual.json")
    args = ap.parse_args()

    # Eingaben lesen
    plan = load_json(Path(args.plan))
    rules_doc = load_json(Path(args.rules))

    # Dual-Report: 2 Diets auswerten
    report = {
        "schema_version": "1.0",
        "mode": "dual",
        "mixed": evaluate_plan_for_diet(plan, rules_doc, "mixed"),
        "ovo_lacto_vegetarian": evaluate_plan_for_diet(
            plan, rules_doc, "ovo_lacto_vegetarian"
        ),
    }

    # Report speichern
    save_json(Path(args.out), report)

    # Kurzusammenfassung auf stdout (praktisch für CLI)
    m = report["mixed"]["summary"]
    v = report["ovo_lacto_vegetarian"]["summary"]
    print("Evaluation fertig!")
    print(f"Mixed: {m['passed_rules']}/{m['applicable_rules']} = {m['score']}")
    print(f"Veg:   {v['passed_rules']}/{v['applicable_rules']} = {v['score']}")
    print(f"Out:   {args.out}")


if __name__ == "__main__":
    main()
