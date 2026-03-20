from pathlib import Path
import sys

import pandas as pd

# Erlaubt Imports wie `from scripts...`, wenn Tests aus dem Projekt-Root laufen.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.parse_foodplan_xlsx import (  # noqa: E402
    is_preparation_fragment,
    parse_block,
    parse_foodplan_xlsx,
)


def test_is_preparation_fragment_detects_common_preparation_words():
    assert is_preparation_fragment("ueberbacken") is True
    assert is_preparation_fragment("frittiert") is True
    assert is_preparation_fragment("gegrillt") is True


def test_is_preparation_fragment_rejects_real_food_names():
    assert is_preparation_fragment("Gurkensalat") is False
    assert is_preparation_fragment("Tomaten-Kraeutersauce") is False


def test_parse_block_merges_preparation_line_into_previous_item():
    # Simuliert einen kleinen Vegetarisch-Block mit einer separaten Zubereitungszeile.
    block = pd.DataFrame(
        [
            [None, "Canneloni (Gemuesefuellung)", 380, "TK"],
            [None, "mit Tomatensauce & Mozzarella", None, "K"],
            [None, "ueberbacken", None, None],
            [None, "Gurkensalat", 80, "frisch"],
        ]
    )

    items = parse_block(block, name_col=1, amount_col=2, notes_col=3)

    # Aktuelle Parserlogik: "ueberbacken" wird an den direkt vorherigen Eintrag
    # angehaengt (hier: "mit Tomatensauce & Mozzarella").
    assert len(items) == 3
    assert items[1]["raw_text"] == "mit Tomatensauce & Mozzarella ueberbacken"
    assert items[2]["raw_text"] == "Gurkensalat"


def test_parse_month_example_groups_into_4_weeks_and_20_days():
    project_root = BACKEND_DIR.parent
    xlsx_path = project_root / "data" / "Speiseplan_Beispiel_Monat.xlsx"

    plan = parse_foodplan_xlsx(xlsx_path)

    assert len(plan.get("weeks", [])) == 4
    assert len(plan.get("days", [])) == 20

    first_week = plan["weeks"][0]
    assert first_week["week_index"] == 0
    assert len(first_week.get("days", [])) == 5
