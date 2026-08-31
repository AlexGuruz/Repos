"""
Worker service health API (Guru §26). GET /api/workers/health and /api/workers/health/{worker_name}.
Includes tunnel_status, last_checked, and per-service latency for frontend visibility.

_sync health checks use urllib with multi-second timeouts each; they MUST run in a thread pool so
they do not block the asyncio event loop (otherwise WS/chat and other requests can stall, and
clients may see "connection closed" especially under uvicorn --reload).
"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


def _get_worker_health(worker_name: str = "worker-rig-01"):
    try:
        from core.ai_lab import ensure_ai_lab_root_on_path
        ensure_ai_lab_root_on_path()
        from brain.worker_health import get_worker_health_snapshot, worker_health_snapshot_to_dict
        snap = get_worker_health_snapshot(worker_name, timeout_budget_ms=5000, interactive=True)
        data = worker_health_snapshot_to_dict(snap)
        data["last_checked"] = snap.checked_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return data
    except Exception:
        return None


def _fallback(worker_name: str, error: str = "brain.worker_health not available"):
    return {
        "worker_name": worker_name,
        "ssh_configured": False,
        "all_ok": False,
        "services": [],
        "tunnel_status": {"worker_name": worker_name, "likely_up": False, "detail": error},
        "last_checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": error,
    }


@router.get("/api/workers/health")
async def workers_health():
    """Worker health for default worker (worker-rig-01). Includes tunnel_status and last_checked."""
    data = await asyncio.to_thread(_get_worker_health, "worker-rig-01")
    if data is not None:
        return data
    return _fallback("worker-rig-01")


@router.get("/api/workers/health/{worker_name}")
async def worker_health_by_name(worker_name: str):
    """Worker health for named worker. Includes tunnel_status and last_checked."""
    data = await asyncio.to_thread(_get_worker_health, worker_name)
    if data is not None:
        return data
    return _fallback(worker_name)
