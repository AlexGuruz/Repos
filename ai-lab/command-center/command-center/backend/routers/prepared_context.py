"""
Prepared context visibility + refresh endpoints.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

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


@router.get("/api/growflow/validation-status")
async def growflow_validation_status():
    from core.ai_lab import AI_LAB_ROOT

    growflow_root = AI_LAB_ROOT.parent / "Growflow"
    reports_root = growflow_root / "state" / "validation_reports"
    out: list[dict] = []
    if not reports_root.exists():
        return {"metrics": out, "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}

    for metric_dir in sorted([p for p in reports_root.iterdir() if p.is_dir()]):
        files = sorted(metric_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            continue
        latest = files[0]
        try:
            payload = json.loads(latest.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            payload = {}
        sv = payload.get("schema_verification") if isinstance(payload.get("schema_verification"), dict) else {}
        drift = sv.get("drift") if isinstance(sv.get("drift"), dict) else {}
        crit = drift.get("critical_missing_paths") if isinstance(drift.get("critical_missing_paths"), list) else []
        drift_active = bool(
            drift.get("missing_paths") or drift.get("added_paths") or drift.get("critical_missing_paths")
        )
        merged_warnings: list = []
        for key in (
            "warnings",
            "sanity_warnings",
            "schema_drift_warnings",
            "parser_warnings",
            "target_alignment_warnings",
        ):
            chunk = payload.get(key)
            if isinstance(chunk, list):
                merged_warnings.extend(chunk)
        seen_w: set[str] = set()
        deduped_warnings: list = []
        for w in merged_warnings:
            sw = str(w)
            if sw not in seen_w:
                seen_w.add(sw)
                deduped_warnings.append(w)
        out.append(
            {
                "metric_id": str(payload.get("metric_id") or metric_dir.name),
                "latest_report": str(latest.name),
                "ok": bool(payload.get("ok")),
                "confidence": payload.get("confidence"),
                "confidence_score": payload.get("confidence_score"),
                "field_confidence_counts": payload.get("field_confidence_counts") or {},
                "schema_drift": {
                    "baseline_exists": bool(sv.get("baseline_exists")),
                    "drift": drift_active,
                    "critical_missing_paths_count": len(crit),
                },
                "normalized_row_count": payload.get("normalized_row_count"),
                "warnings": deduped_warnings,
                "errors": payload.get("errors") or payload.get("hard_failures") or [],
                "generated_at": payload.get("generated_at"),
                "report_path": str(latest),
            }
        )
    return {"metrics": out, "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}

