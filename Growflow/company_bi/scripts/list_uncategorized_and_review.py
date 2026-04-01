#!/usr/bin/env python3
"""
List uncategorized transactions and a short breakdown by subcategory for review.
Run from Growflow repo root: python -m company_bi.scripts.list_uncategorized_and_review [--months 24]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from collections import defaultdict

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
    ap = argparse.ArgumentParser(description="Uncategorized transactions and subcategory review")
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

    # Uncategorized (expenses with no rule match)
    uncat = [r for r in tagged if r.get("category") == "other" and r.get("subcategory") == "uncategorized"]
    uncat.sort(key=lambda x: (x["date_ym"], -abs(x.get("amount", 0))))

    print("UNCATEGORIZED TRANSACTIONS (no pattern match in categories.yaml)")
    print("=" * 80)
    if not uncat:
        print("(none)")
    else:
        for r in uncat:
            date_str = r.get("date_str", "")
            desc = (r.get("source_raw") or r.get("source_upper") or "")[:55]
            amt = r.get("amount", 0)
            print(f"  {date_str}  {desc:<55}  ${amt:>12,.2f}")
        print(f"\nTotal: {len(uncat)} transactions, ${sum(abs(r.get('amount',0)) for r in uncat):,.2f}")

    # Breakdown by category/subcategory with sample descriptions (for review)
    by_sub = defaultdict(list)  # (category, subcategory) -> list of (desc, amount, date_str)
    for r in tagged:
        if r.get("amount", 0) >= 0:
            continue
        cat = r.get("category", "other")
        sub = r.get("subcategory", "?")
        key = (cat, sub)
        desc = (r.get("source_raw") or r.get("source_upper") or "").strip()[:50]
        by_sub[key].append((desc, r.get("amount", 0), r.get("date_str", "")))

    print("\n\nEXPENSE SUBCATEGORIES (sample descriptions for review)")
    print("=" * 80)
    for (cat, sub) in sorted(by_sub.keys()):
        items = by_sub[(cat, sub)]
        total = sum(abs(x[1]) for x in items)
        # unique descriptions (up to 15)
        seen = set()
        samples = []
        for desc, amt, d in sorted(items, key=lambda x: -abs(x[1])):
            if desc not in seen and len(samples) < 12:
                seen.add(desc)
                samples.append((desc, amt, d))
        print(f"\n  {cat} / {sub}  ({len(items)} txns, ${total:,.2f})")
        for desc, amt, d in samples[:10]:
            print(f"    {d}  {desc:<48}  ${amt:>10,.2f}")
        if len(samples) > 10:
            print(f"    ... and {len(samples) - 10} more unique descriptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
