import sqlite3

from scripts.enrich_foodplan import enrich_plan


def build_plan(raw_text: str, portion_value: float = 100.0) -> dict:
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
                                "raw_text": raw_text,
                                "portion": {"value": portion_value, "unit": "g"},
                                "food_groups": [],
                                "links": {
                                    "bls_id": None,
                                    "food_group": None,
                                    "confidence": None,
                                },
                                "tags": [],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_enrich_plan_detects_multiple_groups_and_tags():
    plan = build_plan("Fisch mit Gemüse und Vollkornbrot")

    group_keywords = {
        "fish": ["fisch"],
        "vegetables": ["gemüse"],
        "grains_potatoes": ["brot"],
    }
    tag_keywords = {"wholegrain": ["vollkorn"]}

    enriched, stats = enrich_plan(plan, group_keywords, tag_keywords)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["total_items"] == 1
    assert stats["mapped_groups"] == 1
    assert stats["still_unmapped"] == 0
    assert item["food_groups"] == ["fish", "grains_potatoes", "vegetables"]
    assert item["links"]["food_group"] == "fish"
    assert item["links"]["confidence"] == 1.0
    assert item["tags"] == ["wholegrain"]


def test_enrich_plan_uses_bls_fallback_when_keywords_do_not_match(tmp_path):
    plan = build_plan("Pfanne")

    group_keywords = {"vegetables": ["gemüse"]}
    tag_keywords = {}

    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO foods (id, name) VALUES (?, ?)", (1, "Gemüsepfanne"))
    conn.commit()
    conn.close()

    enriched, stats = enrich_plan(plan, group_keywords, tag_keywords, db_path)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["unmapped_before_bls"] == 1
    assert stats["mapped_via_bls"] == 1
    assert item["food_groups"] == ["vegetables"]
    assert item["links"]["food_group"] == "vegetables"
    assert item["links"]["bls_id"] == 1
    assert item["links"]["bls_name"] == "Gemüsepfanne"