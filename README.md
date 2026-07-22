# Genau_Projekt (BLS Food API)

Kleines **Flask + SQLite** Backend mit Next.js-Frontend, das BLS-Daten importiert und Speisepläne über eine JSON-API enrich't.

Die aktuelle Enrichment-Logik arbeitet **BLS-first**: Es wird gegen die BLS-Datenbank gematcht und das BLS-Code-Präfix über `backend/rules/bls_to_dge_groups.json` auf DGE-Gruppen abgebildet.

## Quickstart (End-to-End testen)

Du willst nur schnell prüfen, ob alles läuft? Dann:

1. Setup (venv + Pakete)

```sh
cd <pfad-zum-projekt>/Genau_Projekt
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend
npm install
cd ..
```

2. DB erstellen + BLS importieren (Pflicht)

```sh
rm -f backend/instance/bls.db
python backend/import_bls.py
```

Die BLS-Datenbank ist für den Excel-Upload zwingend erforderlich. Ohne `backend/instance/bls.db` startet das Backend zwar, der Upload von `.xlsx`-Plänen schlägt jedoch fehl.

Der Import speichert zusätzlich den BLS-Code in der Spalte `Food.code`, damit das Enrichment später nur über den BLS-Code arbeiten kann.

3. Alle Services starten (Backend + Frontend)

```sh
# im Projekt-Root
npm install
npm run dev
```

Dann im Browser öffnen:

- http://localhost:3000

Alternativ (manuell, in zwei Terminals):

- Backend: `python backend/app.py`
- Frontend: `cd frontend && npm install && npm run dev`

---

## 1) Voraussetzungen

- macOS / Linux / Windows
- Python (empfohlen: über virtuelle Umgebung)
- Node.js + npm (nur falls das Frontend genutzt werden soll)

## 2) Setup (virtuelle Umgebung)

Im Projekt-Root (Ordner, in dem `backend/` liegt):

```sh
# in den Projektordner wechseln (Beispiel)
cd <pfad-zum-projekt>/Genau_Projekt

python3 -m venv .venv
source .venv/bin/activate
```

Pakete installieren:

```sh
pip install -r backend/requirements.txt
```

Danach das Frontend einmalig installieren:

```sh
cd frontend
npm install
```

## 3) Datenbank neu erstellen + Import aus Excel

Die SQLite-DB liegt (typisch) unter `backend/instance/bls.db`.

Die BLS-Datenbank ist für den Excel-Import und das Enrichment verpflichtend. Wenn die Datei fehlt, wird der Upload von `.xlsx`-Speiseplänen mit einer Fehlermeldung abgewiesen.

Das Mapping selbst liegt in `backend/rules/bls_to_dge_groups.json` und basiert auf dem ersten Buchstaben des BLS-Codes.

### Komplett neu (frische DB-Datei)

1. Server stoppen, falls er läuft.
2. DB-Datei löschen:

```sh
rm -f backend/instance/bls.db
```

3. Import ausführen:

```sh
python backend/import_bls.py
```

Dabei werden:

- Tabellen automatisch erstellt (`db.create_all()`)
- vorhandene Daten (falls vorhanden) gelöscht
- Daten aus `data/BLS_4_0_Daten_2025_DE.xlsx` importiert

### Excel-Pfad anpassen (optional)

Standard:

- `data/BLS_4_0_Daten_2025_DE.xlsx`

Alternativ über Umgebungsvariable:

```sh
export BLS_XLSX_PATH="/pfad/zur/BLS_4_0_Daten_2025_DE.xlsx"
python backend/import_bls.py
```

### BLS-DB-Pfad anpassen (optional)

Wenn die SQLite-Datei nicht unter `backend/instance/bls.db` liegt, kannst du sie für den Upload und das Enrichment setzen:

```sh
export BLS_DB_PATH="/pfad/zur/bls.db"
```

Wichtig:

- `BLS_DB_PATH` wird in der Enrichment-/Upload-Pipeline genutzt.
- `import_bls.py` nutzt **nicht** `BLS_DB_PATH`, sondern die App-DB-Konfiguration (`DATABASE_URL`).

Falls du den Zielpfad der SQLite-DB für Import und API explizit setzen willst:

```sh
export DATABASE_URL="sqlite:////absoluter/pfad/bls.db"
python backend/import_bls.py
```

## 4) Server starten

```sh
python backend/app.py
```

Der Server läuft dann lokal auf:

- `http://127.0.0.1:5000`

### Troubleshooting: `/foods` gibt leeres Ergebnis zurück

Symptom:

- `GET /health` funktioniert
- `GET /foods?q=apfel&limit=10` liefert `{"items":[]}` trotz importierter BLS-Daten

Typische Ursache:

- Es laufen mehrere Backend-Prozesse parallel (z.B. durch Debug-ReLoader oder andere lokale Tools).
- Die App wurde in unterschiedlichen Startmodi gestartet und hat dadurch früher unterschiedliche SQLite-Instanzen verwendet.

Status im Projekt:

- Die Standard-DB ist jetzt stabil auf `backend/instance/bls.db` gesetzt, damit Paket-Import und Skript-Start dieselbe Datenbank nutzen.

Empfohlene Lösung:

1. Laufende Backend-Prozesse stoppen.
2. Backend eindeutig neu starten (ein Prozess, ein Port).
3. Endpunkte erneut prüfen.

Beispiel (Port 5001):

```sh
cd <pfad-zum-projekt>/Genau_Projekt
source .venv/bin/activate
python -c "from backend.app import create_app; app=create_app(); app.run(host='127.0.0.1', port=5001, debug=False)"

curl http://127.0.0.1:5001/health
curl "http://127.0.0.1:5001/foods?q=apfel&limit=10"
```

Wenn auf Port 5000 bereits ein anderer Dienst lauscht, nutze einen freien Port (z.B. 5001) und setze im Frontend `BACKEND_URL` entsprechend in `frontend/.env.local`.

## 5) API-Endpunkte

### Health Check

- `GET /health`

Beispiel:

```sh
curl http://127.0.0.1:5000/health
```

### Lebensmittelsuche

- `GET /foods?q=<suchbegriff>&limit=<n>`

Beispiel:

```sh
curl "http://127.0.0.1:5000/foods?q=apfel&limit=10"
```

Antwort (Beispiel):

```json
{ "items": [{ "id": 123, "name_de": "Apfel" }] }
```

### Lebensmittel-Details

- `GET /foods/<id>`

Beispiel:

```sh
curl http://127.0.0.1:5000/foods/123
```

Antwort enthält u.a. die Nährwerte pro 100g (siehe `Food.to_dict()` in `backend/models.py`).

## 6) Frontend (optional)

Wenn du die UI testen willst:

```sh
cd frontend
npm install
npm run dev
```

### Frontend-Konfiguration (`.env.local`)

Für das Frontend wird eine lokale Env-Datei empfohlen:

- Datei: `frontend/.env.local`
- Zweck: enthält die URL/Adresse, unter der das Backend erreichbar ist (und ggf. weitere Frontend-Settings)

**Wichtig:** `frontend/.env.local` ist in der Regel in `.gitignore` und wird **nicht** mit ins Repo committed.
Das heißt: **Nach dem Klonen** muss jede\*r diese Datei lokal selbst anlegen.

Minimal-Schritte:

1. Datei erstellen: `frontend/.env.local`
2. Variable setzen (Beispiel, Backend läuft lokal auf Port 5000):

```env
# URL zum Flask-Backend (für API-Calls aus dem Frontend)
BACKEND_URL=http://127.0.0.1:5000
```

> Hinweis: `BACKEND_URL` wird in den Next.js-API-Routen gelesen. Nach Änderungen an `.env.local` den Dev-Server neu starten.

Dann:

- http://localhost:3000

## 7) Tests (Unit Tests)

Für die Tests verwenden wir aktuell zwei Werkzeuge:

- `pytest` für das Backend
- `vitest` für das Frontend

## 8) Quantitative Evaluation

Für die Auswertung der Erkennungsleistung gibt es ein separates Skript, das aus den
BLS-Daten synthetische Wochenpläne erzeugt und das Enrichment automatisiert misst.

### Was wird gemessen?

- Gesamtzahl erkannter Gerichte
- Erkennungsrate pro Woche
- unzugeordnete Gerichte und deren Fehlerursachen
- Mehrfachzuordnungen (Gerichte, die mehreren Gruppen zugeordnet wurden)

### Struktur der synthetischen Daten

- **Pro Tag:** 1 Menu mit genau 2 Gerichten
- **Standard:** 1 Woche (5 Wochentage)
- Beliebig erweiterbar auf mehrere Wochen mit `--weeks`

### Standardlauf

Im Backend-Verzeichnis ausführen:

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 10 --seed 42 --weeks 1 --stress-profile none
```

### Wichtige Optionen

- `--sample-size 0`: alle BLS-Gerichte testen
- `--weeks 4`: mehrere Wochen simulieren
- `--show-weeks`: Zeige detaillierte Wochen-Ergebnisse (Standard: deaktiviert)
- `--stress-profile noisy`: absichtlich schwierigere Texte erzeugen
  - `none` (Standard): unveränderte BLS-Namen
  - `noisy`: Zusätze wie "frisch", "hausgemacht" hinzufügen
  - `long`: längere, zusammengesetzte Beschreibungen
  - `duplicate`: Namen mehrfach/mit Trennzeichen
  - `ambiguous`: Kombinationen mehrerer Gerichtsnamen
- `--report-out /tmp/report.json`: JSON-Report speichern

### Beispiele

Schneller Test mit 10 Gerichten:

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 10 --seed 42
```

Test mit 100 Gerichten über 10 Wochen und detaillierten Wochen-Ergebnissen:

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 100 --seed 42 --weeks 10 --show-weeks
```

**Alle 7.140 BLS-Gerichte testen** (ca. 1-2 Minuten, automatisch verteilt auf ~143 Wochen):

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 0 --seed 42 --stress-profile none --report-out /tmp/all_bls_results.json
```

Stress-Test mit schwierigeren Texten (ambig) und Wochen-Details:

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 50 --seed 7 --weeks 2 --stress-profile ambiguous --show-weeks
```

JSON-Report schreiben:

```sh
cd backend
.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 100 --seed 42 --report-out /tmp/quant_eval_report.json
```

### Ausgabe interpretieren

Die Konsole zeigt:

- **Gesamtgerichte**: Anzahl getesteter Items
- **Erkannt**: Anzahl erfolgreich zugeordneter Items (%)
- **Über BLS-Code erkannt**: Erfolgreiche BLS-Treffer (%)
- **Unverändert unzugeordnet**: Items ohne Zuordnung (%)
- **Mehrfach zugeordnete**: Items, die mehreren Gruppen zugeordnet wurden (%)
- **Hauptgründe für Nicht-Erkennung**: Fehlerklassifikation mit Beispiel-Items
- **Top Primärgruppen**: Häufigste erkannte Lebensmittelgruppen
- **Wochen-Details** (mit `--show-weeks`): Pro Woche erkannte und nicht erkannte Items

Der JSON-Report enthält zusätzlich:

- `summary.group_distribution`: Verteilung der erkannten Primärgruppen
- `summary.unmapped_reason_counts`: Gründe für nicht erkannte Items
- `summary.per_week[*]`: Details pro Woche mit erkannten/nicht erkannten Items
- `summary.per_week_summary`: Statistiken über alle Wochen hinweg

### Backend-Tests starten

### Einmalig installieren

Im Projekt-Root (mit aktiver venv):

```sh
source .venv/bin/activate
pip install pytest
```

### Alle Tests ausführen

```sh
.venv/bin/python -m pytest backend/tests -q
```

### Einzelne Datei testen

```sh
.venv/bin/python -m pytest backend/tests/test_parse_foodplan.py -q
```

### Einzelnen Testfall ausführen

```sh
.venv/bin/python -m pytest backend/tests/test_parse_foodplan.py::test_parse_month_example_groups_into_4_weeks_and_20_days -q
```

Aktuell enthalten die Tests u.a. Prüfungen für:

- BLS-Code-Matching und Gruppen-Ableitung
- mehrteilige Gerichte wie `Hähnchen mit Reis`
- korrektes Zusammenführen von Fortsetzungszeilen
- Monatsbeispiel-Datei mit 4 Wochen / 20 Tagen

### Quantitativer BLS-Test

Wenn man messen will, wie gut die aktuelle Enrichment-Logik BLS-Gerichte erkennt, kann man das CLI-Skript ausführen:

```sh
cd backend
# Standard: keine Seed-Angabe → bei jedem Aufruf neue Zufallsstichprobe
./.venv/bin/python scripts/quantitative_bls_eval.py --all
```

Optional kannst du nur eine Teilmenge testen:

```sh
cd backend
# Teilmenge testen, standardmäßig ohne festen Seed (zufällige Auswahl)
./.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 200
```

Das Skript loggt im Terminal u.a.:

- Gesamtzahl der getesteten Gerichte
- direkt erkannte Gerichte vor dem BLS-Fallback
- final erkannte Gerichte inkl. BLS-Fallback
- Anzahl unzugeordneter Einträge
- Top-Gruppenverteilung

Der Parameter `--seed` steuert die Zufallsauswahl bei Stichproben und bei
der internen Reihenfolge des Testlaufs. Wenn du `--seed` weglässt, erzeugt
jeder Aufruf eine neue, zufällige Stichprobe (praktisch für Exploration).
Setze `--seed <zahl>` (z. B. `--seed 42`), wenn du einen Lauf reproduzierbar
machen möchtest.

Auf Wunsch kannst du zusätzlich einen JSON-Report schreiben lassen:

```sh
cd backend
# Mit Report-Ausgabe (optional) — Seed weglassen für neue Stichprobe, oder setzen für Reproduzierbarkeit
./.venv/bin/python scripts/quantitative_bls_eval.py --all --report-out instance/quantitative_bls_report.json
```

#### Wochen‑Simulation (`--weeks`)

Du kannst mehrere Wochen simulieren lassen, damit das Skript **pro Woche** Metriken ausgibt
und im Report die Liste `per_week` sowie die Aggregation `per_week_summary` enthält.

- Default: `--weeks 1` (eine Woche).
- Beispiel: `--weeks 4` simuliert 4 Wochen und verteilt die getesteten Gerichte auf
  `4 * 5` Wochentage.

Beispielaufruf mit 4 Wochen und Report‑Ausgabe:

```sh
cd backend
./.venv/bin/python scripts/quantitative_bls_eval.py --sample-size 100 --weeks 4 --report-out instance/bls_report_4w.json
```

Im erzeugten JSON‑Report findest du dann unter `summary.per_week` die Metriken pro
Woche und unter `summary.per_week_summary` die zusammenfassenden Kennzahlen
(Durchschnittsrate, Minimum, Maximum der finalen Erkennungsraten pro Woche).

Jede Woche im Report enthält zudem:

- `items_recognized`: Liste der erkannten Gerichte (mit Gruppen, Confidence, ggf. BLS-ID)
- `items_unmapped`: Liste der nicht erkannten Gerichte

**Console-Ausgabe:** Bei der Ausführung werden pro Woche die Top 10 erkannten und nicht erkannten Gerichte angezeigt (in tabellarischer Form mit Gruppen und Confidence-Werten), sodass du schnell sehen kannst, wo das System gut funktioniert und wo es Probleme gibt.

Hinweis: Wenn du `--seed` weglässt, erzeugt jeder Aufruf eine neue zufällige
Stichprobe; setze `--seed <zahl>` für reproduzierbare Läufe.

### Backend-Coverage anzeigen

```sh
.venv/bin/python -m pytest backend/tests --cov=backend --cov-report=term-missing
```

### Frontend-Tests starten

Im Frontend-Ordner:

```sh
cd frontend
npm install
npm test -- --coverage
```

Alternativ direkt aus dem Projekt-Root:

```sh
npm --prefix frontend test -- --coverage
```

Der Frontend-Testlauf prüft aktuell unter anderem:

- die Upload- und Hilfekomponente
- den Selbstcheck-Flow
- die Report-Anzeige
- die Next.js-Proxy-Routen `/api/preview` und `/api/analyze`

### Alle Tests zusammen

Wenn Backend und Frontend direkt nacheinander ausführen willst:

```sh
.venv/bin/python -m pytest backend/tests -q && npm --prefix frontend test -- --coverage
```

## 8) Konfiguration (Umgebungsvariablen)

Umgebungsvariablen (Environment Variables) sind **optionale Einstellungen**, die du im Terminal setzt, damit Skripte/Apps anders arbeiten, **ohne dass du Code ändern musst**.

In diesem Projekt ist aktuell vor allem diese Variable relevant:

### `BLS_XLSX_PATH`

- **Wofür?** Steuert, **welche Excel-Datei** beim Import (`python backend/import_bls.py`) verwendet wird.
- **Standard (wenn nicht gesetzt):** `data/BLS_4_0_Daten_2025_DE.xlsx`
- **Wann brauchst du das?** Wenn die Excel-Datei bei dir **an einem anderen Ort** liegt oder anders heißt.

Beispiel (Excel liegt z.B. in Downloads):

```sh
export BLS_XLSX_PATH="$HOME/Downloads/BLS_4_0_Daten_2025_DE.xlsx"
python backend/import_bls.py
```

> Tipp: Du kannst den aktuellen Wert prüfen mit `echo $BLS_XLSX_PATH`.

| Variable        | Bedeutung                              | Beispiel                               |
| --------------- | -------------------------------------- | -------------------------------------- |
| `BLS_XLSX_PATH` | Pfad zur BLS-Exceldatei für den Import | `export BLS_XLSX_PATH="/tmp/BLS.xlsx"` |

## 9) Häufige Probleme

### `ModuleNotFoundError: No module named 'flask'`

Du verwendest sehr wahrscheinlich den falschen Python-Interpreter.

- Stelle sicher, dass die venv aktiv ist (`source .venv/bin/activate`)
- und installiere die Requirements (`pip install -r backend/requirements.txt`)

### Import findet Excel nicht

- Stelle sicher, dass die Datei unter `data/BLS_4_0_Daten_2025_DE.xlsx` liegt
- oder setze `BLS_XLSX_PATH`

### Port belegt

Wenn `127.0.0.1:5000` belegt ist, stoppe den Prozess, der den Port nutzt, oder starte das Backend auf einem anderen Port (ggf. Code in `backend/app.py` anpassen).

### `sqlite3.OperationalError: unable to open database file`

Typische Ursachen:

- Der DB-Pfad zeigt auf einen Ordner, der nicht existiert.
- Es wird ein falscher/unerwarteter `DATABASE_URL` verwendet.

Checkliste:

1. Sicherstellen, dass die venv aktiv ist.
2. Optional gesetzte Variablen prüfen: `echo $DATABASE_URL` und `echo $BLS_DB_PATH`.
3. Für Standardbetrieb ohne Sonderpfade `DATABASE_URL` nicht setzen und `python backend/import_bls.py` aus dem Projekt-Root starten.
4. Wenn `DATABASE_URL` gesetzt wird, immer einen absoluten SQLite-Pfad mit existierendem Parent-Ordner verwenden.

## `npm run dev` hängt bei "Starting..."

Wenn der Next.js Dev-Server bei **"Starting..."** hängen bleibt, hilft in der Regel ein kompletter Clean-Reinstall (Cache + Dependencies neu aufsetzen):

```sh
cd frontend

# Next Build-Cache + Dependencies entfernen
rm -rf node_modules package-lock.json .next

# Alles neu installieren
npm install

# Dev-Server starten
npm run dev
```

## 10) Projekt-Dateien (Kurzüberblick)

- `backend/app.py`: Flask-API (Routes)
- `backend/models.py`: SQLAlchemy Modelle + `to_dict()`
- `backend/import_bls.py`: Import aus Excel in SQLite
- `backend/scripts/`: Hilfsskripte für Verarbeitung/Evaluation (siehe unten)
  - `backend/scripts/enrich_foodplan.py`: reichert `foodplan.json` mit `links.food_group`, `tags` und Confidence an (Output: `foodplan.enriched.json`)
  - `backend/scripts/evaluate_foodplan.py`: bewertet einen (enriched) Plan gegen `rules/dge_lunch_rules.json` und erzeugt einen Dual-Report (`report.dual.json`)
- `backend/rules/`: Regel- und Mapping-Dateien (JSON)
  - `backend/rules/dge_lunch_rules.json`: Regeln für die DGE-Lunch-Auswertung
  - `backend/rules/DGE_GRAMM_TODO.md`: Arbeitsstand + TODO-Liste für die geplante Gramm-Regelumsetzung
  - `backend/rules/bls_to_dge_groups.json`: Mapping/Keywords zur Zuordnung BLS/Begriffe -> DGE-Food-Groups
- `backend/instance/bls.db`: SQLite Datenbankdatei (wird beim Import erzeugt)
- `backend/instance/uploads/`: optionaler Ordner (derzeit nicht genutzt) – Uploads werden in-memory verarbeitet und nicht auf Disk gespeichert

- `frontend/app/page.tsx`: steuert den Frontend-Ablauf (Upload -> Report -> Selbstcheck) und verwaltet den Haupt-UI-State
- `frontend/app/lib/foodplan.ts`: gemeinsame Typen, Labels, Styles und kleine Helper-Funktionen für Foodgroups/Tags
- `frontend/app/components/navigation/StepNavigation.tsx`: Schrittanzeige + Navigation zwischen Upload und Report
- `frontend/app/components/upload/UploadSection.tsx`: Upload-UI mit Klick/Drag-and-Drop + Template-Link
- `frontend/app/components/selfcheck/SelfCheckSection.tsx`: Selbstcheck-UI zum Bearbeiten von Foodgroups/Tags und erneuten Auswerten
- `frontend/app/components/report/ReportSection.tsx`: Report-Container (Warnhinweis, Monats-/Wochenansicht, Regelbereiche)
- `frontend/app/components/report/ReportCards.tsx`: wiederverwendbare Report-Bausteine (`ScoreCard`, `RulesList`)
- `frontend/app/api/preview/route.ts`: Next.js-Proxyroute für Preview-Requests zum Backend
- `frontend/app/api/analyze/route.ts`: Next.js-Proxyroute für Analyse-Requests zum Backend

  ## 11) Transparenz: Einsatz von KI

  Im Rahmen der Entwicklung wurde KI punktuell zur Ideengenerierung (Brainstorming) sowie als Programmierassistenz genutzt. Die originären Projektideen, die Auswahl der Lösungswege und die fachliche Verantwortung liegen bei mir. KI-generierte Inhalte wurden nicht ungeprüft übernommen, sondern eigenständig überprüft, überarbeitet und testbasiert abgesichert.
