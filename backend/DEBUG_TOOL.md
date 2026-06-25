# Debug-Tool für Enrichment-Pipeline

Dieses Tool zeigt dir **detailliert**, was bei der Enrichment-Pipeline passiert — von der Text-Zerlegung bis zur finalen Gruppen-Zuweisung.

## Quick Start

```bash
# 1. Zum Projekt navigieren
cd <GENAU_PROJEKT>

# 2. Virtual Environment aktivieren
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Debug-Tool starten (mit echter BLS-DB)
python backend/scripts/debug_enrichment.py "Hähnchen mit Reis"
```

Das war's! Jetzt siehst du farbig, was bei der Enrichment-Pipeline passiert.

## Installation

Das Tool ist bereits im Backend vorhanden:
- `backend/scripts/debug_enrichment.py` — Hauptdebugger (mit echter BLS-DB)

## Vorbereitung

```bash
# 1. Zum Projekt-Root navigieren
cd <GENAU_PROJEKT>

# 2. Virtual Environment aktivieren
source .venv/bin/activate
# oder auf Windows:
# .venv\Scripts\activate
```

## Verwendung

### 1. **Mit echter BLS-Datenbank**

```bash
python backend/scripts/debug_enrichment.py "Hähnchen mit Reis"
```

Der Debugger nutzt standardmäßig `backend/instance/bls.db`. Wenn deine Datenbank woanders liegt, gib sie mit `--bls-db /pfad/zur/bls.db` an.

Optional:
```bash
# Mit custom DB-Pfad
python backend/scripts/debug_enrichment.py "Spinat" \
  --bls-db backend/instance/bls.db \
  --mapping-json backend/rules/bls_to_dge_groups.json

# Nur Ergebnisse (ohne Debug-Output)
python backend/scripts/debug_enrichment.py "Spinat" --quiet
```

## Beispiele

### Beispiel 1: "Hähnchen mit Reis" (zwei Gruppen pro Phrase)

```bash
python backend/scripts/debug_enrichment.py "Hähnchen mit Reis"
```

**Ergebnis:**
- **Phrase 1 "Hähnchen"**: 2 Matches (U-Code) → **meat**
- **Phrase 2 "Reis"**: 1 Match (C-Code) → **grains_potatoes**
- **Finale Gruppen:** `["meat", "grains_potatoes"]` (66.67% confidence)

### Beispiel 2: "Spinat" (einzelne Phrase, Mehrheits-Logik)

```bash
python backend/scripts/debug_enrichment.py "Spinat"
```

**Ergebnis:**
- Findet 2 Matches: beide G-Code (Spinat frisch + Rahmspinat)
- Gruppe Scores: vegetables=2
- **Finale Gruppe:** `["vegetables"]` (100% confidence)

### Beispiel 3: "Joghurt-Minzdipp" (Hyphen-Split)

```bash
python backend/scripts/debug_enrichment.py "Joghurt-Minzdipp"
```

**Ergebnis:**
- Text wird auf Hyphen gesplittet → ["joghurt", "minzdipp"]
- Findet nur "Joghurt natur" (M-Code, minze/dipp hat keinen BLS-Match)
- **Finale Gruppe:** `["dairy"]` (100% confidence)

## Was wird debuggt?

Das Tool zeigt alle 5 Schritte der **per-Phrase Enrichment-Pipeline**:

1. **TEXT-ZERLEGUNG IN PHRASEN**
   - Input-Text wird an Trennzeichen gesplittet (mit, und, oder, etc.)
   - Zeigt alle Phrasen separat

2. **TOKENISIERUNG**
   - Jede Phrase wird in Tokens zerlegt
   - Zeigt Token-Namen und Längen

3. **BLS-DATENBANKSUCHE**
   - Pro Token: welche Varianten werden gesucht
   - Alle gefundenen BLS-Matches mit Code, Name, ID, Score

4. **GRUPPEN-MAPPING & SCORING (PRO PHRASE)**
   - **Pro Phrase einzeln** bewertet (nicht global!)
   - Zeigt welche Gruppe pro Phrase gewonnen hat
   - Scores akkumuliert für Debug-Zwecke

5. **FINALES ERGEBNIS (PRO-PHRASE)**
   - Alle Gruppen aus allen Phrasen kombiniert
   - Keine Duplikate
   - Confidence basiert auf Top-Score

## Farbcodes

- 🟢 **SUCCESS** (grün) — Match gefunden, Gruppe hinzugefügt
- 🔴 **ERROR** (rot) — Keine Gruppen gefunden
- 🟡 **WARNING** (gelb) — Warnung (z.B. 'other'-Gruppe übersprungen)
- ⚪ **DEBUG** (weiß) — Detailinformation
- ⚪ **INFO** (weiß) — Allgemeine Information

## Tips

- **Verbose ausschalten:** `--quiet` Flag
- **Verschiedene Texte testen:** Einfach Text als Argument übergeben
  ```bash
  python backend/scripts/debug_enrichment.py "Dein Text hier"
  ```
- **Im Terminal speichern:** 
  ```bash
  python backend/scripts/debug_enrichment.py "Text" > debug_output.txt
  ```
- **Mit echter BLS-DB debuggen:**
  ```bash
  python backend/scripts/debug_enrichment.py "Text" --quiet
  ```
  (Voraussetzung: BLS-Datenbank wurde importiert)

## Architektur

Das Tool nutzt die bestehenden Funktionen aus `enrich_foodplan.py`:
- `split_candidate_phrases()` — Phrase-Splitting
- `tokenize()` — Tokenisierung
- `compound_token_variants()` — Compound-Token-Varianten
- `find_bls_matches_for_text()` — BLS-Suche
- `load_code_letter_mapping()` — Mapping laden

Die `DebugLogger` Klasse kümmert sich um formatierte Ausgabe mit Farben und Einrückung.

## Wie die Per-Phrase Logik funktioniert

Die Enrichment-Pipeline bewertet jede Phrase **individuell**:

```
Input: "Hähnchen mit Reis"
       ↓
Phrase-Split: ["hähnchen", "reis"]
       ↓
PHRASE 1 "hähnchen":
  └─ Suche BLS-Matches → U111000 (meat), U222000 (meat)
  └─ Scores pro Gruppe: meat=2
  └─ Beste Gruppe dieser Phrase: meat ✓
       ↓
PHRASE 2 "reis":
  └─ Suche BLS-Matches → C333000 (grains_potatoes)
  └─ Scores pro Gruppe: grains_potatoes=1
  └─ Beste Gruppe dieser Phrase: grains_potatoes ✓
       ↓
FINALES ERGEBNIS: ["meat", "grains_potatoes"]
```

**Wichtig:** "Hähnchen" und "Reis" werden nicht miteinander verglichen! Jede Zutat erhält ihre eigene Gruppe.

## Troubleshooting

### Virtual Environment nicht aktiviert?
```bash
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

### `ModuleNotFoundError` beim Starten?
→ Sicherstellen, dass der Command aus dem **Projekt-Root** ausgeführt wird (dort wo `.venv/` liegt)

### DB nicht gefunden?
```
❌ DB nicht gefunden: backend/instance/bls.db
```
→ Importiere die BLS-DB mit:
```bash
python backend/scripts/import_bls.py <path_to_bls_csv>
```

### Keine Matches gefunden?
→ Überprüfe mit Debug-Tool, ob die Tokens korrekt sind:
```bash
python backend/scripts/debug_enrichment.py "Test-Text"
```
Achte auf Schritt 3 (BLS-DATENBANKSUCHE) — wenn dort "Gesamt-Matches gefunden: 0" steht, passen die Tokens nicht.

### Score-Überraschungen?
→ Tool zeigt genau, wie pro Phrase gescort wird und welche Gruppe pro Phrase gewinnt
