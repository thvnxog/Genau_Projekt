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
import io
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
        """Analysiert einen hochgeladenen Speiseplan und gibt einen Dual-Report zurück.

        Erwartung:
        - multipart/form-data Upload mit Feldname "file"
        - aktuell: .xlsx im KW47-Template

        Ablauf (ohne Upload-Datei auf Disk zu speichern):
        1) Upload holen
        2) XLSX in-memory parsen -> foodplan-Format
        3) Enrichment (food_group + tags)
        4) Normalisieren (Datenhygiene)
        5) Regeln laden
        6) Evaluation (dual)
        7) Report als JSON zurücckgeben
        """

        # 1) Upload aus der HTTP-Anfrage lesen
        f = request.files.get("file")
        if not f:
            abort(400, description="Kein Upload unter 'file' gefunden.")

        # Dateiname bereinigen (Sicherheit) und Suffix bestimmen
        filename = secure_filename(f.filename or "upload.json")
        suffix = Path(filename).suffix.lower()

        # Datei NICHT speichern – nur in-memory verarbeiten
        data = f.read()
        bio = io.BytesIO(data)

        # 2) Dateityp-Check: ab jetzt nur XLSX (KW47-Template)
        if suffix != ".xlsx":
            abort(400, description="Bitte eine .xlsx Datei im KW47-Template hochladen.")

        # 3) XLSX parsen -> foodplan.json-Format
        from scripts.parse_foodplan_xlsx import parse_foodplan_xlsx
        plan = parse_foodplan_xlsx(bio)


        # 4) Enrichment: food_group + tags setzen
        from scripts.enrich_foodplan import load_keyword_files, load_json_mapping, merge_keywords, enrich_plan

        base_dir = Path(__file__).resolve().parent  # backend/
        keywords_root = base_dir / "rules" / "keywords"
        mapping_json = base_dir / "rules" / "bls_to_dge_groups.json"

        group_txt = load_keyword_files(keywords_root / "groups")
        tag_txt = load_keyword_files(keywords_root / "tags")
        group_json, tag_json = load_json_mapping(mapping_json)

        group_keywords = merge_keywords(group_txt, group_json)
        tag_keywords = merge_keywords(tag_txt, tag_json)

        plan, _stats = enrich_plan(plan, group_keywords, tag_keywords, bls_db_path=None)

        # 5) Normalisieren (deine Datenhygiene)
        plan = normalize_plan(plan)

        # 6) Regeln laden (robust, relativ zu backend/)
        rules_path = base_dir / "rules" / "dge_lunch_rules.json"
        if not rules_path.exists():
            abort(500, description="rules/dge_lunch_rules.json nicht gefunden (Pfad prüfen).")
        rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))

        # 7) Evaluation (dual)
        from scripts.evaluate_foodplan import evaluate_plan_for_diet

        report = {
            "schema_version": "1.0",
            "mode": "dual",
            "mixed": evaluate_plan_for_diet(plan, rules_doc, "mixed"),
            "ovo_lacto_vegetarian": evaluate_plan_for_diet(plan, rules_doc, "ovo_lacto_vegetarian"),
            "debug": {
                # Upload wird nicht gespeichert; nur der Name wird zurückgegeben.
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
