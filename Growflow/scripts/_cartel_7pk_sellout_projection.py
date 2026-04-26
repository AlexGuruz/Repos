"""Project days to sell N Cartel 7pk units from Growflow findOrderItems (validated multi-window).

Validation (see validate_cartel_7pk_projection.py):
- Retail OrderItems have no Quantity field; 1 line ~= 1 unit.
- Raw line count == dedupe-by-objectId count (no double-count or over-dedup in sample).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import importlib.util

from lib.cartel_7pk_names import is_cartel_7pk_product_name, order_item_brand_name

_spec = importlib.util.spec_from_file_location(
    "cb", _root / "scripts" / "_cartel_preroll_velocity_budget.py"
)
_cb = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_cb)


def fetch_7pk_lines(days: int, cp, tz) -> list[dict]:
    lines = _cb.fetch_cartel_pack_lines(days, 14, cp, tz)
    return [
        n
        for n in lines
        if is_cartel_7pk_product_name(
            str((n.get("Product") or {}).get("Name") or ""),
            brand_name=order_item_brand_name(n),
            pack_re=_cb.PACK_RE,
        )
    ]


def cents(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", type=int, default=125, help="Purchase units to project")
    ap.add_argument(
        "--windows",
        default="28,90,183",
        help="Comma-separated trailing day counts (store-local calendar days)",
    )
    args = ap.parse_args()

    _cb._load_config()
    tz = _cb._store_tz()
    cp = _cb._credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: missing credentials")
        sys.exit(1)

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    units_buy = args.units
    end = datetime.now(tz).date()

    print(f"Store TZ: {tz}  |  End date: {end}  |  Units to sell: {units_buy}")
    print()
    print("Validation notes: OrderItems have no Quantity field in Retail GraphQL; projection uses line count.")
    print("Dedupe uses objectId (see lib.allocate_stock_pool.order_item_key).")
    print()

    rows: list[tuple[int, int, float, float, float]] = []
    for d in windows:
        start = end - timedelta(days=d - 1)
        seven = fetch_7pk_lines(d, cp, tz)
        sold = len(seven)
        per_day = sold / float(d)
        gross = sum(cents(n.get("GrossPrice")) for n in seven)
        avg_gross = (gross / 100.0 / sold) if sold else 0.0
        days_cover = units_buy / per_day if per_day > 0 else 0.0
        rows.append((d, sold, per_day, days_cover, avg_gross))
        print(
            f"  {d:3d}d  {start} .. {end}  |  lines={sold:4d}  {per_day:.3f}/day  "
            f"avg_gross=${avg_gross:.2f}  |  {units_buy} units -> {days_cover:.1f} d ({days_cover/7:.1f} wk)"
        )

    print()
    if len(rows) >= 2:
        covs = [r[3] for r in rows if r[3] > 0]
        print(
            f"=== Band for {units_buy} units (trailing windows above) ===\n"
            f"  ~{min(covs):.1f} – {max(covs):.1f} days ({min(covs)/7:.1f} – {max(covs)/7:.1f} weeks)\n"
            f"  6-month ({183 if 183 in windows else max(windows)}d) is a long average; "
            f"if recent demand is stronger than the older part of that window, expect the shorter end."
        )
    print()
    print("Flavor mix + breadth scenarios: python scripts/cartel_7pk_portfolio_projection.py")
    print("Re-validate counts: python scripts/validate_cartel_7pk_projection.py")


if __name__ == "__main__":
    main()
