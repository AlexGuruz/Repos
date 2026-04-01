"""
Process priority control (Guru §25). Approval-gated; uses psutil.
"""
from __future__ import annotations

import sys

try:
    import psutil
except ImportError:
    psutil = None


def set_process_priority(pid: int, nice: int) -> dict[str, str | bool]:
    """
    Set process priority. Unix: nice in [-20, 19] (higher = lower priority).
    Windows: maps to BELOW_NORMAL / NORMAL / ABOVE_NORMAL. Requires approval before use.
    Returns: {"ok": bool, "error": str}
    """
    if not psutil:
        return {"ok": False, "error": "psutil not installed."}
    if pid <= 0:
        return {"ok": False, "error": "Invalid pid."}
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"ok": False, "error": f"Process {pid} not found."}
    except psutil.AccessDenied:
        return {"ok": False, "error": f"Access denied to process {pid} (run with sufficient privileges)."}
    try:
        if sys.platform == "win32":
            if nice > 5:
                proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            elif nice < -5:
                proc.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            else:
                proc.nice(psutil.NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(nice)
        return {"ok": True, "error": ""}
    except (ValueError, PermissionError, OSError) as e:
        return {"ok": False, "error": str(e)}
