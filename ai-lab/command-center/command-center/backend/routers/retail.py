from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from services.observability import log_api


router = APIRouter()


class RetailRefreshRequest(BaseModel):
    run_id: str | None = None
    force: bool = False


class RetailScenarioRequest(BaseModel):
    scenario_name: str | None = None
    assumptions: dict[str, Any] | None = None


def _not_configured_payload(section: str) -> dict[str, Any]:
    return {
        "ok": True,
        "section": section,
        "mode": "read_only",
        "configured": False,
        "items": [],
        "message": "Retail data source is not configured in this environment.",
    }


@router.get("/api/retail/health")
async def retail_health():
    log_api("retail", "health")
    return {
        "ok": True,
        "mode": "read_only",
        "configured": False,
        "status": "available_without_live_sources",
    }


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    log_api("retail", "dashboard", run_id=run_id)
    payload = _not_configured_payload("dashboard")
    payload["run_id"] = run_id
    payload["cards"] = []
    return payload


@router.get("/api/retail/stores")
async def retail_stores():
    log_api("retail", "stores")
    return _not_configured_payload("stores")


@router.post("/api/retail/refresh")
async def retail_refresh(body: RetailRefreshRequest):
    log_api("retail", "refresh", run_id=body.run_id, force=body.force)
    return {
        "ok": True,
        "mode": "read_only",
        "job_id": body.run_id or "retail-read-only-refresh",
        "status": "skipped",
        "message": "Retail refresh is unavailable because no live retail source is configured.",
    }


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    log_api("retail", "job", job_id=job_id)
    return {"ok": True, "job_id": job_id, "status": "skipped", "mode": "read_only"}


@router.get("/api/retail/capital")
async def retail_capital():
    log_api("retail", "capital")
    payload = _not_configured_payload("capital")
    payload["scenarios"] = []
    return payload


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(body: RetailScenarioRequest):
    log_api("retail", "capital_scenario", scenario_name=body.scenario_name)
    return {
        "ok": True,
        "mode": "read_only",
        "approval_id": None,
        "scenario": {
            "name": body.scenario_name or "untitled",
            "assumptions": body.assumptions or {},
            "status": "not_created",
        },
        "message": "No approval was created because retail capital execution is not configured.",
    }


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    log_api("retail", "capital_approve", approval_id=approval_id)
    return {
        "ok": True,
        "mode": "read_only",
        "approval_id": approval_id,
        "job_id": f"{approval_id}-read-only",
        "status": "skipped",
    }


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    log_api("retail", "capital_deny", approval_id=approval_id)
    return {"ok": True, "mode": "read_only", "approval_id": approval_id, "status": "denied"}


@router.get("/api/retail/consignment")
async def retail_consignment():
    log_api("retail", "consignment")
    return _not_configured_payload("consignment")


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    log_api("retail", "reconciliation")
    return _not_configured_payload("reconciliation")
