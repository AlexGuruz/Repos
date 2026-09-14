"""
Read-only retail dashboard API.

The fuller retail data pipeline is optional; these endpoints keep Command
Center import/startup stable and return explicit empty states when no snapshot
files have been produced yet.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

router = APIRouter(prefix="/api/retail")

_JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _growflow_root() -> Path:
    from core.ai_lab import AI_LAB_ROOT

    return AI_LAB_ROOT.parent / "Growflow"


def _read_json(path: Path, default: dict) -> dict:
    if not path.is_file():
        return default
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc), **default}
    return raw if isinstance(raw, dict) else default


@router.get("/health")
async def retail_health():
    root = _growflow_root()
    return {
        "ok": True,
        "generated_at": _now(),
        "growflow_root": str(root),
        "growflow_root_exists": root.exists(),
        "mode": "read_only_empty_state",
    }


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    default = {"ok": True, "run_id": run_id, "stores": [], "summary": {}, "rows": [], "generated_at": _now()}
    return _read_json(_growflow_root() / "state" / "retail_dashboard.json", default)


@router.get("/stores")
async def retail_stores():
    default = {"ok": True, "stores": [], "generated_at": _now()}
    return _read_json(_growflow_root() / "state" / "retail_stores.json", default)


@router.post("/refresh")
async def retail_refresh(body: dict | None = None):
    job_id = f"retail-refresh-{uuid4().hex[:10]}"
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "skipped",
        "requested_at": _now(),
        "request": body or {},
        "message": "Retail refresh worker is not configured in this checkout.",
    }
    return {"ok": True, **_JOBS[job_id]}


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return {"ok": True, **_JOBS.get(job_id, {"job_id": job_id, "status": "unknown"})}


@router.get("/capital")
async def retail_capital():
    default = {"ok": True, "available_capital": None, "scenarios": [], "pending_approvals": [], "generated_at": _now()}
    return _read_json(_growflow_root() / "state" / "retail_capital.json", default)


@router.post("/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    approval_id = f"retail-capital-{uuid4().hex[:10]}"
    payload = {
        "approval_id": approval_id,
        "status": "preview_only",
        "requested_at": _now(),
        "request": body or {},
        "message": "Capital scenario execution is not configured in this checkout.",
    }
    _JOBS[approval_id] = payload
    return {"ok": True, **payload}


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    job_id = f"retail-capital-approved-{uuid4().hex[:10]}"
    _JOBS[job_id] = {
        "job_id": job_id,
        "approval_id": approval_id,
        "status": "skipped",
        "message": "Capital scenario execution is not configured in this checkout.",
        "requested_at": _now(),
    }
    return {"ok": True, **_JOBS[job_id]}


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    _JOBS[approval_id] = {"approval_id": approval_id, "status": "denied", "requested_at": _now()}
    return {"ok": True, **_JOBS[approval_id]}


@router.get("/consignment")
async def retail_consignment():
    default = {"ok": True, "rows": [], "summary": {}, "generated_at": _now()}
    return _read_json(_growflow_root() / "state" / "retail_consignment.json", default)


@router.get("/reconciliation")
async def retail_reconciliation():
    default = {"ok": True, "rows": [], "summary": {}, "generated_at": _now()}
    return _read_json(_growflow_root() / "state" / "retail_reconciliation.json", default)
