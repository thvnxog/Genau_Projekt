"""backend/scripts/enrich_foodplan.py

Enrichment-Skript für `foodplan.json`.

Ziel:
- Aus freiem Text (`item.raw_text`) sollen strukturierte Signale abgeleitet werden:
  - `item.links.food_group`  (z.B. "vegetables", "meat", ...)
  - `item.tags`              (z.B. "raw_veg", "fish", ...)
  - außerdem ein Confidence-Score

Wie passiert das?
1) Text-Normalisierung + Tokenisierung
2) Keyword-Matching über vordefinierte Keyword-Listen
   - Gruppen-Keywords: `rules/keywords/groups/*.txt`
   - Tag-Keywords:     `rules/keywords/tags/*.txt`
3) Optionaler Fallback über die BLS-DB (SQLite):
   - Wenn kein Keyword-Match greift, versuchen wir einen groben DB-Lookup,
     nehmen den besten Treffer-Namen und matchen darauf nochmal.

Input:
- `foodplan.json`

Output:
- `foodplan.enriched.json`

Erwartetes Item-Format im Plan:
  { "raw_text": "...", "links": {...}, "tags": [...] }

CLI Beispiel:
  python3 backend/scripts/enrich_foodplan.py \
    --in backend/instance/testdata/foodplan.json \
    --out backend/instance/testdata/foodplan.enriched.json \
    --mapping-json backend/rules/bls_to_dge_groups.json \
    --keywords-root backend/rules/keywords \
    --bls-db backend/instance/bls.db
"""

import argparse
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Text Normalisierung
# -----------------------------

# Stopwords sind häufige Wörter, die kaum semantische Bedeutung für das Matching haben.
# Durch das Entfernen reduzieren wir Rauschen in den Tokens.
STOPWORDS = {
    "mit",
    "und",
    "in",
    "vom",
    "von",
    "nach",
    "art",
    "im",
    "an",
    "der",
    "die",
    "das",
    "auf",
    "für",
    "zu",
    "oder",
    "sowie",
    "inkl",
    "inkl.",
    "ca",
    "ca.",
    "tk",
    "bio",
}


def normalize_text(s: str) -> str:
    """Normalisiert Eingabetext für robustes Matching.

    Schritte:
    - lowercasing
    - trim
    - Unicode Normalisierung (NFKC) für konsistentere Zeichenrepräsentation
    - mehrfach spaces reduzieren

    Ergebnis: ein stabiler String, der besser für Tokenisierung/Vergleiche geeignet ist.
    """

    if not s:
        return ""
    s = s.strip().lower()
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    return s


def tokenize(s: str) -> List[str]:
    """Zerlegt Text in Tokens.

    - Trennt an Nicht-Buchstaben/Ziffern
    - Entfernt Stopwords

    Beispiel:
      "Kartoffeln mit Gemüse" -> ["kartoffeln", "gemüse"]
    """

    s = normalize_text(s)
    raw_tokens = re.split(r"[^a-z0-9äöüß]+", s, flags=re.IGNORECASE)
    tokens: List[str] = []
    for t in raw_tokens:
        t = t.strip()
        if not t:
            continue
        if t in STOPWORDS:
            continue
        tokens.append(t)
    return tokens


def token_matches_keyword(token: str, kw: str) -> bool:
    """"Stemming light" Match zwischen Token und Keyword.

    Idee: Keine echte linguistische Stemming-Library, sondern pragmatische Regeln:
    - token == kw
    - token startswith kw   ("kartoffeln" startswith "kartoffel")
    - token contains kw     ("gemüselasagne" enthält "gemüse")
    """

    if not token or not kw:
        return False
    if token == kw:
        return True
    if token.startswith(kw):
        return True
    if kw in token:
        return True
    return False


# -----------------------------
# Keyword-Lader
# -----------------------------

def load_keyword_files(folder: Path) -> Dict[str, List[str]]:
    """Lädt Keyword-Listen aus einem Ordner (`*.txt`).

    Konvention:
    - Dateiname ohne Endung wird zum Key
      z.B. `vegetables.txt` -> key "vegetables"

    Dateiinhalt:
    - je Zeile ein Keyword
    - leere Zeilen und Kommentare (#...) werden ignoriert
    """

    data: Dict[str, List[str]] = {}
    if not folder.exists():
        return data

    for p in sorted(folder.glob("*.txt")):
        key = p.stem
        lines: List[str] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = normalize_text(line)
            if not line or line.startswith("#"):
                continue
            lines.append(line)

        # Duplikate entfernen und stabil sortieren
        data[key] = sorted(set(lines))

    return data


# -----------------------------
# Optional: JSON-Mapping zusätzlich laden
# (wir "mergen" Keywords aus JSON + .txt)
# -----------------------------

def load_json_mapping(path: Path) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Lädt optional Keyword-Listen aus einem JSON-Mapping.

    Erwartete Struktur:
      {
        "mapping": [{"dge_food_group": "...", "match": {"contains_any": [...] }}, ...],
        "tags":    [{"tag": "...",           "match": {"contains_any": [...] }}, ...]
      }

    Rückgabe:
      group_keywords[group] = [...]
      tag_keywords[tag]     = [...]

    Das wird später mit den .txt Keywords zusammengeführt (merge_keywords).
    """

    if not path.exists():
        return {}, {}

    obj = json.loads(path.read_text(encoding="utf-8"))
    group_kw: Dict[str, List[str]] = {}
    tag_kw: Dict[str, List[str]] = {}

    for r in obj.get("mapping", []) or []:
        g = r.get("dge_food_group")
        kws = (r.get("match", {}) or {}).get("contains_any", []) or []
        if g:
            group_kw.setdefault(g, [])
            group_kw[g].extend([normalize_text(k) for k in kws if k])

    for r in obj.get("tags", []) or []:
        t = r.get("tag")
        kws = (r.get("match", {}) or {}).get("contains_any", []) or []
        if t:
            tag_kw.setdefault(t, [])
            tag_kw[t].extend([normalize_text(k) for k in kws if k])

    # dedupe
    group_kw = {k: sorted(set(v)) for k, v in group_kw.items()}
    tag_kw = {k: sorted(set(v)) for k, v in tag_kw.items()}
    return group_kw, tag_kw


def merge_keywords(a: Dict[str, List[str]], b: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Merged zwei Keyword-Dicts (key->list) und dedupliziert."""

    out: Dict[str, List[str]] = {}
    keys = set(a.keys()) | set(b.keys())
    for k in keys:
        out[k] = sorted(set((a.get(k, []) or []) + (b.get(k, []) or [])))
    return out


# -----------------------------
# Matching: Best Group + Tags
# -----------------------------

@dataclass
class MatchResult:
    """Ergebnis eines Group-Matches."""

    key: Optional[str]
    score: float
    hits: int


def score_keywords(tokens: List[str], keywords: List[str]) -> int:
    """Zählt, wie viele Keywords in den Tokens "irgendwie" matchen.

    Wichtig:
    - max. 1 Hit pro Keyword (sonst könnte ein Keyword mehrfach zählen)
    """

    hits = 0
    for kw in keywords:
        for tok in tokens:
            if token_matches_keyword(tok, kw):
                hits += 1
                break
    return hits


def pick_best_group(raw_text: str, group_keywords: Dict[str, List[str]]) -> MatchResult:
    """Ermittelt die beste DGE-Gruppe für `raw_text`.

    Strategie:
    - Tokenize raw_text
    - Für jede Gruppe: zähle Keyword-Hits
    - Nimm Gruppe mit den meisten Hits

    Score:
    - grober Confidence-Score: hits / (#keywords der Gruppe), gekappt auf 1.0
    """

    tokens = tokenize(raw_text)
    best_key: Optional[str] = None
    best_hits = 0
    best_kw_len = 0

    for group, kws in group_keywords.items():
        if not kws:
            continue
        hits = score_keywords(tokens, kws)
        if hits > best_hits:
            best_hits = hits
            best_key = group
            best_kw_len = len(kws)

    score = 0.0
    if best_key and best_kw_len > 0:
        score = min(1.0, best_hits / max(1, best_kw_len))

    return MatchResult(best_key, score, best_hits)


def collect_tags(raw_text: str, tag_keywords: Dict[str, List[str]]) -> List[str]:
    """Sammelt alle Tags, deren Keyword-Liste mindestens einen Hit hat."""

    tokens = tokenize(raw_text)
    tags: List[str] = []
    for tag, kws in tag_keywords.items():
        if not kws:
            continue
        hits = score_keywords(tokens, kws)
        if hits > 0:
            tags.append(tag)
    return sorted(set(tags))


# -----------------------------
# Optional: BLS-Fallback (SQLite)
# - versucht Tabellen/Spalten automatisch zu finden
# -----------------------------

# Heuristiken: mögliche Spaltennamen in der DB
COMMON_NAME_COLS = [
    "Lebensmittelbezeichnung",
    "lebensmittelbezeichnung",
    "name",
    "bezeichnung",
    "lebensmittel",
]
COMMON_ID_COLS = ["id", "ID", "key", "schluessel", "schlüssel", "code"]


def detect_table_and_columns(
    conn: sqlite3.Connection,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Versucht in der BLS-DB die passende Tabelle/Spalten zu finden.

    Vorgehen:
    - Tabellen aus sqlite_master lesen
    - Für jede Tabelle: PRAGMA table_info -> Spaltennamen
    - Erste Tabelle mit einer Namensspalte wird genommen

    Rückgabe:
    - (table_name, name_col, id_col)
    """

    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = [t[0] for t in tables]

    for t in tables:
        cols = cur.execute(f"PRAGMA table_info('{t}')").fetchall()
        colnames = [c[1] for c in cols]

        name_col = next((c for c in colnames if c in COMMON_NAME_COLS), None)
        if name_col:
            id_col = next((c for c in colnames if c in COMMON_ID_COLS), None)
            return t, name_col, id_col

    return None, None, None


def bls_best_match(
    conn: sqlite3.Connection, query_text: str, limit: int = 10
) -> Tuple[Optional[str], Optional[str]]:
    """Sehr einfacher BLS-Fallback über SQLite.

    Idee:
    - Wir suchen Kandidaten über LIKE %token%
    - Dann ranken wir Kandidaten danach, wie viele Tokens matchen

    Rückgabe:
    - (best_id, best_name)

    Hinweis:
    - Das ist bewusst simpel (MVP) und nicht "fuzzy matching" im wissenschaftlichen Sinn.
    """

    t, name_col, id_col = detect_table_and_columns(conn)
    if not t or not name_col:
        return None, None

    tokens = tokenize(query_text)
    if not tokens:
        return None, None

    # Kandidaten holen: OR-LIKE über Tokens
    where_parts: List[str] = []
    params: List[str] = []
    for tok in tokens[:6]:  # limit, damit Query nicht explodiert
        where_parts.append(f"LOWER({name_col}) LIKE ?")
        params.append(f"%{tok}%")

    where_sql = " OR ".join(where_parts)
    sql = (
        f"SELECT {name_col}{',' + id_col if id_col else ''} "
        f"FROM {t} WHERE {where_sql} LIMIT {limit}"
    )

    cur = conn.cursor()
    rows = cur.execute(sql, params).fetchall()

    # best = (id, name, hits)
    best: Tuple[Optional[str], Optional[str], int] = (None, None, -1)

    for row in rows:
        name = row[0]
        rid = row[1] if id_col else None

        hits = 0
        name_norm = normalize_text(str(name))
        name_tokens = tokenize(name_norm)

        for tok in tokens:
            # symmetrischer Contains/Startswith-Check über token_matches_keyword
            if any(
                token_matches_keyword(nt, tok) or token_matches_keyword(tok, nt)
                for nt in name_tokens
            ):
                hits += 1

        if hits > best[2]:
            best = (rid, str(name), hits)

    return best[0], best[1]


# -----------------------------
# Enrichment Pipeline
# -----------------------------

def enrich_plan(
    plan: dict,
    group_keywords: Dict[str, List[str]],
    tag_keywords: Dict[str, List[str]],
    bls_db_path: Optional[Path] = None,
) -> Tuple[dict, dict]:
    """Enriched den gesamten Plan.

    Für jedes Item:
    1) Keyword-Matching über raw_text
    2) optional: BLS-Fallback, falls keine Gruppe gefunden wurde
    3) Ergebnis in `item.links` und `item.tags` zurückschreiben

    Rückgabe:
    - (enriched_plan, stats)
    """

    stats = {
        "total_items": 0,
        "mapped_groups": 0,
        "unmapped_before_bls": 0,
        "mapped_via_bls": 0,
        "still_unmapped": 0,
    }

    # Optional DB-Verbindung
    conn: Optional[sqlite3.Connection] = None
    if bls_db_path:
        if bls_db_path.exists():
            conn = sqlite3.connect(str(bls_db_path))
        else:
            print(f"⚠️ BLS DB nicht gefunden: {bls_db_path} (Fallback deaktiviert)")

    for day in plan.get("days", []):
        for menu in day.get("menus", []):
            for item in menu.get("items", []):
                stats["total_items"] += 1
                raw = item.get("raw_text", "") or ""

                # 1) normaler Keyword-Match
                group_res = pick_best_group(raw, group_keywords)
                tags = collect_tags(raw, tag_keywords)

                # 2) optional BLS-Fallback, wenn keine Gruppe gefunden
                used_bls = False
                bls_id = None
                bls_name = None

                if not group_res.key:
                    stats["unmapped_before_bls"] += 1
                    if conn:
                        bls_id, bls_name = bls_best_match(conn, raw)
                        if bls_name:
                            # Versuch nochmal über BLS-Name zu mappen
                            group_res = pick_best_group(bls_name, group_keywords)
                            tags = sorted(
                                set(tags + collect_tags(bls_name, tag_keywords))
                            )
                            used_bls = True

                # 3) writeback: Ergebnisse ins Item schreiben
                links = item.get("links") or {}
                links["food_group"] = group_res.key
                links["confidence"] = group_res.score

                # Falls BLS benutzt wurde, behalten wir Debug-Infos
                if used_bls:
                    links["bls_id"] = bls_id
                    links["bls_name"] = bls_name

                item["links"] = links
                item["tags"] = sorted(set((item.get("tags") or []) + tags))

                if group_res.key:
                    stats["mapped_groups"] += 1
                    if used_bls:
                        stats["mapped_via_bls"] += 1
                else:
                    stats["still_unmapped"] += 1

    if conn:
        conn.close()

    return plan, stats


def main():
    """CLI Entry-Point."""

    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input foodplan.json")
    ap.add_argument("--out", dest="out", required=True, help="Output enriched json")
    ap.add_argument(
        "--mapping-json",
        dest="mapping_json",
        required=False,
        help="Optional: bls_to_dge_groups.json (wird mit .txt Keywords gemerged)",
    )
    ap.add_argument(
        "--keywords-root",
        dest="kwroot",
        default="rules/keywords",
        help="Ordner mit keywords/groups und keywords/tags (default: rules/keywords)",
    )
    ap.add_argument(
        "--bls-db",
        dest="blsdb",
        required=False,
        help="Optional: Pfad zur SQLite BLS DB (Fallback), z.B. instance/bls.db",
    )
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    kwroot = Path(args.kwroot)

    # Input-Plan laden
    plan = json.loads(inp.read_text(encoding="utf-8"))

    # 1) Keywords aus TXT
    group_txt = load_keyword_files(kwroot / "groups")
    tag_txt = load_keyword_files(kwroot / "tags")

    # 2) optional Keywords aus JSON (werden gemerged)
    group_json: Dict[str, List[str]] = {}
    tag_json: Dict[str, List[str]] = {}
    if args.mapping_json:
        group_json, tag_json = load_json_mapping(Path(args.mapping_json))

    group_keywords = merge_keywords(group_txt, group_json)
    tag_keywords = merge_keywords(tag_txt, tag_json)

    # 3) enrichment durchführen
    bls_db_path = Path(args.blsdb) if args.blsdb else None
    enriched, stats = enrich_plan(plan, group_keywords, tag_keywords, bls_db_path)

    # Output schreiben
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

    print("✅ Enrichment fertig!")
    print(f"Input:  {inp}")
    print(f"Output: {out}")
    print(f"Stats:  {stats}")


if __name__ == "__main__":
    main()
