"""
app.py
Ein sehr kleiner Flask-Server, der:
- eine SQLite-Datenbank benutzt
- beim Start (einmal) die Tabellen erstellt

Für jetzt machen wir nur "health check".
Die API-Endpunkte kommen danach.
"""

import os
import json
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, request, abort
from dotenv import load_dotenv

from models import db, Food

# .env laden (optional)
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Datenbank-URL:
    # - Default: sqlite:///bls.db (landet dann im Flask instance-Ordner)
    # - kann über .env überschrieben werden (DATABASE_URL=...)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///bls.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # DB mit der App verbinden
    db.init_app(app)

    @app.get("/health")
    def health():
        # Minimale Route zum Testen, ob der Server läuft
        return {"status": "ok"}
    

    @app.get("/foods")
    def search_foods():
        """
        Beispiel:
        /foods?q=apfel&limit=10

        Gibt eine Liste von Treffern zurück (ohne alle Nährwerte, damit es schnell bleibt).
        """
        q = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 10)

        if not q:
            return {"items": []}

        # Case-insensitive Suche in SQLite
        like = f"%{q.lower()}%"
        hits = (
            Food.query
            .filter(db.func.lower(Food.name_de).like(like))
            .limit(limit)
            .all()
        )

        return {
            "items": [
                {"id": h.id, "name_de": h.name_de}
                for h in hits
            ]
        }


    @app.get("/foods/<int:food_id>")
    def get_food(food_id: int):
        """
        Gibt Details inkl. Nährwerte für einen Eintrag zurück.
        """
        item = Food.query.get(food_id)
        if not item:
            abort(404, description="Food not found")

        return item.to_dict()
    
        
    def normalize_plan(plan: dict) -> dict:
        """
        Kleine Datenhygiene, damit die Evaluation stabil läuft:
        - vegetable / vegetables -> vegetables
        - raw_veg als food_group -> vegetables + Tag raw_veg
        """
        for day in plan.get("days", []) or []:
            for menu in day.get("menus", []) or []:
                for item in menu.get("items", []) or []:
                    links = item.get("links") or {}
                    fg = links.get("food_group")

                    # 1) alias vereinheitlichen
                    if fg in ("vegetable", "vegetables"):
                        links["food_group"] = "vegetables"

                    # 2) raw_veg falsch als food_group -> korrigieren
                    if fg == "raw_veg":
                        links["food_group"] = "vegetables"
                        tags = item.get("tags") or []
                        if "raw_veg" not in tags:
                            tags.append("raw_veg")
                        item["tags"] = tags

                    item["links"] = links
        return plan

    @app.post("/api/analyze")
    def analyze():
        """
        Nimmt JSON (foodplan) per Upload entgegen und liefert Dual-Report zurück.
        Später erweitern wir auf Excel.
        """
        f = request.files.get("file")
        if not f:
            abort(400, description="Kein Upload unter 'file' gefunden.")

        filename = secure_filename(f.filename or "upload.json")
        suffix = Path(filename).suffix.lower()

        # Fürs Debuggen speichern wir die Datei kurz in instance/uploads
        upload_dir = Path(app.instance_path) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / filename
        f.save(saved_path)

        if suffix != ".json":
            abort(400, description="Für den Test akzeptieren wir erstmal nur .json (Excel kommt als nächstes).")

        # JSON laden
        try:
            plan = json.loads(saved_path.read_text(encoding="utf-8"))
        except Exception as e:
            abort(400, description=f"Ungültiges JSON: {e}")

        # Normalisieren (siehe oben)
        plan = normalize_plan(plan)

        # Regeln laden
        rules_path = Path("rules/dge_lunch_rules.json")
        if not rules_path.exists():
            abort(500, description="rules/dge_lunch_rules.json nicht gefunden (Pfad prüfen).")

        rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))

        # Evaluation ausführen:
        # -> Wir importieren hier den Script-Code.
        # Stelle sicher, dass die Datei so liegt: backend/scripts/evaluate_foodplan.py
        from scripts.evaluate_foodplan import evaluate_plan_for_diet

        report = {
            "schema_version": "1.0",
            "mode": "dual",
            "mixed": evaluate_plan_for_diet(plan, rules_doc, "mixed"),
            "ovo_lacto_vegetarian": evaluate_plan_for_diet(plan, rules_doc, "ovo_lacto_vegetarian"),
            "debug": {
                "saved_upload": str(saved_path),
                "source_filename": filename,
            }
        }

        return report


    return app




if __name__ == "__main__":
    app = create_app()

    # Tabellen erstellen, falls noch nicht vorhanden
    with app.app_context():
        db.create_all()

    # Server starten
    app.run(host="127.0.0.1", port=5000, debug=True)
