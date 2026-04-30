"""
Read-only live work orchestration API (Phase 9).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


def _live_work_dir() -> Path:
    from core.ai_lab import AI_LAB_ROOT

    d = AI_LAB_ROOT / "state" / "live_work_orchestration"
    return d


def _status_sync() -> dict:
    idx = _live_work_dir() / "index.json"
    if not idx.is_file():
        return {"ok": False, "error": "live_work_index_missing", "hint": "Run scripts/build_live_work_orchestration_snapshots.py"}
    try:
        return {"ok": True, **json.loads(idx.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _plan_preview_sync() -> dict:
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.live_work_orchestration.compiler import compile_daily_plan_preview

    return {"ok": True, "preview": compile_daily_plan_preview()}


@router.get("/api/live-work/status")
async def live_work_status():
    return await asyncio.to_thread(_status_sync)


@router.get("/api/live-work/plan-preview")
async def live_work_plan_preview():
    return await asyncio.to_thread(_plan_preview_sync)
