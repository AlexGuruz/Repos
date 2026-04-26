"""Average gross sales by weekday over trailing N local-calendar days (findOrderItems / SoldAt)."""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lib.brand_merit_pool import cents_field, parse_iso_utc
from lib.growflow_graphql import resolve_graphql_url
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


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
            print(f"WARNING: invalid timezone {name!r}, using system local", flush=True)
    now = datetime.now().astimezone()
    return now.tzinfo if now.tzinfo is not None else timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _local_day_bounds_utc(d: date, tz) -> tuple[str, str]:
    start_local = datetime.combine(d, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1) - timedelta(milliseconds=1)

    def fmt_utc(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return fmt_utc(start_local), fmt_utc(end_local)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    # ~3 months: 90 local calendar days inclusive of today (override via GROWFLOW_WEEKDAY_WINDOW_DAYS).
    days_inclusive = int((os.environ.get("GROWFLOW_WEEKDAY_WINDOW_DAYS") or "90").strip() or "90")

    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _retail_org(repo_root)
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org
            print(f"Retail org (from config): {org}", flush=True)

    cp = _credentials_path()
    tz = _sales_tz(repo_root)
    end_local = datetime.now(tz).date()
    start_local = end_local - timedelta(days=days_inclusive - 1)

    print(f"Window: {start_local} .. {end_local} ({days_inclusive} local days inclusive)", flush=True)
    print(f"Timezone: {getattr(tz, 'key', None) or tz}", flush=True)
    print(f"GraphQL: {resolve_graphql_url()}", flush=True)
    if cp:
        print(f"Credentials: {cp}", flush=True)
    else:
        print("Credentials: GROWFLOW_ACCESS_TOKEN", flush=True)

    daily_gross: dict[date, int] = defaultdict(int)
    chunk_days = 14
    d = start_local
    while d <= end_local:
        chunk_end = min(d + timedelta(days=chunk_days - 1), end_local)
        from_iso, _ = _local_day_bounds_utc(d, tz)
        _, to_iso = _local_day_bounds_utc(chunk_end, tz)
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        variables = {"first": PAGE_SIZE, "where": where}
        try:
            nodes = fetch_paginated(
                "findOrderItems",
                ORDER_ITEMS_QUERY,
                variables,
                credentials_path=cp,
            )
        except RuntimeError as e:
            if "Brand" in str(e):
                nodes = fetch_paginated(
                    "findOrderItems",
                    ORDER_ITEMS_QUERY_NO_BRAND,
                    variables,
                    credentials_path=cp,
                )
            else:
                print(f"ERROR: {e}", file=sys.stderr)
                sys.exit(1)
        for n in nodes:
            sold = parse_iso_utc(n.get("SoldAt"))
            if sold is None:
                continue
            ld = sold.astimezone(tz).date()
            if ld < start_local or ld > end_local:
                continue
            daily_gross[ld] += cents_field(n.get("GrossPrice"))
        print(f"  SoldAt chunk {d} .. {chunk_end}: {len(nodes)} line(s)", flush=True)
        d = chunk_end + timedelta(days=1)

    wk_count = [0] * 7
    wk_total_cents = [0] * 7
    cur = start_local
    while cur <= end_local:
        wd = cur.weekday()
        wk_count[wd] += 1
        wk_total_cents[wd] += daily_gross.get(cur, 0)
        cur += timedelta(days=1)

    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    print()
    print("Average gross sales by weekday (USD). Days with no lines count as $0.")
    print("-" * 56)
    for i in range(7):
        c = wk_count[i]
        avg = (wk_total_cents[i] / c / 100.0) if c else 0.0
        print(f"  {names[i]:12}  n={c:3} days   avg gross: ${avg:,.2f}")
    grand = sum(daily_gross.values()) / 100.0
    print("-" * 56)
    print(f"  Total window gross: ${grand:,.2f}")


if __name__ == "__main__":
    main()
