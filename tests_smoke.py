from modules.scorer import calculate_gap_score
from modules.normalization import dedupe_records, normalize_result
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
    assert len(db.recent_history("test")) == 2

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
