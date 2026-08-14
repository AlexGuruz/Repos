"""Read-only retail API placeholders.

These endpoints keep Command Center bootable when the optional retail lane is
not configured. They intentionally avoid external writes or background jobs.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/retail", tags=["retail"])


def _unconfigured() -> dict:
    return {
        "ok": True,
        "configured": False,
        "mode": "read_only",
        "status": "unconfigured",
        "message": "Retail integrations are not configured in this workspace.",
    }


@router.get("/health")
async def retail_health():
    return _unconfigured()


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    return {
        **_unconfigured(),
        "run_id": run_id,
        "metrics": [],
        "stores": [],
        "jobs": [],
    }


@router.get("/stores")
async def retail_stores():
    return {**_unconfigured(), "stores": []}


@router.post("/refresh")
async def retail_refresh(_body: dict | None = None):
    return {**_unconfigured(), "job_id": None, "started": False}


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return {**_unconfigured(), "job_id": job_id, "job": None}


@router.get("/capital")
async def retail_capital():
    return {**_unconfigured(), "scenarios": [], "pending_approvals": []}


@router.post("/capital/scenario")
async def retail_capital_scenario(_body: dict | None = None):
    return {**_unconfigured(), "approval_id": None, "job_id": None, "queued": False}


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    return {**_unconfigured(), "approval_id": approval_id, "approved": False, "job_id": None}


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {**_unconfigured(), "approval_id": approval_id, "denied": False}


@router.get("/consignment")
async def retail_consignment():
    return {**_unconfigured(), "items": []}


@router.get("/reconciliation")
async def retail_reconciliation():
    return {**_unconfigured(), "items": []}
