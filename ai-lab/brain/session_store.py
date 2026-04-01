"""
SQLite session persistence (Guru §24 / Phase 3.1).

Stores minimal session fields so restarts don't lose context.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db_path() -> Path:
    env = os.environ.get("AI_LAB_SESSION_DB") or os.environ.get("SESSION_DB_PATH")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[1]
    return root / "sessions.sqlite"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          session_id TEXT PRIMARY KEY,
          state_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def load_session(session_id: str) -> dict[str, Any] | None:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except Exception:
        return None


def save_session(session_id: str, state: dict[str, Any]) -> None:
    try:
        payload = json.dumps(state, default=str)
        with _connect() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, state_json, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
                (session_id, payload, _now()),
            )
            conn.commit()
    except Exception:
        pass

