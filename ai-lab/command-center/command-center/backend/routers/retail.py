from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

router = APIRouter()


_CAPITAL_APPROVALS: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _growflow_root() -> Path:
    from core.ai_lab import AI_LAB_ROOT

    return AI_LAB_ROOT.parent / "Growflow"


def _prepared_growflow_snapshot() -> dict:
    from core.ai_lab import AI_LAB_ROOT

    path = AI_LAB_ROOT / "state" / "prepared_context" / "growflow_snapshot.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _retail_health_sync() -> dict:
    root = _growflow_root()
    snap = _prepared_growflow_snapshot()
    data = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    return {
        "ok": root.is_dir(),
        "generated_at": _now_iso(),
        "growflow_root": str(root),
        "growflow_snapshot_available": bool(snap),
        "validation_status_by_metric": data.get("validation_status_by_metric") or {},
        "warnings": [] if root.is_dir() else ["Growflow sibling repo not found"],
    }


def _retail_dashboard_sync(run_id: str | None = None) -> dict:
    snap = _prepared_growflow_snapshot()
    data = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    return {
        "ok": True,
        "run_id": run_id,
        "generated_at": snap.get("generated_at") or _now_iso(),
        "summary": snap.get("summary_short") or "Growflow retail dashboard snapshot unavailable.",
        "validation_status_by_metric": data.get("validation_status_by_metric") or {},
        "latest_trusted_output_by_metric": data.get("latest_trusted_output_by_metric") or {},
    }


@router.get("/api/retail/health")
async def retail_health():
    return await asyncio.to_thread(_retail_health_sync)


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    return await asyncio.to_thread(_retail_dashboard_sync, run_id)


@router.get("/api/retail/stores")
async def retail_stores():
    return {"ok": True, "stores": [], "generated_at": _now_iso(), "note": "No store catalog is committed."}


@router.post("/api/retail/refresh")
async def retail_refresh(body: dict | None = None):
    return {
        "ok": True,
        "job_id": f"retail-refresh-{uuid4().hex[:8]}",
        "status": "preview-only",
        "request": body or {},
        "note": "Refresh is not executed from Command Center in this environment.",
    }


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    return {"ok": True, "job_id": job_id, "status": "preview-only", "generated_at": _now_iso()}


@router.get("/api/retail/capital")
async def retail_capital():
    return {
        "ok": True,
        "approvals": list(_CAPITAL_APPROVALS.values()),
        "status": "preview-only",
        "generated_at": _now_iso(),
    }


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    approval_id = f"retail-capital-{uuid4().hex[:8]}"
    payload = {
        "id": approval_id,
        "action": "retail_capital_scenario",
        "status": "pending",
        "payload": body or {},
        "created_at": _now_iso(),
    }
    _CAPITAL_APPROVALS[approval_id] = payload
    return {"ok": True, "approval_id": approval_id, "approval": payload}


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    approval = _CAPITAL_APPROVALS.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    approval["status"] = "approved"
    approval["resolved_at"] = _now_iso()
    return {"ok": True, "approval_id": approval_id, "job_id": f"retail-capital-job-{uuid4().hex[:8]}"}


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    approval = _CAPITAL_APPROVALS.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    approval["status"] = "denied"
    approval["resolved_at"] = _now_iso()
    return {"ok": True, "approval_id": approval_id}


@router.get("/api/retail/consignment")
async def retail_consignment():
    return {"ok": True, "items": [], "generated_at": _now_iso(), "note": "No consignment snapshot is committed."}


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    return {"ok": True, "items": [], "generated_at": _now_iso(), "note": "No reconciliation snapshot is committed."}
