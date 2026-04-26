"""
Estimate sell-through (days) per brand × format bucket for packages on a transfer.

Cartel infused multipacks on transfers are aligned with retail signifiers: **Cartel Oil Co** brand plus
**Infused Pre-Roll Bundle** and **8.4G** in the product name. Spec: `docs/GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md`;
code: `lib/cartel_7pk_names.py`.

Uses the same **format buckets** as the buy planner (`lib.brand_merit_pool.package_format_bucket`
/ `order_line_format_bucket`) so velocity matches existing projection logic.

Velocity: trailing `findOrderItems` SoldAt window, **1 line ≈ 1 unit** (Retail API has no line qty).

Default transfer: latest **Accepted** by `ReceivedAt` (same as `_last_accepted_transfer.py`).

Usage:
  PYTHONPATH=. python scripts/transfer_sellout_by_brand_category.py
  PYTHONPATH=. python scripts/transfer_sellout_by_brand_category.py --days 90 --transfer-id BMaBmjDNmT
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.brand_merit_pool import (
    brand_label_from_line,
    order_line_format_bucket,
    package_brand,
    package_format_bucket,
)
from lib.cartel_7pk_names import is_cartel_7pk_product_name, product_brand_name
from lib.growflow_graphql import graphql_request
from lib.growflow_queries import ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_BRAND, PAGE_SIZE, fetch_paginated

# Transfer validation: 7pk = Cartel Oil Co + Infused Pre-Roll Bundle + 8.4g, or legacy 7pk/8.4g name rules.
_RX_14 = re.compile(r"(?i)14[\s-]*pk|14PK")
_RX_DISPO = re.compile(r"(?i)dispo|disposable")


def _package_audit_tag(pkg: dict) -> str:
    pr = pkg.get("Product")
    if not pr:
        return "Product_NULL"
    nm = str(pr.get("Name") or "")
    if not nm.strip():
        return "Product_EMPTY_NAME"
    bn = product_brand_name(pr)
    if _RX_14.search(nm):
        return "name_14pk"
    if _RX_DISPO.search(nm):
        return "name_dispo"
    if is_cartel_7pk_product_name(nm, brand_name=bn, pack_re=None):
        return "name_7pk"
    return "name_other"


def transfer_package_validation(packages: list[dict]) -> dict[str, dict[str, int]]:
    """Ground-truth counts from API rows (Product null vs name hints)."""
    acc: dict[str, dict[str, int]] = defaultdict(lambda: {"pkgs": 0, "qty": 0})
    for p in packages:
        tag = _package_audit_tag(p)
        oq = int(p.get("OriginalQty") or 0)
        acc[tag]["pkgs"] += 1
        acc[tag]["qty"] += max(oq, 0)
    return dict(acc)


def blend_unassigned_velocity(
    *,
    packages: list[dict],
    brand: str,
    vel: dict[tuple[str, str], int],
    days: int,
) -> tuple[float, float, int, str]:
    """
    Equivalent order-lines in window and per-day rate for Product-null stock: weight each
    format bucket's observed line count by **labeled** units of the same brand on this transfer.
    (Does not assume null rows are 7pk — API leaves them unidentified.)
    Returns (per_day, equiv_lines_in_window, labeled_units_in_mix, note).
    """
    mix: dict[str, int] = defaultdict(int)
    for pkg in packages:
        pr = pkg.get("Product") or {}
        if not str(pr.get("Name") or "").strip():
            continue
        oq = int(pkg.get("OriginalQty") or 0)
        if oq <= 0:
            continue
        if package_brand_resolved(pkg) != brand:
            continue
        mix[package_format_bucket(pkg)] += oq
    named_total = sum(mix.values())
    if named_total <= 0:
        for pkg in packages:
            pr = pkg.get("Product") or {}
            if not str(pr.get("Name") or "").strip():
                continue
            oq = int(pkg.get("OriginalQty") or 0)
            if oq <= 0:
                continue
            mix[package_format_bucket(pkg)] += oq
        named_total = sum(mix.values())
    if not days:
        return (0.0, 0.0, named_total, "zero-day window")
    if named_total <= 0:
        tot = float(brand_total_lines(vel, brand))
        return (tot / float(days), tot, 0, "no labeled packages — blended brand velocity")
    equiv_lines = 0.0
    for bucket, q in mix.items():
        w = q / float(named_total)
        equiv_lines += w * float(vel.get((brand, bucket), 0))
    per_day = equiv_lines / float(days)
    note = f"mix-weighted from {named_total} labeled {brand} units (format buckets on transfer)"
    return (per_day, equiv_lines, named_total, note)


TRANSFER_QUERY = """
query TransferPkgs($id: ID!) {
  findTransfers(first: 1, where: { objectId: { equalTo: $id } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        Packages {
          ... on Packages {
            objectId
            SKU
            OriginalQty
            Product {
              Name
              SKU
              Brand { Name }
              ProductCategory { Name }
            }
          }
        }
      }
    }
  }
}
"""

LATEST_ACCEPTED = """
query LatestAccepted {
  findTransfers(first: 1, order: [ReceivedAt_DESC], where: { Status: { equalTo: "Accepted" } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        Packages {
          ... on Packages {
            objectId
            SKU
            OriginalQty
            Product {
              Name
              SKU
              Brand { Name }
              ProductCategory { Name }
            }
          }
        }
      }
    }
  }
}
"""


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def _load_config() -> None:
    p = _root / "config" / "config.yaml"
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _yaml_scalar(text, "org_id")
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org


def _store_tz():
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = _root / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.now(timezone.utc).astimezone().tzinfo or timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _infer_brand_from_title(name: str) -> str | None:
    u = (name or "").upper()
    if u.startswith("CARTEL ") or " CARTEL " in u:
        return "Cartel"
    return None


def package_brand_resolved(pkg: dict) -> str:
    b = package_brand(pkg, {})
    if b != "(no brand)":
        return b
    nm = str((pkg.get("Product") or {}).get("Name") or "")
    guess = _infer_brand_from_title(nm)
    return guess if guess else b


def fetch_transfer_node(transfer_id: str | None, cp: str | None) -> dict | None:
    if transfer_id:
        r = graphql_request(TRANSFER_QUERY, {"id": transfer_id}, credentials_path=cp)
    else:
        r = graphql_request(LATEST_ACCEPTED, {}, credentials_path=cp)
    if r.get("errors"):
        raise RuntimeError(r["errors"][0].get("message", r["errors"]))
    edges = ((r.get("data") or {}).get("findTransfers") or {}).get("edges") or []
    if not edges:
        return None
    return edges[0].get("node") or {}


UNASSIGNED = "Unassigned (no Product on package)"

def inbound_by_brand_bucket(packages: list[dict]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = defaultdict(int)
    for pkg in packages:
        oq = int(pkg.get("OriginalQty") or 0)
        if oq <= 0:
            continue
        brand = package_brand_resolved(pkg)
        bucket = package_format_bucket(pkg)
        out[(brand, bucket)] += oq
    return dict(out)


def dominant_brand_for_transfer(inbound: dict[tuple[str, str], int]) -> str:
    """Map (no brand) buckets to the main brand on this transfer."""
    by_b: dict[str, int] = defaultdict(int)
    for (b, _), q in inbound.items():
        by_b[b] += q
    named = {b for b in by_b if b != "(no brand)"}
    if len(named) == 1:
        return next(iter(named))
    if "Cartel" in named:
        return "Cartel"
    if named:
        return max(named, key=lambda x: by_b[x])
    return "Cartel"


def reassign_no_brand_unassigned(
    inbound: dict[tuple[str, str], int],
    *,
    dominant: str,
) -> dict[tuple[str, str], int]:
    out = dict(inbound)
    nb_other = out.pop(("(no brand)", "Other"), 0)
    if nb_other <= 0:
        return out
    key = (dominant, UNASSIGNED)
    out[key] = out.get(key, 0) + nb_other
    return out


def brand_total_lines(vel: dict[tuple[str, str], int], brand: str) -> int:
    return sum(c for (b, _), c in vel.items() if b == brand)


def fetch_brand_sales_lines(
    brands: set[str],
    days: int,
    chunk_days: int,
    cp: str | None,
    tz,
) -> list[dict]:
    """Order lines in window where Product.Brand.Name is one of `brands` (case-sensitive API)."""
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)

    brand_list = sorted(brands)
    if len(brand_list) == 1:
        brand_where = {
            "Product": {
                "have": {
                    "Brand": {"have": {"Name": {"equalTo": brand_list[0]}}},
                }
            }
        }
    else:
        brand_where = {
            "OR": [
                {
                    "Product": {
                        "have": {
                            "Brand": {"have": {"Name": {"equalTo": b}}},
                        }
                    }
                }
                for b in brand_list
            ]
        }

    seen: set[str] = set()
    lines: list[dict] = []
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days):
        where = {
            "SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
            **brand_where,
        }
        variables = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated(
                "findOrderItems", ORDER_ITEMS_QUERY, variables, credentials_path=cp
            )
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated(
                    "findOrderItems", ORDER_ITEMS_QUERY_NO_BRAND, variables, credentials_path=cp
                )
            else:
                raise
        for n in nodes:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            lines.append(n)
    return lines


def filter_lines_to_brands(lines: list[dict], brands: set[str]) -> list[dict]:
    """Client filter + title inference when Brand missing on line."""
    out = []
    brands_lower = {b.lower() for b in brands}
    for n in lines:
        b = brand_label_from_line(n)
        if b != "(no brand)" and b in brands:
            out.append(n)
            continue
        if b == "(no brand)":
            nm = str((n.get("Product") or {}).get("Name") or "")
            g = _infer_brand_from_title(nm)
            if g and g in brands:
                out.append(n)
    return out


def velocity_by_brand_bucket(lines: list[dict]) -> dict[tuple[str, str], int]:
    ctr: dict[tuple[str, str], int] = defaultdict(int)
    for n in lines:
        b = brand_label_from_line(n)
        if b == "(no brand)":
            nm = str((n.get("Product") or {}).get("Name") or "")
            g = _infer_brand_from_title(nm)
            b = g if g else b
        fb = order_line_format_bucket(n)
        ctr[(b, fb)] += 1
    return dict(ctr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transfer-id", default=None, help="Transfer objectId (default: latest Accepted)")
    ap.add_argument("--days", type=int, default=90, help="Trailing days for velocity (store-local)")
    ap.add_argument("--chunk-days", type=int, default=14, help="SoldAt chunk size")
    args = ap.parse_args()

    _load_config()
    tz = _store_tz()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: missing credentials", file=sys.stderr)
        sys.exit(1)

    node = fetch_transfer_node(args.transfer_id, cp)
    if not node:
        print("No transfer found.")
        sys.exit(1)

    pkgs = node.get("Packages") or []
    if not isinstance(pkgs, list):
        pkgs = []

    inbound = inbound_by_brand_bucket(pkgs)
    dominant = dominant_brand_for_transfer(inbound)
    inbound = reassign_no_brand_unassigned(inbound, dominant=dominant)
    brands = {b for (b, _) in inbound.keys() if b != "(no brand)"}
    if not brands:
        brands = {dominant}

    print(f"Transfer {node.get('objectId')}  Status={node.get('Status')}  ReceivedAt={node.get('ReceivedAt')}")
    print(f"Velocity window: {args.days} store-local days ending {datetime.now(tz).date()} ({tz})")
    print(f"Brands on transfer (for API filter): {sorted(brands)}")
    print()
    val = transfer_package_validation(pkgs)
    print(
        "API validation (transfer packages; Cartel multipack = Cartel Oil Co + Infused Pre-Roll Bundle + 8.4G,"
        " or legacy 7pk / 8.4g in name):"
    )
    for tag in sorted(val.keys()):
        d = val[tag]
        print(f"  {tag}: {d['pkgs']} pkgs, {d['qty']} OriginalQty")
    print()

    lines = fetch_brand_sales_lines(brands, args.days, args.chunk_days, cp, tz)
    lines = filter_lines_to_brands(lines, brands)
    vel = velocity_by_brand_bucket(lines)

    print(
        f"Pulled {len(lines)} order lines for brand filter in {args.days}d "
        f"(deduped by objectId; 1 line ~= 1 unit).\n"
    )

    total_in = sum(inbound.values())
    pool_per_day = len(lines) / float(args.days) if args.days else 0.0
    if pool_per_day > 0:
        pool_days = total_in / pool_per_day
        print(
            f"Portfolio (all inbound units, blended brand velocity): "
            f"{total_in} units / {pool_per_day:.3f} per day -> ~{pool_days:.1f} days (~{pool_days/7:.1f} wk)"
        )
        print("(Per-category rows below use bucket-specific rates; they overlap the same sales stream.)\n")

    rows = []
    for (brand, bucket), qty in sorted(inbound.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        note = ""
        if bucket == UNASSIGNED:
            per_day, equiv_lines, _named_n, mix_note = blend_unassigned_velocity(
                packages=pkgs, brand=brand, vel=vel, days=args.days
            )
            sold = int(round(equiv_lines))
            note = f" ({mix_note})"
        else:
            sold = vel.get((brand, bucket), 0)
            per_day = sold / float(args.days) if args.days else 0.0
        if per_day > 0:
            days_clear = qty / per_day
        else:
            days_clear = float("inf")
        rows.append((brand, bucket, qty, sold, per_day, days_clear, note))

    print(f"{'Brand':<14} {'Category (format bucket)':<22} {'Inbound qty':>12} {'Lines':>8} {'/day':>8} {'Est days':>10} {'Est wk':>8}")
    print("-" * 92)
    for brand, bucket, qty, sold, per_day, days_clear, note in rows:
        wk = days_clear / 7.0 if days_clear != float("inf") else float("inf")
        dstr = f"{days_clear:.1f}" if days_clear != float("inf") else "n/a (0 sales)"
        wstr = f"{wk:.1f}" if wk != float("inf") else "n/a"
        bkt = (bucket[:18] + "..") if len(bucket) > 22 else bucket[:22]
        print(
            f"{brand[:14]:<14} {bkt:<22} {qty:12d} {sold:8d} {per_day:8.3f} {dstr:>10} {wstr:>8}{note}"
        )

    print()
    print("Notes:")
    print("  - Category = planner format bucket (same as brand_merit_pool / buy planner), not raw Growflow category.")
    print("  - Inbound qty = sum OriginalQty on transfer packages for that brand x bucket.")
    print("  - Unassigned (Product null on package): velocity = mix-weighted lines from **labeled** same-brand")
    print("    units on this transfer (format buckets). Not 7pk-only; API does not identify null rows.")
    print("  - If Est days = n/a, zero matching sales in window; try --days 183.")


if __name__ == "__main__":
    main()
