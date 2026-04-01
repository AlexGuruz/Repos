"""
Export prepackaged flower sales metrics to a new Google Sheet.

- Fetches last 2 months of order items (category: prepackaged flower).
- Aggregates by strain: Net $, Gross $, Grams sold, Line count.
- Age = days since the first sale of that strain (in the 2-month window).
- Creates a new Google spreadsheet using the Stashbox GCP service account and writes the table.
- Shares the sheet with alexstonedz@stonedprojects.com (writer access).

Usage:
  python prepackaged_flower_metrics_to_sheet.py --sheets-service-account "E:\\secrets\\gcp\\stashbox.json"
  python prepackaged_flower_metrics_to_sheet.py  # uses GOOGLE_APPLICATION_CREDENTIALS or config

Growflow API credentials: GROWFLOW_CREDENTIALS_PATH or --growflow-credentials.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root for lib imports
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

PREPACKAGED_FLOWER_CATEGORY = "prepackaged flower"
SHARE_EMAIL = "alexstonedz@stonedprojects.com"

UOM_TO_GRAMS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
}


def weight_to_grams(amount: float | None, uom: str | None) -> float:
    if amount is None:
        return 0.0
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if not uom or not str(uom).strip():
        return val
    key = (uom or "").strip().lower()
    return val * UOM_TO_GRAMS.get(key, 1.0)


def parse_iso(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_service_account_path(service_account_path: str | None = None) -> str:
    """Resolve path to GCP service account JSON."""
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
            "Google service account JSON not found. Set --sheets-service-account or "
            "GOOGLE_APPLICATION_CREDENTIALS to the stashbox (or other) GCP service account path."
        )
    return path


def get_sheets_service(service_account_path: str | None = None):
    """Build Google Sheets API v4 service. Uses stashbox/service account path if provided."""
    path = _get_service_account_path(service_account_path)
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    _SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(path, scopes=_SHEETS_SCOPE)
    return build("sheets", "v4", credentials=creds)


def share_spreadsheet_with_email(
    service_account_path: str | None,
    spreadsheet_id: str,
    email: str,
    role: str = "writer",
) -> None:
    """Share the spreadsheet (Drive file) with the given email via Drive API."""
    path = _get_service_account_path(service_account_path)
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    _DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(path, scopes=_DRIVE_SCOPE)
    drive = build("drive", "v3", credentials=creds)
    body = {
        "type": "user",
        "role": role,
        "emailAddress": email,
    }
    drive.permissions().create(
        fileId=spreadsheet_id,
        body=body,
        sendNotificationEmail=True,
        fields="id",
    ).execute()


def create_new_spreadsheet(service, title: str):
    """Create a new spreadsheet; returns (spreadsheet_id, spreadsheet_url)."""
    body = {"properties": {"title": title}}
    result = service.spreadsheets().create(body=body).execute()
    return result.get("spreadsheetId"), result.get("spreadsheetUrl", "")


def main() -> None:
    ap = argparse.ArgumentParser(description="Export prepackaged flower metrics to a new Google Sheet")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow API credentials file")
    ap.add_argument(
        "--sheets-service-account",
        default=None,
        help="Path to GCP service account JSON (e.g. stashbox). Overrides GOOGLE_APPLICATION_CREDENTIALS.",
    )
    args = ap.parse_args()

    growflow_creds = args.growflow_credentials or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
    if not growflow_creds and Path("E:/secrets/gcp/growflowapi.txt").exists():
        growflow_creds = "E:/secrets/gcp/growflowapi.txt"

    # Date range: last 2 months
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=60)
    from_iso = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    where = date_range_to_where("SoldAt", from_iso, to_iso)

    print("Fetching order items (last 2 months)...", flush=True)
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

    category_lower = PREPACKAGED_FLOWER_CATEGORY.strip().lower()
    by_strain: dict[str, dict] = defaultdict(lambda: {
        "net_cents": 0,
        "gross_cents": 0,
        "grams_sold": 0.0,
        "line_count": 0,
        "first_sold_at": None,
    })

    for node in nodes:
        cat = (node.get("ProductCategory") or {}).get("Name") or ""
        if category_lower not in (cat or "").lower():
            continue
        product = node.get("Product") or {}
        strain = (product.get("Name") or "").strip() or "Unknown"
        by_strain[strain]["net_cents"] += node.get("NetPrice") or 0
        by_strain[strain]["gross_cents"] += node.get("GrossPrice") or 0
        grams = weight_to_grams(node.get("NetWeight"), node.get("NetWeightUOM"))
        if grams <= 0:
            grams = weight_to_grams(node.get("UnitWeight"), node.get("UnitWeightUOM"))
        by_strain[strain]["grams_sold"] += grams
        by_strain[strain]["line_count"] += 1
        sold_at = parse_iso(node.get("SoldAt"))
        if sold_at:
            prev = by_strain[strain]["first_sold_at"]
            if prev is None or sold_at < prev:
                by_strain[strain]["first_sold_at"] = sold_at

    # Age = days since first sale of that strain (in this window)
    for strain, data in by_strain.items():
        first = data.get("first_sold_at")
        if first is not None:
            data["age_days"] = (end_date - first).days
        else:
            data["age_days"] = None

    sorted_strains = sorted(
        by_strain.keys(),
        key=lambda s: by_strain[s]["net_cents"],
        reverse=True,
    )

    if not sorted_strains:
        print("No prepackaged flower order items in the date range.", file=sys.stderr)
        sys.exit(1)

    # Build sheet rows: Strain, Net $, Gross $, Grams, Age (days), First sale date, Lines
    headers = ["Strain", "Net $", "Gross $", "Grams Sold", "Age (days)", "First Sale Date", "Line Count"]
    rows = [headers]
    for strain in sorted_strains:
        d = by_strain[strain]
        first = d.get("first_sold_at")
        first_str = first.strftime("%Y-%m-%d") if first else ""
        age = d.get("age_days")
        age_str = str(age) if age is not None else ""
        rows.append([
            strain,
            round(d["net_cents"] / 100.0, 2),
            round(d["gross_cents"] / 100.0, 2),
            round(d["grams_sold"], 2),
            age_str,
            first_str,
            d["line_count"],
        ])
    # Total row
    total_net = sum(by_strain[s]["net_cents"] for s in sorted_strains) / 100.0
    total_gross = sum(by_strain[s]["gross_cents"] for s in sorted_strains) / 100.0
    total_grams = sum(by_strain[s]["grams_sold"] for s in sorted_strains)
    total_lines = sum(by_strain[s]["line_count"] for s in sorted_strains)
    rows.append(["TOTAL", round(total_net, 2), round(total_gross, 2), round(total_grams, 2), "", "", total_lines])

    print("Creating new Google Sheet with Stashbox service account...", flush=True)
    try:
        service = get_sheets_service(args.sheets_service_account)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    title = f"Prepackaged Flower Metrics ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
    try:
        spreadsheet_id, spreadsheet_url = create_new_spreadsheet(service, title)
    except Exception as e:
        print(f"Failed to create spreadsheet: {e}", file=sys.stderr)
        sys.exit(1)

    range_name = f"Sheet1!A1:G{len(rows)}"
    body = {"values": rows}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()

    print("Sharing with {}...".format(SHARE_EMAIL), flush=True)
    try:
        share_spreadsheet_with_email(args.sheets_service_account, spreadsheet_id, SHARE_EMAIL)
        print("Shared (writer access).", flush=True)
    except Exception as e:
        print("Warning: could not share spreadsheet: {}".format(e), file=sys.stderr)

    print()
    print("Done.")
    print(f"New spreadsheet: {spreadsheet_url}")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Wrote {len(rows)-1} strain rows + total ({len(sorted_strains)} strains).")


if __name__ == "__main__":
    main()
