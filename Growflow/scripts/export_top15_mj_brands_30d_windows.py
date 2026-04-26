"""
Pull **MJ-format** order lines once over a trailing period (default **365** store-local days),
bucket into consecutive **30-day windows**, and save the **top N brands** per window by **gross sales**
(sum of ``GrossPrice`` / **margin** sum for extension).

Outputs (under ``exports/``, created if missing):
- **JSON** — structured for follow-on evaluation (metrics object per window + ranked rows)
- **CSV** — flat rows: ``window_index,window_start,window_end,window_label,rank,brand,gross_usd,lines,margin_usd``

MJ filter matches ``scripts/export_brand_suppliers_to_sheet.py`` / rank script (format pool + flower/concentrate substrings).

Usage:
  PYTHONPATH=. python scripts/export_top15_mj_brands_30d_windows.py
  PYTHONPATH=. python scripts/export_top15_mj_brands_30d_windows.py --total-days 365 --window-days 30 --top 15
  PYTHONPATH=. python scripts/export_top15_mj_brands_30d_windows.py --evaluation-filters
  # Granular: --exclude-prepackaged-flower --exclude-bulk-flower --exclude-non-cannabis-accessories --exclude-brands "710 Empire,Other"
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.allocate_stock_pool import iter_sold_at_date_chunks, order_item_key
from lib.brand_merit_pool import (
    category_matches_format_substrings,
    order_line_in_format_product_pool,
    order_line_product_category_name,
    order_line_product_name,
    parse_iso_utc,
)
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    fetch_paginated,
)

EXTRA_MJ_CATEGORY_SUBSTRINGS: tuple[str, ...] = (
    "flower",
    "concentrate",
    "extract",
    "rosin",
    "hash",
    "prepack",
    "pre-pack",
    "prepackaged",
    "bulk flower",
    "shake",
    "trim",
    "kief",
    "infused",
)

# Category signals that a line is concentrate / vape / edible — not prepack *flower* carve-out.
_CONCENTRATE_VAPE_EDIBLE_IN_CAT: tuple[str, ...] = (
    "concentrate",
    "extract",
    "rosin",
    "hash",
    "vape",
    "cartridge",
    "disposable",
    "edible",
    "preroll",
    "pre-roll",
    "infused",
)

# Substrings on category + product (lowercased) — drop obvious non-cannabis / accessory SKUs.
_NON_CANNABIS_ACCESSORY_SUBSTRINGS: tuple[str, ...] = (
    "accessories",
    "accessory",
    "apparel",
    "clothing",
    "merchandise",
    "gift card",
    "rolling tray",
    "rolling papers",
    "ashtray",
    "grinder",
    "hemp wick",
    "t-shirt",
    "tee shirt",
    "sticker",
    "mug",
    "lighter",
    "scale",
)


def _normalize_brand_key(name: str) -> str:
    return " ".join(name.lower().split())


def _is_prepackaged_flower_line(n: dict[str, Any]) -> bool:
    """True when category/product reads as prepackaged / pre-pack flower (not concentrates)."""
    cat = order_line_product_category_name(n).lower()
    prod = order_line_product_name(n).lower()
    blob = f"{cat} {prod}"
    if any(x in cat for x in _CONCENTRATE_VAPE_EDIBLE_IN_CAT):
        return "prepackaged flower" in blob or "pre-packaged flower" in blob or "prepacked flower" in blob
    if "prepackaged flower" in blob or "pre-packaged flower" in blob or "prepacked flower" in blob:
        return True
    if "bulk flower" in cat:
        return False
    if "flower" in cat and any(p in cat for p in ("prepack", "pre-pack", "prepackaged")):
        return True
    return False


def _is_bulk_flower_line(n: dict[str, Any]) -> bool:
    """True when category/product reads as bulk flower (not concentrates)."""
    cat = order_line_product_category_name(n).lower()
    prod = order_line_product_name(n).lower()
    blob = f"{cat} {prod}"
    if "bulk flower" in blob or "bulk-flower" in blob:
        return True
    if "bulk" in cat and "flower" in cat and not any(x in cat for x in _CONCENTRATE_VAPE_EDIBLE_IN_CAT):
        return True
    return False


def _looks_like_non_cannabis_accessory_line(n: dict[str, Any]) -> bool:
    cat = order_line_product_category_name(n).lower()
    prod = order_line_product_name(n).lower()
    blob = f"{cat} {prod}"
    if re.search(r"\bmerch\b", blob):
        return True
    if re.search(r"\bhat\b", blob):
        return True
    return any(s in blob for s in _NON_CANNABIS_ACCESSORY_SUBSTRINGS)


def _load_org() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = _root / "config" / "config.yaml"
    if cfg.is_file():
        t = cfg.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^\s*org_id:\s*["\']?([^"\'#\n]+)', t, re.MULTILINE)
        if m:
            os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


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
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _is_mj_order_line(n: dict[str, Any]) -> bool:
    if order_line_in_format_product_pool(n):
        return True
    cat = order_line_product_category_name(n)
    return category_matches_format_substrings(cat, EXTRA_MJ_CATEGORY_SUBSTRINGS)


def _line_passes_ranking_filters(
    n: dict[str, Any],
    *,
    exclude_prepackaged_flower: bool,
    exclude_bulk_flower: bool,
    excluded_brand_keys: frozenset[str],
    exclude_non_cannabis_accessories: bool,
) -> bool:
    """MJ line that passes optional evaluation filters (prepack/bulk flower, brand blocklist, accessories)."""
    if not _is_mj_order_line(n):
        return False
    if exclude_prepackaged_flower and _is_prepackaged_flower_line(n):
        return False
    if exclude_bulk_flower and _is_bulk_flower_line(n):
        return False
    if exclude_non_cannabis_accessories and _looks_like_non_cannabis_accessory_line(n):
        return False
    b = _brand_from_line(n)
    if not b:
        return False
    if _normalize_brand_key(b) in excluded_brand_keys:
        return False
    return True


def _brand_from_line(n: dict[str, Any]) -> str | None:
    prod = n.get("Product") or {}
    bo = prod.get("Brand")
    if isinstance(bo, dict) and (bo.get("Name") or "").strip():
        return str(bo["Name"]).strip()
    return None


def _line_margin_cents(n: dict[str, Any]) -> int:
    try:
        gp = int(n.get("GrossPrice") or 0)
    except (TypeError, ValueError):
        return 0
    cog = n.get("COG")
    try:
        cog_i = int(cog) if cog is not None else None
    except (TypeError, ValueError):
        return 0
    if cog_i is None or not (0 <= cog_i <= gp):
        return 0
    return gp - cog_i


def _num_windows(total_days: int, window_days: int) -> int:
    if total_days < 1 or window_days < 1:
        return 0
    return (total_days + window_days - 1) // window_days


def _window_index(sold_local: date, period_start: date, window_days: int, num_windows: int) -> int | None:
    off = (sold_local - period_start).days
    if off < 0 or off >= num_windows * window_days:
        return None
    return min(off // window_days, num_windows - 1)


def _transient_network_error(msg: str) -> bool:
    """HTML error pages / Cloudflare / proxies often surface as non-JSON parse errors."""
    m = msg.lower()
    return any(
        x in m
        for x in (
            "520",
            "502",
            "503",
            "504",
            "timeout",
            "timed out",
            "invalid json",
            "unexpected token",
            "econnreset",
            "econnrefused",
            "fetch failed",
            "socket hang up",
            "cloudflare",
            "bad gateway",
            "gateway timeout",
            "service unavailable",
        )
    )


def _fetch_order_items_chunk_with_retry(
    creds: str | None,
    base: dict[str, Any],
    *,
    max_attempts: int = 6,
) -> list[dict[str, Any]]:
    def _paginate_with_retries(query: str) -> list[dict[str, Any]]:
        last: RuntimeError | None = None
        for attempt in range(max_attempts):
            try:
                return fetch_paginated("findOrderItems", query, base, credentials_path=creds)
            except RuntimeError as e:
                last = e
                msg = str(e).lower()
                if attempt + 1 < max_attempts and _transient_network_error(msg):
                    time.sleep(8.0 * (attempt + 1))
                    continue
                raise
        assert last is not None
        raise last

    try:
        return _paginate_with_retries(ORDER_ITEMS_QUERY)
    except RuntimeError as e:
        if "brand" in str(e).lower():
            return _paginate_with_retries(ORDER_ITEMS_QUERY_NO_BRAND)
        raise


def _fetch_mj_lines_windowed(
    creds: str | None,
    tz: Any,
    *,
    total_days: int,
    window_days: int,
    chunk_days: int,
    exclude_prepackaged_flower: bool = False,
    exclude_bulk_flower: bool = False,
    excluded_brand_keys: frozenset[str] | None = None,
    exclude_non_cannabis_accessories: bool = False,
) -> tuple[
    dict[tuple[int, str], dict[str, int]],
    date,
    date,
    int,
]:
    """
    Returns (aggregates keyed (window_idx, brand) -> {gross_cents, lines, margin_cents}),
    period_start, period_end (store-local inclusive), num_windows.
    """
    end = datetime.now(tz).date()
    start = end - timedelta(days=total_days - 1)
    start_utc = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(
        end.year, end.month, end.day, 23, 59, 59, 999000, tzinfo=tz
    ).astimezone(timezone.utc)

    brand_excl = excluded_brand_keys or frozenset()
    num_windows = _num_windows(total_days, window_days)
    agg: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {"gross_cents": 0, "lines": 0, "margin_cents": 0})
    seen: set[str] = set()

    for fi, ti in iter_sold_at_date_chunks(start_utc, end_utc, max(1, chunk_days)):
        where = {"SoldAt": {"greaterThanOrEqualTo": fi, "lessThanOrEqualTo": ti}}
        base = {"first": PAGE_SIZE, "where": where}
        nodes = _fetch_order_items_chunk_with_retry(creds, base)
        for n in nodes:
            k = order_item_key(n)
            if k in seen:
                continue
            seen.add(k)
            if not _line_passes_ranking_filters(
                n,
                exclude_prepackaged_flower=exclude_prepackaged_flower,
                exclude_bulk_flower=exclude_bulk_flower,
                excluded_brand_keys=brand_excl,
                exclude_non_cannabis_accessories=exclude_non_cannabis_accessories,
            ):
                continue
            b = _brand_from_line(n)
            if not b:
                continue
            sold = parse_iso_utc(n.get("SoldAt"))
            if sold is None:
                continue
            ld = sold.astimezone(tz).date()
            wi = _window_index(ld, start, window_days, num_windows)
            if wi is None:
                continue
            key = (wi, b)
            try:
                gp = int(n.get("GrossPrice") or 0)
            except (TypeError, ValueError):
                gp = 0
            agg[key]["gross_cents"] += gp
            agg[key]["lines"] += 1
            agg[key]["margin_cents"] += _line_margin_cents(n)

    return agg, start, end, num_windows


def _stem_filter_suffix(
    *,
    exclude_prepackaged_flower: bool,
    exclude_bulk_flower: bool,
    excluded_brand_keys: frozenset[str],
    exclude_non_cannabis_accessories: bool,
    evaluation_preset: bool,
) -> str:
    parts: list[str] = []
    if exclude_prepackaged_flower:
        parts.append("no_prepack_flower")
    if exclude_bulk_flower:
        parts.append("no_bulk_flower")
    if exclude_non_cannabis_accessories:
        parts.append("no_accessory_skus")
    for bk in sorted(excluded_brand_keys):
        parts.append("no_" + bk.replace(" ", "_"))
    if not parts:
        return ""
    body = "_".join(parts)
    return f"_curated_{body}" if evaluation_preset else f"_filtered_{body}"


def _window_date_span(period_start: date, window_days: int, wi: int, period_end: date) -> tuple[date, date]:
    ws = period_start + timedelta(days=wi * window_days)
    we = ws + timedelta(days=window_days - 1)
    if we > period_end:
        we = period_end
    return ws, we


def main() -> None:
    ap = argparse.ArgumentParser(description="Top MJ brands per 30d windows → JSON + CSV exports")
    ap.add_argument("--total-days", type=int, default=365, help="Trailing store-local days (default 12 months)")
    ap.add_argument("--window-days", type=int, default=30, help="Days per ranking window")
    ap.add_argument("--top", type=int, default=15, help="How many brands per window")
    ap.add_argument(
        "--chunk-days",
        type=int,
        default=14,
        help="findOrderItems SoldAt chunk size (smaller = gentler on API; default 14)",
    )
    ap.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: Growflow/exports)",
    )
    ap.add_argument(
        "--evaluation-filters",
        action="store_true",
        help="Preset: exclude prepackaged + bulk flower, exclude 710 Empire, strip accessory/non-cannabis SKU hints",
    )
    ap.add_argument(
        "--exclude-prepackaged-flower",
        action="store_true",
        help="Drop lines that read as prepack / pre-packaged flower (not concentrates)",
    )
    ap.add_argument(
        "--exclude-bulk-flower",
        action="store_true",
        help="Drop lines that read as bulk flower (category/product: bulk flower, bulk-flower, or bulk+flower in category)",
    )
    ap.add_argument(
        "--exclude-non-cannabis-accessories",
        action="store_true",
        help="Drop lines whose category/product matches accessory / merch / gift card hints",
    )
    ap.add_argument(
        "--exclude-brands",
        default="",
        help="Comma-separated brand names to exclude (case-insensitive, normalized spaces)",
    )
    args = ap.parse_args()

    _load_org()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("ERROR: Growflow credentials not found.", file=sys.stderr)
        sys.exit(1)

    total_days = max(1, args.total_days)
    window_days = max(1, args.window_days)
    top_k = max(1, args.top)
    tz = _store_tz()
    n_win = _num_windows(total_days, window_days)

    ex_pf = bool(args.exclude_prepackaged_flower)
    ex_bf = bool(args.exclude_bulk_flower)
    ex_acc = bool(args.exclude_non_cannabis_accessories)
    brand_tokens = [x.strip() for x in (args.exclude_brands or "").split(",") if x.strip()]
    if args.evaluation_filters:
        ex_pf = True
        ex_bf = True
        ex_acc = True
        if not any(_normalize_brand_key(b) == "710 empire" for b in brand_tokens):
            brand_tokens.append("710 Empire")
    excluded_brand_keys = frozenset(_normalize_brand_key(b) for b in brand_tokens)

    print(
        f"Fetching MJ lines: {total_days}d back, {n_win} x ~{window_days}d windows, top {top_k} by gross, TZ={tz}",
        flush=True,
    )
    if ex_pf or ex_bf or ex_acc or excluded_brand_keys:
        print(
            f"  Filters: prepack_flower_out={ex_pf} bulk_flower_out={ex_bf} accessory_hint_out={ex_acc} excluded_brands={sorted(excluded_brand_keys)}",
            flush=True,
        )

    agg, period_start, period_end, num_windows = _fetch_mj_lines_windowed(
        cp,
        tz,
        total_days=total_days,
        window_days=window_days,
        chunk_days=max(1, args.chunk_days),
        exclude_prepackaged_flower=ex_pf,
        exclude_bulk_flower=ex_bf,
        excluded_brand_keys=excluded_brand_keys,
        exclude_non_cannabis_accessories=ex_acc,
    )

    # bucket per window list of (brand, gross, lines, margin)
    per_w: dict[int, list[tuple[str, int, int, int]]] = defaultdict(list)
    for (wi, b), m in agg.items():
        per_w[wi].append((b, m["gross_cents"], m["lines"], m["margin_cents"]))

    windows_out: list[dict[str, Any]] = []
    csv_rows: list[list[Any]] = []

    for wi in sorted(per_w.keys()):
        ws, we = _window_date_span(period_start, window_days, wi, period_end)
        label = f"{ws.isoformat()}..{we.isoformat()}"
        ranked = sorted(per_w[wi], key=lambda x: (-x[1], -x[2], x[0].lower()))[:top_k]
        block: dict[str, Any] = {
            "window_index": wi,
            "window_start": ws.isoformat(),
            "window_end": we.isoformat(),
            "window_label": label,
            "brand_count_in_window": len(per_w[wi]),
            "top_brands": [],
        }
        for rank, (b, gc, ln, mc) in enumerate(ranked, start=1):
            row_obj = {
                "rank": rank,
                "brand": b,
                "gross_usd": round(gc / 100.0, 2),
                "gross_cents": gc,
                "lines": ln,
                "margin_usd": round(mc / 100.0, 2),
                "margin_cents": mc,
            }
            block["top_brands"].append(row_obj)
            csv_rows.append(
                [
                    wi,
                    ws.isoformat(),
                    we.isoformat(),
                    label,
                    rank,
                    b,
                    round(gc / 100.0, 2),
                    ln,
                    round(mc / 100.0, 2),
                ]
            )
        windows_out.append(block)

    out_dir = Path(args.out_dir) if args.out_dir else (_root / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz).strftime("%Y%m%d_%H%M")
    sfx = _stem_filter_suffix(
        exclude_prepackaged_flower=ex_pf,
        exclude_bulk_flower=ex_bf,
        excluded_brand_keys=excluded_brand_keys,
        exclude_non_cannabis_accessories=ex_acc,
        evaluation_preset=bool(args.evaluation_filters),
    )
    base = out_dir / f"top{top_k}_mj_brands_{window_days}d_x{num_windows}_windows_{stamp}{sfx}"
    org = (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip()

    payload = {
        "generated_at_store_local": datetime.now(tz).isoformat(),
        "growflow_org": org,
        "period_store_local_start": period_start.isoformat(),
        "period_store_local_end": period_end.isoformat(),
        "total_days": total_days,
        "window_days": window_days,
        "num_windows": num_windows,
        "top_k": top_k,
        "rank_primary": "gross_usd_desc_then_lines_desc_then_brand_az",
        "timezone": str(tz),
        "filters": {
            "evaluation_preset": bool(args.evaluation_filters),
            "exclude_prepackaged_flower": ex_pf,
            "exclude_bulk_flower": ex_bf,
            "exclude_non_cannabis_accessories": ex_acc,
            "excluded_brands_normalized": sorted(excluded_brand_keys),
            "non_cannabis_substrings_documented": list(_NON_CANNABIS_ACCESSORY_SUBSTRINGS),
        },
        "windows": windows_out,
    }

    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(
            [
                "window_index",
                "window_start",
                "window_end",
                "window_label",
                "rank",
                "brand",
                "gross_usd",
                "lines",
                "margin_usd",
            ]
        )
        w.writerows(csv_rows)

    print(f"Wrote {json_path}", flush=True)
    print(f"Wrote {csv_path}", flush=True)


if __name__ == "__main__":
    main()
