"""Debug: list distinct Product Brand/Name in a SoldAt window matching loose substrings."""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    p = repo / "config" / "config.yaml"
    text = p.read_text(encoding="utf-8", errors="replace")
    org = _yaml_scalar(text, "org_id")
    tzn = _yaml_scalar(text, "sales_timezone") or "America/Chicago"
    os.environ["GROWFLOW_RETAIL_ORG"] = org or ""
    try:
        tz = ZoneInfo(tzn)
    except ZoneInfoNotFoundError:
        tz = datetime.now().astimezone().tzinfo or timezone.utc
    cp = os.environ.get("GROWFLOW_CREDENTIALS_PATH") or (
        r"E:/secrets/gcp/growflowapi.txt" if Path(r"E:/secrets/gcp/growflowapi.txt").is_file() else None
    )

    end = datetime.now(tz).date()
    start = end - timedelta(days=13)

    def bounds(d):
        s = datetime.combine(d, datetime.min.time(), tzinfo=tz)
        e = s + timedelta(days=1) - timedelta(milliseconds=1)

        def f(dt: datetime) -> str:
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        return f(s), f(e)

    fi, _ = bounds(start)
    _, ti = bounds(end)
    where = date_range_to_where("SoldAt", fi, ti)
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

    needles = ("stix", "xtrax", "sap")
    seen: set[tuple[str, str, str, str]] = set()
    for n in nodes:
        pr = n.get("Product") or {}
        bd = pr.get("Brand")
        bn = bd.get("Name") if isinstance(bd, dict) else ""
        nm = pr.get("Name") or ""
        blob = f"{bn} {nm}".lower()
        if any(x in blob for x in needles):
            seen.add((bn, nm, pr.get("SKU") or "", n.get("SKU") or ""))

    print(f"Window {start}..{end} lines={len(nodes)} distinct hits={len(seen)}")
    for t in sorted(seen):
        print(t)


if __name__ == "__main__":
    main()
