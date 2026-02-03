"""
models.py
Hier definiere ich, wie ein Datensatz in der Datenbank aussieht.

Für den Anfang speichern wir:
- name_de (Lebensmittelbezeichnung)
- ein paar Nährwerte pro 100g (kJ/kcal/Wasser/Protein/Fett/CHO)

Später kann man das erweitern (z. B. mehr Nährwerte, Gruppen, etc.).
"""

from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy ist die Bibliothek, die uns Python-Objekte <-> DB-Tabellen abbildet.
db = SQLAlchemy()

# Definiere die Tabelle 'foods' als Python-Klasse
class Food(db.Model):
    """
    Eine Zeile in der Tabelle 'foods'.

    Ich benutze eine einfache autoincrement ID, weil ich nicht sicher weiß,
    ob die Excel eine zuverlässige eindeutige ID-Spalte hat (z. B. BLS-Code).
    Wenn du den BLS-Code findest, kann man den später als Primary Key nutzen.
    """
    __tablename__ = "foods"

    id = db.Column(db.Integer, primary_key=True)

    # Lebensmittelname (deutsch) – das ist unser Hauptsuchfeld
    name_de = db.Column(db.String(500), nullable=False, index=True)

    # Typische Nährwerte (pro 100g)
    #energy_kj = db.Column(db.Float, nullable=True)
    energy_kcal = db.Column(db.Float, nullable=True)
    water_g = db.Column(db.Float, nullable=True)
    protein_g = db.Column(db.Float, nullable=True)
    fat_g = db.Column(db.Float, nullable=True)
    carbs_g = db.Column(db.Float, nullable=True)

    # Hilfsfunktion: DB-Objekt -> Dictionary (für spätere API-Ausgabe)
    def to_dict(self):
        """
        Kleine Hilfsfunktion: DB-Objekt -> Dictionary (für spätere API-Ausgabe)
        """
        return {
            "id": self.id,
            "name_de": self.name_de,
            "per_100g": {
                #"energy_kj": self.energy_kj,
                "energy_kcal": self.energy_kcal,
                "water_g": self.water_g,
                "protein_g": self.protein_g,
                "fat_g": self.fat_g,
                "carbs_g": self.carbs_g,
            }
        }
