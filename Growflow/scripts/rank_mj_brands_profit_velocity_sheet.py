"""
Rank **MJ-format** brands by combined **profit/day + units/day** over a trailing store-local window,
then write **Brand | Supplier** to Google Sheets **D:E** (same defaults as the export script).

Metrics (per brand, over ``--days``):
- **units/day** = (MJ order line count) / days  (Retail: 1 line ≈ 1 unit)
- **profit/day** = (sum of line margin in USD) / days, margin = (GrossPrice - COG)/100 when
  COG is present and 0 <= COG <= GrossPrice

**Rank score** (for sorting): normalize each dimension to [0,1] vs the best brand in the cohort
that period, then **score = profit_norm + units_norm** (equal weight). Row order = rank (best first).

Usage:
  PYTHONPATH=. python scripts/rank_mj_brands_profit_velocity_sheet.py
  PYTHONPATH=. python scripts/rank_mj_brands_profit_velocity_sheet.py --days 7 --chunk-days 14
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
    package_in_format_product_pool,
)
from lib.dashboard_sheets_env import load_dashboard_sheets_env_file
from lib.data_validation_gateway import validate_and_normalize
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    fetch_paginated,
)
from lib.stashbox_sheets_auth import sheets_service

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
    "infused",
)

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


def _brand_from_line(n: dict[str, Any]) -> str | None:
    prod = n.get("Product") or {}
    bo = prod.get("Brand")
    if isinstance(bo, dict) and (bo.get("Name") or "").strip():
        return str(bo["Name"]).strip()
    return None


def _line_margin_cents(n: dict[str, Any]) -> int:
    try:
        gp = int(n.get("GrossPrice") or 0)
    except (TypeError, ValueError):
        return 0
    cog = n.get("COG")
    try:
        cog_i = int(cog) if cog is not None else None
    except (TypeError, ValueError):
        return 0
    if cog_i is None or not (0 <= cog_i <= gp):
        return 0
    return gp - cog_i


def aggregate_mj_brands_sales(
    creds: str | None,
    tz: Any,
    *,
    days: int,
    chunk_days: int,
) -> tuple[dict[str, tuple[int, int]], list[dict[str, Any]]]:
    """
    Returns brand -> (line_count, margin_cents_sum).
    """
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)

    lines_ct: dict[str, int] = defaultdict(int)
    margin_cents: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    normalized_source_rows: list[dict[str, Any]] = []

    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days):
        where = {"SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti}}
        base = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY, base, credentials_path=creds)
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated(
                    "findOrderItems", ORDER_ITEMS_QUERY_NO_BRAND, base, credentials_path=creds
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
            b = _brand_from_line(n)
            if not b:
                continue
            lines_ct[b] += 1
            margin_cents[b] += _line_margin_cents(n)
            normalized_source_rows.append(n)

    return ({b: (lines_ct[b], margin_cents[b]) for b in lines_ct}, normalized_source_rows)


def _suppliers_for_brands(creds: str | None, brands: set[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    nodes = fetch_paginated(
        "findProducts",
        PRODUCTS_BRAND_SUPPLIER_MJ_QUERY,
        {"first": PAGE_SIZE},
        credentials_path=creds,
    )
    for n in nodes:
        pr = n or {}
        b = str(((pr.get("Brand") or {}).get("Name")) or "").strip()
        if not b or b not in brands:
            continue
        if not _is_mj_product_node(pr):
            continue
        sn = _supplier_name(pr.get("Supplier"))
        if sn:
            out[b].add(sn)
    return dict(out)


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
    ap = argparse.ArgumentParser(
        description="Rank MJ brands by profit/day + units/day → Google Sheet D:E"
    )
    ap.add_argument(
        "--spreadsheet-id",
        default="1NL9y3Jj1mcgR1aTFsiYEY6foTzDiPtBNHwMb4kUEbSU",
    )
    ap.add_argument("--sheet-gid", type=int, default=1572737988)
    ap.add_argument("--range-start", default="D1")
    ap.add_argument("--days", type=int, default=7, help="Trailing store-local calendar days")
    ap.add_argument("--chunk-days", type=int, default=30, help="SoldAt chunk size for API")
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument(
        "--validation-mode",
        choices=("strict", "warning", "discovery"),
        default="strict",
        help="Validation gateway mode (strict fail-closed by default).",
    )
    args = ap.parse_args()

    _load_org()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: Growflow credentials not found.", file=sys.stderr)
        sys.exit(1)

    tz = _store_tz()
    d = max(1, int(args.days))
    print(
        f"Ranking MJ brands: trailing {d} store-local days ({tz}), "
        f"score = norm(profit/day) + norm(units/day).",
        flush=True,
    )

    agg, validation_rows = aggregate_mj_brands_sales(cp, tz, days=d, chunk_days=max(1, args.chunk_days))
    if not agg:
        print("No MJ sales lines in window; nothing to write.", file=sys.stderr)
        sys.exit(1)
    validation = validate_and_normalize(
        metric_id="brand_profit_velocity",
        template_id="order_items_brand_profit_velocity_v1",
        raw_json={"data": {"findOrderItems": {"edges": [{"node": r} for r in validation_rows]}}},
        request_context={
            "requested_date_range": {"from": None, "to": None},
            "days": d,
            "source_script": "scripts/rank_mj_brands_profit_velocity_sheet.py",
        },
        mode=args.validation_mode,
    )
    print(f"Validation report: {validation.get('report_path')}")
    if not validation.get("ok"):
        print(f"Validation blocked trusted output: {validation.get('errors')}", file=sys.stderr)
        sys.exit(1)

    profit_per_day: dict[str, float] = {}
    units_per_day: dict[str, float] = {}
    for b, (lc, mc) in agg.items():
        units_per_day[b] = lc / float(d)
        profit_per_day[b] = (mc / 100.0) / float(d)

    p_max = max(profit_per_day.values()) if profit_per_day else 0.0
    u_max = max(units_per_day.values()) if units_per_day else 0.0

    scored: list[tuple[str, float, float, float]] = []
    for b in agg:
        pn = (profit_per_day[b] / p_max) if p_max > 0 else 0.0
        un = (units_per_day[b] / u_max) if u_max > 0 else 0.0
        score = pn + un
        scored.append((b, score, profit_per_day[b], units_per_day[b]))

    scored.sort(
        key=lambda x: (-x[1], -x[2], -x[3], x[0].lower()),
    )

    brands_set = {t[0] for t in scored}
    sup_map = _suppliers_for_brands(cp, brands_set)

    values: list[list[str]] = [["Brand", "Supplier"]]
    for b, _sc, _ppd, _upd in scored:
        su = sup_map.get(b, set())
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
    print(f"Wrote {len(values)} rows (ranked, incl. header) to {range_a1}", flush=True)
    print(f"Top brand: {scored[0][0]}  score={scored[0][1]:.3f}  profit/day=${scored[0][2]:.2f}  units/day={scored[0][3]:.2f}", flush=True)
    print(url, flush=True)


if __name__ == "__main__":
    main()
