"""One-off audit: chart titles + biggest-allocation table vs CSV. Remove after use."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.projection_dashboard_sheet_dynamic import build_dashboard_data_formula_grid  # noqa: E402
from lib.projection_exec_kpis import compute_kpis, kpi_ac_column_values  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402

CSV = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"
ERR = re.compile(r"^#(REF|ERROR|N/A|VALUE|DIV/0|NAME|NUM|NULL|SPILL)!", re.I)


def fnum(x):
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def main() -> int:
    with CSV.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        headers = list(r.fieldnames or [])
        rows = list(r)
    kpis = compute_kpis(rows, meaningful_usd=25.0, high_dollar_usd=500.0)
    kpi_ac = kpi_ac_column_values(kpis)
    _, meta = build_dashboard_data_formula_grid(
        headers=headers,
        rows=rows,
        table_top_n=20,
        chart_top_n=15,
        meaningful_usd=25.0,
        high_dollar_usd=500.0,
        scatter_max_months=36.0,
        scatter_max_days=120.0,
        scatter_cap_rows=80,
        kpi_ac_values=kpi_ac,
    )

    top = sorted(rows, key=lambda r: fnum(r.get("allocated_cog_usd")) or 0, reverse=True)[0]
    exp_brand = (top.get("brand") or "").strip()
    exp_cat = (top.get("category") or "").strip()
    exp_alloc = fnum(top.get("allocated_cog_usd")) or 0

    svc = sheets_service(None)
    sid = DEFAULT_SPREADSHEET_ID

    meta2 = (
        svc.spreadsheets()
        .get(
            spreadsheetId=sid,
            fields="sheets(properties(title),charts(chartId,spec(title)))",
        )
        .execute()
    )
    for sh in meta2.get("sheets", []):
        if sh.get("properties", {}).get("title") != "dashboard":
            continue
        charts = sh.get("charts") or []
        print("Embedded charts on dashboard:", len(charts))
        for c in charts:
            t = (c.get("spec") or {}).get("title") or ""
            print(" ", str(t))

    ar0 = meta["alloc_data_start"] + 1
    fr0 = meta["fast_recovery_data_start"] + 1
    pack = (
        svc.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=sid,
            ranges=[
                f"'dashboard_data'!A{ar0}:H{ar0 + 4}",
                f"'dashboard_data'!A{fr0}:H{fr0 + 4}",
                "'dashboard'!B24:E28",
                "'dashboard'!B38:E42",
                "'dashboard'!A4:B14",
                "'dashboard'!A80:C88",
            ],
            majorDimension="ROWS",
        )
        .execute()
    )
    names = (
        "dashboard_data_ALLOC_top_rows",
        "dashboard_data_FAST rows",
        "biggest_alloc_sample",
        "fast_recovery_sample",
        "kpi_block_A_B",
        "ledger_sample",
    )
    vrs = pack.get("valueRanges", [])
    for name, vr in zip(names, vrs):
        vals = vr.get("values", [])
        bad = any(
            any(ERR.match(str(c)) for c in row if c is not None)
            for row in vals
        )
        print(f"\n{name} (formula errors in range: {bad}):", vals[:6])

    print("\nCSV expected top allocation (brand, category, $):", exp_brand, exp_cat, exp_alloc)
    b24 = vrs[2].get("values", []) if len(vrs) > 2 else []
    if b24 and b24[0]:
        db_brand = str(b24[0][0] or "").strip()
        db_cat = str(b24[0][1] or "").strip() if len(b24[0]) > 1 else ""
        db_usd = fnum(b24[0][2]) if len(b24[0]) > 2 else None
        ok = db_brand == exp_brand and db_cat == exp_cat and db_usd is not None and abs(db_usd - exp_alloc) < 0.05
        print("Biggest row matches CSV:", ok, "| sheet:", db_brand, db_cat, db_usd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
