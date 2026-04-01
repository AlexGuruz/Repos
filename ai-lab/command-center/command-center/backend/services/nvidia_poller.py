"""
nvidia_poller.py — polls hardware every N seconds and publishes snapshots.

As of Guru §25 (Phase 3.2 Hardware Observability), prefer brain.hardware
for normalized CPU/GPU/process attribution, but keep the legacy payload
shape so the existing frontend continues to work.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.ai_lab import AI_LAB_ROOT, ensure_ai_lab_root_on_path
from core.config import settings
from services.feed_bus import bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fallback_snapshot() -> dict:
    """Fallback snapshot if brain.hardware is unavailable."""
    try:
        import psutil
        ram = psutil.virtual_memory()
        # First interval=None call is 0.0; use a short blocking sample.
        cpu_percent = round(float(psutil.cpu_percent(interval=0.08)), 1)
        return {
            "gpu": None,
            "cpu_percent": cpu_percent,
            "ram_used_gb": round(ram.used / 1e9, 1),
            "ram_total_gb": round(ram.total / 1e9, 1),
            "timestamp": _now(),
        }
    except Exception:
        return {"gpu": None, "cpu_percent": 0.0, "ram_used_gb": 0.0, "ram_total_gb": 0.0, "timestamp": _now()}


def _hardware_snapshot_and_alerts() -> tuple[dict, list[str]]:
    """
    Return (payload, alerts). Payload must contain legacy keys:
    gpu, cpu_percent, ram_used_gb, ram_total_gb, timestamp.
    """
    try:
        ensure_ai_lab_root_on_path()
        from brain.hardware import get_snapshot
        from brain.hardware.telemetry import check_thresholds, log_snapshot

        snap = get_snapshot()
        alerts = check_thresholds(snap)

        # Telemetry logging: write under ai-lab/logs/hardware/...
        try:
            log_snapshot(snap, log_dir=AI_LAB_ROOT / "logs")
        except Exception:
            pass

        d = snap.to_dict()
        payload = {
            # Legacy for ComputePanel/store
            "gpu": d.get("gpu_legacy"),
            "cpu_percent": d.get("cpu_percent"),
            "ram_used_gb": d.get("ram_used_gb"),
            "ram_total_gb": d.get("ram_total_gb"),
            "timestamp": d.get("timestamp") or _now(),
            # Extended normalized data (optional UI use)
            "cpu": d.get("cpu"),
            "node": d.get("node"),
        }
        return payload, alerts
    except Exception:
        return _fallback_snapshot(), []


async def nvidia_poll_loop():
    """Background task — runs forever, publishes hardware snapshots."""
    interval = settings.nvidia_smi_poll_interval
    while True:
        payload, alerts = _hardware_snapshot_and_alerts()
        await bus.publish("hardware", payload)
        if alerts:
            await bus.publish("hardware_alert", {"alerts": alerts, "snapshot": payload, "timestamp": payload.get("timestamp")})
        await asyncio.sleep(interval)
