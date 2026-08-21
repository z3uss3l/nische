import os
from .http import request_json
from .models import SourceResult


def fetch_books_openlibrary(keyword, limit=40, timeout=15):
    url = "https://openlibrary.org/search.json"
    params = {"q": keyword, "limit": min(limit, 100), "fields": "key,title,author_name,first_publish_year,edition_count,ratings_average,subject,number_of_pages_median"}
    try:
        data, latency = request_json("GET", url, params=params, timeout=timeout)
        records = []
        for doc in data.get("docs", []):
            records.append({
                "id": doc.get("key") or doc.get("title"), "source": "OpenLibrary", "kind": "book",
                "title": doc.get("title", ""), "author": ", ".join(doc.get("author_name", [])[:3]),
                "year": doc.get("first_publish_year"), "edition_count": doc.get("edition_count", 0),
                "rating": doc.get("ratings_average"), "subjects": ", ".join(doc.get("subject", [])[:8]),
                "pages": doc.get("number_of_pages_median"),
                "url": f"https://openlibrary.org{doc.get('key', '')}" if doc.get("key") else "",
            })
        return SourceResult("OpenLibrary", "ok" if records else "empty", records, latency_ms=latency, total_available=data.get("numFound"))
    except Exception as exc:
        return SourceResult("OpenLibrary", "error", error=str(exc))


def fetch_books_google(keyword, limit=40, timeout=15):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": keyword, "maxResults": min(limit, 40), "orderBy": "relevance", "printType": "books", "projection": "lite"}
    if os.getenv("GOOGLE_BOOKS_API_KEY"):
        params["key"] = os.getenv("GOOGLE_BOOKS_API_KEY")
    try:
        data, latency = request_json("GET", url, params=params, timeout=timeout)
        records = []
        for item in data.get("items", []):
            vol = item.get("volumeInfo", {})
            records.append({
                "id": item.get("id"), "source": "Google Books", "kind": "book",
                "title": vol.get("title", ""), "author": ", ".join(vol.get("authors", [])[:3]),
                "year": (vol.get("publishedDate") or "")[:4], "rating": vol.get("averageRating"),
                "rating_count": vol.get("ratingsCount", 0), "subjects": ", ".join(vol.get("categories", [])[:8]),
                "pages": vol.get("pageCount"), "url": vol.get("infoLink", ""),
            })
        return SourceResult("Google Books", "ok" if records else "empty", records, latency_ms=latency, total_available=data.get("totalItems"))
    except Exception as exc:
        return SourceResult("Google Books", "error", error=str(exc))
