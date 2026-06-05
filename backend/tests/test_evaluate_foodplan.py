from scripts.evaluate_foodplan import evaluate_plan_for_diet, infer_groups_for_item


def build_plan() -> dict:
    # Beispielplan mit mehreren Gerichten, um Zählung und Grammverteilung zu testen.
    return {
        "schema_version": "1.0",
        "days": [
            {
                "weekday": "Montag",
                "week_index": 0,
                "menus": [
                    {
                        "menu_type": "mischkost",
                        "items": [
                            {
                                "raw_text": "Gemüsepfanne mit Fisch",
                                "food_groups": ["vegetables", "fish"],
                                "links": {
                                    "food_group": "vegetables",
                                    "confidence": 1.0,
                                },
                                "tags": [],
                                "portion": {"value": 100, "unit": "g"},
                            },
                            {
                                "raw_text": "Fischfilet",
                                "food_groups": [],
                                "links": {"food_group": "fish", "confidence": 1.0},
                                "tags": [],
                                "portion": {"value": 50, "unit": "g"},
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_infer_groups_for_item_prefers_multi_groups_and_deduplicates():
    # Mehrfach vorhandene Gruppen werden bereinigt und nur einmal gezählt.
    item = {
        "food_groups": ["fish", "vegetables", "fish"],
        "links": {"food_group": "vegetables"},
        "tags": ["wholegrain"],
        "raw_text": "irrelevant",
    }

    assert infer_groups_for_item(item) == ["vegetables", "fish"]


def test_evaluate_plan_for_diet_counts_groups_and_builds_gram_hints():
    # Die Bewertung zählt Gruppen und erzeugt Gramm-Hinweise für Regel-Checks.
    plan = build_plan()
    rules_doc = {
        "scope": {"time_window_days": 5},
        "rules": [
            {
                "id": "fish-count",
                "label": "Fisch zählt",
                "diet": "all",
                "target": {"count_by": "food_group", "value": "fish"},
                "operator": "min",
                "threshold": 2,
            },
            {
                "id": "veg-grams",
                "label": "Gemüse in Gramm",
                "diet": "all",
                "target": {"count_by": "food_group_grams", "value": "vegetables"},
                "operator": "min",
                "threshold": 300,
            },
        ],
    }

    report = evaluate_plan_for_diet(plan, rules_doc, "mixed", school_level="P")

    assert report["summary"] == {
        "applicable_rules": 1,
        "passed_rules": 1,
        "score": 1.0,
    }
    assert report["counts"]["food_groups"]["fish"] == 2
    assert report["counts"]["food_groups"]["vegetables"] == 1
    assert report["counts"]["food_groups_grams"]["fish"] == 100.0
    assert report["counts"]["food_groups_grams"]["vegetables"] == 50.0
    assert report["gram_hints"][0]["id"] == "veg-grams"
    assert report["gram_hints"][0]["target_grams"] == 60.0
    assert report["gram_hints"][0]["missing_grams"] == 10.0
    assert report["gram_hints"][0]["status"] == "needs_more"


def test_evaluate_plan_for_diet_marks_gram_hints_when_target_is_exceeded():
    # Bei Gramm-Regeln vom Typ max soll ein Überschreiten als Warnung sichtbar sein.
    plan = build_plan()
    rules_doc = {
        "scope": {"time_window_days": 5},
        "rules": [
            {
                "id": "veg-grams-max",
                "label": "Gemüse in Gramm",
                "diet": "all",
                "target": {"count_by": "food_group_grams", "value": "vegetables"},
                "operator": "max",
                "threshold": 40,
            },
        ],
    }

    report = evaluate_plan_for_diet(plan, rules_doc, "mixed", school_level="P")

    assert report["gram_hints"][0]["status"] == "too_much"


def test_evaluate_plan_for_diet_marks_min_gram_hints_when_target_is_exceeded():
    # Auch Mindest-Regeln sollen bei Überschreiten als Warnung markiert werden.
    plan = build_plan()
    rules_doc = {
        "scope": {"time_window_days": 5},
        "rules": [
            {
                "id": "veg-grams-min",
                "label": "Gemüse in Gramm",
                "diet": "all",
                "target": {"count_by": "food_group_grams", "value": "vegetables"},
                "operator": "min",
                "threshold": 40,
            },
        ],
    }

    report = evaluate_plan_for_diet(plan, rules_doc, "mixed", school_level="P")

    assert report["gram_hints"][0]["status"] == "too_much"