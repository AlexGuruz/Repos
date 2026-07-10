"""Earliest Cartel 7pk preroll intake (findPackages) + days to sell through first same-day batch.

Growflow OrderItem.OriginId is a compliance tag (e.g. 1A40E...), not package objectId.
Sell-through uses FIFO: order lines per Product.Name, oldest package consumes earliest sales.
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.growflow_queries import ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_BRAND, PACKAGES_TABLE_QUERY, PAGE_SIZE, fetch_paginated


# 7pk multipack: 7pk+prer, Cartel+8.4g, or Infused Pre-Roll Bundle+8.4g (Cartel Oil Co on Brand in app).
PKG_NAME_RE = (
    r"(?i)(cartel.*7[\s-]*pk.*prer)|(cartel.*8\.4\s*g)"
    r"|(infused.{0,220}(pre[\s-]?roll|preroll).{0,220}bundle.{0,220}(8\.4\s*g|8\.4G))"
    r"|((8\.4\s*g|8\.4G).{0,220}infused.{0,220}(pre[\s-]?roll|preroll).{0,220}bundle)"
)


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


def parse_iso(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_cartel_7pk_packages(cp: str | None) -> list[dict]:
    start_utc = datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_utc = datetime.now(timezone.utc)
    seen: set[str] = set()
    out: list[dict] = []
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, 120):
        where = {
            "createdAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
            "Product": {"have": {"Name": {"matchesRegex": PKG_NAME_RE}}},
        }
        nodes = fetch_paginated(
            "findPackages",
            PACKAGES_TABLE_QUERY,
            {"first": PAGE_SIZE, "where": where},
            credentials_path=cp,
        )
        for n in nodes:
            oid = str(n.get("objectId") or "").strip()
            if not oid or oid in seen:
                continue
            seen.add(oid)
            out.append(n)
    return out


def fetch_cartel_7pk_order_lines(from_utc: datetime, cp: str | None) -> list[dict]:
    end_utc = datetime.now(timezone.utc)
    seen: set[str] = set()
    out: list[dict] = []
    for fi, ti in iter_sold_at_date_chunks(from_utc, end_utc, 30):
        where = {
            "SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
            "Product": {"have": {"Name": {"matchesRegex": PKG_NAME_RE}}},
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
            out.append(n)
    return out


def main() -> None:
    _load_config()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: missing credentials")
        sys.exit(1)

    tz = _store_tz()
    print("Fetching Cartel 7pk preroll packages (createdAt 2018 .. now)...", flush=True)
    pkgs = fetch_cartel_7pk_packages(cp)
    if not pkgs:
        print("No matching packages.")
        sys.exit(0)

    pkgs.sort(key=lambda p: parse_iso(p.get("createdAt")) or datetime.max.replace(tzinfo=timezone.utc))
    earliest = pkgs[0]
    t0 = parse_iso(earliest.get("createdAt"))
    if not t0:
        print("Earliest package has no createdAt")
        sys.exit(1)

    local_day = t0.astimezone(tz).date()
    batch = []
    for p in pkgs:
        ct = parse_iso(p.get("createdAt"))
        if ct and ct.astimezone(tz).date() == local_day:
            batch.append(p)

    print()
    print("=== First Cartel 7pk preroll package (findPackages) ===")
    print(f"  createdAt (UTC): {t0.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Store local ({getattr(tz, 'key', tz)}): {t0.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Product: {(earliest.get('Product') or {}).get('Name')}")
    print(f"  objectId: {earliest.get('objectId')}  SKU: {earliest.get('SKU')}")
    print(f"  OriginalQty: {earliest.get('OriginalQty')}  CurrentQty: {earliest.get('CurrentQty')}")
    print()
    print(f"=== Same-store-local-date intake batch ({local_day}): {len(batch)} packages ===")
    for p in sorted(batch, key=lambda x: str((x.get("Product") or {}).get("Name"))):
        pr = p.get("Product") or {}
        print(
            f"  {p.get('objectId')} | OQ={p.get('OriginalQty')} CQ={p.get('CurrentQty')} | {pr.get('Name')}"
        )

    batch_ids = {str(p.get("objectId")) for p in batch}
    total_oq = sum(int(p.get("OriginalQty") or 0) for p in batch)
    total_cq = sum(int(p.get("CurrentQty") or 0) for p in batch)
    print(f"  Sum OriginalQty (batch): {total_oq}  Sum CurrentQty: {total_cq}")

    print()
    print("Fetching order lines (SoldAt) from first package date for FIFO sell-through...", flush=True)
    lines = fetch_cartel_7pk_order_lines(t0, cp)
    by_name: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for n in lines:
        nm = str((n.get("Product") or {}).get("Name") or "").strip()
        if not nm:
            continue
        sold = parse_iso(n.get("SoldAt"))
        if not sold:
            continue
        by_name[nm].append((sold, str(n.get("OriginId") or "")))

    for nm in by_name:
        by_name[nm].sort(key=lambda x: x[0])

    # All packages grouped by exact Product.Name, FIFO by package createdAt
    by_name_pkgs: dict[str, list[dict]] = defaultdict(list)
    for p in pkgs:
        nm = str((p.get("Product") or {}).get("Name") or "").strip()
        if nm:
            by_name_pkgs[nm].append(p)
    for nm in by_name_pkgs:
        by_name_pkgs[nm].sort(
            key=lambda x: parse_iso(x.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc)
        )

    batch_last_sales: list[datetime] = []
    batch_first_sales: list[datetime] = []
    print()
    print("=== FIFO per SKU (package order = createdAt) — packages in first batch only ===")
    for p in sorted(batch, key=lambda x: parse_iso(x.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc)):
        nm = str((p.get("Product") or {}).get("Name") or "").strip()
        oid = str(p.get("objectId"))
        oq = int(p.get("OriginalQty") or 0)
        created = parse_iso(p.get("createdAt"))
        chain = by_name_pkgs.get(nm, [])
        idx = next((i for i, x in enumerate(chain) if str(x.get("objectId")) == oid), -1)
        if idx < 0 or oq <= 0 or not created:
            print(f"  {oid[:8]}… | SKIP (no chain or OQ)")
            continue
        sales_times = [t for t, _ in by_name[nm] if t >= created]
        # Skip sales consumed by earlier packages of same name
        consumed_before = sum(int(chain[i].get("OriginalQty") or 0) for i in range(idx))
        window = sales_times[consumed_before : consumed_before + oq]
        if len(window) < oq:
            print(
                f"  {nm[:50]}… | OQ={oq} matched_lines={len(window)} (short — restock or line qty not 1)"
            )
        if window:
            batch_first_sales.append(window[0])
            batch_last_sales.append(window[-1])
            print(
                f"  {oid} | first_sale {window[0].strftime('%Y-%m-%d %H:%M')} UTC | "
                f"last_sale {window[-1].strftime('%Y-%m-%d %H:%M')} UTC | OQ={oq}"
            )

    if batch_last_sales and batch_first_sales:
        recv = min(parse_iso(p.get("createdAt")) for p in batch if parse_iso(p.get("createdAt")))
        last = max(batch_last_sales)
        first_sale_any = min(batch_first_sales)
        days_recv_to_last = (last - recv).total_seconds() / 86400.0
        days_recv_to_first = (first_sale_any - recv).total_seconds() / 86400.0
        print()
        print("=== Sell-through of first intake batch (FIFO, 1 line = 1 unit) ===")
        print(f"  Receipt window start (earliest package createdAt): {recv.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"  First sale from any batch SKU: {first_sale_any.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"  Last sale to clear batch (last of batch SKUs): {last.strftime('%Y-%m-%d %H:%M')} UTC")
        print(
            f"  Days receipt -> last sale (batch depleted): {days_recv_to_last:.2f} (~{days_recv_to_last/7:.1f} weeks)"
        )
        print(f"  Days receipt -> first sale: {days_recv_to_first:.2f}")

    print()
    print("Note: If Growflow uses line quantity > 1, days are still right but OQ vs line count may mismatch.")


if __name__ == "__main__":
    main()
