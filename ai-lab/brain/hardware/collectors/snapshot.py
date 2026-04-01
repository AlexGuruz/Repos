"""
Single hardware snapshot combining CPU, GPU, RAM (Guru §25).
"""
from __future__ import annotations

from datetime import datetime, timezone

from brain.hardware.schemas.hardware_metrics import HardwareSnapshot, CPUMetrics, GPUMetrics
from brain.hardware.collectors.cpu_monitor import get_cpu_metrics
from brain.hardware.collectors.gpu_monitor import get_gpu_metrics

try:
    import psutil
except ImportError:
    psutil = None


def get_snapshot(node: str = "local") -> HardwareSnapshot:
    """
    Collect full hardware snapshot for assistant and Compute panel.
    Returns normalized §25 schema; safe to call from backend or orchestrator.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cpu = get_cpu_metrics()
    gpu = get_gpu_metrics()

    ram_used_gb = 0.0
    ram_total_gb = 0.0
    if psutil:
        try:
            v = psutil.virtual_memory()
            ram_used_gb = round(v.used / 1e9, 1)
            ram_total_gb = round(v.total / 1e9, 1)
        except Exception:
            pass

    return HardwareSnapshot(
        timestamp=ts,
        node=node,
        cpu=cpu,
        gpu=gpu,
        ram_used_gb=ram_used_gb,
        ram_total_gb=ram_total_gb,
    )
