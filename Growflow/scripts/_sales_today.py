"""One-off: sum order-item sales for *local* calendar day (SoldAt), converted to UTC for the API.

Timezone: GROWFLOW_SALES_TZ (e.g. America/Chicago), or growflow.sales_timezone in config/config.yaml,
or the system local timezone (last resort UTC).
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _retail_org_from_config(repo_root: Path) -> str | None:
    """Read growflow org_id from config/config.yaml without PyYAML (best-effort)."""
    p = repo_root / "config" / "config.yaml"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    return _yaml_scalar(text, "org_id")


def _sales_timezone_name_from_config(repo_root: Path) -> str | None:
    p = repo_root / "config" / "config.yaml"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    return _yaml_scalar(text, "sales_timezone")


def _resolve_sales_tz(repo_root: Path):
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        name = (_sales_timezone_name_from_config(repo_root) or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            print(f"WARNING: invalid GROWFLOW_SALES_TZ/sales_timezone {name!r}, using system local", flush=True)
    now = datetime.now().astimezone()
    if now.tzinfo is not None:
        return now.tzinfo
    return timezone.utc


def _local_day_utc_iso_range(tz) -> tuple[datetime.date, str, str]:
    """Return (local_date, from_iso_utc, to_iso_utc) inclusive for SoldAt filter."""
    now_local = datetime.now(tz)
    day = now_local.date()
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1) - timedelta(milliseconds=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    def fmt_utc(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return day, fmt_utc(start_utc), fmt_utc(end_utc)


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _cents(x: object) -> int:
    try:
        return int(x) if x is not None else 0
    except (TypeError, ValueError):
        return 0


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _retail_org_from_config(repo_root)
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org
            print(f"Retail org (from config): {org}", flush=True)

    cp = _credentials_path()
    tz = _resolve_sales_tz(repo_root)
    local_day, from_iso, to_iso = _local_day_utc_iso_range(tz)
    where = date_range_to_where("SoldAt", from_iso, to_iso)
    tz_label = getattr(tz, "key", None) or str(tz)
    print(
        f"Sales day (local): {local_day}  timezone: {tz_label}  SoldAt UTC: {from_iso} .. {to_iso}",
        flush=True,
    )
    if cp:
        print(f"Credentials: {cp}", flush=True)
    else:
        print("Credentials: GROWFLOW_ACCESS_TOKEN", flush=True)
    print(f"GraphQL URL: {resolve_graphql_url()}", flush=True)

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

    gross = sum(_cents(n.get("GrossPrice")) for n in nodes)
    net = sum(_cents(n.get("NetPrice")) for n in nodes)
    print(f"Line items: {len(nodes)}")
    print(f"Gross sales (USD): {gross / 100:,.2f}")
    print(f"Net sales (USD):   {net / 100:,.2f}")


if __name__ == "__main__":
    main()
