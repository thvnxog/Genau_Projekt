from scripts.evaluate_foodplan import evaluate_plan_for_diet, infer_groups_for_item


def build_plan() -> dict:
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
    item = {
        "food_groups": ["fish", "vegetables", "fish"],
        "links": {"food_group": "vegetables"},
        "tags": ["wholegrain"],
        "raw_text": "irrelevant",
    }

    assert infer_groups_for_item(item) == ["vegetables", "fish"]


def test_evaluate_plan_for_diet_counts_groups_and_builds_gram_hints():
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