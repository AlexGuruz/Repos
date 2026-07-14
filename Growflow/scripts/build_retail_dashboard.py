"""
Build retail dashboard aggregates from growflow_facts.db.

Usage:
  PYTHONPATH=. python scripts/build_retail_dashboard.py --preset last_30_days --compare
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.growflow_config import load_config
from lib.growflow_fact_store import DEFAULT_DB_PATH, connect, init_db, query_lines_between
from lib.retail_dashboard.cache import connect_cache, save_payload
from lib.retail_dashboard.metrics import _period_dates, build_dashboard, prior_period, validate_sums
from lib.retail_dashboard.reconcile import (
    DEFAULT_REPORT_JSON,
    Tolerance,
    exit_code_for_report,
    load_reference_csv,
    load_reference_json,
    load_retail_dashboard_config,
    reconcile,
    write_report,
)
from zoneinfo import ZoneInfo

LATEST_JSON = REPO / "data" / "retail_dashboard_latest.json"


def _payload_to_dict(payload) -> dict:
    return {
        "meta": payload.meta,
        "period_compare_kpis": payload.period_compare_kpis,
        "budtender_sales": payload.budtender_sales,
        "discounts_over_time": payload.discounts_over_time,
        "budtender_by_category": payload.budtender_by_category,
        "brand_summary": payload.brand_summary,
        "alerts": payload.alerts,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build retail dashboard from fact store")
    ap.add_argument("--facts-db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--cache-db", default=str(REPO / "data" / "retail_dashboard.db"))
    ap.add_argument("--preset", default="last_30_days", choices=["last_7_days", "last_30_days", "last_90_days"])
    ap.add_argument("--compare", action="store_true", help="Include prior-period compare KPIs")
    ap.add_argument("--store-id", default=None)
    ap.add_argument("--channel", default="all", choices=["all", "in_store", "online"])
    ap.add_argument("--start", default=None, help="Override start YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="Override end YYYY-MM-DD")
    ap.add_argument("--strict", action="store_true", help="Exit 1 if sum validation fails")
    ap.add_argument("--reconcile", action="store_true", help="Run reconciliation after build (sum gates + optional reference)")
    ap.add_argument("--reference-csv", default=None, help="Reference CSV for reconciliation")
    ap.add_argument("--reference-json", default=None, help="Reference JSON for reconciliation")
    ap.add_argument("--reconcile-strict", action="store_true", help="Exit 1 on reconciliation warning")
    args = ap.parse_args()

    if args.reference_csv and args.reference_json:
        print("error: use only one of --reference-csv or --reference-json", file=sys.stderr)
        return 2

    cfg = load_config()
    tz = ZoneInfo(cfg.get("sales_timezone") or "America/Chicago")

    if args.start and args.end:
        period_start = date.fromisoformat(args.start)
        period_end = date.fromisoformat(args.end)
    else:
        period_start, period_end = _period_dates(args.preset, tz)

    prior_start = prior_end = None
    if args.compare:
        prior_start, prior_end = prior_period(period_start, period_end)

  # Load lines spanning current + prior if comparing
    query_start = prior_start.isoformat() if prior_start else period_start.isoformat()
    query_end = period_end.isoformat()

    facts = connect(args.facts_db)
    init_db(facts)
    lines = query_lines_between(
        facts,
        query_start,
        query_end,
        store_object_id=args.store_id,
        channel=None if args.channel == "all" else args.channel,
    )
    facts.close()

    if not lines:
        print("No fact rows in range — run ingest_growflow_facts.py first", flush=True)
        return 1

    payload = build_dashboard(
        lines,
        period_start=period_start,
        period_end=period_end,
        prior_start=prior_start,
        prior_end=prior_end,
        store_id=args.store_id,
        channel=args.channel,
    )
    errors = validate_sums(payload)
    validation_ok = not errors
    if errors:
        print("Sum validation errors:", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)

    run_id = f"rd_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    cache = connect_cache(args.cache_db)
    save_payload(cache, run_id, payload, validation_ok=validation_ok)
    cache.close()

    out = _payload_to_dict(payload)
    out["meta"]["run_id"] = run_id
    out["meta"]["validation"] = {"ok": validation_ok, "errors": errors}
    LATEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(
        f"Built run {run_id}: lines={len(lines)} store_net={payload.meta.get('store_net_sales')} "
        f"validation_ok={validation_ok}",
        flush=True,
    )
    print(f"Wrote {LATEST_JSON}", flush=True)
    if args.strict and not validation_ok:
        return 1

    if args.reconcile:
        rec_cfg = load_retail_dashboard_config().get("reconciliation") or {}
        ref_csv = Path(args.reference_csv) if args.reference_csv else (
            REPO / rec_cfg["default_reference_csv"] if rec_cfg.get("default_reference_csv") else None
        )
        ref_json = Path(args.reference_json) if args.reference_json else (
            REPO / rec_cfg["default_reference_json"] if rec_cfg.get("default_reference_json") else None
        )
        reference = None
        reference_type = None
        reference_path = None
        if ref_csv and ref_csv.is_file():
            reference_path = ref_csv
            reference_type = "csv"
            reference = load_reference_csv(ref_csv)
        elif ref_json and ref_json.is_file():
            reference_path = ref_json
            reference_type = "json"
            reference = load_reference_json(ref_json)

        tol = Tolerance(
            money_abs=float(rec_cfg.get("money_tolerance_abs", 1.0)),
            pct=float(rec_cfg.get("pct_tolerance", 0.005)),
        )
        report = reconcile(
            out,
            reference=reference,
            reference_type=reference_type,
            reference_path=reference_path,
            tol=tol,
        )
        report["dashboard"] = {"path": str(LATEST_JSON)}
        out_path = REPO / str(rec_cfg.get("default_out") or DEFAULT_REPORT_JSON.relative_to(REPO))
        write_report(report, out_path)
        print(
            f"Reconciliation {report['status']}: "
            f"{report['summary']['checks_passed']}/{report['summary']['checks_total']} passed",
            flush=True,
        )
        print(f"Wrote {out_path}", flush=True)
        rc = exit_code_for_report(report, strict=args.reconcile_strict)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
