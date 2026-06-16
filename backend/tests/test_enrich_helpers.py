from pathlib import Path

from scripts.enrich_foodplan import (
    collect_tags,
    collect_note_tags,
    load_json_mapping,
    pick_best_group,
    pick_matching_groups,
    tokenize,
)


def test_tokenize_removes_stopwords_and_preparation_words():
  # Die Tokenisierung soll unwichtige Wörter und Zubereitungsbegriffe entfernen.
    tokens = tokenize("Fisch mit überbacken und Gemüse")

    assert tokens == ["fisch", "gemüse"]


def test_pick_best_group_and_matching_groups():
  # Die Matching-Funktionen wählen die beste Gruppe und erkennen mehrere Treffer.
    group_keywords = {
        "fish": ["fisch"],
        "vegetables": ["gemüse"],
        "grains_potatoes": ["brot", "kartoffel"],
    }

    best = pick_best_group("Gemüsepfanne", group_keywords)
    matches = pick_matching_groups("Fisch und Gemüse", group_keywords)

    assert best.key == "vegetables"
    assert best.hits == 1
    assert matches[0].key == "fish"
    assert {match.key for match in matches} == {"fish", "vegetables"}


def test_collect_tags_and_json_mapping(tmp_path):
  # Keywords werden aus JSON geladen und zu Tags zusammengeführt.
    json_path = tmp_path / "mapping.json"
    json_path.write_text(
        """
        {
          "mapping": [
            {"dge_food_group": "fish", "match": {"contains_any": ["fisch"]}},
            {"dge_food_group": "vegetables", "match": {"contains_any": ["gemüse"]}}
          ],
          "tags": [
            {"tag": "raw_veg", "match": {"contains_any": ["rohkost"]}},
            {"tag": "wholegrain", "match": {"contains_any": ["vollkorn"]}}
          ]
        }
        """,
        encoding="utf-8",
    )

    group_json, tag_json = load_json_mapping(json_path)

    assert group_json == {"fish": ["fisch"], "vegetables": ["gemüse"]}
    assert tag_json == {"raw_veg": ["rohkost"], "wholegrain": ["vollkorn"]}

    assert collect_tags("Vollkorn und Rohkost", tag_json) == ["raw_veg", "wholegrain"]


def test_collect_note_tags_maps_excel_additions_to_tags():
  # Die Zusatzspalte soll typische Kürzel in reguläre Tags übersetzen.
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