"""
Write $18k projection dashboard to Google Sheets (Stashbox service account).

Tabs:
  Summary          — pool, window, metric definitions
  ByBrand          — allocation roll-up + COG recovery + on-hand sell-through
  ByBrandCategory  — layer-2 detail + allocated-unit sell time + on-hand cover
  Rankings         — payback, gross profit, capital efficiency

Inputs:
  data/projection_by_category_brand.md
  data/projection_by_category_brand_layer2_recovery.csv

Optional: --with-packages fetches Growflow packages for on-hand units by brand×format bucket.

Usage:
  PYTHONPATH=. python scripts/projection_dashboard_to_sheet.py
  PYTHONPATH=. python scripts/projection_dashboard_to_sheet.py --with-packages

Share the spreadsheet with the service account client_email (Editor).
Default spreadsheet: 17sqC9JOMMLEWZhd5S_t9FUkZJpKYSqtblBeKs8WCz7U
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.brand_merit_pool import (  # noqa: E402
    package_brand,
    package_format_bucket,
    package_product_category_name,
    package_product_name,
)
from lib.growflow_queries import (  # noqa: E402
    PACKAGES_TABLE_QUERY_WITH_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)

DEFAULT_SPREADSHEET_ID = "17sqC9JOMMLEWZhd5S_t9FUkZJpKYSqtblBeKs8WCz7U"
DEFAULT_MD = REPO / "data" / "projection_by_category_brand.md"
DEFAULT_LAYER2 = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"


def _stashbox_sa_path(cli: str | None) -> str:
    path = cli
    if not path:
        path = os.environ.get("STASHBOX_SERVICE_ACCOUNT", "").strip() or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", ""
        ).strip()
    if not path:
        try:
            from lib.config_loader import get_google_service_account_path

            p = get_google_service_account_path()
            path = str(p) if p else ""
        except Exception:
            path = ""
    if not path and Path("E:/secrets/gcp/stashbox.json").exists():
        path = "E:/secrets/gcp/stashbox.json"
    if not path or not Path(path).exists():
        raise FileNotFoundError(
            "Stashbox / service account JSON not found. Set --sheets-service-account, "
            "STASHBOX_SERVICE_ACCOUNT, GOOGLE_APPLICATION_CREDENTIALS, or E:/secrets/gcp/stashbox.json"
        )
    return path


def _growflow_creds(cli: str | None) -> str | None:
    if cli:
        return cli
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def get_sheets_service(service_account_path: str | None) -> Any:
    path = _stashbox_sa_path(service_account_path)
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def ensure_sheet(service: Any, spreadsheet_id: str, title: str) -> None:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"
    ).execute()
    for s in meta.get("sheets") or []:
        props = s.get("properties") or {}
        if (props.get("title") or "").strip() == title:
            return
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()


def clear_sheet(service: Any, spreadsheet_id: str, sheet_title: str) -> None:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"
    ).execute()
    for s in meta.get("sheets") or []:
        props = s.get("properties") or {}
        if (props.get("title") or "").strip() == sheet_title:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!A:ZZ",
                body={},
            ).execute()
            return


def write_values(
    service: Any,
    spreadsheet_id: str,
    sheet_title: str,
    values: list[list[Any]],
) -> None:
    if not values:
        values = [["(empty)"]]
    ensure_sheet(service, spreadsheet_id, sheet_title)
    clear_sheet(service, spreadsheet_id, sheet_title)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def parse_md_summary(md_path: Path) -> list[list[str]]:
    if not md_path.is_file():
        return [["Summary file not found", str(md_path)]]
    text = md_path.read_text(encoding="utf-8", errors="replace")
    lines: list[list[str]] = [["Projection — source summary (markdown)"], [""]]
    for raw in text.splitlines()[:35]:
        if raw.startswith("#"):
            continue
        if any(
            x in raw
            for x in (
                "**Generated:**",
                "**Pool:**",
                "**Sales window:**",
                "**Unique order lines",
                "**Layer 2:**",
                "**Brands excluded",
            )
        ):
            t = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw).lstrip("- ").strip()
            if t:
                lines.append([t])
    lines.extend(
        [
            [""],
            [
                "COG return time = months to recover allocated pool $ at trailing velocity "
                "(layer-2 model)."
            ],
            [
                "Months sell-through allocated units = units_from_allocation / avg_units_per_month "
                "(matches COG return time in this model)."
            ],
            [
                "On-hand sell-through (mo) = package CurrentQty / avg_units_per_month for that "
                "brand×category when --with-packages is used."
            ],
        ]
    )
    return lines


def load_layer2_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(x: str | None) -> float | None:
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _i(x: str | None) -> int | None:
    v = _f(x)
    return int(v) if v is not None else None


def fetch_on_hand_by_brand_category(
    creds: str | None,
    days_back: int,
    chunk_days: int,
) -> dict[tuple[str, str], int]:
    now = datetime.now(timezone.utc)
    chunk_start = now
    by_id: dict[str, dict] = {}
    chunk_num = 0
    sku_map: dict[str, str] = {}
    while chunk_num * chunk_days < days_back:
        chunk_end = chunk_start - timedelta(days=chunk_days)
        from_pkg = chunk_end.strftime("%Y-%m-%dT00:00:00.000Z")
        to_pkg = chunk_start.strftime("%Y-%m-%dT23:59:59.999Z")
        where_pkg = date_range_to_where("createdAt", from_pkg, to_pkg)
        chunk = fetch_paginated(
            "findPackages",
            PACKAGES_TABLE_QUERY_WITH_BRAND,
            {"first": PAGE_SIZE, "where": where_pkg},
            credentials_path=creds,
        )
        for n in chunk:
            pid = str(n.get("objectId") or n.get("id") or "")
            if pid and pid not in by_id:
                by_id[pid] = n
        chunk_start = chunk_end
        chunk_num += 1

    out: dict[tuple[str, str], int] = defaultdict(int)
    for n in by_id.values():
        try:
            qty = int(float(n.get("CurrentQty") or 0))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        b = package_brand(n, sku_map)
        buck = package_format_bucket(
            package_product_category_name(n),
            package_product_name(n),
        )
        if buck == "Other":
            continue
        out[(b, buck)] += qty
    return out


def aggregate_brand_rows(
    rows: list[dict[str, str]],
    on_hand: dict[tuple[str, str], int],
) -> list[list[Any]]:
    by_brand: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_brand[r["brand"]].append(r)

    header = [
        "Brand",
        "Allocated COG $",
        "Trailing units (window)",
        "Avg months recover COG (alloc-weighted)",
        "Avg months sell-through allocated units (alloc-weighted)",
        "On-hand units (packages)",
        "Est mo sell-through on-hand (brand approx)",
        "Sum proj gross profit $",
        "Avg capital efficiency (alloc-weighted)",
    ]
    out = [header]
    for brand in sorted(
        by_brand.keys(),
        key=lambda b: (-sum(_f(x["allocated_cog_usd"]) or 0 for x in by_brand[b]), b.lower()),
    ):
        rs = by_brand[brand]
        alloc = sum(_f(r["allocated_cog_usd"]) or 0 for r in rs)
        tunits = sum(_i(r["trailing_units_sold"]) or 0 for r in rs)
        gp_sum = sum(_f(r["projected_gross_profit_usd"]) or 0 for r in rs)
        w_mo = w_sell = w_eff = 0.0
        denom = 0.0
        oh_total = 0
        for r in rs:
            a = _f(r["allocated_cog_usd"]) or 0
            mo = _f(r["months_to_recover_cog"])
            aum = _f(r["avg_units_per_month"])
            ufa = _f(r["units_from_allocation"])
            eff = _f(r["allocation_efficiency"])
            if a > 0:
                denom += a
                if mo is not None:
                    w_mo += mo * a
                if ufa is not None and aum is not None and aum > 0:
                    w_sell += (ufa / aum) * a
                if eff is not None:
                    w_eff += eff * a
            oh_total += on_hand.get((brand, r["category"]), 0)

        avg_mo = round(w_mo / denom, 4) if denom else ""
        avg_sell = round(w_sell / denom, 4) if denom else ""
        avg_eff = round(w_eff / denom, 4) if denom else ""

        aums_stock = [
            _f(r["avg_units_per_month"])
            for r in rs
            if on_hand.get((brand, r["category"]), 0) > 0 and (_f(r["avg_units_per_month"]) or 0) > 0
        ]
        mo_oh = ""
        if oh_total > 0 and aums_stock:
            avg_vel = sum(aums_stock) / len(aums_stock)
            mo_oh = round(oh_total / avg_vel, 4)

        out.append(
            [
                brand,
                round(alloc, 2),
                tunits,
                avg_mo,
                avg_sell,
                oh_total,
                mo_oh,
                round(gp_sum, 2),
                avg_eff,
            ]
        )
    return out


def detail_rows(
    rows: list[dict[str, str]],
    on_hand: dict[tuple[str, str], int],
) -> list[list[Any]]:
    header = [
        "Brand",
        "Category",
        "Allocated COG $",
        "Trailing units sold",
        "Avg units / month",
        "Avg COG / unit",
        "Avg retail / unit",
        "Units from allocation",
        "Months recover allocated COG",
        "Months sell-through allocated units",
        "Turns / year",
        "Recovery bucket",
        "Proj revenue (alloc) $",
        "Proj gross profit $",
        "Capital efficiency",
        "On-hand units (packages)",
        "Est months sell-through on-hand",
    ]
    out = [header]
    for r in sorted(rows, key=lambda x: -(_f(x["allocated_cog_usd"]) or 0)):
        aum = _f(r["avg_units_per_month"])
        ufa = _f(r["units_from_allocation"])
        mo = _f(r["months_to_recover_cog"])
        sell_mo = (ufa / aum) if ufa is not None and aum is not None and aum > 0 else None
        key = (r["brand"], r["category"])
        oh = on_hand.get(key, 0)
        mo_oh = (oh / aum) if oh > 0 and aum is not None and aum > 0 else None
        out.append(
            [
                r["brand"],
                r["category"],
                _f(r["allocated_cog_usd"]),
                _i(r["trailing_units_sold"]),
                aum,
                _f(r["avg_cog_per_unit"]),
                _f(r["avg_retail_per_unit"]),
                ufa,
                mo,
                round(sell_mo, 6) if sell_mo is not None else "",
                _f(r["turns_per_year"]),
                r.get("recovery_bucket") or "",
                _f(r["projected_revenue_from_allocated_units_usd"]),
                _f(r["projected_gross_profit_usd"]),
                _f(r["allocation_efficiency"]),
                oh if oh else "",
                round(mo_oh, 4) if mo_oh is not None else "",
            ]
        )
    return out


def _ranking_payback(rows: list[dict[str, str]], n: int) -> list[list[Any]]:
    def k(r: dict[str, str]) -> tuple:
        v = _f(r["months_to_recover_cog"])
        if v is None:
            return (1, 1e9, r["brand"])
        return (0, v, r["brand"])

    ranked = sorted(rows, key=k)[:n]
    out: list[list[Any]] = [
        [f"Fastest COG payback (top {n})"],
        [""],
        ["Brand", "Category", "Months recover COG", "Allocated $", "Proj GP $"],
    ]
    for r in ranked:
        out.append(
            [
                r["brand"],
                r["category"],
                _f(r["months_to_recover_cog"]),
                _f(r["allocated_cog_usd"]),
                _f(r["projected_gross_profit_usd"]),
            ]
        )
    return out


def _ranking_gp(rows: list[dict[str, str]], n: int) -> list[list[Any]]:
    ranked = sorted(rows, key=lambda r: -(_f(r["projected_gross_profit_usd"]) or -1))[:n]
    out: list[list[Any]] = [
        [f"Highest projected gross profit (top {n})"],
        [""],
        ["Brand", "Category", "Proj GP $", "Allocated $", "Months recover COG"],
    ]
    for r in ranked:
        out.append(
            [
                r["brand"],
                r["category"],
                _f(r["projected_gross_profit_usd"]),
                _f(r["allocated_cog_usd"]),
                _f(r["months_to_recover_cog"]),
            ]
        )
    return out


def _ranking_eff(rows: list[dict[str, str]], n: int) -> list[list[Any]]:
    ranked = sorted(rows, key=lambda r: -(_f(r["allocation_efficiency"]) or -1))[:n]
    out: list[list[Any]] = [
        [f"Highest capital efficiency (top {n})"],
        [""],
        ["Brand", "Category", "Capital efficiency", "Allocated $", "Months recover COG"],
    ]
    for r in ranked:
        out.append(
            [
                r["brand"],
                r["category"],
                _f(r["allocation_efficiency"]),
                _f(r["allocated_cog_usd"]),
                _f(r["months_to_recover_cog"]),
            ]
        )
    return out


def build_rankings(rows: list[dict[str, str]], top_n: int) -> list[list[Any]]:
    out: list[list[Any]] = []
    out.extend(_ranking_payback(rows, top_n))
    out.append([""])
    out.extend(_ranking_gp(rows, top_n))
    out.append([""])
    out.extend(_ranking_eff(rows, top_n))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Projection dashboard -> Google Sheet (Stashbox SA)")
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--projection-md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--layer2-csv", type=Path, default=DEFAULT_LAYER2)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument("--with-packages", action="store_true")
    ap.add_argument("--packages-days-back", type=int, default=730)
    ap.add_argument("--package-chunk-days", type=int, default=90)
    ap.add_argument("--growflow-credentials", default=None)
    ap.add_argument("--ranking-top", type=int, default=25)
    args = ap.parse_args()

    if not args.layer2_csv.is_file():
        print(f"Layer2 CSV not found: {args.layer2_csv}", file=sys.stderr)
        print("Run: PYTHONPATH=. python scripts/build_projection_by_category_brand.py", file=sys.stderr)
        return 1

    layer_rows = load_layer2_rows(args.layer2_csv)
    on_hand: dict[tuple[str, str], int] = defaultdict(int)
    if args.with_packages:
        creds = _growflow_creds(args.growflow_credentials)
        if creds is None and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
            print("Growflow credentials not found; skipping on-hand fetch.", file=sys.stderr)
        else:
            print("Fetching packages for on-hand units (may take a minute)...", flush=True)
            on_hand = fetch_on_hand_by_brand_category(
                creds, args.packages_days_back, args.package_chunk_days
            )
            print(f"  Unique (brand, category) keys with stock: {len(on_hand)}", flush=True)

    service = get_sheets_service(args.sheets_service_account)
    sid = args.spreadsheet_id

    summary = parse_md_summary(args.projection_md)
    summary.insert(0, [f"Dashboard updated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"])
    summary.insert(1, [f"Layer2 CSV: {args.layer2_csv.name}"])
    summary.insert(2, [""])

    write_values(service, sid, "Summary", summary)
    write_values(service, sid, "ByBrand", aggregate_brand_rows(layer_rows, on_hand))
    write_values(service, sid, "ByBrandCategory", detail_rows(layer_rows, on_hand))
    write_values(service, sid, "Rankings", build_rankings(layer_rows, args.ranking_top))

    print(
        "Wrote tabs: Summary | ByBrand | ByBrandCategory | Rankings",
        flush=True,
    )
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
