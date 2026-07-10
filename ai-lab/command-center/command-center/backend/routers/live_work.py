"""
Read-only live work orchestration API (Phase 9 + Phase 10 ClickUp proposals).
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


def _json_file_or_default(name: str, default: dict) -> dict:
    p = _live_work_dir() / name
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _clickup_queue_sync() -> dict:
    return {"ok": True, **_json_file_or_default("clickup_action_queue.json", {"generated_at": None, "items": []})}


def _clickup_preview_sync() -> dict:
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.live_work_orchestration.compiler import (
        compile_daily_plan_preview,
        generate_clickup_action_recommendations,
    )

    prev = compile_daily_plan_preview(include_action_recommendations=False)
    w = _json_file_or_default("work_demand_snapshot.json", {})
    t = _json_file_or_default("time_constraints_snapshot.json", {})
    p = _json_file_or_default("daily_progress_snapshot.json", {})
    g = _json_file_or_default("planning_gaps_snapshot.json", {})
    q = _json_file_or_default("communication_queue_snapshot.json", {})
    rec = generate_clickup_action_recommendations(
        prev,
        {
            "work_demand_snapshot": w,
            "time_constraints_snapshot": t,
            "daily_progress_snapshot": p,
            "planning_gaps_snapshot": g,
            "communication_queue_snapshot": q,
        },
        clickup_tool_available=False,
        enqueue=False,
    )
    return {"ok": True, "preview": rec}


def _repo_activity_ingestion_sync() -> dict:
    return {
        "ok": True,
        **_json_file_or_default(
            "ingestion/repo_activity_snapshot.json",
            {"generated_at": None, "snapshot_type": "repo_activity_snapshot", "data": {"activity": [], "summary": {}}},
        ),
    }


def _github_activity_ingestion_sync() -> dict:
    return {
        "ok": True,
        **_json_file_or_default(
            "ingestion/github_activity_snapshot.json",
            {
                "generated_at": None,
                "snapshot_type": "github_activity_snapshot",
                "data": {"prs": [], "issues": [], "feature_states": [], "correlation_summary": {}},
            },
        ),
    }


@router.get("/api/live-work/status")
async def live_work_status():
    return await asyncio.to_thread(_status_sync)


@router.get("/api/live-work/plan-preview")
async def live_work_plan_preview():
    return await asyncio.to_thread(_plan_preview_sync)


@router.get("/api/live-work/clickup-queue")
async def live_work_clickup_queue():
    return await asyncio.to_thread(_clickup_queue_sync)


@router.get("/api/live-work/clickup-preview")
async def live_work_clickup_preview():
    return await asyncio.to_thread(_clickup_preview_sync)


@router.get("/api/live-work/ingestion/repo-activity")
async def live_work_repo_activity_ingestion():
    return await asyncio.to_thread(_repo_activity_ingestion_sync)


@router.get("/api/live-work/ingestion/github-activity")
async def live_work_github_activity_ingestion():
    return await asyncio.to_thread(_github_activity_ingestion_sync)
