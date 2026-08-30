import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.models import ApprovalResolution
from core.ai_lab import ensure_ai_lab_root_on_path
from services.channels import channels
from services.executors import APPROVAL_EXECUTOR, EXEC_EXECUTOR, run_in
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
    rules = await run_in(APPROVAL_EXECUTOR, list_rules)
    log_api("approvals", "permanent_list", count=len(rules))
    return {"rules": rules}


@router.post("/api/approvals/permanent")
async def create_permanent_rule(body: AddPermanentRuleBody):
    """
    Always Approve guardrail: permanent rule must be created while the brain
    approval is still pending (permanent-before-resolve). Rejects create-after-resolved.
    """
    action = (body.action or "").strip() or None
    match = dict(body.match or {})
    src = (body.source_approval_id or "").strip() or None
    if body.approval_id and not src:
        src = body.approval_id.strip()
    # Brain queue ids: require still-pending before creating a durable rule.
    guard_id = (body.approval_id or src or "").strip()
    if guard_id.lower().startswith("approval-"):
        pending = await run_in(APPROVAL_EXECUTOR, _pending_as_dict)
        if guard_id not in pending:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Approval '{guard_id}' is missing or already resolved. "
                    "Always Approve requires a pending approval_id "
                    "(save permanent rule, then resolve — permanent-before-resolve)."
                ),
            )
    if body.approval_id:
        aid = body.approval_id.strip()
        pending = await run_in(APPROVAL_EXECUTOR, _pending_as_dict)
        spec = pending.get(aid)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Approval '{aid}' not in queue.")
        action = action or (spec.get("action_type") or spec.get("action") or "").strip()
        base = brain_spec_match_payload(spec)
        if spec.get("tool_name") and "tool_name" not in base:
            base["tool_name"] = str(spec["tool_name"])
        base.update({k: v for k, v in match.items() if v is not None and str(v).strip()})
        match = base
    if not action:
        raise HTTPException(status_code=400, detail="action is required (or pass approval_id).")
    try:
        rule = await run_in(
            APPROVAL_EXECUTOR,
            lambda: add_rule(action, match, note=body.note or "", source_approval_id=src),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        await channels.control.publish(
            "permanent_rule",
            {"rule": rule, "action": action},
        )
        await channels.ops.publish(
            "feed",
            {
                "agent": "supervisor",
                "op": "sys",
                "detail": f"Permanent approval rule {rule['id']}: {action}",
                "bytes": None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    except Exception as exc:
        log_error("approvals", "permanent_publish_failed", rule_id=rule["id"], error=str(exc)[:200])
    log_api("approvals", "permanent_add", rule_id=rule["id"], approval_action=action)
    return {"ok": True, "rule": rule}


@router.delete("/api/approvals/permanent/{rule_id}")
async def remove_permanent_rule(rule_id: str):
    ok = await run_in(APPROVAL_EXECUTOR, delete_rule, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found.")
    try:
        await channels.control.publish("permanent_rule_deleted", {"rule_id": rule_id})
    except Exception as exc:
        log_error("approvals", "permanent_delete_publish_failed", rule_id=rule_id, error=str(exc)[:200])
    log_api("approvals", "permanent_delete", rule_id=rule_id)
    return {"ok": True}


async def _ws_channel(ws: WebSocket, name: str) -> None:
    ch = channels.get(name)  # type: ignore[arg-type]
    await ch.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ch.disconnect(ws)


@router.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await _ws_channel(ws, "telemetry")


@router.websocket("/ws/control")
async def ws_control(ws: WebSocket):
    await _ws_channel(ws, "control")


@router.websocket("/ws/ops")
async def ws_ops(ws: WebSocket):
    await _ws_channel(ws, "ops")


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await _ws_channel(ws, "chat")


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Deprecated multiplex: control + ops + chat only (no telemetry). Prefer /ws/control|/ws/ops|/ws/chat|/ws/telemetry."""
    import logging

    logging.getLogger("uvicorn.error").warning(
        "Deprecated /ws/events client connected — prefer explicit /ws/control, /ws/ops, /ws/chat, /ws/telemetry"
    )
    log_api("ws", "events_deprecated_connect")
    await bus.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        bus.disconnect(ws)


@router.post("/api/approvals/resolve")
async def resolve_approval(body: ApprovalResolution):
    t0 = asyncio.get_running_loop().time()
    log_api("approvals", "resolve_request", approval_id=body.id, resolution=body.resolution)
    aid = str(body.id).strip()
    pending_lookup = await _run_approval_io(_pending_as_dict)
    t_pending = asyncio.get_running_loop().time()
    apr = pending_lookup.get(aid)
    ok = await _resolve_queue(aid, body.resolution == "approved")
    t_resolve = asyncio.get_running_loop().time()
    if not ok:
        if aid.upper().startswith("APR-"):
            # Persist-equivalent dismiss is UI-only; notify after decision path returns.
            await channels.control.publish(
                "approval_resolution",
                {"id": aid, "resolution": body.resolution, "status": body.resolution},
            )
            log_api("approvals", "resolve_dismiss_ui", approval_id=aid, resolution=body.resolution)
            return {"ok": True, "id": aid, "resolution": body.resolution, "dismissed_only": True}
        log_error("approvals", "resolve_missing", approval_id=aid, resolution=body.resolution)
        log_api(
            "approvals",
            "resolve_timing",
            approval_id=aid,
            pending_ms=int((t_pending - t0) * 1000),
            resolve_ms=int((t_resolve - t_pending) * 1000),
            total_ms=int((asyncio.get_running_loop().time() - t0) * 1000),
            found=False,
        )
        return {"ok": False, "error": f"Approval '{aid}' not found in queue.", "id": aid, "resolution": body.resolution}

    # Durable state persisted above — notify control only after resolve returns ok.
    resolution_data = {
        "id": aid,
        "resolution": body.resolution,
        "status": body.resolution,
    }
    await channels.control.publish("approval_resolution", resolution_data)
    t_pub = asyncio.get_running_loop().time()

    if apr and str(apr.get("agent", "")) == "repo_index_coordinator":
        await get_coordinator().handle_approval_resolution(aid, body.resolution, apr)
        log_api("approvals", "resolve_result", approval_id=aid, resolution=body.resolution, executed=False, coordinator=True)
        return {"ok": True, "id": aid, "resolution": body.resolution}

    if body.resolution == "approved" and apr:
        _kickoff_approved_execution(aid, apr)
        log_api(
            "approvals",
            "resolve_result",
            approval_id=aid,
            resolution=body.resolution,
            executed=True,
            execute_queued=True,
            pending_ms=int((t_pending - t0) * 1000),
            resolve_ms=int((t_resolve - t_pending) * 1000),
            publish_ms=int((t_pub - t_resolve) * 1000),
            total_ms=int((asyncio.get_running_loop().time() - t0) * 1000),
        )
        return {
            "ok": True,
            "id": aid,
            "resolution": body.resolution,
            "executed": True,
            "execute_queued": True,
            "act_id": f"ACT-{aid}",
        }

    log_api(
        "approvals",
        "resolve_result",
        approval_id=aid,
        resolution=body.resolution,
        executed=False,
        pending_ms=int((t_pending - t0) * 1000),
        resolve_ms=int((t_resolve - t_pending) * 1000),
        publish_ms=int((t_pub - t_resolve) * 1000),
        total_ms=int((asyncio.get_running_loop().time() - t0) * 1000),
    )
    return {"ok": True, "id": aid, "resolution": body.resolution, "executed": False}


@router.get("/api/approvals")
async def list_approvals():
    pending_items = await run_in(APPROVAL_EXECUTOR, list_pending)
    approvals = []
    for apr_id, spec in pending_items:
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
        if spec.get("tool_name"):
            row["tool_name"] = spec["tool_name"]
        row["payload"] = brain_spec_match_payload(spec)
        # Mark execute-capable brain rows vs supervisor APR-* dismiss stubs (UI labeling).
        row["execute_path"] = bool(spec.get("tool_name")) and str(apr_id).startswith("approval-")
        approvals.append(row)
    approvals.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    log_api("approvals", "list", count=len(approvals))
    return approvals


def _pending_as_dict() -> dict:
    return dict(list_pending())


async def _run_approval_io(fn, /, *args):
    return await run_in(APPROVAL_EXECUTOR, fn, *args)


async def _resolve_queue(approval_id: str, approve: bool) -> bool:
    return await run_in(APPROVAL_EXECUTOR, resolve, approval_id, approve)


def _kickoff_approved_execution(approval_id: str, spec: dict) -> None:
    """Schedule approved tool run; failures are logged/published, never undo the decision."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log_error("approvals", "execute_no_loop", approval_id=approval_id)
        return
    loop.create_task(_run_approved_execution(approval_id, spec))


async def _run_approved_execution(approval_id: str, spec: dict) -> None:
    try:
        await _execute_approved(approval_id, spec)
    except Exception as exc:
        safe = str(exc)[:300]
        log_error("approvals", "execute_failed", approval_id=approval_id, error=safe)
        try:
            await channels.control.publish(
                "action",
                {
                    "id": f"ACT-{approval_id}",
                    "type": "action",
                    "agent": spec.get("agent", "orchestrator"),
                    "op": "exec",
                    "detail": f"Approved but execution failed: {safe}",
                    "status": "error",
                    "timestamp": spec.get("created_at"),
                },
            )
        except Exception as pub_exc:
            log_error(
                "approvals",
                "execute_fail_publish_failed",
                approval_id=approval_id,
                error=str(pub_exc)[:200],
            )


async def _execute_approved(approval_id: str, spec: dict):
    tool_name = spec.get("tool_name")
    args = spec.get("args", {})
    if tool_name:
        result = await run_in(
            EXEC_EXECUTOR,
            lambda: execution_run(
                tool_name,
                args,
                300,
                approval_context={"approved": True, "approval_id": approval_id, "source": "events.resolve_approval"},
            ),
        )
        status = "done" if result.success else "error"
        detail = (
            f"Approved run completed for `{tool_name}`."
            if result.success else
            f"Approved run failed for `{tool_name}`: {result.stderr or result.stdout or 'unknown error'}"
        )
        await channels.control.publish("action", {
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

    await channels.control.publish("action", {
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
