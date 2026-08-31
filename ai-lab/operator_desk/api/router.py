"""Operator Desk FastAPI router (loopback-only; behind OPERATOR_DESK_ENABLED)."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from operator_desk.approvals import list_pending_approvals, submit_tool_proposal
from operator_desk.errors import OperatorError
from operator_desk.job_primer import load_job_manifest, load_job_primer
from operator_desk.settings import get_settings
from operator_desk.tools.email_ops import fetch_unread_digest, propose_draft_reply
from operator_desk.tools.growflow_ops import (
    get_growflow_bi_summary,
    get_growflow_capital,
    get_growflow_catalog,
    get_growflow_consignment,
    get_growflow_projection,
    get_growflow_retail,
    get_growflow_status,
)
from operator_desk.tools.repo_ops import get_repo_map_summary

router = APIRouter(prefix="/api/operator", tags=["operator_desk"])


def _enabled_or_404() -> None:
    if not get_settings().enabled:
        raise HTTPException(status_code=404, detail={"error_code": "OPERATOR_DISABLED"})


def _err(exc: OperatorError) -> HTTPException:
    status = 400
    if exc.code.endswith("UNAVAILABLE") or exc.code.endswith("MISSING"):
        status = 503
    return HTTPException(status_code=status, detail={"error_code": exc.code, "message": exc.message})


@router.get("/health")
def health() -> dict[str, Any]:
    _enabled_or_404()
    return {"ok": True, "service": "operator_desk", "version": "0.1.0"}


@router.get("/jobs")
def list_jobs() -> dict[str, Any]:
    _enabled_or_404()
    jobs = [
        {"job_id": e.job_id, "title": e.title, "tool_ids": list(e.tool_ids)}
        for e in load_job_manifest().values()
    ]
    return {"ok": True, "jobs": jobs}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    _enabled_or_404()
    bundle = load_job_primer(job_id)
    if not bundle.ok:
        raise HTTPException(
            status_code=404,
            detail={"error_code": bundle.error_code, "message": bundle.warnings},
        )
    return bundle.to_dict()


@router.get("/growflow/status")
def growflow_status() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_status().to_dict()


@router.get("/growflow/retail")
def growflow_retail() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_retail().to_dict()


@router.get("/growflow/capital")
def growflow_capital() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_capital().to_dict()


@router.get("/growflow/consignment")
def growflow_consignment() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_consignment().to_dict()


@router.get("/growflow/projection")
def growflow_projection() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_projection().to_dict()


@router.get("/growflow/bi")
def growflow_bi() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_bi_summary().to_dict()


@router.get("/growflow/catalog")
def growflow_catalog() -> dict[str, Any]:
    _enabled_or_404()
    return get_growflow_catalog().to_dict()


@router.get("/email/digest")
def email_digest(limit_per_account: int = 20) -> dict[str, Any]:
    _enabled_or_404()
    try:
        return fetch_unread_digest(limit_per_account=limit_per_account).to_dict()
    except OperatorError as exc:
        raise _err(exc) from exc


class DraftProposeBody(BaseModel):
    account_id: str
    message_id: str
    body_text: str = Field(..., max_length=20000)


@router.post("/email/drafts:propose")
def email_draft_propose(body: DraftProposeBody) -> dict[str, Any]:
    _enabled_or_404()
    try:
        return propose_draft_reply(body.account_id, body.message_id, body.body_text).to_dict()
    except OperatorError as exc:
        raise _err(exc) from exc


@router.get("/approvals/pending")
def approvals_pending() -> dict[str, Any]:
    _enabled_or_404()
    return list_pending_approvals().to_dict()


class ActionProposeBody(BaseModel):
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=3, max_length=2000)


@router.post("/actions:propose")
def actions_propose(body: ActionProposeBody) -> dict[str, Any]:
    _enabled_or_404()
    try:
        return submit_tool_proposal(body.tool_name, body.args, reason=body.reason).to_dict()
    except OperatorError as exc:
        raise _err(exc) from exc


@router.get("/repos/map")
def repos_map(q: str | None = None) -> dict[str, Any]:
    _enabled_or_404()
    return get_repo_map_summary(q).to_dict()


def is_router_enabled() -> bool:
    """Integration helper — check env/settings without raising."""
    if os.environ.get("OPERATOR_DESK_ENABLED", "").strip() in ("0", "false", "no"):
        return False
    try:
        return get_settings().enabled or os.environ.get("OPERATOR_DESK_ENABLED", "").strip() in (
            "1",
            "true",
            "yes",
            "on",
        )
    except Exception:
        return False
