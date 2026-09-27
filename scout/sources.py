"""Web sources via Tavily — search + extract.

Tavily is the research layer of Scout (and its own prize category in the
hackathon: Best Use of Tavily, $3,000).
"""
import requests

from . import config


def _headers():
    if not config.TAVILY_API_KEY:
        raise RuntimeError(
            "TAVILY_API_KEY is not set. Get a free key at https://app.tavily.com"
        )
    return {"Authorization": f"Bearer {config.TAVILY_API_KEY}"}


def tavily_search(query, max_results=None):
    """Web search. Returns a list of {title, url, content} dicts."""
    resp = requests.post(
        "https://api.tavily.com/search",
        headers=_headers(),
        json={
            "query": query,
            "max_results": max_results or config.SCAN_MAX_RESULTS,
            "search_depth": "advanced",
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def tavily_extract(urls):
    """Pull readable page content. Returns {url: text}."""
    resp = requests.post(
        "https://api.tavily.com/extract",
        headers=_headers(),
        json={"urls": urls},
        timeout=60,
    )
    resp.raise_for_status()
    out = {}
    for r in resp.json().get("results", []):
        out[r.get("url")] = r.get("raw_content", "")
    return out


def scan_all(queries=None):
    """Run every query and merge + dedupe results by URL."""
    queries = queries or config.DEFAULT_QUERIES
    seen = {}
    for q in queries:
        try:
            for r in tavily_search(q):
                url = r.get("url", "")
                if url and url not in seen:
                    seen[url] = {
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("content", ""),
                    }
        except requests.HTTPError as e:
            # One failed query must not kill the scan.
            print(f"[sources] query failed ({e.response.status_code if e.response else '?'}): {q}")
        except requests.RequestException as e:
            print(f"[sources] query failed: {q} ({e})")
    return list(seen.values())
