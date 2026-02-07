from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


@dataclass
class RunResult:
    instance_id: str
    years: str
    exit_code: int
    wall_ms: int
    heartbeat: Dict[str, Any]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _p95(values: List[int]) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    # nearest-rank p95
    k = int(round(0.95 * (len(s) - 1)))
    return int(s[min(max(k, 0), len(s) - 1)])

def _run_one(instance_id: str, years: str) -> RunResult:
    env = dict(os.environ)
    env["KYLO_CONFIG_PATH"] = env.get("KYLO_CONFIG_PATH") or os.path.join("config", "global.yaml")
    env["KYLO_INSTANCE_ID"] = instance_id
    env["KYLO_ACTIVE_YEARS"] = years
    env["KYLO_READ_ONLY"] = "1"
    env["KYLO_SHEETS_DRY_RUN"] = "1"
    env["KYLO_WATCH_INTERVAL_SECS"] = "1"
    env["KYLO_WATCH_JITTER_SECS"] = "0"

    cmd = [sys.executable, "-u", "-m", "kylo.watcher_runtime", "--instance-id", instance_id, "--years", years, "--once"]
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, cwd=str(Path(__file__).resolve().parent.parent))
    t1 = time.time()

    hb_path = Path(".kylo") / "instances" / instance_id / "health" / "heartbeat.json"
    hb = _read_json(hb_path)
    return RunResult(
        instance_id=instance_id,
        years=years,
        exit_code=int(proc.returncode),
        wall_ms=int(round((t1 - t0) * 1000)),
        heartbeat=hb,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark multiple Kylo watchers (dry-run)")
    ap.add_argument("--ticks", type=int, default=10, help="How many one-shot ticks to run per instance")
    args = ap.parse_args()

    ticks = max(1, int(args.ticks))

    cases = [
        ("JGD_2025", "2025"),
        ("JGD_2026", "2026"),
    ]

    per_instance_tick_ms: Dict[str, List[int]] = {iid: [] for iid, _ in cases}
    per_instance_exit: Dict[str, List[int]] = {iid: [] for iid, _ in cases}
    per_instance_last: Dict[str, Dict[str, Any]] = {iid: {} for iid, _ in cases}

    overall_start = time.time()
    for _i in range(ticks):
        procs: List[subprocess.Popen] = []
        meta: List[Dict[str, str]] = []
        for iid, years in cases:
            env = dict(os.environ)
            env["KYLO_CONFIG_PATH"] = env.get("KYLO_CONFIG_PATH") or os.path.join("config", "global.yaml")
            env["KYLO_INSTANCE_ID"] = iid
            env["KYLO_ACTIVE_YEARS"] = years
            env["KYLO_READ_ONLY"] = "1"
            env["KYLO_SHEETS_DRY_RUN"] = "1"
            env["KYLO_WATCH_INTERVAL_SECS"] = "1"
            env["KYLO_WATCH_JITTER_SECS"] = "0"
            cmd = [sys.executable, "-u", "-m", "kylo.watcher_runtime", "--instance-id", iid, "--years", years, "--once"]
            meta.append({"instance_id": iid, "years": years})
            procs.append(subprocess.Popen(cmd, env=env))

        exit_codes = [p.wait() for p in procs]
        for (m, code) in zip(meta, exit_codes):
            iid = m["instance_id"]
            per_instance_exit[iid].append(int(code))
            hb_path = Path(".kylo") / "instances" / iid / "health" / "heartbeat.json"
            hb = _read_json(hb_path)
            per_instance_last[iid] = hb
            try:
                ms = hb.get("last_tick_duration_ms")
                if ms is not None:
                    per_instance_tick_ms[iid].append(int(ms))
            except Exception:
                pass

    overall_end = time.time()
    wall_ms_total_parallel = int(round((overall_end - overall_start) * 1000))

    results: List[Dict[str, Any]] = []
    for iid, years in cases:
        series = per_instance_tick_ms.get(iid, [])
        avg = (sum(series) / len(series)) if series else None
        results.append(
            {
                "instance_id": iid,
                "years": years,
                "ticks": ticks,
                "wall_ms_total_parallel": wall_ms_total_parallel,
                "tick_ms_series": series,
                "tick_ms_avg": (round(avg, 2) if avg is not None else None),
                "tick_ms_p95": _p95(series),
                "exit_codes": per_instance_exit.get(iid, []),
                "change_detected": per_instance_last.get(iid, {}).get("change_detected"),
                "posting_attempted": per_instance_last.get(iid, {}).get("posting_attempted"),
                "posting_skipped_reason": per_instance_last.get(iid, {}).get("posting_skipped_reason"),
                "last_error": per_instance_last.get(iid, {}).get("last_error"),
            }
        )

    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

