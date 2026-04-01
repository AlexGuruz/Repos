"""
Web search tool (Guru §24 / Phase 3.1). Returns structured results for evidence fusion.

Providers are selected by env vars (no new dependencies required):
- Tavily: set TAVILY_API_KEY
- Serper: set SERPER_API_KEY

If no provider configured, returns [] (graceful degradation).
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.parse
from typing import Any


def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Run a web search and return list of { title, url, snippet, timestamp }.
    Configurable provider; returns [] if unavailable.
    """
    q = (query or "").strip()
    if not q:
        return []
    max_results = max(1, min(int(max_results or 5), 10))

    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if tavily_key:
        return _tavily_search(q, tavily_key, max_results=max_results)

    serper_key = os.environ.get("SERPER_API_KEY", "").strip()
    if serper_key:
        return _serper_search(q, serper_key, max_results=max_results)

    return []


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_sec: int = 8) -> dict[str, Any] | None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _tavily_search(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    data = _post_json(url, payload, headers={})
    if not data:
        return []
    results = data.get("results") or []
    out: list[dict[str, Any]] = []
    for r in results[:max_results]:
        out.append({
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("content") or r.get("snippet") or "",
            "timestamp": r.get("published_date") or r.get("retrieved_at") or "",
            "source": "tavily",
            "published_at": r.get("published_date"),
            "retrieved_at": data.get("response_time") or "",
        })
    return out


def _serper_search(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": max_results}
    data = _post_json(url, payload, headers={"X-API-KEY": api_key})
    if not data:
        return []
    results = data.get("organic") or []
    out: list[dict[str, Any]] = []
    for r in results[:max_results]:
        out.append({
            "title": r.get("title") or "",
            "url": r.get("link") or "",
            "snippet": r.get("snippet") or "",
            "timestamp": "",
            "source": "serper",
            "published_at": r.get("date"),
            "retrieved_at": "",
        })
    return out
