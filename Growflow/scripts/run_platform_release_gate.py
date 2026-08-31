#!/usr/bin/env python3
"""
Platform release gate — retail reconcile + freshness/fixture checks + optional domains.

  PYTHONPATH=. python scripts/run_platform_release_gate.py --skip-build
  PYTHONPATH=. python scripts/run_platform_release_gate.py --preset last_30_days --compare

Exit codes:
  0 pass
  1 fail (freshness/fixture/reconcile/domain)
  2 invalid inputs
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.platform_config import load_platform_config  # noqa: E402
from lib.platform_status import (  # noqa: E402
    is_fixture_dashboard,
    read_json,
    write_platform_status,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Growflow platform release gate")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--preset", default="last_30_days")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--allow-fixture", action="store_true", help="Do not fail on fixture-scale retail JSON")
    ap.add_argument("--require-projection", action="store_true")
    ap.add_argument("--require-capital", action="store_true", default=True)
    ap.add_argument("--no-require-capital", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_platform_config()
    require_capital = args.require_capital and not args.no_require_capital

    if not args.skip_build:
        cmd = [
            sys.executable,
            str(REPO / "scripts" / "run_retail_release_gate.py"),
            "--preset",
            args.preset,
        ]
        if args.compare:
            cmd.append("--compare")
        print(">>", " ".join(cmd), flush=True)
        code = subprocess.call(cmd, cwd=str(REPO))
        if code != 0:
            return code
    else:
        # still run reconcile-only if dashboard exists
        if cfg.retail_dashboard_json.is_file():
            cmd = [
                sys.executable,
                str(REPO / "scripts" / "run_retail_release_gate.py"),
                "--skip-build",
                "--dashboard-json",
                str(cfg.retail_dashboard_json),
            ]
            print(">>", " ".join(cmd), flush=True)
            code = subprocess.call(cmd, cwd=str(REPO))
            if code != 0:
                return code

    dash = read_json(cfg.retail_dashboard_json)
    if not dash:
        print("platform gate: retail dashboard missing", file=sys.stderr)
        return 2
    meta = dash.get("meta") if isinstance(dash.get("meta"), dict) else {}
    if is_fixture_dashboard(meta, cfg=cfg) and not args.allow_fixture:
        print("platform gate: FAIL fixture_suspected on retail dashboard", file=sys.stderr)
        return 1

    if require_capital and not cfg.capital_json.is_file():
        print("platform gate: FAIL capital JSON missing", file=sys.stderr)
        return 1
    if require_capital:
        cap = read_json(cfg.capital_json) or {}
        cap_meta = cap.get("meta") if isinstance(cap.get("meta"), dict) else {}
        if not cap_meta.get("source_exists", True):
            print("platform gate: FAIL capital source_exists=false", file=sys.stderr)
            return 1

    if not cfg.consignment_json.is_file() and not (cfg.data_dir / "consignment_state.json").is_file():
        print("platform gate: FAIL consignment artifacts missing", file=sys.stderr)
        return 1

    if args.require_projection and not cfg.sales_projection_json.is_file():
        print("platform gate: FAIL projection JSON missing", file=sys.stderr)
        return 1

    status = write_platform_status(cfg=cfg)
    print(json.dumps({"platform_gate": "PASS", "overall_ok": status.get("overall_ok"), "breaches": status.get("slo_breaches")}))
    # SLO breaches warn but do not fail gate after artifact presence checks — ops may be mid-refresh
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
