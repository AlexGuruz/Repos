"""
Daily agenda stub: read project_state / summaries, return today's focus list.
"""
from __future__ import annotations

import json
from pathlib import Path

_root = Path(__file__).resolve().parents[2]


def get_daily_agenda() -> list[str]:
    """Return list of suggested focus items for today."""
    agenda = []
    state_path = _root / "memory" / "project_state.json"
    if state_path.exists():
        with open(state_path) as f:
            data = json.load(f)
        for proj in data.get("projects", [])[:5]:
            agenda.append(f"Project: {proj.get('name', '?')} ({proj.get('status', '?')})")
    if not agenda:
        agenda.append("No projects in project_state; add repos to summaries and project_state.")
    return agenda
