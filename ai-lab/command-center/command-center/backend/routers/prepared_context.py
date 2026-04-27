"""
Prepared context visibility + refresh endpoints.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

router = APIRouter()


def _load_all():
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.prepared_context.store import load_index
    from brain.prepared_context.loader import load_all_snapshots

    return {"index": load_index(), "snapshots": load_all_snapshots()}


def _load_one(snapshot_type: str):
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.prepared_context.loader import load_snapshot_fresh

    return load_snapshot_fresh(snapshot_type)


def _refresh(snapshot_type: str):
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.prepared_context.builders import build_all_snapshots, build_snapshot
    from brain.prepared_context.store import write_snapshot, write_index, SNAPSHOT_NAMES, load_snapshot

    snaps = build_all_snapshots() if snapshot_type == "all" else [build_snapshot(snapshot_type)]
    for s in snaps:
        write_snapshot(s)
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
    return {"ok": True, "refreshed": [s.snapshot_type for s in snaps]}


@router.get("/api/prepared-context")
async def prepared_context_all():
    return await asyncio.to_thread(_load_all)


@router.get("/api/prepared-context/{snapshot_type}")
async def prepared_context_one(snapshot_type: str):
    data = await asyncio.to_thread(_load_one, snapshot_type)
    return data or {"error": "snapshot_not_found", "snapshot_type": snapshot_type}


@router.post("/api/prepared-context/refresh/{snapshot_type}")
async def refresh_prepared_context(snapshot_type: str):
    return await asyncio.to_thread(_refresh, snapshot_type)


@router.get("/api/prepared-context/status/refresher")
async def prepared_context_refresher_status():
    from services.prepared_context_refresher import get_refresher_status

    return get_refresher_status()

