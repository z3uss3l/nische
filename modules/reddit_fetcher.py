from datetime import datetime, timezone, timedelta
import os
from .models import SourceResult

PAIN_TERMS = ["problem", "issue", "frustrat", "annoy", "broken", "missing", "lack", "can't", "cannot", "wish", "need", "alternative", "why isn't", "no way"]
WISH_TERMS = ["wish", "would love", "need a", "looking for", "is there a", "someone should", "i want", "would pay"]


def _classify(text):
    t = text.lower()
    pain = sum(1 for term in PAIN_TERMS if term in t)
    wish = sum(1 for term in WISH_TERMS if term in t)
    if wish > pain and wish > 0:
        return "wish", min(1.0, 0.35 + wish * 0.15)
    if pain > 0:
        return "complaint", min(1.0, 0.30 + pain * 0.12)
    return "other", 0.0


def fetch_reddit_pain_points(keyword, days=7, limit=120):
    client_id, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_SECRET")
    if not client_id or not secret:
        return SourceResult("Reddit", "disabled", error="REDDIT_CLIENT_ID/REDDIT_SECRET fehlen")
    try:
        import praw
        reddit = praw.Reddit(client_id=client_id, client_secret=secret,
                             user_agent=os.getenv("REDDIT_USER_AGENT", "nischen-explorer/1.0"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        seen, records = set(), []
        queries = [keyword, f'"{keyword}" problem', f'"{keyword}" alternative', f'"{keyword}" need']
        for query in queries:
            for post in reddit.subreddit("all").search(query, limit=max(20, limit // 2), sort="new", time_filter="month"):
                created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                if created < cutoff or post.id in seen:
                    continue
                seen.add(post.id)
                text = f"{post.title} {post.selftext or ''}".strip()
                intent, confidence = _classify(text)
                if intent == "other":
                    continue
                records.append({
                    "id": post.id, "source": "Reddit", "kind": "social", "title": post.title,
                    "text": text, "subreddit": str(post.subreddit), "score": int(post.score or 0),
                    "comments": int(post.num_comments or 0), "intent": intent, "intent_confidence": round(confidence, 3),
                    "date": created.isoformat(), "url": f"https://www.reddit.com{post.permalink}",
                })
                if len(records) >= limit:
                    break
            if len(records) >= limit:
                break
        records.sort(key=lambda r: (r["intent_confidence"], r["score"], r["comments"]), reverse=True)
        return SourceResult("Reddit", "ok" if records else "empty", records, total_available=len(records))
    except Exception as exc:
        return SourceResult("Reddit", "error", error=str(exc))
