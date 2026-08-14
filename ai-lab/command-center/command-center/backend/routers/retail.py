"""
Read-only Retail API placeholders.

The frontend exposes a Retail tab, but the full retail data pipeline is optional.
These endpoints keep Command Center startup healthy and report unavailable data
without performing external writes or inventing metrics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter

router = APIRouter(prefix="/api/retail")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(kind: str) -> dict:
    return {
        "ok": False,
        "kind": kind,
        "status": "unavailable",
        "generated_at": _now_iso(),
        "reason": "retail pipeline is not configured in this checkout",
    }


@router.get("/health")
async def retail_health():
    return _unavailable("health")


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    payload = _unavailable("dashboard")
    payload.update({"run_id": run_id, "rows": [], "summary": {}})
    return payload


@router.get("/stores")
async def retail_stores():
    payload = _unavailable("stores")
    payload["stores"] = []
    return payload


@router.post("/refresh")
async def retail_refresh(body: dict | None = None):
    return {
        **_unavailable("refresh"),
        "job_id": f"retail-unavailable-{uuid4().hex[:8]}",
        "requested": body or {},
    }


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return {**_unavailable("job"), "job_id": job_id}


@router.get("/capital")
async def retail_capital():
    payload = _unavailable("capital")
    payload.update({"available_cents": None, "scenarios": []})
    return payload


@router.post("/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    return {
        **_unavailable("capital_scenario"),
        "approval_id": None,
        "requested": body or {},
    }


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    return {
        **_unavailable("capital_approval"),
        "approval_id": approval_id,
        "job_id": f"retail-unavailable-{uuid4().hex[:8]}",
    }


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {**_unavailable("capital_denial"), "approval_id": approval_id}


@router.get("/consignment")
async def retail_consignment():
    payload = _unavailable("consignment")
    payload["rows"] = []
    return payload


@router.get("/reconciliation")
async def retail_reconciliation():
    payload = _unavailable("reconciliation")
    payload["rows"] = []
    return payload
