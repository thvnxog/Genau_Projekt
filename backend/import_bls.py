"""
import_bls.py
Dieses Skript liest die BLS-Excel ein und speichert die Daten in die DB.

Idee:
- Excel wird einmal importiert (oder bei Bedarf neu)
- danach arbeitet der Server nur noch mit der Datenbank

Wichtig:
- Wir importieren erstmal nur wenige Spalten, damit es übersichtlich bleibt.
"""

import os
import pandas as pd

from app import create_app
from models import db, Food

# Pfad zur Excel (bei uns im Projekt: ../data/...)
DEFAULT_XLSX = os.getenv("BLS_XLSX_PATH", "../data/BLS_4_0_Daten_2025_DE.xlsx")

# Hilfsfunktion: sichere Float-Konvertierung
def safe_float(value):
    """
    Kleine Hilfsfunktion:
    - Excel hat manchmal NaN/Strings/etc.
    - Wir versuchen float, sonst None.
    """
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def main():
    app = create_app()

    # In Flask braucht DB-Zugriff immer einen App-Context
    with app.app_context():
        db.create_all()

        xlsx_path = DEFAULT_XLSX
        if not os.path.exists(xlsx_path):
            raise FileNotFoundError(
                f"Excel nicht gefunden: {xlsx_path}\n"
                "Lege die Datei in ../data/ oder setze BLS_XLSX_PATH in deiner .env"
            )

        print(f"📥 Lese Excel ein: {xlsx_path}")
        df = pd.read_excel(xlsx_path)

        # Diese Spaltennamen hast du bereits genannt / benutzt:
        NAME_COL = "Lebensmittelbezeichnung"
        #ENERCJ_COL = "ENERCJ Energie (Kilojoule) [kJ/100g]"
        ENERCC_COL = "ENERCC Energie (Kilokalorien) [kcal/100g]"
        WATER_COL = "WATER Wasser [g/100g]"
        PROT_COL = "PROT625 Protein (Nx6,25) [g/100g]"
        FAT_COL = "FAT Fett [g/100g]"
        CHO_COL = "CHO Kohlenhydrate, verfügbar [g/100g]"

        # Sicherheitscheck: existieren die Spalten?
        required = [NAME_COL]
        for col in required:
            if col not in df.columns:
                raise KeyError(f"Spalte fehlt in Excel: {col}")

        # Für einen sauberen Import:
        # Ich lösche erstmal alles (POC). Später: Upsert/Delta-Import.
        print("🧹 Lösche alte Datensätze (POC-Reset)...")
        Food.query.delete()
        db.session.commit()

        print(f"🚚 Importiere {len(df)} Zeilen...")

        objects = []
        for _, row in df.iterrows():
            name = str(row.get(NAME_COL, "")).strip()
            if not name:
                continue

            obj = Food(
                name_de=name,
                #energy_kj=safe_float(row.get(ENERCJ_COL)),
                energy_kcal=safe_float(row.get(ENERCC_COL)),
                water_g=safe_float(row.get(WATER_COL)),
                protein_g=safe_float(row.get(PROT_COL)),
                fat_g=safe_float(row.get(FAT_COL)),
                carbs_g=safe_float(row.get(CHO_COL)),
            )
            objects.append(obj)

        # bulk_save_objects ist schneller als einzeln committen
        db.session.bulk_save_objects(objects)
        db.session.commit()

        print(f"✅ Fertig! Importiert: {len(objects)} Einträge")
        print("ℹ️ Du kannst jetzt den Server starten und später Such-Endpoints bauen.")


if __name__ == "__main__":
    main()
