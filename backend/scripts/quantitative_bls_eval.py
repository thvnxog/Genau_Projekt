"""Quantitativer BLS-Test für das Enrichment.

Das Skript lädt Gerichtsnamen aus der BLS-Datenbank, baut daraus einen
synthetischen Wochenplan und misst, wie viele Einträge aktuell erkannt werden.

Warum das nützlich ist:
- Es ist wiederholbar und liefert eine Terminal-Metrik.
- Es testet die reale BLS-Datenbasis statt handgeschriebener Beispiele.
- Es misst sowohl die direkte Keyword-Erkennung als auch den BLS-Fallback.

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
from collections import Counter
from pathlib import Path
from typing import Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.enrich_foodplan import (  # noqa: E402
    detect_table_and_columns,
    enrich_plan,
    load_json_mapping,
    load_keyword_files,
    merge_keywords,
)


WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]


def default_bls_db_path() -> Path:
    return BACKEND_DIR / "instance" / "bls.db"


def load_bls_rows(db_path: Path) -> list[dict]:
    """Lädt alle BLS-Zeilen aus der SQLite-Datenbank."""

    if not db_path.exists():
        raise FileNotFoundError(f"BLS-Datenbank nicht gefunden: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        table, name_col, id_col = detect_table_and_columns(conn)
        if not table or not name_col:
            raise RuntimeError("Konnte keine passende BLS-Tabelle/Spalte erkennen.")

        select_cols = [name_col]
        if id_col:
            select_cols.append(id_col)

        order_col = id_col or name_col
        sql = f"SELECT {', '.join(select_cols)} FROM {table} ORDER BY {order_col}"
        rows = conn.execute(sql).fetchall()

        items: list[dict] = []
        for row in rows:
            name = str(row[0]).strip()
            if not name:
                continue

            food_id = row[1] if id_col else None
            items.append({"id": food_id, "name": name})

        return items
    finally:
        conn.close()


def build_week_plan(names: Iterable[str], seed: int | None = None) -> dict:
    """Verpackt Gerichtsnamen in einen künstlichen Wochenplan."""

    items = [{"raw_text": name, "portion": {"value": 100, "unit": "g"}, "food_groups": [], "links": {}, "tags": []} for name in names]

    rng = random.Random(seed)
    rng.shuffle(items)

    days: list[dict] = []
    chunks = max(1, len(items) // len(WEEKDAYS) + (1 if len(items) % len(WEEKDAYS) else 0))

    for idx, weekday in enumerate(WEEKDAYS):
        start = idx * chunks
        end = min(start + chunks, len(items))
        day_items = items[start:end]
        days.append(
            {
                "weekday": weekday,
                "week_index": 0,
                "menus": [
                    {
                        "menu_type": "mischkost",
                        "items": day_items,
                    }
                ],
            }
        )

    return {"schema_version": "1.0", "days": days}


def build_keywords(root: Path, mapping_json: Path | None) -> tuple[dict, dict]:
    group_txt = load_keyword_files(root / "groups")
    tag_txt = load_keyword_files(root / "tags")

    group_json: dict = {}
    tag_json: dict = {}
    if mapping_json and mapping_json.exists():
        group_json, tag_json = load_json_mapping(mapping_json)

    return merge_keywords(group_txt, group_json), merge_keywords(tag_txt, tag_json)


def summarize(enriched: dict, stats: dict, total_items: int) -> dict:
    items = [item for day in enriched.get("days", []) for menu in day.get("menus", []) for item in menu.get("items", [])]

    group_counter = Counter()
    primary_counter = Counter()
    multi_group_items = 0
    unmapped_names: list[str] = []

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

    direct_recognition = total_items - int(stats.get("unmapped_before_bls", 0))
    final_recognition = int(stats.get("mapped_groups", 0))
    via_bls = int(stats.get("mapped_via_bls", 0))
    still_unmapped = int(stats.get("still_unmapped", 0))

    return {
        "total_items": total_items,
        "direct_recognition_count": direct_recognition,
        "direct_recognition_rate": round(direct_recognition / total_items, 4) if total_items else 0.0,
        "final_recognition_count": final_recognition,
        "final_recognition_rate": round(final_recognition / total_items, 4) if total_items else 0.0,
        "bls_fallback_count": via_bls,
        "bls_fallback_rate": round(via_bls / total_items, 4) if total_items else 0.0,
        "still_unmapped_count": still_unmapped,
        "still_unmapped_rate": round(still_unmapped / total_items, 4) if total_items else 0.0,
        "multi_group_items": multi_group_items,
        "multi_group_rate": round(multi_group_items / total_items, 4) if total_items else 0.0,
        "group_distribution": primary_counter.most_common(),
        "all_group_distribution": group_counter.most_common(),
        "sample_unmapped": unmapped_names[:20],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quantitativer BLS-Test für das Foodplan-Enrichment")
    parser.add_argument("--bls-db", type=Path, default=default_bls_db_path(), help="Pfad zur SQLite-BLS-Datenbank")
    parser.add_argument("--keywords-root", type=Path, default=BACKEND_DIR / "rules" / "keywords", help="Keyword-Ordner mit groups/ und tags/")
    parser.add_argument("--mapping-json", type=Path, default=BACKEND_DIR / "rules" / "bls_to_dge_groups.json", help="Optionales JSON-Mapping")
    parser.add_argument("--all", action="store_true", help="Alle BLS-Gerichte testen (Default)")
    parser.add_argument("--sample-size", type=int, default=0, help="Zufällige Teilmenge der BLS-Gerichte (0 = alle)")
    parser.add_argument("--seed", type=int, default=42, help="Seed für reproduzierbare Zufallsauswahl")
    parser.add_argument("--report-out", type=Path, default=None, help="Optional: JSON-Report auf Disk schreiben")
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

    names = [row["name"] for row in rows]
    plan = build_week_plan(names, seed=args.seed)
    group_keywords, tag_keywords = build_keywords(args.keywords_root, args.mapping_json)

    enriched, stats = enrich_plan(plan, group_keywords, tag_keywords, args.bls_db)
    summary = summarize(enriched, stats, len(names))

    print("Quantitativer BLS-Test")
    print(f"BLS-DB: {args.bls_db}")
    print(f"Gesamtgerichte: {summary['total_items']}")
    print(f"Direkt erkannt: {summary['direct_recognition_count']} ({summary['direct_recognition_rate']:.2%})")
    print(f"Final erkannt inkl. BLS-Fallback: {summary['final_recognition_count']} ({summary['final_recognition_rate']:.2%})")
    print(f"Über BLS-Fallback erkannt: {summary['bls_fallback_count']} ({summary['bls_fallback_rate']:.2%})")
    print(f"Unverändert unzugeordnet: {summary['still_unmapped_count']} ({summary['still_unmapped_rate']:.2%})")
    print(f"Mehrfach zugeordnete Gerichte: {summary['multi_group_items']} ({summary['multi_group_rate']:.2%})")

    print("\nTop Primärgruppen:")
    for group, count in summary["group_distribution"][:10]:
        print(f"- {group}: {count}")

    if summary["sample_unmapped"]:
        print("\nBeispiel für unzugeordnete Gerichte:")
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