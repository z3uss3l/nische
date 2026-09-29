# Nische v5 — Market Intelligence Architecture

## Ziel

Nische wird von einem Keyword-Scorer zu einer evidenzbasierten Opportunity-Intelligence-Plattform.
Das System verbindet **Marktnachfrage, Zeitreihen, Ereignisse, Regulierung, Funding,
Beschaffung, Produkte/Bauteile/Materialien und Lieferketten**, ohne Korrelation als
Kausalität oder angekündigte Regeln als geltendes Recht darzustellen.

## 1. Gemeinsamer Kern

Alle Quellen werden auf fünf Objekttypen normalisiert:

1. `TemporalSignal` — numerischer Messwert mit Zeitpunkt, Region, Einheit und Provenienz.
2. `TemporalEvent` — diskretes Ereignis mit Bekanntgabe-, Start-, End- und Wirksamkeitsdatum.
3. `Relationship` — gerichtete Beziehung mit Lag, Stärke, Stabilität und Evidenzgrad.
4. `ProductNode/ProductEdge` — Produkt-, Komponenten-, Material-, Stoff- und Substitutionsgraph.
5. `FundingOpportunity` — Förderchance mit Eligibility, Budget, Frist und Konditionen.

Daraus werden ausschließlich nachvollziehbare `MarketImpact`-Objekte und getrennte
Opportunity-Scores erzeugt.

## 2. Signaluniversum

### Nachfrage und Angebot
Google Trends/Related/Autocomplete, DataForSEO, Reddit, YouTube, Social, Bücher,
Keepa, Shopping, Local Services, News, öffentliche Beschaffung.

### Tages- und Echtzeitsignale
Wetter und Prognosen; Strom/Gas/Öl/CO2; Rohstoffe; FX; Zinsen; Aktien-/Volatilitätsindizes;
Fracht/Lieferzeiten; Agrarpreise; Luftqualität/Pollen; Wasser/Pegel; Mobilität; Kalender,
Ferien, Feiertage, Saison und Großveranstaltungen/Sport.

Jeder Messwert wird historisiert. Abgeleitet werden u. a. 1/7/30-Tage-Änderung,
saisonaler Vergleich, Perzentil, Anomalie, Volatilität und Momentum.

### Deutschland/EU Struktur
Destatis GENESIS, Eurostat, BA, Bundesbank/ECB, GovData und weitere amtliche Quellen.
Strukturelle Kontextdaten dürfen keyword-spezifische Nachfrage nicht künstlich erhöhen.

## 3. Regulatory Foresight

Quellen: EUR-Lex/CELLAR/RSS, EU-Kommission, Bundestag/DIP/RSS, Bundesrat,
Bundesministerien und Behörden sowie DIN, CEN/CENELEC, ETSI und fachlich zuständige
legitimierte Gremien.

Reifegrade werden getrennt gespeichert:
`binding -> adopted_not_effective -> legislative_proposal -> consultation ->
official_roadmap -> standard_draft -> committee_work_item ->
authority_announcement -> industry_position`.

Wichtige Zeitpunkte:
Bekanntgabe, Konsultationsende, Abstimmung, Veröffentlichung, Inkrafttreten,
Übergangsfrist, verpflichtende Anwendung.

Eine Impact-Hypothese muss die Kette offenlegen:
`Änderung -> Pflicht/Entlastung -> betroffene Akteure -> Prozess/Produkt ->
Bedarf/Mangel/Substitution -> Marktfolge`.

## 4. Funding Engine

Quellenklassen:
EU Funding & Tenders, Cascade Funding, nationale/regionale EU-Portale,
Stiftungen, Corporate Foundations, Preise, Förderbanken und relevante Ausschreibungen.

Nicht vermischen:
Programmvolumen != Call-Budget != noch verfügbares Budget != bereits bewilligtes Geld.

Funding Cards enthalten Eligibility, Förderquote, Eigenanteil, Konsortium, Frist,
Geografie, Budget, Aufwand, Topic-Fit, Expertise-Fit und Interessen-Fit.

Queues:
- NOW: hohe Passung, zeitkritisch, mit vorhandenen Ressourcen realistisch.
- BUILD: hohe Passung, aber Projekt/Partner müssen aufgebaut werden.
- WATCH: kommende Calls oder noch unreife Chancen.

Nach expliziter Nutzerentscheidung darf ein Proposal Workspace die offiziellen
Call-Templates vorbefüllen; erfundene Angaben bleiben verboten und fehlende Nachweise
werden als offen markiert.

## 5. Product & Supply-chain Intelligence

Resolver:
`Produkt/GTIN/EAN/MPN -> Produktklassifikation -> Komponenten -> Materialien/Stoffe ->
CN/TARIC -> Handelsströme -> Herkunft -> Rohstoffpreise -> Regulierung -> Substitute`.

Quellen können SCIP, TARIC/CN/EZT, Eurostat/COMEXT, UN Comtrade, PRODCOM,
EPREL sowie legitime Hersteller-/Ersatzteil-/BOM-Kataloge umfassen.

SCIP ist ein wichtiger, aber partieller Graph: SVHC-relevante Artikel und komplexe
Objekte sind keine vollständige universelle Stückliste. Herkunft und Abdeckung jeder
Kante müssen deshalb gespeichert werden.

## 6. Temporal Relationship Engine

Keine fest codierten Aussagen wie `DAX runter -> Gold hoch`.

Kandidatenbeziehungen werden aus Historie getestet:
- Cross-correlation über mehrere Lags
- saisonale Baselines
- robuste Regression
- Change-point/Anomaly Detection
- Granger-Tests als Vorhersagehinweis, nicht als Kausalitätsbeweis
- Stabilität über verschiedene Zeitfenster und Regionen
- später kausale Verfahren, wenn Identifikationsannahmen vertretbar sind

Point-in-time-Datenstände werden bevorzugt, damit Backtests keinen Look-ahead Bias haben.

## 7. Collision Engine

Mehrere unabhängige Treiber können eine Opportunity verstärken oder abschwächen:

`Hitze + Wochenende + Ferien + Event + Search Spike + Low Inventory`

oder

`Regulation + Deadline + Funding + Procurement + Few Suppliers`.

Die Engine bewertet Unabhängigkeit, Richtung, zeitliche Überlappung, Region,
historische Trefferquote und Evidenzqualität.

## 8. Scores

### Base Opportunity 0..10
Strukturelle Nachfrage, Pain, Angebotslücke, Wettbewerb, langfristiger Trend.

### Dynamic Impact -5..+5
Aktuelle Abweichungen: Wetter, Preise, Ereignisse, Lieferengpässe, Suchspikes usw.

### Forward Impact -5..+5
Bereits bekannte zukünftige Treiber: Wetterprognose, regulatorische Deadline,
Förderöffnung, Veranstaltung, Saison, Ausschreibung.

Der UI-Gesamteindruck darf diese drei Werte anzeigen, aber nicht zu einer scheinpräzisen
Zahl verschmelzen. Jede Änderung muss auf konkrete Driver/Evidence-IDs zurückführbar sein.

## 9. Datenhaltung

Bestehende `analysis`- und `trend_records`-Tabellen bleiben für Kompatibilität.
Neu folgen:
- temporal_signals
- temporal_events
- relationships
- product_nodes / product_edges
- funding_opportunities
- market_impacts
- opportunity_snapshots

Für SQLite werden Indizes auf timestamp/domain/region/subject benötigt; PostgreSQL ist
für größere Historien der bevorzugte Produktionspfad.

## 10. UI

### Marktlage heute
Tageswerte und Anomalien nach Wetter, Energie, Makro, Rohstoffen, Nachfrage,
Regulierung, Funding, Beschaffung und Events.

### Historie
24h / 7T / 30T / 1J / 5J plus saisonaler Vergleich.

### Opportunity Radar
Base, Dynamic und Forward getrennt; positive und negative Treiber sichtbar.

### Wirkungsketten
Interaktive Evidence Chain, z. B.
`Kälte -> Heizbedarf -> Brennholz -> Holzpreis -> Inputkosten -> Substitute`.
Jede Kante zeigt Evidenzgrad, Lag und Stabilität.

### Regulatory Calendar
Bekanntgabe bis verpflichtende Anwendung inklusive Opportunity Window.

### Funding Inbox
NOW / BUILD / WATCH und Proposal Workspace.

### Product Graph
Produkt -> Teil -> Material -> CN/TARIC -> Herkunft -> Risiko -> Substitute.

## 11. Implementierungsreihenfolge

Phase A — Datenmodell + Historisierung + Dashboard-Tageswerte.
Phase B — Wetter, Kalender, SMARD, Bundesbank/ECB, Destatis/Eurostat.
Phase C — Regulatory Foresight und Kalender.
Phase D — Funding Engine und Proposal Workspace.
Phase E — Product Resolver/SCIP/TARIC/Handelsdaten.
Phase F — Relationship-, Lag- und Collision Engine.
Phase G — automatische Opportunity-Erkennung und Backtesting.

Jede Phase bleibt auch ohne spätere Phasen produktiv nutzbar.
