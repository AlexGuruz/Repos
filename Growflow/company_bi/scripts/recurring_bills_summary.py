#!/usr/bin/env python3
"""
Print recurring monthly bills (overhead by subcategory) from cleaned Transactions/Bank data.
Does not require GrowFlow; only reads transaction sheets and categorizes.
Run from Growflow repo root: python -m company_bi.scripts.recurring_bills_summary [--months 12]
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
    detect_transaction_columns,
)
from company_bi.lib.normalization import normalize_transactions
from company_bi.lib.categorization import (
    apply_categorization,
    aggregate_overhead_by_subcategory_by_month,
)


def _month_label(ym: tuple[int, int]) -> str:
    from datetime import datetime
    return datetime(ym[0], ym[1], 1).strftime("%b %Y")


def main() -> int:
    ap = argparse.ArgumentParser(description="Recurring bills from Transactions/Bank (no GrowFlow)")
    ap.add_argument("--months", type=int, default=12, help="Months to include")
    args = ap.parse_args()

    cfg = load_sources_config()
    trans_cfg = cfg.get("transactions", {})
    try:
        service = get_sheets_service(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or (cfg.get("sheets") or {}).get("default_service_account_path")
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    all_txn_rows = []
    for year_key, src in trans_cfg.items():
        if not isinstance(src, dict) or (isinstance(year_key, str) and year_key.startswith("_")):
            continue
        sid = src.get("spreadsheet_id")
        tabs = src.get("tabs") or []
        if not sid or not tabs:
            continue
        for tab in tabs:
            try:
                r = f"'{tab}'!A1:Z"
                resp = service.spreadsheets().values().get(
                    spreadsheetId=sid,
                    range=r,
                    valueRenderOption="UNFORMATTED_VALUE",
                ).execute()
                vals = resp.get("values") or []
                for row in vals:
                    all_txn_rows.append(list(row) + [year_key])
            except Exception as e:
                print(f"  Skip {sid} tab {tab}: {e}", file=sys.stderr)
    if not all_txn_rows:
        print("No transaction data.", file=sys.stderr)
        return 0

    date_col, _c, source_col, amount_col, start_row = detect_transaction_columns(all_txn_rows)
    normalized_txns = normalize_transactions(all_txn_rows, date_col, source_col, amount_col, start_row)

    from datetime import date
    today = date.today()
    allowed_ym = set()
    for i in range(args.months + 1):
        y, m = today.year, today.month
        m -= i
        while m <= 0:
            m += 12
            y -= 1
        allowed_ym.add((y, m))
    normalized_txns = [t for t in normalized_txns if t["date_ym"] in allowed_ym]
    tagged = apply_categorization(normalized_txns)
    overhead_by_sub = aggregate_overhead_by_subcategory_by_month(tagged)

    if not overhead_by_sub:
        print("No overhead (recurring bills) found in the transaction window.")
        return 0

    # Summary: sum across all months by bill type for a single "typical" view, then show last month detail
    from collections import defaultdict
    total_by_bill_type: dict[str, float] = defaultdict(float)
    for ym, subs in overhead_by_sub.items():
        for bill_type, amt in subs.items():
            total_by_bill_type[bill_type] += amt
    months_count = len(overhead_by_sub)
    avg_by_bill_type = {k: v / months_count for k, v in total_by_bill_type.items()}

    print("RECURRING MONTHLY BILLS (inferred from cleaned Transactions/Bank)")
    print("=" * 56)
    print(f"Based on {len(normalized_txns)} transactions over {months_count} months.")
    print()
    print(f"{'Bill type':<24} {'Avg/month':>12} {'Total (period)':>14}")
    print("-" * 56)
    grand_avg = 0.0
    for bill_type in sorted(avg_by_bill_type.keys(), key=lambda x: -avg_by_bill_type[x]):
        avg = avg_by_bill_type[bill_type]
        total = total_by_bill_type[bill_type]
        grand_avg += avg
        print(f"{bill_type:<24} ${avg:>11,.2f} ${total:>13,.2f}")
    print("-" * 56)
    print(f"{'OVERHEAD TOTAL (avg/month)':<24} ${grand_avg:>11,.2f}")
    print()
    # Last month detail
    last_ym = max(overhead_by_sub.keys())
    subs = overhead_by_sub[last_ym]
    print(f"Last month ({_month_label(last_ym)}):")
    for bill_type in sorted(subs.keys(), key=lambda x: -subs[x]):
        print(f"  {bill_type}: ${subs[bill_type]:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
