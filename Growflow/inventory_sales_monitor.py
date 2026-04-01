"""
Ongoing inventory vs sales monitor: rolling window alerts.

- For a rolling window (default last 90 days), computes daily gross and a simplified
  inventory status (do we have open packages for key SKUs / category?).
- Flags:
  - Demand signal: X-day rolling sales drop (e.g. 20–30%) while inventory is healthy.
  - Supply signal: sales flatten or drop right as inventory approaches zero (stockout risk).
- Writes results to CSV and optionally to a sheet tab "Inventory vs Sales Alerts".
- Intended to run daily or weekly via Task Scheduler / cron.

Usage:
  python inventory_sales_monitor.py
  python inventory_sales_monitor.py --days 60 --sales-drop-pct 25 --output alerts.csv
  python inventory_sales_monitor.py --write-sheet
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
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
DEFAULT_ROLLING_DAYS = 90
SALES_DROP_PCT_DEFAULT = 25.0
ROLLING_WINDOW_DAYS = 14   # compare last N days to previous N days for "drop"
LOW_INVENTORY_UNITS = 10   # "inventory approaching zero" if total current units <= this


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


def _category_matches(category_name: str | None, filter_substring: str) -> bool:
    if not filter_substring:
        return True
    name = (category_name or "").strip().lower()
    return filter_substring.strip().lower() in name


def main() -> None:
    ap = argparse.ArgumentParser(description="Rolling inventory vs sales monitor; output alerts to CSV/sheet")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow API credentials")
    ap.add_argument("--sheets-service-account", default=None, help="Path to GCP service account JSON")
    ap.add_argument("--days", type=int, default=DEFAULT_ROLLING_DAYS, help="Rolling window days")
    ap.add_argument("--sales-drop-pct", type=float, default=SALES_DROP_PCT_DEFAULT, help="Rolling sales drop %% to flag")
    ap.add_argument("--category", default="", help="Category filter substring; default all categories")
    ap.add_argument("--output", default=None, help="Output CSV path (default: inventory_sales_alerts_YYYYMMDD.csv)")
    ap.add_argument("--write-sheet", action="store_true", help="Also write to sheet tab Inventory vs Sales Alerts")
    args = ap.parse_args()

    growflow_creds = args.growflow_credentials or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
    if not growflow_creds and Path("E:/secrets/gcp/growflowapi.txt").exists():
        growflow_creds = "E:/secrets/gcp/growflowapi.txt"

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=args.days)
    from_iso = start_dt.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = now.strftime("%Y-%m-%dT23:59:59.999Z")
    where_sold = date_range_to_where("SoldAt", from_iso, to_iso)
    where_created = date_range_to_where("createdAt", from_iso, to_iso)

    print("Fetching order items...", flush=True)
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

    print("Fetching packages...", flush=True)
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

    category_filter = (args.category or "").strip() or None
    if category_filter:
        order_nodes = [n for n in order_nodes if _category_matches((n.get("ProductCategory") or {}).get("Name"), category_filter)]
        package_nodes = [n for n in package_nodes if _category_matches(((n.get("Product") or {}).get("ProductCategory") or {}).get("Name"), category_filter)]
    # Packages: we want current inventory (no date filter on "current"); use same window for consistency, then sum CurrentQty
    total_current_units = sum(n.get("CurrentQty") or 0 for n in package_nodes)
    skus_with_stock = set()
    for n in package_nodes:
        if (n.get("CurrentQty") or 0) > 0:
            sku = (n.get("Product") or {}).get("SKU") or n.get("SKU") or ""
            if sku:
                skus_with_stock.add(sku)
    inventory_healthy = total_current_units > LOW_INVENTORY_UNITS and len(skus_with_stock) > 0

    # Daily gross in window
    by_day: dict[str, float] = {}
    for n in order_nodes:
        sold = _parse_iso(n.get("SoldAt"))
        if not sold:
            continue
        day_key = sold.strftime("%Y-%m-%d")
        gross_cents = n.get("GrossPrice") or 0
        by_day[day_key] = by_day.get(day_key, 0) + gross_cents / 100.0

    # Rolling comparison: last ROLLING_WINDOW_DAYS vs previous ROLLING_WINDOW_DAYS
    sorted_days = sorted(by_day.keys())
    if len(sorted_days) < ROLLING_WINDOW_DAYS * 2:
        recent_gross = sum(by_day.get(d, 0) for d in sorted_days[-ROLLING_WINDOW_DAYS:]) if sorted_days else 0
        prior_gross = sum(by_day.get(d, 0) for d in sorted_days[:-ROLLING_WINDOW_DAYS][-ROLLING_WINDOW_DAYS:]) if len(sorted_days) > ROLLING_WINDOW_DAYS else 0
    else:
        recent_days = sorted_days[-ROLLING_WINDOW_DAYS:]
        prior_days = sorted_days[-(ROLLING_WINDOW_DAYS * 2):-ROLLING_WINDOW_DAYS]
        recent_gross = sum(by_day.get(d, 0) for d in recent_days)
        prior_gross = sum(by_day.get(d, 0) for d in prior_days)

    drop_pct = 0.0
    if prior_gross > 0:
        drop_pct = (prior_gross - recent_gross) / prior_gross * 100

    alerts = []
    reason_code = ""
    if drop_pct >= args.sales_drop_pct and inventory_healthy:
        reason_code = "DEMAND"
        alerts.append({
            "date": now.strftime("%Y-%m-%d"),
            "category": category_filter or "all",
            "sales_trend": f"Rolling {ROLLING_WINDOW_DAYS}d sales down {drop_pct:.1f}%",
            "inventory_status": "Healthy",
            "reason_code": reason_code,
            "note": "Sales drop with healthy inventory; likely demand or outside factor.",
        })
    elif drop_pct >= args.sales_drop_pct and not inventory_healthy:
        reason_code = "SUPPLY"
        alerts.append({
            "date": now.strftime("%Y-%m-%d"),
            "category": category_filter or "all",
            "sales_trend": f"Rolling {ROLLING_WINDOW_DAYS}d sales down {drop_pct:.1f}%",
            "inventory_status": "Low",
            "reason_code": reason_code,
            "note": "Sales drop with low inventory; possible stockout or supply bottleneck.",
        })
    elif total_current_units <= LOW_INVENTORY_UNITS and len(sorted_days) > 0:
        reason_code = "LOW_STOCK"
        alerts.append({
            "date": now.strftime("%Y-%m-%d"),
            "category": category_filter or "all",
            "sales_trend": f"Recent daily gross present",
            "inventory_status": "Low",
            "reason_code": reason_code,
            "note": f"Total current units ({total_current_units}) at or below threshold ({LOW_INVENTORY_UNITS}); monitor for stockout.",
        })

    if not alerts:
        alerts.append({
            "date": now.strftime("%Y-%m-%d"),
            "category": category_filter or "all",
            "sales_trend": f"Rolling {ROLLING_WINDOW_DAYS}d: no significant drop",
            "inventory_status": "Healthy" if inventory_healthy else "Low",
            "reason_code": "OK",
            "note": "No alert.",
        })

    # CSV
    out_path = args.output
    if not out_path:
        out_path = Path(__file__).resolve().parent / f"inventory_sales_alerts_{now.strftime('%Y%m%d')}.csv"
    else:
        out_path = Path(out_path)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "category", "sales_trend", "inventory_status", "reason_code", "note"])
        w.writeheader()
        w.writerows(alerts)
    print(f"Wrote {len(alerts)} row(s) to {out_path}")

    if args.write_sheet:
        sheet_title = "Inventory vs Sales Alerts"
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
        sheet_rows = [["Date", "Category", "Sales trend", "Inventory status", "Reason code", "Note"]]
        for a in alerts:
            sheet_rows.append([a["date"], a["category"], a["sales_trend"], a["inventory_status"], a["reason_code"], a["note"]])
        range_name = f"'{sheet_title}'!A1:F{len(sheet_rows)}"
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": sheet_rows},
        ).execute()
        print(f"Updated sheet tab: \"{sheet_title}\"")

    for a in alerts:
        print(f"  [{a['reason_code']}] {a['note']}")
    print("Done.")


if __name__ == "__main__":
    main()
