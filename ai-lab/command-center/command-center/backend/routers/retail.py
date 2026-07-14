"""Retail dashboard API surface for the Command Center.

These endpoints are read-only/placeholders unless a retail data pipeline writes
snapshots under the ai-lab state directory.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.ai_lab import AI_LAB_ROOT

router = APIRouter()


class RetailRefreshBody(BaseModel):
    run_id: str | None = None
    scope: str = Field(default="all")


def _retail_dir() -> Path:
    return AI_LAB_ROOT / "state" / "retail"


def _load_json(name: str, default: dict[str, Any]) -> dict[str, Any]:
    p = _retail_dir() / name
    if not p.is_file():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"read_failed:{exc}", **default}
    return data if isinstance(data, dict) else default


def _health_sync() -> dict[str, Any]:
    d = _retail_dir()
    return {
        "ok": True,
        "configured": d.exists(),
        "state_dir": str(d),
        "note": "Retail endpoints are read-only and use local snapshots when present.",
    }


@router.get("/api/retail/health")
async def retail_health():
    return await asyncio.to_thread(_health_sync)


@router.get("/api/retail/dashboard")
async def retail_dashboard(run_id: str | None = None):
    default = {"ok": True, "run_id": run_id, "stores": [], "metrics": {}, "warnings": ["retail snapshot not found"]}
    return await asyncio.to_thread(_load_json, "dashboard.json", default)


@router.get("/api/retail/stores")
async def retail_stores():
    return await asyncio.to_thread(_load_json, "stores.json", {"ok": True, "stores": []})


@router.post("/api/retail/refresh")
async def retail_refresh(body: RetailRefreshBody):
    return {
        "ok": False,
        "status": "not_configured",
        "run_id": body.run_id,
        "scope": body.scope,
        "message": "No retail refresh worker is configured in this repository.",
    }


@router.get("/api/retail/jobs/{job_id}")
async def retail_job(job_id: str):
    return {"ok": False, "job_id": job_id, "status": "not_found"}


@router.get("/api/retail/capital")
async def retail_capital():
    return await asyncio.to_thread(_load_json, "capital.json", {"ok": True, "scenarios": [], "approvals": []})


@router.post("/api/retail/capital/scenario")
async def retail_capital_scenario(body: dict[str, Any]):
    return {
        "ok": False,
        "status": "not_configured",
        "scenario": body,
        "message": "Retail capital scenarios require a configured retail snapshot pipeline.",
    }


@router.post("/api/retail/capital/scenario/{approval_id}/approve")
async def retail_capital_approve(approval_id: str):
    return {"ok": False, "approval_id": approval_id, "status": "not_found"}


@router.post("/api/retail/capital/scenario/{approval_id}/deny")
async def retail_capital_deny(approval_id: str):
    return {"ok": False, "approval_id": approval_id, "status": "not_found"}


@router.get("/api/retail/consignment")
async def retail_consignment():
    return await asyncio.to_thread(_load_json, "consignment.json", {"ok": True, "items": []})


@router.get("/api/retail/reconciliation")
async def retail_reconciliation():
    return await asyncio.to_thread(_load_json, "reconciliation.json", {"ok": True, "items": []})
