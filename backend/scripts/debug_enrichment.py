#!/usr/bin/env python3
"""
Debug-Tool für die Enrichment-Pipeline.

Zeigt detailliert:
- Text-Zerlegung in Phrasen
- Token-Generierung
- BLS-Suche und Matches
- Score-Berechnung
- Gruppen-Zuweisung
"""

import sys
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.enrich_foodplan import (
    _db_path_for_connection,
    _load_known_terms_from_db_path,
    detect_table_and_columns,
    split_candidate_phrases,
    tokenize,
    compound_token_variants,
    find_bls_matches_for_text,
    load_code_letter_mapping,
    rank_phrase_groups,
    phrase_is_too_ambiguous,
    enrich_plan,
)


class DebugLogger:
    """Simple Logger für strukturierte Debug-Ausgabe."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.indent_level = 0
    
    def log(self, msg: str, level: str = "INFO"):
        """Log eine Nachricht mit Einrückung."""
        indent = "  " * self.indent_level
        color_code = {
            "DEBUG": "\033[36m",      # Cyan
            "INFO": "\033[37m",       # White
            "SUCCESS": "\033[32m",    # Green
            "WARNING": "\033[33m",    # Yellow
            "ERROR": "\033[31m",      # Red
        }.get(level, "\033[37m")
        reset = "\033[0m"
        
        if self.verbose:
            print(f"{color_code}[{level:7}]{reset} {indent}{msg}")
    
    def section(self, title: str):
        """Neue Section."""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    
    def push(self):
        """Einrückung erhöhen."""
        self.indent_level += 1
    
    def pop(self):
        """Einrückung senken."""
        self.indent_level = max(0, self.indent_level - 1)


def debug_phrase_splitting(logger: DebugLogger, raw_text: str):
    """Debug die Phrase-Splitting."""
    logger.section("1. TEXT-ZERLEGUNG IN PHRASEN")
    logger.log(f"Input: '{raw_text}'")
    
    phrases = split_candidate_phrases(raw_text)
    logger.log(f"Anzahl Phrasen: {len(phrases)}", "SUCCESS")
    logger.push()
    for i, phrase in enumerate(phrases, 1):
        logger.log(f"Phrase {i}: '{phrase}'", "DEBUG")
    logger.pop()
    return phrases


def debug_tokenization(logger: DebugLogger, text: str, conn: sqlite3.Connection | None = None):
    """Debug die Tokenisierung."""
    logger.section("2. TOKENISIERUNG")
    logger.log(f"Input: '{text}'")
    
    tokens = tokenize(text)
    logger.log(f"Anzahl Tokens: {len(tokens)}", "SUCCESS")

    known_terms = None
    if conn:
        t, name_col, _, _ = detect_table_and_columns(conn)
        db_path = _db_path_for_connection(conn)
        if t and name_col and db_path:
            known_terms = set(_load_known_terms_from_db_path(db_path, t, name_col))

    logger.push()
    for token in tokens:
        logger.log(f"Token: '{token}' ({len(token)} chars)", "DEBUG")
        variants = compound_token_variants(token, known_terms)
        if len(variants) == 1:
            logger.log(f"  → Varianten: {variants[0]}", "INFO")
        else:
            logger.log(f"  → Varianten ({len(variants)} Stück):", "WARNING")
            logger.push()
            for i, variant in enumerate(variants, 1):
                logger.log(f"{i}. '{variant}'", "DEBUG")
            logger.pop()
    logger.pop()
    return tokens


def debug_compound_variants(logger: DebugLogger, token: str):
    """Debug die Compound-Varianten."""
    variants = compound_token_variants(token)
    
    if len(variants) == 1:
        logger.log(f"  → Varianten (Direkttreffer): {variants[0]}")
    else:
        logger.log(f"  → Varianten ({len(variants)} Stück):", "WARNING")
        logger.push()
        for i, v in enumerate(variants, 1):
            logger.log(f"{i}. '{v}'", "DEBUG")
        logger.pop()


def debug_bls_matches(logger: DebugLogger, conn: sqlite3.Connection, raw_text: str):
    """Debug die BLS-Suche und Matches."""
    logger.section("3. BLS-DATENBANKSUCHE")
    
    matches = find_bls_matches_for_text(conn, raw_text)
    logger.log(f"Gesamt-Matches gefunden: {len(matches)}", "SUCCESS" if matches else "WARNING")
    
    logger.push()
    phrases = split_candidate_phrases(raw_text)
    for phrase in phrases:
        logger.log(f"Phrase: '{phrase}'")
        tokens = tokenize(phrase)
        logger.push()
        for token in tokens:
            logger.log(f"Token '{token}':")
            logger.push()
            debug_compound_variants(logger, token)
            logger.pop()
        logger.pop()
    
    logger.log("\nAlle Treffer (aggregiert):")
    logger.push()
    for code, name, rid, score in matches:
        logger.log(f"Code={code}, Name='{name}', ID={rid}, Score={score}", "DEBUG")
    logger.pop()


def debug_enrichment(
    logger: DebugLogger,
    conn: sqlite3.Connection,
    raw_text: str,
    code_letter_map: dict,
):
    """Debug den kompletten Enrichment-Prozess (pro-Phrase)."""
    logger.section("4. GRUPPEN-MAPPING & SCORING (PRO PHRASE)")
    
    phrases = split_candidate_phrases(raw_text)
    all_groups = []
    all_group_scores = {}
    
    for phrase_num, phrase in enumerate(phrases, 1):
        logger.log(f"\n--- PHRASE {phrase_num}: '{phrase}' ---")
        logger.push()
        
        matches = find_bls_matches_for_text(conn, phrase)
        logger.log(f"Matches gefunden: {len(matches)}")
        
        phrase_group_scores = {}
        phrase_group_first_seen = {}
        
        logger.push()
        for bls_code, bls_name, bls_id, score in matches:
            if not bls_code:
                logger.pop()
                logger.log(f"⚠ Skip: Kein Code für '{bls_name}'", "WARNING")
                logger.push()
                continue
            
            code = str(bls_code).strip()
            if not code:
                continue
            
            letter = code[0].upper()
            mapped_groups = code_letter_map.get(letter, [])
            
            logger.log(f"BLS-Code: {code} ('{bls_name}', score={score})")
            logger.push()
            logger.log(f"  → Letter: '{letter}'", "DEBUG")
            logger.log(f"  → Maps zu Gruppen: {mapped_groups}", "DEBUG")
            
            for group in mapped_groups:
                if str(group).strip().lower() == "other":
                    logger.log(f"  ✗ Skip 'other' group", "WARNING")
                    continue
                
                phrase_group_scores[group] = phrase_group_scores.get(group, 0) + score
                all_group_scores[group] = all_group_scores.get(group, 0) + score
                if group not in phrase_group_first_seen:
                    phrase_group_first_seen[group] = len(phrase_group_first_seen)
                
                logger.log(f"  ✓ Group '{group}' += {score}", "SUCCESS")
            
            logger.pop()
        
        logger.pop()
        
        # Beste Gruppe für diese Phrase, aber nur wenn nicht zu breit
        phrase_best_groups, max_score, total_score = rank_phrase_groups(
            phrase_group_scores,
            phrase_group_first_seen,
        )
        if phrase_group_scores and phrase_is_too_ambiguous(
            len(phrase_group_scores), max_score, total_score
        ):
            logger.log(
                f"\n⚠ Phrase zu mehrdeutig: {len(phrase_group_scores)} Gruppen, "
                f"Top-Score {max_score}/{total_score}",
                "WARNING",
            )
        elif phrase_group_scores:
            logger.log(f"\n✓ Phrase-Ergebnis: {phrase_best_groups} (max score: {max_score})", "SUCCESS")
            for group in phrase_best_groups:
                if group not in all_groups:
                    all_groups.append(group)
        else:
            logger.log(f"\n❌ Keine Gruppen für diese Phrase", "WARNING")
        
        logger.pop()
    
    logger.section("5. FINALES ERGEBNIS (PRO-PHRASE)")
    logger.log(f"Total Group Scores (aggregiert): {all_group_scores}")
    logger.log(f"Finales Ergebnis: {all_groups}", "SUCCESS" if all_groups else "ERROR")
    
    if all_groups:
        total_score = sum(all_group_scores.values())
        top_score = all_group_scores.get(all_groups[0], 0)
        confidence = (top_score / total_score) if total_score else 0.0
        logger.log(f"Confidence (Top-Score/Total): {top_score}/{total_score} = {confidence:.2%}")
        
        return all_groups, confidence
    else:
        logger.log("❌ Keine Gruppen gefunden", "ERROR")
        return [], 0.0


def debug_foodplan_item(
    logger: DebugLogger,
    raw_text: str,
    db_path: Path,
    mapping_json: Path,
):
    """Debugge ein einzelnes Item."""
    logger.section("FOODPLAN-ITEM ENRICHMENT")
    logger.log(f"Raw Text: '{raw_text}'")
    logger.log(f"BLS-DB: {db_path}")
    logger.log(f"Mapping: {mapping_json}\n")
    
    # Load mapping
    code_letter_map = load_code_letter_mapping(mapping_json)
    logger.log(f"Code-Letter Mapping geladen: {len(code_letter_map)} Mappings")
    
    # Connect to DB
    if not db_path.exists():
        logger.log(f"❌ DB nicht gefunden: {db_path}", "ERROR")
        return
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Step 1: Phrase splitting
        debug_phrase_splitting(logger, raw_text)
        
        # Step 2: Tokenization
        phrases = split_candidate_phrases(raw_text)
        for phrase in phrases:
            debug_tokenization(logger, phrase, conn)
        
        # Step 3: BLS matching
        debug_bls_matches(logger, conn, raw_text)
        
        # Step 4: Enrichment
        groups, confidence = debug_enrichment(logger, conn, raw_text, code_letter_map)
        
        logger.section("ZUSAMMENFASSUNG")
        logger.log(f"Food Groups: {groups}", "SUCCESS")
        logger.log(f"Primary Group: {groups[0] if groups else 'NONE'}", "SUCCESS" if groups else "ERROR")
        logger.log(f"Confidence: {confidence:.2%}", "SUCCESS")
    
    finally:
        conn.close()


def main():
    """Haupteinstiegspunkt."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Debug-Tool für die Enrichment-Pipeline"
    )
    parser.add_argument(
        "raw_text",
        help="Der zu analysierte Text (z.B. 'Hähnchen mit Reis')",
    )
    parser.add_argument(
        "--bls-db",
        type=Path,
        default=Path(__file__).parent.parent / "instance" / "bls.db",
        help="Pfad zur BLS-Datenbank",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(__file__).parent.parent / "rules" / "bls_to_dge_groups.json",
        help="Pfad zum Code-Letter Mapping",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Keine Ausgabe (nur Ergebnisse)",
    )
    
    args = parser.parse_args()
    
    logger = DebugLogger(verbose=not args.quiet)
    
    debug_foodplan_item(
        logger,
        args.raw_text,
        args.bls_db,
        args.mapping_json,
    )


if __name__ == "__main__":
    main()
