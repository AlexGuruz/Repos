"""
Threshold alerts (Guru §25). Detect high temp/util and return alert messages.
"""
from __future__ import annotations

from brain.hardware.schemas.hardware_metrics import HardwareSnapshot


def check_thresholds(snapshot: HardwareSnapshot) -> list[str]:
    """
    Check snapshot against simple thresholds. Returns list of alert messages.
    Example: GPU temp > 85°C, CPU > 95%, VRAM > 90%.
    """
    alerts: list[str] = []
    if snapshot.cpu.total_usage_percent >= 95:
        alerts.append("CPU usage very high (≥95%).")
    elif snapshot.cpu.total_usage_percent >= 85:
        alerts.append("CPU usage high (≥85%).")
    if snapshot.gpu:
        if snapshot.gpu.temp_c is not None and snapshot.gpu.temp_c >= 85:
            alerts.append("GPU temperature high (≥85°C).")
        if snapshot.gpu.used_percent >= 95:
            alerts.append("GPU VRAM nearly full (≥95%).")
        elif snapshot.gpu.used_percent >= 90:
            alerts.append("GPU VRAM usage high (≥90%).")
    return alerts
