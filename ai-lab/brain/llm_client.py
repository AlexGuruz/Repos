"""
OpenAI-compatible chat completion client for local model runtimes (e.g. LM Studio).
Supports LM Studio native API (/api/v1/chat) first, then OpenAI-style /v1/chat/completions.
Uses stdlib only so brain has no extra dependencies.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

# Shorter default completions = faster average replies in command-center chat.
_DEFAULT_MAX_OUT: int = 1024


def _max_output_cap() -> int:
    raw = (os.environ.get("LLM_MAX_OUTPUT_TOKENS") or "").strip()
    if raw.isdigit():
        return max(256, min(8192, int(raw)))
    return _DEFAULT_MAX_OUT
# Avoid a remote /v1/models round-trip on every message (Tailscale/LAN LM Studio host).
_MODEL_LIST_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL_MODELS_OK_SEC = 90.0
_CACHE_TTL_MODELS_EMPTY_SEC = 4.0


def _server_base(base_url: str) -> str:
    """e.g. http://host:1234/v1 -> http://host:1234"""
    u = urlparse(base_url.strip().rstrip("/"))
    return f"{u.scheme}://{u.netloc}"


def list_openai_model_ids(
    base_url: str,
    timeout_sec: float = 5.0,
    *,
    use_cache: bool = True,
) -> list[str]:
    """GET OpenAI-style /v1/models — LM Studio lists loaded model id(s) here."""
    key = base_url.strip().rstrip("/")
    now = time.monotonic()
    if use_cache and key in _MODEL_LIST_CACHE:
        ts, cached = _MODEL_LIST_CACHE[key]
        ttl = _CACHE_TTL_MODELS_EMPTY_SEC if not cached else _CACHE_TTL_MODELS_OK_SEC
        if now - ts < ttl:
            return list(cached)

    url = base_url.rstrip("/") + "/models"
    ids: list[str] = []
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        _MODEL_LIST_CACHE[key] = (now, [])
        return []
    if not isinstance(out, dict):
        _MODEL_LIST_CACHE[key] = (now, [])
        return []
    data = out.get("data")
    if not isinstance(data, list):
        _MODEL_LIST_CACHE[key] = (now, [])
        return []
    for d in data:
        if isinstance(d, dict) and d.get("id"):
            ids.append(str(d["id"]))
    _MODEL_LIST_CACHE[key] = (now, ids)
    return ids


def resolve_model_from_list(ids: list[str], configured: str) -> tuple[str, str]:
    """
    Pick the model id LM Studio will see for chat.
    Prefer exact (case-insensitive) match to LLM_MODEL; else single loaded model; else first loaded.
    Returns (model_id, human note for diagnostics).
    """
    cfg = (configured or "").strip()
    if not ids:
        fallback = cfg or "gpt-3.5-turbo"
        return (fallback, "GET /v1/models failed or returned no models; using LLM_MODEL as-is (server may reject).")
    cfg_l = cfg.lower()
    if cfg:
        for mid in ids:
            if mid.lower() == cfg_l:
                return (mid, f"LLM_MODEL matches loaded server id `{mid}`.")
    if len(ids) == 1:
        return (ids[0], f"One model loaded (`{ids[0]}`); chat uses it" + (f" (LLM_MODEL `{cfg}` differs from id)" if cfg and ids[0].lower() != cfg_l else "."))
    return (
        ids[0],
        f"LLM_MODEL `{cfg}` not among loaded ids {ids!r}; chat uses `{ids[0]}` — set LLM_MODEL to the exact id you want.",
    )


def get_llm_connection_status(base_url: str, configured_model: str) -> dict[str, Any]:
    """Diagnostics for command-center: what chat will send to LM Studio."""
    base = (base_url or "").strip()
    cfg = (configured_model or "").strip()
    out: dict[str, Any] = {
        "llm_base_url": base or None,
        "llm_model_configured": cfg or None,
        "openai_server_base": _server_base(base) if base else None,
        "models_endpoint": (base.rstrip("/") + "/models") if base else None,
        "models_loaded_ids": [],
        "resolved_model_id": None,
        "resolution": "",
        "chat_uses_resolved_id": True,
        "hints": [],
    }
    if not base:
        out["resolution"] = "LLM_BASE_URL is empty — orchestrator will not call a local LLM."
        out["hints"].append("Set LLM_BASE_URL (e.g. http://100.71.161.10:1234/v1) in command-center backend .env")
        return out
    ids = list_openai_model_ids(base, timeout_sec=5.0, use_cache=False)
    out["models_loaded_ids"] = ids
    resolved, note = resolve_model_from_list(ids, cfg)
    out["resolved_model_id"] = resolved
    out["resolution"] = note
    if not ids:
        out["hints"].append("Open LM Studio → load your model → Local Server → Start (port 1234).")
        out["hints"].append(f"Then open {out['models_endpoint']} — you should see JSON with a data[].id.")
    elif cfg and all(mid.lower() != cfg.lower() for mid in ids):
        out["hints"].append("Copy the exact id from models_loaded_ids into LLM_MODEL in .env and restart the backend.")
    return out


def _try_lm_studio_native(
    base_url: str,
    model: str,
    messages: list[dict],
    timeout_sec: float,
) -> str | None:
    """POST to /api/v1/chat (LM Studio native). Request: model, system_prompt, input. Response: output[].content."""
    server = _server_base(base_url)
    url = server + "/api/v1/chat"
    system_content = ""
    user_content = ""
    for m in messages:
        if isinstance(m, dict):
            role = (m.get("role") or "").strip().lower()
            content = m.get("content") or ""
            if role == "system":
                system_content = content if isinstance(content, str) else str(content)
            elif role == "user":
                user_content = content if isinstance(content, str) else str(content)
    if not user_content:
        return None
    # Use id from /v1/models when possible (see chat_completion); LM Studio matches loaded model by this string.
    model_id = (model or "").strip() or "gpt-3.5-turbo"
    body = {
        "model": model_id,
        "input": user_content,
        "stream": False,
        "temperature": 0.3,
        "max_output_tokens": _max_output_cap(),
    }
    if system_content:
        body["system_prompt"] = system_content
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(out, dict):
        return None
    output = out.get("output")
    if not isinstance(output, list):
        return None
    parts = []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "message" and item.get("content"):
            parts.append(item["content"].strip() if isinstance(item["content"], str) else str(item["content"]).strip())
    return " ".join(parts).strip() or None


def _openai_chat_completion_stream(
    base_url: str,
    model_eff: str,
    messages: list[dict],
    timeout_sec: float,
    on_delta: Callable[[str], None],
    alt_model_ids: list[str],
    *,
    on_first_token: Callable[[], None] | None = None,
) -> str | None:
    """POST /v1/chat/completions with stream=true; emit token deltas. Returns full text or None."""
    import http.client

    url_path = base_url.rstrip("/") + "/chat/completions"
    u = urlparse(url_path)
    if not u.hostname:
        return None
    port = u.port or (443 if u.scheme == "https" else 80)
    path = u.path or "/"
    if u.query:
        path = f"{path}?{u.query}"

    to_try = [model_eff] + [m for m in alt_model_ids if m != model_eff]
    first_hook = on_first_token

    for mid in to_try:
        body = json.dumps(
            {
                "model": mid,
                "messages": messages,
                "stream": True,
                "max_tokens": _max_output_cap(),
                "temperature": 0.3,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        try:
            if u.scheme == "https":
                conn = http.client.HTTPSConnection(u.hostname, port, timeout=timeout_sec)
            else:
                conn = http.client.HTTPConnection(u.hostname, port, timeout=timeout_sec)
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            if resp.status != 200:
                conn.close()
                continue
            local: list[str] = []
            while True:
                raw = resp.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                delta = (choices[0] or {}).get("delta") if isinstance(choices[0], dict) else None
                piece = (delta or {}).get("content") if isinstance(delta, dict) else None
                if piece:
                    local.append(piece)
                    if first_hook:
                        first_hook()
                        first_hook = None
                    on_delta(piece)
            conn.close()
            text = "".join(local).strip()
            if text:
                return text
        except (OSError, json.JSONDecodeError, Exception):
            continue
    return None


def _parse_reply(out: dict) -> str | None:
    choices = out.get("choices") if isinstance(out, dict) else None
    if not choices or not isinstance(choices, list):
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    msg = first.get("message")
    if isinstance(msg, dict) and msg.get("content") is not None:
        text = msg["content"]
        return text.strip() if isinstance(text, str) else str(text).strip()
    delta = first.get("delta") or {}
    text = delta.get("content") if isinstance(delta, dict) else None
    if text is not None:
        return text.strip() if isinstance(text, str) else str(text).strip()
    return None


def chat_completion(
    base_url: str,
    model: str,
    messages: list[dict],
    timeout_sec: float = 60.0,
    stream_delta: Callable[[str], None] | None = None,
    *,
    on_first_token: Callable[[], None] | None = None,
    skip_model_list_probe: bool | None = None,
) -> str | None:
    """
    POST to base_url/chat/completions (OpenAI-compatible). Returns assistant text or None on failure.
    base_url should be the OpenAI-compatible root, e.g. http://100.71.161.10:1234/v1 (no trailing slash).
    messages: list of {"role": "system"|"user"|"assistant", "content": "..."}.
    If stream_delta is set, uses OpenAI streaming when supported; may fall back to one-shot native API
    (single delta with full text).

    on_first_token: invoked once when the first model output token is produced (stream or non-stream).

    skip_model_list_probe: when True, skip GET /v1/models (faster cold start). When None, env
    AI_LAB_LLM_SKIP_MODEL_LIST_PROBE=1 enables skip.
    """
    if not base_url or not base_url.strip():
        return None
    if skip_model_list_probe is None:
        skip_model_list_probe = os.environ.get("AI_LAB_LLM_SKIP_MODEL_LIST_PROBE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    if skip_model_list_probe:
        model_eff = (model or "").strip() or "gpt-3.5-turbo"
        ids: list[str] = []
    else:
        ids = list_openai_model_ids(base_url, timeout_sec=min(5.0, timeout_sec))
        model_eff, _ = resolve_model_from_list(ids, model)
    if stream_delta:
        streamed = _openai_chat_completion_stream(
            base_url,
            model_eff,
            messages,
            timeout_sec,
            stream_delta,
            ids,
            on_first_token=on_first_token,
        )
        if streamed is not None:
            return streamed
    # Try LM Studio native API first (POST /api/v1/chat) — matches your working curl
    reply = _try_lm_studio_native(base_url, model_eff, messages, timeout_sec)
    if reply:
        if on_first_token:
            on_first_token()
        if stream_delta:
            stream_delta(reply)
        return reply
    # Fallback: OpenAI-compatible POST /v1/chat/completions
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model_eff,
        "messages": messages,
        "max_tokens": _max_output_cap(),
        "temperature": 0.3,
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        reply = _parse_reply(out)
        if reply:
            if on_first_token:
                on_first_token()
            if stream_delta:
                stream_delta(reply)
            return reply
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass
    # Retry OpenAI path with each loaded id (model_eff may still not match server expectations)
    for alt in ids:
        if alt == model_eff:
            continue
        body["model"] = alt
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            got = _parse_reply(out)
            if got:
                if on_first_token:
                    on_first_token()
                if stream_delta:
                    stream_delta(got)
                return got
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            pass
    return None
