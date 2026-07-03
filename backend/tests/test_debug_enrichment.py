from scripts.debug_enrichment import build_unmapped_debug_reason


def test_build_unmapped_debug_reason_detects_compound_without_bls_match():
    reason_key, reason_label = build_unmapped_debug_reason(
        "Bohnen & Reis",
        [],
        {},
    )

    assert reason_key == "no_bls_match_compound_text"
    assert "zusammengesetzten Text" in reason_label


def test_build_unmapped_debug_reason_detects_blocked_ambiguity():
    reason_key, reason_label = build_unmapped_debug_reason(
        "Aprikosen im Ausbackteig frittiert",
        [("A123", "Aprikosen", 1, 1.0)],
        {"fruit": 0.5, "grains_potatoes": 0.5},
    )

    assert reason_key == "ambiguous_or_blocked"
    assert "mehrdeutig" in reason_label