"""
Inventory vs sales: last 6 months analysis (supply vs demand heuristic).

- Fetches order items (sales) and packages (inventory created) from Growflow for the same
  6-month window as monthly_gross_projection_to_sheet.py.
- Filters packages by category (default: prepackaged flower) and aggregates units created per month.
- Classifies each month as likely supply-constrained vs demand/outside factor using:
  - Sales down + units created down/zero + many SKUs with no current inventory → supply.
  - Sales down + units created similar/higher + inventory still present → demand/outside.
- Writes results to a new tab "Inventory vs Sales (6m)" in the same spreadsheet.

Usage:
  python inventory_vs_sales_last_6_months.py
  python inventory_vs_sales_last_6_months.py --growflow-credentials "E:\\secrets\\gcp\\growflowapi.txt" --sheets-service-account "E:\\secrets\\gcp\\sa.json"
  python inventory_vs_sales_last_6_months.py --category "prepackaged"
"""
from __future__ import annotations

import argparse
import os
import sys
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and "__file__" in dir():
    _root = Path(__file__).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    PACKAGES_TABLE_QUERY,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)

SPREADSHEET_ID = "13Wm3UdCdvzw6lpYUDIs-J2UOiRO42oNxE8wKzVyCqRA"
NUM_MONTHS = 6
DEFAULT_CATEGORY_FILTER = ""  # empty = all categories

# Thresholds for heuristic
SALES_DROP_PCT = 15.0   # consider "sales down" if drop >= this vs prior month
UNITS_DROP_PCT = 15.0   # consider "units created down" similarly
SKU_STOCKOUT_THRESHOLD = 0.5  # "many SKUs out" = fraction of distinct SKUs with CurrentQty == 0


def _get_service_account_path(service_account_path: str | None = None) -> str:
    path = service_account_path
    if not path:
        path = os.environ.get("STASHBOX_SERVICE_ACCOUNT", "").strip() or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not path:
        try:
            from lib.config_loader import get_google_service_account_path
            p = get_google_service_account_path()
            path = str(p) if p else None
        except Exception:
            path = None
    if not path and Path("E:/secrets/gcp/stashbox.json").exists():
        path = "E:/secrets/gcp/stashbox.json"
    if not path or not Path(path).exists():
        raise FileNotFoundError(
            "Google service account JSON not found. Set --sheets-service-account or GOOGLE_APPLICATION_CREDENTIALS."
        )
    return path


def get_sheets_service(service_account_path: str | None = None):
    path = _get_service_account_path(service_account_path)
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds)


def ensure_sheet(service, spreadsheet_id: str, title: str) -> str:
    """Ensure a sheet with the given title exists; create if missing."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))").execute()
    sheets = meta.get("sheets") or []
    for s in sheets:
        props = s.get("properties") or {}
        if (props.get("title") or "").strip() == title:
            return title
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    return title


def _parse_iso(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _category_matches(category_name: str | None, filter_substring: str) -> bool:
    if not filter_substring:
        return True
    name = (category_name or "").strip().lower()
    return filter_substring.strip().lower() in name


def main() -> None:
    ap = argparse.ArgumentParser(description="Last 6 months inventory vs sales analysis, add tab")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow API credentials")
    ap.add_argument("--sheets-service-account", default=None, help="Path to GCP service account JSON")
    ap.add_argument("--category", default=DEFAULT_CATEGORY_FILTER, help="Category filter substring; default all categories")
    ap.add_argument("--no-sheet", action="store_true", help="Do not write to Google Sheet; print only")
    args = ap.parse_args()

    growflow_creds = args.growflow_credentials or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
    if not growflow_creds and Path("E:/secrets/gcp/growflowapi.txt").exists():
        growflow_creds = "E:/secrets/gcp/growflowapi.txt"

    now = datetime.now(timezone.utc)
    cur_year, cur_month = now.year, now.month

    # Same 6 calendar months as monthly_gross_projection_to_sheet (oldest first)
    month_list = []
    y, m = cur_year, cur_month
    for _ in range(NUM_MONTHS):
        month_list.append((y, m))
        m -= 1
        if m < 1:
            m += 12
            y -= 1
    month_list.reverse()

    first_y, first_m = month_list[0]
    start_dt = datetime(first_y, first_m, 1, 0, 0, 0, tzinfo=timezone.utc)
    from_iso = start_dt.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = now.strftime("%Y-%m-%dT23:59:59.999Z")
    where_sold = date_range_to_where("SoldAt", from_iso, to_iso)
    where_created = date_range_to_where("createdAt", from_iso, to_iso)

    print("Fetching order items (last 6 months)...", flush=True)
    try:
        order_nodes = fetch_paginated(
            "findOrderItems",
            ORDER_ITEMS_QUERY,
            {"first": PAGE_SIZE, "where": where_sold},
            credentials_path=growflow_creds,
        )
    except Exception as e:
        print(f"Error fetching order items: {e}", file=sys.stderr)
        sys.exit(1)

    print("Fetching packages (created in same window)...", flush=True)
    try:
        package_nodes = fetch_paginated(
            "findPackages",
            PACKAGES_TABLE_QUERY,
            {"first": PAGE_SIZE, "where": where_created},
            credentials_path=growflow_creds,
        )
    except Exception as e:
        print(f"Error fetching packages: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter packages by category (e.g. prepackaged flower)
    category_filter = (args.category or "").strip() or None
    if category_filter:
        package_nodes = [
            n for n in package_nodes
            if _category_matches(((n.get("Product") or {}).get("ProductCategory") or {}).get("Name"), category_filter)
        ]
    print(f"Packages in category filter '{category_filter or 'all'}': {len(package_nodes)}", flush=True)

    # Sales by month (from order items in same category for consistency)
    by_month_sales: dict[tuple[int, int], list] = {}
    for n in order_nodes:
        sold = _parse_iso(n.get("SoldAt"))
        if not sold:
            continue
        cat_name = (n.get("ProductCategory") or {}).get("Name")
        if category_filter and not _category_matches(cat_name, category_filter):
            continue
        key = (sold.year, sold.month)
        if key not in by_month_sales:
            by_month_sales[key] = []
        by_month_sales[key].append(n)

    # Packages by created-at month; and current SKU inventory (CurrentQty > 0)
    by_month_units: dict[tuple[int, int], list] = {}
    sku_current_qty: dict[str, int] = {}  # SKU -> current total qty (today)
    for n in package_nodes:
        created = _parse_iso(n.get("createdAt"))
        key = (created.year, created.month) if created else None
        orig = n.get("OriginalQty") or 0
        curr = n.get("CurrentQty") or 0
        sku = (n.get("Product") or {}).get("SKU") or n.get("SKU") or ""
        if sku:
            sku_current_qty[sku] = sku_current_qty.get(sku, 0) + curr
        if key:
            if key not in by_month_units:
                by_month_units[key] = []
            by_month_units[key].append({"OriginalQty": orig, "CurrentQty": curr, "SKU": sku})

    # Distinct SKUs that ever appeared in packages (in window + category)
    all_skus = set()
    for nodes in by_month_units.values():
        for p in nodes:
            if p.get("SKU"):
                all_skus.add(p["SKU"])
    num_skus = len(all_skus) if all_skus else 1
    skus_with_stock = sum(1 for s in all_skus if (sku_current_qty.get(s) or 0) > 0)
    fraction_stockout = 1.0 - (skus_with_stock / num_skus) if num_skus else 0.0

    # Build one row per month with classification
    headers = ["Month", "Gross ($)", "Sales lines", "Units created", "Classification", "Note"]
    rows = [headers]
    prev_gross = None
    prev_units = None

    for (y, m) in month_list:
        month_name = datetime(y, m, 1).strftime("%B %Y")
        items = by_month_sales.get((y, m), [])
        gross_cents = sum(i.get("GrossPrice") or 0 for i in items)
        gross = gross_cents / 100.0
        line_count = len(items)

        pkgs = by_month_units.get((y, m), [])
        units_created = sum(p.get("OriginalQty") or 0 for p in pkgs)

        # Heuristic
        sales_down = prev_gross is not None and prev_gross > 0 and (gross <= 0 or (prev_gross - gross) / prev_gross * 100 >= SALES_DROP_PCT)
        units_down = prev_units is not None and (units_created <= 0 or (prev_units > 0 and (prev_units - units_created) / prev_units * 100 >= UNITS_DROP_PCT))
        many_skus_out = fraction_stockout >= SKU_STOCKOUT_THRESHOLD

        if sales_down and (units_down or units_created == 0) and many_skus_out:
            classification = "Likely supply-constrained"
            note = "Sales down; units created down or zero; many SKUs have no current inventory."
        elif sales_down and (not units_down or units_created > 0) and (not many_skus_out or skus_with_stock > 0):
            classification = "Likely demand / outside factor"
            note = "Sales down but supply similar or higher; inventory still present. Consider pricing, competition, seasonality."
        elif sales_down:
            classification = "Unclear"
            note = "Sales down; supply/inventory signals mixed."
        else:
            classification = "-"
            note = "No significant sales drop vs prior month."

        rows.append([
            month_name,
            round(gross, 2),
            line_count,
            units_created,
            classification,
            note,
        ])
        prev_gross = gross
        prev_units = units_created

    rows.append([])
    rows.append([f"Category filter: {category_filter or 'all'}. Distinct SKUs: {num_skus}, with current stock: {skus_with_stock}."])
    rows.append([f"Calculated: {now.strftime('%Y-%m-%d %H:%M UTC')}. Heuristic: supply = sales down + units down + many SKUs out; demand = sales down + supply healthy."])

    # Print summary
    print()
    for r in rows[1:]:
        if not r or r[0] == "":
            continue
        if r[0].startswith("Category") or r[0].startswith("Calculated"):
            print(r[0])
            continue
        print(f"  {r[0]}: ${r[1]:,.2f} gross, {r[2]} lines, {r[3]} units created -> {r[4]}")

    if not args.no_sheet:
        sheet_title = "Inventory vs Sales (6m)"
        print("Writing to sheet...", flush=True)
        try:
            service = get_sheets_service(args.sheets_service_account)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        try:
            ensure_sheet(service, SPREADSHEET_ID, sheet_title)
        except Exception as e:
            print(f"Failed to ensure sheet: {e}", file=sys.stderr)
            sys.exit(1)
        range_name = f"'{sheet_title}'!A1:F{len(rows)}"
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()
        print(f"Done. Tab: \"{sheet_title}\"")
        print(f"Spreadsheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    else:
        print("Done (no sheet write).")


if __name__ == "__main__":
    main()
