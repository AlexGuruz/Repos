from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter


router = APIRouter()


def _unavailable_payload(kind: str) -> dict:
    return {
        "ok": False,
        "status": "unavailable",
        "kind": kind,
        "items": [],
        "message": "Retail data adapter is not configured in this checkout.",
    }


@router.get("/api/retail/health")
async def retail_health():
    return {
        "ok": True,
        "status": "degraded",
        "read_only": True,
        "message": "Retail router loaded; no live retail adapter configured.",
    }


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    payload = _unavailable_payload("dashboard")
    payload["run_id"] = run_id
    payload["stores"] = []
    payload["metrics"] = []
    return payload


@router.get("/api/retail/stores")
async def retail_stores():
    return {"ok": True, "stores": [], "message": "No retail stores configured."}


@router.post("/api/retail/refresh")
async def retail_refresh(_body: dict | None = None):
    return {
        "ok": False,
        "job_id": str(uuid4()),
        "status": "skipped",
        "message": "Retail refresh is unavailable without a configured adapter.",
    }


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    return {"ok": False, "job_id": job_id, "status": "unknown", "message": "No retail job backend configured."}


@router.get("/api/retail/capital")
async def retail_capital():
    payload = _unavailable_payload("capital")
    payload["approvals"] = []
    payload["scenarios"] = []
    return payload


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(_body: dict | None = None):
    return {
        "ok": False,
        "approval_id": None,
        "status": "skipped",
        "message": "Capital scenarios require a configured retail adapter.",
    }


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    return {
        "ok": False,
        "approval_id": approval_id,
        "job_id": None,
        "status": "skipped",
        "message": "Capital scenario approval is unavailable without a configured retail adapter.",
    }


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {"ok": True, "approval_id": approval_id, "status": "denied"}


@router.get("/api/retail/consignment")
async def retail_consignment():
    return _unavailable_payload("consignment")


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    return _unavailable_payload("reconciliation")
