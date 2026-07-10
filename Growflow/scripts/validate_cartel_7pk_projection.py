"""
Validate Cartel 7pk sell-through projection:
- Probe OrderItem fields (quantity?)
- Deduped vs raw line counts, fallback-key rate
- Velocity 28d / 90d / 183d
- Gross $ sanity (cents sum / lines)
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.cartel_7pk_names import cartel_pack_line_kept_after_fetch, is_cartel_7pk_product_name, order_item_brand_name
from lib.growflow_graphql import graphql_request
from lib.growflow_queries import ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_BRAND, PAGE_SIZE, fetch_paginated

_spec_cb = importlib.util.spec_from_file_location(
    "cb", _root / "scripts" / "_cartel_preroll_velocity_budget.py"
)
_cb = importlib.util.module_from_spec(_spec_cb)
assert _spec_cb.loader
_spec_cb.loader.exec_module(_cb)


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


def item_key_type(n: dict) -> str:
    if n.get("objectId"):
        return "objectId"
    if n.get("id"):
        return "id"
    return "fallback"


def cents(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def fetch_window_raw_and_deduped(
    days: int,
    chunk_days: int,
    cp: str | None,
    tz,
) -> tuple[list[dict], int, Counter[str], int]:
    """Returns (deduped_cartel_server_lines, raw_matching_lines, key_types, dupes_dropped)."""
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)
    seen: set[str] = set()
    deduped: list[dict] = []
    raw_count = 0
    key_types: Counter[str] = Counter()
    dupes = 0
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days):
        where = {
            "SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
            "Product": {"have": {"Name": {"matchesRegex": _cb.SERVER_REGEX}}},
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
            pr = n.get("Product") or {}
            nm = str(pr.get("Name") or "")
            bd = pr.get("Brand") if isinstance(pr.get("Brand"), dict) else {}
            bn = str((bd or {}).get("Name") or "")
            if not cartel_pack_line_kept_after_fetch(nm, bn, pack_re=_cb.PACK_RE):
                continue
            raw_count += 1
            k = order_item_key(n)
            if k in seen:
                dupes += 1
                continue
            seen.add(k)
            deduped.append(n)
            key_types[item_key_type(n)] += 1
    return deduped, raw_count, key_types, dupes


def probe_quantity_fields(cp: str | None) -> None:
    candidates = [
        "Quantity",
        "Qty",
        "SoldQuantity",
        "Units",
        "UnitQuantity",
        "Count",
        "LineQuantity",
    ]
    fields = " ".join(candidates)
    q = f"""
query {{
  findOrderItems(first: 3) {{
    edges {{
      node {{
        id
        objectId
        SoldAt
        GrossPrice
        {fields}
      }}
    }}
  }}
}}
"""
    try:
        r = graphql_request(q, variables={}, credentials_path=cp)
    except Exception as e:
        print(f"Quantity probe HTTP/error: {e}")
        return
    errs = r.get("errors")
    if errs:
        print("Quantity probe GraphQL errors (field names not on OrderItems):")
        for e in errs[:8]:
            print(" ", e.get("message", e))
    else:
        print("Quantity probe: all candidate fields accepted (unexpected). Sample:", r.get("data"))


def main() -> None:
    _load_config()
    tz = _store_tz()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: missing credentials")
        sys.exit(1)

    print("=== A) Schema probe: line quantity fields on OrderItems ===", flush=True)
    probe_quantity_fields(cp)

    units_buy = 125
    print()
    print("=== B) Cartel server-regex window: raw vs deduped lines ===", flush=True)
    for days in (28, 90, 183):
        deduped, raw, kt, ddup = fetch_window_raw_and_deduped(days, 14, cp, tz)
        seven = [
            n
            for n in deduped
            if is_cartel_7pk_product_name(
                str((n.get("Product") or {}).get("Name") or ""),
                brand_name=order_item_brand_name(n),
                pack_re=_cb.PACK_RE,
            )
        ]
        seven_raw_estimate = int(round(raw * (len(seven) / len(deduped)))) if deduped else 0
        gross = sum(cents(n.get("GrossPrice")) for n in seven)
        per_d = len(seven) / float(days)
        proj = units_buy / per_d if per_d > 0 else 0
        print(f"  {days}d: deduped_cartel_lines={len(deduped)} raw_cartel_lines={raw} dupes_dropped={ddup}")
        print(f"       key_types: {dict(kt)}")
        print(
            f"       7pk subset: lines={len(seven)} (~{per_d:.3f}/day) "
            f"gross_sum=${gross/100:.2f} avg_line=${(gross/100/len(seven)) if seven else 0:.2f}"
        )
        print(f"       125 units @ {days}d velocity -> {proj:.1f} days ({proj/7:.1f} wk)")
        if deduped and seven_raw_estimate and raw != len(deduped):
            pr = units_buy / (seven_raw_estimate / float(days))
            print(f"       (if 7pk share same as deduped: raw_7pk~{seven_raw_estimate} -> {pr:.1f} days)")

    print()
    print("=== C) Top 7pk product names (183d deduped) ===", flush=True)
    ded183, _, _, _ = fetch_window_raw_and_deduped(183, 14, cp, tz)
    seven183 = [
        n
        for n in ded183
        if is_cartel_7pk_product_name(
            str((n.get("Product") or {}).get("Name") or ""),
            brand_name=order_item_brand_name(n),
            pack_re=_cb.PACK_RE,
        )
    ]
    by_name: dict[str, int] = defaultdict(int)
    for n in seven183:
        by_name[str((n.get("Product") or {}).get("Name") or "")] += 1
    for name, c in sorted(by_name.items(), key=lambda x: -x[1])[:20]:
        print(f"  {c:4d}  {name[:75]}")

    total_top = sum(by_name.values())
    print(f"  (top-20 sum {sum(sorted(by_name.values(), reverse=True)[:20])} of {total_top} lines)")

    print()
    print("=== D) Check: fallback-key collision risk (183d, 7pk only) ===", flush=True)
    fallbacks: list[str] = []
    for n in seven183:
        if item_key_type(n) == "fallback":
            fallbacks.append(order_item_key(n))
    fb_dup = len(fallbacks) - len(set(fallbacks))
    print(f"  7pk lines using fallback key: {len(fallbacks)}  duplicate fallback keys: {fb_dup}")

    print()
    print("=== E) Recommended projection band ===", flush=True)
    d28, _, _, _ = fetch_window_raw_and_deduped(28, 14, cp, tz)
    s28 = [
        n
        for n in d28
        if is_cartel_7pk_product_name(
            str((n.get("Product") or {}).get("Name") or ""),
            brand_name=order_item_brand_name(n),
            pack_re=_cb.PACK_RE,
        )
    ]
    d90, _, _, _ = fetch_window_raw_and_deduped(90, 14, cp, tz)
    s90 = [
        n
        for n in d90
        if is_cartel_7pk_product_name(
            str((n.get("Product") or {}).get("Name") or ""),
            brand_name=order_item_brand_name(n),
            pack_re=_cb.PACK_RE,
        )
    ]
    v28 = len(s28) / 28.0
    v90 = len(s90) / 90.0
    v183 = len(seven183) / 183.0
    if v28 > 0 and v90 > 0 and v183 > 0:
        slow = units_buy / v28
        mid = units_buy / v183
        fast = units_buy / v90
        print(f"  125 / 28d rate ({v28:.3f}/d): {slow:.1f} d")
        print(f"  125 / 90d rate ({v90:.3f}/d): {fast:.1f} d")
        print(f"  125 / 183d rate ({v183:.3f}/d): {mid:.1f} d")
        print("  Use 90-183d for smoother trend; 28d if you want recent-only (may be noisy).")


if __name__ == "__main__":
    main()
