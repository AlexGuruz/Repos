"""
Project gross for the last 6 months; add a new tab to the prepackaged flower spreadsheet.

- Fetches all order items for the last 6 months (SoldAt) from Growflow API.
- For each month: actual gross (sum GrossPrice), order line count, days in month, daily avg.
- For current month only: projects month-end gross if pace maintained (daily_avg * days_in_month).
- Adds a new sheet "Last 6 Months Gross" with one row per month.

Usage:
  python monthly_gross_projection_to_sheet.py
  python monthly_gross_projection_to_sheet.py --growflow-credentials "E:\\secrets\\gcp\\growflowapi.txt" --sheets-service-account "E:\\secrets\\gcp\\sa.json"
"""
from __future__ import annotations

import argparse
import os
import sys
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __name__ == "__main__" and "__file__" in dir():
    _root = Path(__file__).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)

SPREADSHEET_ID = "13Wm3UdCdvzw6lpYUDIs-J2UOiRO42oNxE8wKzVyCqRA"
NUM_MONTHS = 6


def _get_service_account_path(service_account_path: str | None = None) -> str:
    path = service_account_path
    if not path:
        path = os.environ.get("STASHBOX_SERVICE_ACCOUNT", "").strip() or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not path:
        from lib.config_loader import get_google_service_account_path
        p = get_google_service_account_path()
        path = str(p) if p else None
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
    """Ensure a sheet with the given title exists; create if missing. Returns the sheet title for range."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))").execute()
    sheets = meta.get("sheets") or []
    for s in sheets:
        props = s.get("properties") or {}
        if (props.get("title") or "").strip() == title:
            return title
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    return title


def _parse_sold_at(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Last 6 months gross (actual + current month projection), add tab")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow API credentials")
    ap.add_argument("--sheets-service-account", default=None, help="Path to GCP service account JSON")
    args = ap.parse_args()

    growflow_creds = args.growflow_credentials or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
    if not growflow_creds and Path("E:/secrets/gcp/growflowapi.txt").exists():
        growflow_creds = "E:/secrets/gcp/growflowapi.txt"

    now = datetime.now(timezone.utc)
    cur_year, cur_month = now.year, now.month

    # Last 6 calendar months (oldest first): e.g. Oct, Nov, Dec, Jan, Feb, Mar
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
    where = date_range_to_where("SoldAt", from_iso, to_iso)

    print("Fetching order items for the last 6 months...", flush=True)
    try:
        nodes = fetch_paginated(
            "findOrderItems",
            ORDER_ITEMS_QUERY,
            {"first": PAGE_SIZE, "where": where},
            credentials_path=growflow_creds,
        )
    except Exception as e:
        print(f"Error fetching order items: {e}", file=sys.stderr)
        sys.exit(1)

    # Bucket by (year, month)
    by_month: dict[tuple[int, int], list] = {}
    for n in nodes:
        sold = _parse_sold_at(n.get("SoldAt"))
        if not sold:
            continue
        key = (sold.year, sold.month)
        if key not in by_month:
            by_month[key] = []
        by_month[key].append(n)

    # Build one row per month (oldest first)
    headers = ["Month", "Gross ($)", "Order lines", "Days in month", "Daily avg ($)", "Note"]
    rows = [headers]
    for (y, m) in month_list:
        month_name = datetime(y, m, 1).strftime("%B %Y")
        days_in_month = monthrange(y, m)[1]
        items = by_month.get((y, m), [])
        gross_cents = sum(i.get("GrossPrice") or 0 for i in items)
        gross = gross_cents / 100.0
        line_count = len(items)

        is_current = (y == cur_year and m == cur_month)
        if is_current:
            month_start = datetime(y, m, 1, 0, 0, 0, tzinfo=timezone.utc)
            days_elapsed = (now.date() - month_start.date()).days + 1
            if days_elapsed <= 0:
                days_elapsed = 1
            daily_avg = gross / days_elapsed if days_elapsed else 0
            projected = daily_avg * days_in_month
            gross_display = round(projected, 2)
            note = "Projected (pace maintained)"
        else:
            daily_avg = gross / days_in_month if days_in_month else 0
            gross_display = round(gross, 2)
            note = "Actual"

        rows.append([
            month_name,
            gross_display,
            line_count,
            days_in_month,
            round(daily_avg, 2),
            note,
        ])

    total_gross = sum(r[1] for r in rows[1:])
    total_lines = sum(r[2] for r in rows[1:])
    rows.append(["TOTAL", round(total_gross, 2), total_lines, "", "", ""])

    rows.append([])
    rows.append(["Source: Growflow API, order items SoldAt. Current month = projected if pace maintained."])
    rows.append([f"Calculated: {now.strftime('%Y-%m-%d %H:%M UTC')}"])

    sheet_title = "Last 6 Months Gross"
    print("Adding new tab and writing table...", flush=True)
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

    print()
    print("Done.")
    print(f"New tab: \"{sheet_title}\"")
    for r in rows[1:-3]:
        if r[0] != "TOTAL":
            print(f"  {r[0]}: ${r[1]:,.2f} ({r[4]})")
    print(f"Total: ${total_gross:,.2f}")
    print(f"Spreadsheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()
