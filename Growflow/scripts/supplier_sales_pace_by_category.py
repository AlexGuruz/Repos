"""
Units/day by ProductCategory for products whose Supplier matches (Growflow Retail API).

Reuses: findProducts (objectId + Supplier), findOrderItems (SoldAt chunks, ProductCategory on line),
lib.allocate_stock_pool (date chunks, line dedupe), lib.growflow_queries (ORDER_ITEMS_QUERY).

Window modes (store TZ from config / ``GROWFLOW_SALES_TZ``):

- **Trailing strict:** ``--window-days N`` and ``--exclude-recent-days K`` → exactly **N** inclusive
  local days ending **K** calendar days before today (today and the prior **K-1** days are excluded when **K>=1**;
  for **K=5**, sales through **today-5** local are included, the last **5** local days are not).
- **Legacy:** omit ``--window-days`` → ``--since`` through end of **today** local.

Units: 1 order line = 1 unit (repo convention; see docs/GROWFLOW_PLANNER_DATA_MAPPING.md).

Usage (repo root):
  PYTHONPATH=. python scripts/supplier_sales_pace_by_category.py
  PYTHONPATH=. python scripts/supplier_sales_pace_by_category.py --supplier "HIGH SOLUTIONS, LLC" --since 2026-03-21 --csv-out data/supplier_category_pace.csv
  PYTHONPATH=. python scripts/supplier_sales_pace_by_category.py --window-days 30 --exclude-recent-days 5 --csv-out data/supplier_category_pace_30d.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.growflow_graphql import graphql_request
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    fetch_paginated,
)

PRODUCTS_SUPPLIER_QUERY = """
query ProductsSupplier($first: Int, $after: String) {
  findProducts(first: $first, after: $after) {
    edges {
      node {
        objectId
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


def _store_tz() -> ZoneInfo | timezone:
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
    cfg = _root / "config" / "config.yaml"
    if cfg.is_file():
        y = _yaml_scalar(cfg.read_text(encoding="utf-8", errors="replace"), "credentials_path")
        if y and Path(y).expanduser().is_file():
            return str(Path(y).expanduser())
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _supplier_name(supplier: object) -> str:
    if supplier is None:
        return ""
    if isinstance(supplier, dict):
        return str(supplier.get("Name") or "").strip()
    return str(supplier).strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().upper())


def _product_ids_for_supplier(credentials_path: str | None, target_norm: str) -> set[str]:
    out: set[str] = set()
    after: str | None = None
    while True:
        variables: dict[str, object] = {"first": PAGE_SIZE}
        if after:
            variables["after"] = after
        resp = graphql_request(PRODUCTS_SUPPLIER_QUERY, variables, credentials_path=credentials_path)
        errs = resp.get("errors")
        if errs:
            msg = errs[0].get("message", str(errs)) if isinstance(errs, list) else str(errs)
            raise RuntimeError(msg)
        conn = (resp.get("data") or {}).get("findProducts") or {}
        for e in conn.get("edges") or []:
            n = e.get("node") or {}
            if _norm(_supplier_name(n.get("Supplier"))) != target_norm:
                continue
            oid = str(n.get("objectId") or "").strip()
            if oid:
                out.add(oid)
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        after = page.get("endCursor")
        if not after:
            break
    return out


def _category_name(node: dict) -> str:
    pc = node.get("ProductCategory") or {}
    if isinstance(pc, dict):
        return str(pc.get("Name") or "").strip() or "(no category)"
    return "(no category)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Supplier sales pace (units/day) by ProductCategory")
    ap.add_argument("--supplier", default="HIGH SOLUTIONS, LLC", help="Supplier display name (normalized match)")
    ap.add_argument(
        "--since",
        default="2026-03-21",
        help="Start date YYYY-MM-DD (store-local inclusive); used only when --window-days is omitted",
    )
    ap.add_argument(
        "--window-days",
        type=int,
        default=None,
        metavar="N",
        help="If set: exactly N inclusive local days of sales; end date is today minus --exclude-recent-days",
    )
    ap.add_argument(
        "--exclude-recent-days",
        type=int,
        default=0,
        metavar="K",
        help="With --window-days: drop the last K local calendar days before counting (default 0)",
    )
    ap.add_argument("--chunk-days", type=int, default=14, help="SoldAt slice size for findOrderItems")
    ap.add_argument("--credentials", default=None, help="Growflow credentials file (default: config or env)")
    ap.add_argument("--csv-out", default=None, help="Optional path to write category rows CSV")
    args = ap.parse_args()

    _load_org()
    cp = args.credentials or _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: Growflow credentials not found.", file=sys.stderr)
        sys.exit(1)

    tz = _store_tz()
    target_n = _norm(args.supplier)
    today_local: date = datetime.now(tz).date()

    if args.window_days is not None:
        if args.window_days < 1:
            print("ERROR: --window-days must be >= 1", file=sys.stderr)
            sys.exit(2)
        if args.exclude_recent_days < 0:
            print("ERROR: --exclude-recent-days must be >= 0", file=sys.stderr)
            sys.exit(2)
        end_local = today_local - timedelta(days=args.exclude_recent_days)
        start_local_date = end_local - timedelta(days=args.window_days - 1)
        if start_local_date > end_local:
            print("ERROR: computed start after end (check --window-days / --exclude-recent-days)", file=sys.stderr)
            sys.exit(2)
        start_local = datetime(
            start_local_date.year, start_local_date.month, start_local_date.day, 0, 0, 0, tzinfo=tz
        )
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = datetime(
            end_local.year, end_local.month, end_local.day, 23, 59, 59, 999000, tzinfo=tz
        ).astimezone(timezone.utc)
        days_inclusive = args.window_days
        since_label = start_local_date.isoformat()
        through_label = end_local.isoformat()
    else:
        y, mo, d = map(int, args.since.split("-"))
        start_local = datetime(y, mo, d, 0, 0, 0, tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_local = today_local
        end_utc = datetime(
            end_local.year, end_local.month, end_local.day, 23, 59, 59, 999000, tzinfo=tz
        ).astimezone(timezone.utc)
        days_inclusive = (end_local - start_local.date()).days + 1
        if days_inclusive < 1:
            days_inclusive = 1
        since_label = args.since
        through_label = end_local.isoformat()

    product_ids = _product_ids_for_supplier(cp, target_n)
    if not product_ids:
        print(f"No products for supplier match {args.supplier!r}.")
        sys.exit(0)

    units_by_cat: dict[str, int] = defaultdict(int)
    seen: set[str] = set()

    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days=args.chunk_days):
        where = {"SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti}}
        base = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY, base, credentials_path=cp)
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY_NO_BRAND, base, credentials_path=cp)
            else:
                raise
        for n in nodes:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            prod = n.get("Product") or {}
            oid = str(prod.get("objectId") or "").strip()
            if oid not in product_ids:
                continue
            units_by_cat[_category_name(n)] += 1

    total_u = sum(units_by_cat.values())
    rows: list[tuple[str, int, float]] = []
    for cat, u in sorted(units_by_cat.items(), key=lambda x: (-x[1], x[0].lower())):
        rows.append((cat, u, u / days_inclusive))

    print(f"Supplier: {args.supplier}")
    print(
        f"Store TZ: {getattr(tz, 'key', tz)}  |  Window: {since_label} .. {through_label} "
        f"({days_inclusive} local days, inclusive; denominator={days_inclusive})"
    )
    if args.window_days is not None:
        print(
            f"(strict trailing: window_days={args.window_days}, exclude_recent_days={args.exclude_recent_days})",
            flush=True,
        )
    print(f"Products (supplier): {len(product_ids)}  |  Order lines (units): {total_u}")
    print("")
    print("ProductCategory | Units | Units/day (window)")
    for cat, u, upd in rows:
        print(f"{cat} | {u} | {upd:.4f}")
    print(f"TOTAL | {total_u} | {total_u / days_inclusive:.4f}")

    if args.csv_out:
        outp = Path(args.csv_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "supplier",
                    "since_local",
                    "through_local",
                    "store_tz",
                    "window_days_inclusive",
                    "product_category",
                    "units",
                    "units_per_day",
                ]
            )
            for cat, u, upd in rows:
                w.writerow(
                    [
                        args.supplier,
                        since_label,
                        through_label,
                        str(getattr(tz, "key", tz)),
                        days_inclusive,
                        cat,
                        u,
                        f"{upd:.6f}",
                    ]
                )
            w.writerow(
                [
                    args.supplier,
                    since_label,
                    through_label,
                    str(getattr(tz, "key", tz)),
                    days_inclusive,
                    "TOTAL",
                    total_u,
                    f"{total_u / days_inclusive:.6f}",
                ]
            )
        print("", f"Wrote {outp}", sep="\n")


if __name__ == "__main__":
    main()
