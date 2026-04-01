"""Compute avg days from Product.createdAt to last sale per OriginId (source)."""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_queries import fetch_paginated

CREDS = str(Path("E:/secrets/gcp/growflowapi.txt"))
NAME_SUBSTR = "CARTEL 7PK DIAM INFU PREROLL"

ORDER_ITEMS_Q = """
query Oi($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        OriginId
        SoldAt
        Product { Name createdAt objectId }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""


def parse_iso(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def main() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=2000)

    # per OriginId: list of (sold_at, product_created_at)
    by_origin: dict[str, list[tuple[datetime, datetime | None]]] = defaultdict(list)

    t = start
    chunk_days = 90
    while t < now:
        t_end = min(t + timedelta(days=chunk_days), now)
        where_oi = {
            "SoldAt": {
                "greaterThanOrEqualTo": t.strftime("%Y-%m-%dT00:00:00.000Z"),
                "lessThanOrEqualTo": t_end.strftime("%Y-%m-%dT23:59:59.999Z"),
            },
            "Product": {
                "have": {
                    "Name": {
                        "matchesRegex": f"(?i){NAME_SUBSTR.replace('(', r'\\(').replace(')', r'\\)')}"
                    }
                }
            },
        }
        items = fetch_paginated(
            "findOrderItems",
            ORDER_ITEMS_Q,
            {"first": 100, "where": where_oi},
            credentials_path=CREDS,
        )
        for node in items:
            oid = str(node.get("OriginId") or "").strip()
            if not oid:
                continue
            sold = parse_iso(node.get("SoldAt"))
            if not sold:
                continue
            prod = node.get("Product") or {}
            pc = parse_iso(prod.get("createdAt"))
            by_origin[oid].append((sold, pc))
        t = t_end

    durations: list[float] = []
    for oid, pairs in by_origin.items():
        last_sale = max(p[0] for p in pairs)
        createds = [p[1] for p in pairs if p[1] is not None]
        if not createds:
            continue
        created = min(createds)
        days = (last_sale - created).total_seconds() / 86400.0
        if days >= 0:
            durations.append(days)

    print("Name filter (case-insensitive substring):", NAME_SUBSTR)
    print("Distinct sources (OriginId with sales):", len(by_origin))
    print("Sources with Product.createdAt on at least one line:", len(durations))
    if not durations:
        return
    print(f"Average days (created to last sale per source): {statistics.mean(durations):.2f}")
    print(f"Median: {statistics.median(durations):.2f}")
    print(f"Min: {min(durations):.2f}  Max: {max(durations):.2f}")


if __name__ == "__main__":
    main()
