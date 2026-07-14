from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/api/retail", tags=["retail"])


def _not_configured() -> dict:
    return {
        "ok": False,
        "status": "not_configured",
        "detail": "Retail command-center module is not available in this checkout.",
    }


@router.get("/health")
async def retail_health():
    return _not_configured()


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = None):
    out = _not_configured()
    out["run_id"] = run_id
    return out


@router.get("/stores")
async def retail_stores():
    out = _not_configured()
    out["stores"] = []
    return out


@router.post("/refresh")
async def retail_refresh(body: dict | None = None):
    out = _not_configured()
    out["request"] = body or {}
    return out


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    out = _not_configured()
    out["job_id"] = job_id
    return out


@router.get("/capital")
async def retail_capital():
    out = _not_configured()
    out["capital"] = {}
    return out


@router.post("/capital/scenario")
async def retail_capital_scenario(body: dict | None = None):
    out = _not_configured()
    out["request"] = body or {}
    return out


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    out = _not_configured()
    out["approval_id"] = approval_id
    return out


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    out = _not_configured()
    out["approval_id"] = approval_id
    return out


@router.get("/consignment")
async def retail_consignment():
    out = _not_configured()
    out["consignment"] = {}
    return out


@router.get("/reconciliation")
async def retail_reconciliation():
    out = _not_configured()
    out["reconciliation"] = {}
    return out
