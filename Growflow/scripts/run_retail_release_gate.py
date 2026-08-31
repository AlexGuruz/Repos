"""
Retail Operations release gate — build dashboard then reconcile.

Use in CI or before promoting Operations metrics:

  PYTHONPATH=. python scripts/run_retail_release_gate.py \\
    --preset last_30_days \\
    --compare \\
    --reference-csv data/reference/growflow_retail_dashboard_export.csv

Exit codes:
  0 — build + reconciliation pass
  1 — build sum validation failed or reconciliation fail
  2 — invalid/missing required inputs
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.retail_dashboard.reconcile import (  # noqa: E402
    DEFAULT_DASHBOARD_JSON,
    DEFAULT_REPORT_JSON,
    Tolerance,
    exit_code_for_report,
    load_retail_dashboard_config,
)


def _resolve(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else REPO / p


def _run_build(argv: list[str]) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / "build_retail_dashboard.py"), *argv]
    print(">>", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(REPO))


def _run_reconcile(argv: list[str]) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / "reconcile_retail_dashboard.py"), *argv]
    print(">>", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(REPO))


def main(argv: list[str] | None = None) -> int:
    cfg = load_retail_dashboard_config()
    rec = cfg.get("reconciliation") or {}

    ap = argparse.ArgumentParser(description="Retail Operations release gate (build + reconcile)")
    ap.add_argument("--preset", default="last_30_days", choices=["last_7_days", "last_30_days", "last_90_days"])
    ap.add_argument("--compare", action="store_true", help="Include prior-period compare in build")
    ap.add_argument("--store-id", default=None)
    ap.add_argument("--channel", default="all", choices=["all", "in_store", "online"])
    ap.add_argument("--start", default=None, help="Override period start YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="Override period end YYYY-MM-DD")
    ap.add_argument("--skip-build", action="store_true", help="Only run reconciliation against existing dashboard JSON")
    ap.add_argument(
        "--dashboard-json",
        default=None,
        help="Dashboard JSON path (default: config reconciliation.default_dashboard_json)",
    )
    ap.add_argument("--reference-csv", default=rec.get("default_reference_csv"))
    ap.add_argument("--reference-json", default=rec.get("default_reference_json"))
    ap.add_argument(
        "--require-reference",
        action="store_true",
        default=bool(rec.get("require_reference")),
        help="Fail if no reference file is provided or found",
    )
    ap.add_argument(
        "--out",
        default=str(rec.get("default_out") or DEFAULT_REPORT_JSON.relative_to(REPO)),
    )
    ap.add_argument("--money-tolerance", type=float, default=float(rec.get("money_tolerance_abs", 1.0)))
    ap.add_argument("--pct-tolerance", type=float, default=float(rec.get("pct_tolerance", 0.005)))
    ap.add_argument("--strict", action="store_true", help="Fail on reconciliation warnings")
    args = ap.parse_args(argv)

    if args.reference_csv and args.reference_json:
        print("error: use only one of --reference-csv or --reference-json", file=sys.stderr)
        return 2

    ref_csv = _resolve(args.reference_csv) if args.reference_csv else None
    ref_json = _resolve(args.reference_json) if args.reference_json else None
    if args.require_reference and not ref_csv and not ref_json:
        print("error: --require-reference set but no reference path configured", file=sys.stderr)
        return 2
    if args.require_reference:
        if ref_csv and not ref_csv.is_file():
            print(f"error: required reference csv missing: {ref_csv}", file=sys.stderr)
            return 2
        if ref_json and not ref_json.is_file():
            print(f"error: required reference json missing: {ref_json}", file=sys.stderr)
            return 2

    if not args.skip_build:
        build_argv = ["--preset", args.preset, "--strict"]
        if args.compare:
            build_argv.append("--compare")
        if args.store_id:
            build_argv.extend(["--store-id", args.store_id])
        if args.channel != "all":
            build_argv.extend(["--channel", args.channel])
        if args.start and args.end:
            build_argv.extend(["--start", args.start, "--end", args.end])
        code = _run_build(build_argv)
        if code != 0:
            print("release gate: build failed", file=sys.stderr)
            return code

    dashboard_path = _resolve(
        args.dashboard_json
        or str(rec.get("default_dashboard_json") or DEFAULT_DASHBOARD_JSON.relative_to(REPO))
    )
    if not dashboard_path.is_file():
        print(f"error: dashboard json missing after build: {dashboard_path}", file=sys.stderr)
        return 2

    reconcile_argv = [
        "--dashboard-json",
        str(dashboard_path),
        "--out",
        str(_resolve(args.out)),
        "--money-tolerance",
        str(args.money_tolerance),
        "--pct-tolerance",
        str(args.pct_tolerance),
    ]
    if ref_csv and ref_csv.is_file():
        reconcile_argv.extend(["--reference-csv", str(ref_csv)])
    elif ref_json and ref_json.is_file():
        reconcile_argv.extend(["--reference-json", str(ref_json)])
    elif args.require_reference:
        print("error: reference file not found", file=sys.stderr)
        return 2

    if args.strict:
        reconcile_argv.append("--strict")

    code = _run_reconcile(reconcile_argv)
    if code == 0:
        print("release gate: PASS", flush=True)
    elif code == 1:
        print("release gate: FAIL (reconciliation)", file=sys.stderr)
    else:
        print("release gate: INVALID INPUT", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
