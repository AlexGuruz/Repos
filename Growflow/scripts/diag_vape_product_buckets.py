"""
Sample recent order lines from Growflow and show ProductCategory + Product.Name -> format bucket.
Validates disposable vs cartridge tagging against live API data.

  PYTHONPATH=. python scripts/diag_vape_product_buckets.py --days 14 --brand-contains cartel
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.brand_merit_pool import (  # noqa: E402
    order_line_format_bucket,
    order_line_product_category_name,
    order_line_product_name,
)
from lib.growflow_queries import (  # noqa: E402
    ORDER_ITEMS_QUERY,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose vape bucket from API order lines")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--brand-contains", default="", help="Case-insensitive filter on Product.Brand.Name")
    ap.add_argument("--max-lines", type=int, default=500)
    ap.add_argument("--growflow-credentials", default=None)
    args = ap.parse_args()

    creds = args.growflow_credentials or _credentials_path()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    where = date_range_to_where("SoldAt", start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z"))

    raw = fetch_paginated(
        "findOrderItems",
        ORDER_ITEMS_QUERY,
        {"first": PAGE_SIZE, "where": where},
        credentials_path=creds,
    )

    bc = args.brand_contains.strip().casefold()
    seen: Counter[tuple[str, str, str]] = Counter()
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)

    n_shown = 0
    for n in raw:
        prod = n.get("Product") or {}
        brand = (prod.get("Brand") or {}).get("Name") or ""
        if bc and bc not in str(brand).casefold():
            continue
        cat = order_line_product_category_name(n)
        pname = order_line_product_name(n)
        b = order_line_format_bucket(n)
        if b not in ("Cartridges", "Disposables"):
            continue
        key = (cat, pname[:80], b)
        seen[key] += 1
        if len(examples[(cat, b)]) < 3:
            examples[(cat, b)].append(pname[:120])
        n_shown += 1
        if n_shown >= args.max_lines:
            break

    print(f"Window: last {args.days} days UTC; vape-related lines (carts/dispos) shown: {n_shown}")
    if bc:
        print(f"Brand filter contains: {bc!r}")
    print()
    for (cat, pname, buck), cnt in seen.most_common(50):
        print(f"{cnt:4}  {buck:12}  cat={cat!r}")
        print(f"       product={pname!r}")
    print()
    print("Example Product.Name per (category, bucket):")
    for (cat, buck), names in sorted(examples.items(), key=lambda x: (x[0][0], x[0][1])):
        print(f"  {buck}  cat={cat!r}")
        for nm in names:
            print(f"      - {nm!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
