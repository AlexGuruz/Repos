#!/usr/bin/env python3
"""
Sync runner: periodically applies Kylo_Config rules and refreshes layout maps.
Runs:
  1) sync_bank.py (Kylo_Config -> CLEAN TRANSACTIONS)
  2) dynamic_columns_jgdtruth.py (layout map)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


def _parse_years(value: str | None) -> List[str]:
    if not value:
        return []
    raw = value.replace(";", ",")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _load_enabled_years(repo_root: Path) -> List[str]:
    if yaml is None:
        return []
    idx_path = repo_root / "config" / "instances" / "index.yaml"
    if not idx_path.exists():
        return []
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return []
    items = data.get("instances") or []
    years: List[str] = []
    for it in items:
        if isinstance(it, dict) and it.get("enabled", True):
            raw_years = str(it.get("years", "")).strip()
            for part in raw_years.replace(";", ",").split(","):
                y = part.strip()
                if y:
                    years.append(y)
    return sorted(set(years))


def _run_script(script_path: Path, args: List[str], repo_root: Path, log_handle) -> int:
    env = os.environ.copy()
    # Ensure repo root + tools path are importable
    pythonpath = env.get("PYTHONPATH", "")
    extra = os.pathsep.join([str(repo_root), str(script_path.parent)])
    env["PYTHONPATH"] = extra + (os.pathsep + pythonpath if pythonpath else "")

    cmd = [sys.executable, str(script_path)] + args
    log_handle.write(f"\n[{datetime.now().isoformat()}] Running: {' '.join(cmd)}\n")
    log_handle.flush()
    return subprocess.call(cmd, cwd=str(repo_root), env=env, stdout=log_handle, stderr=log_handle)


def run_once(repo_root: Path, years: List[str], cfg_path: Path, log_handle) -> int:
    year_arg = ",".join(years) if years else ""
    sync_bank = repo_root / "tools" / "scripthub_legacy" / "sync_bank.py"
    mapper = repo_root / "tools" / "scripthub_legacy" / "dynamic_columns_jgdtruth.py"

    args_sync = ["--config", str(cfg_path)]
    args_mapper = []
    if year_arg:
        args_sync.extend(["--years", year_arg])
        args_mapper.extend(["--years", year_arg])

    rc1 = _run_script(sync_bank, args_sync, repo_root, log_handle)
    rc2 = _run_script(mapper, args_mapper, repo_root, log_handle)
    return 0 if rc1 == 0 and rc2 == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Kylo Sync Runner")
    parser.add_argument("--interval", type=int, default=None, help="Loop interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--years", default=None, help="Comma-separated years to target")
    parser.add_argument("--config", default=None, help="Path to sync_bank config.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    cfg_path = Path(args.config) if args.config else repo_root / "tools" / "scripthub_legacy" / "config.json"

    years = _parse_years(args.years) or _parse_years(os.environ.get("KYLO_ACTIVE_YEARS"))
    if not years:
        years = _load_enabled_years(repo_root)

    interval = args.interval or int(os.environ.get("KYLO_SYNC_INTERVAL_SECS", "300"))
    log_dir = repo_root / ".kylo" / "sync"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "sync_runner.log"

    with open(log_path, "a", encoding="utf-8") as log_handle:
        log_handle.write(f"\n=== Sync runner start {datetime.now().isoformat()} ===\n")
        log_handle.write(f"Years: {', '.join(years) if years else 'default'}\n")
        log_handle.write(f"Interval: {interval}s\n")
        log_handle.flush()

        if args.once:
            return run_once(repo_root, years, cfg_path, log_handle)

        while True:
            run_once(repo_root, years, cfg_path, log_handle)
            log_handle.flush()
            time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
