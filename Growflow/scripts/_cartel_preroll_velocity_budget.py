"""One-off: Cartel preroll/pack sales velocity + $ budget units (Growflow findOrderItems)."""
from __future__ import annotations

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
from lib.cartel_7pk_names import WEIGHT_8_4G, cartel_pack_line_kept_after_fetch
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    fetch_paginated,
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
    now = datetime.now().astimezone()
    return now.tzinfo or timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


# Server-side filter: Cartel name patterns + Infused Pre-Roll Bundle + 8.4g (may omit "cartel" in Name).
SERVER_REGEX = (
    r"(?i)(cartel.*(7pk|14pk|preroll|pre-roll|diam|8\.4))"
    r"|(infused.{0,220}(pre[\s-]?roll|preroll).{0,220}bundle.{0,220}(8\.4\s*g|8\.4G))"
    r"|((8\.4\s*g|8\.4G).{0,220}infused.{0,220}(pre[\s-]?roll|preroll).{0,220}bundle)"
)
PACK_RE = re.compile(
    r"(?i)cartel.*(7pk|7[\s-]+pk|preroll|pre[\s-]+roll|diam.*infu|infu.*preroll|pk[\s.]*diam|8\.4\s*g)"
)
EXC_RE = re.compile(r"(?i)disposable|cartridge")


def cents(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def fetch_cartel_pack_lines(days: int, chunk_days: int, cp: str | None, tz) -> list[dict]:
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)
    seen: set[str] = set()
    lines: list[dict] = []
    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, chunk_days):
        where = {
            "SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti},
            "Product": {"have": {"Name": {"matchesRegex": SERVER_REGEX}}},
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
            pr = n.get("Product") or {}
            nm = str(pr.get("Name") or "")
            bd = pr.get("Brand") if isinstance(pr.get("Brand"), dict) else {}
            bn = str((bd or {}).get("Name") or "")
            if not cartel_pack_line_kept_after_fetch(nm, bn, pack_re=PACK_RE):
                continue
            lines.append(n)
    return lines


MULTI_PACK_RE = re.compile(r"(?i)\b(7pk|7[\s-]pk|14pk|14[\s-]pk)\b")

# Your landed cost (purchase planning).
COST_7PK = 12.0
COST_14PK = 21.0
BUDGET_DEFAULT = 1500.0


def pack_buy_bucket(product_name: str) -> str | None:
    """7pk resin vs diamond same unit cost -> '7pk'; 14pk -> '14pk'; else None."""
    u = product_name.upper()
    nm = product_name or ""
    if re.search(r"\b14[\s-]*PK\b", u) or "14PK" in u.replace(" ", ""):
        return "14pk"
    if re.search(r"\b7[\s-]*PK\b", u) or "7PK" in u.replace(" ", ""):
        return "7pk"
    if "cartel" in nm.lower() and WEIGHT_8_4G.search(nm):
        return "7pk"
    return None


def allocate_budget_by_velocity(
    lines: list[dict],
    budget: float,
    *,
    days: int,
) -> None:
    """Split budget across 7pk ($12) and 14pk ($21) by recent sales mix (order lines)."""
    def _is_mp_line(n: dict) -> bool:
        nm = str((n.get("Product") or {}).get("Name") or "")
        if MULTI_PACK_RE.search(nm):
            return True
        return "cartel" in nm.lower() and bool(WEIGHT_8_4G.search(nm))

    mp_lines = [n for n in lines if _is_mp_line(n)]
    n7 = sum(1 for n in mp_lines if pack_buy_bucket(str((n.get("Product") or {}).get("Name") or "")) == "7pk")
    n14 = sum(1 for n in mp_lines if pack_buy_bucket(str((n.get("Product") or {}).get("Name") or "")) == "14pk")
    n_other = len(mp_lines) - n7 - n14
    total_mix = n7 + n14
    print(
        f"[BUY TIERS @ ${COST_7PK:.0f}/7pk ${COST_14PK:.0f}/14pk] DAYS={days} "
        f"7pk_lines={n7} 14pk_lines={n14} other_multi={n_other} (1.2g singles excluded from tiers)"
    )
    if total_mix <= 0:
        print("  No 7pk/14pk lines in window; cannot split by mix.")
        return
    # Proportional dollars by sales mix, then floor units; sweep remainder on cheaper tier.
    d7 = budget * (n7 / total_mix)
    d14 = budget * (n14 / total_mix)
    u7 = int(d7 // COST_7PK)
    u14 = int(d14 // COST_14PK)
    spent = u7 * COST_7PK + u14 * COST_14PK
    rem = budget - spent
    while rem >= COST_7PK:
        u7 += 1
        rem -= COST_7PK
    while rem >= COST_14PK:
        u14 += 1
        rem -= COST_14PK
    spent2 = u7 * COST_7PK + u14 * COST_14PK
    v7 = n7 / float(days)
    v14 = n14 / float(days)
    w7 = u7 / v7 / 7.0 if v7 > 0 else None
    w14 = u14 / v14 / 7.0 if v14 > 0 else None
    print(
        f"  Mix-weighted ~${d7:.0f} on 7pk -> {u7} units (${u7 * COST_7PK:.0f}); "
        f"~${d14:.0f} on 14pk -> {u14} units (${u14 * COST_14PK:.0f}); "
        f"total spend ${spent2:.0f} (remainder ${budget - spent2:.2f})"
    )
    if w7 is not None and w7 > 0:
        print(f"  Weeks cover (7pk only): ~{w7:.1f} wk at {days}d velocity ({v7:.2f}/day)")
    if w14 is not None and w14 > 0:
        print(f"  Weeks cover (14pk only): ~{w14:.1f} wk at {days}d velocity ({v14:.2f}/day)")
    print(
        f"  All-7pk max for ${budget:.0f}: {int(budget // COST_7PK)} units | "
        f"All-14pk max: {int(budget // COST_14PK)} units"
    )


def _report_slice(label: str, lines: list[dict], days: int, budget: float) -> None:
    packs = len(lines)
    gross = sum(cents(n.get("GrossPrice")) for n in lines)
    cog_lines = [n for n in lines if cents(n.get("COG")) > 0]
    cog_sum = sum(cents(n.get("COG")) for n in cog_lines)
    avg_cog_usd = (cog_sum / len(cog_lines) / 100.0) if cog_lines else None
    per_day = packs / float(days)
    print(
        f"{label} DAYS={days} order_lines={packs} gross_usd={gross/100:.2f} "
        f"lines_with_COG={len(cog_lines)} avg_COG_usd={avg_cog_usd} lines_per_day={per_day:.2f}"
    )
    if avg_cog_usd and avg_cog_usd > 0 and per_day > 0:
        max_units_budget = int(budget // avg_cog_usd)
        weeks_cover = max_units_budget / per_day / 7.0
        print(
            f"  Budget ${budget:.0f} @ avg COG ${avg_cog_usd:.2f}/line -> max {max_units_budget} lines "
            f"(~{weeks_cover:.1f} weeks cover at {days}d run rate)"
        )
    by_name: dict[str, int] = defaultdict(int)
    for n in lines:
        by_name[str((n.get("Product") or {}).get("Name") or "")] += 1
    top = sorted(by_name.items(), key=lambda x: -x[1])[:12]
    print(f"  top_products: {top}")


def main() -> None:
    _load_config()
    tz = _store_tz()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: No credentials (GROWFLOW_CREDENTIALS_PATH or growflowapi.txt or GROWFLOW_ACCESS_TOKEN)")
        sys.exit(1)

    budget = BUDGET_DEFAULT

    for days in (14, 28, 56):
        lines = fetch_cartel_pack_lines(days, 14, cp, tz)
        _report_slice("[ALL cartel diam/ros/preroll name match]", lines, days, budget)
        mp = [n for n in lines if MULTI_PACK_RE.search(str((n.get("Product") or {}).get("Name") or ""))]
        _report_slice("[MULTI-PACK only 7PK/14PK in product name]", mp, days, budget)
        allocate_budget_by_velocity(lines, budget, days=days)
        print()


if __name__ == "__main__":
    main()
