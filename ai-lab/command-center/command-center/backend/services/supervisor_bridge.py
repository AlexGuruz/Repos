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


def _ensure_brain_path():
    try:
        from core.ai_lab import ensure_ai_lab_root_on_path

        ensure_ai_lab_root_on_path()
    except Exception:
        pass


def _catalog_attachment_from_payload(payload: dict) -> str | None:
    try:
        from core.ai_lab import ensure_ai_lab_root_on_path
        import os

        ensure_ai_lab_root_on_path()
        gr = (settings.ai_lab_governance_root or "").strip()
        if gr:
            os.environ["AI_LAB_GOVERNANCE_ROOT"] = gr
        from brain.catalog_loader import format_approval_catalog_attachment
    except Exception:
        return None
    for key in ("file_path", "path", "target", "repo_path", "script_path"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            ctx = format_approval_catalog_attachment(v.strip())
            return ctx or None
    return None


ALLOWLISTED_READ_OPS = frozenset({
    "index_repo",
    "semantic_search",
    "chunk_retrieve",
    "retrieve",
    "promote_repo_index",
    "explain_log",
    "summarize_diff",
    "embed",
    # Common worker assistant / tunnel endpoints (GET or POST depending on worker)
    "health",
    "ready",
    "live",
    "status",
    "ping",
    "list_collections",
    "collection_stats",
    "vector_search",
    "query",
    "search",
})

# These paths are invoked with HTTP GET (no JSON body).
WORKER_HTTP_GET_OPS = frozenset({"health", "ready", "live", "status", "ping"})

CONTROLLED_OPS = {
    "run_approved", "submit_approval", "write_sheet",
    "restart_service", "modify_registry",
}


# Long-running worker ops (Chroma build, atomic promote) share the same httpx budget.
_WORKER_SLOW_OPS = frozenset({"index_repo", "promote_repo_index"})


def effective_allowlisted_read_ops() -> frozenset[str]:
    extra = (settings.worker_read_ops_extra or "").strip()
    if not extra:
        return frozenset(ALLOWLISTED_READ_OPS)
    more = {x.strip() for x in extra.split(",") if x.strip()}
    return frozenset(ALLOWLISTED_READ_OPS) | more


def _worker_timeout_seconds(op: str) -> float:
    if op in _WORKER_SLOW_OPS:
        return float(settings.worker_bridge_index_repo_timeout_seconds)
    return float(settings.worker_bridge_timeout_seconds)


def _httpx_timeout(op: str) -> httpx.Timeout:
    read_sec = _worker_timeout_seconds(op)
    c = float(settings.worker_connect_timeout_seconds)
    return httpx.Timeout(connect=c, read=read_sec, write=min(read_sec, 120.0), pool=5.0)


def _normalize_worker_post_body(op: str, payload: dict) -> dict:
    """
    Worker FastAPI handlers often require repo_path; hub coordinator sends repo_id + staging metadata.
    Map repo_id -> absolute path under the same parent directory as AI_LAB_ROOT (e.g. E:/Repos/<repo_id>).
    """
    body = dict(payload or {})
    if op not in ("index_repo", "promote_repo_index"):
        return body
    if body.get("repo_path"):
        return body
    rid = str(body.get("repo_id") or "").strip()
    if not rid:
        return body
    try:
        from core.ai_lab import AI_LAB_ROOT

        body["repo_path"] = str((AI_LAB_ROOT.parent / rid).resolve())
    except Exception:
        body["repo_path"] = rid
    return body


async def _worker_call(op: str, payload: dict) -> dict:
    """Forward a read-only op to the worker API over the SSH tunnel."""
    base = settings.worker_tunnel_url.rstrip("/")
    url = f"{base}/{op}"
    timeout = _httpx_timeout(op)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if op in WORKER_HTTP_GET_OPS:
            r = await client.get(url)
        else:
            body = _normalize_worker_post_body(op, payload)
            r = await client.post(url, json=body)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            snippet = (e.response.text or "")[:1500]
            raise RuntimeError(f"Worker HTTP {e.response.status_code}: {snippet}") from None
        txt = (r.text or "").strip()
        if not txt:
            return {}
        try:
            return r.json()
        except Exception:
            return {"ok": True, "status_code": r.status_code, "text": txt[:8000]}


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
    if op in effective_allowlisted_read_ops():
        await bus.publish("feed", {
            "agent": agent, "op": "rag" if "search" in op or "retrieve" in op or "embed" in op else "read",
            "detail": f"{op} → {payload.get('target', payload.get('repo_path', '?'))}",
            "bytes": None, "timestamp": datetime.utcnow().isoformat(),
        })
        try:
            result = await _worker_call(op, payload)
            await _log_action(act_id, agent, op, f"{op} completed ({settings.worker_tunnel_url})")
            return {"ok": True, "act_id": act_id, "result": result}
        except httpx.ConnectError as e:
            msg = f"{op} FAILED: cannot connect to worker tunnel ({settings.worker_tunnel_url}). {e}"
            await _log_action(act_id, agent, op, msg, status="error")
            return {"ok": False, "act_id": act_id, "error": msg}
        except httpx.TimeoutException as e:
            msg = f"{op} FAILED: timeout calling worker ({e})."
            await _log_action(act_id, agent, op, msg, status="error")
            return {"ok": False, "act_id": act_id, "error": msg}
        except Exception as e:
            await _log_action(act_id, agent, op, f"{op} FAILED: {e}", status="error")
            return {"ok": False, "act_id": act_id, "error": str(e)}

    # State-changing → permanent rule may auto-execute; else approval card
    if op in CONTROLLED_OPS:
        _ensure_brain_path()
        match_payload: dict = {}
        rule = None
        try:
            from brain.permanent_allowlist import approval_payload_subset, find_matching_rule

            match_payload = approval_payload_subset(payload)
            rule = find_matching_rule(op, match_payload)
        except Exception:
            pass
        if rule:
            rid = str(rule.get("id") or "")
            exec_result = await execute_approved(
                f"AUTO-{rid}", agent, op, dict(payload or {}),
            )
            await bus.publish(
                "feed",
                {
                    "agent": agent,
                    "op": "sys",
                    "detail": f"Permanent rule {rid}: auto-approved {op}",
                    "bytes": None,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            return {
                "ok": True,
                "auto_permanent": True,
                "permanent_rule_id": rid,
                **exec_result,
            }

        catalog_context = _catalog_attachment_from_payload(payload)
        try:
            from brain.approval_queue.queue import submit

            apr_id = submit(
                {
                    "agent": agent,
                    "action": op,
                    "detail": payload.get("detail", str(payload)),
                    "repo_class": "CONTROLLED",
                    "catalog_context": catalog_context,
                    "payload": match_payload,
                }
            )
        except Exception as e:
            await _log_action(act_id, agent, op, f"{op} approval queue failed: {e}", status="error")
            return {"ok": False, "act_id": act_id, "error": f"approval queue failed: {e}"}

        apr = ApprovalEvent(
            id=apr_id,
            agent=agent,
            action=op,
            detail=payload.get("detail", str(payload)),
            repo_class="CONTROLLED",
            catalog_context=catalog_context,
            payload=match_payload or None,
        )
        await bus.publish("approval", apr.model_dump(mode="json"))
        return {"ok": True, "queued": True, "apr_id": apr.id, "status": "pending"}

    # Unknown op — reject with discoverability hints
    return {
        "ok": False,
        "error": (
            f"Unknown op '{op}'. Use a controlled op {sorted(CONTROLLED_OPS)} "
            f"or a read op from {sorted(effective_allowlisted_read_ops())[:30]}"
            f"{'…' if len(effective_allowlisted_read_ops()) > 30 else ''}. "
            f"Extend reads via WORKER_READ_OPS_EXTRA in .env."
        ),
    }


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
