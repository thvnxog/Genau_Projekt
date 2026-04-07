# DGE Gramm-Regeln (TODO)

Status: offen  
Letzte Aktualisierung: 2026-03-29

## Ziel

- Umstellung von reinen Haeufigkeitsregeln auf Mengenregeln in Gramm.
- Auch Fluessigkeiten werden im Projekt bereits als Gramm behandelt (ml 1:1).

## Bedeutung von P und S

- P steht fuer Primarstufe (7 bis unter 10 Jahre).
- S steht fuer Sekundarstufe (10 bis unter 19 Jahre).

## TODOs fuer naechsten Termin

- [ ] Werte aus offizieller Quelle final gegenpruefen (insb. P/S-Bereiche).
- [ ] Entscheiden, ob P- oder S-Werte als Sollwert fuer die Regeln genutzt werden.
- [ ] Regelstrategie festlegen: `min`, `max`, oder Bereich (`min` + `max`) pro Kategorie.
- [ ] Regeln in `backend/rules/dge_lunch_rules.json` als `*_grams` ergaenzen.
- [ ] Optional: 4-Tage-Variante mit skalierten Schwellen dokumentieren.
- [ ] Schaetzverfahren (nur Gesamtgewicht pro Gericht) fachlich freigeben.

## Arbeitsvorschlag: Schaetzung bei nur Gesamtgewicht pro Gericht

Ausgangslage:

- Nutzer geben teilweise nur ein Gesamtgewicht fuer das ganze Gericht an (z. B. 500 g).
- Einzelmengen je Komponente (Gemuese, Staerke, Protein, Fett) fehlen.

Vorschlag fuer die Reihenfolge der Datenqualitaet:

1. Rezeptbasiert (beste Qualitaet): bekannte Mengen je Komponente.
2. Profilbasiert (mittlere Qualitaet): feste Verteilprofile je Gerichtstyp.
3. Keyword-Fallback (niedrige Qualitaet): grobe Verteilung nur aus Gerichtsname/Tags.

Rechenprinzip:

- geschaetzte_gramm_je_gruppe = gesamtgewicht_gericht \* anteil_der_gruppe
- Beispiel: 500 g Gesamtgewicht, 40 % Gemuese -> 200 g Gemuese.

Wichtige Grenzen:

- Es gibt in der Praxis keine allgemein verbindliche Einzelregel, die aus nur einem Gesamtgewicht exakte DGE-Gruppenmengen erzeugt.
- Die Methode ist eine nachvollziehbare Naeherung, keine exakte Bilanz.
- Ergebnisse muessen im Report als geschaetzt gekennzeichnet werden.

Empfehlung fuer die Umsetzung im Projekt:

- Jedes Ergebnis mit Herkunft markieren: `recipe`, `profile`, `keyword_fallback`.
- Zusaetzlich ein Unsicherheitslevel speichern: `hoch`, `mittel`, `niedrig`.
- Regeln optional zweistufig bewerten:
  - hart bei `recipe`
  - weich/hinweisbasiert bei `profile` und `keyword_fallback`

Offen zur Bestaetigung im naechsten Termin:

- [ ] Ist dieses Schaetzverfahren als Zwischenloesung in Ordnung?
- [ ] Duerfen wir dafuer Standardprofile je Gerichtstyp definieren?
- [ ] Soll bei unsicherer Schaetzung nur gewarnt statt durchgefallen werden?

## Entwurf: Gramm-Sollwerte aus Tabelle (pro 5 Verpflegungstage)

Hinweis: Die Bezeichnungen in Klammern sind Vorschlaege fuer Mapping auf vorhandene Food-Groups/Tags.

### Mischkost

1. Getreide/Kartoffeln taeglich (`grains_potatoes`)

- P: ca. 600 g
- S: ca. 650-800 g
- Davon: mind. 1x Vollkorn (`tag: wholegrain`)
- Davon: max. 1x Kartoffelerzeugnisse (`tag: potato_product`)

2. Gemuese/Salat taeglich (`vegetables`)

- P: ca. 800 g
- S: ca. 900-1200 g
- Davon: mind. 2x Rohkost (`tag: raw_veg`)
- Davon: mind. 1x Huelsenfruechte (`legumes`)
- Huelsenfruechte Menge: P ca. 80 g, S ca. 100-120 g

3. Obst mind. 2x (`fruit`)

- P: ca. 150 g
- S: ca. 150-200 g
- Davon: mind. 1x als Stueckobst (`tag: whole_fruit`)

4. Milch/Milchprodukte mind. 2x (`dairy`)

- P: ca. 200 g
- S: ca. 200-300 g

5. Fleisch/Wurstwaren (`meat`)

- Max. 1x
- P: ca. 60 g
- S: ca. 70-90 g
- Zusatz: mind. 2x mageres Muskelfleisch innerhalb 20 Verpflegungstagen

6. Fisch (`fish`)

- 1x
- P: ca. 45 g
- S: ca. 50-70 g
- Zusatz: mind. 2x fettreicher Fisch innerhalb 20 Verpflegungstagen

7. Rapsoel als Standardfett

- P: ca. 30 g
- S: ca. 30-40 g

8. Getraenke jederzeit verfuegbar

- Nicht als Grammregel modelliert.

### Ovo-lacto-vegetarische Kost

1. Getreide/Kartoffeln taeglich (`grains_potatoes`)

- P: ca. 600 g
- S: ca. 650-800 g
- Davon: mind. 1x Vollkorn (`tag: wholegrain`)
- Davon: max. 1x Kartoffelerzeugnisse (`tag: potato_product`)

2. Gemuese/Salat taeglich (`vegetables`)

- P: ca. 900 g
- S: ca. 1000-1400 g
- Davon: mind. 2x Rohkost (`tag: raw_veg`)
- Davon: mind. 1x Huelsenfruechte (`legumes`)
- Huelsenfruechte Menge: P ca. 140 g, S ca. 150-200 g

3. Obst mind. 2x (`fruit`)

- P: ca. 150 g
- S: ca. 150-200 g
- Davon: mind. 1x als Stueckobst (`tag: whole_fruit`)
- Davon: mind. 1x Nuesse oder Oelsaaten (`tag-vorschlag: nuts_seeds`)
- Nuesse/Oelsaaten Menge: P ca. 25 g, S ca. 25-30 g

4. Milch/Milchprodukte mind. 2x (`dairy`)

- P: ca. 200 g
- S: ca. 200-300 g

5. Fleisch/Fisch-Regel

- Entfaellt bei ovo-lacto-vegetarischem Angebot.

6. Rapsoel als Standardfett

- P: ca. 30 g
- S: ca. 30-40 g

7. Getraenke jederzeit verfuegbar

- Nicht als Grammregel modelliert.

## JSON-Entwurf (nur Beispiel, noch nicht aktiv)

```json
{
  "id": "LUNCH_VEGETABLES_GRAMS_MIN",
  "label": "Gemuese/Salat Mindestmenge in g",
  "diet": "all",
  "target": { "count_by": "food_group_grams", "value": "vegetables" },
  "operator": "min",
  "threshold": 900,
  "notes": "TODO: Schwelle finalisieren (P/S Entscheidung offen)."
}
```

## Offene Modellierungsfragen

- Sollen P-Werte als harte Mindestwerte gelten und S-Bereiche nur als Empfehlung?
- Wie strikt sollen Obergrenzen fuer Kategorien mit Bandbreiten (`max`) umgesetzt werden?
- Brauchen wir separate Rule-Sets fuer 4 Tage und 5 Tage oder skalieren wir dynamisch?

## Getroffene Entscheidung (2026-04-07)

- Bei 4-Tage-Wochen wird fuer `min`-Schwellen der Dreisatz verwendet.
- Formel: `threshold_4T = threshold_5T * (4/5)`.
- `max`-Schwellen bleiben unveraendert (keine Absenkung), da nur ein Tag fehlt.
- `equals` bleibt ebenfalls unveraendert.
