import sqlite3

from scripts.enrich_foodplan import (
    collect_note_tags,
    compound_token_variants,
    detect_table_and_columns,
    enrich_plan,
    load_code_letter_mapping,
)


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
                                    "bls_name": None,
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


def test_enrich_plan_maps_dge_group_from_bls_code_letter(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.execute(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        (1, "Hafer Flocken", "C131000"),
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"C": ["grains_potatoes"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Hafer")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["total_items"] == 1
    assert stats["mapped_groups"] == 1
    assert stats["mapped_via_bls"] == 1
    assert stats["still_unmapped"] == 0
    assert item["food_groups"] == ["grains_potatoes"]
    assert item["links"]["food_group"] == "grains_potatoes"
    assert item["links"]["confidence"] == 1.0
    assert item["links"]["bls_id"] == 1
    assert item["links"]["bls_name"] == "Hafer Flocken"


def test_enrich_plan_leaves_item_unmapped_without_code_mapping(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.execute(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        (7, "Gemüsepfanne", "G111000"),
    )
    conn.commit()
    conn.close()

    plan = build_plan("Gemüsepfanne")
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map={})

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 0
    assert stats["still_unmapped"] == 1
    assert item["food_groups"] == []
    assert item["links"]["food_group"] is None
    assert item["links"]["confidence"] == 0.0
    assert item["links"]["bls_id"] == 7
    assert item["links"]["bls_name"] == "Gemüsepfanne"


def test_enrich_plan_combines_multiple_groups_for_composite_dishes(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.executemany(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        [
            (1, "Hähnchenbrust", "U111000"),
            (2, "Reis", "C222000"),
        ],
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"U": ["meat"], "C": ["grains_potatoes"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Hähnchen mit Reis")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 1
    assert item["food_groups"] == ["meat", "grains_potatoes"]
    assert item["links"]["food_group"] == "meat"
    assert item["links"]["bls_matches"][0]["name"] == "Hähnchenbrust"
    assert item["links"]["bls_matches"][1]["name"] == "Reis"


def test_enrich_plan_chooses_majority_group_for_shared_token(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.executemany(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        [
            (1, "Spinat frisch", "G111000"),
            (2, "Rahmspinat", "G222000"),
            (3, "Spinat mit Rahm", "M333000"),
        ],
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"G": ["vegetables"], "M": ["dairy"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Spinat")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 1
    assert item["food_groups"] == ["vegetables"]
    assert item["links"]["food_group"] == "vegetables"
    assert item["links"]["confidence"] == 2 / 3
    assert item["links"]["group_scores"]["vegetables"] == 2
    assert item["links"]["group_scores"].get("dairy", 0) == 1


def test_enrich_plan_prefers_dairy_for_yoghurt_compound(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.executemany(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        [
            (1, "Joghurt natur", "M111000"),
            (2, "Joghurt mit Kräutern", "M222000"),
            (3, "Minzdip", "H333000"),
        ],
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"M": ["dairy"], "H": ["legumes"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Joghurt-Minzdipp")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 1
    assert item["food_groups"] == ["dairy"]
    assert item["links"]["food_group"] == "dairy"
    assert item["links"]["confidence"] > 0.5


def test_enrich_plan_finds_bread_in_compound_token(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.execute(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        (1, "Brot", "C444000"),
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"C": ["grains_potatoes"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Saatenbrot")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 1
    assert item["food_groups"] == ["grains_potatoes"]
    assert item["links"]["food_group"] == "grains_potatoes"


def test_enrich_plan_ignores_other_group(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.execute(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        (1, "Sonderfall", "Q999000"),
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"Q": ["other"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Sonderfall")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 0
    assert stats["still_unmapped"] == 1
    assert item["food_groups"] == []
    assert item["links"]["food_group"] is None
    assert item["links"]["confidence"] == 0.0


def test_compound_token_variants_only_keep_known_terms():
    variants = compound_token_variants(
        "salzkartoffeln",
        {"salz", "kartoffeln", "kartoffel", "brot"},
    )

    assert variants == ["salzkartoffeln", "kartoffeln"]


def test_enrich_plan_leaves_ambiguous_phrase_unmapped(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")
    conn.executemany(
        "INSERT INTO foods (id, name_de, code) VALUES (?, ?, ?)",
        [
            (1, "Tomatensauce Fisch", "A111000"),
            (2, "Tomatensauce Gemüse", "G222000"),
            (3, "Mozzarella Milch", "M333000"),
            (4, "Überbacken Brot", "C444000"),
            (5, "Überbacken Hähnchen", "U555000"),
        ],
    )
    conn.commit()
    conn.close()

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"code_letter_mapping": {"A": ["fish"], "G": ["vegetables"], "M": ["dairy"], "C": ["grains_potatoes"], "U": ["meat"]}}',
        encoding="utf-8",
    )

    plan = build_plan("Tomatensauce & Mozzarella überbacken")
    code_letter_map = load_code_letter_mapping(mapping_path)
    enriched, stats = enrich_plan(plan, bls_db_path=db_path, code_letter_map=code_letter_map)

    item = enriched["days"][0]["menus"][0]["items"][0]

    assert stats["mapped_groups"] == 0
    assert stats["still_unmapped"] == 1
    assert item["food_groups"] == []
    assert item["links"]["food_group"] is None
    assert item["links"]["confidence"] == 0.0
    assert item["links"]["group_scores"]


def test_collect_note_tags_maps_excel_additions_to_tags():
    notes = [
        "Bio",
        "VK: Vollkorn",
        "M: Mageres Muskelfleisch",
        "pf: paniert oder frittiert",
        "TK=Tiefkühl, frisch, Konserve",
    ]

    assert collect_note_tags(notes) == [
        "bio",
        "canned",
        "fresh",
        "fried_or_breaded",
        "frozen",
        "lean_meat",
        "wholegrain",
    ]


def test_detect_table_and_columns_prefers_foods_name_de_and_code(tmp_path):
    db_path = tmp_path / "bls.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foods (id INTEGER PRIMARY KEY, name_de TEXT, code TEXT)")

    assert detect_table_and_columns(conn) == ("foods", "name_de", "id", "code")
    conn.close()
