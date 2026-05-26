from pathlib import Path

from scripts.enrich_foodplan import (
    collect_tags,
    load_json_mapping,
    load_keyword_files,
    merge_keywords,
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


def test_collect_tags_and_keyword_loading(tmp_path):
  # Keywords werden aus Dateien und JSON geladen und anschließend zu Tags zusammengeführt.
    keywords_root = tmp_path / "keywords"
    groups_dir = keywords_root / "groups"
    tags_dir = keywords_root / "tags"
    groups_dir.mkdir(parents=True)
    tags_dir.mkdir(parents=True)

    (groups_dir / "vegetables.txt").write_text("# comment\nGemüse\nGemüse\n", encoding="utf-8")
    (tags_dir / "wholegrain.txt").write_text("Vollkorn\n", encoding="utf-8")

    json_path = tmp_path / "mapping.json"
    json_path.write_text(
        """
        {
          "mapping": [
            {"dge_food_group": "fish", "match": {"contains_any": ["fisch"]}}
          ],
          "tags": [
            {"tag": "raw_veg", "match": {"contains_any": ["rohkost"]}}
          ]
        }
        """,
        encoding="utf-8",
    )

    group_txt = load_keyword_files(groups_dir)
    tag_txt = load_keyword_files(tags_dir)
    group_json, tag_json = load_json_mapping(json_path)

    assert group_txt == {"vegetables": ["gemüse"]}
    assert tag_txt == {"wholegrain": ["vollkorn"]}
    assert group_json == {"fish": ["fisch"]}
    assert tag_json == {"raw_veg": ["rohkost"]}

    merged_groups = merge_keywords(group_txt, group_json)
    merged_tags = merge_keywords(tag_txt, tag_json)

    assert merged_groups == {"fish": ["fisch"], "vegetables": ["gemüse"]}
    assert merged_tags == {"raw_veg": ["rohkost"], "wholegrain": ["vollkorn"]}

    assert collect_tags("Vollkorn und Rohkost", merged_tags) == ["raw_veg", "wholegrain"]