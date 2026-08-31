"""
Proxy to Growflow retail dashboard API (localhost:8791).

Approval flow (reuses Command Center sidebar + WebSocket):
  1. POST /capital/scenario with skip_approval=false → pending dict + bus.publish("approval")
  2. Sidebar + ChatPanel ApprovalCard show APR-cap-* events
  3. Approve → proxy POST /capital/scenario/{id}/execute on Growflow API
  4. Deny → proxy POST /capital/scenario/{id}/deny
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.channels import channels

router = APIRouter(prefix="/api/retail", tags=["retail"])

RETAIL_API_BASE = os.environ.get("GROWFLOW_RETAIL_API_URL", "http://127.0.0.1:8791").rstrip("/")
# Acheron must not run GrowFlow production writers. Default: honest disabled surface.
ACHERON_RETAIL_DISABLED = str(os.environ.get("ACHERON_RETAIL_DISABLED", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
}

_RETAIL_DISABLED = {
    "ok": False,
    "available": False,
    "disabled": True,
    "machine": "acheron",
    "reason": (
        "GrowFlow retail writers stay on power-1. This Acheron tab is read-status only "
        "and will not start or proxy a live GrowFlow production API."
    ),
}
_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=5.0)
_SCENARIO_TIMEOUT = httpx.Timeout(connect=15.0, read=15.0, write=15.0, pool=5.0)

# Local mirror of pending approvals (Growflow also stores pending for execute/deny).
_pending_retail_capital: dict[str, dict] = {}

# Shared HTTP client. Creating httpx.AsyncClient per-request is expensive on
# Windows (synchronous SSL-context construction ~1s) and, because it runs inside
# the async handler, it blocks the single-threaded event loop and serializes ALL
# Command Center requests. Reuse one client so that cost is paid once.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        try:
            await _client.aclose()
        except Exception:
            pass
    _client = None


class RefreshBody(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    preset: str = "last_30_days"
    compare: bool = True
    store_id: str | None = None
    channel: str = "all"
    start: str | None = None
    end: str | None = None


class CapitalScenarioBody(BaseModel):
    pool_usd: float = Field(default=18000.0, ge=1000, le=500_000)
    velocity_days: int = Field(default=49, ge=7, le=365)
    cash_cycle_days: int = Field(default=14, ge=7, le=90)
    allocation_mode: str = "buy-plan"
    days: int = Field(default=365, ge=30, le=730)
    skip_approval: bool = Field(default=False)


async def _proxy(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict:
    if ACHERON_RETAIL_DISABLED:
        raise HTTPException(503, _RETAIL_DISABLED["reason"])
    url = f"{RETAIL_API_BASE}{path}"
    t = timeout or _TIMEOUT
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    client = _get_client()
    try:
        if method == "GET":
            r = await client.get(url, params=clean_params or None, timeout=t)
        else:
            r = await client.post(url, json=json_body or {}, timeout=t)
    except httpx.ConnectError:
        raise HTTPException(
            503,
            f"Growflow retail API unreachable at {RETAIL_API_BASE}. "
            "Run scripts/run_retail_dashboard_api.ps1 in the Growflow repo.",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            503,
            f"Growflow retail API timed out at {RETAIL_API_BASE}. "
            "Ensure the Growflow API is running and responsive.",
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:500])
    return r.json()


def _capital_approval_detail(body: CapitalScenarioBody) -> str:
    return (
        f"Pool ${body.pool_usd:,.0f}, velocity {body.velocity_days}d, "
        f"cash cycle {body.cash_cycle_days}d, mode {body.allocation_mode} → "
        f"data/retail_capital_latest.json"
    )


@router.get("/health")
async def retail_health():
    if ACHERON_RETAIL_DISABLED:
        return _RETAIL_DISABLED
    return await _proxy("GET", "/api/health")


@router.get("/dashboard")
async def retail_dashboard(run_id: str | None = Query(default=None)):
    return await _proxy("GET", "/api/retail/dashboard", params={"run_id": run_id})


@router.get("/dashboard/range")
async def retail_dashboard_range(
    start: str = Query(...),
    end: str = Query(...),
    compare: bool = Query(default=False),
    compare_start: str | None = Query(default=None),
    compare_end: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    channel: str = Query(default="all"),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    budtender: str | None = Query(default=None),
):
    return await _proxy(
        "GET",
        "/api/retail/dashboard/range",
        params={
            "start": start,
            "end": end,
            "compare": str(compare).lower(),
            "compare_start": compare_start,
            "compare_end": compare_end,
            "store_id": store_id,
            "channel": channel,
            "brand": brand,
            "category": category,
            "budtender": budtender,
        },
    )


@router.get("/facets")
async def retail_facets():
    return await _proxy("GET", "/api/retail/facets")


@router.get("/live-status")
async def retail_live_status():
    return await _proxy("GET", "/api/retail/live-status")


@router.get("/stores")
async def retail_stores():
    return await _proxy("GET", "/api/retail/stores")


@router.post("/refresh")
async def retail_refresh(body: RefreshBody):
    return await _proxy("POST", "/api/retail/refresh", json_body=body.model_dump())


@router.get("/jobs/{job_id}")
async def retail_job(job_id: str):
    return await _proxy("GET", f"/api/retail/jobs/{job_id}")


@router.get("/capital")
async def retail_capital():
    return await _proxy("GET", "/api/retail/capital")


@router.get("/consignment")
async def retail_consignment():
    return await _proxy("GET", "/api/retail/consignment")


@router.get("/reconciliation")
async def retail_reconciliation():
    return await _proxy("GET", "/api/retail/reconciliation")


@router.get("/projection")
async def retail_projection():
    return await _proxy("GET", "/api/v1/projection")


@router.get("/platform-health")
async def retail_platform_health():
    return await _proxy("GET", "/api/v1/platform/health")


@router.get("/platform-events/latest")
async def retail_platform_events_latest():
    return await _proxy("GET", "/api/v1/platform/events/latest")


@router.get("/bi")
async def retail_bi():
    return await _proxy("GET", "/api/v1/bi")


@router.post("/capital/scenario")
async def retail_capital_scenario(body: CapitalScenarioBody):
    if body.skip_approval:
        return await _proxy("POST", "/api/retail/capital/scenario", json_body=body.model_dump(), timeout=_SCENARIO_TIMEOUT)

    result = await _proxy(
        "POST",
        "/api/retail/capital/scenario",
        json_body={**body.model_dump(), "skip_approval": False},
        timeout=_SCENARIO_TIMEOUT,
    )
    approval_id = result.get("approval_id") or f"APR-cap-{uuid.uuid4().hex[:8]}"
    _pending_retail_capital[approval_id] = {
        "approval_id": approval_id,
        "job_id": result.get("job_id"),
        "scenario": body.model_dump(),
        "summary": result.get("summary"),
    }
    await channels.control.publish(
        "approval",
        {
            "id": approval_id,
            "type": "approval",
            "agent": "growflow-retail",
            "action": "retail_capital_scenario",
            "detail": _capital_approval_detail(body),
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "payload": {
                **body.model_dump(),
                "job_id": result.get("job_id"),
                "expected_output": result.get("expected_output", "data/retail_capital_latest.json"),
                "summary": result.get("summary"),
                "approve_route": f"/api/retail/capital/scenario/{approval_id}/approve",
                "deny_route": f"/api/retail/capital/scenario/{approval_id}/deny",
            },
        },
    )
    return {
        **result,
        "approval_id": approval_id,
        "status": "awaiting_approval",
        "approval_required": True,
    }


@router.post("/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    # Allow approve after ai-lab restart when Growflow still holds the pending spec.
    result = await _proxy(
        "POST",
        f"/api/retail/capital/scenario/{approval_id}/execute",
        timeout=_SCENARIO_TIMEOUT,
    )
    _pending_retail_capital.pop(approval_id, None)
    await channels.control.publish(
        "approval_resolution",
        {"id": approval_id, "resolution": "approved", "status": "approved", "job_id": result.get("job_id")},
    )
    await channels.ops.publish(
        "dashboard_run_completed",
        {
            "job_id": result.get("job_id"),
            "job_type": "capital_scenario",
            "approval_id": approval_id,
            "status": "queued_or_running",
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
    )
    return {"ok": True, "approval_id": approval_id, **result}


@router.post("/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    _pending_retail_capital.pop(approval_id, None)
    try:
        await _proxy("POST", f"/api/retail/capital/scenario/{approval_id}/deny", timeout=_SCENARIO_TIMEOUT)
    except HTTPException as e:
        if e.status_code != 404:
            raise
    await channels.control.publish(
        "approval_resolution",
        {"id": approval_id, "resolution": "denied", "status": "denied"},
    )
    return {"ok": True, "approval_id": approval_id, "resolution": "denied"}
