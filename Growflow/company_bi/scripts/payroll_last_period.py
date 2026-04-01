#!/usr/bin/env python3
"""
Print payroll by period from the Kylo PAYROLL sheet.
- Default: last pay period (most recent date with payments).
- With --year and --month: everyone paid in that month (e.g. --year 2026 --month 3 for March 2026).
Run from Growflow repo root: python -m company_bi.scripts.payroll_last_period
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from company_bi.lib.sources import (
    load_sources_config,
    get_sheets_service,
    fetch_payroll_sheet_raw_rows,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Payroll: last period or by month")
    ap.add_argument("--year", type=int, default=None, help="Year (e.g. 2026)")
    ap.add_argument("--month", type=int, default=None, help="Month 1-12 (e.g. 3 for March)")
    args = ap.parse_args()
    filter_ym = (args.year, args.month) if (args.year is not None and args.month is not None) else None

    cfg = load_sources_config()
    try:
        service = get_sheets_service(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or (cfg.get("sheets") or {}).get("default_service_account_path")
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    rows = fetch_payroll_sheet_raw_rows(service, cfg)
    if not rows:
        print("No payroll rows found. Check config payroll_sheet and that the PAYROLL tab has data from row 20 (dates in A, amounts in B,C,...).")
        return 0

    if filter_ym:
        y, m = filter_ym
        period_rows = [r for r in rows if (r["date_ymd"][0], r["date_ymd"][1]) == (y, m)]
        title = f"Payroll for {m:02d}-{y} (month to date)"
    else:
        max_date = max(r["date_ymd"] for r in rows)
        period_rows = [r for r in rows if r["date_ymd"] == max_date]
        title = f"Last pay period (date): {period_rows[0]['date_str']}" if period_rows else "Last pay period"

    by_employee: dict[str, float] = {}
    for r in period_rows:
        name = r["employee"]
        by_employee[name] = by_employee.get(name, 0) + r["amount"]
    by_employee = {k: v for k, v in by_employee.items() if v > 0}

    print(title)
    print(f"Employees paid: {len(by_employee)}")
    print()
    print(f"{'Employee':<40} {'Amount':>12}")
    print("-" * 54)
    total = 0.0
    for name in sorted(by_employee.keys()):
        amt = by_employee[name]
        total += amt
        print(f"{name:<40} ${amt:>11,.2f}")
    print("-" * 54)
    print(f"{'Total':<40} ${total:>11,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
