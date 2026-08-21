# Nischen-Explorer v4 – Quellen-/Marktdaten-Erweiterung

## Neu

### Video & Social
- **YouTube Data API v3**: Videosuche + nachgelagerte Statistikabfrage (Views, Likes, Kommentare, Kanal, Tags).
- **X Trends**: offizieller WOEID-Trendendpoint, zusätzlich zur bestehenden X-Postsuche.
- **Instagram Hashtags**: offizieller Meta Graph API Hashtag Search + `recent_media` + `top_media`, sofern ein geeigneter Instagram-/Meta-Zugang konfiguriert ist.
- **Pinterest Trends**: offizieller Trends-Endpunkt mit `growing`, `monthly`, `yearly`, `seasonal`.
- **Facebook Pages**: konfigurierte Page-Feeds als klar gekennzeichnete Hashtag-/Keyword-Quelle. Keine Behauptung einer globalen Facebook-Hashtag-Suche.

### Commerce
- **Google Shopping / DataForSEO Merchant API**: echte Produkt-/Angebotsdaten mit Preis, Händler, Rating und URL.
- Merchant-Aufgaben werden korrekt über `task_post` → `task_get` behandelt; `task_post.result == null` wird nicht als fertiges Ergebnis interpretiert.
- **Keepa** bleibt als Amazon-Marktquelle erhalten.
- **Local Services** über DataForSEO Google Local Finder, sofern ein exakter Standortcode konfiguriert ist.

### Web / Feeds / Crawling
- Konfigurierbare **RSS/Atom-Feeds**.
- Konfigurierbare **URL Requests** mit `{keyword}`-Substitution.
- Konfigurierbarer **Same-Domain-Crawler**.
- robots.txt wird vor automatisiertem Crawling geprüft.
- Begrenzung von Crawl-Tiefe, Seitenanzahl und Domains.
- Kein Login-, CAPTCHA- oder Anti-Bot-Bypass.
- Keine ungeprüfte Umwandlung von HTML in Marktmetriken: Webdaten bleiben als `web`/`feed`-Evidence erhalten.

## Scoring
- YouTube-Reichweite und X/Pinterest-Trends können das Nachfrage-/Trendbild ergänzen.
- Shopping-Händlerdichte ergänzt die Wettbewerbsbewertung.
- Dienste-/Service-Treffer werden als Markt-/Monetarisierungs-Evidence persistiert, aber nicht fälschlich als Nachfragevolumen behandelt.
- Plattformmetriken werden nicht als identisch zu Google-Suchvolumen interpretiert.

## Datenqualität
Jede Quelle bleibt separat sichtbar als:

- `ok`
- `empty`
- `disabled`
- `error`

Ein fehlender Zugang ist damit nicht gleichbedeutend mit einem Markt ohne Nachfrage.


## v4.1 — Google Trends Discovery Deep-Merge

Cherry-picked from the additional legacy source package without replacing the current v4 architecture.

- Google Trends Related Queries: Rising + Top Queries
- Google Trends regional interest
- Rising Queries contribute to trend evidence, never to absolute search volume
- Added dedicated provenance/status entries
- Added UI tables for related queries and regional interest
- Added `pytrends` as an explicit dependency because the existing Trends adapter already requires it
- Legacy synchronous fetchers, Redis/Celery, placeholder connectors and dummy implementations were deliberately not merged
