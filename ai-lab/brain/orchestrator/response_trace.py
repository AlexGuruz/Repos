"""
Structured per-request timing for AI-lab orchestrator → command-center chat.

Writes one JSON object per completed turn to state/ai_response_traces.jsonl (append-only).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _ai_lab_root() -> Path:
    return Path(__file__).resolve().parents[2]


def trace_file_path() -> Path:
    return _ai_lab_root() / "state" / "ai_response_traces.jsonl"


@dataclass
class StageTimer:
    """Monotonic segment timings in milliseconds."""

    _t0: float = field(default_factory=time.perf_counter)
    _last: float = field(init=False)
    segments_ms: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._last = self._t0

    def segment(self, name: str) -> None:
        now = time.perf_counter()
        self.segments_ms[f"{name}_ms"] = round((now - self._last) * 1000.0, 2)
        self._last = now

    def total_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000.0, 2)


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"


def append_response_trace(record: dict[str, Any]) -> None:
    """Best-effort append of one trace line."""
    try:
        path = trace_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def first_token_tracker() -> tuple[Callable[[], None], Callable[[], float | None]]:
    """Returns (mark_first_token, elapsed_ms_since_create)."""
    t0 = time.perf_counter()
    first: float | None = None

    def mark() -> None:
        nonlocal first
        if first is None:
            first = time.perf_counter()

    def elapsed() -> float | None:
        if first is None:
            return None
        return round((first - t0) * 1000.0, 2)

    return mark, elapsed
