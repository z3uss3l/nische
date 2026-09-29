# Nischen-Explorer v4

Mehrquellen-Analyse für Nischen, Marktchancen und Marktlücken. Der Explorer kombiniert Nachfrage, Pain, Angebot, Wettbewerb, Social-/Plattform-Signale, Commerce-Daten und Web-Evidence.

## Quellen

### Nachfrage / Trends
- Google Trends
- Google Trends Related Queries (Top/Rising)
- Google Trends regional interest
- Google Autocomplete (keyless Long-Tail-Discovery; kein Suchvolumen)
- DataForSEO Keyword Ideas
- GDELT / GNews / TheNewsAPI
- YouTube Data API v3
- X Posts + X Trends by WOEID
- Instagram Hashtags über Meta Graph API
- Pinterest Trends API
- Reddit

### Angebot / Commerce
- OpenLibrary
- Google Books
- Keepa / Amazon
- DataForSEO Google Shopping
- DataForSEO Google Local Finder

### Web-Evidence
- RSS/Atom-Feeds
- frei konfigurierbare URL Requests
- robots.txt-konformer Same-Domain-Crawler

## Architektur

- asyncio/aiohttp für HTTP-I/O
- synchrone SDKs isoliert über `asyncio.to_thread()`
- Pydantic-Kanonisierung
- SQLite WAL / PostgreSQL über SQLAlchemy
- idempotente Persistenz und Historie
- Streamlit + Plotly
- Cache über `st.cache_data`

## Konfiguration

Siehe `.env.example`. Quellen ohne erforderliche Zugangsdaten werden als `disabled` angezeigt und beeinflussen die Messung nicht so, als ob sie einen Nullwert geliefert hätten.

### Wichtige neue Variablen

```text
YOUTUBE_API_KEY=
META_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_USER_ID=
FACEBOOK_PAGE_IDS=
META_GRAPH_VERSION=v25.0
PINTEREST_ACCESS_TOKEN=
PINTEREST_REGION=DE

DATAFORSEO_SHOPPING_LOCATION_CODE=2276
DATAFORSEO_SHOPPING_LANGUAGE_CODE=de
DATAFORSEO_SERVICE_LOCATION_CODE=
DATAFORSEO_MERCHANT_MAX_POLLS=6
DATAFORSEO_MERCHANT_POLL_SECONDS=1.5

FEED_URLS=
URL_REQUESTS=
CRAWL_URLS=
CRAWL_MAX_PAGES=20
CRAWL_MAX_DEPTH=1
CRAWL_USER_AGENT=Nischen-Explorer/4.0 (+respectful crawler)
```

`{keyword}` wird in `FEED_URLS` und `URL_REQUESTS` URL-encodiert eingesetzt.

## Plattformgrenzen

- Facebook bietet keine allgemeine globale Public-Post-Hashtag-Suche über die aktuelle Graph-API-Oberfläche. Deshalb wird im Projekt keine solche Funktion vorgetäuscht. Konfigurierte Facebook-Pages können als begrenzte, nachvollziehbare Proxy-Quelle analysiert werden.
- Instagram Hashtag Discovery setzt einen geeigneten Meta-/Instagram-Zugang und die erforderlichen Berechtigungen voraus.
- Pinterest Trends ist laut aktueller API-Dokumentation in der Verfügbarkeit eingeschränkt.
- X Trends erfordern einen Zugang, der den Trends-Endpunkt tatsächlich freischaltet.
- YouTube API-Aufrufe unterliegen Quoten.
- Google Autocomplete ist ein Discovery-Signal und darf nicht als Search-Volume-Messung interpretiert werden.

## Tests

```bash
pytest -q tests_smoke.py
```

Die Tests decken Score-Grenzen, Deduplizierung, Pydantic-Validierung, SQLite-WAL/Upsert, Commerce-/Social-Signale sowie Google-Trends-Discovery-Signale ab.


## Deutschland-spezifische Marktintelligenz

- **TED Ausschreibungen**: keywordbezogene öffentliche Beschaffungsnachfrage; fließt als eigenes Nachfragesignal in den Score ein.
- **GovData**: Discovery relevanter deutscher Open-Data-Datensätze und Behördenquellen.
- **BA Arbeitsmarkt**: amtlicher Arbeitsmarkt-Kontext. Aggregate werden bewusst nicht als keywordbezogene Nachfrage gewertet.
- **Google Autocomplete**: Long-Tail-/Problem-Discovery, ausdrücklich kein Suchvolumen.

Grundsatz: struktureller Kontext, Discovery-Signale und transaktionale Nachfrage werden getrennt behandelt. Fehlende oder fehlerhafte Quellen werden nicht als Null-Nachfrage interpretiert.
