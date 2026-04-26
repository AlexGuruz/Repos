"""Pull findOrderItems + findPackages from GrowFlow; filter SAP Xtrax + Stix for 2-week stock math.

Convention: 1 order line ≈ 1 unit (no line quantity in schema). Override window with GROWFLOW_STIX_WINDOW_DAYS.
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lib.growflow_graphql import resolve_graphql_url
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PACKAGES_TABLE_QUERY_WITH_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def _retail_org(repo_root: Path) -> str | None:
    p = repo_root / "config" / "config.yaml"
    if not p.is_file():
        return None
    return _yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "org_id")


def _sales_tz(repo_root: Path):
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = repo_root / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            print("WARNING: invalid timezone, using local", flush=True)
    now = datetime.now().astimezone()
    return now.tzinfo if now.tzinfo else timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _local_day_bounds_utc(d, tz) -> tuple[str, str]:
    start_local = datetime.combine(d, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1) - timedelta(milliseconds=1)

    def fmt_utc(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return fmt_utc(start_local), fmt_utc(end_local)


def _match_stix_xtrax_line(n: dict) -> bool:
    p = n.get("Product") or {}
    brand = ""
    bd = p.get("Brand")
    if isinstance(bd, dict):
        brand = (bd.get("Name") or "").lower()
    name = (p.get("Name") or "").lower()
    sku = f"{n.get('SKU') or ''} {(p.get('SKU') or '')}".lower()
    if "stix" not in name and "stix" not in sku:
        return False
    if brand and "xtrax" in brand:
        return True
    if not brand and ("xtrax" in name or "xtrax" in sku):
        return True
    return False


def _match_stix_xtrax_pkg(node: dict) -> bool:
    p = node.get("Product") or {}
    brand = ""
    bd = p.get("Brand")
    if isinstance(bd, dict):
        brand = (bd.get("Name") or "").lower()
    name = (p.get("Name") or "").lower()
    sku = f"{node.get('SKU') or ''} {(p.get('SKU') or '')}".lower()
    if "stix" not in name and "stix" not in sku:
        return False
    if brand and "xtrax" in brand:
        return True
    if not brand and ("xtrax" in name or "xtrax" in sku):
        return True
    return False


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    window = int((os.environ.get("GROWFLOW_STIX_WINDOW_DAYS") or "14").strip() or "14")

    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _retail_org(repo_root)
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org
            print(f"Retail org: {org}", flush=True)

    cp = _credentials_path()
    tz = _sales_tz(repo_root)
    end_local = datetime.now(tz).date()
    start_local = end_local - timedelta(days=window - 1)

    print(f"Sales window (local): {start_local} .. {end_local} ({window} days)", flush=True)
    print(f"Timezone: {getattr(tz, 'key', None) or tz}", flush=True)
    print(f"GraphQL: {resolve_graphql_url()}", flush=True)
    print(f"Creds: {cp or 'GROWFLOW_ACCESS_TOKEN'}", flush=True)

    def fetch_chunk(d0, d1):
        from_iso, _ = _local_day_bounds_utc(d0, tz)
        _, to_iso = _local_day_bounds_utc(d1, tz)
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        variables = {"first": PAGE_SIZE, "where": where}
        try:
            return fetch_paginated(
                "findOrderItems",
                ORDER_ITEMS_QUERY,
                variables,
                credentials_path=cp,
            )
        except RuntimeError as e:
            if "Brand" in str(e):
                return fetch_paginated(
                    "findOrderItems",
                    ORDER_ITEMS_QUERY_NO_BRAND,
                    variables,
                    credentials_path=cp,
                )
            raise

    all_nodes: list[dict] = []
    d = start_local
    chunk_days = 14
    while d <= end_local:
        d1 = min(d + timedelta(days=chunk_days - 1), end_local)
        chunk = fetch_chunk(d, d1)
        all_nodes.extend(chunk)
        print(f"  SoldAt chunk {d} .. {d1}: {len(chunk)} line(s)", flush=True)
        d = d1 + timedelta(days=1)

    matched = [n for n in all_nodes if _match_stix_xtrax_line(n)]
    print()
    print(
        "=== SAP Xtrax + Stix (product/sku contains 'stix'; brand or text contains 'xtrax') ===",
        flush=True,
    )
    print(f"Total order lines in window: {len(all_nodes)}", flush=True)
    print(f"Matched lines (1 line = 1 unit): {len(matched)}", flush=True)

    ctr: Counter[str] = Counter()
    for n in matched:
        p = n.get("Product") or {}
        b = "?"
        bd = p.get("Brand")
        if isinstance(bd, dict):
            b = bd.get("Name") or "?"
        nm = p.get("Name") or ""
        sku = p.get("SKU") or n.get("SKU") or ""
        ctr[f"{b} | {nm} | {sku}"] += 1

    print("\nTop product keys by line count:", flush=True)
    for k, v in ctr.most_common(25):
        print(f"  {v:4d}  {k}", flush=True)

    daily = len(matched) / window if window else 0.0
    need_same_pace = math.ceil(daily * 14) if daily else 0
    print(f"\nAvg units/day (over {window}d): {daily:.3f}", flush=True)
    print(
        f"If that pace holds, ~units sold in next 14 days: {need_same_pace} (excl. on-hand / lead time)",
        flush=True,
    )

    print("\nFetching findPackages (all pages) for on-hand ...", flush=True)
    try:
        pkgs = fetch_paginated(
            "findPackages",
            PACKAGES_TABLE_QUERY_WITH_BRAND,
            {"first": PAGE_SIZE, "where": {}},
            credentials_path=cp,
        )
    except RuntimeError as e:
        print(f"  Packages skip: {e}", flush=True)
        pkgs = []

    inv = [x for x in pkgs if _match_stix_xtrax_pkg(x)]
    qty = sum(int(x.get("CurrentQty") or 0) for x in inv)
    print(f"Packages scanned: {len(pkgs)}", flush=True)
    print(f"Matched Stix+Xtrax packages: {len(inv)}  sum(CurrentQty): {qty}", flush=True)
    if daily > 0:
        cover = qty / daily
        order_to_14 = max(0, need_same_pace - qty)
        print(f"At avg daily {daily:.3f}, on-hand ~{cover:.1f} days cover", flush=True)
        print(f"Rough order qty for ~14d cover from current on-hand: {order_to_14}", flush=True)


if __name__ == "__main__":
    main()
