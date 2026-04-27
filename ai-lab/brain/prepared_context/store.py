"""
Prepared context file store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import PreparedSnapshot, now_iso, validate_snapshot_dict

SNAPSHOT_NAMES = (
    "system_snapshot",
    "repo_pulse",
    "project_agenda",
    "personal_ops_snapshot",
    "growflow_snapshot",
    "worker_snapshot",
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def prepared_context_dir() -> Path:
    p = _root() / "state" / "prepared_context"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshot_path(snapshot_type: str) -> Path:
    return prepared_context_dir() / f"{snapshot_type}.json"


def index_path() -> Path:
    return prepared_context_dir() / "index.json"


def write_snapshot(snapshot: PreparedSnapshot) -> Path:
    p = snapshot_path(snapshot.snapshot_type)
    p.write_text(json.dumps(snapshot.to_dict(), indent=2, default=str), encoding="utf-8")
    return p


def load_snapshot(snapshot_type: str) -> dict[str, Any] | None:
    p = snapshot_path(snapshot_type)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    ok, errs = validate_snapshot_dict(data)
    if not ok:
        data.setdefault("errors", [])
        data["errors"] = list(data["errors"]) + errs
    return data


def write_index(rows: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": now_iso(),
        "snapshots": rows,
    }
    index_path().write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def load_index() -> dict[str, Any]:
    p = index_path()
    if not p.exists():
        return {"generated_at": None, "snapshots": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "snapshots": []}

