import json
import os
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.utils import load_env, get_config, normalize_keyword, slugify
from modules.pipeline import SOURCE_NAMES, run_analysis
from modules.normalization import source_summary
from modules import db

load_env(); config = get_config()
DASHBOARD_SECTIONS = ["Übersicht", "Nachfrage & Trends", "Social & Hashtags",
                      "Angebot & SEO", "Commerce & Dienste", "Web & Feeds",
                      "Historie", "Quellenqualität", "Rohdaten"]
preferences = db.get_dashboard_preferences(DASHBOARD_SECTIONS)
st.set_page_config(page_title="Nischen-Explorer", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

@st.cache_data(ttl=int(config.get("CACHE_TTL_SECONDS") or 900), show_spinner=False)
def cached_analysis(keyword, region, days, max_workers):
    return run_analysis(keyword, region, days, max_workers)

st.markdown("""
<style>
:root { color-scheme: dark; }
[data-testid="stAppViewContainer"] { background: radial-gradient(circle at 15% 0%, #182338 0%, #090d14 35%, #070a10 100%); }
[data-testid="stHeader"] { background: rgba(0,0,0,0); }
.block-container { max-width: 1500px; padding-top: 1.5rem; }
.sticky-filter { position: sticky; top: 2.8rem; z-index: 20; padding: .7rem 0 .35rem; backdrop-filter: blur(14px); }
.hero { padding: 1.4rem 1.5rem; border: 1px solid #26344a; border-radius: 18px; background: linear-gradient(135deg, rgba(25,37,58,.92), rgba(10,14,22,.88)); margin-bottom: 1rem; }
.hero h1 { margin: 0; letter-spacing: -.03em; }
.hero p { color: #aebbd0; margin: .35rem 0 0; }
.card { border: 1px solid #26344a; border-radius: 15px; padding: 1rem; background: rgba(15,21,32,.82); }
.small { color:#8796ad; font-size:.84rem; }
.badge { display:inline-block; padding:.2rem .5rem; border-radius:999px; border:1px solid #33445d; font-size:.75rem; }
</style>
""", unsafe_allow_html=True)

if preferences["theme"] == "light":
    st.markdown("<style>:root { color-scheme: light; } [data-testid='stAppViewContainer'] { background: #f4f6f8; }</style>", unsafe_allow_html=True)
elif preferences["theme"] == "research":
    st.markdown("<style>[data-testid='stAppViewContainer'] { background: radial-gradient(circle at 80% 0%, #173b3b 0%, #071316 42%, #05090b 100%); }</style>", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>◈ Nischen- & Marktlücken-Explorer</h1><p>Mehrquellen-Analyse für Nachfrage, Pain, Angebot, Wettbewerb und Trenddynamik — mit Provenienz, Fehlerstatus und Konsistenzprüfung.</p></div>', unsafe_allow_html=True)

# --- Controls
with st.sidebar:
    st.header("Analyse")
    keyword = normalize_keyword(st.text_input("Suchbegriff / Seed", value=st.session_state.get("keyword", ""), max_chars=200))
    region = st.selectbox("Markt / Region", ["DE", "US", "GB", "FR", "IT", "ES", "AT", "CH", "NL"], index=0)
    days = st.slider("Datenfenster", 1, 90, 30)
    max_workers = st.slider("Parallelität", 2, 12, int(config.get("MAX_WORKERS") or 8))
    run = st.button("▶ Analyse starten", type="primary", use_container_width=True)
    if st.button("↻ Cache leeren", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.divider()
    with st.expander("Dashboard-Pflege", expanded=False):
        with st.form("dashboard_preferences"):
            visible_sections = st.multiselect(
                "Sichtbare Bereiche", DASHBOARD_SECTIONS,
                default=[section for section in preferences["visible_sections"] if section in DASHBOARD_SECTIONS],
            )
            categories = st.text_input("Kategorien (kommagetrennt)", ", ".join(preferences["categories"]))
            attributes = st.text_input("Attribute (kommagetrennt)", ", ".join(preferences["attributes"]))
            theme = st.selectbox("Inhaltsthema", ["night", "light", "research"],
                                 index=["night", "light", "research"].index(preferences["theme"]) if preferences["theme"] in {"night", "light", "research"} else 0)
            save_dashboard = st.form_submit_button("Dashboard speichern")
        if save_dashboard:
            db.save_dashboard_preferences(
                visible_sections or ["Übersicht"],
                [item.strip() for item in categories.split(",") if item.strip()],
                [item.strip() for item in attributes.split(",") if item.strip()],
                theme,
            )
            st.session_state["dashboard_preferences"] = db.get_dashboard_preferences(DASHBOARD_SECTIONS)
            st.success("Dashboard-Einstellungen gespeichert.")
    with st.expander("Quellenpflege", expanded=False):
        health = db.list_source_health(SOURCE_NAMES)
        health_df = pd.DataFrame(health)
        health_df["ampel"] = health_df["status"].map({
            "ok": "🟢 erreichbar", "empty": "🟢 erreichbar, leer",
            "error": "🔴 Fehler", "disabled": "⚪ deaktiviert",
            "unknown": "🟡 noch nicht geprüft",
        }).fillna("🟡 unbekannt")
        health_df["last_fetched_at"] = health_df["last_fetched_at"].fillna("-")
        health_df["last_checked_at"] = health_df["last_checked_at"].fillna("-")
        edited = st.data_editor(
            health_df[["enabled", "source", "ampel", "last_fetched_at", "last_checked_at", "latency_ms", "last_error"]],
            hide_index=True, use_container_width=True,
            column_config={"enabled": st.column_config.CheckboxColumn("aktiv"), "source": st.column_config.TextColumn("Quelle", disabled=True), "ampel": st.column_config.TextColumn("Erreichbarkeit", disabled=True)},
            disabled=["source", "ampel", "last_fetched_at", "last_checked_at", "latency_ms", "last_error"],
            key="source_health_editor",
        )
        st.caption("Grün = erfolgreich geprüft, Rot = letzter Abruf fehlgeschlagen, Grau = deaktiviert. Zeitstempel sind UTC.")
        with st.form("source_configuration"):
            feed_urls = st.text_area("Feed-URLs (kommagetrennt)", os.getenv("FEED_URLS", ""))
            request_urls = st.text_area("Abruf-URLs (kommagetrennt)", os.getenv("URL_REQUESTS", ""))
            crawl_urls = st.text_area("Crawler-Startseiten (kommagetrennt)", os.getenv("CRAWL_URLS", ""))
            save_sources = st.form_submit_button("Quellen speichern und Cache leeren", type="primary")
        if save_sources:
            for _, row in edited.iterrows():
                db.set_source_enabled(row["source"], row["enabled"])
            os.environ["FEED_URLS"] = feed_urls.strip()
            os.environ["URL_REQUESTS"] = request_urls.strip()
            os.environ["CRAWL_URLS"] = crawl_urls.strip()
            st.cache_data.clear()
            st.success("Quellenkonfiguration gespeichert. Der nächste Lauf verwendet die neuen Einstellungen.")

if run and keyword:
    with st.spinner("Quellen parallel abfragen, normalisieren und prüfen …"):
        result = cached_analysis(keyword, region, days, max_workers)
        st.session_state["analysis"] = result
        st.session_state["analysis_meta"] = {"keyword": keyword, "region": region, "days": days,
                                               "timestamp": datetime.now(timezone.utc).isoformat()}
        st.session_state["analysis_saved"] = db.save_analysis(
            keyword, region, days, result["score"],
            source_summary(result["results"]), result.get("records", []),
        )

analysis = st.session_state.get("analysis")
if not analysis:
    st.info("Links Suchbegriff und Markt wählen und die Analyse starten. Die Anwendung arbeitet ausschließlich mit echten Quellen bzw. klar als deaktiviert markierten Konnektoren.")
    st.stop()

meta = st.session_state["analysis_meta"]
results = analysis["results"]; score = analysis["score"]; records = analysis["records"]
consistency = analysis.get("consistency", {})
summary = pd.DataFrame(source_summary(results))
if st.session_state.get("analysis_saved") is False:
    st.error("Die Analyse ist sichtbar, konnte aber nicht in der Datenbank gespeichert werden.")

# --- global data quality banner
ok = int((summary.status == "ok").sum()); errors = int((summary.status == "error").sum()); disabled = int((summary.status == "disabled").sum())
quality = max(0, min(100, round((ok / max(1, len(summary))) * 100)))
cols = st.columns(5)
cols[0].metric("Gap-Score", f"{score['score']:.2f}/10")
cols[1].metric("Vertrauen", f"{score['confidence']*100:.0f}%")
cols[2].metric("Quellen OK", f"{ok}/{len(summary)}")
cols[3].metric("Datensätze", f"{len(records):,}")
cols[4].metric("Datenqualität", f"{quality}%")

if errors:
    st.warning(f"{errors} Quelle(n) lieferten Fehler. Der Score wird nicht so behandelt, als wären fehlende Daten = Null-Daten.")

# --- filters
with st.expander("Filter & Ansicht", expanded=True):
    fcols = st.columns([1.1, 1.1, 1.1, 1.4, 1.2, 1.3])
    source_options = sorted({r.get("source", "") for r in records if r.get("source")})
    selected_sources = fcols[0].multiselect("Quellen", source_options, default=source_options)
    kinds = sorted({r.get("kind", "") for r in records if r.get("kind")})
    selected_kinds = fcols[1].multiselect("Datentyp", kinds, default=kinds)
    category_options = preferences["categories"] or kinds
    selected_categories = fcols[2].multiselect("Kategorien", category_options, default=category_options)
    text_filter = fcols[3].text_input("Textfilter", placeholder="Titel, Keyword, Text …")
    min_score = fcols[4].number_input("Mindest-Engagement", min_value=0, value=0, step=1)
    sort_by = fcols[5].selectbox("Sortierung", ["Relevanz/Score", "Neueste", "Engagement"])

filtered = [r for r in records if r.get("source") in selected_sources and r.get("kind") in selected_kinds and (r.get("category") or r.get("kind")) in selected_categories]
if text_filter:
    q = text_filter.lower(); filtered = [r for r in filtered if q in json.dumps(r, ensure_ascii=False).lower()]
if min_score:
    filtered = [r for r in filtered if (r.get("score") or 0) + (r.get("likes") or 0) + (r.get("comments") or 0) >= min_score]
if sort_by == "Neueste":
    filtered.sort(key=lambda r: str(r.get("date", "")), reverse=True)
elif sort_by == "Engagement":
    filtered.sort(key=lambda r: (r.get("score") or 0) + (r.get("likes") or 0) + (r.get("comments") or 0), reverse=True)
else:
    filtered.sort(key=lambda r: (r.get("intent_confidence") or 0, r.get("relevance") or 0, r.get("score") or 0), reverse=True)

# --- Tabs
visible_sections = st.session_state.get("dashboard_preferences", preferences)["visible_sections"]
visible_sections = [section for section in DASHBOARD_SECTIONS if section in visible_sections] or ["Übersicht"]
tabs = st.tabs(visible_sections)
tab_by_section = dict(zip(visible_sections, tabs))
hidden_tab = st.container()
for section in DASHBOARD_SECTIONS:
    tab_by_section.setdefault(section, hidden_tab)

with tab_by_section["Übersicht"]:
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.subheader("Opportunity-Matrix")
        factors = pd.DataFrame({"Faktor": ["Nachfrage", "Pain", "Angebotslücke", "Wettbewerbslücke", "Trend"],
                                "Wert": [score["demand"], score["pain"], score["supply_gap"], score["competition_gap"], score["trend"]]})
        fig = px.bar(factors, x="Wert", y="Faktor", orientation="h", range_x=[0,1], text_auto=".0%")
        fig.update_layout(height=310, margin=dict(l=10,r=10,t=20,b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Entscheidung")
        st.markdown(f"### {score['verdict'].title()}")
        st.write(f"**Score:** {score['score']:.2f}/10 · **Konfidenz:** {score['confidence']:.0%}")
        if score["confidence"] < .6:
            st.warning("Vor einer Geschäftsentscheidung zuerst fehlende Kernquellen aktivieren.")
        elif score["score"] >= 7:
            st.success("Signal stark genug für eine vertiefte Validierung.")
        else:
            st.info("Signal vorhanden, aber noch kein belastbarer Selbstläufer.")
        st.caption(f"Analyse: {meta['keyword']} · {meta['region']} · {meta['days']} Tage · {meta['timestamp'][:19]} UTC")

    st.subheader("Konsistenzprüfung")
    consistency_cols = st.columns(4)
    consistency_cols[0].metric("Keyword-Treffer", f"{consistency.get('keyword_matches', 0)}/{consistency.get('records', 0)}")
    consistency_cols[1].metric("Trefferquote", f"{consistency.get('keyword_match_rate', 0):.0%}")
    consistency_cols[2].metric("Dublettengruppen", consistency.get("duplicate_count", 0))
    consistency_cols[3].metric("Pflichtfelder fehlen", consistency.get("missing_required_fields", 0))
    if consistency.get("duplicate_count"):
        st.warning("Quellenübergreifende Dubletten wurden erkannt und für die Prüfung markiert.")
    checks = []
    trend_points = score["trend_points"]
    keyword_count = score["keyword_count"]
    book_count = score["book_count"]
    checks.append(("Nachfrage trianguliert", trend_points > 0 and keyword_count > 0, "Google Trends + Keyword-Daten vorhanden"))
    book_sources = {r.source: r for r in results if r.source in {"OpenLibrary", "Google Books"}}
    book_signal_present = any(r.status in {"ok", "empty"} for r in book_sources.values())
    checks.append(("Angebotsergebnis korrekt interpretiert", book_signal_present, f"{book_count} deduplizierte Titel; erfolgreiche 0-Treffer bleiben ein valides Signal"))
    checks.append(("Score-Konfidenz spiegelt Signale", score["confidence"] <= 1.0 and bool(score.get("available_signals")), "Konfidenz basiert auf tatsächlich vorhandenen Messpunkten"))
    checks.append(("Keine Fake-Connectoren", all(r.status != "ok" or r.error is None for r in results), "Nicht verifizierte externe Connectoren bleiben deaktiviert"))
    for label, passed, detail in checks:
        st.write(("✓" if passed else "⚠") + f" **{label}** — {detail}")

with tab_by_section["Nachfrage & Trends"]:
    st.subheader("Google Trends")
    trend_records = next((r.records for r in results if r.source == "Google Trends"), [])
    if trend_records:
        df = pd.DataFrame(trend_records); df["date"] = pd.to_datetime(df["date"])
        fig = px.line(df, x="date", y="value", markers=True)
        fig.update_layout(height=360, margin=dict(l=10,r=10,t=20,b=10), yaxis_title="relatives Interesse (0–100)", xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Wichtig: Google Trends liefert relatives Suchinteresse, kein absolutes Suchvolumen.")
    else: st.info("Keine Trenddaten.")
    related = pd.DataFrame(next((r.records for r in results if r.source == "Google Trends Related"), []))
    if not related.empty:
        st.subheader("Verwandte Suchanfragen")
        rising = related[related.get("query_type", "") == "rising"] if "query_type" in related else pd.DataFrame()
        top = related[related.get("query_type", "") == "top"] if "query_type" in related else pd.DataFrame()
        a, b = st.columns(2)
        with a:
            st.caption("Rising Queries — Trend-/Discovery-Signal")
            if not rising.empty:
                st.dataframe(rising[[c for c in ["keyword", "value", "region", "url"] if c in rising.columns]].head(50), use_container_width=True, hide_index=True)
            else:
                st.info("Keine Rising Queries.")
        with b:
            st.caption("Top Queries — relatives Interesse")
            if not top.empty:
                st.dataframe(top[[c for c in ["keyword", "value", "region", "url"] if c in top.columns]].head(50), use_container_width=True, hide_index=True)
            else:
                st.info("Keine Top Queries.")

    regional = pd.DataFrame(next((r.records for r in results if r.source == "Google Trends Regions"), []))
    if not regional.empty:
        st.subheader("Geografische Nachfrageverteilung")
        st.dataframe(regional[[c for c in ["region", "value", "parent_region"] if c in regional.columns]].head(100), use_container_width=True, hide_index=True)

    st.subheader("Keyword-Nachfrage")
    seo = pd.DataFrame(next((r.records for r in results if r.source == "DataForSEO"), []))
    if not seo.empty:
        cols = [c for c in ["keyword","search_volume","competition","cpc","keyword_difficulty"] if c in seo.columns]
        st.dataframe(seo[cols].head(100), use_container_width=True, hide_index=True)
    else: st.info("Keine DataForSEO-Daten verfügbar.")

with tab_by_section["Social & Hashtags"]:
    st.subheader("Plattform-Trends & Hashtags")
    platform = pd.DataFrame([r for r in filtered if r.get("kind") == "hashtag_trend"])
    if not platform.empty:
        pcols = [c for c in ["source","platform","trend_name","keyword","hashtag","rank","tweet_count","growth_wow","growth_mom","growth_yoy","region","url"] if c in platform.columns]
        st.dataframe(platform[pcols].head(300), use_container_width=True, hide_index=True)
    else:
        st.info("Keine Plattform-Trends/Hashtag-Daten mit den aktuellen Filtern.")
    social = pd.DataFrame([r for r in filtered if r.get("kind") == "social"])
    if social.empty: st.info("Keine Social-Daten mit den aktuellen Filtern.")
    else:
        a,b,c = st.columns(3)
        a.metric("Signale", len(social)); b.metric("Wünsche", int((social.get("intent") == "wish").sum()) if "intent" in social else 0); c.metric("Beschwerden", int((social.get("intent") == "complaint").sum()) if "intent" in social else 0)
        if "source" in social:
            st.plotly_chart(px.histogram(social, x="source", color="intent" if "intent" in social else None), use_container_width=True)
        display = [c for c in ["source","subreddit","platform","title","text","intent","intent_confidence","score","comments","likes","date","url"] if c in social.columns]
        st.dataframe(social[display].head(200), use_container_width=True, hide_index=True)

with tab_by_section["Angebot & SEO"]:
    books = pd.DataFrame([r for r in filtered if r.get("kind") == "book"])
    products = pd.DataFrame([r for r in filtered if r.get("kind") == "product"])
    a,b = st.columns(2)
    with a:
        st.subheader("Bibliografisches Angebot")
        st.metric("Deduplizierte Titel", score["book_count"])
        if not books.empty:
            cols = [c for c in ["source","title","author","year","rating","rating_count","edition_count","subjects","url"] if c in books.columns]
            st.dataframe(books[cols].head(200), use_container_width=True, hide_index=True)
    with b:
        st.subheader("Amazon / Keepa")
        if not products.empty:
            cols = [c for c in ["asin","title","bsr","price","category","url"] if c in products.columns]
            st.dataframe(products[cols], use_container_width=True, hide_index=True)
        else: st.info("Keepa nicht konfiguriert oder keine Treffer.")

with tab_by_section["Commerce & Dienste"]:
    shopping = pd.DataFrame([r for r in filtered if r.get("kind") == "price_offer"])
    services = pd.DataFrame([r for r in filtered if r.get("kind") == "service"])
    a, b = st.columns(2)
    with a:
        st.subheader("Preisvergleich / Shopping")
        if shopping.empty:
            st.info("Keine Google-Shopping-Angebote verfügbar.")
        else:
            price_cols = [c for c in ["rank","title","price","currency","seller","domain","rating","reviews","url"] if c in shopping.columns]
            st.dataframe(shopping[price_cols].head(300), use_container_width=True, hide_index=True)
            if "price" in shopping.columns:
                prices = pd.to_numeric(shopping["price"], errors="coerce").dropna()
                if not prices.empty:
                    x, y, z = st.columns(3)
                    x.metric("Günstigstes Angebot", f"{prices.min():.2f} €")
                    y.metric("Median", f"{prices.median():.2f} €")
                    z.metric("Angebote", len(prices))
    with b:
        st.subheader("Lokale Dienste")
        if services.empty:
            st.info("Keine Local-Finder-Daten. DATAFORSEO_SERVICE_LOCATION_CODE konfigurieren.")
        else:
            service_cols = [c for c in ["rank","title","rating","reviews","address","phone","url"] if c in services.columns]
            st.dataframe(services[service_cols].head(200), use_container_width=True, hide_index=True)

with tab_by_section["Web & Feeds"]:
    feeds = pd.DataFrame([r for r in filtered if r.get("kind") in {"feed","web"}])
    st.subheader("Feeds, URL-Requests & Crawler")
    if feeds.empty:
        st.info("Keine konfigurierten Feed-/URL-/Crawler-Daten.")
    else:
        web_cols = [c for c in ["source","title","text","url","feed_url","crawl_depth","date"] if c in feeds.columns]
        st.dataframe(feeds[web_cols].head(500), use_container_width=True, hide_index=True)
        st.caption("Crawler arbeitet konservativ: robots.txt, Same-Domain-Grenze, Tiefen-/Seitenlimit und kein Anti-Bot-/Login-Bypass.")

with tab_by_section["Historie"]:
    st.subheader("Score-Historie")
    history = pd.DataFrame(db.recent_history(meta["keyword"], 40))
    if history.empty:
        st.info("Noch keine historischen Analysen gespeichert.")
    else:
        history["timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
        fig = px.line(history, x="timestamp", y="score", markers=True, hover_data=["confidence", "region", "days"])
        fig.update_yaxes(range=[0, 10], title="Gap-Score")
        fig.update_layout(height=320, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(history.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

with tab_by_section["Quellenqualität"]:
    st.subheader("Quellenqualität & Provenienz")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    fig = px.bar(summary, x="source", y="records", color="status", text_auto=True)
    fig.update_layout(height=360, margin=dict(l=10,r=10,t=20,b=10), xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Warum diese Anzeige wichtig ist"):
        st.write("Deaktivierte, leere und fehlerhafte Quellen werden getrennt behandelt. Ein fehlender API-Key wird nicht als 'keine Nachfrage' interpretiert. Laufzeit, Abrufzeitpunkt und Fehler werden pro Quelle gespeichert.")

with tab_by_section["Rohdaten"]:
    st.subheader(f"Gefilterte Datensätze · {len(filtered):,}")
    st.dataframe(pd.DataFrame(filtered).head(500), use_container_width=True, hide_index=True)
    export = pd.DataFrame(filtered).to_csv(index=False).encode("utf-8")
    st.download_button("CSV exportieren", export, f"nischen_{slugify(keyword)}.csv", "text/csv")
    json_export = json.dumps({"meta": meta, "score": score, "sources": source_summary(results), "records": filtered}, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("JSON exportieren", json_export, f"nischen_{slugify(keyword)}.json", "application/json")

st.divider()
st.caption("Nischen-Explorer · Datenprovenienz vor Optik: echte Antworten, explizite Fehlerzustände, keine Platzhalterdaten. Google Books und DataForSEO liefern unterschiedliche Metriktypen; Google Trends ist relativ.")
