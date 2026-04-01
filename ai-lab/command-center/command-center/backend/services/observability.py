from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from core.ai_lab import AI_LAB_ROOT


LOG_DIR = AI_LAB_ROOT / "logs" / "command_center"
_WRITE_LOCK = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_for(name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"{name}.jsonl"


def append_jsonl(name: str, record: dict[str, Any]) -> Path:
    path = _path_for(name)
    payload = {
        "logged_at": _now(),
        **record,
    }
    line = json.dumps(payload, default=str)
    with _WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return path


def log_api(category: str, action: str, **fields: Any) -> Path:
    return append_jsonl(
        "api_requests",
        {
            "category": category,
            "action": action,
            **fields,
        },
    )


def log_event_stream(event: str, data: Any) -> Path:
    return append_jsonl(
        "event_stream",
        {
            "event": event,
            "data": data,
        },
    )


def log_error(category: str, error_message: str, **fields: Any) -> Path:
    return append_jsonl(
        "errors",
        {
            "category": category,
            "message": error_message,
            **fields,
        },
    )
