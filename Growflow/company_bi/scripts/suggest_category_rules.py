#!/usr/bin/env python3
"""
Analyze uncategorized / "other" transactions and recommend rule patterns.
Does NOT modify categories.yaml; writes company_bi/output/category_rule_suggestions.csv.
Run from Growflow repo root: python -m company_bi.scripts.suggest_category_rules [--months 6]
"""
from __future__ import annotations

import argparse
import csv
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

# Heuristic keywords (uppercase) -> suggested category; used to suggest_category only
KEYWORD_HINTS = [
    (["PAYROLL", "PAY ROLL", "WAGE", "SALARY", "941", "TIP", "ADP", "PAYCHEX"], "labor"),
    (["RENT", "LEASE", "PROPERTY", "MORTGAGE"], "overhead"),
    (["UTILITIES", "OG&E", "ELECTRIC", "WATER", "GAS", "AT&T", "INTERNET"], "overhead"),
    (["INSURANCE", " FARMERS", "STATE FARM"], "overhead"),
    (["TAX", "OMMA", "LICENSE", "COMPLIANCE", "SALES TAX", "MJ TAX"], "overhead"),
    (["BANK", "TRANSFER", "WITHDRAW", "DEPOSIT"], "overhead"),
    (["ORDER", "PURCHASE", "INVENTORY", "SUPPLIER", "VENDOR"], "inventory"),
    (["CARD", "CAPITAL ONE", "CITI", "AMEX", "VISA "], "overhead"),
]
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


def suggest_category(description: str) -> tuple[str, str]:
    """Suggest category and confidence (high/medium/low) from keyword hints."""
    u = description.upper()
    for keywords, cat in KEYWORD_HINTS:
        for kw in keywords:
            if kw in u:
                if len(kw) >= 6 or kw in ("RENT", "TAX", "WAGE", "ORDER"):
                    return cat, "medium"
                return cat, "low"
    return "other", "low"


def main() -> int:
    ap = argparse.ArgumentParser(description="Suggest category rules from uncategorized transactions")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument("--out", default=None, help="Default: company_bi/output/category_rule_suggestions.csv")
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

    date_col, _, source_col, amount_col, start_row = detect_transaction_columns(all_txn_rows)
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
    by_desc: dict[str, list[float]] = defaultdict(list)
    for t in other_only:
        raw = (t.get("source_raw") or t.get("source_upper") or "").strip()
        norm = " ".join(raw.upper().split()) or "(blank)"
        by_desc[norm].append(abs(t["amount"]))

    rows = []
    for desc, amts in by_desc.items():
        total = sum(amts)
        count = len(amts)
        suggested, confidence = suggest_category(desc)
        rows.append((desc, count, total, suggested, confidence))
    rows.sort(key=lambda x: (-x[2], -x[1]))  # total amount desc, then count desc

    out_path = Path(args.out) if args.out else (Path(__file__).resolve().parent.parent / "output" / "category_rule_suggestions.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["description", "count", "total_amount", "suggested_category", "confidence"])
        for r in rows:
            w.writerow([r[0], r[1], round(r[2], 2), r[3], r[4]])
    print(f"Wrote {len(rows)} suggestions to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
