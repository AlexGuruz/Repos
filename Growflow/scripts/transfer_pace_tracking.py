"""
Receipt-anchored sales pace for a Growflow inventory transfer cohort.

Tracks sell-through since ``ReceivedAt`` to calibrate reorder qty (default 7-day supply target).
The **full transfer** is tracked with **each product format on its own row** (7pk, 5pk, singles, blunts, …).

Reorder sizing is treated as **preliminary** until the receipt has been on shelf for at least
``--min-pace-days`` (default **14**). Early numbers are for monitoring only.

State file: ``data/pace_tracking.json`` (gitignored pattern — local ops state).

Usage:
  PYTHONPATH=. python scripts/transfer_pace_tracking.py --start --supplier "Clone To Grown, LLC"
  PYTHONPATH=. python scripts/transfer_pace_tracking.py --report
  PYTHONPATH=. python scripts/transfer_pace_tracking.py --report --target-days 7
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.cartel_7pk_names import (
    CARTEL_PACE_BUCKETS_ORDER,
    cartel_reorder_pace_bucket,
    order_item_brand_name,
    product_brand_name,
)
from lib.growflow_graphql import graphql_request
from lib.growflow_queries import ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_BRAND, PAGE_SIZE, fetch_paginated
from lib.transfer_receipt_export import parse_received_at_utc

DEFAULT_STATE = _root / "data" / "pace_tracking.json"
DEFAULT_MIN_RELIABLE_PACE_DAYS = 14

TRANSFER_BY_ID = """
query TransferById($id: ID!) {
  findTransfers(first: 1, where: { objectId: { equalTo: $id } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        FromName
        Packages {
          ... on Packages {
            objectId
            OriginalQty
            CurrentQty
            Product { objectId Name Brand { Name } }
          }
        }
      }
    }
  }
}
"""

LATEST_BY_SUPPLIER = """
query LatestTransfers($first: Int!) {
  findTransfers(first: $first, order: [ReceivedAt_DESC], where: { Status: { equalTo: "Accepted" } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        FromName
        Packages {
          ... on Packages {
            objectId
            OriginalQty
            CurrentQty
            Product { objectId Name Brand { Name } }
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


def _load_org() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = _root / "config" / "config.yaml"
    if not cfg.is_file():
        return
    org = _yaml_scalar(cfg.read_text(encoding="utf-8", errors="replace"), "org_id")
    if org:
        os.environ["GROWFLOW_RETAIL_ORG"] = org


def _store_tz() -> ZoneInfo | timezone:
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        cfg = _root / "config" / "config.yaml"
        if cfg.is_file():
            name = (_yaml_scalar(cfg.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
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


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().upper())


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"active": [], "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _summarize_transfer(node: dict[str, Any]) -> dict[str, Any]:
    pkgs = [p for p in (node.get("Packages") or []) if isinstance(p, dict)]
    product_ids: set[str] = set()
    product_id_to_bucket: dict[str, str] = {}
    inbound_by_bucket: dict[str, int] = defaultdict(int)
    on_hand_by_bucket: dict[str, int] = defaultdict(int)
    for pkg in pkgs:
        oq = int(pkg.get("OriginalQty") or 0)
        cq = int(pkg.get("CurrentQty") or 0)
        if oq <= 0 and cq <= 0:
            continue
        pr = pkg.get("Product") or {}
        oid = str(pr.get("objectId") or "").strip()
        name = str(pr.get("Name") or "")
        brand = product_brand_name(pr if isinstance(pr, dict) else None)
        bucket = cartel_reorder_pace_bucket(name, brand)
        if oid:
            product_ids.add(oid)
            product_id_to_bucket[oid] = bucket
        inbound_by_bucket[bucket] += max(oq, 0)
        on_hand_by_bucket[bucket] += max(cq, 0)
    return {
        "transfer_object_id": str(node.get("objectId") or ""),
        "status": str(node.get("Status") or ""),
        "received_at": str(node.get("ReceivedAt") or ""),
        "supplier": str(node.get("FromName") or ""),
        "package_lines": len(pkgs),
        "units_received": sum(int(p.get("OriginalQty") or 0) for p in pkgs),
        "units_on_hand": sum(int(p.get("CurrentQty") or 0) for p in pkgs),
        "product_ids": sorted(product_ids),
        "product_id_to_bucket": product_id_to_bucket,
        "inbound_by_bucket": dict(inbound_by_bucket),
        "on_hand_by_bucket": dict(on_hand_by_bucket),
    }


def _fetch_transfer(*, transfer_id: str | None, supplier: str | None, cp: str | None) -> dict[str, Any] | None:
    if transfer_id:
        r = graphql_request(TRANSFER_BY_ID, {"id": transfer_id}, credentials_path=cp)
        if r.get("errors"):
            raise RuntimeError(r["errors"][0].get("message", r["errors"]))
        edges = ((r.get("data") or {}).get("findTransfers") or {}).get("edges") or []
        return (edges[0].get("node") if edges else None) or None
    target = _norm(supplier or "")
    r = graphql_request(LATEST_BY_SUPPLIER, {"first": 80}, credentials_path=cp)
    if r.get("errors"):
        raise RuntimeError(r["errors"][0].get("message", r["errors"]))
    for e in ((r.get("data") or {}).get("findTransfers") or {}).get("edges") or []:
        n = e.get("node") or {}
        if _norm(str(n.get("FromName") or "")) == target:
            return n
    return None


def _sales_since_receipt(
    product_ids: set[str],
    product_id_to_bucket: dict[str, str],
    received_at: datetime,
    *,
    cp: str | None,
    chunk_days: int,
) -> tuple[int, dict[str, int]]:
    end_utc = datetime.now(timezone.utc)
    start_utc = received_at.astimezone(timezone.utc)
    units = 0
    sold_by_bucket: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days=chunk_days):
        where = {"SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti}}
        base = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY, base, credentials_path=cp)
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY_NO_BRAND, base, credentials_path=cp)
            else:
                raise
        for n in nodes:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            prod = n.get("Product") or {}
            oid = str(prod.get("objectId") or "").strip()
            if oid not in product_ids:
                continue
            units += 1
            bucket = product_id_to_bucket.get(oid)
            if not bucket:
                bucket = cartel_reorder_pace_bucket(
                    str(prod.get("Name") or ""),
                    order_item_brand_name(n),
                )
            sold_by_bucket[bucket] += 1
    return units, dict(sold_by_bucket)


def _format_bucket_rows(
    *,
    inbound_map: dict[str, int],
    on_hand_map: dict[str, int],
    sold_by_bucket: dict[str, int],
    elapsed_days: float,
    target_days: int,
) -> list[tuple[str, int, int, int, float, int, str]]:
    """Return display rows: (bucket, inbound, on_hand, sold, per_day, need, cover_str)."""
    bucket_keys = list(CARTEL_PACE_BUCKETS_ORDER)
    extra = sorted(
        (set(inbound_map) | set(on_hand_map) | set(sold_by_bucket)) - set(bucket_keys),
        key=str.lower,
    )
    rows: list[tuple[str, int, int, int, float, int, str]] = []
    for bucket in bucket_keys + extra:
        inb = inbound_map.get(bucket, 0)
        oh = on_hand_map.get(bucket, 0)
        s = sold_by_bucket.get(bucket, 0)
        if inb == 0 and oh == 0 and s == 0:
            continue
        pd = s / elapsed_days
        need = max(0, int(round(pd * target_days)))
        cover = oh / pd if pd > 0 else float("inf")
        cover_s = f"{cover:.1f}" if cover != float("inf") else "n/a"
        rows.append((bucket, inb, oh, s, pd, need, cover_s))
    return rows


def _print_format_breakdown(
    rows: list[tuple[str, int, int, int, float, int, str]],
    *,
    target_days: int,
    elapsed_days: float,
    pace_reliable: bool,
) -> int:
    """Print table; return sum of per-format reorder units (full order)."""
    need_hdr = f"{target_days}d need" if pace_reliable else f"{target_days}d (prelim)"
    print(f"Full order - each format tracked separately ({need_hdr} per row):")
    print(
        f"{'Format':<22} {'Inbound':>8} {'On hand':>8} {'Sold':>6} "
        f"{'/day':>8} {need_hdr:>10} {'Cover d':>8}"
    )
    print("-" * 78)
    tot_inb = tot_oh = tot_s = tot_need = 0
    for bucket, inb, oh, s, pd, need, cover_s in rows:
        tot_inb += inb
        tot_oh += oh
        tot_s += s
        tot_need += need
        print(f"{bucket[:22]:<22} {inb:8d} {oh:8d} {s:6d} {pd:8.3f} {need:8d} {cover_s:>8}")
    print("-" * 78)
    tot_pd = tot_s / elapsed_days if elapsed_days > 0 else 0.0
    print(
        f"{'TOTAL (full order)':<22} {tot_inb:8d} {tot_oh:8d} {tot_s:6d} "
        f"{tot_pd:8.3f} {tot_need:8d}"
    )
    print("")
    return tot_need


def cmd_start(args: argparse.Namespace) -> int:
    cp = args.credentials or _credentials_path()
    node = _fetch_transfer(transfer_id=args.transfer_id, supplier=args.supplier, cp=cp)
    if not node:
        print(f"No transfer found for supplier={args.supplier!r} transfer_id={args.transfer_id!r}", file=sys.stderr)
        return 1
    summary = _summarize_transfer(node)
    state = _load_state(Path(args.state))
    active = state.setdefault("active", [])
    tid = summary["transfer_object_id"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entry = {
        "transfer_object_id": tid,
        "supplier": summary["supplier"],
        "received_at": summary["received_at"],
        "target_supply_days": int(args.target_days),
        "min_pace_days": int(args.min_pace_days),
        "started_at": now,
        "units_received": summary["units_received"],
        "package_lines": summary["package_lines"],
        "inbound_by_bucket": summary.get("inbound_by_bucket") or {},
        "notes": args.notes or "",
    }
    active = [a for a in active if str(a.get("transfer_object_id") or "") != tid]
    active.insert(0, entry)
    state["active"] = active[: int(args.max_active)]
    _save_state(Path(args.state), state)
    print(f"Started pace tracking: {tid} ({summary['supplier']})")
    print(f"  ReceivedAt: {summary['received_at']}")
    print(f"  Units received: {summary['units_received']}  |  On hand now: {summary['units_on_hand']}")
    print(f"  Target reorder supply: {args.target_days} days per format (reliable after {args.min_pace_days}d on shelf)")
    print(f"  State: {args.state}")
    rows = _format_bucket_rows(
        inbound_map=dict(summary.get("inbound_by_bucket") or {}),
        on_hand_map=dict(summary.get("on_hand_by_bucket") or {}),
        sold_by_bucket={},
        elapsed_days=1.0,
        target_days=int(args.target_days),
    )
    if rows:
        print("")
        print("Inbound by format (tracking each separately):")
        for bucket, inb, oh, *_ in rows:
            print(f"  {bucket}: {inb} units")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    state = _load_state(Path(args.state))
    active = state.get("active") or []
    if not active:
        print("No active pace tracking entries. Run with --start first.", file=sys.stderr)
        return 1
    cp = args.credentials or _credentials_path()
    tz = _store_tz()
    for entry in active:
        tid = str(entry.get("transfer_object_id") or "")
        target_days = int(args.target_days or entry.get("target_supply_days") or 7)
        min_pace_days = int(args.min_pace_days or entry.get("min_pace_days") or DEFAULT_MIN_RELIABLE_PACE_DAYS)
        node = _fetch_transfer(transfer_id=tid, supplier=None, cp=cp)
        if not node:
            print(f"Transfer {tid} not found in API.", file=sys.stderr)
            continue
        summary = _summarize_transfer(node)
        recv = parse_received_at_utc(summary["received_at"])
        if recv is None:
            print(f"Bad ReceivedAt on {tid}", file=sys.stderr)
            continue
        now = datetime.now(timezone.utc)
        elapsed_days = max((now - recv).total_seconds() / 86400.0, 1.0 / 24.0)
        sold, sold_by_bucket = _sales_since_receipt(
            set(summary["product_ids"]),
            dict(summary.get("product_id_to_bucket") or {}),
            recv,
            cp=cp,
            chunk_days=args.chunk_days,
        )
        units_recv = summary["units_received"]
        on_hand = summary["units_on_hand"]
        per_day = sold / elapsed_days
        days_cover = on_hand / per_day if per_day > 0 else float("inf")
        recv_local = recv.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
        bucket_rows = _format_bucket_rows(
            inbound_map=dict(summary.get("inbound_by_bucket") or {}),
            on_hand_map=dict(summary.get("on_hand_by_bucket") or {}),
            sold_by_bucket=sold_by_bucket,
            elapsed_days=elapsed_days,
            target_days=target_days,
        )
        reorder_total = sum(r[5] for r in bucket_rows)
        pace_reliable = elapsed_days >= float(min_pace_days)
        reliable_local = (recv + timedelta(days=min_pace_days)).astimezone(tz).strftime("%Y-%m-%d")
        print(f"=== Pace tracking: {tid} ===")
        print(f"Supplier: {summary['supplier']}")
        print(f"Received (local): {recv_local}")
        print(f"Tracking since: {entry.get('started_at', '?')}  |  Target supply: {target_days} days per format")
        print(f"Units received: {units_recv}  |  On hand: {on_hand}  |  Sold since receipt: {sold}")
        print(f"Elapsed on shelf: {elapsed_days:.2f} days  |  Blended pace: {per_day:.3f} units/day")
        if pace_reliable:
            print(f"Pace status: RELIABLE ({min_pace_days}+ days on shelf)")
        else:
            days_left = max(0.0, float(min_pace_days) - elapsed_days)
            print(
                f"Pace status: PRELIMINARY ({elapsed_days:.1f}d on shelf; "
                f"reorder math not actionable until ~{reliable_local}, {days_left:.1f}d left)"
            )
        if per_day > 0:
            print(f"Days of cover (blended on-hand / pace): {days_cover:.1f}")
        else:
            print("Days of cover: n/a (no sales yet since receipt)")
        if pace_reliable:
            print(
                f"Suggested full reorder ({target_days}-day supply, sum of each format): "
                f"{reorder_total} units"
            )
        else:
            print(
                f"Early reorder estimate ({target_days}-day, NOT for ordering yet): "
                f"{reorder_total} units - recheck after {reliable_local}"
            )
        print("")
        _print_format_breakdown(
            bucket_rows,
            target_days=target_days,
            elapsed_days=elapsed_days,
            pace_reliable=pace_reliable,
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Receipt-anchored transfer pace tracking for reorder sizing")
    ap.add_argument("--start", action="store_true", help="Register latest transfer (by supplier or id) for tracking")
    ap.add_argument("--report", action="store_true", help="Print current pace vs target supply days")
    ap.add_argument("--supplier", default="Clone To Grown, LLC", help="Supplier FromName for --start")
    ap.add_argument("--transfer-id", default=None, help="Explicit transfer objectId (overrides --supplier lookup)")
    ap.add_argument("--target-days", type=int, default=7, help="Reorder supply target in days (default 7)")
    ap.add_argument(
        "--min-pace-days",
        type=int,
        default=DEFAULT_MIN_RELIABLE_PACE_DAYS,
        help="Days on shelf before reorder math is treated as actionable (default 14)",
    )
    ap.add_argument("--state", default=str(DEFAULT_STATE), help="JSON state file path")
    ap.add_argument("--max-active", type=int, default=5, help="Max concurrent active tracking entries")
    ap.add_argument("--notes", default="", help="Optional note stored with tracking entry")
    ap.add_argument("--chunk-days", type=int, default=7, help="SoldAt chunk size for sales pull")
    ap.add_argument("--credentials", default=None)
    args = ap.parse_args()

    _load_org()
    if not args.start and not args.report:
        ap.error("Specify --start and/or --report")
    rc = 0
    if args.start:
        rc = max(rc, cmd_start(args))
    if args.report:
        rc = max(rc, cmd_report(args))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
