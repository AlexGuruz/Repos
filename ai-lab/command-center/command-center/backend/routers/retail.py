"""Read-only Retail/Growflow status endpoints for Command Center."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _disabled(feature: str) -> dict:
    return {
        "ok": True,
        "feature": feature,
        "read_only": True,
        "status": "not_configured",
        "generated_at": _now(),
        "message": "Retail lane is wired read-only; no refresh, approval, or external mutation is performed here.",
    }


@router.get("/api/retail/health")
async def retail_health():
    return _disabled("retail_health")


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    payload = _disabled("retail_dashboard")
    payload.update({"run_id": run_id, "stores": [], "metrics": []})
    return payload


@router.get("/api/retail/stores")
async def retail_stores():
    payload = _disabled("retail_stores")
    payload.update({"stores": []})
    return payload


@router.post("/api/retail/refresh")
async def retail_refresh(body: dict | None = None):
    payload = _disabled("retail_refresh")
    payload.update({"job_id": f"retail-readonly-{uuid4().hex[:8]}", "request": body or {}})
    return payload


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    payload = _disabled("retail_job")
    payload.update({"job_id": job_id, "state": "skipped"})
    return payload


@router.get("/api/retail/capital")
async def retail_capital():
    payload = _disabled("retail_capital")
    payload.update({"approvals": [], "scenarios": []})
    return payload


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    payload = _disabled("retail_capital_scenario")
    payload.update({"approval_id": None, "scenario": body or {}})
    return payload


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    payload = _disabled("retail_capital_approve")
    payload.update({"approval_id": approval_id, "job_id": None, "decision": "not_applied"})
    return payload


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    payload = _disabled("retail_capital_deny")
    payload.update({"approval_id": approval_id, "decision": "not_applied"})
    return payload


@router.get("/api/retail/consignment")
async def retail_consignment():
    payload = _disabled("retail_consignment")
    payload.update({"items": []})
    return payload


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    payload = _disabled("retail_reconciliation")
    payload.update({"items": []})
    return payload
