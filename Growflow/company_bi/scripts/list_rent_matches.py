#!/usr/bin/env python3
"""
List every transaction that currently matches RENT (from Transactions/Bank).
Shows date, description (source), amount, and sheet/year so you can verify or adjust categories.yaml.
Run from Growflow repo root: python -m company_bi.scripts.list_rent_matches [--months 24]
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
from company_bi.lib.categorization import apply_categorization


def main() -> int:
    ap = argparse.ArgumentParser(description="List transactions matching rent")
    ap.add_argument("--months", type=int, default=24, help="Months to include")
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
    rent_rows = [r for r in tagged if r.get("category") == "overhead" and r.get("subcategory") == "rent"]

    print("TRANSACTIONS MATCHING RENT (Transactions + Bank tabs)")
    print("Rules in config/categories.yaml: pattern in (RENT, LEASE, PROPERTY PAYMENT)")
    print("=" * 90)
    print(f"{'Date':<12} {'Description (Source)':<50} {'Amount':>12}")
    print("-" * 76)
    for r in sorted(rent_rows, key=lambda x: (x["date_ym"], -abs(x["amount"]))):
        date_str = r.get("date_str") or f"{r['date_ym'][0]}-{r['date_ym'][1]:02d}"
        desc = (r.get("source_raw") or r.get("source_upper") or "")[:48]
        amt = r.get("amount", 0)
        print(f"{date_str:<12} {desc:<50} ${amt:>11,.2f}")
    print("-" * 76)
    total = sum(abs(r.get("amount", 0)) for r in rent_rows)
    print(f"Total: {len(rent_rows)} transactions, ${total:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
