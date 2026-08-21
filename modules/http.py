import asyncio
import time
import requests
import aiohttp

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Nischen-Explorer/2.1 (+https://github.com/z3uss3l)"})

class HttpError(RuntimeError):
    pass

def request_json(method, url, *, timeout=15, **kwargs):
    started = time.perf_counter()
    response = SESSION.request(method, url, timeout=timeout, **kwargs)
    if response.status_code == 429:
        raise HttpError("HTTP 429 rate limit")
    if response.status_code >= 500:
        raise HttpError(f"HTTP {response.status_code} server error")
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise HttpError("Antwort war kein gültiges JSON") from exc
    return payload, int((time.perf_counter() - started) * 1000)

async def request_json_async(method, url, *, timeout=15, headers=None, params=None, json=None, auth=None):
    started = time.perf_counter()
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    basic_auth = aiohttp.BasicAuth(*auth) if auth else None
    request_headers = {"User-Agent": SESSION.headers["User-Agent"], "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    async with aiohttp.ClientSession(timeout=timeout_obj, headers=request_headers) as session:
        async with session.request(method, url, params=params, json=json, auth=basic_auth) as response:
            if response.status == 429:
                raise HttpError("HTTP 429 rate limit")
            if response.status >= 500:
                raise HttpError(f"HTTP {response.status} server error")
            if response.status >= 400:
                text = await response.text()
                raise HttpError(f"HTTP {response.status}: {text[:300]}")
            try:
                payload = await response.json(content_type=None)
            except Exception as exc:
                raise HttpError("Antwort war kein gültiges JSON") from exc
    return payload, int((time.perf_counter() - started) * 1000)

async def gather_limited(coros, limit=8):
    semaphore = asyncio.Semaphore(max(1, limit))
    async def guarded(coro):
        async with semaphore:
            return await coro
    return await asyncio.gather(*(guarded(c) for c in coros), return_exceptions=True)

async def request_text_async(method, url, *, timeout=15, headers=None, params=None, data=None, auth=None):
    """Async text request for feeds/HTML; preserves HTTP error semantics."""
    started = time.perf_counter()
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    basic_auth = aiohttp.BasicAuth(*auth) if auth else None
    request_headers = {"User-Agent": SESSION.headers["User-Agent"], "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,*/*"}
    if headers:
        request_headers.update(headers)
    async with aiohttp.ClientSession(timeout=timeout_obj, headers=request_headers) as session:
        async with session.request(method, url, params=params, data=data, auth=basic_auth, allow_redirects=True) as response:
            if response.status == 429:
                raise HttpError("HTTP 429 rate limit")
            if response.status >= 500:
                raise HttpError(f"HTTP {response.status} server error")
            if response.status >= 400:
                text = await response.text(errors="replace")
                raise HttpError(f"HTTP {response.status}: {text[:300]}")
            payload = await response.text(errors="replace")
    return payload, int((time.perf_counter() - started) * 1000)
