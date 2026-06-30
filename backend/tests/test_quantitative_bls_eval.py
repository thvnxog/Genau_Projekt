from scripts.quantitative_bls_eval import build_week_plan, classify_unmapped_item, summarize


def test_build_week_plan_creates_one_menu_per_day_with_two_items():
    """Verifies that build_week_plan creates exactly 1 menu per day with 2 items."""
    plan = build_week_plan(
        ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],  # 10 Items für 5 Tage * 2
        seed=7,
        weeks=1,
        menu_types=["vegetarisch", "mischkost"],  # Parameter wird ignoriert
    )

    assert len(plan["days"]) == 5  # 5 Wochentage
    total_items = 0
    for day in plan["days"]:
        assert len(day["menus"]) == 1  # Genau 1 Menu pro Tag
        assert len(day["menus"][0]["items"]) == 2  # Genau 2 Items pro Menu
        total_items += len(day["menus"][0]["items"])

    assert total_items == 10  # 5 Tage * 2 Items = 10 Items


def test_classify_unmapped_item_detects_compound_text_reason():
    item = {
        "raw_text": "Bohnen & Reis",
        "food_groups": [],
        "links": {"bls_matches": [], "group_scores": {}, "food_group": None, "confidence": 0.0},
    }

    assert classify_unmapped_item(item) == "no_bls_match_compound_text"


def test_summarize_exposes_unmapped_reasons():
    """Verifies that summarize correctly aggregates unmapped reasons."""
    enriched = {
        "days": [
            {
                "week_index": 0,
                "menus": [
                    {
                        "items": [
                            {
                                "raw_text": "Gemüsepfanne",
                                "food_groups": ["vegetables"],
                                "links": {
                                    "bls_id": 1,
                                    "bls_matches": [{"code": "G111", "name": "Gemüsepfanne", "id": 1, "score": 1}],
                                    "group_scores": {"vegetables": 1},
                                    "confidence": 1.0,
                                },
                            },
                            {
                                "raw_text": "Bohnen & Reis",
                                "food_groups": [],
                                "links": {"bls_matches": [], "group_scores": {}, "confidence": 0.0},
                            },
                        ],
                    }
                ],
            }
        ]
    }

    summary = summarize(enriched, {"mapped_groups": 1, "mapped_via_bls": 1, "still_unmapped": 1}, 2)

    assert summary["total_items"] == 2
    assert summary["final_recognition_count"] == 1
    assert summary["still_unmapped_count"] == 1
    assert summary["unmapped_reason_counts"][0] == ("no_bls_match_compound_text", 1)
    assert summary["per_week"][0]["final_recognition_count"] == 1
    assert summary["per_week"][0]["still_unmapped_count"] == 1