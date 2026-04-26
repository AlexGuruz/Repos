"""
Load optional local env file for projection dashboard / Sheets tools (no extra deps).

File: ``config/dashboard_sheets.env`` (copy from ``config/dashboard_sheets.env.example``).
Ignored by git via ``*.env`` — set paths here so scripts find Stashbox without manual export each session.

Only sets variables that are **not** already in the process environment.
"""
from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def load_dashboard_sheets_env_file() -> None:
    """Load ``config/dashboard_sheets.env`` once per process."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    repo = Path(__file__).resolve().parents[1]
    path = repo / "config" / "dashboard_sheets.env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
