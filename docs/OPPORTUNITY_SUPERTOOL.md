# Nische v5 — Opportunity Intelligence Supertool

## Leitidee

Nische behandelt eine Marktlücke nicht als `Trend - Trefferzahl`, sondern als überprüfbare Hypothese.
Jeder Kandidat durchläuft Discovery → Probe Ladder → Matching → Gap Classification → Validation →
Historisierung → Re-Probing. Fakten, Schätzungen, statistische Beziehungen und Hypothesen bleiben getrennt.

## Übernommene Muster aus der Markt-/Open-Source-Sichtung

- Search analytics: no-hit, no-click und conversion events als explizite Nachfragebeobachtungen.
- Recursive niche discovery: vielversprechende Begriffe erzeugen neue Seeds.
- Marketplace MCP: Netzwerkadapter getrennt von reinen/testbaren Analysefunktionen.
- Price intelligence: Identifier-first Product Matching, danach fuzzy/semantic matching; Preis/Stock als Zeitreihe.
- Retail analytics: ABC/XYZ, GMROI, Turnover, Sell-through, Preisindex und Elastizität.
- Basket intelligence: Support, Confidence, Lift, Conviction; FP-Growth/Apriori für Complements.
- Temporal intelligence: Snapshot-Historisierung, point-in-time Features, Outlier, Velocity, Acceleration.
- Validation: KILL / PIVOT / CONTINUE / WATCH und nächster informationsreicher Test.

## Kernobjekte

### ResearchLens
Fachlicher Vertrag für POD, E-Book, Marketplace, Finance oder eigene Verticals:
Datenquellen, Discovery-Modi, Dimensionen, Probe-Provider, Validation Gates und Dashboard-Panels.

### Candidate
Eine zu prüfende Opportunity-Hypothese. Sie enthält noch keine behauptete Marktlücke.

### ProbePlan / ProbeStep
Reproduzierbare Prüfkaskade. Standard:
Identifier → exact → synonyms → semantic → category → substitutes → andere Region/Sprache.

### ProbeResult
Unveränderte Beobachtung eines Providers inkl. Status, Trefferzahl, relevante Treffer,
Verfügbarkeit, Preise, Relevanz und Fehlerzustand.

### GapEvidence
Klassifiziert ausschließlich aus validen ProbeResults:
confirmed_zero, near_zero, semantic_gap, availability_gap, geographic_gap, price_gap,
quality_gap, format_gap, variant_gap, none, data_unknown.

### TemporalSignal / TemporalEvent
Historisierte Messwerte und Ereignisse. Jeder Snapshot ist point-in-time auswertbar.

## Harte Regeln

1. Timeout, Block oder Parserfehler sind niemals ein Nulltreffer.
2. Ein Treffer ist nicht automatisch relevant; Product Matching und Query-Relevanz sind getrennt.
3. Ein `confirmed_zero` verlangt standardmäßig mehrere unabhängige Provider und Query-Broadening.
4. Marketplace-Supply ist keine Demand-Messung. Nachfrage braucht eigene Evidenz.
5. LLMs dürfen Seeds, Synonyme und Hypothesen erzeugen, aber keine Messwerte erfinden.
6. Provider-Rohdaten bleiben auditierbar.
7. Offizielle APIs werden bevorzugt; Scraping ist Adapter/Fallback und muss ToS/robots/rate limits beachten.
8. Scores ranken Kandidaten; sie sind keine Absatz- oder Erfolgswahrscheinlichkeit.
9. Kausalität wird nicht aus Korrelation abgeleitet.
10. Entscheidungen/automatische Preisänderungen bleiben außerhalb der Intelligence-Schicht, sofern nicht explizit freigegeben.

## Verarbeitung

```
Sources / Search Logs / Marketplaces / Trends / Events
                     |
                     v
               Normalization
                     |
       +-------------+-------------+
       |                           |
 Demand Signals                Supply Probes
       |                           |
       v                           v
 Candidate Generator ------> Query Ladder
       |                           |
       |                    Product Matching
       |                           |
       +-------------> Gap Classifier
                             |
                             v
                     Evidence Matrix
                             |
              +--------------+--------------+
              |                             |
        Temporal Engine              Product/Market Graph
              |                             |
              +--------------+--------------+
                             v
                 Opportunity Verification
                             |
              KILL / PIVOT / WATCH / CONTINUE
                             |
                             v
                 Adaptive Probe Scheduler
```

## Product Matching

Priorität:
1. GTIN/EAN/UPC/ISBN/ASIN/MPN
2. Brand + model + variant
3. normalized attributes/unit/pack size
4. lexical/fuzzy similarity
5. embedding/semantic similarity
6. optional image/vision match
7. human-review band for ambiguous matches

Preise werden erst nach Matching vergleichbar gemacht: currency, VAT, shipping, pack/unit,
condition, subscription/promo und landed cost werden separat gespeichert und normalisiert.

## Negative Nachfrage-/Supply-Evidenz

Stärkste Form: echte interne Suchlogs mit wiederholtem no-hit/no-click und anschließender
Conversion anderswo bzw. Reformulierung. Externe Marketplace-Nulltreffer sind Supply-Gap-Evidenz,
keine direkte Nachfrage. Stark wird die Opportunity erst durch unabhängige Nachfragequellen.

## Discovery

Seeds entstehen aus:
- Trends/Autocomplete/Search logs
- Pain/Questions/Reviews
- Events/News/Regulation/Funding
- Produkte, Accessories, Consumables, Replacements, Services
- Basket Complements
- Substitute/Compatibility gaps
- Cross-country lead/lag
- Cross-format gaps (Video vorhanden, Buch/Kurs/Tool fehlt)
- Outliers relativ zur eigenen Baseline

## Retail/Preis-Analytik

Pro Produkt/Cluster getrennt berechenbar:
Demand volume/velocity/acceleration, offer/seller depth, stock, price distribution/index,
spread, elasticity, promotion lift, cannibalization, GMROI, turnover, sell-through,
ABC/XYZ, concentration/Gini/HHI, review barrier, quality gap, basket support/confidence/lift,
seasonality, volatility und anomaly.

## Market State Machine

Long Tail → Emerging → Hidden Gem → Star → Overheated → Saturated → Falling → Overstock.

Transitions sind wichtiger als statische Labels und werden historisiert. Antizyklische Fenster
entstehen z.B. nach Demand Pull-Forward, Preisübertreibung, Supply Catch-up oder Overstock.

## Background Worker

Priorität basiert transparent auf Nachfrage, Beschleunigung, Anomalie, Gap-Confidence,
externem Trigger, Informationswert und Probe-Kosten. Hohe Priorität wird häufiger geprüft;
ruhige/saturierte Kandidaten erhalten Backoff. Ergebnisse werden nie überschrieben, sondern
als Snapshot-Historie gespeichert.

## Dashboard

Ein globaler Filterzustand steuert Situation, Kalender, Timeline, Trends, Heatmap, Evidence,
Opportunity Funnel, Gap Matrix, Price Landscape, Product Graph und Probe History.
Research Lenses speichern nicht nur Filter, sondern Methodik. Eigene Views können daraus
abgeleitet und gespeichert werden.

## Interfaces

Domain/Application Logic ist einmalig implementiert. Streamlit, HTTP API, Background Worker
und MCP rufen dieselben Use Cases auf. Provider-spezifische Netzwerklogik bleibt in Adaptern.

## Nächste Adapter

Priorität:
1. eigene/verbundene Search Logs (Typesense/OpenSearch/Shop export)
2. eBay Browse API
3. Amazon Creators API sofern Zugang vorhanden
4. bestehende Keepa/DataForSEO/Google-Autocomplete Quellen
5. Preisvergleich/Shopping-Provider mit zulässigem API/Feed-Zugang
6. Review/Pain Mining
7. Basket/Order Import für eigenes Warenangebot
