"""
Prepackaged flower sales metrics (last 2 months) via Growflow API.

Reports per strain (Product.Name):
- Dollar sales (net and gross)
- Grams sold in the period
- Average days in inventory before sale (when package OriginId is available)

Category filter: ProductCategory.Name containing "prepackaged flower" (case-insensitive).

Usage:
  python prepackaged_flower_sales_metrics.py
  python prepackaged_flower_sales_metrics.py --credentials-path "path/to/creds"

Credentials: set GROWFLOW_CREDENTIALS_PATH or use --credentials-path. File format:
  client id: <value>
  client secret: <value>
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    PACKAGES_TABLE_QUERY,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)

# Category to filter (case-insensitive substring match)
PREPACKAGED_FLOWER_CATEGORY = "prepackaged flower"

# Weight UOM -> grams conversion
UOM_TO_GRAMS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
}


def weight_to_grams(amount: float | None, uom: str | None) -> float:
    """Convert weight to grams. Returns 0 if amount is None or invalid."""
    if amount is None:
        return 0.0
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if not uom or not str(uom).strip():
        return val  # assume already grams
    key = (uom or "").strip().lower()
    factor = UOM_TO_GRAMS.get(key, 1.0)
    return val * factor


def parse_iso(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepackaged flower sales metrics (last 2 months)")
    ap.add_argument(
        "--credentials-path",
        default=None,
        help="Path to Growflow credentials file (default: env or E:\\secrets\\GrowFlow\\growflowapi.txt)",
    )
    args = ap.parse_args()
    credentials_path = args.credentials_path or None

    # Last 2 months (inclusive of today)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=60)
    from_iso = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    where = date_range_to_where("SoldAt", from_iso, to_iso)

    print("Fetching order items (last 2 months)...", flush=True)
    variables = {"first": PAGE_SIZE, "where": where}
    try:
        nodes = fetch_paginated(
            "findOrderItems",
            ORDER_ITEMS_QUERY,
            variables,
            credentials_path=credentials_path,
        )
    except Exception as e:
        print(f"Error fetching order items: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter by category and aggregate by strain (Product.Name)
    category_lower = PREPACKAGED_FLOWER_CATEGORY.strip().lower()
    by_strain: dict[str, dict] = defaultdict(lambda: {
        "net_cents": 0,
        "gross_cents": 0,
        "grams_sold": 0.0,
        "line_count": 0,
        "origin_ids": [],   # for inventory age
        "sold_at_list": [],  # (sold_at, origin_id) for age calc
    })

    for node in nodes:
        cat = (node.get("ProductCategory") or {}).get("Name") or ""
        if category_lower not in (cat or "").lower():
            continue
        product = node.get("Product") or {}
        strain = (product.get("Name") or "").strip() or "Unknown"
        by_strain[strain]["net_cents"] += node.get("NetPrice") or 0
        by_strain[strain]["gross_cents"] += node.get("GrossPrice") or 0
        grams = weight_to_grams(node.get("NetWeight"), node.get("NetWeightUOM"))
        if grams <= 0:
            # Fallback: UnitWeight
            grams = weight_to_grams(node.get("UnitWeight"), node.get("UnitWeightUOM"))
        by_strain[strain]["grams_sold"] += grams
        by_strain[strain]["line_count"] += 1
        origin_id = node.get("OriginId")
        sold_at = node.get("SoldAt")
        if origin_id and sold_at:
            by_strain[strain]["sold_at_list"].append((sold_at, str(origin_id).strip()))

    # Optional: fetch packages to get createdAt for inventory age
    # Use a wider window (e.g. 4 months) so we have package creation dates for sold items
    package_created: dict[str, datetime] = {}
    all_origin_ids = set()
    for strain, data in by_strain.items():
        for _, oid in data["sold_at_list"]:
            if oid:
                all_origin_ids.add(oid)
    if all_origin_ids:
        pkg_start = (start_date - timedelta(days=60)).strftime("%Y-%m-%dT00:00:00.000Z")
        pkg_where = date_range_to_where("createdAt", pkg_start, to_iso)
        pkg_vars = {"first": PAGE_SIZE, "where": pkg_where}
        try:
            pkg_nodes = fetch_paginated(
                "findPackages",
                PACKAGES_TABLE_QUERY,
                pkg_vars,
                credentials_path=credentials_path,
            )
            for p in pkg_nodes:
                created = p.get("createdAt")
                if not created:
                    continue
                dt = parse_iso(created)
                if not dt:
                    continue
                for key in (p.get("objectId"), p.get("id")):
                    if key and str(key).strip():
                        package_created[str(key).strip()] = dt
        except Exception as e:
            print(f"Note: could not fetch packages for inventory age: {e}", file=sys.stderr)

    # Compute average days in inventory per strain
    for strain, data in by_strain.items():
        days_list = []
        for sold_at_str, oid in data["sold_at_list"]:
            created = package_created.get(oid)
            sold_at = parse_iso(sold_at_str)
            if created and sold_at and sold_at >= created:
                delta = (sold_at - created).total_seconds() / 86400
                days_list.append(delta)
        data["avg_days_in_inventory"] = sum(days_list) / len(days_list) if days_list else None
        data["items_with_age"] = len(days_list)

    # Sort by net sales descending
    sorted_strains = sorted(
        by_strain.keys(),
        key=lambda s: by_strain[s]["net_cents"],
        reverse=True,
    )

    print()
    print("=" * 80)
    print("Prepackaged Flower — Sales metrics (last 2 months)")
    print("=" * 80)
    print(f"Date range: {from_iso[:10]} to {to_iso[:10]}")
    print(f"Category filter: \"{PREPACKAGED_FLOWER_CATEGORY}\" (case-insensitive)")
    print(f"Strains: {len(by_strain)}")
    print()

    if not sorted_strains:
        print("No order items found in that category for the date range.")
        return

    # Table header
    print(f"{'Strain':<40} {'Net $':>12} {'Gross $':>12} {'Grams':>10} {'Avg days inv':>12} {'Lines':>6}")
    print("-" * 92)

    total_net = 0.0
    total_gross = 0.0
    total_grams = 0.0
    for strain in sorted_strains:
        d = by_strain[strain]
        net = d["net_cents"] / 100.0
        gross = d["gross_cents"] / 100.0
        grams = d["grams_sold"]
        total_net += net
        total_gross += gross
        total_grams += grams
        avg_days = d.get("avg_days_in_inventory")
        avg_str = f"{avg_days:.1f}" if avg_days is not None else "—"
        print(f"{strain[:39]:<40} {net:>12,.2f} {gross:>12,.2f} {grams:>10.2f} {avg_str:>12} {d['line_count']:>6}")

    print("-" * 92)
    print(f"{'TOTAL':<40} {total_net:>12,.2f} {total_gross:>12,.2f} {total_grams:>10.2f}")
    print()
    print("Note: 'Avg days inv' = average days from package creation to sale (when package data available).")
    print("=" * 80)


if __name__ == "__main__":
    main()
