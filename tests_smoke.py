from modules.scorer import calculate_gap_score
from modules.normalization import dedupe_records, normalize_result
from modules.normalization import consistency_report
from modules.models import SourceResult
from modules.web_sources import _feed_entries
from modules import db


def test_score_is_bounded_and_bsr_is_not_competition():
    score = calculate_gap_score(
        trends=[{"value": 10}, {"value": 20}, {"value": 30}],
        reddit=[{"intent":"complaint", "score":20, "comments":5, "intent_confidence":.8}],
        books=[{"title":"A"},{"title":"A"},{"title":"B"}],
        social_mentions=[], keepa=[{"asin":"A","bsr":100}],
        seo_gaps=[{"search_volume":1000,"competition":.2,"cpc":1.2}],
    )
    assert 0 <= score["score"] <= 10
    assert 0 <= score["confidence"] <= 1
    assert score["market_traction"] is not None


def test_dedupe():
    out = dedupe_records([{"id":"1","source":"x","kind":"social","title":"x"},{"id":"1","source":"x","kind":"social","title":"x"}])
    assert len(out) == 1


def test_dedupe_keeps_same_id_from_different_sources():
    out = dedupe_records([
        {"id": "1", "source": "x", "kind": "social"},
        {"id": "1", "source": "y", "kind": "feed"},
    ])
    assert len(out) == 2


def test_consistency_report_matches_keywords_and_cross_source_duplicates():
    report = consistency_report("solar battery", [
        {"id": "1", "source": "A", "kind": "news", "title": "Solar battery"},
        {"id": "2", "source": "B", "kind": "news", "title": "Solar battery", "url": "https://example.test/x"},
        {"id": "3", "source": "C", "kind": "news", "title": "Other", "url": "https://example.test/x"},
    ])
    assert report["keyword_matches"] == 2
    assert report["duplicate_count"] == 1


def test_pydantic_validation_counts_bad_records():
    result = normalize_result(SourceResult("Test", "ok", [
        {"id":"1","source":"Test","kind":"x","title":"ok"},
        {"source":"Test","kind":"x"},
    ]))
    assert result.count == 1
    assert result.invalid_records == 1


def test_sqlite_wal_and_upsert(tmp_path, monkeypatch):
    dbfile = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    db._ENGINE = None
    assert db.save_analysis("test", "DE", 7, {"score": 5, "confidence": .8}, [], [
        {"canonical_id":"abc","source":"Test","kind":"x","title":"A"}
    ])
    assert db.save_analysis("test", "DE", 7, {"score": 6, "confidence": .9}, [], [
        {"canonical_id":"abc","source":"Test","kind":"x","title":"B"}
    ])
    history = db.recent_history("test")
    assert len(history) == 2
    assert [row["score"] for row in history] == [5, 6]

import asyncio
from modules.scorer import calculate_gap_score
from modules.social_trends_fetcher import _tag


def test_extended_score_accepts_new_sources():
    score = calculate_gap_score(
        trends=[{"value": 50}, {"value": 60}, {"value": 70}],
        reddit=[], books=[], social_mentions=[], keepa=[],
        seo_gaps=[{"search_volume": 5000, "competition": .3}],
        youtube=[{"views": 100000}],
        platform_trends=[{"platform": "X", "tweet_count": 50000}, {"platform": "Pinterest", "growth_mom": 40}],
        shopping=[{"seller": "a"}, {"seller": "b"}], services=[{"title": "Service A"}],
        books_source_available=False,
    )
    assert 0 <= score["score"] <= 10
    assert score["youtube_views"] == 100000
    assert score["shopping_sellers"] == 2


def test_hashtag_normalization():
    assert _tag("CRISPR Archaeology!") == "crisprarchaeology"


def test_related_queries_are_trend_only_signals():
    score = calculate_gap_score(
        trends=[{"value": 50}, {"value": 60}, {"value": 70}],
        reddit=[], books=[], social_mentions=[], keepa=[],
        seo_gaps=[{"search_volume": 5000, "competition": .3}],
        related_queries=[
            {"query_type": "rising", "value": 100},
            {"query_type": "rising", "value": 50},
            {"query_type": "top", "value": 100},
        ],
        books_source_available=False,
    )
    assert score["rising_queries"] == 2
    assert 0 <= score["trend"] <= 1


def test_rss_dublin_core_date_is_parsed():
    entries = _feed_entries(
        '<rss><channel><item><title>Example</title>'
        '<dc:date xmlns:dc="http://purl.org/dc/elements/1.1/">2026-08-21</dc:date>'
        '</item></channel></rss>'
    )
    assert entries[0]["date"] == "2026-08-21"


def test_google_autocomplete_discovery(monkeypatch):
    from modules import web_sources

    async def fake_request_text_async(method, url, **kwargs):
        assert "suggestqueries.google.com" in url
        return '["test", ["test tool", "test software", "test service"]]', 7

    monkeypatch.setattr(web_sources, "request_text_async", fake_request_text_async)
    result = asyncio.run(web_sources.fetch_google_autocomplete("test", "DE"))
    assert result.status == "ok"
    assert result.count >= 3
    assert all(r["kind"] == "related_query" for r in result.records)
    assert all(r["query_type"] == "autocomplete" for r in result.records)


def test_german_market_sources(monkeypatch):
    from modules import germany_sources

    async def fake_json(method, url, **kwargs):
        if "govdata" in url:
            return {"result": {"count": 1, "results": [{"id": "d1", "name": "heat-data", "title": "Wärmepumpen Daten", "notes": "Marktdaten", "tags": []}]}}, 5
        if "ted.europa.eu" in url:
            return {"totalNoticeCount": 1, "notices": [{"publication-number": "1-2026", "notice-title": "Wärmepumpe", "buyer-name": "Kommune"}]}, 6
        return [], 4

    monkeypatch.setattr(germany_sources, "request_json_async", fake_json)
    gov = asyncio.run(germany_sources.fetch_govdata("Wärmepumpe"))
    ted = asyncio.run(germany_sources.fetch_ted_procurement("Wärmepumpe"))
    assert gov.status == "ok" and gov.count == 1
    assert ted.status == "ok" and ted.count == 1
    assert ted.records[0]["kind"] == "procurement"


def test_procurement_is_real_demand_signal():
    score = calculate_gap_score(
        trends=[], reddit=[], books=[], social_mentions=[], keepa=[], seo_gaps=[],
        procurement=[{"id": str(i), "source": "TED Ausschreibungen", "kind": "procurement"} for i in range(25)],
        books_source_available=False,
    )
    assert score["procurement_notices"] == 25
    assert score["demand"] > 0


def test_temporal_signal_enrichment_is_point_in_time():
    from datetime import datetime, timezone, timedelta
    from modules.intelligence_models import TemporalSignal
    from modules.temporal_intelligence import enrich_signal

    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    history = [
        TemporalSignal(signal_id=f"s{i}", timestamp=now-timedelta(days=i), source="test",
                       domain="weather", metric="temperature", value=20+i, unit="C",
                       region="DE-BY", subject="market")
        for i in range(1, 8)
    ]
    future = TemporalSignal(signal_id="future", timestamp=now+timedelta(days=1), source="test",
                            domain="weather", metric="temperature", value=99, region="DE-BY",
                            subject="market")
    current = TemporalSignal(signal_id="now", timestamp=now, source="test", domain="weather",
                             metric="temperature", value=30, unit="C", region="DE-BY", subject="market")
    enriched = enrich_signal(current, history + [future])
    assert enriched.baseline < 99
    assert enriched.change_1d is not None
    assert 0 <= enriched.percentile <= 1


def test_lagged_relationship_does_not_claim_causality():
    from datetime import datetime, timezone, timedelta
    from modules.intelligence_models import TemporalSignal
    from modules.temporal_intelligence import lagged_correlation

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    x = [TemporalSignal(signal_id=f"x{i}", timestamp=start+timedelta(days=i), source="x",
                        domain="a", metric="x", value=float(i), subject="m") for i in range(20)]
    y = [TemporalSignal(signal_id=f"y{i}", timestamp=start+timedelta(days=i+2), source="y",
                        domain="b", metric="y", value=float(i), subject="m") for i in range(20)]
    rels = lagged_correlation(x, y, 5)
    best = max(rels, key=lambda r: abs(r["correlation"]))
    assert best["sample_size"] >= 5
    assert "causal" not in best
