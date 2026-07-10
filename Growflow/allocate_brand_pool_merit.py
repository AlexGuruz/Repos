"""
Allocate a fixed dollar pool (default $18,000) across brands by *merit*:
  - Margin where COG exists on order lines (GrossPrice - COG).
  - Recent velocity: gross sales in the last N store-local days (default 14).
  - Turnover proxy: recent gross vs on-hand inventory cost (packages CurrentQty * Cost).

Order lines are fetched in **small SoldAt chunks** (default 30 days), deduped globally,
merged incrementally (no full-year list kept in memory). Packages fetched in separate
createdAt chunks with per-chunk logging and global dedupe by package id.

Usage:
  python allocate_brand_pool_merit.py --days 365 --chunk-days 30 --csv data/out.csv
    --daily-sales-csv data/brand_daily_grid.csv

Day-by-day per brand: use --daily-sales-csv (full date x brand grid with zeros). Coverage file
defaults to <stem>_coverage.csv. Window = --daily-track-days (default: same as --velocity-days).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if __name__ == "__main__" and "__file__" in dir():
    _root = Path(__file__).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import (
    allocate_pool_cents_largest_remainder,
    iter_sold_at_date_chunks,
    order_item_key,
    validate_allocation,
)
from lib.brand_merit_pool import (
    FORMAT_PRODUCT_POOL_SUBSTRINGS,
    accumulate_order_lines_chunk,
    cents_field,
    merge_sku_brand_counters,
    order_line_in_format_product_pool,
    package_in_format_product_pool,
    parse_iso_utc,
    rows_from_order_acc_and_packages,
    merit_weights,
)
from lib.brand_daily_sales import (
    brands_to_track_daily,
    local_dates_inclusive,
    merge_brand_daily_window,
    write_daily_coverage_csv,
    write_daily_sales_grid_csv,
)
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PACKAGES_TABLE_QUERY,
    PACKAGES_TABLE_QUERY_WITH_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _load_config_flags(repo_root: Path) -> None:
    p = repo_root / "config" / "config.yaml"
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _yaml_scalar(text, "org_id")
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org


def _store_tz(repo_root: Path):
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = repo_root / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            print(f"WARNING: invalid timezone {name!r}, using local system tz", flush=True)
    now = datetime.now().astimezone()
    return now.tzinfo or timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _validate_sold_at_in_window(
    lines: list[dict],
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> tuple[int, datetime | None, datetime | None]:
    """
    Count lines whose SoldAt **UTC calendar date** falls outside the inclusive date range
    spanned by the window (matches iter_sold_at_date_chunks day boundaries).
    """
    start_d = window_start_utc.astimezone(timezone.utc).date()
    end_d = window_end_utc.astimezone(timezone.utc).date()
    bad = 0
    mn: datetime | None = None
    mx: datetime | None = None
    for n in lines:
        dt = parse_iso_utc(n.get("SoldAt"))
        if dt is None:
            bad += 1
            continue
        if mn is None or dt < mn:
            mn = dt
        if mx is None or dt > mx:
            mx = dt
        ld = dt.astimezone(timezone.utc).date()
        if ld < start_d or ld > end_d:
            bad += 1
    return bad, mn, mx


def _fetch_packages_by_chunks(
    creds: str | None,
    days_back: int,
    query: str,
    package_chunk_days: int,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    chunk_start = now
    by_id: dict[str, dict] = {}
    chunk_num = 0
    total_raw = 0
    while chunk_num * package_chunk_days < days_back:
        chunk_end = chunk_start - timedelta(days=package_chunk_days)
        from_pkg = chunk_end.strftime("%Y-%m-%dT00:00:00.000Z")
        to_pkg = chunk_start.strftime("%Y-%m-%dT23:59:59.999Z")
        where_pkg = date_range_to_where("createdAt", from_pkg, to_pkg)
        try:
            chunk = fetch_paginated(
                "findPackages",
                query,
                {"first": PAGE_SIZE, "where": where_pkg},
                credentials_path=creds,
            )
        except Exception as e:
            print(f"  Package chunk {chunk_num + 1} FAILED: {e}", flush=True)
            break
        total_raw += len(chunk)
        new_ids = 0
        for n in chunk:
            pid = str(n.get("objectId") or n.get("id") or "")
            if not pid:
                continue
            if pid not in by_id:
                by_id[pid] = n
                new_ids += 1
        print(
            f"  Package chunk {chunk_num + 1}: createdAt {from_pkg[:10]} .. {to_pkg[:10]} | "
            f"api_rows={len(chunk)} new_unique_ids={new_ids} cum_unique_pkgs={len(by_id)}",
            flush=True,
        )
        chunk_start = chunk_end
        chunk_num += 1
    out = list(by_id.values())
    print(f"  Packages summary: raw_rows={total_raw} unique_packages={len(out)}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Merit-based brand pool (chunked fetch + validation)")
    ap.add_argument("--pool", type=float, default=18_000.0, help="Total pool USD (default 18000)")
    ap.add_argument("--days", type=int, default=365, help="Trailing sales window in days (default 365)")
    ap.add_argument(
        "--chunk-days",
        type=int,
        default=30,
        help="Max calendar days per findOrderItems SoldAt chunk (default 30; smaller = safer API)",
    )
    ap.add_argument("--velocity-days", type=int, default=14, help="Trailing store-local days for velocity")
    ap.add_argument(
        "--daily-track-days",
        type=int,
        default=None,
        help="Store-local days for day-by-day brand grid (default: same as --velocity-days)",
    )
    ap.add_argument(
        "--daily-sales-csv",
        default=None,
        help="Write day-by-day gross/lines per brand (zeros filled). Coverage CSV defaults alongside.",
    )
    ap.add_argument(
        "--daily-coverage-csv",
        default=None,
        help="Per-brand: days with sales vs full cycle; if omitted, derived from --daily-sales-csv name",
    )
    ap.add_argument("--packages-days-back", type=int, default=730, help="How far back to scan packages")
    ap.add_argument(
        "--package-chunk-days",
        type=int,
        default=90,
        help="Calendar days per findPackages createdAt chunk (default 90)",
    )
    # Defaults favor fast recent sales + margin (ROI proxy); turnover still breaks ties on back-stock.
    ap.add_argument("--w-margin", type=float, default=0.32, help="Weight for margin ratio (default 0.32)")
    ap.add_argument("--w-velocity", type=float, default=0.48, help="Weight for log(1+14d$) (default 0.48)")
    ap.add_argument("--w-turnover", type=float, default=0.20, help="Weight for log(1+turnover) (default 0.20)")
    ap.add_argument("--growflow-credentials", default=None, help="Path to Growflow credentials file")
    ap.add_argument("--csv", default=None, help="Write CSV path")
    ap.add_argument(
        "--format-product-pool",
        action="store_true",
        help=(
            "Only order lines and packages whose ProductCategory name matches one of: "
            "edible, cartridge, disposable, topical, preroll, pre-roll (substring, case-insensitive). "
            "Infused prerolls usually match 'preroll' or 'pre-roll'."
        ),
    )
    ap.add_argument(
        "--category-substrings",
        default="",
        help=(
            "Comma-separated substrings OR-matched against ProductCategory.Name (case-insensitive). "
            "When set, implies format filter; overrides built-in list unless empty."
        ),
    )
    args = ap.parse_args()
    if args.daily_track_days is None:
        args.daily_track_days = args.velocity_days

    cat_subs: tuple[str, ...] | None = None
    raw_subs = [s.strip() for s in (args.category_substrings or "").split(",") if s.strip()]
    if raw_subs:
        cat_subs = tuple(raw_subs)
    elif args.format_product_pool:
        cat_subs = FORMAT_PRODUCT_POOL_SUBSTRINGS

    repo_root = Path(__file__).resolve().parent
    _load_config_flags(repo_root)
    tz = _store_tz(repo_root)
    today_local = datetime.now(tz).date()

    creds = (
        args.growflow_credentials
        or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
        or (str(Path("E:/secrets/gcp/growflowapi.txt")) if Path("E:/secrets/gcp/growflowapi.txt").exists() else None)
    )

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=args.days)
    pool_cents = int(round(float(args.pool) * 100.0))

    oi_query = ORDER_ITEMS_QUERY
    print("=" * 92)
    print("PHASE 1: Order items (chunked SoldAt, global dedupe, incremental merge)")
    print("=" * 92)
    print(
        f"UTC window: {window_start.isoformat()} .. {window_end.isoformat()}  ({args.days} days)",
        flush=True,
    )
    print(f"Chunk size: {args.chunk_days} days per API window (non-overlapping)", flush=True)
    if cat_subs:
        print(
            "ProductCategory filter (order lines + packages): OR of substrings in Name: "
            + ", ".join(cat_subs),
            flush=True,
        )
    daily_track_start = today_local - timedelta(days=args.daily_track_days - 1)
    print(
        f"Day-by-day tracker: store-local {daily_track_start} .. {today_local} "
        f"({args.daily_track_days} days) merged from order chunks",
        flush=True,
    )

    order_acc: dict[str, dict[str, int]] = {}
    daily_acc: dict[tuple[str, date], list[int]] = {}
    sku_counters: dict[str, Counter[str]] = defaultdict(Counter)
    seen_keys: set[str] = set()
    api_lines_total = 0
    dup_total = 0
    bad_date_total = 0
    global_min_sold: datetime | None = None
    global_max_sold: datetime | None = None
    chunk_idx = 0

    for from_iso, to_iso in iter_sold_at_date_chunks(window_start, window_end, args.chunk_days):
        chunk_idx += 1
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        try:
            raw = fetch_paginated(
                "findOrderItems",
                oi_query,
                {"first": PAGE_SIZE, "where": where},
                credentials_path=creds,
            )
        except RuntimeError as e:
            err = str(e).lower()
            if chunk_idx == 1 and ("brand" in err or "cannot query field" in err):
                print("Retrying order items without Product.Brand...", flush=True)
                oi_query = ORDER_ITEMS_QUERY_NO_BRAND
                raw = fetch_paginated(
                    "findOrderItems",
                    oi_query,
                    {"first": PAGE_SIZE, "where": where},
                    credentials_path=creds,
                )
            else:
                raise

        api_lines_total += len(raw)
        kept: list[dict] = []
        dup_c = 0
        for n in raw:
            k = order_item_key(n)
            if k in seen_keys:
                dup_c += 1
                continue
            seen_keys.add(k)
            kept.append(n)
        dup_total += dup_c

        bad_win, cmin, cmax = _validate_sold_at_in_window(kept, window_start, window_end)
        bad_date_total += bad_win
        for dt in (cmin, cmax):
            if dt is None:
                continue
            if global_min_sold is None or dt < global_min_sold:
                global_min_sold = dt
            if global_max_sold is None or dt > global_max_sold:
                global_max_sold = dt

        use_lines = (
            [n for n in kept if order_line_in_format_product_pool(n, cat_subs)]
            if cat_subs
            else kept
        )

        merge_sku_brand_counters(use_lines, sku_counters)
        accumulate_order_lines_chunk(
            use_lines,
            order_acc,
            today_local=today_local,
            velocity_days=args.velocity_days,
            store_tz=tz,
        )
        merge_brand_daily_window(
            use_lines,
            daily_acc,
            tz,
            daily_track_start,
            today_local,
        )

        chunk_gross = sum(cents_field(n.get("GrossPrice")) for n in use_lines)
        fmt_note = f" format_lines={len(use_lines)}/{len(kept)}" if cat_subs else ""
        print(
            f"  Chunk {chunk_idx}: SoldAt {from_iso[:10]} .. {to_iso[:10]} | "
            f"api_lines={len(raw)} new_unique={len(kept)} dup_api={dup_c} "
            f"outside_window_flag={bad_win} chunk_gross=${chunk_gross/100:,.0f}{fmt_note}",
            flush=True,
        )

    unique_lines = len(seen_keys)
    acc_gross_sum = sum(a["gross_y"] for a in order_acc.values())
    print()
    print("  Phase 1 totals:")
    print(f"    API lines (with overlap across chunk boundaries if any): {api_lines_total}")
    print(f"    Global duplicate keys skipped: {dup_total}")
    print(f"    Unique order lines kept: {unique_lines}")
    print(f"    Lines flagged SoldAt outside {args.days}d UTC window: {bad_date_total}")
    print(f"    Min SoldAt (UTC): {global_min_sold}")
    print(f"    Max SoldAt (UTC): {global_max_sold}")
    print(f"    Sum of GrossPrice (cents) from merged acc: {acc_gross_sum} (${acc_gross_sum/100:,.2f})")
    print("=" * 92)

    sku_map: dict[str, str] = {sku: ctr.most_common(1)[0][0] for sku, ctr in sku_counters.items() if ctr}

    print()
    print("PHASE 2: Packages (chunked createdAt, dedupe by package id)")
    print("=" * 92)
    pkg_query = PACKAGES_TABLE_QUERY_WITH_BRAND
    try:
        pkgs = _fetch_packages_by_chunks(creds, args.packages_days_back, pkg_query, args.package_chunk_days)
    except RuntimeError as e:
        if "brand" in str(e).lower() or "cannot query field" in str(e).lower():
            print("Retrying packages without Product.Brand (SKU->brand from order lines)...", flush=True)
            pkg_query = PACKAGES_TABLE_QUERY
            pkgs = _fetch_packages_by_chunks(creds, args.packages_days_back, pkg_query, args.package_chunk_days)
        else:
            raise

    if pkg_query is PACKAGES_TABLE_QUERY:
        # sku_map already built from all order lines
        pass
    if cat_subs:
        before_pkg = len(pkgs)
        pkgs = [p for p in pkgs if package_in_format_product_pool(p, cat_subs)]
        print(f"  Packages after ProductCategory filter: {len(pkgs)} (was {before_pkg})", flush=True)
    print("=" * 92)

    print()
    print("PHASE 3: Merge metrics, merit weights, $ allocation (largest remainder)")
    print("=" * 92)
    by_brand = rows_from_order_acc_and_packages(order_acc, pkgs, sku_map)
    rows = sorted(by_brand.values(), key=lambda r: (-r.gross_year_cents, r.brand))

    weights, merit_issues = merit_weights(
        rows,
        w_margin=args.w_margin,
        w_velocity14=args.w_velocity,
        w_turnover=args.w_turnover,
    )
    allocated = allocate_pool_cents_largest_remainder(pool_cents, weights)
    val_issues = validate_allocation(pool_cents, allocated)

    cross_gross = sum(r.gross_year_cents for r in rows)
    if cross_gross != acc_gross_sum:
        print(f"  WARNING: row gross sum {cross_gross} != acc gross {acc_gross_sum} (investigate)")
    else:
        print(f"  Cross-check: sum(brand year gross) == merged acc gross ({cross_gross} cents) OK")

    tw = args.w_margin + args.w_velocity + args.w_turnover
    print()
    print("=" * 92)
    print("MERIT-BASED BRAND POOL (margin + recent velocity + turnover)")
    print("=" * 92)
    print(f"Store local 'today': {today_local}  timezone: {getattr(tz, 'key', None) or tz}")
    print(f"Sales window: {args.days} days UTC ending now | order chunks: {args.chunk_days}d")
    print(f"Velocity: last {args.velocity_days} store-local days vs prior {args.velocity_days} days")
    print(
        f"Composite = {args.w_margin/tw:.2f}*margin_norm + "
        f"{args.w_velocity/tw:.2f}*log(1+14d$)_norm + {args.w_turnover/tw:.2f}*log(1+turnover)_norm"
    )
    print(f"Higher velocity + higher margin + better turnover vs stock => larger share of ${args.pool:,.0f}")
    if cat_subs:
        print("SCOPE: Category-filtered (edibles / carts / disposables / prerolls / topicals per CLI)")
    print(f"Pool: ${pool_cents/100:,.2f}  |  Orders: {'with Brand' if oi_query is ORDER_ITEMS_QUERY else 'no Brand'}")
    print(f"Packages: {'with Brand' if pkg_query is PACKAGES_TABLE_QUERY_WITH_BRAND else 'SKU->brand map'}")
    for msg in merit_issues:
        print(f"  NOTE: {msg}")
    if val_issues:
        for x in val_issues:
            print(f"  ALLOC ISSUE: {x}")
    else:
        print(f"  Allocation: OK  sum(pool $) = ${sum(allocated)/100:,.2f}  (exactly {pool_cents} cents)")
    print("=" * 92)
    print()
    print(f"{'Brand':<36} {'Year $':>11} {'14d $':>9} {'Margin%*':>9} {'Inv@cost':>10} {'Weight%':>8} {'Pool $':>10}")
    print("-" * 92)
    wsum = sum(weights)
    for i, r in enumerate(rows):
        w_pct = (100.0 * weights[i] / wsum) if wsum > 0 else 0.0
        m_pct = (100.0 * r.margin_ratio) if r.gross_with_cog_cents else 0.0
        print(
            f"{r.brand[:35]:<36} "
            f"${r.gross_year_cents/100:>9,.0f} "
            f"${r.gross_14d_cents/100:>7,.0f} "
            f"{m_pct:>8.1f}% "
            f"${r.inventory_cost_cents/100:>8,.0f} "
            f"{w_pct:>7.2f}% "
            f"${allocated[i]/100:>8,.2f}"
        )
    print("-" * 92)
    print("*Margin% on lines with usable COG only.")
    print("=" * 92)
    print()
    print("WALKTHROUGH")
    print("  1) Order lines: many small SoldAt chunks; each chunk validated; global dedupe; running totals.")
    print("  2) Packages: separate createdAt chunks; unique by package id; inventory cost = sum(CurrentQty*Cost).")
    print("  3) $18k split by merit weights; largest-remainder on cents so the pool is fully allocated.")
    print()

    if args.daily_sales_csv:
        dates = local_dates_inclusive(today_local, args.daily_track_days)
        merit_by_brand = {r.brand: r for r in rows}
        track_brands = brands_to_track_daily(daily_acc, merit_rows=rows)
        grid_path = Path(args.daily_sales_csv)
        cov_path = Path(
            args.daily_coverage_csv
            if args.daily_coverage_csv
            else grid_path.with_name(grid_path.stem + "_coverage.csv")
        )
        write_daily_sales_grid_csv(
            str(grid_path),
            brands=track_brands,
            dates=dates,
            daily_acc=daily_acc,
        )
        write_daily_coverage_csv(
            str(cov_path),
            brands=track_brands,
            dates=dates,
            daily_acc=daily_acc,
            merit_by_brand=merit_by_brand,
        )
        print("=" * 92)
        print("DAY-BY-DAY BRAND SALES (back-stock / 14d cycle check)")
        print("=" * 92)
        print(f"Grid CSV: {grid_path.resolve()}")
        print(f"Coverage CSV: {cov_path.resolve()}")
        print(
            f"full_cycle_all_days_active = had gross > 0 on every store-local day in the "
            f"{args.daily_track_days}-day window (see dates_with_no_sales_pipe_sep if No)."
        )
        backstock_no_cycle = [
            b
            for b in sorted(track_brands)
            if merit_by_brand.get(b)
            and merit_by_brand[b].inventory_cost_cents > 0
            and sum(1 for d in dates if daily_acc.get((b, d), [0, 0])[0] > 0) < len(dates)
        ]
        if backstock_no_cycle:
            print(f"Brands with inventory but NOT a full {args.daily_track_days}d sales streak: {len(backstock_no_cycle)}")
            for b in backstock_no_cycle[:20]:
                r = merit_by_brand[b]
                miss = [d.isoformat() for d in dates if daily_acc.get((b, d), [0, 0])[0] == 0]
                print(
                    f"  - {b[:40]}: Inv~${r.inventory_cost_cents/100:,.0f} | "
                    f"zero-sales days: {len(miss)} (e.g. {', '.join(miss[:5])}{'...' if len(miss)>5 else ''})"
                )
            if len(backstock_no_cycle) > 20:
                print(f"  ... and {len(backstock_no_cycle) - 20} more (see coverage CSV)")
        else:
            print("No brands with inventory + incomplete daily streak in this window (or no inventory brands).")
        print("=" * 92)
        print()

    if args.csv:
        outp = Path(args.csv)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "brand",
                    "gross_year_usd",
                    "gross_14d_usd",
                    "gross_prev14_usd",
                    "margin_ratio",
                    "inventory_cost_usd",
                    "merit_weight_pct",
                    "pool_allocation_usd",
                    "lines_year",
                    "lines_with_cog",
                ]
            )
            for i, r in enumerate(rows):
                w_pct = (100.0 * weights[i] / wsum) if wsum > 0 else 0.0
                w.writerow(
                    [
                        r.brand,
                        f"{r.gross_year_cents / 100:.2f}",
                        f"{r.gross_14d_cents / 100:.2f}",
                        f"{r.gross_prev14_cents / 100:.2f}",
                        f"{r.margin_ratio:.6f}",
                        f"{r.inventory_cost_cents / 100:.2f}",
                        f"{w_pct:.4f}",
                        f"{allocated[i] / 100:.2f}",
                        r.lines_year,
                        r.lines_with_cog,
                    ]
                )
        print(f"Wrote {outp.resolve()}", flush=True)

    return 1 if val_issues else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
