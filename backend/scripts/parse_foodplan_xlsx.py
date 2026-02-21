# backend/scripts/parse_foodplan_xlsx.py
# ------------------------------------------------------------
# Speiseplan XLSX (Layout) -> foodplan.json
#
# Annahmen (wie Speiseplan OS Hermann Böse KW 47):
# - Sheet: "Tabelle1"
# - Spalte 0: Wochentage ("Montag"..."Freitag") markieren Tagesblöcke
# - Mischkost-Block:   Spalten 1..3  (Name | Portion | Notes)
# - Vegetarisch-Block: Spalten 4..6  (Name | Portion | Notes)
# - Dessert-Block:     Spalten 7..9  (Name | Portion | Notes)
#
# Das ist bewusst NICHT generisch (MVP). Parser später erweitern.
# ------------------------------------------------------------

import json
import math
import re
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, IO

import pandas as pd


DAYS = {"montag", "dienstag", "mittwoch", "donnerstag", "freitag"}


def norm_cell(x) -> Optional[str]:
    """Excel-Zellen robust in String/None wandeln."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    s = str(x).strip()
    return s if s else None


def parse_amount(text: Optional[str]) -> Optional[dict]:
    """
    Portion sehr simpel parsen:
      - "200 g", "200g"
      - "120 ml", "120ml"
    """
    if not text:
        return None
    s = text.strip().lower().replace(" ", "")

    m = re.match(r"^(\d+(?:\.\d+)?)\s*(g|ml)$", s)
    if not m:
        return None

    return {"value": float(m.group(1)), "unit": m.group(2)}


def join_hyphen(prev: str, curr: str) -> str:
    """Bindestrich-Zeilenumbruch zusammenziehen."""
    if prev.endswith("-"):
        return prev[:-1] + curr
    return prev + " " + curr


def parse_block(block_df: pd.DataFrame, name_col: int, amount_col: int, notes_col: int) -> List[dict]:
    """
    Liest einen Block (z.B. Mischkost) innerhalb eines Tages aus.
    Wir bauen Items, die später enrich/evaluate nutzen können.
    """
    items: List[dict] = []
    current: Optional[dict] = None

    for _, row in block_df.iterrows():
        name = norm_cell(row[name_col]) if name_col < len(row) else None
        amount = norm_cell(row[amount_col]) if amount_col < len(row) else None
        notes = norm_cell(row[notes_col]) if notes_col < len(row) else None

        # komplett leer
        if not name and not amount and not notes:
            continue

        # Fortsetzung ohne neue Portion/Notes (z.B. durch Zeilenumbruch)
        if name and current and not amount and not notes:
            current["raw_text"] = join_hyphen(current["raw_text"], name)
            continue

        # neuer Eintrag
        if name:
            if current:
                items.append(current)

            current = {
                "raw_text": name,
                "portion": parse_amount(amount),
                "notes": [notes] if notes else [],
                "links": {"bls_id": None, "food_group": None, "confidence": None},
                "tags": []
            }
        else:
            # kein Name -> als Ergänzung zum aktuellen Eintrag
            if current and amount and current.get("portion") is None:
                current["portion"] = parse_amount(amount)
            if current and notes:
                current["notes"].append(notes)

    if current:
        items.append(current)

    return [it for it in items if it.get("raw_text")]


def parse_foodplan_xlsx(xlsx_input: Union[Path, IO[bytes]]) -> dict:
    """Parst das KW47-XLSX-Template in unser foodplan.json-Format.

    `xlsx_input` kann sein:
    - `Path` (CLI / lokale Datei)
    - file-like object (z.B. `io.BytesIO` oder Flask Upload-Stream)

    Hinweis: Diese Funktion speichert nichts auf Disk.
    """

    df = pd.read_excel(
        xlsx_input,
        sheet_name="Tabelle1",
        header=None,
        usecols="A:J",      # nur 0..9 (genau deine Blöcke)
        nrows=400,          # reicht locker fürs Template
        engine="openpyxl"   # explizit, damit es stabil ist
    )

    # Tagesstartzeilen finden (Spalte 0)
    day_rows: List[int] = []
    for i in df.index:
        v = norm_cell(df.loc[i, 0])
        if v and v.lower() in DAYS:
            day_rows.append(i)

    if not day_rows:
        raise RuntimeError("Keine Tageszeilen (Montag-Freitag) in Spalte 0 gefunden. Format passt nicht.")
    
    
    file_name = xlsx_input.name if isinstance(xlsx_input, Path) else None


    plan: Dict[str, Any] = {
        "schema_version": "1.0",
        "source": {"type": "excel", "file": file_name, "sheet": "Tabelle1"},
        "context": {
            "school": None,
            "week_label": None,
            "year": None,
            "meal_type": "lunch",
            "timezone": "Europe/Berlin"
        },
        "days": []
    }

    for idx, start in enumerate(day_rows):
        end = day_rows[idx + 1] if idx + 1 < len(day_rows) else len(df)

        weekday = norm_cell(df.loc[start, 0])
        block = df.iloc[start:end].copy()

        # den Wochentag aus dem Block entfernen
        block.iat[0, 0] = None

        mischkost = parse_block(block, 1, 2, 3)
        vegetarisch = parse_block(block, 4, 5, 6)
        dessert = parse_block(block, 7, 8, 9)

        plan["days"].append({
            "date": None,
            "weekday": weekday,
            "menus": [
                {"menu_type": "mischkost", "items": mischkost},
                {"menu_type": "vegetarisch", "items": vegetarisch},
                {"menu_type": "dessert", "items": dessert},
            ]
        })

    # Wenn gar keine Items extrahiert wurden, ist das XLSX-Format sehr wahrscheinlich falsch.
    total_items = sum(
        len(menu.get("items") or [])
        for day in plan.get("days") or []
        for menu in (day.get("menus") or [])
    )
    if total_items == 0:
        raise RuntimeError(
            "0 Items extrahiert. Vermutlich passt das XLSX nicht zum KW47-Template (Sheet 'Tabelle1', Spalten A..J)."
        )

    return plan


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input Speiseplan .xlsx")
    ap.add_argument("--out", dest="out", required=True, help="Output foodplan.json")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)

    plan = parse_foodplan_xlsx(inp)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    print(" foodplan.json geschrieben:", out)
