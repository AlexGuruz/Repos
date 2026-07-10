"""
Pure logic for stock-pool allocation by brand (testable without API).

See allocate_stock_pool_by_brand.py for CLI; company_bi/METRICS.md for GrossPrice cents.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from typing import Any


def iter_sold_at_date_chunks(
    start: datetime,
    end: datetime,
    chunk_days: int,
) -> Iterator[tuple[str, str]]:
    """
    Yield (from_iso, to_iso) UTC strings for SoldAt filters.
    Uses inclusive calendar-day ranges with **no gaps and no overlaps** between chunks.
    Each chunk spans at most `chunk_days` calendar days (inclusive).
    """
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")
    start_d = start.date()
    end_d = end.date()
    cur = start_d
    while cur <= end_d:
        chunk_last = min(cur + timedelta(days=chunk_days - 1), end_d)
        from_dt = datetime(cur.year, cur.month, cur.day, 0, 0, 0, 0, tzinfo=timezone.utc)
        to_dt = datetime(
            chunk_last.year, chunk_last.month, chunk_last.day,
            23, 59, 59, 999000, tzinfo=timezone.utc,
        )
        yield (
            from_dt.strftime("%Y-%m-%dT00:00:00.000Z"),
            to_dt.strftime("%Y-%m-%dT23:59:59.999Z"),
        )
        cur = chunk_last + timedelta(days=1)


def order_item_package_object_id(node: dict[str, Any]) -> str:
    """Inventory package line id from findOrderItems (not OriginId / compliance tag)."""
    pkg = node.get("Package")
    if isinstance(pkg, dict):
        oid = pkg.get("objectId")
        if oid is not None and str(oid).strip():
            return str(oid).strip()
    return ""


def order_item_key(node: dict[str, Any]) -> str:
    """Stable id for dedupe; GrowFlow may expose objectId or id."""
    for k in ("objectId", "id"):
        v = node.get(k)
        if v is not None and str(v).strip():
            return f"{k}:{v}"
    sold = node.get("SoldAt")
    sku = (node.get("Product") or {}).get("SKU") or node.get("SKU")
    gp = node.get("GrossPrice")
    return f"fallback:{sold}|{sku}|{gp}"


def aggregate_by_brand(
    nodes: list[dict[str, Any]],
    *,
    dedupe: bool = True,
) -> tuple[dict[str, int], dict[str, int], int]:
    """
    Returns (gross_cents_by_brand, line_count_by_brand, duplicate_lines_skipped).
    """
    by_cents: dict[str, int] = defaultdict(int)
    lines: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    raw_count = len(nodes)
    dup_skipped = 0
    for n in nodes:
        if dedupe:
            k = order_item_key(n)
            if k in seen:
                dup_skipped += 1
                continue
            seen.add(k)
        prod = n.get("Product") or {}
        brand_obj = prod.get("Brand")
        if isinstance(brand_obj, dict):
            bname = brand_obj.get("Name")
        else:
            bname = None
        label = str(bname).strip() if bname and str(bname).strip() else "(no brand)"
        try:
            cents = int(n.get("GrossPrice") or 0)
        except (TypeError, ValueError):
            cents = 0
        by_cents[label] += cents
        lines[label] += 1
    if not dedupe:
        dup_skipped = 0
    return dict(by_cents), dict(lines), dup_skipped


def allocate_pool_cents_largest_remainder(pool_cents: int, weights: list[float]) -> list[int]:
    """Largest-remainder; sum(result) == pool_cents exactly when pool_cents >= 0."""
    n = len(weights)
    if pool_cents <= 0:
        return [0] * n
    total_w = sum(weights)
    if n == 0:
        return []
    if total_w <= 0:
        base, rem = divmod(pool_cents, n)
        return [base + (1 if i < rem else 0) for i in range(n)]
    raw = [pool_cents * w / total_w for w in weights]
    floors = [int(r) for r in raw]
    assigned = sum(floors)
    rem = pool_cents - assigned
    order = sorted(range(n), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(rem):
        floors[order[i]] += 1
    return floors


def validate_allocation(
    pool_cents: int,
    allocated_cents: list[int],
) -> list[str]:
    """Return issues if sum(allocated) != pool or negative cents."""
    issues: list[str] = []
    if any(a < 0 for a in allocated_cents):
        issues.append("NEGATIVE_ALLOCATION")
    s = sum(allocated_cents)
    if s != pool_cents:
        issues.append(f"ALLOCATION_SUM_MISMATCH: sum(allocated)={s} != pool={pool_cents}")
    return issues


def concentration_hhi(shares: list[float]) -> float:
    """Herfindahl index on shares (0..1 each); 1 = monopoly."""
    return sum(s * s for s in shares)
