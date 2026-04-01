from fastapi import APIRouter
from services.observability import log_api, log_error

router = APIRouter()


def _get_snapshot():
    """Use brain.hardware (Guru §25) for normalized snapshot when ai-lab is on path."""
    try:
        from core.ai_lab import ensure_ai_lab_root_on_path
        ensure_ai_lab_root_on_path()
        from brain.hardware import get_snapshot
        return get_snapshot()
    except Exception as exc:
        log_error("hardware", "brain_snapshot_failed", error=str(exc))
        return None


@router.get("/api/hardware/snapshot")
async def hardware_snapshot():
    """One-shot hardware snapshot for initial page load (before WS connects). Uses brain.hardware when available."""
    snapshot = _get_snapshot()
    if snapshot is not None:
        d = snapshot.to_dict()
        log_api("hardware", "snapshot", gpu_present=bool(d.get("gpu_legacy") or d.get("gpu")), cpu_percent=d.get("cpu_percent"))
        return {
            "gpu": d.get("gpu_legacy"),
            "cpu_percent": d.get("cpu_percent"),
            "ram_used_gb": d.get("ram_used_gb"),
            "ram_total_gb": d.get("ram_total_gb"),
            "timestamp": d.get("timestamp"),
            "cpu": d.get("cpu"),
            "node": d.get("node"),
        }
    # Fallback: reuse the same snapshot logic as the polling loop.
    # The previous implementation referenced legacy helper functions
    # that are no longer present in `services/nvidia_poller.py`.
    from services.nvidia_poller import _hardware_snapshot_and_alerts

    payload, _alerts = _hardware_snapshot_and_alerts()
    log_api(
        "hardware",
        "snapshot_fallback",
        gpu_present=bool(payload.get("gpu")),
        cpu_percent=payload.get("cpu_percent"),
    )
    return payload
