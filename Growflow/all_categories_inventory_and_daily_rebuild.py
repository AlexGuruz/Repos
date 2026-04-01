"""
All categories: inventory vs sales + backward reconstruction of daily inventory.

- Fetches ALL order items and ALL packages from Growflow (no category filter).
- Packages are fetched in 6-month chunks (default 4 chunks = 2 years) so older
  packages with stock are included without triggering API 520; results are deduped by package id.
- Uses current package CurrentQty by SKU as baseline, then reconstructs each day's
  end-of-day inventory backwards: inventory_end[day] = inventory_start[day+1];
  inventory_start[day] = inventory_end[day] + sales[day]. So we add sales back as we
  go backward in time.
- Sales quantity: 1 unit per order line (API does not expose line quantity; each line
  is one sold item).
- Writes:
  1) "Inventory vs Sales (6m) All" - monthly gross, units created, lines, classification, all categories.
  2) "Daily Inventory Reconstructed" - date, total inventory (end of day), sales (units), and by category.
  3) Optional "Daily Inventory by SKU" - date, SKU, category, inventory end, sales (large).

Usage:
  python all_categories_inventory_and_daily_rebuild.py
  python all_categories_inventory_and_daily_rebuild.py --growflow-credentials "E:\\secrets\\gcp\\growflowapi.txt" --sheets-service-account "E:/secrets/gcp/sa.json"
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
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
# Packages: fetch in chunks to include older packages without API 520. Each chunk = 6 months.
PACKAGES_CHUNK_DAYS = 180  # 6 months per request
PACKAGES_TOTAL_DAYS_BACK = 730  # 2 years total (4 chunks)
SALES_DROP_PCT = 15.0
UNITS_DROP_PCT = 15.0
SKU_STOCKOUT_THRESHOLD = 0.5


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


def _normalize_category(cat: str | None) -> str:
    return (cat or "").strip() or "(no category)"


def _col_letter(n: int) -> str:
    """Column letter for 1-based n (1=A, 27=AA)."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s or "A"


def main() -> None:
    ap = argparse.ArgumentParser(description="All categories inventory vs sales + daily inventory reconstruction")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow API credentials")
    ap.add_argument("--sheets-service-account", default=None, help="Path to GCP service account JSON")
    ap.add_argument("--no-sheet", action="store_true", help="Do not write to Google Sheet")
    ap.add_argument("--no-daily-by-sku", action="store_true", help="Do not write Daily Inventory by SKU (large)")
    ap.add_argument("--packages-days-back", type=int, default=PACKAGES_TOTAL_DAYS_BACK, help="How far back to fetch packages (default 730 = 2 years)")
    args = ap.parse_args()
    packages_total_days = max(args.packages_days_back, PACKAGES_CHUNK_DAYS)

    growflow_creds = args.growflow_credentials or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
    if not growflow_creds and Path("E:/secrets/gcp/growflowapi.txt").exists():
        growflow_creds = "E:/secrets/gcp/growflowapi.txt"

    now = datetime.now(timezone.utc)
    today = now.date()

    # 6-month window
    first_dt = now - timedelta(days=30 * NUM_MONTHS)
    from_iso = first_dt.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = now.strftime("%Y-%m-%dT23:59:59.999Z")
    where_sold = date_range_to_where("SoldAt", from_iso, to_iso)

    print("Fetching ALL order items (last 6 months, no category filter)...", flush=True)
    order_nodes = fetch_paginated(
        "findOrderItems",
        ORDER_ITEMS_QUERY,
        {"first": PAGE_SIZE, "where": where_sold},
        credentials_path=growflow_creds,
    )
    print(f"  Order items: {len(order_nodes)}", flush=True)

    # Packages: fetch in 6-month chunks to include older packages (avoids single huge request -> 520)
    package_nodes: list[dict] = []
    chunk_start = now
    chunk_num = 0
    while True:
        chunk_end = chunk_start - timedelta(days=PACKAGES_CHUNK_DAYS)
        if chunk_num * PACKAGES_CHUNK_DAYS >= packages_total_days:
            break
        from_pkg = chunk_end.strftime("%Y-%m-%dT00:00:00.000Z")
        to_pkg = chunk_start.strftime("%Y-%m-%dT23:59:59.999Z")
        where_pkg = date_range_to_where("createdAt", from_pkg, to_pkg)
        print(f"Fetching packages chunk {chunk_num + 1} (created {chunk_end.date()} to {chunk_start.date()})...", flush=True)
        try:
            chunk = fetch_paginated(
                "findPackages",
                PACKAGES_TABLE_QUERY,
                {"first": PAGE_SIZE, "where": where_pkg},
                credentials_path=growflow_creds,
            )
            package_nodes.extend(chunk)
            print(f"  got {len(chunk)} packages (total {len(package_nodes)})", flush=True)
        except Exception as e:
            print(f"  chunk failed: {e} (using packages fetched so far)", flush=True)
        chunk_start = chunk_end
        chunk_num += 1
    # Dedupe by package id (boundary dates can appear in two chunks)
    seen_ids: set[str] = set()
    unique_packages: list[dict] = []
    for n in package_nodes:
        pid = n.get("objectId") or n.get("id") or ""
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_packages.append(n)
    if len(unique_packages) < len(package_nodes):
        print(f"  Deduped to {len(unique_packages)} packages", flush=True)
    package_nodes = unique_packages
    print(f"  Packages total: {len(package_nodes)}", flush=True)

    # --- Sales by date, by (date, SKU), by (date, category), and by (year, month) ---
    # Quantity = 1 per order line (API has no line quantity)
    sales_by_date: dict[str, int] = defaultdict(int)  # date_iso -> units
    sales_by_date_sku: dict[tuple[str, str], int] = defaultdict(int)  # (date, sku) -> units
    sales_by_date_cat: dict[tuple[str, str], int] = defaultdict(int)  # (date, category) -> units
    gross_by_date: dict[str, float] = defaultdict(float)
    by_month_sales: dict[tuple[int, int], list] = defaultdict(list)
    by_month_units_created: dict[tuple[int, int], int] = defaultdict(int)

    for n in order_nodes:
        sold = _parse_iso(n.get("SoldAt"))
        if not sold:
            continue
        date_key = sold.strftime("%Y-%m-%d")
        sku = (n.get("Product") or {}).get("SKU") or n.get("SKU") or ""
        cat = _normalize_category((n.get("ProductCategory") or {}).get("Name"))
        gross_cents = n.get("GrossPrice") or 0
        qty = 1  # one line = one unit
        sales_by_date[date_key] += qty
        gross_by_date[date_key] += gross_cents / 100.0
        if sku:
            sales_by_date_sku[(date_key, sku)] += qty
        sales_by_date_cat[(date_key, cat)] += qty
        by_month_sales[(sold.year, sold.month)].append(n)

    # --- Current inventory by SKU (baseline for reconstruction) ---
    current_inv_sku: dict[str, int] = defaultdict(int)  # sku -> units
    current_inv_sku_cat: dict[tuple[str, str], int] = defaultdict(int)  # (sku, category) -> units
    by_month_units: dict[tuple[int, int], list] = defaultdict(list)
    all_skus: set[str] = set()

    for n in package_nodes:
        created = _parse_iso(n.get("createdAt"))
        orig = n.get("OriginalQty") or 0
        curr = n.get("CurrentQty") or 0
        sku = (n.get("Product") or {}).get("SKU") or n.get("SKU") or ""
        cat = _normalize_category(((n.get("Product") or {}).get("ProductCategory") or {}).get("Name"))
        if sku:
            all_skus.add(sku)
            current_inv_sku[sku] += curr
            current_inv_sku_cat[(sku, cat)] += curr
        if created:
            by_month_units[(created.year, created.month)].append({"OriginalQty": orig, "CurrentQty": curr, "SKU": sku})
            by_month_units_created[(created.year, created.month)] += orig or 0

    num_skus = len(all_skus) or 1
    skus_with_stock = sum(1 for s in all_skus if (current_inv_sku.get(s) or 0) > 0)
    fraction_stockout = 1.0 - (skus_with_stock / num_skus) if num_skus else 0.0

    # --- Reconstruct daily inventory backwards (by SKU) ---
    # For each date from today down to first: inventory_end[date][sku] = current[sku]; then current[sku] += sales[date][sku]
    sorted_dates = sorted(sales_by_date.keys(), reverse=True)
    if not sorted_dates:
        sorted_dates = [today.strftime("%Y-%m-%d")]
    first_date_str = min(sorted_dates)
    last_date_str = max(sorted_dates)
    d0 = datetime.strptime(first_date_str, "%Y-%m-%d").date()
    d1 = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    all_dates = []
    d = d0
    while d <= d1:
        all_dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    all_dates.sort(reverse=True)  # newest first

    inv_end_by_date_sku: dict[str, dict[str, int]] = {}
    current: dict[str, int] = dict(current_inv_sku)
    for date_key in all_dates:
        inv_end_by_date_sku[date_key] = dict(current)
        for (d, sku), qty in sales_by_date_sku.items():
            if d == date_key:
                current[sku] = current.get(sku, 0) + qty

    # --- Daily totals (reconstructed) ---
    daily_total_inv_end: dict[str, int] = {}
    for date_key, sku_map in inv_end_by_date_sku.items():
        daily_total_inv_end[date_key] = sum(sku_map.values())

    # --- Monthly summary for Inventory vs Sales (6m) All ---
    cur_year, cur_month = now.year, now.month
    month_list = []
    y, m = cur_year, cur_month
    for _ in range(NUM_MONTHS):
        month_list.append((y, m))
        m -= 1
        if m < 1:
            m += 12
            y -= 1
    month_list.reverse()

    rows_6m = [
        ["Month", "Gross ($)", "Sales lines", "Units created", "Classification", "Note"]
    ]
    prev_gross = None
    prev_units = None
    for (y, m) in month_list:
        month_name = datetime(y, m, 1).strftime("%B %Y")
        items = by_month_sales.get((y, m), [])
        gross = sum(i.get("GrossPrice") or 0 for i in items) / 100.0
        line_count = len(items)
        units_created = by_month_units_created.get((y, m), 0)
        sales_down = prev_gross is not None and prev_gross > 0 and (gross <= 0 or (prev_gross - gross) / prev_gross * 100 >= SALES_DROP_PCT)
        units_down = prev_units is not None and (units_created <= 0 or (prev_units > 0 and (prev_units - units_created) / prev_units * 100 >= UNITS_DROP_PCT))
        many_skus_out = fraction_stockout >= SKU_STOCKOUT_THRESHOLD
        if sales_down and (units_down or units_created == 0) and many_skus_out:
            classification = "Likely supply-constrained"
            note = "Sales down; units created down or zero; many SKUs no current inventory."
        elif sales_down and (not units_down or units_created > 0) and (not many_skus_out or skus_with_stock > 0):
            classification = "Likely demand / outside factor"
            note = "Sales down but supply similar or higher; inventory present."
        elif sales_down:
            classification = "Unclear"
            note = "Sales down; supply/inventory signals mixed."
        else:
            classification = "-"
            note = "No significant sales drop vs prior month."
        rows_6m.append([month_name, round(gross, 2), line_count, units_created, classification, note])
        prev_gross = gross
        prev_units = units_created
    rows_6m.append([])
    rows_6m.append([f"ALL categories. Distinct SKUs: {num_skus}, with current stock: {skus_with_stock}."])
    rows_6m.append([f"Calculated: {now.strftime('%Y-%m-%d %H:%M UTC')}. Daily inventory reconstructed backwards from current package CurrentQty + sales."])

    # --- Daily Inventory Reconstructed sheet: Date, Total inv (end), Sales (units), Gross ($), then per-category sales ---
    categories_seen = set()
    for (_, cat) in sales_by_date_cat:
        categories_seen.add(cat)
    cat_list = sorted(categories_seen)
    daily_rows_cat_header = ["Date", "Total inv (end)", "Total sales", "Gross ($)"] + [f"Sales: {c}" for c in cat_list]
    daily_rows_with_cat = [daily_rows_cat_header]
    for date_key in sorted(inv_end_by_date_sku.keys(), reverse=True):
        row = [
            date_key,
            daily_total_inv_end.get(date_key, 0),
            sales_by_date.get(date_key, 0),
            round(gross_by_date.get(date_key, 0), 2),
        ]
        for c in cat_list:
            row.append(sales_by_date_cat.get((date_key, c), 0))
        daily_rows_with_cat.append(row)

    # --- Daily by SKU (optional, can be large) ---
    sku_rows = [["Date", "SKU", "Inventory end of day", "Sales that day"]]
    for date_key in sorted(inv_end_by_date_sku.keys(), reverse=True)[:92]:  # last ~3 months to limit size
        for sku in sorted(inv_end_by_date_sku[date_key].keys()):
            end_qty = inv_end_by_date_sku[date_key].get(sku, 0)
            sales_qty = sales_by_date_sku.get((date_key, sku), 0)
            if end_qty == 0 and sales_qty == 0:
                continue
            sku_rows.append([date_key, sku, end_qty, sales_qty])

    if not args.no_sheet:
        try:
            service = get_sheets_service(args.sheets_service_account)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        # Tab 1: Inventory vs Sales (6m) All
        ensure_sheet(service, SPREADSHEET_ID, "Inventory vs Sales (6m) All")
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="'Inventory vs Sales (6m) All'!A1:F" + str(len(rows_6m)),
            valueInputOption="USER_ENTERED",
            body={"values": rows_6m},
        ).execute()
        print("Wrote tab: Inventory vs Sales (6m) All")
        # Tab 2: Daily Inventory Reconstructed (with category sales columns)
        ensure_sheet(service, SPREADSHEET_ID, "Daily Inventory Reconstructed")
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="'Daily Inventory Reconstructed'!A1:" + _col_letter(4 + len(cat_list)) + str(len(daily_rows_with_cat)),
            valueInputOption="USER_ENTERED",
            body={"values": daily_rows_with_cat},
        ).execute()
        print("Wrote tab: Daily Inventory Reconstructed")
        if not args.no_daily_by_sku and len(sku_rows) <= 50000:
            ensure_sheet(service, SPREADSHEET_ID, "Daily Inventory by SKU")
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range="'Daily Inventory by SKU'!A1:D" + str(len(sku_rows)),
                valueInputOption="USER_ENTERED",
                body={"values": sku_rows},
            ).execute()
            print("Wrote tab: Daily Inventory by SKU")
        print(f"Spreadsheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    else:
        print("(No sheet write; use without --no-sheet to write.)")

    print(f"All categories: {len(order_nodes)} order lines, {len(package_nodes)} packages, {num_skus} SKUs, {skus_with_stock} with stock.")


if __name__ == "__main__":
    main()
