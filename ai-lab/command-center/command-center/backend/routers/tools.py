"""Tool registry + worker bridge ops for Tools panel and diagnostics."""
import json
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.ai_lab import AI_LAB_ROOT, ensure_ai_lab_root_on_path
from core.config import settings
from services.supervisor_bridge import (
    COORDINATOR_ONLY_WORKER_OPS,
    CONTROLLED_OPS,
    WORKER_HTTP_GET_OPS,
    effective_allowlisted_read_ops,
    route_intent,
)

router = APIRouter()


def _registry_tools() -> list[dict]:
    p = AI_LAB_ROOT / "registry" / "scripts.json"
    if not p.is_file():
        return []
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for e in data:
        if isinstance(e, dict) and e.get("tool_name"):
            out.append(
                {
                    "tool_name": e.get("tool_name"),
                    "path": e.get("path"),
                    "repo": e.get("repo"),
                    "description": e.get("description") or "",
                }
            )
    return out


@router.get("/api/tools/stats")
async def tools_stats():
    """Registered scripts + worker tunnel ops the supervisor can route (read vs controlled)."""
    ensure_ai_lab_root_on_path()
    reads = sorted(effective_allowlisted_read_ops())
    reg = _registry_tools()
    tool_calls = [
        {
            "tool": row["tool_name"],
            "orch": 0,
            "worker": 1,
            "rag": 0,
            "sup": 0,
        }
        for row in reg
    ]
    data_movement = [
        {
            "op": "read (worker tunnel)",
            "cls": "op-read",
            "vol": f"{len(reads)} ops",
            "pct": min(100, 20 + len(reads) * 2),
            "calls": len(reads),
        },
        {
            "op": "controlled (approval)",
            "cls": "op-write",
            "vol": f"{len(CONTROLLED_OPS)} ops",
            "pct": min(100, 15 + len(CONTROLLED_OPS) * 3),
            "calls": len(CONTROLLED_OPS),
        },
    ]
    return {
        "toolCalls": tool_calls,
        "dataMovement": data_movement,
        "registeredTools": reg,
        "workerReadOps": reads,
        "workerHttpGetOps": sorted(WORKER_HTTP_GET_OPS),
        "controlledOps": sorted(CONTROLLED_OPS),
        "registryPath": str(AI_LAB_ROOT / "registry" / "scripts.json"),
        "registryCount": len(reg),
        "workerTunnelUrl": settings.worker_tunnel_url,
        "note": "Ensure WORKER_TUNNEL_URL reaches the worker API. Add ops via WORKER_READ_OPS_EXTRA in .env.",
    }


class ToolInvokeBody(BaseModel):
    op: str = Field(..., min_length=1)
    agent: str = "command-center"
    payload: dict = Field(default_factory=dict)


@router.post("/api/tools/invoke")
async def tools_invoke(body: ToolInvokeBody):
    """
    Invoke a supervisor-routed op (read → worker tunnel, controlled → approval event).
    Use for diagnostics and Guru-style automations; not a substitute for governance on writes.
    """
    op = body.op.strip()
    if not op:
        raise HTTPException(status_code=400, detail="op required")
    if op in COORDINATOR_ONLY_WORKER_OPS:
        raise HTTPException(
            status_code=403,
            detail=f"{op} is restricted to the repo index coordinator.",
        )
    return await route_intent(body.agent.strip() or "command-center", op, dict(body.payload or {}))


@router.get("/api/tools/worker-reachable")
async def tools_worker_reachable():
    """Quick probe: can we open a TCP connection to the configured tunnel base."""
    base = settings.worker_tunnel_url.rstrip("/")
    timeout = httpx.Timeout(
        connect=float(settings.worker_connect_timeout_seconds),
        read=8.0,
        write=8.0,
        pool=5.0,
    )
    last_err = None
    for suffix in ("/health", "/ping", "/ready"):
        url = f"{base}{suffix}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(url)
                if r.status_code < 500:
                    return {
                        "ok": True,
                        "url": url,
                        "status_code": r.status_code,
                        "worker_tunnel_url": settings.worker_tunnel_url,
                    }
        except Exception as e:
            last_err = str(e)
    return {
        "ok": False,
        "worker_tunnel_url": settings.worker_tunnel_url,
        "error": last_err or "unreachable",
    }
