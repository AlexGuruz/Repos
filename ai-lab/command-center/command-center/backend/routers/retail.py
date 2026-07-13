"""Retail dashboard API placeholder.

The frontend already links to these routes, so keep startup/navigation alive while
the trusted retail backend is unavailable. All responses are read-only and explicit.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/retail", tags=["retail"])


def _disabled_payload() -> dict:
    return {
        "status": "disabled",
        "available": False,
        "message": "Retail backend is not configured in this checkout.",
    }


@router.get("/health")
async def health():
    return _disabled_payload()


@router.get("/dashboard")
async def dashboard(run_id: str | None = None):
    return {**_disabled_payload(), "run_id": run_id, "rows": [], "metrics": {}}


@router.get("/stores")
async def stores():
    return {**_disabled_payload(), "stores": []}


@router.post("/refresh")
async def refresh(body: dict | None = None):
    raise HTTPException(status_code=503, detail="Retail refresh is unavailable: backend not configured")


@router.get("/jobs/{job_id}")
async def job(job_id: str):
    return {**_disabled_payload(), "job_id": job_id, "job": {"status": "unavailable"}}


@router.get("/capital")
async def capital():
    return {**_disabled_payload(), "scenarios": [], "trusted_payload": None}


@router.post("/capital/scenario")
async def capital_scenario(body: dict | None = None):
    raise HTTPException(status_code=503, detail="Retail capital scenarios are unavailable: backend not configured")


@router.post("/capital/scenario/{approval_id}/approve")
async def capital_scenario_approve(approval_id: str):
    raise HTTPException(status_code=503, detail=f"Retail approval {approval_id} cannot run: backend not configured")


@router.post("/capital/scenario/{approval_id}/deny")
async def capital_scenario_deny(approval_id: str):
    return {**_disabled_payload(), "approval_id": approval_id, "resolution": "denied"}


@router.get("/consignment")
async def consignment():
    return {**_disabled_payload(), "rows": []}


@router.get("/reconciliation")
async def reconciliation():
    return {**_disabled_payload(), "rows": []}
