"""
Export **MJ-format** brands (planner product pool + flower/concentrate-style categories) that appear
on **inventory or sales in the trailing 12 months**, with supplier names from `findProducts` → `Supplier`.

Brand universe (union):
- **findPackages** with `createdAt` in the last **365** store-calendar days (chunked), MJ only
- **findOrderItems** with `SoldAt` in that same window (chunked), MJ only
- **findPackages** with `CurrentQty > 0` today (if the API accepts the filter), MJ only

Supplier column: distinct `Supplier.Name` per brand from **MJ** `findProducts` rows only (same brand set
or any product for that brand — restricted to MJ product rows).

Retail GraphQL does not expose `Supplier` on `findBrands`.

Usage (repo root):
  PYTHONPATH=. python scripts/export_brand_suppliers_to_sheet.py

Share the spreadsheet with the Stashbox service account client_email (Editor).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.brand_merit_pool import (
    category_matches_format_substrings,
    order_line_in_format_product_pool,
    order_line_product_category_name,
    package_brand,
    package_in_format_product_pool,
    package_product_category_name,
)
from lib.dashboard_sheets_env import load_dashboard_sheets_env_file
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)
from lib.stashbox_sheets_auth import sheets_service

# Substrings on ProductCategory.Name (case-insensitive) for MJ catalog not covered by preroll/vape/edible pool.
EXTRA_MJ_CATEGORY_SUBSTRINGS: tuple[str, ...] = (
    "flower",
    "concentrate",
    "extract",
    "rosin",
    "hash",
    "prepack",
    "pre-pack",
    "prepackaged",
    "bulk flower",
    "shake",
    "trim",
    "kief",
    "infused",  # e.g. infused flower category
)

PACKAGES_WITH_BRAND = """
query PackagesBrand($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        createdAt
        CurrentQty
        Product {
          Name
          ProductCategory { Name }
          Brand { Name }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

PRODUCTS_BRAND_SUPPLIER_MJ_QUERY = """
query ProductsBrandSupplierMj($first: Int, $after: String) {
  findProducts(first: $first, after: $after) {
    edges {
      node {
        Name
        ProductCategory { Name }
        Brand {
          Name
        }
        Supplier
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def _load_org() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = _root / "config" / "config.yaml"
    if cfg.is_file():
        t = cfg.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^\s*org_id:\s*["\']?([^"\'#\n]+)', t, re.MULTILINE)
        if m:
            os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def _store_tz():
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = _root / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.now(timezone.utc).astimezone().tzinfo or timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _supplier_name(supplier: Any) -> str:
    if supplier is None:
        return ""
    if isinstance(supplier, dict):
        return str(supplier.get("Name") or "").strip()
    return str(supplier).strip()


def _is_mj_package(pkg: dict[str, Any]) -> bool:
    if package_in_format_product_pool(pkg):
        return True
    cat = package_product_category_name(pkg)
    return category_matches_format_substrings(cat, EXTRA_MJ_CATEGORY_SUBSTRINGS)


def _is_mj_order_line(n: dict[str, Any]) -> bool:
    if order_line_in_format_product_pool(n):
        return True
    cat = order_line_product_category_name(n)
    return category_matches_format_substrings(cat, EXTRA_MJ_CATEGORY_SUBSTRINGS)


def _is_mj_product_node(pr: dict[str, Any]) -> bool:
    fake_pkg = {"Product": pr}
    if package_in_format_product_pool(fake_pkg):
        return True
    cat = str(((pr.get("ProductCategory") or {}) or {}).get("Name") or "")
    return category_matches_format_substrings(cat, EXTRA_MJ_CATEGORY_SUBSTRINGS)


def _collect_brands_from_packages_created(
    creds: str | None,
    *,
    days_back: int,
    chunk_days: int,
) -> set[str]:
    brands: set[str] = set()
    now = datetime.now(timezone.utc)
    chunk_start = now
    chunk_num = 0
    while chunk_num * chunk_days < days_back:
        chunk_end = chunk_start - timedelta(days=chunk_days)
        from_pkg = chunk_end.strftime("%Y-%m-%dT00:00:00.000Z")
        to_pkg = chunk_start.strftime("%Y-%m-%dT23:59:59.999Z")
        where_pkg = date_range_to_where("createdAt", from_pkg, to_pkg)
        chunk = fetch_paginated(
            "findPackages",
            PACKAGES_WITH_BRAND,
            {"first": PAGE_SIZE, "where": where_pkg},
            credentials_path=creds,
        )
        for pkg in chunk:
            if not _is_mj_package(pkg):
                continue
            b = package_brand(pkg, {})
            if b and b != "(no brand)":
                brands.add(b)
        chunk_start = chunk_end
        chunk_num += 1
    return brands


def _collect_brands_from_packages_on_hand(creds: str | None) -> set[str]:
    brands: set[str] = set()
    where = {"CurrentQty": {"greaterThan": 0}}
    try:
        chunk = fetch_paginated(
            "findPackages",
            PACKAGES_WITH_BRAND,
            {"first": PAGE_SIZE, "where": where},
            credentials_path=creds,
        )
    except RuntimeError:
        return brands
    for pkg in chunk:
        if not _is_mj_package(pkg):
            continue
        b = package_brand(pkg, {})
        if b and b != "(no brand)":
            brands.add(b)
    return brands


def _collect_brands_from_order_items(
    creds: str | None,
    tz: Any,
    *,
    days: int,
    chunk_days: int,
) -> set[str]:
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)

    brands: set[str] = set()
    seen: set[str] = set()
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days):
        where = {
            "SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
        }
        base = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated(
                "findOrderItems",
                ORDER_ITEMS_QUERY,
                base,
                credentials_path=creds,
            )
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated(
                    "findOrderItems",
                    ORDER_ITEMS_QUERY_NO_BRAND,
                    base,
                    credentials_path=creds,
                )
            else:
                raise
        for n in nodes:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            if not _is_mj_order_line(n):
                continue
            prod = n.get("Product") or {}
            bo = prod.get("Brand")
            if isinstance(bo, dict) and (bo.get("Name") or "").strip():
                brands.add(str(bo["Name"]).strip())
    return brands


def _sheet_title_for_gid(service: Any, spreadsheet_id: str, sheet_gid: int) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sh in meta.get("sheets", []):
        props = sh.get("properties") or {}
        if int(props.get("sheetId", -1)) == int(sheet_gid):
            return str(props.get("title") or "")
    raise SystemExit(f"No sheet with sheetId (gid)={sheet_gid} in spreadsheet {spreadsheet_id}")


def _a1_range_tab(tab_title: str, cell_a1: str) -> str:
    safe = str(tab_title).replace("'", "''")
    return f"'{safe}'!{cell_a1}"


def main() -> None:
    load_dashboard_sheets_env_file()
    ap = argparse.ArgumentParser(description="MJ brands (12mo stock/sales) + suppliers → Google Sheet")
    ap.add_argument(
        "--spreadsheet-id",
        default="1NL9y3Jj1mcgR1aTFsiYEY6foTzDiPtBNHwMb4kUEbSU",
        help="Google Spreadsheet ID",
    )
    ap.add_argument("--sheet-gid", type=int, default=1572737988, help="Tab gid from URL #gid=...")
    ap.add_argument("--range-start", default="D1", help="Top-left cell (two columns written)")
    ap.add_argument("--days", type=int, default=365, help="Trailing calendar days for sales + package createdAt")
    ap.add_argument("--chunk-days", type=int, default=30, help="SoldAt / package createdAt chunk size")
    ap.add_argument("--package-chunk-days", type=int, default=30, help="Days per findPackages createdAt slice")
    ap.add_argument("--sheets-service-account", default=None)
    args = ap.parse_args()

    _load_org()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: Growflow credentials not found.", file=sys.stderr)
        sys.exit(1)

    tz = _store_tz()
    print(
        f"Collecting MJ brands: last {args.days}d sales (store TZ {tz}), "
        f"packages created in same window, plus on-hand MJ packages (CurrentQty>0 if supported).",
        flush=True,
    )

    brands_sales = _collect_brands_from_order_items(cp, tz, days=args.days, chunk_days=args.chunk_days)
    print(f"  From order lines (MJ): {len(brands_sales)} brands", flush=True)

    brands_pkg = _collect_brands_from_packages_created(
        cp, days_back=args.days, chunk_days=args.package_chunk_days
    )
    print(f"  From packages created (MJ): {len(brands_pkg)} brands", flush=True)

    brands_oh = _collect_brands_from_packages_on_hand(cp)
    print(f"  From on-hand packages (MJ): {len(brands_oh)} brands", flush=True)

    brand_names = sorted(brands_sales | brands_pkg | brands_oh, key=str.lower)
    allowed = set(brand_names)
    print(f"  Union: {len(brand_names)} brands", flush=True)

    sup_by_brand: dict[str, set[str]] = defaultdict(set)
    nodes_p = fetch_paginated(
        "findProducts",
        PRODUCTS_BRAND_SUPPLIER_MJ_QUERY,
        {"first": PAGE_SIZE},
        credentials_path=cp,
    )
    for n in nodes_p:
        pr = n or {}
        b = str(((pr.get("Brand") or {}).get("Name")) or "").strip()
        if not b or b not in allowed:
            continue
        if not _is_mj_product_node(pr):
            continue
        sn = _supplier_name(pr.get("Supplier"))
        if sn:
            sup_by_brand[b].add(sn)

    values: list[list[str]] = [["Brand", "Supplier"]]
    for b in brand_names:
        su = sup_by_brand.get(b, set())
        values.append([b, "; ".join(sorted(su, key=str.lower)) if su else ""])

    service = sheets_service(args.sheets_service_account)
    title = _sheet_title_for_gid(service, args.spreadsheet_id, args.sheet_gid)
    m = re.match(r"^([A-Za-z]+)(\d+)$", args.range_start.strip())
    if not m:
        print("ERROR: --range-start must be like D1", file=sys.stderr)
        sys.exit(1)
    col, row_part = m.group(1).upper(), m.group(2)
    if len(col) != 1 or col < "A" or col > "Y":
        print("ERROR: --range-start column must be a single letter A–Y.", file=sys.stderr)
        sys.exit(1)
    start_row = int(row_part)
    end_row = start_row + len(values) - 1
    col2 = chr(ord(col) + 1)
    range_a1 = _a1_range_tab(title, f"{col}{start_row}:{col2}{end_row}")
    clear_a1 = _a1_range_tab(title, f"{col}:{col2}")

    service.spreadsheets().values().clear(
        spreadsheetId=args.spreadsheet_id,
        range=clear_a1,
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=args.spreadsheet_id,
        range=range_a1,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{args.spreadsheet_id}/edit#gid={args.sheet_gid}"
    print(f"Wrote {len(values)} rows (incl. header) to {range_a1}", flush=True)
    print(url, flush=True)


if __name__ == "__main__":
    main()
