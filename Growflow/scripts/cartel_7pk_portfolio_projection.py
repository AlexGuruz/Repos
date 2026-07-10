"""
Cartel 7pk preroll portfolio projection: flavor (Product.objectId) mix vs equal split.

Data: findOrderItems only (chunked SoldAt). Retail GraphQL exposes the same OrderItems
fields under findOrders(...).Items { ... on OrderItems { ... } } — confirmed — but still
no line Quantity; 1 row ~= 1 sellable unit.

Scenarios
-----------
1) **Portfolio** — total units / total trailing rate (same as aggregate projection).
2) **Historical mix** — split 125 packs by each SKU's share of Cartel 7pk sales; every
   flavor still clears at the same calendar time if demand matches history (math identity).
3) **Equal split** — if you stock `N` active SKUs and split ~evenly, the slowest SKU
   sets a **bottleneck** (more realistic when you force breadth without matching velocity).

4) **Top-K equal** — equal units among the K fastest-moving SKUs from history (optional).

Usage (repo root):
  PYTHONPATH=. python scripts/cartel_7pk_portfolio_projection.py --units 125 --days 90
  PYTHONPATH=. python scripts/cartel_7pk_portfolio_projection.py --units 125 --days 90 --top-k 15
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

_spec = importlib.util.spec_from_file_location(
    "cb", _root / "scripts" / "_cartel_preroll_velocity_budget.py"
)
_cb = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_cb)

from lib.cartel_7pk_names import is_cartel_7pk_product_name, order_item_brand_name


def fetch_7pk_by_product(days: int, cp, tz) -> tuple[list[dict], dict[tuple[str, str], int]]:
    lines = _cb.fetch_cartel_pack_lines(days, 14, cp, tz)
    seven = [
        n
        for n in lines
        if is_cartel_7pk_product_name(
            str((n.get("Product") or {}).get("Name") or ""),
            brand_name=order_item_brand_name(n),
            pack_re=_cb.PACK_RE,
        )
    ]
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for n in seven:
        pr = n.get("Product") or {}
        oid = str(pr.get("objectId") or "").strip() or "(no objectId)"
        nm = str(pr.get("Name") or "").strip()
        counts[(oid, nm)] += 1
    return seven, dict(counts)


def allocate_largest_remainder(n_units: int, shares: dict[tuple[str, str], float]) -> dict[tuple[str, str], int]:
    """Integer allocations summing to n_units from fractional shares (sum shares = 1)."""
    keys = list(shares.keys())
    raw = [n_units * shares[k] for k in keys]
    flo = [math.floor(x) for x in raw]
    alloc = {keys[i]: flo[i] for i in range(len(keys))}
    rem = n_units - sum(flo)
    frac_idx = sorted(range(len(keys)), key=lambda i: raw[i] - flo[i], reverse=True)
    for i in range(rem):
        alloc[keys[frac_idx[i]]] += 1
    return alloc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", type=int, default=125, help="Total 7pk packs purchased")
    ap.add_argument("--days", type=int, default=90, help="Trailing store-local days for velocity")
    ap.add_argument("--top-k", type=int, default=0, help="If >0, equal-split bottleneck among top-K SKUs by volume")
    args = ap.parse_args()

    _cb._load_config()
    tz = _cb._store_tz()
    cp = _cb._credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: missing credentials")
        sys.exit(1)

    u = args.units
    d = args.days
    end = datetime.now(tz).date()
    start = end - timedelta(days=d - 1)

    print(f"Cartel 7pk portfolio | {d}d window {start} .. {end} ({tz}) | buy {u} packs")
    print(
        "Schema: findOrderItems (1 row ~ 1 unit). findOrders.Items uses same OrderItems shape; no Quantity field.\n"
    )

    seven, by_sku = fetch_7pk_by_product(d, cp, tz)
    total_lines = len(seven)
    if total_lines == 0:
        print("No Cartel 7pk lines in window.")
        sys.exit(0)

    portfolio_per_day = total_lines / float(d)
    portfolio_days = u / portfolio_per_day
    print("=== A) Portfolio (aggregate) ===")
    print(f"  Trailing lines: {total_lines} -> {portfolio_per_day:.3f} packs/day")
    print(f"  {u} packs -> {portfolio_days:.1f} days (~{portfolio_days/7:.1f} weeks)")

    # Mix table
    total = float(sum(by_sku.values()))
    ranked = sorted(by_sku.items(), key=lambda x: -x[1])
    shares = {k: v / total for k, v in by_sku.items()}
    alloc_mix = allocate_largest_remainder(u, shares)
    if sum(alloc_mix.values()) != u:
        print("ERROR: mix allocation does not sum to --units", sum(alloc_mix.values()))
        sys.exit(1)

    print()
    print("=== B) Historical mix (allocation of purchase across SKUs) ===")
    print("  If future mix matches this window, all flavors still clear same calendar day (portfolio rate).")
    print(f"  {'units':>5}  {'share':>6}  {'lines':>4}  {'name':<50}")
    print("  " + "-" * 78)
    for (poid, name), cnt in ranked[:25]:
        a = alloc_mix.get((poid, name), 0)
        sh = 100.0 * cnt / total
        print(f"  {a:5d}  {sh:5.1f}%  {cnt:4d}  {name[:50]}")
    if len(ranked) > 25:
        rest_n = len(ranked) - 25
        rest_lines = sum(c for _, c in ranked[25:])
        rest_u = sum(alloc_mix.get(k, 0) for k, _ in ranked[25:])
        print(f"  ... +{rest_n} more SKUs  (lines={rest_lines}, mix_units_in_tail={rest_u}) ...")

    # Equal split bottleneck
    N = len(by_sku)
    per = u / float(N)
    print()
    print("=== C) Equal split across all SKUs that sold in window ===")
    print(f"  Active SKUs (>=1 sale in {d}d): {N}")
    print(f"  ~{per:.2f} packs per SKU if perfectly even")

    slowest_days = 0.0
    slowest = None
    for (poid, name), cnt in by_sku.items():
        v = cnt / float(d)
        if v <= 0:
            continue
        days_clear = per / v
        if days_clear > slowest_days:
            slowest_days = days_clear
            slowest = (name, cnt, v)
    if slowest:
        print(f"  Bottleneck (slowest SKU at equal share): {slowest_days:.1f} days (~{slowest_days/7:.1f} wk)")
        print(f"    -> {slowest[0][:55]} | lines/{d}d={slowest[1]} | {slowest[2]:.3f}/day")

    # Top-K equal
    if args.top_k and args.top_k > 0:
        K = min(args.top_k, len(ranked))
        top = ranked[:K]
        per_k = u / float(K)
        print()
        print(f"=== D) Equal split among top {K} SKUs by volume ===")
        print(f"  ~{per_k:.2f} packs each")
        worst = 0.0
        worst_name = ""
        for (poid, name), cnt in top:
            v = cnt / float(d)
            if v <= 0:
                continue
            days_clear = per_k / v
            if days_clear > worst:
                worst = days_clear
                worst_name = name
        print(f"  Bottleneck (slowest of top-{K}): {worst:.1f} days (~{worst/7:.1f} wk)")
        print(f"    -> {worst_name[:60]}")

    print()
    print("Interpretation:")
    print("  - (A) is correct total-inventory turnover if all packs are substitutable.")
    print("  - (C)/(D) matter when you force breadth: slow movers get equal units and dominate calendar time.")


if __name__ == "__main__":
    main()
