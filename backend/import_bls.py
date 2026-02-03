"""
import_bls.py

Dieses Skript importiert Daten aus der offiziellen BLS-Exceldatei in unsere SQLite-Datenbank.

Warum ein separates Import-Skript?
- Die Exceldatei ist groß und das Einlesen dauert.
- Wir importieren deshalb einmal in eine DB und verwenden danach nur noch SQL (schnell).

Wie wird es benutzt?
- `python backend/import_bls.py`
- Falls die Excel nicht unter `data/` liegt, kann der Pfad per Environment Variable gesetzt werden:
  `export BLS_XLSX_PATH="/pfad/zur/BLS_4_0_Daten_2025_DE.xlsx"`
"""

import os

# pandas: liest Excel komfortabel und behandelt NaN/fehlende Werte.
import pandas as pd

# Wir nutzen die gleiche App/DB-Konfiguration wie der Server.
from app import create_app
from models import db, Food

# --- Konfiguration -------------------------------------------------------------
# Default-Pfad zur Excel (relativ zu `backend/` gedacht).
# Über `BLS_XLSX_PATH` kann man den Pfad überschreiben, ohne Code zu ändern.
DEFAULT_XLSX = os.getenv("BLS_XLSX_PATH", "../data/BLS_4_0_Daten_2025_DE.xlsx")


def safe_float(value):
    """Konvertiert Excel-Zellen robust zu float.

    Hintergrund:
    - In Excel können Zellen leer sein (NaN) oder als Text vorliegen.
    - SQLAlchemy-Spalten erwarten für numerische Werte entweder float oder None.

    Rückgabe:
    - `float`, wenn konvertierbar
    - `None`, wenn leer/NaN oder nicht konvertierbar
    """

    try:
        # pandas markiert fehlende Werte meist als NaN
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def main():
    # App erzeugen (ohne Server zu starten), damit wir DB-Config + instance_path haben.
    app = create_app()

    # In Flask braucht DB-Zugriff immer einen App-Context.
    # (Sonst weiß SQLAlchemy nicht, zu welcher App/Config es gehört.)
    with app.app_context():
        # Falls DB/Tabellen noch nicht existieren, werden sie angelegt.
        db.create_all()

        # Excel-Pfad bestimmen
        xlsx_path = DEFAULT_XLSX

        # Frühzeitig und verständlich abbrechen, falls Datei fehlt.
        if not os.path.exists(xlsx_path):
            raise FileNotFoundError(
                f"Excel nicht gefunden: {xlsx_path}\n"
                "Lege die Datei in ../data/ oder setze BLS_XLSX_PATH in deiner .env"
            )

        print(f"📥 Lese Excel ein: {xlsx_path}")

        # Excel einlesen (pandas erkennt Tabellenblatt & Datentypen automatisch).
        # Falls nötig könnte man später: sheet_name=..., usecols=..., dtype=...
        df = pd.read_excel(xlsx_path)

        # --- Spalten-Mapping -----------------------------------------------------
        # Diese Namen entsprechen den Spalten in der BLS-Datei.
        # Wichtig: Wenn BLS-Versionen sich ändern, können die Namen abweichen.
        NAME_COL = "Lebensmittelbezeichnung"
        # ENERCJ_COL = "ENERCJ Energie (Kilojoule) [kJ/100g]"  # derzeit nicht importiert
        ENERCC_COL = "ENERCC Energie (Kilokalorien) [kcal/100g]"
        WATER_COL = "WATER Wasser [g/100g]"
        PROT_COL = "PROT625 Protein (Nx6,25) [g/100g]"
        FAT_COL = "FAT Fett [g/100g]"
        CHO_COL = "CHO Kohlenhydrate, verfügbar [g/100g]"

        # Sicherheitscheck: existieren die Pflichtspalten?
        # Wenn nicht, ist die BLS-Datei vermutlich eine andere Version oder anders formatiert.
        required = [NAME_COL]
        for col in required:
            if col not in df.columns:
                raise KeyError(f"Spalte fehlt in Excel: {col}")

        # --- Importstrategie ------------------------------------------------------
        # Für PoC/Entwicklung machen wir einen "Reset":
        # - alle vorhandenen Foods löschen
        # - dann alles erneut importieren
        # Vorteil: einfach und reproduzierbar.
        # Nachteil: keine inkrementellen Updates.
        print("🧹 Lösche alte Datensätze (POC-Reset)...")
        Food.query.delete()
        db.session.commit()

        print(f"🚚 Importiere {len(df)} Zeilen...")

        # Objekte sammeln und in einem Rutsch speichern (Performance)
        objects: list[Food] = []

        for _, row in df.iterrows():
            # Lebensmittelname ist Pflichtfeld.
            name = str(row.get(NAME_COL, "")).strip()
            if not name:
                continue

            # Food-ORM-Objekt bauen.
            # safe_float sorgt dafür, dass leere/ungültige Zellen als None landen.
            obj = Food(
                name_de=name,
                # energy_kj=safe_float(row.get(ENERCJ_COL)),
                energy_kcal=safe_float(row.get(ENERCC_COL)),
                water_g=safe_float(row.get(WATER_COL)),
                protein_g=safe_float(row.get(PROT_COL)),
                fat_g=safe_float(row.get(FAT_COL)),
                carbs_g=safe_float(row.get(CHO_COL)),
            )
            objects.append(obj)

        # bulk_save_objects ist deutlich schneller als pro Zeile committen.
        # Danach einmal committen, damit die Daten in der DB landen.
        db.session.bulk_save_objects(objects)
        db.session.commit()

        print(f"✅ Fertig! Importiert: {len(objects)} Einträge")
        print("ℹ️ Du kannst jetzt den Server starten und /foods durchsuchen.")


if __name__ == "__main__":
    # Direktaufruf über CLI
    main()
