"""Safe placeholder retail API.

The Command Center frontend imports retail routes, but the live retail backend has
not been wired in this repo yet. These endpoints keep the app bootable while
reporting that the integration is unavailable instead of fabricating data.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


def _unconfigured_payload(section: str) -> dict:
    return {
        "ok": False,
        "status": "not_configured",
        "section": section,
        "items": [],
        "message": "Retail integration is not configured in this workspace.",
    }


class RetailScenarioBody(BaseModel):
    amount: float | None = None
    notes: str = ""
    metadata: dict = Field(default_factory=dict)


@router.get("/api/retail/health")
async def retail_health():
    return _unconfigured_payload("health")


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    payload = _unconfigured_payload("dashboard")
    payload["run_id"] = run_id
    payload["metrics"] = []
    return payload


@router.get("/api/retail/stores")
async def retail_stores():
    return _unconfigured_payload("stores")


@router.post("/api/retail/refresh")
async def retail_refresh(body: dict | None = None):
    payload = _unconfigured_payload("refresh")
    payload["accepted"] = False
    payload["request"] = body or {}
    return payload


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    payload = _unconfigured_payload("job")
    payload["job_id"] = job_id
    return payload


@router.get("/api/retail/capital")
async def retail_capital():
    payload = _unconfigured_payload("capital")
    payload["approvals"] = []
    return payload


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(body: RetailScenarioBody):
    payload = _unconfigured_payload("capital_scenario")
    payload["scenario"] = body.model_dump()
    return payload


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    payload = _unconfigured_payload("capital_approval")
    payload["approval_id"] = approval_id
    payload["approved"] = False
    return payload


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    payload = _unconfigured_payload("capital_approval")
    payload["approval_id"] = approval_id
    payload["approved"] = False
    return payload


@router.get("/api/retail/consignment")
async def retail_consignment():
    return _unconfigured_payload("consignment")


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    return _unconfigured_payload("reconciliation")
