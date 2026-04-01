"""
Hardware telemetry logger (Guru §25). Writes snapshots for trend/debug; optional.
"""
from __future__ import annotations

import json
from pathlib import Path

from brain.hardware.schemas.hardware_metrics import HardwareSnapshot


def log_snapshot(snapshot: HardwareSnapshot, log_dir: str | Path | None = None) -> None:
    """
    Append a compact snapshot to hardware log. No-op if log_dir not set or write fails.
    Fields: timestamp, node, cpu total %, gpu util %, vram used/free, alerts.
    """
    if log_dir is None:
        return
    try:
        path = Path(log_dir) / "hardware"
        path.mkdir(parents=True, exist_ok=True)
        # One file per day for easier rotation
        from datetime import datetime, timezone
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fpath = path / f"snapshots_{day}.jsonl"
        entry = snapshot.to_dict()
        # Trim process lists for log size
        if "cpu" in entry and "process_top" in entry["cpu"]:
            entry["cpu"]["process_top"] = entry["cpu"]["process_top"][:5]
        if entry.get("gpu") and "process_top" in entry["gpu"]:
            entry["gpu"]["process_top"] = entry["gpu"]["process_top"][:3]
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
