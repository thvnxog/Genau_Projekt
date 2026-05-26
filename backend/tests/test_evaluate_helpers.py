import pytest

from scripts.evaluate_foodplan import (
    adjusted_threshold_for_plan,
    count_plan_days,
    evaluate_operator,
    rule_applies,
)


def test_rule_applies_and_evaluate_operator():
    # Grundfunktionen der Regelprüfung: Gültigkeit und Operatoren.
    assert rule_applies({"diet": "all"}, "mixed") is True
    assert rule_applies({"diet": "mixed"}, "mixed") is True
    assert rule_applies({"diet": "ovo_lacto_vegetarian"}, "mixed") is False

    assert evaluate_operator(5, "min", 5) is True
    assert evaluate_operator(4, "min", 5) is False
    assert evaluate_operator(4, "max", 5) is True
    assert evaluate_operator(5, "equals", 5) is True

    with pytest.raises(ValueError):
        evaluate_operator(1, "unsupported", 2)


def test_count_plan_days_and_threshold_scaling():
    # Die Schwelle für Mindestwerte wird an die tatsächlich vorhandenen Tage angepasst.
    plan = {
        "days": [
            {
                "menus": [
                    {"menu_type": "mischkost", "items": [{}]},
                    {"menu_type": "dessert", "items": []},
                ]
            },
            {
                "menus": [
                    {"menu_type": "vegetarisch", "items": []},
                ]
            },
        ]
    }

    rule = {"operator": "min", "threshold": 10}
    rules_doc = {"scope": {"time_window_days": 5}}

    assert count_plan_days(plan, "mixed") == 1
    assert adjusted_threshold_for_plan(rule, rules_doc, plan, "mixed") == 2.0
    assert adjusted_threshold_for_plan({"operator": "max", "threshold": 10}, rules_doc, plan, "mixed") == 10.0