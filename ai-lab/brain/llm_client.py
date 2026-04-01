"""
OpenAI-compatible chat completion client for local model runtimes (e.g. LM Studio).
Supports LM Studio native API (/api/v1/chat) first, then OpenAI-style /v1/chat/completions.
Uses stdlib only so brain has no extra dependencies.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse


def _server_base(base_url: str) -> str:
    """e.g. http://localhost:1234/v1 -> http://localhost:1234"""
    u = urlparse(base_url.strip().rstrip("/"))
    return f"{u.scheme}://{u.netloc}"


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
    # LM Studio native API often expects lowercase model id (e.g. qwen2.5-coder-14b-instruct)
    model_id = (model or "").strip().lower() or "qwen2.5-coder-14b-instruct"
    body = {
        "model": model_id,
        "input": user_content,
        "stream": False,
        "temperature": 0.3,
        "max_output_tokens": 2048,
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


def _get_first_model_id(base_url: str, timeout_sec: float = 5.0) -> str | None:
    """GET /v1/models and return the id of the first model (LM Studio often has one loaded)."""
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(out, dict):
        return None
    data = out.get("data")
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data[0].get("id")
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
) -> str | None:
    """
    POST to base_url/chat/completions (OpenAI-compatible). Returns assistant text or None on failure.
    base_url should be e.g. http://localhost:1234/v1 (no trailing slash).
    messages: list of {"role": "system"|"user"|"assistant", "content": "..."}.
    """
    if not base_url or not base_url.strip():
        return None
    # Try LM Studio native API first (POST /api/v1/chat) — matches your working curl
    reply = _try_lm_studio_native(base_url, model, messages, timeout_sec)
    if reply:
        return reply
    # Fallback: OpenAI-compatible POST /v1/chat/completions
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
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
            return reply
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass
    # Fallback: LM Studio may expose the loaded model under a different id (e.g. with quantization suffix)
    fallback_id = _get_first_model_id(base_url, timeout_sec=5.0)
    if fallback_id and fallback_id != model:
        body["model"] = fallback_id
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            return _parse_reply(out)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            pass
    return None
