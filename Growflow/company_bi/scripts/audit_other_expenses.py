#!/usr/bin/env python3
"""
Audit transactions categorized as "other" to support Phase 2: reduce other bucket.
Outputs: ranked by description, by month, recurring amount patterns.
Run from Growflow repo root: python -m company_bi.scripts.audit_other_expenses [--months 6] [--out path]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
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


def _resolve_sheet_title(service, spreadsheet_id: str, wanted: str):
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title))",
    ).execute()
    for s in meta.get("sheets", []):
        title = (s.get("properties") or {}).get("title", "")
        if title.strip().lower() == wanted.strip().lower():
            return title
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit other-category expenses")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument("--out", default=None, help="Write summary CSV to this path (e.g. docs/other_expense_analysis.csv)")
    args = ap.parse_args()

    cfg = load_sources_config()
    trans_cfg = cfg.get("transactions", {})
    months_back = args.months

    try:
        service = get_sheets_service(args.sheets_service_account)
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
            exact = _resolve_sheet_title(service, sid, tab) or tab
            try:
                r = f"'{exact}'!A1:Z"
                resp = service.spreadsheets().values().get(
                    spreadsheetId=sid, range=r, valueRenderOption="UNFORMATTED_VALUE",
                ).execute()
                for row in (resp.get("values") or []):
                    all_txn_rows.append(list(row) + [year_key])
            except Exception as e:
                print(f"  Skip {sid} tab {tab}: {e}", file=sys.stderr)

    if not all_txn_rows:
        print("No transaction rows.", file=sys.stderr)
        return 1

    date_col, company_col, source_col, amount_col, start_row = detect_transaction_columns(all_txn_rows)
    normalized_txns = normalize_transactions(all_txn_rows, date_col, source_col, amount_col, start_row)

    from datetime import date
    today = date.today()
    allowed_ym = set()
    for i in range(months_back + 1):
        y, m = today.year, today.month
        m -= i
        while m <= 0:
            m += 12
            y -= 1
        allowed_ym.add((y, m))
    normalized_txns = [t for t in normalized_txns if t["date_ym"] in allowed_ym]
    tagged = apply_categorization(normalized_txns)

    other_only = [t for t in tagged if t.get("category") == "other" and (t.get("amount") or 0) < 0]
    total_other = sum(abs(t["amount"]) for t in other_only)
    total_expense = sum(abs(t["amount"]) for t in tagged if (t.get("amount") or 0) < 0)
    pct = total_other / total_expense * 100 if total_expense else 0

    # By description (normalized: strip, upper, collapse spaces)
    by_desc: dict[str, list[float]] = defaultdict(list)
    for t in other_only:
        raw = (t.get("source_raw") or t.get("source_upper") or "").strip()
        norm = " ".join(raw.upper().split()) or "(blank)"
        by_desc[norm].append(abs(t["amount"]))

    desc_totals = [(d, sum(amts), len(amts)) for d, amts in by_desc.items()]
    desc_totals.sort(key=lambda x: -x[1])

    # By month
    by_month: dict[tuple[int, int], float] = defaultdict(float)
    for t in other_only:
        by_month[t["date_ym"]] += abs(t["amount"])

    # Recurring: same rounded amount (to $10) 3+ times
    amount_counts: dict[float, int] = defaultdict(int)
    for t in other_only:
        amount_counts[round(abs(t["amount"]) / 10) * 10] += 1
    recurring = [(amt, c) for amt, c in amount_counts.items() if c >= 3]
    recurring.sort(key=lambda x: -x[1])

    # Output
    def month_label(ym):
        from datetime import datetime
        return datetime(ym[0], ym[1], 1).strftime("%b %Y")

    print(f"Other expense: ${total_other:,.2f} ({pct:.1f}% of total expense); {len(other_only)} transactions in last {months_back} months")
    print("\nTop 30 descriptions by total $ (description, total, count):")
    for d, tot, cnt in desc_totals[:30]:
        short = (d[:60] + "…") if len(d) > 60 else d
        print(f"  {short!r} | ${tot:,.2f} | {cnt}")
    print("\nMonthly other total:")
    for ym in sorted(by_month.keys()):
        print(f"  {month_label(ym)}: ${by_month[ym]:,.2f}")
    print("\nRecurring (rounded to $10, 3+ occurrences):")
    for amt, cnt in recurring[:20]:
        print(f"  ${amt:,.0f}: {cnt} txns")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["description", "total_abs_amount", "count"])
            for d, tot, cnt in desc_totals:
                w.writerow([d, round(tot, 2), cnt])
        print(f"\nWrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
