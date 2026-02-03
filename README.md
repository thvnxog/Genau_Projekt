# Genau_Projekt (BLS Food API)

Kleines **Flask + SQLite** Backend, das Daten aus der BLS-Excel importiert und über eine JSON-API durchsuchbar macht.

## Quickstart (End-to-End testen)

Du willst nur schnell prüfen, ob alles läuft? Dann:

1. Setup (venv + Pakete)

```sh
cd <pfad-zum-projekt>/Genau_Projekt
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. DB erstellen + BLS importieren

```sh
rm -f backend/instance/bls.db
python backend/import_bls.py
```

3. Backend starten

```sh
python backend/app.py
```

4. API testen

```sh
curl http://127.0.0.1:5000/health
curl "http://127.0.0.1:5000/foods?q=apfel&limit=5"
```

5. (Optional) Frontend starten und im Browser testen

```sh
cd frontend
npm install
npm run dev
```

Dann im Browser öffnen:

- http://localhost:3000

> Hinweis: Das Frontend nutzt die Route `frontend/app/api/analyze/route.ts`. Je nach Implementierung ruft diese Route intern das Flask-Backend auf oder verarbeitet die Daten selbst. Wenn im Frontend Fehler auftauchen: Backend starten und die DevTools-Konsole prüfen.

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

> Hinweis: Falls bei euch statt `requirements.txt` nur `requierements.txt` existiert, benennt die Datei um oder installiert entsprechend aus dieser Datei.

## 3) Datenbank neu erstellen + Import aus Excel

Die SQLite-DB liegt (typisch) unter `backend/instance/bls.db`.

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

## 4) Server starten

```sh
python backend/app.py
```

Der Server läuft dann lokal auf:

- `http://127.0.0.1:5000`

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

Dann:

- http://localhost:3000

## 7) Testdaten

Zum schnellen Testen liegen Beispiel-Dateien hier:

- `backend/instance/testdata/`

Nützlich sind u.a.:

- `foodplan.json`
- `foodplan.enriched.json`

Diese Dateien kannst du im Frontend per Upload verwenden (falls aktiviert) oder als Referenz für erwartete Report-Strukturen.

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

## 10) Projekt-Dateien (Kurzüberblick)

- `backend/app.py`: Flask-API (Routes)
- `backend/models.py`: SQLAlchemy Modelle + `to_dict()`
- `backend/import_bls.py`: Import aus Excel in SQLite
- `backend/instance/bls.db`: SQLite Datenbankdatei
- `data/`: Excel-Quelle
- `frontend/`: Next.js Frontend
