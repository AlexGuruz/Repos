"""
Store-local day-by-day gross + line counts per brand (for velocity / back-stock cycle checks).

Used while streaming order chunks: only lines whose SoldAt falls in [day_start, day_end]
inclusive (local dates) are accumulated.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from lib.brand_merit_pool import brand_label_from_line, cents_field, parse_iso_utc


def local_dates_inclusive(end_local: date, num_days: int) -> list[date]:
    """end_local inclusive; num_days e.g. 14 => 14 consecutive calendar days ending end_local."""
    start = end_local - timedelta(days=num_days - 1)
    out: list[date] = []
    d = start
    while d <= end_local:
        out.append(d)
        d += timedelta(days=1)
    return out


def merge_brand_daily_window(
    lines: list[dict[str, Any]],
    daily_acc: dict[tuple[str, date], list[int]],
    store_tz: Any,
    day_start_local: date,
    day_end_local: date,
) -> None:
    """
    Merge lines into daily_acc[(brand, local_date)] = [gross_cents, line_count].
    Only lines with SoldAt local date in [day_start_local, day_end_local] inclusive.
    """
    for n in lines:
        sold = parse_iso_utc(n.get("SoldAt"))
        if sold is None:
            continue
        ld = sold.astimezone(store_tz).date()
        if ld < day_start_local or ld > day_end_local:
            continue
        b = brand_label_from_line(n)
        gp = cents_field(n.get("GrossPrice"))
        key = (b, ld)
        if key not in daily_acc:
            daily_acc[key] = [0, 0]
        daily_acc[key][0] += gp
        daily_acc[key][1] += 1


def brands_to_track_daily(
    daily_acc: dict[tuple[str, date], list[int]],
    *,
    merit_rows: list[Any],
) -> set[str]:
    """Brands with any sale in the daily window, or with on-hand inventory (back-stock context)."""
    from_sales = {b for (b, _) in daily_acc.keys()}
    from_inv = {r.brand for r in merit_rows if getattr(r, "inventory_cost_cents", 0) > 0}
    from_14 = {r.brand for r in merit_rows if getattr(r, "gross_14d_cents", 0) > 0}
    return from_sales | from_inv | from_14


def write_daily_sales_grid_csv(
    path: str,
    *,
    brands: set[str],
    dates: list[date],
    daily_acc: dict[tuple[str, date], list[int]],
) -> None:
    """One row per (brand, date); zeros when no sales that day."""
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows_out: list[tuple] = []
    for b in sorted(brands):
        for d in dates:
            g, lc = daily_acc.get((b, d), [0, 0])
            rows_out.append(
                (
                    d.isoformat(),
                    b,
                    f"{g / 100:.2f}",
                    lc,
                    1 if g > 0 or lc > 0 else 0,
                )
            )
    import csv

    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "sale_date_local",
                "brand",
                "gross_usd",
                "line_count",
                "had_sales_flag",
            ]
        )
        w.writerows(rows_out)


def write_daily_coverage_csv(
    path: str,
    *,
    brands: set[str],
    dates: list[date],
    daily_acc: dict[tuple[str, date], list[int]],
    merit_by_brand: dict[str, Any],
) -> None:
    """
    Per brand: how many days had sales, whether every day in the window had activity,
    and which dates are zero (back-stock not 'cycling' daily).
    """
    from pathlib import Path
    import csv

    n = len(dates)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "brand",
                "track_window_days",
                "days_with_sales",
                "days_with_zero_sales",
                "full_cycle_all_days_active",
                "dates_with_no_sales_pipe_sep",
                "gross_14d_usd",
                "inventory_cost_usd",
            ]
        )
        for b in sorted(brands):
            missing: list[str] = []
            days_with = 0
            for d in dates:
                g, _ = daily_acc.get((b, d), [0, 0])
                if g > 0:
                    days_with += 1
                else:
                    missing.append(d.isoformat())
            mr = merit_by_brand.get(b)
            g14 = (mr.gross_14d_cents / 100.0) if mr else 0.0
            inv = (mr.inventory_cost_cents / 100.0) if mr else 0.0
            w.writerow(
                [
                    b,
                    n,
                    days_with,
                    n - days_with,
                    "Yes" if days_with == n and n > 0 else "No",
                    "|".join(missing),
                    f"{g14:.2f}",
                    f"{inv:.2f}",
                ]
            )
