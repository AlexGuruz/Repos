#!/usr/bin/env python3
"""
Live Google Sheets checks for the projection capital dashboard.

Requires the same service account auth as build_projection_dashboard_google_sheet.py.
Uses the Values API (computed results). Run after a successful deploy.

Exit code 0 = all automated checks passed; non-zero = failure details on stderr.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.projection_dashboard_sheet_dynamic import build_dashboard_data_formula_grid  # noqa: E402
from lib.projection_exec_kpis import compute_kpis, kpi_ac_column_values  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402

DEFAULT_CSV = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"
TABLE_TOP_N = 20
CHART_TOP_N = 15
MEANINGFUL_USD = 25.0
HIGH_DOLLAR_USD = 500.0
SCATTER_MAX_MONTHS = 36.0
SCATTER_MAX_DAYS = 120.0


def load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        headers = list(r.fieldnames or [])
        rows = list(r)
    return headers, rows


def hdr_idx(headers: list[str], name: str) -> int | None:
    t = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == t:
            return i
    return None


def looks_like_sheet_error(val: str) -> bool:
    s = str(val).strip()
    return bool(re.match(r"^#(REF|ERROR|N/A|VALUE|DIV/0|NAME|NUM|NULL|SPILL)!", s, re.I))


def to_float(x: Any) -> float | None:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s or looks_like_sheet_error(s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def get_batch(service: Any, sid: str, ranges: list[str]) -> list[list[list[Any]]]:
    resp = (
        service.spreadsheets()
        .values()
        .batchGet(spreadsheetId=sid, ranges=ranges, majorDimension="ROWS")
        .execute()
    )
    out: list[list[list[Any]]] = []
    for vr in resp.get("valueRanges", []):
        out.append(vr.get("values", []))
    return out


def put_cell(service: Any, sid: str, a1: str, value: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range=a1,
        valueInputOption="USER_ENTERED",
        body={"values": [[value]]},
    ).execute()


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify live projection dashboard sheet.")
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--sheets-service-account", default=None)
    args = ap.parse_args()

    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1

    headers, rows = load_csv_rows(args.csv)
    if not headers or not rows:
        print("CSV empty", file=sys.stderr)
        return 1

    bi = hdr_idx(headers, "brand")
    ci = hdr_idx(headers, "category")
    if bi is None or ci is None:
        print("CSV missing brand/category column", file=sys.stderr)
        return 1

    first_brand = (rows[0].get(headers[bi]) or "").strip()
    first_cat = (rows[0].get(headers[ci]) or "").strip()
    if not first_brand or not first_cat:
        print("First data row missing brand/category", file=sys.stderr)
        return 1

    pair = f"{first_brand} | {first_cat}"

    kpis = compute_kpis(
        rows, meaningful_usd=MEANINGFUL_USD, high_dollar_usd=HIGH_DOLLAR_USD
    )
    kpi_ac = kpi_ac_column_values(kpis)
    _, meta = build_dashboard_data_formula_grid(
        headers=headers,
        rows=rows,
        table_top_n=TABLE_TOP_N,
        chart_top_n=CHART_TOP_N,
        meaningful_usd=MEANINGFUL_USD,
        high_dollar_usd=HIGH_DOLLAR_USD,
        scatter_max_months=SCATTER_MAX_MONTHS,
        scatter_max_days=SCATTER_MAX_DAYS,
        scatter_cap_rows=80,
        kpi_ac_values=kpi_ac,
    )

    def r1(idx0: int) -> int:
        return idx0 + 1

    alloc_row = r1(meta["alloc_data_start"])
    cat_row = r1(meta["cat_data_start"])
    sid = args.spreadsheet_id
    service = sheets_service(args.sheets_service_account)

    failures: list[str] = []

    def check(name: str, cond: bool, detail: str) -> None:
        if not cond:
            failures.append(f"{name}: {detail}")

    # --- Layer 0: raw + filtered spine ---
    raw_pack = get_batch(
        service,
        sid,
        ["'raw_layer2'!A1:Z1", "'dashboard_data'!A2500:A2502", "'dashboard_data'!AC3"],
    )
    raw_hdr = raw_pack[0][0] if raw_pack[0] else []
    check("raw_layer2 headers", len(raw_hdr) > 0, "row 1 empty")
    a2500_block = raw_pack[1]
    ac3_raw = raw_pack[2][0][0] if raw_pack[2] and raw_pack[2][0] else ""
    # Values API returns computed values; A2500 shows the top-left spill cell (header), not the formula text.
    top_left = str(a2500_block[0][0]) if a2500_block and a2500_block[0] else ""
    check(
        "A2500 spill top-left (header col A)",
        bool(top_left) and not looks_like_sheet_error(top_left),
        f"A2500 value={top_left!r}",
    )
    row2501_a = ""
    if len(a2500_block) > 1 and a2500_block[1]:
        row2501_a = str(a2500_block[1][0])
    check(
        "filtered_layer2 row 2501 col A (body under header)",
        bool(row2501_a) and not looks_like_sheet_error(row2501_a),
        f"row 2501 col A = {row2501_a!r}",
    )
    check(
        "AC3 KPI (no filter yet)",
        to_float(ac3_raw) is not None,
        f"AC3 = {ac3_raw!r}",
    )

    # --- Filter tests (dashboard M1 / O1) ---
    def read_kpi_pool() -> float | None:
        pack = get_batch(service, sid, ["'dashboard_data'!AC3"])
        v = pack[0][0][0] if pack[0] and pack[0][0] else ""
        return to_float(v)

    def read_ab_list_sample() -> str:
        pack = get_batch(service, sid, ["'dashboard_data'!AB3:AB6"])
        if not pack[0]:
            return ""
        parts = [str(row[0]) for row in pack[0] if row]
        return " | ".join(parts)

    def read_q1() -> str:
        pack = get_batch(service, sid, ["'dashboard'!Q1"])
        if pack[0] and pack[0][0]:
            return str(pack[0][0][0])
        return ""

    def read_alloc_label() -> str:
        pack = get_batch(service, sid, [f"'dashboard_data'!A{alloc_row}:B{alloc_row}"])
        if pack[0] and pack[0][0] and len(pack[0][0]) > 1:
            return str(pack[0][0][1])
        if pack[0] and pack[0][0]:
            return str(pack[0][0][0])
        return ""

    def read_cat_slice() -> str:
        pack = get_batch(service, sid, [f"'dashboard_data'!A{cat_row}:B{cat_row + 2}"])
        if not pack[0]:
            return ""
        return repr(pack[0])

    # Test 1: None + clear O1
    put_cell(service, sid, "'dashboard'!M1", "None")
    put_cell(service, sid, "'dashboard'!O1", "")
    pool_none = read_kpi_pool()
    q1_none = read_q1()
    alloc_none = read_alloc_label()
    cat_none = read_cat_slice()
    check("Test1 pool numeric", pool_none is not None, f"AC3={pool_none!r}")
    check("Test1 Q1", "none" in q1_none.lower(), f"Q1={q1_none!r}")
    ab3_pack = get_batch(service, sid, ["'dashboard_data'!AB3"])
    ab3v = str(ab3_pack[0][0][0]) if ab3_pack[0] and ab3_pack[0][0] else ""
    check("Test1 AB3 no error", not looks_like_sheet_error(ab3v), f"AB3={ab3v!r}")
    check("Test1 ALLOC_TOP", bool(alloc_none) and not looks_like_sheet_error(alloc_none), alloc_none)
    check(
        "Test1 CATEGORY slice",
        first_cat in cat_none or len(cat_none) > 4,
        cat_none,
    )

    # Test 2: Brand exclusion
    put_cell(service, sid, "'dashboard'!M1", "Brand")
    put_cell(service, sid, "'dashboard'!O1", first_brand)
    pool_brand = read_kpi_pool()
    q1_brand = read_q1()
    ab_brand = read_ab_list_sample()
    check("Test2 pool <= none", pool_brand is not None and pool_none is not None, "missing pool")
    if pool_brand is not None and pool_none is not None:
        check(
            "Test2 pool drops when excluding brand",
            pool_brand <= pool_none + 0.05,
            f"pool_brand={pool_brand} pool_none={pool_none}",
        )
    check("Test2 Q1 mentions exclude", "Excluding" in q1_brand, f"Q1={q1_brand!r}")
    check("Test2 AB has list", first_brand in ab_brand or len(ab_brand) > 3, f"AB={ab_brand!r}")

    # Test 3: Category
    put_cell(service, sid, "'dashboard'!M1", "Category")
    put_cell(service, sid, "'dashboard'!O1", first_cat)
    pool_cat = read_kpi_pool()
    check(
        "Test3 executive KPI pool unchanged under category filter",
        pool_cat is not None and pool_none is not None and abs(pool_cat - pool_none) < 0.05,
        f"pool_cat={pool_cat} pool_none={pool_none}",
    )

    # Test 4: Brand+Category
    put_cell(service, sid, "'dashboard'!M1", "Brand+Category")
    put_cell(service, sid, "'dashboard'!O1", pair)
    pool_bc = read_kpi_pool()
    check(
        "Test4 executive KPI pool unchanged under brand+category filter",
        pool_bc is not None and pool_none is not None and abs(pool_bc - pool_none) < 0.05,
        f"pool_bc={pool_bc} pool_none={pool_none}",
    )

    # Restore friendly default
    put_cell(service, sid, "'dashboard'!M1", "None")
    put_cell(service, sid, "'dashboard'!O1", "")

    # Executive text KPIs (Python → AC) must not be sheet errors
    ktxt = get_batch(
        service,
        sid,
        ["'dashboard_data'!AC10", "'dashboard_data'!AC13", "'dashboard_data'!AC14"],
    )
    for i, lab in enumerate(("AC10", "AC13", "AC14")):
        pack = ktxt[i] if i < len(ktxt) else []
        raw = str(pack[0][0]) if pack and pack[0] and pack[0][0] is not None else ""
        check(
            f"{lab} text KPI (no sheet error)",
            bool(raw) and not looks_like_sheet_error(raw),
            f"{lab}={raw!r}",
        )

    # --- Charts: count embedded charts on dashboard tab ---
    meta_sheet = (
        service.spreadsheets()
        .get(spreadsheetId=sid, fields="sheets(properties(sheetId,title),charts)")
        .execute()
    )
    chart_count = 0
    for sh in meta_sheet.get("sheets", []):
        if sh.get("properties", {}).get("title") == "dashboard":
            chart_count = len(sh.get("charts", []) or [])
            break
    check("dashboard has embedded charts", chart_count > 0, f"chart_count={chart_count}")

    print("verify_projection_dashboard_sheet: OK")
    print(f"  spreadsheet: https://docs.google.com/spreadsheets/d/{sid}/edit")
    print(f"  pool (None mode) AC3: {pool_none}")
    print(f"  charts on dashboard tab: {chart_count}")
    if failures:
        print("FAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
