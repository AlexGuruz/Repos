"""
Finish the $18k merit projection from an existing merit CSV + optional 14-day API pass.

1) Validates pool totals and computes concentration / risk flags -> data/projection_18k_summary.txt
2) With --with-daily (default): fetches only last N store-local days of order lines (small chunks),
   writes day grid + coverage aligned to brands in the merit CSV (no full-year re-pull).

Usage (from repo root):
  python scripts/complete_18k_projection.py
  python scripts/complete_18k_projection.py --merit-csv data/brand_merit_12m.csv --no-daily
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.brand_daily_sales import (
    brands_to_track_daily,
    local_dates_inclusive,
    merge_brand_daily_window,
    write_daily_coverage_csv,
    write_daily_sales_grid_csv,
)
from lib.brand_merit_pool import parse_iso_utc
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _load_config() -> None:
    p = REPO / "config" / "config.yaml"
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _yaml_scalar(text, "org_id")
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org


def _store_tz() -> ZoneInfo | timezone:
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = REPO / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    now = datetime.now().astimezone()
    return now.tzinfo or timezone.utc


def _creds() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


@dataclass
class MeritRowLite:
    brand: str
    gross_14d_cents: int
    inventory_cost_cents: int


def load_merit_csv(path: Path) -> list[MeritRowLite]:
    rows: list[MeritRowLite] = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("brand") or "").strip().upper() == "TOTAL":
                continue
            rows.append(
                MeritRowLite(
                    brand=(r["brand"] or "").strip(),
                    gross_14d_cents=int(round(float(r["gross_14d_usd"]) * 100)),
                    inventory_cost_cents=int(round(float(r["inventory_cost_usd"]) * 100)),
                )
            )
    return rows


def build_summary_text(
    merit_path: Path,
    *,
    pool_total: float,
    year_gross: float,
) -> str:
    pool_by_brand: dict[str, float] = {}
    w_by_brand: dict[str, float] = {}
    g14_by: dict[str, float] = {}
    inv_by: dict[str, float] = {}
    yr_by: dict[str, float] = {}
    with open(merit_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            b = (r.get("brand") or "").strip()
            if not b or b.upper() == "TOTAL":
                continue
            pool_by_brand[b] = float(r["pool_allocation_usd"])
            w_by_brand[b] = float(r["merit_weight_pct"])
            g14_by[b] = float(r["gross_14d_usd"])
            inv_by[b] = float(r["inventory_cost_usd"])
            yr_by[b] = float(r["gross_year_usd"])

    brands = list(pool_by_brand.keys())
    pools = [pool_by_brand.get(b, 0) for b in brands]
    total_calc = sum(pools)
    ordered = sorted(zip(brands, pools), key=lambda x: -x[1])

    def cum_top(k: int) -> float:
        return sum(p for _, p in ordered[:k])

    lines = [
        "=" * 72,
        "$18,000 MERIT POOL — PROJECTION SUMMARY",
        "=" * 72,
        f"Source merit file: {merit_path}",
        f"Brands in file: {len(brands)}",
        f"Pool allocated (sum of pool_allocation_usd): ${total_calc:,.2f}",
        f"Expected pool: ${pool_total:,.2f}",
        f"Trailing year gross (sum gross_year_usd): ${year_gross:,.2f}",
        "",
        "CONCENTRATION (pool $)",
        f"  Top 5 brands:  ${cum_top(5):,.2f}  ({100*cum_top(5)/pool_total:.1f}% of pool)",
        f"  Top 10 brands: ${cum_top(10):,.2f}  ({100*cum_top(10)/pool_total:.1f}% of pool)",
        f"  Top 20 brands: ${cum_top(20):,.2f}  ({100*cum_top(20)/pool_total:.1f}% of pool)",
        "",
        "TOP 20 BRANDS BY POOL $ (merit = margin + 14d velocity + turnover vs inventory)",
    ]
    for i, (b, pl) in enumerate(ordered[:20], 1):
        lines.append(
            f"  {i:2}. {b[:38]:<38} ${pl:>8,.2f}  "
            f"w={w_by_brand.get(b,0):.2f}%  14d=${g14_by.get(b,0):,.0f}  "
            f"yr=${yr_by.get(b,0):,.0f}  inv=${inv_by.get(b,0):,.0f}"
        )

    # Risk: inventory reported high but flat 14d
    risk = [
        (b, inv_by[b], g14_by[b], pool_by_brand[b])
        for b in brands
        if inv_by.get(b, 0) >= 50_000 and g14_by.get(b, 0) < 500 and pool_by_brand.get(b, 0) > 0
    ]
    risk.sort(key=lambda x: -x[1])
    lines.extend(["", "DATA RISK FLAGS (inv >= $50k AND 14d gross < $500) — validate Cost/qty in Growflow:"])
    if not risk:
        lines.append("  (none in this band)")
    else:
        for b, inv, g14, pl in risk[:15]:
            lines.append(f"  - {b[:40]}: pool=${pl:,.0f} | inv=${inv:,.0f} | 14d=${g14:,.0f}")

    lines.extend(
        [
            "",
            "INTERPRETATION",
            "  Pool $ is NOT COGS required; it is a merit-weighted BUDGET SPLIT of $18,000.",
            "  Use *_coverage.csv (from --with-daily) to see which brands had sales every day",
            "  in the velocity window vs gappy back-stock sell-through.",
            "=" * 72,
        ]
    )
    return "\n".join(lines)


def fetch_daily_only(
    creds: str | None,
    tz,
    today_local: date,
    track_days: int,
    api_chunk_days: int,
) -> dict[tuple[str, date], list[int]]:
    window_end = datetime.now(timezone.utc)
    # Pull enough UTC history that store-local [daily_start, today] is fully covered (DST + edges).
    window_start = window_end - timedelta(days=track_days + 4)
    daily_start = today_local - timedelta(days=track_days - 1)
    daily_acc: dict[tuple[str, date], list[int]] = {}
    seen: set[str] = set()
    q = ORDER_ITEMS_QUERY
    chunk_i = 0
    for from_iso, to_iso in iter_sold_at_date_chunks(window_start, window_end, api_chunk_days):
        chunk_i += 1
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        try:
            raw = fetch_paginated(
                "findOrderItems",
                q,
                {"first": PAGE_SIZE, "where": where},
                credentials_path=creds,
            )
        except RuntimeError as e:
            if chunk_i == 1 and ("brand" in str(e).lower() or "cannot query field" in str(e).lower()):
                q = ORDER_ITEMS_QUERY_NO_BRAND
                raw = fetch_paginated(
                    "findOrderItems",
                    q,
                    {"first": PAGE_SIZE, "where": where},
                    credentials_path=creds,
                )
            else:
                raise
        kept = []
        for n in raw:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            dt = parse_iso_utc(n.get("SoldAt"))
            if dt is None:
                continue
            ld = dt.astimezone(tz).date()
            if ld < daily_start or ld > today_local:
                continue
            kept.append(n)
        merge_brand_daily_window(kept, daily_acc, tz, daily_start, today_local)
        print(
            f"  Daily fetch chunk {chunk_i}: UTC {from_iso[:10]}..{to_iso[:10]} "
            f"api={len(raw)} in_window_unique={len(kept)} cells_filled={len(daily_acc)}",
            flush=True,
        )
    print(f"  Daily fetch done: unique lines touching window ~{len(seen)} keys seen", flush=True)
    return daily_acc


def main() -> int:
    ap = argparse.ArgumentParser(description="Complete $18k projection summary + optional 14d daily API")
    ap.add_argument("--merit-csv", type=Path, default=REPO / "data" / "brand_merit_12m.csv")
    ap.add_argument("--pool", type=float, default=18_000.0)
    ap.add_argument("--with-daily", action="store_true", default=True)
    ap.add_argument("--no-daily", action="store_true", help="Skip API; summary only")
    ap.add_argument("--daily-track-days", type=int, default=14)
    ap.add_argument("--api-chunk-days", type=int, default=3, help="SoldAt chunk size for 14d-only fetch")
    ap.add_argument("--summary-out", type=Path, default=REPO / "data" / "projection_18k_summary.txt")
    ap.add_argument("--daily-grid-out", type=Path, default=REPO / "data" / "brand_daily_14d_projection.csv")
    args = ap.parse_args()
    if args.no_daily:
        args.with_daily = False

    merit_path = args.merit_csv
    if not merit_path.is_file():
        print(f"Merit CSV not found: {merit_path}", file=sys.stderr)
        return 1

    merit_rows = load_merit_csv(merit_path)
    pool_by = {}
    year_gross_sum = 0.0
    with open(merit_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            b = (r.get("brand") or "").strip()
            if not b or b.upper() == "TOTAL":
                continue
            pool_by[b] = float(r["pool_allocation_usd"])
            year_gross_sum += float(r["gross_year_usd"])
    total_pool = sum(pool_by.values())

    text = build_summary_text(
        merit_path,
        pool_total=args.pool,
        year_gross=year_gross_sum,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(text, encoding="utf-8")
    print(f"Wrote {args.summary_out.resolve()}", flush=True)

    merit_by_brand = {r.brand: r for r in merit_rows}

    if args.with_daily:
        _load_config()
        tz = _store_tz()
        today_local = datetime.now(tz).date()
        creds = _creds()
        print("Fetching last %d store-local days for day-by-day grid..." % args.daily_track_days, flush=True)
        daily_acc = fetch_daily_only(creds, tz, today_local, args.daily_track_days, args.api_chunk_days)
        dates = local_dates_inclusive(today_local, args.daily_track_days)
        # MeritRowLite works: has .brand, .gross_14d_cents, .inventory_cost_cents
        track_brands = brands_to_track_daily(daily_acc, merit_rows=merit_rows)
        cov_path = args.daily_grid_out.with_name(args.daily_grid_out.stem + "_coverage.csv")
        write_daily_sales_grid_csv(
            str(args.daily_grid_out),
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
        print(f"Wrote {args.daily_grid_out.resolve()}", flush=True)
        print(f"Wrote {cov_path.resolve()}", flush=True)

    return 0 if abs(total_pool - args.pool) < 0.05 else 1


if __name__ == "__main__":
    raise SystemExit(main())
