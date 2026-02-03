# backend/scripts/evaluate_foodplan.py
# ------------------------------------------------------------
# Zweck:
#   - foodplan.enriched.json einlesen
#   - dge_lunch_rules.json einlesen
#   - Plan wird als "dual" interpretiert:
#       menus[].menu_type ist eine Linie: "mischkost" | "vegetarisch" | "dessert"
#   - Wir werten immer beide Linien aus:
#       - Mischkost-Report (mixed)
#       - Veggie-Report (ovo_lacto_vegetarian)
#
# Wichtige Annahme:
#   - "dessert" zählt für beide Linien (shared).
#
# Nutzung:
#   python3 scripts/evaluate_foodplan.py \
#     --plan instance/testdata/foodplan.enriched.json \
#     --rules rules/dge_lunch_rules.json \
#     --out instance/testdata/report.dual.json
# ------------------------------------------------------------

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


# -----------------------------
# Helpers: JSON lesen/schreiben
# -----------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -----------------------------
# Mapping: menu_type -> diet
# -----------------------------

def diet_from_menu_type(menu_type: str) -> str:
    """
    In deinem Plan ist menu_type eine Linien-Kennung:
      - "mischkost" -> mixed
      - "vegetarisch" -> ovo_lacto_vegetarian
      - "dessert" -> shared (Sonderfall)
    """
    mt = (menu_type or "").strip().lower()

    if mt == "mischkost":
        return "mixed"
    if mt == "vegetarisch":
        return "ovo_lacto_vegetarian"
    if mt == "dessert":
        return "shared"

    # Falls später neue Bezeichnungen auftauchen:
    # wir behandeln unbekannt erstmal wie "shared", damit nichts komplett verloren geht.
    return "shared"


def menu_included_for_diet(menu_type: str, selected_diet: str) -> bool:
    """
    Filter:
      - Für mixed:   nimm "mischkost" + "dessert/shared"
      - Für veg:     nimm "vegetarisch" + "dessert/shared"
    """
    d = diet_from_menu_type(menu_type)

    if d == "shared":
        return True

    return d == selected_diet


# -----------------------------
# Iteration über Items im Plan
# -----------------------------

def iter_items(plan: dict):
    """
    Generator über alle Items:
      yield (weekday, menu_type, item)
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
    """
    Zählt pro Diet:
      - food_group counts
      - tag counts

    Evidence:
      - evidence_groups[group] -> [{weekday, menu_type, raw_text}]
      - evidence_tags[tag]     -> [{weekday, menu_type, raw_text}]
    """
    group_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    evidence_groups: Dict[str, List[dict]] = {}
    evidence_tags: Dict[str, List[dict]] = {}

    for weekday, menu_type, item in iter_items(plan):
        if not menu_included_for_diet(menu_type, selected_diet):
            continue

        raw_text = item.get("raw_text")
        links = item.get("links") or {}
        group = links.get("food_group")

        if group:
            group_counts[group] = group_counts.get(group, 0) + 1
            evidence_groups.setdefault(group, []).append({
                "weekday": weekday,
                "menu_type": menu_type,
                "raw_text": raw_text
            })

        tags = item.get("tags") or []
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
            evidence_tags.setdefault(t, []).append({
                "weekday": weekday,
                "menu_type": menu_type,
                "raw_text": raw_text
            })

    return group_counts, tag_counts, evidence_groups, evidence_tags


# -----------------------------
# Regeln: gilt die Regel?
# -----------------------------

def rule_applies(rule: dict, selected_diet: str) -> bool:
    """
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
    if operator == "min":
        return actual >= threshold
    if operator == "max":
        return actual <= threshold
    if operator == "equals":
        return actual == threshold
    raise ValueError(f"Unsupported operator: {operator}")


def as_list(value):
    return value if isinstance(value, list) else [value]


def build_rule_result(
    rule: dict,
    selected_diet: str,
    group_counts: dict,
    tag_counts: dict,
    evidence_groups: dict,
    evidence_tags: dict
) -> dict:
    target = rule.get("target") or {}
    count_by = target.get("count_by")
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
        "evidence_sample": evidence[:10]
    }


def evaluate_plan_for_diet(plan: dict, rules_doc: dict, selected_diet: str) -> dict:
    group_counts, tag_counts, evidence_groups, evidence_tags = collect_counts_and_evidence(plan, selected_diet)

    rule_results: List[dict] = []
    applicable = 0
    passed = 0

    for rule in rules_doc.get("rules", []) or []:
        res = build_rule_result(rule, selected_diet, group_counts, tag_counts, evidence_groups, evidence_tags)

        if res["applies"]:
            applicable += 1
            if res["passed"]:
                passed += 1

        rule_results.append(res)

    score = round(passed / applicable, 3) if applicable else 0.0

    return {
        "schema_version": "1.0",
        "diet": selected_diet,
        "scope": rules_doc.get("scope"),
        "summary": {
            "applicable_rules": applicable,
            "passed_rules": passed,
            "score": score
        },
        "counts": {
            "food_groups": group_counts,
            "tags": tag_counts
        },
        "rules": rule_results
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="Pfad zu foodplan.enriched.json")
    ap.add_argument("--rules", required=True, help="Pfad zu dge_lunch_rules.json")
    ap.add_argument("--out", required=True, help="Pfad für report.dual.json")
    args = ap.parse_args()

    plan = load_json(Path(args.plan))
    rules_doc = load_json(Path(args.rules))

    report = {
        "schema_version": "1.0",
        "mode": "dual",
        "mixed": evaluate_plan_for_diet(plan, rules_doc, "mixed"),
        "ovo_lacto_vegetarian": evaluate_plan_for_diet(plan, rules_doc, "ovo_lacto_vegetarian"),
    }

    save_json(Path(args.out), report)

    m = report["mixed"]["summary"]
    v = report["ovo_lacto_vegetarian"]["summary"]
    print("Evaluation fertig!")
    print(f"Mixed: {m['passed_rules']}/{m['applicable_rules']} = {m['score']}")
    print(f"Veg:   {v['passed_rules']}/{v['applicable_rules']} = {v['score']}")
    print(f"Out:   {args.out}")


if __name__ == "__main__":
    main()
