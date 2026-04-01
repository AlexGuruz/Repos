"""
CPU affinity control (Guru §25). Approval-gated; uses psutil.
"""
from __future__ import annotations

try:
    import psutil
except ImportError:
    psutil = None


def set_cpu_affinity(pid: int, cores: list[int]) -> dict[str, str | bool]:
    """
    Set process CPU affinity so it runs only on the given core indices.
    Requires approval before use. Returns: {"ok": bool, "error": str}
    """
    if not psutil:
        return {"ok": False, "error": "psutil not installed."}
    if pid <= 0:
        return {"ok": False, "error": "Invalid pid."}
    if not cores:
        return {"ok": False, "error": "At least one core index required."}
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"ok": False, "error": f"Process {pid} not found."}
    except psutil.AccessDenied:
        return {"ok": False, "error": f"Access denied to process {pid} (run with sufficient privileges)."}
    try:
        proc.cpu_affinity(cores)
        return {"ok": True, "error": ""}
    except (ValueError, AttributeError, OSError) as e:
        return {"ok": False, "error": str(e)}
