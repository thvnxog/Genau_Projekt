"""
import_bls.py

Dieses Skript importiert Daten aus der offiziellen BLS-Exceldatei in unsere SQLite-Datenbank.

Wie wird es benutzt?
- `python backend/import_bls.py`
- Falls die Excel nicht unter `data/` liegt, kann der Pfad per Environment Variable gesetzt werden:
  `export BLS_XLSX_PATH="/pfad/zur/BLS_4_0_Daten_2025_DE.xlsx"`
"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app import create_app
from models import db, Food

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = os.getenv(
    "BLS_XLSX_PATH",
    str(BACKEND_DIR.parent / "data" / "BLS_4_0_Daten_2025_DE.xlsx"),
)


def safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def ensure_foods_code_column() -> None:
    """Stellt sicher, dass die bestehende `foods`-Tabelle die Spalte `code` hat.

    `db.create_all()` erweitert bestehende Tabellen nicht. Für ältere SQLite-DBs
    wird die Spalte deshalb bei Bedarf per `ALTER TABLE` nachgezogen.
    """

    rows = db.session.execute(text("PRAGMA table_info(foods)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if "code" not in existing_columns:
        db.session.execute(text("ALTER TABLE foods ADD COLUMN code VARCHAR(64)"))
        db.session.commit()


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        ensure_foods_code_column()

        xlsx_path = Path(DEFAULT_XLSX).expanduser()
        if not xlsx_path.is_absolute():
            xlsx_path = (BACKEND_DIR / xlsx_path).resolve()

        if not xlsx_path.exists():
            raise FileNotFoundError(
                f"Excel nicht gefunden: {xlsx_path}\nLege die Datei in data/ oder setze BLS_XLSX_PATH in deiner .env"
            )

        print(f"Lese Excel ein: {xlsx_path}")
        df = pd.read_excel(str(xlsx_path))

        # --- Spalten-Mapping -------------------------------------------------
        NAME_COL = "Lebensmittelbezeichnung"
        ENERCC_COL = "ENERCC Energie (Kilokalorien) [kcal/100g]"
        WATER_COL = "WATER Wasser [g/100g]"
        PROT_COL = "PROT625 Protein (Nx6,25) [g/100g]"
        FAT_COL = "FAT Fett [g/100g]"
        CHO_COL = "CHO Kohlenhydrate, verfügbar [g/100g]"

        required = [NAME_COL]
        for col in required:
            if col not in df.columns:
                raise KeyError(f"Spalte fehlt in Excel: {col}")

        # Erwartete Code-Spalte in der Excel-Datei.
        code_col = "BLS Code" if "BLS Code" in df.columns else None

        print("Lösche alte Datensätze...")
        Food.query.delete()
        db.session.commit()

        print(f"Importiere {len(df)} Zeilen...")
        objects: list[Food] = []

        for _, row in df.iterrows():
            name = str(row.get(NAME_COL, "")).strip()
            if not name:
                continue

            obj = Food(
                name_de=name,
                energy_kcal=safe_float(row.get(ENERCC_COL)),
                water_g=safe_float(row.get(WATER_COL)),
                protein_g=safe_float(row.get(PROT_COL)),
                fat_g=safe_float(row.get(FAT_COL)),
                carbs_g=safe_float(row.get(CHO_COL)),
                code=(str(row.get(code_col)).strip() if code_col and not pd.isna(row.get(code_col)) else None),
            )
            objects.append(obj)

        db.session.bulk_save_objects(objects)
        db.session.commit()

        print(f"Fertig! Importiert: {len(objects)} Einträge")


if __name__ == "__main__":
    main()

