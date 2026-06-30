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
from functools import lru_cache
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


def _candidate_forms(token: str) -> List[str]:
    """Erzeugt wenige einfache Normalformen für einen Kandidaten."""

    forms = [token]
    for suffix in ("en", "er", "es", "e", "n", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            forms.append(token[: -len(suffix)])
    unique_forms: List[str] = []
    seen: set[str] = set()
    for form in forms:
        if form in seen:
            continue
        seen.add(form)
        unique_forms.append(form)
    return unique_forms


def compound_token_variants(
    token: str, known_terms: Optional[set[str]] = None
) -> List[str]:
    """Erzeugt Fallback-Varianten für zusammengesetzte Tokens.

    Direkte Treffer bleiben Vorrang. Wenn ein Token wie `saatenbrot` keinen
    Direkttreffer liefert, helfen nur noch Teilstücke weiter, die auch wirklich
    als bekannte BLS-Wörter vorkommen.

    Ohne `known_terms` wird kein wildes Zerschneiden gemacht, sondern nur das
    Originaltoken zurückgegeben.
    """

    token = normalize_text(token)
    if not token:
        return []

    variants = [token]
    if len(token) < 10 or not known_terms:
        return variants

    known_terms_norm = {normalize_text(term) for term in known_terms if term}

    best_suffix: Optional[str] = None
    best_prefix: Optional[str] = None

    for split_pos in range(4, len(token) - 3):
        prefix = token[:split_pos]
        suffix = token[split_pos:]

        for candidate in _candidate_forms(suffix):
            if len(candidate) >= 4 and candidate in known_terms_norm:
                if best_suffix is None or len(candidate) > len(best_suffix):
                    best_suffix = candidate

        if best_suffix is None:
            for candidate in _candidate_forms(prefix):
                if len(candidate) >= 4 and candidate in known_terms_norm:
                    if best_prefix is None or len(candidate) > len(best_prefix):
                        best_prefix = candidate

    if best_suffix and best_suffix not in variants:
        variants.append(best_suffix)
    elif best_prefix and best_prefix not in variants:
        variants.append(best_prefix)

    unique_variants: List[str] = []
    seen: set[str] = set()
    for variant in variants:
        if variant in seen:
            continue
        seen.add(variant)
        unique_variants.append(variant)
    return unique_variants


def _db_path_for_connection(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("PRAGMA database_list").fetchone()
    if not row:
        return None
    path = str(row[2] or "").strip()
    return path or None


@lru_cache(maxsize=8)
def _load_known_terms_from_db_path(db_path: str, table_name: str, name_col: str) -> frozenset[str]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            f"SELECT DISTINCT {name_col} FROM {table_name} WHERE {name_col} IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    known_terms: set[str] = set()
    for row in rows:
        for token in tokenize(str(row[0])):
            known_terms.add(token)
    return frozenset(known_terms)


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


def token_exactly_matches_keyword(token: str, kw: str) -> bool:
    """Prüft, ob Token und Keyword exakt zusammenpassen.

    Dabei werden auch einfache Umlaut-Varianten über die fold-Form berücksichtigt.
    """

    if not token or not kw:
        return False

    token_variants = {token, fold_umlauts(token)}
    kw_variants = {kw, fold_umlauts(kw)}

    return any(tok == key for tok in token_variants for key in kw_variants)


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
    parts = re.split(r"\s*(?:/|\+|,|;|:|&|\bund\b|\bmit\b|\boder\b|\bsowie\b|\bbzw\.?\b)\s*", text)

    cleaned: List[str] = []
    for part in parts:
        candidate = part.strip()
        if candidate:
            cleaned.append(candidate)

    return cleaned or ([text] if text else [])


def first_candidate_phrase(text: str) -> str:
    """Gibt den ersten groben Phrasenteil zurück."""

    phrases = split_candidate_phrases(text)
    return phrases[0] if phrases else ""


def score_bls_row(name: str, query_tokens: List[str]) -> int:
    """Zählt, wie viele Query-Tokens im BLS-Namen wiedergefunden werden."""

    if not name or not query_tokens:
        return 0

    hits = 0
    name_tokens = tokenize(normalize_text(str(name)))

    for tok in query_tokens:
        if any(
            token_matches_keyword(nt, tok) or token_matches_keyword(tok, nt)
            for nt in name_tokens
        ):
            hits += 1

    return hits


def find_bls_matches_for_text(
    conn: sqlite3.Connection, raw_text: str
) -> List[Tuple[Optional[str], Optional[str], Optional[str], int]]:
    """Sucht BLS-Treffer für den Gesamttext und seine Kandidatenphrasen.

    Rückgabe: Liste von (code, name, id, score) in Fundreihenfolge, ohne Duplikate.
    Dabei wird pro Phrase jeder Token einzeln gegen die BLS-DB geprüft und die
    Evidenz pro BLS-Zeile aufaddiert.
    """

    matches_by_key: Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[object]] = {}
    match_order: List[Tuple[Optional[str], Optional[str], Optional[str]]] = []

    for phrase in split_candidate_phrases(raw_text):
        t, name_col, id_col, code_col = detect_table_and_columns(conn)
        if not t or not name_col:
            continue

        db_path = _db_path_for_connection(conn)
        known_terms = (
            set(_load_known_terms_from_db_path(db_path, t, name_col)) if db_path else None
        )

        tokens = tokenize(phrase)
        if not tokens:
            continue

        cur = conn.cursor()
        for token in tokens:
            search_variants = compound_token_variants(token, known_terms)
            exact_first_matches: List[Tuple[Optional[str], Optional[str], Optional[str], int]] = []
            fallback_matches: List[Tuple[Optional[str], Optional[str], Optional[str], int]] = []

            for search_token in search_variants:
                where_sql = f"LOWER({name_col}) LIKE ?"
                params = [f"%{search_token}%"]

                select_cols = [name_col]
                if code_col:
                    select_cols.append(code_col)
                if id_col:
                    select_cols.append(id_col)
                sql = f"SELECT {', '.join(select_cols)} FROM {t} WHERE {where_sql} LIMIT 25"

                rows = cur.execute(sql, params).fetchall()
                for row in rows:
                    name = str(row[0])
                    code = row[1] if code_col and len(row) > 1 else None
                    rid = None
                    if code_col and id_col and len(row) > 2:
                        rid = row[2]
                    elif id_col and len(row) > 1 and not code_col:
                        rid = row[1]

                    code_prefix = str(code or "").strip().upper()[:1]
                    allow_bonus = code_prefix != "Y"

                    score = score_bls_row(name, [search_token])
                    if score <= 0:
                        continue

                    name_tokens = tokenize(normalize_text(name))
                    first_name_phrase_tokens = tokenize(first_candidate_phrase(name))
                    is_exact_first_token = bool(name_tokens) and token_exactly_matches_keyword(
                        name_tokens[0], search_token
                    )
                    is_contained_anywhere = any(
                        token_matches_keyword(name_token, search_token)
                        for name_token in name_tokens
                    )
                    is_contained_in_first_phrase = any(
                        token_matches_keyword(name_token, search_token)
                        for name_token in first_name_phrase_tokens
                    )
                    if allow_bonus and code_prefix == "X" and is_exact_first_token:
                        score += EXACT_MATCH_BONUS
                    elif allow_bonus and code_prefix == "X" and is_contained_anywhere:
                        score += CONTAINED_MATCH_BONUS
                    elif allow_bonus and is_exact_first_token:
                        score += EXACT_MATCH_BONUS
                    elif allow_bonus and is_contained_in_first_phrase:
                        score += CONTAINED_MATCH_BONUS

                    match_key = (code, name, rid)
                    match = (code, name, rid, score)
                    if is_exact_first_token:
                        exact_first_matches.append(match)
                    else:
                        fallback_matches.append(match)

            token_matches = exact_first_matches if len(exact_first_matches) == 1 else exact_first_matches + fallback_matches
            for code, name, rid, score in token_matches:
                match_key = (code, name, rid)
                if match_key not in matches_by_key:
                    matches_by_key[match_key] = [code, name, rid, 0]
                    match_order.append(match_key)
                matches_by_key[match_key][3] = int(matches_by_key[match_key][3]) + score

    matches: List[Tuple[Optional[str], Optional[str], Optional[str], int]] = []
    for match_key in match_order:
        code, name, rid, score = matches_by_key[match_key]
        matches.append((code, name, rid, int(score)))

    return matches


PHRASE_MAX_CANDIDATE_GROUPS = 3
PHRASE_MIN_DOMINANCE = 0.5
EXACT_MATCH_BONUS = 40
CONTAINED_MATCH_BONUS = 10


def rank_phrase_groups(
    phrase_group_scores: Dict[str, int],
    phrase_group_first_seen: Dict[str, int],
) -> Tuple[List[str], int, int]:
    """Bestimmt die bestbewerteten Gruppen einer Phrase.

    Rückgabe:
    - best_groups: Gruppen mit dem höchsten Score, stabil nach Erstauftreten sortiert
    - max_score: höchster Gruppen-Score
    - total_score: Summe aller Gruppen-Score
    """

    if not phrase_group_scores:
        return [], 0, 0

    max_score = max(phrase_group_scores.values())
    total_score = sum(phrase_group_scores.values())
    best_groups = sorted(
        [g for g, score in phrase_group_scores.items() if score == max_score],
        key=lambda g: phrase_group_first_seen.get(g, float("inf")),
    )
    return best_groups, max_score, total_score


def phrase_is_too_ambiguous(group_count: int, max_score: int, total_score: int, group_scores: Optional[Dict[str, int]] = None) -> bool:
    """Prüft, ob eine Phrase zu viele plausible Gruppen hat.

    Blockieren wenn:
    1. Extrem viele Gruppen (> 5), ODER
    2. Sehr schwache Dominanz (< 45%), ODER
    3. Perfekte 50/50 Ambiguität (dominance == 0.5), ODER
    4. Mehrere Gruppen (> 3) UND schwache Dominanz (0.45 <= dom < 0.55) UND
       der Gewinner nicht deutlich gegen seinen Konkurrenten führt (ratio < 1.2)
    """

    if not total_score:
        return False

    dominance = max_score / total_score

    # 1. Extrem viele Gruppen → blockieren
    if group_count > 5:
        return True

    # 2. Sehr schwache Dominanz → blockieren
    if dominance < 0.45:
        return True

    # 3. Perfekte 50/50 → blockieren
    if abs(dominance - 0.5) < 0.001:  # 0.5 ± tolerance
        return True

    # 4. Mehrere Gruppen + schwache Dominanz → prüfe Winner vs 2. Platz
    if group_count > PHRASE_MAX_CANDIDATE_GROUPS and 0.45 <= dominance < 0.55:
        # Prüfe, ob der Gewinner gegen den 2. Platz deutlich führt
        if group_scores:
            sorted_scores = sorted(group_scores.values(), reverse=True)
            if len(sorted_scores) >= 2:
                max_vs_second = sorted_scores[0] / sorted_scores[1] if sorted_scores[1] > 0 else float('inf')
                # Blockieren nur, wenn auch gegen 2. Platz der Vorsprung schwach ist (< 1.2x)
                if max_vs_second < 1.2:
                    return True
            else:
                return True
        else:
            return True

    return False

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
    """Enriched den gesamten Plan per BLS-Code-Letter-Mapping.
    
    WICHTIG: Pro Phrase (Zutat) wird eine SEPARATE Bewertung durchgeführt.
    Dies stellt sicher, dass "Hähnchen mit Reis" ZWEI Gruppen erhält
    (meat von Hähnchen, grains_potatoes von Reis), nicht nur eine.
    """

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

                # Pro Phrase eine eigene Bewertung
                all_phrases_groups: List[str] = []  # Finales Ergebnis: alle Gruppen aus allen Phrasen
                all_bls_matches = []  # Debug: alle Matches aggregiert
                all_group_scores: Dict[str, int] = {}  # Debug: alle Scores aggregiert
                
                if conn:
                    # Teile Text in Phrasen auf
                    phrases = split_candidate_phrases(raw_text)
                    
                    for phrase in phrases:
                        # Pro Phrase: suche BLS-Matches
                        phrase_matches = find_bls_matches_for_text(conn, phrase)
                        all_bls_matches.extend(phrase_matches)
                        
                        # Pro Phrase: berechne Gruppe-Scores
                        phrase_group_scores: Dict[str, int] = {}
                        phrase_group_first_seen: Dict[str, int] = {}
                        
                        for bls_code, bls_name, bls_id, score in phrase_matches:
                            if not bls_code:
                                continue
                            code = str(bls_code).strip()
                            if not code:
                                continue
                            letter = code[0].upper()
                            mapped_groups = code_letter_map.get(letter, [])
                            for group in mapped_groups:
                                if str(group).strip().lower() == "other":
                                    continue
                                phrase_group_scores[group] = phrase_group_scores.get(group, 0) + score
                                all_group_scores[group] = all_group_scores.get(group, 0) + score
                                if group not in phrase_group_first_seen:
                                    phrase_group_first_seen[group] = len(phrase_group_first_seen)
                        
                        # Pro Phrase: nur zuordnen, wenn die Gruppe klar genug ist
                        phrase_best_groups, max_score, total_score = rank_phrase_groups(
                            phrase_group_scores,
                            phrase_group_first_seen,
                        )
                        if phrase_group_scores and phrase_is_too_ambiguous(
                            len(phrase_group_scores), max_score, total_score, phrase_group_scores
                        ):
                            continue

                        for group in phrase_best_groups:
                            if group not in all_phrases_groups:
                                all_phrases_groups.append(group)

                groups = all_phrases_groups
                links = item.get("links") or {}
                links["food_group"] = groups[0] if groups else None
                
                # Confidence: Top-Score / Total-Score (für Debug)
                total_group_score = sum(all_group_scores.values())
                top_group_score = all_group_scores.get(groups[0], 0) if groups else 0
                links["confidence"] = (top_group_score / total_group_score) if total_group_score else 0.0
                
                if all_bls_matches:
                    first_code, first_name, first_id, _first_score = all_bls_matches[0]
                    links["bls_id"] = first_id
                    links["bls_name"] = first_name
                    links["bls_matches"] = [
                        {"code": code, "name": name, "id": rid, "score": score}
                        for code, name, rid, score in all_bls_matches
                    ]
                    links["group_scores"] = all_group_scores

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
