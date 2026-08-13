"""Safe placeholder retail API.

The frontend exposes a Retail tab, but the live retail service is not wired in
this repo yet. Keep the command center bootable and fail closed for mutations.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/retail", tags=["retail"])


def _unavailable() -> dict:
    return {
        "ok": False,
        "status": "unavailable",
        "reason": "retail_service_not_configured",
        "message": "Retail workflows are not connected in this environment.",
    }


@router.get("/health")
async def retail_health():
    return _unavailable()


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    return {**_unavailable(), "run_id": run_id, "metrics": [], "sections": []}


@router.get("/stores")
async def retail_stores():
    return {**_unavailable(), "stores": []}


@router.post("/refresh")
async def retail_refresh(body: dict | None = None):
    return {**_unavailable(), "accepted": False, "request": body or {}}


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return {**_unavailable(), "job_id": job_id, "job": None}


@router.get("/capital")
async def retail_capital():
    return {**_unavailable(), "scenarios": [], "trusted_payload": None}


@router.post("/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    return {**_unavailable(), "approval_required": False, "scenario": None, "request": body or {}}


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    raise HTTPException(status_code=409, detail=f"Retail capital approvals are unavailable: {approval_id}")


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {**_unavailable(), "approval_id": approval_id, "resolution": "denied"}


@router.get("/consignment")
async def retail_consignment():
    return {**_unavailable(), "items": []}


@router.get("/reconciliation")
async def retail_reconciliation():
    return {**_unavailable(), "items": []}
