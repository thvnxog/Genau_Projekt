"""backend/scripts/enrich_foodplan.py

Enrichment für `foodplan.json` auf Basis der BLS-Datenbank.

Ablauf pro Item:
1) `raw_text` wird gegen die BLS-DB gematcht.
2) Der erste Buchstabe des BLS-Codes wird über `code_letter_mapping`
     auf DGE-Gruppen abgebildet.
3) `food_groups`, `links.food_group`, `links.confidence` und Debug-Felder
     werden ins Item geschrieben.

Es gibt keinen Keyword-Fallback mehr.
"""

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Text Normalisierung
# -----------------------------


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


def fold_umlauts(s: str) -> str:
    """Erzeugt eine ASCII-nahe Vergleichsform (ä->ae, ö->oe, ü->ue, ß->ss)."""

    if not s:
        return ""
    return (
        s.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def tokenize(s: str) -> List[str]:
    """Zerlegt Text in Tokens.

    - Trennt an Nicht-Buchstaben/Ziffern
    - entfernt sehr kurze Tokens

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
        if len(t) < 2:
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
    token_variants = {token, fold_umlauts(token)}
    kw_variants = {kw, fold_umlauts(kw)}

    for tok in token_variants:
        if not tok:
            continue
        for key in kw_variants:
            if not key:
                continue
            if tok == key:
                return True
            if tok.startswith(key):
                return True
            if key in tok:
                return True
    return False


def load_code_letter_mapping(path: Path) -> Dict[str, List[str]]:
    """Lädt das Mapping von BLS-Code-Buchstaben zu DGE-Gruppen."""

    if not path.exists():
        return {}

    obj = json.loads(path.read_text(encoding="utf-8"))
    mapping = obj.get("code_letter_mapping") or {}
    out: Dict[str, List[str]] = {}
    for k, v in mapping.items():
        if not k:
            continue
        out[k.strip().upper()] = v if isinstance(v, list) else [v]
    return out


def split_candidate_phrases(raw_text: str) -> List[str]:
    """Teilt einen Gerichtsnamen in grobe Kandidatenphrasen.

    Ziel ist nicht perfekte Linguistik, sondern ein robuster Heuristik-Schritt,
    damit zusammengesetzte Namen wie "Hähnchen mit Reis" als mehrere BLS-Kandidaten
    geprüft werden können.
    """

    if not raw_text:
        return []

    text = normalize_text(raw_text)
    parts = re.split(r"\s*(?:/|\+|,|;|:|\bund\b|\bmit\b|\boder\b|\bsowie\b|\bbzw\.?\b)\s*", text)

    cleaned: List[str] = []
    for part in parts:
        candidate = part.strip()
        if candidate:
            cleaned.append(candidate)

    return cleaned or ([text] if text else [])


def find_bls_matches_for_text(conn: sqlite3.Connection, raw_text: str) -> List[Tuple[Optional[str], Optional[str], Optional[str]]]:
    """Sucht BLS-Treffer für den Gesamttext und seine Kandidatenphrasen.

    Rückgabe: Liste von (code, name, id) in Fundreihenfolge, ohne Duplikate.
    """

    matches: List[Tuple[Optional[str], Optional[str], Optional[str]]] = []
    seen: set[Tuple[Optional[str], Optional[str], Optional[str]]] = set()

    for phrase in split_candidate_phrases(raw_text):
        code, name, rid = bls_best_match(conn, phrase)
        if not code or not name:
            continue
        match = (code, name, rid)
        if match in seen:
            continue
        seen.add(match)
        matches.append(match)

    return matches

ADDITIONAL_NOTE_TAG_PATTERNS = {
    "bio": [r"\bbio\b"],
    "wholegrain": [r"\bvk\b", r"\bvollkorn\b"],
    "lean_meat": [r"\bm\b", r"\bmageres muskelfleisch\b", r"\bmager\b"],
    "fried_or_breaded": [r"\bpf\b", r"\bpaniert\b", r"\bfrittiert\b"],
    "frozen": [r"\btk\b", r"\btiefk[üu]hl\b", r"\btiefkuehl\b"],
    "fresh": [r"\bfrisch\b"],
    "canned": [r"\bkonserve\b", r"\bkonserven\b"],
}


def collect_note_tags(notes: List[str]) -> List[str]:
    """Leitet Tags aus der Zusatz-/Notizspalte ab.

    Die Excel-Vorlage enthält dort typischerweise kurze Kürzel oder Hinweise
    wie "Bio", "VK", "M" oder "TK". Diese werden in reguläre Tags
    überführt, damit die spätere Bewertung unabhängig vom Excel-Format arbeitet.
    """

    if not notes:
        return []

    note_text = normalize_text(" ".join(str(note) for note in notes if note))
    if not note_text:
        return []

    tags: List[str] = []
    for tag, patterns in ADDITIONAL_NOTE_TAG_PATTERNS.items():
        if any(re.search(pattern, note_text) for pattern in patterns):
            tags.append(tag)

    return sorted(set(tags))


COMMON_NAME_COLS = [
    "name_de",
    "Lebensmittelbezeichnung",
    "lebensmittelbezeichnung",
    "name",
    "bezeichnung",
    "lebensmittel",
]
COMMON_ID_COLS = ["id", "ID", "key", "schluessel", "schlüssel", "code"]


def detect_table_and_columns(
    conn: sqlite3.Connection,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Versucht in der BLS-DB die passende Tabelle/Spalten zu finden.

    Vorgehen:
    - Tabellen aus sqlite_master lesen
    - Für jede Tabelle: PRAGMA table_info -> Spaltennamen
    - Erste Tabelle mit einer Namensspalte wird genommen

    Rückgabe:
    - (table_name, name_col, id_col, code_col)
    """

    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = [t[0] for t in tables]

    if "foods" in tables:
        cols = cur.execute("PRAGMA table_info('foods')").fetchall()
        colnames = [c[1] for c in cols]
        if "name_de" in colnames:
            id_col = next((c for c in colnames if c in COMMON_ID_COLS), None)
            code_col = "code" if "code" in colnames else None
            return "foods", "name_de", id_col, code_col

    for t in tables:
        cols = cur.execute(f"PRAGMA table_info('{t}')").fetchall()
        colnames = [c[1] for c in cols]

        name_col = next((c for c in colnames if c in COMMON_NAME_COLS), None)
        if name_col:
            id_col = next((c for c in colnames if c in COMMON_ID_COLS), None)
            code_col = "code" if "code" in colnames else None
            return t, name_col, id_col, code_col

    return None, None, None, None


def bls_best_match(
    conn: sqlite3.Connection, query_text: str, limit: int = 10
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """BLS-Matcher über SQLite.

    - Wir suchen Kandidaten über LIKE %token%
    - Dann ranken wir Kandidaten danach, wie viele Tokens matchen

    Rückgabe:
    - (best_code, best_name, best_id)
    """

    t, name_col, id_col, code_col = detect_table_and_columns(conn)
    if not t or not name_col:
        return None, None, None

    tokens = tokenize(query_text)
    if not tokens:
        return None, None, None

    # Kandidaten holen: OR-LIKE über Tokens
    where_parts: List[str] = []
    params: List[str] = []
    for tok in tokens[:6]:  # limit, damit Query nicht explodiert
        where_parts.append(f"LOWER({name_col}) LIKE ?")
        params.append(f"%{tok}%")

    where_sql = " OR ".join(where_parts)
    select_cols = [name_col]
    if code_col:
        select_cols.append(code_col)
    if id_col:
        select_cols.append(id_col)
    sql = f"SELECT {', '.join(select_cols)} FROM {t} WHERE {where_sql} LIMIT {limit}"

    cur = conn.cursor()
    rows = cur.execute(sql, params).fetchall()

    # best = (code, name, id, hits)
    best: Tuple[Optional[str], Optional[str], Optional[str], int] = (None, None, None, -1)

    for row in rows:
        name = row[0]
        code = row[1] if code_col and len(row) > 1 else None
        rid = None
        if code_col and id_col and len(row) > 2:
            rid = row[2]
        elif id_col and len(row) > 1 and not code_col:
            rid = row[1]

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

        if hits > best[3]:
            best = (code, str(name), rid, hits)

    return best[0], best[1], best[2]


# -----------------------------
# Enrichment Pipeline
# -----------------------------

def enrich_plan(
    plan: dict,
    bls_db_path: Optional[Path] = None,
    code_letter_map: Optional[Dict[str, List[str]]] = None,
) -> Tuple[dict, dict]:
    """Enriched den gesamten Plan per BLS-Code-Letter-Mapping."""

    stats = {"total_items": 0, "mapped_groups": 0, "mapped_via_bls": 0, "still_unmapped": 0}
    code_letter_map = code_letter_map or {}

    conn: Optional[sqlite3.Connection] = None
    if bls_db_path:
        if bls_db_path.exists():
            conn = sqlite3.connect(str(bls_db_path))
        else:
            print(f"BLS DB nicht gefunden: {bls_db_path}")

    for day in plan.get("days", []):
        for menu in day.get("menus", []):
            for item in menu.get("items", []):
                stats["total_items"] += 1

                raw_text = item.get("raw_text", "") or ""
                tags = sorted(set(collect_note_tags(item.get("notes") or [])))

                groups: List[str] = []
                bls_matches = []

                if conn:
                    bls_matches = find_bls_matches_for_text(conn, raw_text)
                    for bls_code, bls_name, bls_id in bls_matches:
                        if not bls_code:
                            continue
                        code = str(bls_code).strip()
                        if not code:
                            continue
                        letter = code[0].upper()
                        mapped_groups = code_letter_map.get(letter, [])
                        for group in mapped_groups:
                            if group not in groups:
                                groups.append(group)

                links = item.get("links") or {}
                links["food_group"] = groups[0] if groups else None
                links["confidence"] = 1.0 if groups else 0.0
                if bls_matches:
                    first_code, first_name, first_id = bls_matches[0]
                    links["bls_id"] = first_id
                    links["bls_name"] = first_name
                    links["bls_matches"] = [
                        {"code": code, "name": name, "id": rid}
                        for code, name, rid in bls_matches
                    ]

                item["food_groups"] = groups
                item["links"] = links
                item["tags"] = sorted(set((item.get("tags") or []) + tags))

                if groups:
                    stats["mapped_groups"] += 1
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
        required=True,
        help="bls_to_dge_groups.json mit code_letter_mapping",
    )
    ap.add_argument(
        "--bls-db",
        dest="blsdb",
        required=True,
        help="Pfad zur SQLite BLS DB (erforderlich für BLS-only mapping), z.B. instance/bls.db",
    )
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)

    plan = json.loads(inp.read_text(encoding="utf-8"))

    code_letter_map = load_code_letter_mapping(Path(args.mapping_json))

    bls_db_path = Path(args.blsdb)
    enriched, stats = enrich_plan(plan, bls_db_path=bls_db_path, code_letter_map=code_letter_map)

    # Output schreiben
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Enrichment fertig!")
    print(f"Input:  {inp}")
    print(f"Output: {out}")
    print(f"Stats:  {stats}")


if __name__ == "__main__":
    main()
