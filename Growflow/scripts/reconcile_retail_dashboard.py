"""
Reconcile Retail Dashboard Operations metrics against a trusted reference export.

Usage:
  PYTHONPATH=. python scripts/reconcile_retail_dashboard.py \\
    --dashboard-json data/retail_dashboard_latest.json \\
    --reference-csv data/reference/growflow_retail_dashboard_export.csv \\
    --out data/retail_reconciliation_latest.json

Exit codes:
  0 pass (or warning-only unless --strict)
  1 fail
  2 invalid/missing inputs or contract errors
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.retail_dashboard.reconcile import (  # noqa: E402
    DEFAULT_DASHBOARD_JSON,
    DEFAULT_REPORT_JSON,
    ReconcileConfig,
    Tolerance,
    exit_code_for_report,
    load_dashboard_json,
    load_reference_csv,
    load_reference_json,
    load_retail_dashboard_config,
    reconcile,
    write_report,
)


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else REPO / p


def main(argv: list[str] | None = None) -> int:
    cfg = load_retail_dashboard_config()
    rec_cfg = cfg.get("reconciliation") or {}

    ap = argparse.ArgumentParser(description="Reconcile retail dashboard Operations metrics")
    ap.add_argument(
        "--dashboard-json",
        default=None,
        help="Computed dashboard JSON (default: config paths.latest_json or data/retail_dashboard_latest.json)",
    )
    ap.add_argument(
        "--latest",
        action="store_true",
        help="Use data/retail_dashboard_latest.json as dashboard input",
    )
    ap.add_argument("--reference-csv", default=None, help="Trusted reference CSV export")
    ap.add_argument("--reference-json", default=None, help="Trusted reference JSON snapshot")
    ap.add_argument(
        "--out",
        default=str(rec_cfg.get("default_out") or DEFAULT_REPORT_JSON.relative_to(REPO)),
        help="Write reconciliation report JSON here",
    )
    ap.add_argument(
        "--money-tolerance",
        type=float,
        default=float(rec_cfg.get("money_tolerance_abs", 1.0)),
        help="Absolute USD tolerance (default from config, usually 1.00)",
    )
    ap.add_argument(
        "--pct-tolerance",
        type=float,
        default=float(rec_cfg.get("pct_tolerance", 0.005)),
        help="Relative tolerance as decimal (0.005 = 0.5%%)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on warning status (not just fail)",
    )
    args = ap.parse_args(argv)

    if args.reference_csv and args.reference_json:
        print("error: use only one of --reference-csv or --reference-json", file=sys.stderr)
        return 2

    default_dashboard = rec_cfg.get("default_dashboard_json") or str(
        DEFAULT_DASHBOARD_JSON.relative_to(REPO)
    )
    if args.latest:
        dashboard_path = _resolve_path(str(DEFAULT_DASHBOARD_JSON.relative_to(REPO)))
    elif args.dashboard_json:
        dashboard_path = _resolve_path(args.dashboard_json)
    else:
        dashboard_path = _resolve_path(default_dashboard)

    out_path = _resolve_path(args.out)
    tol = Tolerance(money_abs=args.money_tolerance, pct=args.pct_tolerance)

    try:
        dashboard = load_dashboard_json(dashboard_path)
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"error: dashboard input invalid: {e}", file=sys.stderr)
        return 2

    reference = None
    reference_type = None
    reference_path = None
    if args.reference_csv:
        reference_path = _resolve_path(args.reference_csv)
        reference_type = "csv"
        try:
            reference = load_reference_csv(reference_path)
        except (FileNotFoundError, ValueError, OSError) as e:
            print(f"error: reference csv invalid: {e}", file=sys.stderr)
            return 2
    elif args.reference_json:
        reference_path = _resolve_path(args.reference_json)
        reference_type = "json"
        try:
            reference = load_reference_json(reference_path)
        except (FileNotFoundError, ValueError, OSError) as e:
            print(f"error: reference json invalid: {e}", file=sys.stderr)
            return 2

    report = reconcile(
        dashboard,
        reference=reference,
        reference_type=reference_type,
        reference_path=reference_path,
        tol=tol,
    )
    report["dashboard"] = {"path": str(dashboard_path)}
    write_report(report, out_path)

    print(
        f"Reconciliation {report['status']}: "
        f"{report['summary']['checks_passed']}/{report['summary']['checks_total']} passed "
        f"(failed={report['summary']['checks_failed']}, warning={report['summary']['checks_warning']})",
        flush=True,
    )
    print(f"Wrote {out_path}", flush=True)

    for check in report["checks"]:
        if check["status"] != "pass":
            msg = check.get("message") or ""
            print(
                f"  [{check['status']}] {check['name']}: "
                f"expected={check.get('expected')} actual={check.get('actual')} "
                f"delta={check.get('delta_abs')} {msg}".strip(),
                flush=True,
            )

    code = exit_code_for_report(report)
    if args.strict and report["status"] == "warning":
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
