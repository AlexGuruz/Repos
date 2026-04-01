"""
Process attribution (Guru §25). Top CPU/GPU consumers for assistant reasoning.
"""
from __future__ import annotations

from brain.hardware.collectors.cpu_monitor import _top_cpu_processes
from brain.hardware.collectors.gpu_monitor import _gpu_processes
from brain.hardware.schemas.hardware_metrics import ProcessInfo


def get_top_cpu_processes(limit: int = 8) -> list[ProcessInfo]:
    """Top processes by CPU usage."""
    return _top_cpu_processes(limit=limit)


def get_top_gpu_processes(limit: int = 5) -> list[ProcessInfo]:
    """Processes using GPU memory (from nvidia-smi)."""
    return _gpu_processes()[:limit]
