"""
Background refresher for prepared context snapshots.

Runs inside Command Center backend so snapshots refresh automatically
without manual script-by-script execution.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class RefreshPolicy:
    snapshot_type: str
    interval_sec: int


POLICIES: tuple[RefreshPolicy, ...] = (
    RefreshPolicy("worker_snapshot", 10 * 60),
    RefreshPolicy("system_snapshot", 15 * 60),
    RefreshPolicy("repo_pulse", 45 * 60),
    RefreshPolicy("project_agenda", 24 * 60 * 60),
    RefreshPolicy("personal_ops_snapshot", 24 * 60 * 60),
    RefreshPolicy("growflow_snapshot", 60 * 60),
)

_LAST_RUNS: dict[str, dict[str, Any]] = {}
_STATE: dict[str, Any] = {
    "running": False,
    "startup_warmup_ok": None,
    "startup_error": None,
    "last_loop_heartbeat": None,
}


def get_refresher_status() -> dict[str, Any]:
    return {
        "generated_at": _now_iso(),
        "policies": [{"snapshot_type": p.snapshot_type, "interval_sec": p.interval_sec} for p in POLICIES],
        "last_runs": _LAST_RUNS,
        "running": bool(_STATE.get("running")),
        "startup_warmup_ok": _STATE.get("startup_warmup_ok"),
        "startup_error": _STATE.get("startup_error"),
        "last_loop_heartbeat": _STATE.get("last_loop_heartbeat"),
    }


def _refresh_snapshot(snapshot_type: str) -> None:
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.prepared_context.builders import build_snapshot
    from brain.prepared_context.store import write_snapshot, write_index, SNAPSHOT_NAMES, load_snapshot

    started = time.perf_counter()
    status = {"started_at": _now_iso(), "ok": False, "error": None}
    try:
        s = build_snapshot(snapshot_type)
        write_snapshot(s)
        # keep index current after each refresh
        rows = []
        for name in SNAPSHOT_NAMES:
            data = load_snapshot(name)
            if not data:
                continue
            rows.append(
                {
                    "snapshot_type": name,
                    "generated_at": data.get("generated_at"),
                    "freshness_seconds": data.get("freshness_seconds"),
                    "stale": data.get("stale"),
                    "confidence": data.get("confidence"),
                    "errors": data.get("errors", []),
                    "summary_short": data.get("summary_short", ""),
                }
            )
        write_index(rows)
        status["ok"] = True
    except Exception as e:
        status["error"] = str(e)
    status["finished_at"] = _now_iso()
    status["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    _LAST_RUNS[snapshot_type] = status


async def run_prepared_context_refresher() -> None:
    """
    Forever loop that refreshes snapshots on policy intervals.
    """
    _STATE["running"] = True
    _STATE["startup_warmup_ok"] = None
    _STATE["startup_error"] = None
    try:
        # Initial warmup: build all snapshots once on startup.
        for p in POLICIES:
            await asyncio.to_thread(_refresh_snapshot, p.snapshot_type)
        _STATE["startup_warmup_ok"] = all((_LAST_RUNS.get(p.snapshot_type) or {}).get("ok") for p in POLICIES)
        if not _STATE["startup_warmup_ok"]:
            _STATE["startup_error"] = "startup warmup had one or more failed snapshots"
        last_run_monotonic = {p.snapshot_type: time.monotonic() for p in POLICIES}

        while True:
            _STATE["last_loop_heartbeat"] = _now_iso()
            now = time.monotonic()
            due = [p for p in POLICIES if (now - last_run_monotonic.get(p.snapshot_type, 0.0)) >= p.interval_sec]
            for p in due:
                await asyncio.to_thread(_refresh_snapshot, p.snapshot_type)
                last_run_monotonic[p.snapshot_type] = time.monotonic()
            await asyncio.sleep(20.0)
    finally:
        _STATE["running"] = False

