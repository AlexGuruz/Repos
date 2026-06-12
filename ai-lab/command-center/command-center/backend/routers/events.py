import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.models import ApprovalResolution
from core.ai_lab import ensure_ai_lab_root_on_path
from services.feed_bus import bus
from services.observability import log_api, log_error

ensure_ai_lab_root_on_path()

from brain.approval_queue.queue import list_pending, resolve  # noqa: E402
from brain.execution import run as execution_run  # noqa: E402
from brain.permanent_allowlist import (  # noqa: E402
    add_rule,
    brain_spec_match_payload,
    delete_rule,
    list_rules,
)
from services.repo_index_coordinator import get_coordinator

router = APIRouter()


class AddPermanentRuleBody(BaseModel):
    """action + match, or approval_id to derive from the brain queue row."""

    action: str | None = None
    match: dict = Field(default_factory=dict)
    note: str = ""
    source_approval_id: str | None = None
    approval_id: str | None = None


@router.get("/api/approvals/permanent")
async def list_permanent_rules():
    log_api("approvals", "permanent_list", count=len(list_rules()))
    return {"rules": list_rules()}


@router.post("/api/approvals/permanent")
async def create_permanent_rule(body: AddPermanentRuleBody):
    action = (body.action or "").strip() or None
    match = dict(body.match or {})
    src = (body.source_approval_id or "").strip() or None
    if body.approval_id and not src:
        src = body.approval_id.strip()
    if body.approval_id:
        aid = body.approval_id.strip()
        pending = dict(list_pending())
        spec = pending.get(aid)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Approval '{aid}' not in queue.")
        action = action or (spec.get("action_type") or spec.get("action") or "").strip()
        base = brain_spec_match_payload(spec)
        base.update({k: v for k, v in match.items() if v is not None and str(v).strip()})
        match = base
    if not action:
        raise HTTPException(status_code=400, detail="action is required (or pass approval_id).")
    try:
        rule = add_rule(action, match, note=body.note or "", source_approval_id=src)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await bus.publish(
        "feed",
        {
            "agent": "supervisor",
            "op": "sys",
            "detail": f"Permanent approval rule {rule['id']}: {action}",
            "bytes": None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    log_api("approvals", "permanent_add", rule_id=rule["id"], action=action)
    return {"ok": True, "rule": rule}


@router.delete("/api/approvals/permanent/{rule_id}")
async def remove_permanent_rule(rule_id: str):
    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found.")
    log_api("approvals", "permanent_delete", rule_id=rule_id)
    return {"ok": True}


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await bus.connect(ws)
    try:
        while True:
            # Keep connection alive; client messages are fire-and-forget pings
            await ws.receive_text()
    except WebSocketDisconnect:
        bus.disconnect(ws)


@router.post("/api/approvals/resolve")
async def resolve_approval(body: ApprovalResolution):
    log_api("approvals", "resolve_request", approval_id=body.id, resolution=body.resolution)
    aid = str(body.id).strip()
    pending_lookup = dict(list_pending())
    apr = pending_lookup.get(aid)
    ok = await _resolve_queue(aid, body.resolution == "approved")
    if not ok:
        if aid.upper().startswith("APR-"):
            from services.supervisor_bridge import execute_approved as execute_supervisor_approved
            from services.supervisor_bridge import pop_pending_controlled_approval

            supervisor_apr = pop_pending_controlled_approval(aid)
            if not supervisor_apr:
                log_error("approvals", "resolve_missing", approval_id=aid, resolution=body.resolution)
                return {"ok": False, "error": f"Approval '{aid}' not found in queue."}
            await bus.publish(
                "approval_resolution",
                {"id": aid, "resolution": body.resolution, "status": body.resolution},
            )
            if body.resolution == "approved":
                result = await execute_supervisor_approved(
                    aid,
                    str(supervisor_apr.get("agent") or "command-center"),
                    str(supervisor_apr.get("action") or "run_approved"),
                    dict(supervisor_apr.get("payload") or {}),
                )
                log_api("approvals", "resolve_supervisor_result", approval_id=aid, resolution=body.resolution, executed=True)
                return {"ok": True, **result}
            log_api("approvals", "resolve_supervisor_result", approval_id=aid, resolution=body.resolution, executed=False)
            return {"ok": True, "id": aid, "resolution": body.resolution}
        log_error("approvals", "resolve_missing", approval_id=aid, resolution=body.resolution)
        return {"ok": False, "error": f"Approval '{aid}' not found in queue."}

    resolution_data = {
        "id": aid,
        "resolution": body.resolution,
        "status": body.resolution,
    }
    await bus.publish("approval_resolution", resolution_data)

    # Hub coordinator approvals (Gate A/C for repo index) are resumed by coordinator,
    # not by execution.run(tool_name,...).
    if apr and str(apr.get("agent", "")) == "repo_index_coordinator":
        await get_coordinator().handle_approval_resolution(aid, body.resolution, apr)
        log_api("approvals", "resolve_result", approval_id=aid, resolution=body.resolution, executed=False, coordinator=True)
        return {"ok": True, "id": aid, "resolution": body.resolution}

    if body.resolution == "approved" and apr:
        result = await _execute_approved(aid, apr)
        log_api("approvals", "resolve_result", approval_id=aid, resolution=body.resolution, executed=True)
        return {"ok": True, **result}

    log_api("approvals", "resolve_result", approval_id=aid, resolution=body.resolution, executed=False)
    return {"ok": True, "id": aid, "resolution": body.resolution}


@router.get("/api/approvals")
async def list_approvals():
    approvals = []
    for apr_id, spec in list_pending():
        row = {
            "id": apr_id,
            "type": "approval",
            "agent": spec.get("agent", "orchestrator"),
            "action": spec.get("action") or spec.get("action_type", "approval"),
            "detail": spec.get("reason") or spec.get("detail") or spec.get("file_path", ""),
            "status": "pending",
            "timestamp": spec.get("created_at"),
        }
        if spec.get("catalog_context"):
            row["catalog_context"] = spec["catalog_context"]
        fp = spec.get("file_path")
        if fp:
            row["file_path"] = fp
        row["payload"] = brain_spec_match_payload(spec)
        approvals.append(row)
    log_api("approvals", "list", count=len(approvals))
    return approvals


async def _resolve_queue(approval_id: str, approve: bool) -> bool:
    return await asyncio.to_thread(resolve, approval_id, approve)


async def _execute_approved(approval_id: str, spec: dict):
    tool_name = spec.get("tool_name")
    args = spec.get("args", {})
    if tool_name:
        result = await asyncio.to_thread(execution_run, tool_name, args)
        status = "done" if result.success else "error"
        detail = (
            f"Approved run completed for `{tool_name}`."
            if result.success else
            f"Approved run failed for `{tool_name}`: {result.stderr or result.stdout or 'unknown error'}"
        )
        await bus.publish("action", {
            "id": f"ACT-{approval_id}",
            "type": "action",
            "agent": spec.get("agent", "orchestrator"),
            "op": "exec",
            "detail": detail,
            "status": status,
            "timestamp": spec.get("created_at"),
        })
        log_api(
            "approvals",
            "execute_approved",
            approval_id=approval_id,
            tool_name=tool_name,
            success=result.success,
            exit_code=result.exit_code,
        )
        return {"act_id": f"ACT-{approval_id}", "result": result.to_dict()}

    await bus.publish("action", {
        "id": f"ACT-{approval_id}",
        "type": "action",
        "agent": spec.get("agent", "orchestrator"),
        "op": "exec",
        "detail": f"Approval {approval_id} marked approved. No deferred execution payload was attached.",
        "status": "done",
        "timestamp": spec.get("created_at"),
    })
    log_api("approvals", "execute_approved", approval_id=approval_id, tool_name=None, success=True)
    return {"act_id": f"ACT-{approval_id}"}
