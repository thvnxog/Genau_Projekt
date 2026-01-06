import pandas as pd

# ----------------------------------------------------------
# 1) BLS-Datei einlesen
# ----------------------------------------------------------

# Dateiname wie von dir angegeben
BLS_FILE = "BLS_4_0_Daten_2025_DE.xlsx"

def load_bls():
    """
    Liest die BLS-Exceldatei ein und gibt ein pandas DataFrame zurück.
    """
    print(f"Lade BLS-Datei: {BLS_FILE}")
    df = pd.read_excel(BLS_FILE)

    # Optional: falls debuggen
    # print(df.columns)

    return df


# ----------------------------------------------------------
# 2) Suchfunktion nach Lebensmittel
# ----------------------------------------------------------

def search_food(df: pd.DataFrame, term: str) -> pd.DataFrame:
    """
    Sucht im DataFrame nach einem Begriff in der Spalte 'Lebensmittelbezeichnung'.
    Gibt ein gefiltertes DataFrame zurück.
    """
    term = term.strip().lower()
    if not term:
        return df.iloc[0:0]  # leeres DataFrame

    # Falls die Spalte anders heißt, hier anpassen:
    name_col = "Lebensmittelbezeichnung"

    # tolower + contains für eine "enthält"-Suche (z. B. 'apfel' findet auch 'Apfel, roh')
    mask = df[name_col].astype(str).str.lower().str.contains(term, na=False)
    return df[mask].head(1) # nur das erste Ergebnis zurückgeben


# ----------------------------------------------------------
# 3) Ausgabe der Nährwert-Daten
# ----------------------------------------------------------

def print_results(results: pd.DataFrame):
    """
    Gibt die gefundenen Lebensmittel mit einigen Nährwertspalten in einer
    transponierten (zeilenweisen) Form für bessere Lesbarkeit aus.
    """
    if results.empty:
        print("Keine Treffer gefunden.")
        return

    # 1. Definieren Sie die Spalten und deren neue, kurze Bezeichnungen
    # Die Zuordnung von alter Spalte zu neuem Label
    COLUMNS_MAP = {
        "Lebensmittelbezeichnung": "Lebensmittel",
        "ENERCJ Energie (Kilojoule) [kJ/100g]": "Energie (kJ)",
        "ENERCC Energie (Kilokalorien) [kcal/100g]": "Energie (kcal)",
        "WATER Wasser [g/100g]": "Wasser (g)",
        "PROT625 Protein (Nx6,25) [g/100g]": "Protein (g)",
        "FAT Fett [g/100g]": "Fett (g)",
        "CHO Kohlenhydrate, verfügbar [g/100g]": "Kohlenh. (g)",
    }
    
    # Filtern, welche Spalten wirklich im DataFrame existieren
    existing_cols = [c for c in COLUMNS_MAP.keys() if c in results.columns]

    # 2. DataFrame vorbereiten und umbenennen
    view = results[existing_cols].copy()
    view.rename(columns=COLUMNS_MAP, inplace=True)

    # 3. Numerische Spalten runden
    # Die neue Liste der kurzen Spaltennamen
    short_numeric_cols = [v for k, v in COLUMNS_MAP.items() if k in existing_cols and v != "Lebensmittel"]

    for c in short_numeric_cols:
        view[c] = pd.to_numeric(view[c], errors="coerce").round(2)

    # 4. Transponieren und ausgeben
    # Da nur eine Zeile zurückgegeben wird (.head(1) in search_food),
    # macht das Transponieren die Ausgabe sehr übersichtlich.
    
    # Transponiert das 1xN DataFrame zu einem Nx1 DataFrame
    # (Spalten werden zu Index, die Werte zur einzigen Spalte)
    transposed_view = view.iloc[0].transpose().to_frame("Wert pro 100g")

    # Ausgabe
    print("\n--- Gefundener Eintrag ---")
    print(transposed_view)


# ----------------------------------------------------------
# 4) Hauptprogramm (Interaktive Suche)
# ----------------------------------------------------------

def main():
    df = load_bls()

    while True:
        term = input("\nGib ein Lebensmittel/Gericht ein (oder 'q' zum Beenden): ").strip()
        if term.lower() in ("q", "quit", "exit"):
            print("Beende Programm.")
            break

        results = search_food(df, term)
        print_results(results)


if __name__ == "__main__":
    main()
