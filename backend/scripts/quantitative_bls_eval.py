"""Quantitativer BLS-Test für das Enrichment.

Das Skript lädt Gerichtsnamen aus der BLS-Datenbank, baut daraus einen
synthetischen Wochenplan und misst, wie viele Einträge über das BLS-Code-
Letter-Mapping zugeordnet werden.

Warum das nützlich ist:
- Es ist wiederholbar und liefert eine Terminal-Metrik.
- Es testet die reale BLS-Datenbasis statt handgeschriebener Beispiele.
- Es zeigt, wie viele Gerichte im BLS-only-Flow zugeordnet werden.

Beispiel:
  cd backend
    ./.venv/bin/python scripts/quantitative_bls_eval.py --all --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.enrich_foodplan import (  # noqa: E402
    detect_table_and_columns,
    enrich_plan,
    load_code_letter_mapping,
)


WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
DEFAULT_MENU_TYPES = ["vegetarisch", "mischkost"]
STRESS_PROFILES = {"none", "noisy", "long", "duplicate", "ambiguous"}


def default_bls_db_path() -> Path:
    return BACKEND_DIR / "instance" / "bls.db"


def load_bls_rows(db_path: Path) -> list[dict]:
    """Lädt alle BLS-Zeilen aus der SQLite-Datenbank."""

    if not db_path.exists():
        raise FileNotFoundError(f"BLS-Datenbank nicht gefunden: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        table, name_col, id_col, code_col = detect_table_and_columns(conn)
        if not table or not name_col:
            raise RuntimeError("Konnte keine passende BLS-Tabelle/Spalte erkennen.")

        select_cols = [name_col]
        if code_col:
            select_cols.append(code_col)
        if id_col:
            select_cols.append(id_col)

        order_col = id_col or code_col or name_col
        sql = f"SELECT {', '.join(select_cols)} FROM {table} ORDER BY {order_col}"
        rows = conn.execute(sql).fetchall()

        items: list[dict] = []
        for row in rows:
            name = str(row[0]).strip()
            if not name:
                continue

            food_id = row[2] if code_col and id_col else (row[1] if id_col else None)
            items.append({"id": food_id, "name": name})

        return items
    finally:
        conn.close()


def _stressify_name(name: str, rng: random.Random, profile: str, pool: list[str]) -> str:
    """Erzeugt absichtlich schwierigere Varianten für Stress-Tests."""

    if profile == "none":
        return name

    modifiers = ["frisch", "hausgemacht", "überbacken", "mit sauce", "würzig"]

    if profile == "noisy":
        if rng.random() < 0.5:
            return f"{name} {rng.choice(modifiers)}"
        return name

    if profile == "long":
        extra = [rng.choice(modifiers), rng.choice(modifiers)]
        return f"{name}, {extra[0]}, {extra[1]}"

    if profile == "duplicate":
        return f"{name} / {name}"

    if profile == "ambiguous" and pool:
        other = rng.choice(pool)
        if other != name:
            connector = rng.choice(["mit", "und", "&", "/"])
            return f"{name} {connector} {other}"

    return name


def build_week_plan(
    names: Iterable[str],
    seed: int | None = None,
    weeks: int = 1,
    menu_types: Iterable[str] | None = None,
    stress_profile: str = "none",
) -> dict:
    """Verpackt Gerichtsnamen in einen künstlichen Wochenplan.

    Pro Tag wird ein einzelnes Menu mit 2 Gerichten erstellt.
    Wenn `weeks` > 1, werden die Gerichte über mehrere Wochen und Wochentage
    verteilt. Optional können absichtlich schwierigere Stress-Varianten erzeugt
    werden.
    """

    rng = random.Random(seed)
    base_names = [str(name).strip() for name in names if str(name).strip()]
    rng.shuffle(base_names)

    if not base_names:
        base_names = ["unbekannt"]

    stress_profile = stress_profile if stress_profile in STRESS_PROFILES else "none"

    stressed_names = [
        _stressify_name(name, rng, stress_profile, base_names)
        for name in base_names
    ]

    items = [
        {
            "raw_text": name,
            "portion": {"value": 100, "unit": "g"},
            "food_groups": [],
            "links": {},
            "tags": [],
        }
        for name in stressed_names
    ]

    days: list[dict] = []

    # Berechne items_per_day basierend auf der Anzahl der Items und Wochen
    # Standard: 2 Items pro Tag, aber erhöhen wenn zu viele Items für die Wochen
    total_slots = weeks * len(WEEKDAYS)
    items_per_day = max(2, (len(items) + total_slots - 1) // total_slots)
    
    item_idx = 0
    for w in range(weeks):
        for weekday in WEEKDAYS:
            day_items: list[dict] = []
            for _ in range(items_per_day):
                if item_idx < len(items):
                    day_items.append(items[item_idx])
                    item_idx += 1
            
            # Erstelle ein einzelnes Menu pro Tag
            days.append(
                {
                    "weekday": weekday,
                    "week_index": w,
                    "menus": [
                        {
                            "items": day_items,
                        }
                    ],
                }
            )

    return {"schema_version": "1.0", "days": days}


def classify_unmapped_item(item: dict) -> str:
    """Leitet einen plausiblen Fehlergrund für nicht erkannte Items ab."""

    raw_text = str(item.get("raw_text", "") or "").strip()
    links = item.get("links") or {}
    bls_matches = links.get("bls_matches") or []
    group_scores = links.get("group_scores") or {}

    if not raw_text:
        return "empty_text"

    if len(raw_text) <= 3:
        return "too_short"

    if not bls_matches:
        if any(sep in raw_text for sep in ["/", "&", "+", ",", ";", ":"]):
            return "no_bls_match_compound_text"
        return "no_bls_match"

    if group_scores:
        return "ambiguous_or_blocked"

    if links.get("bls_id") and not item.get("food_groups"):
        return "mapping_missing_or_other"

    return "unknown"


def summarize(enriched: dict, stats: dict, total_items: int) -> dict:
    items = [item for day in enriched.get("days", []) for menu in day.get("menus", []) for item in menu.get("items", [])]

    group_counter = Counter()
    primary_counter = Counter()
    multi_group_items = 0
    unmapped_names: list[str] = []
    unmapped_reason_counter = Counter()
    unmapped_by_reason: dict[str, list[str]] = defaultdict(list)

    for item in items:
        groups = item.get("food_groups") or []
        if len(groups) > 1:
            multi_group_items += 1
        if groups:
            primary_counter[groups[0]] += 1
            for group in groups:
                group_counter[group] += 1
        else:
            unmapped_names.append(item.get("raw_text", ""))
            reason = classify_unmapped_item(item)
            unmapped_reason_counter[reason] += 1
            if len(unmapped_by_reason[reason]) < 20:
                unmapped_by_reason[reason].append(item.get("raw_text", ""))

    final_recognition = int(stats.get("mapped_groups", 0))
    via_bls = int(stats.get("mapped_via_bls", 0))
    still_unmapped = int(stats.get("still_unmapped", 0))
    # Per-week statistics: gruppiere Tage nach week_index
    weeks: dict[int, list[dict]] = {}
    for day in enriched.get("days", []):
        wk = int(day.get("week_index", 0) or 0)
        weeks.setdefault(wk, [])
        for menu in day.get("menus", []):
            weeks[wk].extend(menu.get("items", []))

    per_week: list[dict] = []
    final_rates: list[float] = []
    for wk in sorted(weeks.keys()):
        w_items = weeks[wk]
        tot = len(w_items)
        final_count = sum(1 for i in w_items if (i.get("food_groups") or []))
        bls_count = sum(1 for i in w_items if i.get("links", {}).get("bls_id"))
        still_unmapped_w = tot - final_count
        multi_w = sum(1 for i in w_items if len(i.get("food_groups") or []) > 1)

        final_rate = round(final_count / tot, 4) if tot else 0.0
        final_rates.append(final_rate)

        # Sammle Item-Details pro Woche
        items_recognized: list[dict] = []
        items_unmapped: list[dict] = []
        for item in w_items:
            raw_text = item.get("raw_text", "")
            groups = item.get("food_groups") or []
            if groups:
                items_recognized.append({
                    "name": raw_text,
                    "groups": groups,
                    "bls_id": item.get("links", {}).get("bls_id"),
                    "confidence": item.get("links", {}).get("confidence"),
                })
            else:
                items_unmapped.append({"name": raw_text})

        per_week.append(
            {
                "week_index": wk,
                "total_items": tot,
                "final_recognition_count": final_count,
                "final_recognition_rate": final_rate,
                "bls_code_match_count": bls_count,
                "bls_code_match_rate": round(bls_count / tot, 4) if tot else 0.0,
                "still_unmapped_count": still_unmapped_w,
                "still_unmapped_rate": round(still_unmapped_w / tot, 4) if tot else 0.0,
                "multi_group_items": multi_w,
                "multi_group_rate": round(multi_w / tot, 4) if tot else 0.0,
                "items_recognized": items_recognized,
                "items_unmapped": items_unmapped,
            }
        )

    per_week_summary: dict = {}
    if final_rates:
        per_week_summary = {
            "weeks_count": len(final_rates),
            "mean_final_recognition_rate": round(sum(final_rates) / len(final_rates), 4),
            "min_final_recognition_rate": min(final_rates),
            "max_final_recognition_rate": max(final_rates),
        }

    return {
        "total_items": total_items,
        "final_recognition_count": final_recognition,
        "final_recognition_rate": round(final_recognition / total_items, 4) if total_items else 0.0,
        "bls_code_match_count": via_bls,
        "bls_code_match_rate": round(via_bls / total_items, 4) if total_items else 0.0,
        "still_unmapped_count": still_unmapped,
        "still_unmapped_rate": round(still_unmapped / total_items, 4) if total_items else 0.0,
        "multi_group_items": multi_group_items,
        "multi_group_rate": round(multi_group_items / total_items, 4) if total_items else 0.0,
        "group_distribution": primary_counter.most_common(),
        "all_group_distribution": group_counter.most_common(),
        "unmapped_reason_counts": unmapped_reason_counter.most_common(),
        "unmapped_by_reason": dict(unmapped_by_reason),
        "sample_unmapped": unmapped_names[:20],
        "per_week": per_week,
        "per_week_summary": per_week_summary,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quantitativer BLS-Test für das Foodplan-Enrichment")
    parser.add_argument("--bls-db", type=Path, default=default_bls_db_path(), help="Pfad zur SQLite-BLS-Datenbank")
    parser.add_argument("--mapping-json", type=Path, default=BACKEND_DIR / "rules" / "bls_to_dge_groups.json", help="Optionales JSON-Mapping")
    parser.add_argument("--all", action="store_true", help="Alle BLS-Gerichte testen (Default)")
    parser.add_argument("--sample-size", type=int, default=0, help="Zufällige Teilmenge der BLS-Gerichte (0 = alle)")
    parser.add_argument("--seed", type=int, default=None, help="Optionaler Seed für reproduzierbare Zufallsauswahl (default: None = neue Zufallswahl pro Lauf)")
    parser.add_argument("--weeks", type=int, default=1, help="Anzahl Wochen, die pro Sample simuliert werden sollen (default=1)")
    parser.add_argument("--menu-types", type=str, default=",".join(DEFAULT_MENU_TYPES), help="Kommagetrennte Menütypen pro Tag, z.B. 'vegetarisch,mischkost'")
    parser.add_argument("--stress-profile", type=str, default="none", choices=sorted(STRESS_PROFILES), help="Absichtlich schwierige Textvariante für Stress-Tests")
    parser.add_argument("--report-out", type=Path, default=None, help="Optional: JSON-Report auf Disk schreiben")
    parser.add_argument("--show-weeks", action="store_true", help="Zeige detaillierte Wochen-Ergebnisse in der Konsole (default: deaktiviert)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rows = load_bls_rows(args.bls_db)
    if not rows:
        print("Keine BLS-Gerichte gefunden.")
        return 1

    if args.all:
        args.sample_size = 0

    rng = random.Random(args.seed)
    if args.sample_size and args.sample_size > 0 and args.sample_size < len(rows):
        rows = rng.sample(rows, args.sample_size)

    # Bei großen Datenmengen (alle BLS Items) automatisch weeks erhöhen
    # sodass die Aufteilung sinnvoll bleibt
    effective_weeks = getattr(args, "weeks", 1)
    if args.sample_size == 0:  # Alle Items
        total_items = len(rows)
        items_per_day_target = 50  # Ziel: 50 Items pro Tag für große Tests
        total_slots_needed = (total_items + items_per_day_target - 1) // items_per_day_target
        effective_weeks = max(1, (total_slots_needed + len(WEEKDAYS) - 1) // len(WEEKDAYS))
        print(f"Alle {total_items} BLS-Items werden auf {effective_weeks} Wochen verteilt...")

    names = [row["name"] for row in rows]
    menu_types = [part.strip() for part in str(args.menu_types).split(",") if part.strip()]
    plan = build_week_plan(
        names,
        seed=args.seed,
        weeks=effective_weeks,
        menu_types=menu_types,
        stress_profile=args.stress_profile,
    )
    code_letter_map = load_code_letter_mapping(args.mapping_json)

    enriched, stats = enrich_plan(plan, bls_db_path=args.bls_db, code_letter_map=code_letter_map)
    summary = summarize(enriched, stats, len(names))

    print("Quantitativer BLS-Test")
    print(f"BLS-DB: {args.bls_db}")
    print(f"Gesamtgerichte: {summary['total_items']}")
    print(f"Erkannt: {summary['final_recognition_count']} ({summary['final_recognition_rate']:.2%})")
    print(f"Über BLS-Code erkannt: {summary['bls_code_match_count']} ({summary['bls_code_match_rate']:.2%})")
    print(f"Unverändert unzugeordnet: {summary['still_unmapped_count']} ({summary['still_unmapped_rate']:.2%})")
    print(f"Mehrfach zugeordnete Gerichte: {summary['multi_group_items']} ({summary['multi_group_rate']:.2%})")



    if summary.get("unmapped_reason_counts"):
        print("\nHauptgründe für Nicht-Erkennung:")
        for reason, count in summary["unmapped_reason_counts"][:10]:
            print(f"- {reason}: {count}")
            # Zeige bis zu 3 Beispiele pro Fehlergrund
            examples = summary.get("unmapped_by_reason", {}).get(reason, [])
            if examples:
                for ex in examples[:3]:
                    print(f"    • {ex[:70]}")
                if len(examples) > 3:
                    print(f"    ... und {len(examples) - 3} weitere")

    print("\nTop Primärgruppen:")
    for group, count in summary["group_distribution"][:10]:
        print(f"- {group}: {count}")

    # Pro-Woche Übersicht mit erkannten/nicht erkannten Gerichten (optional)
    if args.show_weeks and summary.get("per_week"):
        print("\n" + "=" * 80)
        print("WOCHEN-DETAIL")
        print("=" * 80)
        for week_data in summary["per_week"]:
            wk = week_data.get("week_index", 0)
            tot = week_data.get("total_items", 0)
            final_rate = week_data.get("final_recognition_rate", 0.0)
            recognized = week_data.get("items_recognized", [])
            unmapped = week_data.get("items_unmapped", [])

            print(f"\n### Woche {wk + 1} (insgesamt {tot} Gerichte, erkannt {final_rate:.1%})")
            
            if recognized:
                print(f"  ✓ Erkannt ({len(recognized)}):")
                for item in recognized[:10]:  # max. 10 pro Konsole
                    groups_str = ", ".join(item.get("groups", []))
                    conf = item.get("confidence", 0)
                    print(f"    • {item['name'][:50]:50s} → {groups_str:20s} (conf: {conf:.2f})")
                if len(recognized) > 10:
                    print(f"    ... und {len(recognized) - 10} weitere")
            
            if unmapped:
                print(f"  ✗ Nicht erkannt ({len(unmapped)}):")
                for item in unmapped[:10]:  # max. 10 pro Konsole
                    print(f"    • {item['name'][:60]}")
                if len(unmapped) > 10:
                    print(f"    ... und {len(unmapped) - 10} weitere")

    if summary["sample_unmapped"]:
        print("\nBeispiel für unzugeordnete Gerichte (gesamt):")
        for name in summary["sample_unmapped"][:10]:
            print(f"- {name}")

    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "stats": stats,
                    "seed": args.seed,
                    "sample_size": args.sample_size,
                    "weeks": getattr(args, "weeks", 1),
                    "menu_types": menu_types,
                    "stress_profile": args.stress_profile,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nReport geschrieben: {args.report_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())