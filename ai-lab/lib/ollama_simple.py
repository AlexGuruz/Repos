"""Minimal Ollama chat helper (HTTP). Defaults target worker-node local Ollama."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def ollama_base_url() -> str:
    return (
        os.environ.get("OLLAMA_HOST")
        or os.environ.get("LLM_BASE_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")


def ollama_model() -> str:
    return (os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "llama3.1:8b").strip()


def ollama_chat(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    timeout_sec: float = 120.0,
    base_url: str | None = None,
) -> str:
    """
    Call Ollama /api/chat. Returns assistant message content.
    base_url may be host root (…:11434) or OpenAI-style (…:11434/v1) — /v1 is stripped.
    """
    root = (base_url or ollama_base_url()).rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    url = f"{root}/api/chat"
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload: dict[str, Any] = {
        "model": model or ollama_model(),
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 256},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable at {url}: {exc}") from exc
    obj = json.loads(raw)
    msg = obj.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if not content:
        raise RuntimeError(f"Ollama empty response: {obj!r}")
    return str(content).strip()


def summarize_email_batch(rows: list[dict[str, Any]], *, model: str | None = None) -> str:
    """Short digest for Acheron toast. Falls back to a deterministic string on failure."""
    if not rows:
        return "No inbox mail processed."
    lines = []
    for row in rows[:15]:
        triage = row.get("triage") or {}
        lines.append(
            f"- [{triage.get('gmail_label', '?')}] "
            f"{(row.get('account_id') or '')}: "
            f"{(row.get('subject') or '(no subject)')[:80]}"
        )
    bullet = "\n".join(lines)
    prompt = (
        "Summarize these triaged emails in 2-4 short sentences for a desktop popup. "
        "Call out anything Hot/Urgent, Legal, or Needs Review. Do not invent details.\n\n"
        f"{bullet}"
    )
    try:
        return ollama_chat(
            prompt,
            model=model or ollama_model(),
            system="You write brief operator email digests. No fluff.",
            timeout_sec=90.0,
        )
    except Exception as exc:
        return (
            f"Processed {len(rows)} email(s). "
            f"(LLM summary unavailable: {exc})"
        )
