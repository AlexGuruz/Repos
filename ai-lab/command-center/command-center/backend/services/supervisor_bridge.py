"""
supervisor_bridge.py — the ONLY path from the command center to
state-changing lab actions.

Flow for every intent from the UI:
    1. Check repo_class via registry
    2. If CONTROLLED → submit_approval (returns APR-ID, no execution)
    3. If ALLOWLISTED read-only → forward to worker API tunnel
    4. If approved exec → call run_approved wrapper

No direct shell execution. No file writes. All wrappers only.
"""
import uuid
import httpx
from datetime import datetime
from typing import Literal
from core.config import settings
from core.models import ApprovalEvent, ActionEvent
from services.feed_bus import bus


ALLOWLISTED_READ_OPS = {
    "index_repo", "semantic_search", "chunk_retrieve",
    "retrieve",
    "promote_repo_index",
    "explain_log", "summarize_diff", "embed",
}

CONTROLLED_OPS = {
    "run_approved", "submit_approval", "write_sheet",
    "restart_service", "modify_registry",
}


# Long-running worker ops (Chroma build, atomic promote) share the same httpx budget.
_WORKER_SLOW_OPS = frozenset({"index_repo", "promote_repo_index"})


def _worker_timeout_seconds(op: str) -> float:
    if op in _WORKER_SLOW_OPS:
        return float(settings.worker_bridge_index_repo_timeout_seconds)
    return float(settings.worker_bridge_timeout_seconds)


async def _worker_call(op: str, payload: dict) -> dict:
    """Forward a read-only op to the worker API over the SSH tunnel."""
    url = f"{settings.worker_tunnel_url}/{op}"
    timeout = _worker_timeout_seconds(op)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def fetch_worker_repo_status(repo_id: str) -> dict | None:
    """
    Best-effort GET /repo_status?repo_id=... (worker contract).
    Returns None if tunnel is down or worker returns error.
    """
    rid = (repo_id or "").strip()
    if not rid:
        return None
    base = settings.worker_tunnel_url.rstrip("/")
    url = f"{base}/repo_status"
    try:
        async with httpx.AsyncClient(timeout=float(settings.worker_bridge_timeout_seconds)) as client:
            r = await client.get(url, params={"repo_id": rid})
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _log_action(action_id: str, agent: str, op: str, detail: str, status: str = "done"):
    ev = ActionEvent(
        id=action_id, agent=agent, op="exec",
        detail=detail, status=status,  # type: ignore
    )
    await bus.publish("action", ev.model_dump())


async def route_intent(agent: str, op: str, payload: dict) -> dict:
    """
    Main entry point called by the chat router when the user triggers
    a task. Returns a dict the chat router sends back to the UI.
    """
    act_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"

    # Read-only → forward to worker
    if op in ALLOWLISTED_READ_OPS:
        await bus.publish("feed", {
            "agent": agent, "op": "rag" if "search" in op or "retrieve" in op or "embed" in op else "read",
            "detail": f"{op} → {payload.get('target', '?')}",
            "bytes": None, "timestamp": datetime.utcnow().isoformat(),
        })
        try:
            result = await _worker_call(op, payload)
            await _log_action(act_id, agent, op, f"{op} completed on {payload.get('target','?')}")
            return {"ok": True, "act_id": act_id, "result": result}
        except Exception as e:
            await _log_action(act_id, agent, op, f"{op} FAILED: {e}", status="error")
            return {"ok": False, "act_id": act_id, "error": str(e)}

    # State-changing → create approval, never execute directly
    if op in CONTROLLED_OPS:
        apr = ApprovalEvent(
            agent=agent, action=op,
            detail=payload.get("detail", str(payload)),
            repo_class="CONTROLLED",
        )
        await bus.publish("approval", apr.model_dump())
        return {"ok": True, "queued": True, "apr_id": apr.id, "status": "pending"}

    # Unknown op — reject
    return {"ok": False, "error": f"Unknown op '{op}'. Not in allowlist or controlled set."}


async def execute_approved(apr_id: str, agent: str, action: str, payload: dict) -> dict:
    """
    Called after a human approves an APR. Executes via run_approved wrapper only.
    This is the ONLY place execution happens — never from route_intent directly.
    """
    act_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"
    await bus.publish("feed", {
        "agent": agent, "op": "exec",
        "detail": f"run_approved → {action} (APR: {apr_id})",
        "timestamp": datetime.utcnow().isoformat(),
    })
    # In production: call your actual run_approved wrapper here
    # e.g. subprocess via wrapper script, never direct shell
    await _log_action(act_id, agent, action, f"run_approved: {action} (APR: {apr_id})")
    return {"ok": True, "act_id": act_id, "apr_id": apr_id}
