"""
Split a fixed stock/reorder dollar pool across brands using last N months of sales.

Data source (per repo docs):
- company_bi/DESIGN.md — findOrderItems, SoldAt, GrossPrice, Product, ProductCategory
- company_bi/METRICS.md — revenue uses sum(GrossPrice)/100 (amounts are in cents)

Method: aggregate trailing gross sales by Product.Brand.Name (fallback: \"(no brand)\");
allocate the pool in proportion to each brand's share of total gross, with largest-remainder
rounding so dollar amounts sum exactly to the pool.

Usage:
  python allocate_stock_pool_by_brand.py
  python allocate_stock_pool_by_brand.py --pool 18000 --days 365
  python allocate_stock_pool_by_brand.py --growflow-credentials "E:/secrets/gcp/growflowapi.txt" --csv out.csv

Notes:
- Date chunks use **inclusive calendar days with no overlap** (avoids double-counting at boundaries).
- Optional **dedupe** on objectId/id drops duplicate lines if the API returns them twice.
- If the schema has no Brand on Product, retries without that field.
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

from lib.allocate_stock_pool import (
    aggregate_by_brand,
    allocate_pool_cents_largest_remainder,
    concentration_hhi,
    iter_sold_at_date_chunks,
    validate_allocation,
)
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _chunk_fetch_order_items(
    start: datetime,
    end: datetime,
    chunk_days: int,
    credentials_path: str | None,
    query: str,
) -> list[dict]:
    nodes: list[dict] = []
    for from_iso, to_iso in iter_sold_at_date_chunks(start, end, chunk_days):
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        chunk = fetch_paginated(
            "findOrderItems",
            query,
            {"first": PAGE_SIZE, "where": where},
            credentials_path=credentials_path,
        )
        nodes.extend(chunk)
    return nodes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Allocate a dollar pool across brands from GrowFlow findOrderItems (trailing sales)."
    )
    ap.add_argument("--pool", type=float, default=18_000.0, help="Total pool in dollars (default 18000)")
    ap.add_argument("--days", type=int, default=365, help="Trailing window in days (default 365)")
    ap.add_argument("--chunk-days", type=int, default=45, help="Max calendar days per API chunk (default 45)")
    ap.add_argument("--no-dedupe", action="store_true", help="Do not dedupe order lines by id")
    ap.add_argument("--growflow-credentials", default=None, help="Path to GrowFlow credentials file")
    ap.add_argument("--csv", default=None, help="Write breakdown CSV to this path")
    args = ap.parse_args()

    creds = (
        args.growflow_credentials
        or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
        or (str(Path("E:/secrets/gcp/growflowapi.txt")) if Path("E:/secrets/gcp/growflowapi.txt").exists() else None)
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    pool_cents = int(round(float(args.pool) * 100.0))

    query = ORDER_ITEMS_QUERY
    print(
        f"Fetching findOrderItems: {start.date()} .. {end.date()} ({args.days} days, "
        f"up to {args.chunk_days}d per chunk, no overlap)...",
        flush=True,
    )
    try:
        nodes = _chunk_fetch_order_items(start, end, args.chunk_days, creds, query)
    except RuntimeError as e:
        err = str(e).lower()
        if "brand" in err or "cannot query field" in err:
            print("Retrying without Product.Brand (schema may not expose Brand)...", flush=True)
            query = ORDER_ITEMS_QUERY_NO_BRAND
            nodes = _chunk_fetch_order_items(start, end, args.chunk_days, creds, query)
        else:
            raise

    if not nodes:
        print("No order items returned for this window. Check credentials, date range, and API access.")
        return 1

    dedupe = not args.no_dedupe
    by_brand_cents, lines_by_brand, dup_skipped = aggregate_by_brand(nodes, dedupe=dedupe)
    brands = sorted(by_brand_cents.keys(), key=lambda b: (-by_brand_cents[b], b))
    total_cents = sum(by_brand_cents.values())
    weights = [float(by_brand_cents[b]) for b in brands]
    allocated = allocate_pool_cents_largest_remainder(pool_cents, weights)
    issues = validate_allocation(pool_cents, allocated)

    shares = [by_brand_cents[b] / total_cents for b in brands] if total_cents else []
    hhi = concentration_hhi(shares) if shares else 0.0

    print()
    print("=" * 88)
    print("Stock / reorder pool allocation by brand (GrowFlow findOrderItems)")
    print("=" * 88)
    print(f"Docs: company_bi/DESIGN.md (findOrderItems), company_bi/METRICS.md (GrossPrice cents)")
    print(f"Window: last {args.days} days through {end.strftime('%Y-%m-%d')} UTC")
    print(f"Raw order lines fetched: {len(nodes)}")
    if dedupe and dup_skipped:
        print(f"Duplicate lines skipped (same objectId/id): {dup_skipped}")
    print(f"Lines used in totals: {sum(lines_by_brand.values())}")
    print(f"Distinct brands (or \"(no brand)\"): {len(brands)}")
    if len(brands) == 1 and brands[0] == "(no brand)":
        print(
            "Warning: every line is \"(no brand)\" — Product.Brand missing or query ran without Brand; "
            "check catalog or use findBrands/findProducts per GrowFlow API docs.",
            flush=True,
        )
    print(f"Total gross sales in window: ${total_cents / 100:,.2f}")
    print(f"Pool to allocate: ${pool_cents / 100:,.2f}")
    print(f"Query variant: {'with Brand' if query is ORDER_ITEMS_QUERY else 'no Brand field'}")
    print("Validation:")
    if issues:
        for x in issues:
            print(f"  FAIL: {x}")
    else:
        print(f"  OK: sum(pool allocations) = ${sum(allocated)/100:,.2f} (matches pool exactly)")
    print(f"  Concentration (HHI on revenue shares): {hhi:.4f} (1.0 = single brand)")
    print()
    print(f"{'Brand':<42} {'Gross sales':>14} {'Share %':>10} {'Pool $':>12} {'Lines':>8}")
    print("-" * 88)

    for i, b in enumerate(brands):
        g = by_brand_cents[b]
        share = (100.0 * g / total_cents) if total_cents else 0.0
        dollars = allocated[i] / 100.0
        print(
            f"{b[:41]:<42} ${g/100:>12,.2f} {share:>9.2f}% ${dollars:>10,.2f} {lines_by_brand[b]:>8}"
        )

    print("-" * 88)
    print(f"{'TOTAL':<42} ${total_cents/100:>12,.2f} {'100.00':>9}% ${pool_cents/100:>10,.2f} {sum(lines_by_brand.values()):>8}")
    print("=" * 88)
    print()
    print(
        "Interpretation: pool dollars mirror each brand's share of gross line sales in the window. "
        "GrossPrice is treated as line revenue (cents); see METRICS.md. "
        "If Brand is missing on products, use findBrands/findProducts or fix catalog data."
    )

    if args.csv:
        out_path = Path(args.csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                ["brand", "gross_sales_usd", "share_pct", "pool_allocation_usd", "order_lines"]
            )
            for i, b in enumerate(brands):
                g = by_brand_cents[b]
                share = (100.0 * g / total_cents) if total_cents else 0.0
                w.writerow(
                    [
                        b,
                        f"{g / 100:.2f}",
                        f"{share:.4f}",
                        f"{allocated[i] / 100:.2f}",
                        lines_by_brand[b],
                    ]
                )
            w.writerow(
                [
                    "TOTAL",
                    f"{total_cents / 100:.2f}",
                    "100.0000",
                    f"{pool_cents / 100:.2f}",
                    sum(lines_by_brand.values()),
                ]
            )
        print(f"Wrote {out_path.resolve()}", flush=True)

    return 1 if issues else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
