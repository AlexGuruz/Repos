"""
Layer 2: Normalize dates, amounts, and types from raw sources.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .sources import (
    parse_amount,
    parse_date_to_ymd,
)


def normalize_order_items(nodes: list[dict]) -> list[dict]:
    """Produce list of { date_ym, date_str, gross, cog, order_id? } from findOrderItems nodes."""
    out = []
    for n in nodes:
        sold_at = n.get("SoldAt")
        if not sold_at:
            continue
        try:
            dt = datetime.fromisoformat(sold_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        y, m, d = dt.year, dt.month, dt.day
        gross_cents = n.get("GrossPrice") or 0
        cog_cents = n.get("COG") or 0
        out.append({
            "date_ym": (y, m),
            "date_str": f"{y}-{m:02d}-{d:02d}",
            "year": y,
            "month": m,
            "day": d,
            "gross": gross_cents / 100.0,
            "cog": cog_cents / 100.0,
            "sku": (n.get("Product") or {}).get("SKU") or n.get("SKU") or "",
            "category": ((n.get("ProductCategory") or {}).get("Name") or "").strip(),
        })
    return out


def normalize_transactions(
    rows: list[list],
    date_col: int,
    source_col: int,
    amount_col: int,
    start_row: int,
) -> list[dict]:
    """Produce list of { date_ym, date_str, amount, source_raw, year, month }."""
    out = []
    for row in rows[start_row:]:
        if len(row) <= max(date_col, amount_col):
            continue
        ymd = parse_date_to_ymd(row[date_col])
        if ymd is None:
            continue
        y, m, d = ymd
        amt = parse_amount(row[amount_col] if len(row) > amount_col else None)
        if amt is None:
            continue
        source = str(row[source_col] if len(row) > source_col else "").strip()
        out.append({
            "date_ym": (y, m),
            "date_str": f"{y}-{m:02d}-{d:02d}",
            "year": y,
            "month": m,
            "day": d,
            "amount": amt,
            "source_raw": source,
            "source_upper": source.upper(),
        })
    return out


def aggregate_sales_by_month(normalized_items: list[dict]) -> dict[tuple[int, int], dict]:
    """{(y,m): { gross, cog, lines, daily_gross { date_str: gross } }}."""
    by_month: dict[tuple[int, int], dict] = defaultdict(lambda: {"gross": 0.0, "cog": 0.0, "lines": 0, "daily_gross": defaultdict(float)})
    for r in normalized_items:
        k = r["date_ym"]
        by_month[k]["gross"] += r["gross"]
        by_month[k]["cog"] += r["cog"]
        by_month[k]["lines"] += 1
        by_month[k]["daily_gross"][r["date_str"]] += r["gross"]
    return dict(by_month)


def aggregate_packages_by_month(package_nodes: list[dict]) -> dict[tuple[int, int], dict]:
    """{(y,m): { units_created, current_qty (latest), cost }}. current_qty is sum(CurrentQty) at fetch time."""
    by_month: dict[tuple[int, int], dict] = defaultdict(lambda: {"units_created": 0, "cost": 0.0})
    current_total = 0.0
    for n in package_nodes:
        created = n.get("createdAt")
        orig = n.get("OriginalQty") or 0
        curr = n.get("CurrentQty") or 0
        cost = n.get("Cost") or 0
        if isinstance(cost, (int, float)):
            pass
        else:
            cost = 0
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                y, m = dt.year, dt.month
                by_month[(y, m)]["units_created"] += int(orig) if orig else 0
                by_month[(y, m)]["cost"] += float(cost) if cost else 0
            except Exception:
                pass
        current_total += float(curr) if curr else 0
    result = dict(by_month)
    # Attach current total to the most recent month key for convenience
    if result:
        last_key = max(result.keys())
        result[last_key]["current_qty_total"] = current_total
    return result
