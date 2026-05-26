import math

from scripts.parse_foodplan import (
    extract_week_label,
    is_preparation_fragment,
    is_week_header,
    join_hyphen,
    norm_cell,
    parse_amount,
)


def test_norm_cell_and_week_header_helpers():
    assert norm_cell(None) is None
    assert norm_cell(float("nan")) is None
    assert norm_cell("  Montag ") == "Montag"
    assert is_week_header("Speiseplan vom 12.01.2026") is True
    assert is_week_header("Montag") is False


def test_extract_week_label_and_join_hyphen():
    assert extract_week_label(None, 2) == "Woche 3"
    assert extract_week_label("  Speiseplan   vom  12.01.2026  ", 0) == (
        "Speiseplan vom 12.01.2026"
    )
    assert join_hyphen("Fisch-", "pfanne") == "Fischpfanne"
    assert join_hyphen("Fisch", "pfanne") == "Fisch pfanne"


def test_parse_amount_and_preparation_fragment_detection():
    assert parse_amount(200) == {"value": 200.0, "unit": "g"}
    assert parse_amount("200") == {"value": 200.0, "unit": "g"}
    assert parse_amount("120 ml") == {"value": 120.0, "unit": "ml"}
    assert parse_amount("abc") is None
    assert is_preparation_fragment("Überbacken") is True
    assert is_preparation_fragment("frittiert") is True
    assert is_preparation_fragment("Gurkensalat") is False