"""
app.py

Flask-Backend für das GENAU-Projekt.

Enthält:
- App-Factory (create_app)
- SQLAlchemy/SQLite Konfiguration
- einfache Food-Such-API (/foods)
- Analyse-Endpunkt (/api/analyze), der einen hochgeladenen Foodplan (JSON) evaluiert

Hinweis:
- Die SQLite-Datei liegt standardmäßig im Flask "instance"-Ordner.
- "instance" ist bewusst NICHT im Code-Repo-Root, sondern außerhalb des Python-Pakets,
  damit Laufzeitdaten (DB, Uploads) sauber getrennt sind.
"""

import os
import json
from pathlib import Path

# secure_filename sorgt dafür, dass Dateinamen "sicher" sind (keine ../ Traversal, keine Sonderzeichen)
from werkzeug.utils import secure_filename

# Flask = Webframework, request = eingehende HTTP Anfrage, abort = Fehlerantworten (z.B. 400/404)
from flask import Flask, request, abort

# .env laden: erlaubt lokale Konfiguration ohne Codeänderung (z.B. DATABASE_URL)
from dotenv import load_dotenv

# Unser SQLAlchemy-DB-Objekt und das Food-Model
from models import db, Food

# .env laden (optional). Falls keine .env existiert, passiert nichts.
load_dotenv()


def create_app():
    """Erzeugt und konfiguriert die Flask-App.

    Wichtig: Das ist eine klassische "App Factory".
    Vorteil: Tests/Tools können die App erzeugen, ohne dass sofort ein Server startet.
    """

    app = Flask(__name__)

    # --- Datenbank-Konfiguration -------------------------------------------------
    # SQLALCHEMY_DATABASE_URI gibt an, wo die Datenbank liegt.
    # Default: sqlite:///bls.db
    #   -> Bei Flask bedeutet das: die Datei liegt im instance-Ordner (z.B. backend/instance/bls.db).
    #   -> Der instance-Ordner ist pro Installation/Umgebung gedacht.
    # Per .env kann man das überschreiben:
    #   DATABASE_URL=sqlite:////absoluter/pfad/bls.db
    #   DATABASE_URL=postgresql://...
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///bls.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # DB mit der App verbinden (Initialisierung von Flask-SQLAlchemy)
    db.init_app(app)

    # --- API Endpunkte -----------------------------------------------------------

    @app.get("/health")
    def health():
        """Kleiner Health-Check: zeigt, ob der Server läuft."""
        return {"status": "ok"}

    @app.get("/foods")
    def search_foods():
        """Sucht Lebensmittel in der DB per Query-String.

        Beispiel:
          /foods?q=apfel&limit=10

        - q: Suchbegriff (mindestens 1 Zeichen)
        - limit: max. Treffer (Default 10)

        Wir geben absichtlich nur (id, name_de) zurück, damit die Antwort schnell bleibt.
        Details + Nährwerte gibt es über /foods/<id>.
        """

        # Query-Parameter auslesen (falls nicht gesetzt -> "")
        q = (request.args.get("q") or "").strip()

        # limit ist optional. Falls nicht gesetzt -> 10.
        # Achtung: int(...) kann bei nicht-numerischen Werten eine ValueError werfen;
        # für PoC ok, könnte man später robuster machen.
        limit = int(request.args.get("limit") or 10)

        if not q:
            return {"items": []}

        # Case-insensitive Suche in SQLite:
        # - wir wandeln sowohl DB-Wert als auch q zu lower-case,
        # - und nutzen LIKE mit %...% für "enthält".
        like = f"%{q.lower()}%"
        hits = (
            Food.query.filter(db.func.lower(Food.name_de).like(like))
            .limit(limit)
            .all()
        )

        return {"items": [{"id": h.id, "name_de": h.name_de} for h in hits]}

    @app.get("/foods/<int:food_id>")
    def get_food(food_id: int):
        """Liefert Details für ein Lebensmittel inkl. Nährwerten.

        - food_id: Primärschlüssel in der Tabelle.
        - Rückgabe: Food.to_dict() (siehe backend/models.py)
        """

        # .get(...) liest nach Primärschlüssel.
        item = Food.query.get(food_id)
        if not item:
            abort(404, description="Food not found")

        return item.to_dict()

    # --- Hilfsfunktionen für /api/analyze --------------------------------------

    def normalize_plan(plan: dict) -> dict:
        """Normalisiert ein Foodplan-JSON, damit die Regel-Evaluation stabil läuft.

        Problem: In Eingabedaten können leicht unterschiedliche Schreibweisen vorkommen.
        Beispiele:
        - food_group: "vegetable" vs "vegetables"
        - food_group: "raw_veg" ist eigentlich keine Gruppe, sondern eher ein Tag

        Wir korrigieren daher:
        1) "vegetable"/"vegetables" -> "vegetables"
        2) "raw_veg" -> food_group "vegetables" + Tag "raw_veg"

        Wichtig:
        - Wir mutieren (ändern) das dict in-place und geben es zurück.
        - Das ist für diesen PoC ok.
        """

        # Erwartete Struktur im Plan:
        # plan = {"days": [{"menus": [{"items": [{"links": {...}, "tags": [...]}, ...]}]}]}
        for day in plan.get("days", []) or []:
            for menu in day.get("menus", []) or []:
                for item in menu.get("items", []) or []:
                    links = item.get("links") or {}
                    fg = links.get("food_group")

                    # 1) Alias vereinheitlichen
                    if fg in ("vegetable", "vegetables"):
                        links["food_group"] = "vegetables"

                    # 2) raw_veg falsch als food_group -> korrigieren
                    if fg == "raw_veg":
                        # Gruppe auf Gemüse setzen
                        links["food_group"] = "vegetables"

                        # Tag raw_veg hinzufügen, damit Regeln das trotzdem erkennen können
                        tags = item.get("tags") or []
                        if "raw_veg" not in tags:
                            tags.append("raw_veg")
                        item["tags"] = tags

                    # links wieder zurückschreiben (falls item.links vorher None war)
                    item["links"] = links

        return plan

    @app.post("/api/analyze")
    def analyze():
        """Analysiert einen hochgeladenen Foodplan (JSON) und gibt einen Dual-Report zurück.

        Erwartung:
        - multipart/form-data Upload mit Feldname "file"
        - aktuell nur .json (Excel ist als nächster Schritt geplant)

        Ablauf:
        1) Datei holen und (für Debug) im instance/uploads speichern
        2) JSON laden
        3) Foodplan normalisieren (Datenhygiene)
        4) Regeldefinitionen laden (rules/dge_lunch_rules.json)
        5) Evaluation ausführen (scripts/evaluate_foodplan.py)
        6) Report als JSON zurückgeben
        """

        # 1) Upload aus der HTTP-Anfrage lesen
        f = request.files.get("file")
        if not f:
            abort(400, description="Kein Upload unter 'file' gefunden.")

        # Dateiname bereinigen (Sicherheit) und Suffix bestimmen
        filename = secure_filename(f.filename or "upload.json")
        suffix = Path(filename).suffix.lower()

        # Für Debugging speichern wir Uploads in backend/instance/uploads/
        # app.instance_path zeigt auf den instance-Ordner.
        upload_dir = Path(app.instance_path) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / filename
        f.save(saved_path)

        # 2) Dateityp-Check: derzeit nur JSON
        if suffix != ".json":
            abort(
                400,
                description=(
                    "Für den Test akzeptieren wir erstmal nur .json (Excel kommt als nächstes)."
                ),
            )

        # 3) JSON laden
        try:
            plan = json.loads(saved_path.read_text(encoding="utf-8"))
        except Exception as e:
            abort(400, description=f"Ungültiges JSON: {e}")

        # 4) Normalisieren (siehe oben)
        plan = normalize_plan(plan)

        # 5) Regeln laden
        # Achtung: relativer Pfad. Funktioniert zuverlässig, wenn man aus backend/ startet
        # oder wenn das Working Directory korrekt ist.
        rules_path = Path("rules/dge_lunch_rules.json")
        if not rules_path.exists():
            abort(500, description="rules/dge_lunch_rules.json nicht gefunden (Pfad prüfen).")

        rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))

        # 6) Evaluation ausführen:
        # Wir importieren hier den Script-Code.
        # Stelle sicher, dass die Datei so liegt: backend/scripts/evaluate_foodplan.py
        from scripts.evaluate_foodplan import evaluate_plan_for_diet

        # Dual-Report: wir berechnen 2 Varianten
        report = {
            "schema_version": "1.0",
            "mode": "dual",
            "mixed": evaluate_plan_for_diet(plan, rules_doc, "mixed"),
            "ovo_lacto_vegetarian": evaluate_plan_for_diet(
                plan, rules_doc, "ovo_lacto_vegetarian"
            ),
            # Debug-Infos helfen bei der Fehlersuche
            "debug": {
                "saved_upload": str(saved_path),
                "source_filename": filename,
            },
        }

        return report

    return app


if __name__ == "__main__":
    # Direkt-Start (nur wenn man `python backend/app.py` ausführt)
    app = create_app()

    # Tabellen erstellen, falls noch nicht vorhanden.
    # Das ist bequem im PoC. In "echten" Projekten macht man Migrationen.
    with app.app_context():
        db.create_all()

    # Server starten (debug=True = Auto-Reload + bessere Errors)
    app.run(host="127.0.0.1", port=5000, debug=True)
