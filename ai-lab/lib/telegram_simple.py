"""Minimal Telegram outbound (urllib). Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() and os.environ.get("TELEGRAM_CHAT_ID", "").strip())


def send_telegram_message(text: str, *, parse_mode: str | None = None, timeout_sec: float = 30.0) -> dict:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    q: dict[str, str] = {"chat_id": chat, "text": text}
    if parse_mode:
        q["parse_mode"] = parse_mode
    url = f"https://api.telegram.org/bot{token}/sendMessage?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data
