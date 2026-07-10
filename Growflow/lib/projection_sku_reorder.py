"""
SKU-first reorder math for receipt-aware buy planning.

Each **Product.objectId** row uses its own latest transfer receipt (qty + unit cost) and
units sold since that receipt anchor. Targets are summed into **brand × category** cells
for pool deployment only — fast SKUs do not get averaged down by slow siblings.

See ``scripts/build_projection_by_category_brand.py`` for orchestration.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def target_units_for_product(
    sold_u: int,
    receipt_qty: int | None,
    den_days: int,
    *,
    growth_sensitivity: float,
    shrink_sensitivity: float,
    discontinue_ratio: float,
    shelf_days: float,
) -> float:
    """
    Next-cycle unit target for one product (float before ceiling to purchasable units).

    If ``receipt_qty`` is missing, fall back to replenishing observed sales in-window (sold_u).
    """
    if sold_u < 0:
        sold_u = 0
    den = max(1, int(den_days))
    if receipt_qty is None or receipt_qty <= 0:
        return float(sold_u)

    ratio = float(sold_u) / float(receipt_qty)
    if ratio <= float(discontinue_ratio):
        return 0.0
    if ratio >= 1.0:
        growth = 1.0 + float(growth_sensitivity) * (ratio - 1.0)
        target_u = float(receipt_qty) * growth
    else:
        shrink = 1.0 - float(shrink_sensitivity) * (1.0 - ratio)
        target_u = float(receipt_qty) * max(0.0, shrink)
    # Sell-through / shelf sizing at this product's own daily pace (not category-wide).
    if ratio >= 0.95:
        daily_prod = float(sold_u) / float(den)
        demand_target = daily_prod * float(shelf_days)
        if demand_target > target_u:
            target_u = demand_target
    return max(0.0, float(target_u))


def build_sku_pre_scale_buy(
    *,
    prod_units_since_receipt: dict[tuple[tuple[str, str], str], int],
    prod_den_days_recent: dict[tuple[tuple[str, str], str], int],
    latest_receipt_snapshot: dict[str, dict[str, Any]],
    velocity_span: int,
    growth_sensitivity: float,
    shrink_sensitivity: float,
    discontinue_ratio: float,
    shelf_days: float,
    on_hand_by_product_id: dict[str, int] | None = None,
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    """
    Returns ``(pre_scale_cents_by_cell, pre_scale_units_by_cell)`` from integer unit buys
    at landed unit cost per product.
    """
    pre_cents: dict[tuple[str, str], int] = defaultdict(int)
    pre_units: dict[tuple[str, str], int] = defaultdict(int)

    for (key_bc, pid), sold_u in prod_units_since_receipt.items():
        if not pid or pid in ("(no_product_id)",):
            continue
        snap = latest_receipt_snapshot.get(pid) if latest_receipt_snapshot else None
        if not isinstance(snap, dict):
            continue
        rq: int | None
        try:
            rq = int(snap["original_qty"]) if snap.get("original_qty") is not None else None
        except (TypeError, ValueError):
            rq = None
        uc_raw = snap.get("unit_cost_cents")
        try:
            uc = int(round(float(uc_raw))) if uc_raw is not None else 0
        except (TypeError, ValueError):
            uc = 0
        if uc <= 0:
            continue

        den = int(prod_den_days_recent.get((key_bc, pid), max(1, velocity_span)))
        tu = target_units_for_product(
            int(sold_u),
            rq,
            den,
            growth_sensitivity=growth_sensitivity,
            shrink_sensitivity=shrink_sensitivity,
            discontinue_ratio=discontinue_ratio,
            shelf_days=shelf_days,
        )
        # Likely shelf-out: no on-hand signal but strong sell-through vs last receipt.
        if on_hand_by_product_id is not None and int(on_hand_by_product_id.get(pid, 0)) <= 0 and rq and rq > 0:
            ratio = float(sold_u) / float(rq)
            if ratio >= 0.85:
                daily = float(sold_u) / float(max(1, den))
                tu = max(tu, daily * float(shelf_days) * 1.15)

        units_int = int(math.ceil(tu)) if tu > 1e-9 else 0
        if units_int <= 0:
            continue
        cog = int(units_int) * int(uc)
        pre_units[key_bc] += int(units_int)
        pre_cents[key_bc] += int(cog)

    return dict(pre_cents), dict(pre_units)
