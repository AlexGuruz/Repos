"""
Lightweight telemetry (Guru §24 / Phase 3.1).

Writes jsonl events for debugging trust: intent, sources used, proposals created/executed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Worker service events (Guru §26): worker_health_check, worker_service_call,
# worker_service_failure, worker_tunnel_missing, worker_service_unavailable


def log_event(name: str, **fields: Any) -> None:
    """
    Append telemetry event under ai-lab/logs/telemetry.jsonl. Best-effort.
    """
    try:
        root = Path(__file__).resolve().parents[1]
        out_dir = root / "logs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "telemetry.jsonl"
        payload = {"ts": _now(), "event": name, **fields}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass

