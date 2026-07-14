"""
Read-only retail API stubs for Command Center.

The frontend already links to these routes; returning explicit unavailable states keeps
the backend importable until live Growflow/retail integrations are configured.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter


router = APIRouter(prefix="/api/retail")
_JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/health")
async def retail_health():
    return {
        "ok": True,
        "configured": False,
        "read_only": True,
        "generated_at": _now(),
        "detail": "Retail integrations are not configured in this checkout.",
    }


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    return {
        "ok": True,
        "run_id": run_id,
        "stores": [],
        "metrics": [],
        "warnings": ["retail data source not configured"],
        "generated_at": _now(),
    }


@router.get("/stores")
async def retail_stores():
    return {"ok": True, "stores": [], "generated_at": _now()}


@router.post("/refresh")
async def retail_refresh(body: dict | None = None):
    job_id = f"retail-refresh-{uuid4().hex[:10]}"
    job = {
        "job_id": job_id,
        "status": "skipped",
        "read_only": True,
        "request": body or {},
        "detail": "No retail data source configured; refresh skipped safely.",
        "generated_at": _now(),
    }
    _JOBS[job_id] = job
    return job


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return _JOBS.get(
        job_id,
        {
            "job_id": job_id,
            "status": "unknown",
            "read_only": True,
            "detail": "Job id is not present in this backend process.",
            "generated_at": _now(),
        },
    )


@router.get("/capital")
async def retail_capital():
    return {"ok": True, "scenarios": [], "trusted_payload": None, "generated_at": _now()}


@router.post("/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    approval_id = f"retail-capital-{uuid4().hex[:10]}"
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "preview-only",
        "approval_required": True,
        "scenario": body or {},
        "generated_at": _now(),
    }


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    job_id = f"retail-capital-{uuid4().hex[:10]}"
    job = {
        "job_id": job_id,
        "approval_id": approval_id,
        "status": "skipped",
        "read_only": True,
        "detail": "Approval acknowledged, but no retail writer is configured.",
        "generated_at": _now(),
    }
    _JOBS[job_id] = job
    return job


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {"ok": True, "approval_id": approval_id, "status": "denied", "generated_at": _now()}


@router.get("/consignment")
async def retail_consignment():
    return {"ok": True, "rows": [], "generated_at": _now()}


@router.get("/reconciliation")
async def retail_reconciliation():
    return {"ok": True, "rows": [], "generated_at": _now()}
