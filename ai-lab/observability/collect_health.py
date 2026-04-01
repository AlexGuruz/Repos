"""
Health collector: runs with sufficient privileges, writes observability/health.json.
Agents only read this file; they do not write it.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def _disk_free_gb() -> float | None:
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic", "logicaldisk", "get", "FreeSpace", "/value"],
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                if "FreeSpace" in line:
                    val = line.split("=", 1)[-1].strip()
                    return int(val) / (1024**3)
        else:
            stat = os.statvfs("/")
            return (stat.f_bavail * stat.f_frsize) / (1024**3)
    except Exception:
        return None
    return None


def _ssh_reachable(host: str = "worker", timeout_sec: int = 5) -> bool | None:
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=" + str(timeout_sec), "-o", "BatchMode=yes", host, "echo ok"],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2,
        )
        return r.returncode == 0 and "ok" in (r.stdout or "")
    except Exception:
        return None


def main() -> None:
    root = Path(__file__).resolve().parent
    health = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "disk_free_gb": _disk_free_gb(),
        "ssh_reachable": _ssh_reachable() if os.environ.get("AI_LAB_HEALTH_CHECK_SSH") else None,
        "platform": platform.system(),
    }
    out_path = root / "health.json"
    with open(out_path, "w") as f:
        json.dump(health, f, indent=2)
    print("Wrote", out_path, file=sys.stderr)


if __name__ == "__main__":
    main()
