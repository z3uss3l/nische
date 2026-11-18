from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar

import pandas as pd
import plotly.express as px
import streamlit as st

from modules import db
from modules.dashboard_v5 import BUILTIN_VIEWS, DEFAULT_PANELS, derive_calendar_context, filter_records
from modules.intelligence_store import delete_view, init_v5, list_events, list_saved_views, list_signals, save_view

st.set_page_config(page_title="Nische v5 · Market Intelligence", page_icon="◈", layout="wide")
init_v5()

EVIDENCE = ["observed", "official", "derived", "statistical", "plausible", "speculative"]
ALL_PANELS = ["Situation", "Kalender", "Timeline", "Trends", "Heatmap", "Evidenz"]
VIEW_MODES = ["Situation", "Kalender", "Timeline", "Trends", "Heatmap", "Evidenz"]

st.title("Market Intelligence · v5")
st.caption("Ein Filterzustand · mehrere Perspektiven · Fakten, Statistik und Hypothesen bleiben getrennt.")

signals = list_signals()
events = list_events()
saved = list_saved_views()
presets = {**BUILTIN_VIEWS, **saved}

if "v5_cfg" not in st.session_state:
    st.session_state.v5_cfg = dict(BUILTIN_VIEWS["Allgemeine Marktlage"])
if "v5_preset" not in st.session_state:
    st.session_state.v5_preset = "Allgemeine Marktlage"

def load_preset(name):
    st.session_state.v5_cfg = dict(presets.get(name, BUILTIN_VIEWS["Allgemeine Marktlage"]))
    st.session_state.v5_preset = name

with st.sidebar:
    st.header("Ansicht")
    preset_name = st.selectbox("Gespeicherte / spezielle View", list(presets), index=list(presets).index(st.session_state.v5_preset) if st.session_state.v5_preset in presets else 0)
    if st.button("View laden", use_container_width=True):
        load_preset(preset_name); st.rerun()
    if st.button("Filter zurücksetzen", use_container_width=True):
        load_preset("Allgemeine Marktlage"); st.rerun()

    cfg = st.session_state.v5_cfg
    all_regions = sorted({str(x.get("region")) for x in signals + events if x.get("region")})
    all_domains = sorted({str(x.get("domain")) for x in signals + events if x.get("domain")})
    query = st.text_input("Thema / Produkt / Stichworte", value=cfg.get("query", ""))
    regions = st.multiselect("Region", all_regions, default=[x for x in cfg.get("regions", []) if x in all_regions])
    domains = st.multiselect("Kategorien", all_domains, default=[x for x in cfg.get("domains", []) if x in all_domains])
    evidence = st.multiselect("Evidenz", EVIDENCE, default=[x for x in cfg.get("evidence", []) if x in EVIDENCE])
    panels = st.multiselect("Panels", ALL_PANELS, default=[x for x in cfg.get("panels", DEFAULT_PANELS) if x in ALL_PANELS])
    today = date.today()
    start, end = st.date_input("Zeitraum", value=(today - timedelta(days=90), today + timedelta(days=365)))
    st.session_state.v5_cfg = {"query": query, "regions": regions, "domains": domains, "evidence": evidence, "panels": panels}

    st.divider()
    new_name = st.text_input("Aktuelle View speichern als")
    if st.button("View speichern", use_container_width=True, disabled=not new_name.strip()):
        save_view(new_name, st.session_state.v5_cfg)
        st.session_state.v5_preset = new_name.strip()
        st.success("Gespeichert."); st.rerun()
    if preset_name in saved and st.button("Gewählte eigene View löschen", use_container_width=True):
        delete_view(preset_name); load_preset("Allgemeine Marktlage"); st.rerun()

# Calendar-derived context is generated only inside the selected time window.
calendar_events = []
span = min((end - start).days, 1095)
for i in range(max(0, span) + 1):
    calendar_events.extend(derive_calendar_context(start + timedelta(days=i)))

fs = filter_records(signals, query=query, regions=regions, domains=domains, evidence=evidence, start=start, end=end)
fe = filter_records(events + calendar_events, query=query, regions=regions, domains=domains, evidence=evidence, start=start, end=end)

# Legacy records are exposed as evidence, not silently reclassified as temporal signals.
engine = db.get_db_engine()
try:
    legacy = pd.read_sql("SELECT source, kind, title, url, date, score, last_seen FROM trend_records ORDER BY last_seen DESC LIMIT 5000", engine)
except Exception:
    legacy = pd.DataFrame()
if query and not legacy.empty:
    qterms = [x.lower() for x in query.split() if x]
    mask = legacy.astype(str).apply(lambda row: any(t in " ".join(row).lower() for t in qterms), axis=1)
    legacy = legacy[mask]

mode = st.segmented_control("Perspektive", VIEW_MODES, default="Situation", selection_mode="single")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Signale", len(fs))
c2.metric("Ereignisse", len(fe))
c3.metric("Quellen", len({x.get("source") for x in fs + fe if x.get("source")}))
c4.metric("Legacy-Evidenz", len(legacy))

if not fs and not fe:
    st.warning("Für diesen Filter liegen noch keine v5-Zeitreihen/Ereignisse vor. Es werden keine Ersatz- oder Demo-Daten erzeugt.")

def event_frame(rows):
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    for c in ["known_since", "starts_at", "ends_at", "effective_at"]:
        if c in df: df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def signal_frame(rows):
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "timestamp" in df: df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df

edf, sdf = event_frame(fe), signal_frame(fs)

if mode == "Situation":
    st.subheader("Aktuelle Situation im gewählten Kontext")
    left, right = st.columns([1.2, 1])
    with left:
        if not sdf.empty:
            latest = sdf.sort_values("timestamp").groupby(["domain", "metric", "region"], as_index=False).tail(1)
            show = [c for c in ["domain", "metric", "value", "unit", "region", "timestamp", "source", "evidence", "confidence"] if c in latest]
            st.dataframe(latest[show].sort_values(["domain", "metric"]), use_container_width=True, hide_index=True)
        else:
            st.info("Noch keine aktuellen v5-Messwerte für diesen Filter.")
    with right:
        if not edf.empty:
            now = pd.Timestamp.now(tz="UTC").tz_localize(None)
            tmp = edf.copy()
            if "starts_at" in tmp:
                tmp["distance"] = (tmp["starts_at"] - now).abs()
                tmp = tmp.sort_values("distance")
            show = [c for c in ["starts_at", "domain", "event_type", "title", "region", "evidence", "source"] if c in tmp]
            st.dataframe(tmp[show].head(30), use_container_width=True, hide_index=True)
        else:
            st.info("Keine Ereignisse.")

elif mode == "Kalender":
    st.subheader("Kalender")
    month = st.date_input("Monat", value=today.replace(day=1), key="v5_month").replace(day=1)
    _, days_in_month = calendar.monthrange(month.year, month.month)
    if not edf.empty:
        cal = edf.copy()
        cal["day"] = cal["starts_at"].dt.date
        cal = cal[(cal["day"] >= month) & (cal["day"] <= month.replace(day=days_in_month))]
    else: cal = pd.DataFrame()
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month)
    headers = st.columns(7)
    for col, label in zip(headers, ["Mo","Di","Mi","Do","Fr","Sa","So"]): col.markdown(f"**{label}**")
    for week in weeks:
        cols = st.columns(7)
        for col, d in zip(cols, week):
            with col:
                if d.month != month.month:
                    st.caption(str(d.day))
                    continue
                st.markdown(f"**{d.day}**")
                if not cal.empty:
                    items = cal[cal["day"] == d]
                    for _, r in items.head(5).iterrows():
                        st.caption(f"{r.get('domain','')} · {r.get('title','')}")
                    if len(items) > 5: st.caption(f"+{len(items)-5} weitere")

elif mode == "Timeline":
    st.subheader("Timeline")
    if edf.empty:
        st.info("Keine Ereignisse im Filter.")
    else:
        t = edf.dropna(subset=["starts_at"]).copy()
        t["end"] = t["ends_at"].fillna(t["starts_at"] + pd.Timedelta(hours=12))
        fig = px.timeline(t, x_start="starts_at", x_end="end", y="domain", color="domain",
                          hover_name="title", hover_data=[c for c in ["event_type","source","evidence","region"] if c in t])
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

elif mode == "Trends":
    st.subheader("Zeitreihen")
    if sdf.empty:
        st.info("Noch keine v5-Zeitreihen im Filter.")
    else:
        metric_choices = sorted(sdf["metric"].dropna().unique())
        chosen = st.multiselect("Metriken", metric_choices, default=metric_choices[:min(4, len(metric_choices))])
        chart = sdf[sdf["metric"].isin(chosen)]
        if not chart.empty:
            fig = px.line(chart.sort_values("timestamp"), x="timestamp", y="value", color="metric",
                          line_dash="region" if chart["region"].nunique() > 1 else None,
                          hover_data=["source","unit","evidence","confidence"])
            st.plotly_chart(fig, use_container_width=True)

elif mode == "Heatmap":
    st.subheader("Signal-Heatmap")
    if sdf.empty:
        st.info("Heatmap benötigt historische v5-Signale.")
    else:
        h = sdf.copy()
        h["date"] = h["timestamp"].dt.date
        h["z"] = h.groupby("metric")["value"].transform(lambda s: (s-s.mean()) / s.std() if s.std() else 0)
        pivot = h.pivot_table(index="metric", columns="date", values="z", aggfunc="mean")
        fig = px.imshow(pivot, aspect="auto", color_continuous_midpoint=0, labels={"color":"Abweichung σ"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Standardisierte Abweichung innerhalb der aktuell gefilterten Historie; keine Kausalitätsaussage.")

elif mode == "Evidenz":
    st.subheader("Evidenz & Provenienz")
    a, b = st.tabs(["v5 Events/Signale", "bestehende Nische-Daten"])
    with a:
        combined = pd.concat([sdf.assign(record_type="signal"), edf.assign(record_type="event")], ignore_index=True, sort=False)
        if combined.empty: st.info("Keine v5-Daten.")
        else:
            cols = [c for c in ["record_type","domain","metric","event_type","title","value","unit","timestamp","starts_at","region","source","evidence","confidence","url"] if c in combined]
            st.dataframe(combined[cols], use_container_width=True, hide_index=True)
    with b:
        if legacy.empty: st.info("Keine passenden bestehenden Records.")
        else: st.dataframe(legacy, use_container_width=True, hide_index=True)

with st.expander("Filterzustand / Debug"):
    st.json({"view": st.session_state.v5_cfg, "period": [str(start), str(end)], "signals": len(fs), "events": len(fe)})
