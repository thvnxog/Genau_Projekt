"""backend/models.py

ORM-Modelle für die Datenbank.

In SQLAlchemy/Flask-SQLAlchemy wird eine Datenbank-Tabelle als Python-Klasse beschrieben.
- `db = SQLAlchemy()` ist das zentrale DB/ORM-Objekt.
- Jede Model-Klasse (z.B. `Food`) entspricht einer Tabelle.
- Jede `db.Column(...)` entspricht einer Spalte.

Diese Models werden in `backend/app.py` an die Flask-App gebunden über:
- `db.init_app(app)`

Hinweis:
- Das Schema legst du hier im Code fest.
- Wenn du Spalten hinzufügst/entfernst, musst du i.d.R. die DB neu erzeugen
  (oder später Migrationen einsetzen).
"""

from flask_sqlalchemy import SQLAlchemy

# `db` wird in `backend/app.py` initialisiert (db.init_app).
# Danach kann man damit:
# - Tabellen erzeugen: db.create_all()
# - Queries ausführen: Food.query...
db = SQLAlchemy()


class Food(db.Model):
    """Lebensmittel-Tabelle (`foods`).

    Ein `Food`-Objekt entspricht einer Zeile in der Tabelle.

    Warum eine eigene ID?
    - Wir nutzen eine auto-increment ID als Primary Key (`id`).
    - Falls die BLS-Excel einen stabilen eindeutigen Code hat, könnte man den später
      ebenfalls speichern und/oder als Key verwenden.
    """

    # Expliziter Tabellenname in der DB
    __tablename__ = "foods"

    # Primary Key (autoincrement Integer)
    id = db.Column(db.Integer, primary_key=True)

    # Lebensmittel-Name (Deutsch)
    # - nullable=False: darf nicht leer sein
    # - index=True: beschleunigt Suchabfragen (z.B. /foods?q=...)
    name_de = db.Column(db.String(500), nullable=False, index=True)

    # Nährwerte pro 100g (können fehlen -> nullable=True)
    # energy_kj = db.Column(db.Float, nullable=True)  # aktuell deaktiviert
    energy_kcal = db.Column(db.Float, nullable=True)
    water_g = db.Column(db.Float, nullable=True)
    protein_g = db.Column(db.Float, nullable=True)
    fat_g = db.Column(db.Float, nullable=True)
    carbs_g = db.Column(db.Float, nullable=True)

    def to_dict(self) -> dict:
        """Wandelt das ORM-Objekt in ein JSON-serialisierbares Dict um.

        Flask kann Dicts direkt als JSON zurückgeben (Response).

        Struktur der Ausgabe:
        - `id`, `name_de` auf Top-Level
        - Nährwerte gebündelt unter `per_100g`

        Vorteil:
        - API-Antworten bleiben stabil, auch wenn intern Spalten umbenannt werden.
        """

        return {
            "id": self.id,
            "name_de": self.name_de,
            "per_100g": {
                # "energy_kj": self.energy_kj,
                "energy_kcal": self.energy_kcal,
                "water_g": self.water_g,
                "protein_g": self.protein_g,
                "fat_g": self.fat_g,
                "carbs_g": self.carbs_g,
            },
        }
