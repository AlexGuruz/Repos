"""Command Center observability — per-channel JSONL with rotation."""
from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from core.ai_lab import AI_LAB_ROOT


LOG_DIR = AI_LAB_ROOT / "logs" / "command_center"
_MAX_BYTES = int(os.environ.get("CC_JSONL_MAX_BYTES", str(50 * 1024 * 1024)))
_RETENTION = int(os.environ.get("CC_JSONL_RETENTION", "5"))

# Per-stream executors so one channel cannot block another's writes.
_CHANNEL_EXECUTORS: dict[str, ThreadPoolExecutor] = {}
_CHANNEL_LOCKS: dict[str, Lock] = {}
_API_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cc-jsonl-api")
_ERR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cc-jsonl-err")
_API_LOCK = Lock()
_ERR_LOCK = Lock()
_LEGACY_EVENT_STREAM = "event_stream"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_for(name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"{name}.jsonl"


def _executor_for(name: str) -> ThreadPoolExecutor:
    if name not in _CHANNEL_EXECUTORS:
        _CHANNEL_EXECUTORS[name] = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"cc-jsonl-{name}")
        _CHANNEL_LOCKS[name] = Lock()
    return _CHANNEL_EXECUTORS[name]


def _rotate_if_needed(path: Path, lock: Lock) -> None:
    try:
        if not path.exists() or path.stat().st_size < _MAX_BYTES:
            return
        with lock:
            if not path.exists() or path.stat().st_size < _MAX_BYTES:
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = path.with_name(f"{path.stem}_{stamp}.jsonl")
            shutil.move(str(path), str(dest))
            # Retention: keep newest N rotated files
            rotated = sorted(path.parent.glob(f"{path.stem}_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in rotated[_RETENTION:]:
                try:
                    old.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass


def _append_jsonl_sync(name: str, record: dict[str, Any], lock: Lock) -> Path:
    # Never reopen the legacy monster event_stream for append.
    if name == _LEGACY_EVENT_STREAM:
        name = "ops"
    path = _path_for(name)
    _rotate_if_needed(path, lock)
    payload = {"logged_at": _now(), **record}
    line = json.dumps(payload, default=str)
    with lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return path


def append_jsonl(name: str, record: dict[str, Any]) -> Path:
    path = _path_for(name if name != _LEGACY_EVENT_STREAM else "ops")
    if name in {"api_requests"}:
        _API_EXECUTOR.submit(_append_jsonl_sync, name, record, _API_LOCK)
        return path
    if name in {"errors"}:
        _ERR_EXECUTOR.submit(_append_jsonl_sync, name, record, _ERR_LOCK)
        return path
    ex = _executor_for(name)
    lock = _CHANNEL_LOCKS[name]
    ex.submit(_append_jsonl_sync, name, record, lock)
    return path


def log_api(category: str, action: str, **fields: Any) -> Path:
    return append_jsonl(
        "api_requests",
        {"category": category, "action": action, **fields},
    )


def log_channel_event(channel: str, event_type: str, data: Any) -> Path:
    """Per-channel event log. Telemetry snapshots sampled (~1/10)."""
    if channel == "telemetry":
        # Sample: only log alerts or ~10% of snapshots via simple hash
        if event_type == "hardware":
            return _path_for("telemetry")
        # hardware_alert always logged
    return append_jsonl(
        channel if channel in {"telemetry", "control", "chat", "ops"} else "ops",
        {"channel": channel, "event": event_type, "data": data},
    )


def log_event_stream(event: str, data: Any) -> Path:
    """Legacy helper — routes into channel files; never appends event_stream.jsonl."""
    # Map roughly like compatibility shim
    if event in {"hardware", "hardware_alert"} or str(event).startswith("hardware"):
        return log_channel_event("telemetry", event, data)
    if event in {"approval", "approval_resolution", "action"} or str(event).startswith("approval"):
        return log_channel_event("control", event, data)
    if event == "chat" or str(event).startswith("chat"):
        return log_channel_event("chat", event, data)
    return log_channel_event("ops", event, data)


def log_error(category: str, error_message: str, **fields: Any) -> Path:
    return append_jsonl(
        "errors",
        {"category": category, "message": error_message, **fields},
    )


def log_metric(name: str, **fields: Any) -> Path:
    return append_jsonl(
        "metrics",
        {"metric": name, **fields},
    )


def ensure_legacy_event_stream_not_appended() -> dict[str, Any]:
    """Safe guard: rename active event_stream.jsonl if oversized so it is never appended."""
    path = LOG_DIR / "event_stream.jsonl"
    info: dict[str, Any] = {"path": str(path), "action": "none"}
    try:
        if not path.exists():
            return info
        size = path.stat().st_size
        info["size_bytes"] = size
        if size >= _MAX_BYTES:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = LOG_DIR / f"event_stream_{stamp}.jsonl.archived"
            shutil.move(str(path), str(dest))
            info["action"] = "archived"
            info["dest"] = str(dest)
    except Exception as exc:
        info["action"] = "error"
        info["error"] = str(exc)[:200]
    return info
