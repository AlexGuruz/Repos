"""
Fixed-layout renderer for the ``dashboard`` tab (visual contract vs. screenshots).

- ``dashboard_data`` remains the formula/source layer (unchanged by this module).
- KPI values stay Python → ``dashboard_data`` AC via existing pipeline.
- This module writes **anchored** zones, explicit ``dashboard_data`` INDEX formulas for filtered
  ranking tables, Python-written deployment ledger (with brand subtotals), borders/header fills only,
  no full-sheet black paint, and rebuilds embedded charts from explicit ranges each run.

All public coordinates in ``DASHBOARD_LAYOUT`` are **1-based** (spreadsheet rows/columns as users see them).

**Zone-oriented API:**

- ``refresh_projection_dashboard_sheet`` — targeted value updates (ledger; optional subtitle/narrative); no clear/charts/formatting
- ``rebuild_projection_dashboard_sheet`` (alias ``build_projection_dashboard_sheet``) — full regeneration
- ``clear_dashboard_sheet`` — clear working area + delete embedded charts
- ``apply_dashboard_grid`` — freeze rows 3 (no frozen column; merges span A+ and cannot cross a freeze line)
- ``build_dashboard_value_grid`` — title, subtitle, filters, KPI links, narrative, action, tables, ledger
- ``apply_dashboard_formatting`` — merges, header/banner fills, borders, number formats
- ``dashboard_conditional_formats`` — payback / efficiency heatmaps
- ``build_dashboard_charts`` — seven charts with explicit ``dashboard_data`` source ranges
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# --- Reused semantics (keep aligned with scripts/build_projection_dashboard_google_sheet.py) ---
CHART_TOP_N = 15
TABLE_TOP_N = 20
MEANINGFUL_USD = 25.0
HIGH_DOLLAR_USD = 500.0


def fnum(x: str | None) -> float | None:
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


@dataclass(frozen=True)
class _Zone1:
    """1-based inclusive top-left, height × width."""

    row: int
    col: int
    rows: int
    cols: int

    def r0(self) -> int:
        return self.row - 1

    def c0(self) -> int:
        return self.col - 1

    def r1(self) -> int:
        return self.row - 1 + self.rows

    def c1(self) -> int:
        return self.col - 1 + self.cols


# Visual contract (1-based). Tuned for top alignment, tighter vertical stack, paired table+charts.
DASHBOARD_LAYOUT: dict[str, _Zone1] = {
    "title": _Zone1(1, 1, 1, 11),
    "subtitle": _Zone1(2, 1, 1, 22),
    "filter_strip": _Zone1(1, 12, 1, 6),  # L1:Q1
    "kpi_banner": _Zone1(3, 1, 1, 6),
    "kpi_block": _Zone1(4, 1, 11, 6),
    "pie_chart": _Zone1(4, 7, 11, 8),
    "brand_chart": _Zone1(4, 15, 11, 10),
    "allocation_chart": _Zone1(4, 25, 22, 12),
    "narrative_block": _Zone1(15, 1, 4, 22),
    "action_block": _Zone1(19, 1, 3, 22),
    "largest_alloc_table": _Zone1(22, 1, 13, 8),
    "alloc_vs_profit_chart": _Zone1(22, 10, 13, 18),
    "fastest_recovery_table": _Zone1(36, 1, 11, 8),
    "fastest_recovery_chart": _Zone1(36, 10, 13, 18),
    "highest_profit_table": _Zone1(48, 1, 11, 8),
    "weak_efficiency_table": _Zone1(60, 1, 10, 8),
    "category_perf_table": _Zone1(71, 1, 7, 8),
    "detail_ledger_table": _Zone1(78, 1, 45, 4),
    "recovery_bucket_chart": _Zone1(78, 8, 18, 14),
    "category_recovery_chart": _Zone1(78, 22, 18, 14),
}

DASHBOARD_ROW_COUNT = 135
DASHBOARD_COL_COUNT = 36  # A:AJ (through col 36 = AJ)

# Header / banner fills (no full-sheet background)
HDR = {"red": 0.27, "green": 0.45, "blue": 0.69}
HDR_FG = {"red": 1, "green": 1, "blue": 1}
SUBHDR = {"red": 0.12, "green": 0.16, "blue": 0.22}
BANNER_FG = {"red": 1, "green": 1, "blue": 1}
SECTION_BAR = {"red": 0.22, "green": 0.32, "blue": 0.42}
SECTION_BAR_FG = BANNER_FG

CHART_BG = {"rgbColor": {"red": 0.05, "green": 0.05, "blue": 0.06}}
CHART_TITLE_FG = {"red": 0.95, "green": 0.96, "blue": 0.98}
CHART_SUBTITLE_FG = {"red": 0.72, "green": 0.76, "blue": 0.82}
SERIES_PRIMARY = {"red": 0.39, "green": 0.72, "blue": 1.0}
SERIES_SECONDARY = {"red": 0.86, "green": 0.44, "blue": 0.18}


def grid_range(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
    return {
        "sheetId": sheet_id,
        "startRowIndex": r0,
        "endRowIndex": r1,
        "startColumnIndex": c0,
        "endColumnIndex": c1,
    }


def source_range(sid: int, r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
    return {"sources": [grid_range(sid, r0, r1, c0, c1)]}


def _col1_to_a1(col_1based: int) -> str:
    """Spreadsheet column letter(s) from 1-based column index (A=1)."""
    n = col_1based
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _dashboard_zone_a1(z: _Zone1) -> str:
    c_lo = _col1_to_a1(z.col)
    c_hi = _col1_to_a1(z.col + z.cols - 1)
    r_lo = z.row
    r_hi = z.row + z.rows - 1
    return f"'dashboard'!{c_lo}{r_lo}:{c_hi}{r_hi}"


def _extract_zone_subgrid(grid: list[list[Any]], z: _Zone1) -> list[list[Any]]:
    """Copy grid rows/cols for zone; pad/truncate to zone width."""
    w = z.cols
    out: list[list[Any]] = []
    for r in range(z.r0(), z.r1()):
        row = grid[r] if r < len(grid) else []
        chunk = list(row[z.c0() : z.c1()])
        if len(chunk) < w:
            chunk.extend([""] * (w - len(chunk)))
        else:
            chunk = chunk[:w]
        out.append(chunk)
    return out


def _chart_envelope(*, title: str, subtitle: str | None, alt: str) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "title": title,
        "altText": alt,
        "titleTextFormat": {"bold": True, "fontSize": 14, "foregroundColor": CHART_TITLE_FG},
        "backgroundColorStyle": CHART_BG,
    }
    if subtitle:
        spec["subtitle"] = subtitle
        spec["subtitleTextFormat"] = {"fontSize": 10, "foregroundColor": CHART_SUBTITLE_FG}
    return spec


def _chart_pos(sheet_id: int, row_0: int, col_0: int, w: int, h: int) -> dict[str, Any]:
    return {
        "overlayPosition": {
            "anchorCell": {"sheetId": sheet_id, "rowIndex": row_0, "columnIndex": col_0},
            "offsetXPixels": 0,
            "offsetYPixels": 0,
            "widthPixels": w,
            "heightPixels": h,
        }
    }


def _exclusion_tokens_pipe(val: str) -> list[str]:
    return [t.strip() for t in val.split("|") if t.strip()]


def _exclusion_pairs_double_pipe(val: str) -> list[str]:
    return [t.strip() for t in val.split("||") if t.strip()]


def filter_rows_like_sheet(
    rows: list[dict[str, str]], mode: str, val: str
) -> list[dict[str, str]]:
    """Same semantics as ``filtered_layer2`` on dashboard_data (M1/O1)."""
    m = (mode or "").strip()
    v = (val or "").strip()
    if not m or m.lower() == "none" or not v:
        return list(rows)
    if m == "Brand":
        drop = set(_exclusion_tokens_pipe(v))
        return [r for r in rows if (r.get("brand") or "").strip() not in drop]
    if m == "Category":
        drop = set(_exclusion_tokens_pipe(v))
        return [r for r in rows if (r.get("category") or "").strip() not in drop]
    if m == "Brand+Category":
        drop = set(_exclusion_pairs_double_pipe(v))
        return [
            r
            for r in rows
            if f"{(r.get('brand') or '').strip()} | {(r.get('category') or '').strip()}" not in drop
        ]
    return list(rows)


def build_deployment_ledger_subtotal_rows(rows: list[dict[str, str]]) -> list[list[Any]]:
    """Brand × category lines, subtotal after each brand, pool total (matches classic screenshot)."""
    parsed: list[tuple[str, str, float]] = []
    for r in rows:
        b = (r.get("brand") or "").strip()
        c = (r.get("category") or "").strip()
        a = fnum(r.get("allocated_cog_usd"))
        if a is None:
            continue
        parsed.append((b, c, round(float(a), 2)))
    parsed.sort(key=lambda t: (t[0].lower(), -t[2], t[1].lower()))
    out: list[list[Any]] = []
    cur: str | None = None
    sub = 0.0
    for b, c, a in parsed:
        if cur is not None and b != cur:
            out.append([cur, "— Subtotal (this brand) —", round(sub, 2)])
            sub = 0.0
        cur = b
        sub += a
        out.append([b, c, a])
    if cur is not None:
        out.append([cur, "— Subtotal (this brand) —", round(sub, 2)])
    total = round(sum(x[2] for x in parsed), 2)
    out.append(["", "TOTAL POOL (should match KPI)", total])
    return out


def _index_formula(anchor_row_1based: int, dd_ref: str, col_1based: int) -> str:
    return (
        f"=LET(i,ROW()-{anchor_row_1based}+1,src,{dd_ref},"
        f'IF(OR(i<1,i>ROWS(src)),"",IFERROR(INDEX(src,i,{col_1based}),"")))'
    )


def _dd_ref_a_h(d0: int, d1: int) -> str:
    lo, hi = d0 + 1, d1 + 1
    return f"'dashboard_data'!$A${lo}:$H${hi}"


def _dd_ref_a_g(c0: int, c1: int) -> str:
    lo, hi = c0 + 1, c1 + 1
    return f"'dashboard_data'!$A${lo}:$G${hi}"


def _empty_grid(rows: int, cols: int) -> list[list[Any]]:
    return [[""] * cols for _ in range(rows)]


def _paste_table_indexed(
    grid: list[list[Any]],
    zone: _Zone1,
    title: str,
    headers: list[str],
    n_data: int,
    dd_ref: str,
    col_indices_1based: tuple[int, ...],
) -> tuple[int, int, int, int]:
    """Write merged title row, header row, INDEX data rows. Returns (tr, hr, d0, d1) 0-based."""
    z = zone
    tr, hr = z.r0(), z.r0() + 1
    d0 = z.r0() + 2
    anchor_1based = d0 + 1
    grid[tr][z.c0()] = title
    for i, h in enumerate(headers):
        if z.c0() + i < len(grid[0]):
            grid[hr][z.c0() + i] = h
    for i in range(n_data):
        rr = d0 + i
        if rr >= len(grid):
            break
        for j, scol in enumerate(col_indices_1based):
            cc = z.c0() + j
            if cc < len(grid[0]):
                grid[rr][cc] = _index_formula(anchor_1based, dd_ref, scol)
    d1 = d0 + n_data
    return tr, hr, d0, min(d1, len(grid))


def read_dashboard_filter(service: Any, spreadsheet_id: str) -> tuple[str, str]:
    try:
        resp = (
            service.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=["'dashboard'!M1", "'dashboard'!O1"],
            )
            .execute()
        )
        vrs = resp.get("valueRanges", [])
        m = "None"
        o = ""
        if vrs and vrs[0].get("values"):
            m = str(vrs[0]["values"][0][0]).strip() or "None"
        if len(vrs) > 1 and vrs[1].get("values"):
            o = str(vrs[1]["values"][0][0]).strip()
        return m, o
    except Exception:
        return "None", ""


def _table_body_rows(zone: _Zone1, cap: int = TABLE_TOP_N) -> int:
    """Title + header occupy 2 rows in each table zone."""
    return max(0, min(zone.rows - 2, cap))


def build_dashboard_value_grid(
    *,
    meta: dict[str, Any],
    kpis: dict[str, Any],
    kpi_col_letter: str,
    kpi_start_row_1based: int,
    insight_bullets: list[str],
    action_signals: list[str],
    ledger_rows: list[list[Any]],
    subtitle_text: str,
    initial_filter_mode: str,
    initial_filter_value: str,
) -> tuple[list[list[Any]], dict[str, Any]]:
    """Return values grid (0-based) + layout_meta for formatting (table row indices)."""
    grid = _empty_grid(DASHBOARD_ROW_COUNT, DASHBOARD_COL_COUNT)
    lm: dict[str, Any] = {}

    zt = DASHBOARD_LAYOUT["title"]
    grid[zt.r0()][zt.c0()] = "Projection Dashboard — Executive Summary"

    zs = DASHBOARD_LAYOUT["subtitle"]
    grid[zs.r0()][zs.c0()] = subtitle_text

    # Row 1: L–Q (0-based cols 11–16). M1=12, O1=14 hold validation.
    r = DASHBOARD_LAYOUT["filter_strip"].r0()
    grid[r][11] = "Mode"
    grid[r][12] = initial_filter_mode or "None"
    grid[r][13] = "Value"
    grid[r][14] = initial_filter_value or ""
    grid[r][15] = "Active"
    grid[r][16] = (
        '=IF(OR(TRIM($M$1)="",LOWER(TRIM($M$1))="none",TRIM($O$1)=""),'
        '"None","Excluding: "&TRIM($O$1))'
    )
    # Optional: numeric pool shown in KPI (dashboard_data AC3); does not change raw_layer2.
    grid[r][17] = "Pool (override $):"
    # col 18 (S1) left blank for user entry

    zk = DASHBOARD_LAYOUT["kpi_banner"]
    grid[zk.r0()][zk.c0()] = (
        "KPI snapshot — at a glance (full CSV via Python; tables follow L1:Q1 filter)"
    )

    zkb = DASHBOARD_LAYOUT["kpi_block"]
    kpi_defs = _kpi_definitions(kpis)
    for i, (lab, _v, _kind) in enumerate(kpi_defs):
        rr = zkb.r0() + i
        if rr >= len(grid):
            break
        kr = kpi_start_row_1based + i
        grid[rr][zkb.c0()] = lab
        grid[rr][zkb.c0() + 1] = f"='dashboard_data'!{kpi_col_letter}{kr}"

    zn = DASHBOARD_LAYOUT["narrative_block"]
    grid[zn.r0()][zn.c0()] = "What This Dashboard Says"
    for i, b in enumerate(insight_bullets[: zn.rows - 1]):
        grid[zn.r0() + 1 + i][zn.c0()] = "• " + b.replace("**", "")

    za = DASHBOARD_LAYOUT["action_block"]
    grid[za.r0()][za.c0()] = "Action Signals"
    for i, s in enumerate(action_signals[: za.rows - 1]):
        grid[za.r0() + 1 + i][za.c0()] = "• " + s.replace("**", "")

    rec_d = bool(kpis.get("recovery_uses_days"))
    pay_hdr = "Cash recovery (days)" if rec_d else "Payback (months)"
    std_h = [
        "Brand",
        "Category",
        "Allocated COG",
        pay_hdr,
        "Projected gross profit",
        "Revenue per $1 of COG",
    ]
    if rec_d:
        # Buy-plan: raw cash_recovery_days is cash-cycle capped (~flat). Tables use GP payback instead.
        std_h[3] = "COG payback via gross profit (days)"
    rank_cols = (2, 3, 4, 7, 6, 8)

    def _rank(prefix: str, zone_key: str, title: str, *, headers: list[str] | None = None, cols: tuple[int, ...] | None = None) -> None:
        z = DASHBOARD_LAYOUT[zone_key]
        n_rank = _table_body_rows(z)
        d0, d1 = int(meta[f"{prefix}_data_start"]), int(meta[f"{prefix}_data_end"])
        ref = _dd_ref_a_h(d0, d1)
        tr, hr, ds, de = _paste_table_indexed(
            grid, z, title, headers or std_h, n_rank, ref, cols or rank_cols
        )
        lm[zone_key] = {"title_row": tr, "header_row": hr, "data_start": ds, "data_end": de}

    _rank("alloc", "largest_alloc_table", "Biggest allocation rows")
    fast_headers = list(std_h)
    fast_cols = tuple(rank_cols)
    fast_title = f"Fastest cash recovery (Allocated COG ≥ ${MEANINGFUL_USD:g}; rows with payback data only)"
    if rec_d:
        # Buy-plan cash_recovery_days is intentionally ~flat at the cash-cycle cap; show velocity instead.
        fast_headers[3] = "Avg units / day"
        fast_cols = (2, 3, 4, 7, 6, 8)  # col 7 = avg_units_per_day in FAST_RECOVERY spill (A:H)
        fast_title = f"Fastest sell velocity (Allocated COG ≥ ${MEANINGFUL_USD:g}; ranked by avg units/day)"
    _rank(
        "fast_recovery",
        "fastest_recovery_table",
        fast_title,
        headers=fast_headers,
        cols=fast_cols,
    )
    _rank("gp", "highest_profit_table", "Highest projected gross profit (meaningful $)")
    _rank(
        "weak_margin",
        "weak_efficiency_table",
        f"High-dollar rows with weaker efficiency (Allocated COG ≥ ${HIGH_DOLLAR_USD:g})",
    )

    zc = DASHBOARD_LAYOUT["category_perf_table"]
    c0, c1 = int(meta["cat_data_start"]), int(meta["cat_data_end"])
    cref = _dd_ref_a_g(c0, c1)
    cat_h = [
        "Category",
        "Total allocation",
        (
            "Avg COG payback via GP (days)"
            if rec_d
            else "Avg payback (mo)"
        ),
        "Avg revenue per $1 COG",
        "Projected revenue",
        "Projected gross profit",
    ]
    cat_title = (
        "Category performance (payback & efficiency use rows with Allocated COG ≥ "
        f"${MEANINGFUL_USD:g} only)"
    ).replace("${MEANINGFUL_USD:g}", f"{MEANINGFUL_USD:g}")
    n_cat = _table_body_rows(zc, 80)
    tr, hr, ds, de = _paste_table_indexed(grid, zc, cat_title, cat_h, n_cat, cref, (1, 2, 3, 4, 5, 6))
    lm["category_perf_table"] = {"title_row": tr, "header_row": hr, "data_start": ds, "data_end": de}

    zl = DASHBOARD_LAYOUT["detail_ledger_table"]
    ltr = zl.r0()
    grid[ltr][zl.c0()] = "Detail — full deployment ledger (filtered view · brand subtotals)"
    grid[ltr + 1][zl.c0()] = "Brand"
    grid[ltr + 1][zl.c0() + 1] = "Category"
    grid[ltr + 1][zl.c0() + 2] = "Pool spend (Allocated COG)"
    max_body = zl.rows - 2
    for i, row in enumerate(ledger_rows[:max_body]):
        rr = ltr + 2 + i
        if rr >= len(grid):
            break
        for j in range(min(3, len(row))):
            grid[rr][zl.c0() + j] = row[j]
    lm["detail_ledger_table"] = {
        "title_row": ltr,
        "header_row": ltr + 1,
        "data_start": ltr + 2,
        "data_end": ltr + 2 + max_body,
    }

    return grid, lm


def _kpi_definitions(kpis: dict[str, Any]) -> list[tuple[str, Any, str]]:
    defs: list[tuple[str, Any, str]] = [
        ("Total allocation pool", kpis["total_pool"], "money"),
        ("Total projected revenue", kpis["total_rev"], "money"),
        ("Total projected gross profit", kpis["total_gp"], "money"),
    ]
    if kpis.get("is_buy_plan"):
        defs.append(
            (
                "Total units to purchase (funded rows)",
                round(kpis["total_units_buy"], 2) if kpis.get("total_units_buy") is not None else "",
                "num",
            )
        )
        defs.append(
            (
                "Weighted avg weeks to sell through",
                round(kpis["w_avg_weeks"], 2) if kpis.get("w_avg_weeks") is not None else "",
                "wk",
            )
        )
    if kpis.get("recovery_uses_days"):
        if kpis.get("is_buy_plan"):
            defs.extend(
                [
                    (
                        "Avg COG payback via GP (weighted by $)",
                        round(kpis["w_avg_cash_days"], 2)
                        if kpis.get("w_avg_cash_days")
                        else "",
                        "d",
                    ),
                    ("Largest single allocation", kpis["largest_txt"], "text"),
                    (
                        "Fastest velocity (meaningful $ rows)",
                        kpis["fastest_major_txt"],
                        "text",
                    ),
                    ("Highest projected profit row", kpis["high_gp_txt"], "text"),
                    (
                        "Dollars in CAPITAL RISK rows (>21 d GP payback)",
                        round(kpis["slow_dollars"], 2),
                        "money",
                    ),
                    (f"Best efficiency (≥ ${MEANINGFUL_USD:g} rows)", kpis["hi_eff_txt"], "text"),
                    ("Lowest efficiency among high-$ rows", kpis["lo_eff_txt"], "text"),
                ]
            )
        else:
            defs.extend(
                [
                    (
                        "Average cash recovery time (weighted by $)",
                        round(kpis["w_avg_cash_days"], 2)
                        if kpis.get("w_avg_cash_days")
                        else "",
                        "d",
                    ),
                    ("Largest single allocation", kpis["largest_txt"], "text"),
                    ("Fastest recovery (meaningful $ rows)", kpis["fastest_major_txt"], "text"),
                    ("Highest projected profit row", kpis["high_gp_txt"], "text"),
                    (
                        "Dollars in CAPITAL RISK rows (>21 d recovery)",
                        round(kpis["slow_dollars"], 2),
                        "money",
                    ),
                    (f"Best efficiency (≥ ${MEANINGFUL_USD:g} rows)", kpis["hi_eff_txt"], "text"),
                    ("Lowest efficiency among high-$ rows", kpis["lo_eff_txt"], "text"),
                ]
            )
    else:
        defs.extend(
            [
                (
                    "Average payback time (weighted by $)",
                    round(kpis["w_avg_mo"], 2) if kpis["w_avg_mo"] else "",
                    "mo",
                ),
                ("Largest single allocation", kpis["largest_txt"], "text"),
                ("Fastest payback (meaningful $ rows)", kpis["fastest_major_txt"], "text"),
                ("Highest projected profit row", kpis["high_gp_txt"], "text"),
                ("Dollars in slow rows (>4 mo payback)", round(kpis["slow_dollars"], 2), "money"),
                (f"Best efficiency (≥ ${MEANINGFUL_USD:g} rows)", kpis["hi_eff_txt"], "text"),
                ("Lowest efficiency among high-$ rows", kpis["lo_eff_txt"], "text"),
            ]
        )
    return defs


def clear_dashboard_sheet(service: Any, spreadsheet_id: str, sheet_id: int) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'dashboard'!A1:AJ{DASHBOARD_ROW_COUNT}",
        body={},
    ).execute()
    delete_charts_on_sheet(service, spreadsheet_id, sheet_id)


def delete_charts_on_sheet(service: Any, spreadsheet_id: str, sheet_id: int) -> None:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId),charts(chartId))",
    ).execute()
    reqs: list[dict[str, Any]] = []
    for sh in meta.get("sheets", []):
        if sh.get("properties", {}).get("sheetId") != sheet_id:
            continue
        for ch in sh.get("charts") or []:
            cid = ch.get("chartId")
            if cid is not None:
                reqs.append({"deleteEmbeddedObject": {"objectId": cid}})
    if reqs:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": reqs}
        ).execute()


def apply_dashboard_grid(sheet_id: int) -> list[dict[str, Any]]:
    """Frozen rows/columns + column widths (deterministic)."""
    widths = [
        (0, 1, 160),
        (1, 2, 140),
        (2, 3, 120),
        (3, 4, 120),
        (4, 5, 140),
        (5, 6, 120),
        (6, 7, 90),
        (7, 8, 90),
        (8, 9, 90),
        (9, 10, 90),
        (10, 11, 90),
        (11, 18, 100),
        (18, 24, 85),
        (24, 36, 80),
    ]
    reqs: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 3,
                        "frozenColumnCount": 0,
                        "hideGridlines": False,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount,gridProperties.hideGridlines",
            }
        }
    ]
    for s, e, px in widths:
        reqs.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": s,
                        "endIndex": e,
                    },
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )
    title_rows = {0, 2, 14, 18, 21, 35, 47, 59, 70, 77}
    for ri in title_rows:
        reqs.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": ri,
                        "endIndex": ri + 1,
                    },
                    "properties": {"pixelSize": 28},
                    "fields": "pixelSize",
                }
            }
        )
    return reqs


def apply_dashboard_formatting(
    sheet_id: int, layout_meta: dict[str, Any], kpis: dict[str, Any]
) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    reqs.append(
        {"unmergeCells": {"range": grid_range(sheet_id, 0, DASHBOARD_ROW_COUNT, 0, DASHBOARD_COL_COUNT)}}
    )

    def merge_zone(zn: str) -> None:
        z = DASHBOARD_LAYOUT[zn]
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, z.r0(), z.r1(), z.c0(), z.c1()),
                    "mergeType": "MERGE_ALL",
                }
            }
        )

    for zn in ("title", "subtitle", "kpi_banner"):
        merge_zone(zn)
    zf = DASHBOARD_LAYOUT["filter_strip"]
    reqs.append(
        {
            "mergeCells": {
                "range": grid_range(sheet_id, zf.r0(), zf.r1(), zf.c0() + 5, zf.c1()),
                "mergeType": "MERGE_ALL",
            }
        }
    )

    zt = DASHBOARD_LAYOUT["title"]
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, zt.r0(), zt.r1(), zt.c0(), zt.c1()),
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": BANNER_FG},
                        "backgroundColor": SUBHDR,
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment)",
            }
        }
    )
    zs = DASHBOARD_LAYOUT["subtitle"]
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, zs.r0(), zs.r1(), zs.c0(), zs.c1()),
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontSize": 10},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        }
    )

    zk = DASHBOARD_LAYOUT["kpi_banner"]
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, zk.r0(), zk.r1(), zk.c0(), zk.c1()),
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True, "foregroundColor": SECTION_BAR_FG, "fontSize": 11},
                        "backgroundColor": SECTION_BAR,
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment)",
            }
        }
    )

    zkb = DASHBOARD_LAYOUT["kpi_block"]
    kinds = []
    for _lab, _v, kind in _kpi_definitions(kpis):
        kinds.append(kind)
    for i, kind in enumerate(kinds):
        rr = zkb.r0() + i
        if rr >= zkb.r1():
            break
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, rr, rr + 1, zkb.c0(), zkb.c0() + 1),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 10},
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,verticalAlignment)",
                }
            }
        )
        if kind == "money":
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, rr, rr + 1, zkb.c0() + 1, zkb.c0() + 2),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
        elif kind in ("mo", "wk", "num", "d"):
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, rr, rr + 1, zkb.c0() + 1, zkb.c0() + 2),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    for block_key, banner_title in (
        ("narrative_block", "What This Dashboard Says"),
        ("action_block", "Action Signals"),
    ):
        z = DASHBOARD_LAYOUT[block_key]
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, z.r0(), z.r0() + 1, z.c0(), z.c1()),
                    "mergeType": "MERGE_ALL",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, z.r0(), z.r0() + 1, z.c0(), z.c1()),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": SECTION_BAR_FG, "fontSize": 11},
                            "backgroundColor": SECTION_BAR,
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment)",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, z.r0() + 1, z.r1(), z.c0(), z.c1()),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 10},
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "TOP",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,wrapStrategy,verticalAlignment)",
                }
            }
        )

    def style_standard_table(zone_key: str, ncols: int) -> None:
        block = layout_meta.get(zone_key) or {}
        tr = block.get("title_row")
        hr = block.get("header_row")
        d0 = block.get("data_start")
        d1 = block.get("data_end")
        z = DASHBOARD_LAYOUT[zone_key]
        if tr is None:
            return
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, tr, tr + 1, z.c0(), z.c1()),
                    "mergeType": "MERGE_ALL",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, tr, tr + 1, z.c0(), z.c1()),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": BANNER_FG},
                            "backgroundColor": SUBHDR,
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment)",
                }
            }
        )
        if hr is not None:
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, hr, hr + 1, z.c0(), z.c0() + ncols),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "foregroundColor": HDR_FG, "fontSize": 9},
                                "backgroundColor": HDR,
                                "horizontalAlignment": "CENTER",
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,wrapStrategy)",
                    }
                }
            )
        if d1 and d0 is not None and d1 > d0:
            border_top = hr if hr is not None else tr + 1
            reqs.append(
                {
                    "updateBorders": {
                        "range": grid_range(sheet_id, border_top, d1, z.c0(), z.c0() + ncols),
                        "top": {"style": "SOLID", "width": 1, "color": {}},
                        "bottom": {"style": "SOLID", "width": 1, "color": {}},
                        "left": {"style": "SOLID", "width": 1, "color": {}},
                        "right": {"style": "SOLID", "width": 1, "color": {}},
                        "innerHorizontal": {"style": "SOLID", "width": 1, "color": {}},
                        "innerVertical": {"style": "SOLID", "width": 1, "color": {}},
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, z.c0(), z.c0() + ncols),
                        "cell": {
                            "userEnteredFormat": {
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat.verticalAlignment",
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, z.c0() + 2, z.c0() + 3),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, z.c0() + 3, z.c0() + 4),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, z.c0() + 4, z.c0() + 5),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, z.c0() + 5, z.c0() + 6),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    for key in (
        "largest_alloc_table",
        "fastest_recovery_table",
        "highest_profit_table",
        "weak_efficiency_table",
    ):
        style_standard_table(key, 8)

    zc = DASHBOARD_LAYOUT["category_perf_table"]
    cat = layout_meta.get("category_perf_table") or {}
    tr, hr, d0, d1 = cat.get("title_row"), cat.get("header_row"), cat.get("data_start"), cat.get("data_end")
    if tr is not None:
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, tr, tr + 1, zc.c0(), zc.c1()),
                    "mergeType": "MERGE_ALL",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, tr, tr + 1, zc.c0(), zc.c1()),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": BANNER_FG},
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        if hr is not None:
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, hr, hr + 1, zc.c0(), zc.c1()),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "foregroundColor": HDR_FG, "fontSize": 9},
                                "backgroundColor": HDR,
                                "horizontalAlignment": "CENTER",
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,wrapStrategy)",
                    }
                }
            )
        if d1 and d0 is not None and d1 > d0:
            reqs.append(
                {
                    "updateBorders": {
                        "range": grid_range(sheet_id, hr or d0, d1, zc.c0(), zc.c1()),
                        "top": {"style": "SOLID", "width": 1, "color": {}},
                        "bottom": {"style": "SOLID", "width": 1, "color": {}},
                        "left": {"style": "SOLID", "width": 1, "color": {}},
                        "right": {"style": "SOLID", "width": 1, "color": {}},
                        "innerHorizontal": {"style": "SOLID", "width": 1, "color": {}},
                        "innerVertical": {"style": "SOLID", "width": 1, "color": {}},
                    }
                }
            )
            for c0, c1 in ((1, 2), (4, 5), (5, 6)):
                reqs.append(
                    {
                        "repeatCell": {
                            "range": grid_range(sheet_id, d0, d1, zc.c0() + c0, zc.c0() + c1),
                            "cell": {
                                "userEnteredFormat": {
                                    "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                                }
                            },
                            "fields": "userEnteredFormat.numberFormat",
                        }
                    }
                )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, zc.c0() + 2, zc.c0() + 4),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.000"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    ld = layout_meta.get("detail_ledger_table") or {}
    zl = DASHBOARD_LAYOUT["detail_ledger_table"]
    ltr = ld.get("title_row")
    lhr = ld.get("header_row")
    ls, le = ld.get("data_start"), ld.get("data_end")
    if ltr is not None:
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, ltr, ltr + 1, zl.c0(), zl.c1()),
                    "mergeType": "MERGE_ALL",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, ltr, ltr + 1, zl.c0(), zl.c1()),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": BANNER_FG},
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
    if lhr is not None:
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, lhr, lhr + 1, zl.c0(), zl.c0() + 3),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": HDR_FG},
                            "backgroundColor": HDR,
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            }
        )
    if le and ls is not None and le > ls:
        reqs.append(
            {
                "updateBorders": {
                    "range": grid_range(sheet_id, lhr or ls, le, zl.c0(), zl.c0() + 3),
                    "top": {"style": "SOLID", "width": 1, "color": {}},
                    "bottom": {"style": "SOLID", "width": 1, "color": {}},
                    "left": {"style": "SOLID", "width": 1, "color": {}},
                    "right": {"style": "SOLID", "width": 1, "color": {}},
                    "innerHorizontal": {"style": "SOLID", "width": 1, "color": {}},
                    "innerVertical": {"style": "SOLID", "width": 1, "color": {}},
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, ls, le, zl.c0() + 2, zl.c0() + 3),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
        )

    return reqs


def dashboard_conditional_formats(
    sheet_id: int, layout_meta: dict[str, Any], kpis: dict[str, Any]
) -> list[dict[str, Any]]:
    """Heatmaps on payback + revenue/$1 columns for standard 6-col ranking tables."""
    reqs: list[dict[str, Any]] = []
    idx = 0
    rec_d = bool(kpis.get("recovery_uses_days"))
    for key in (
        "largest_alloc_table",
        "fastest_recovery_table",
        "highest_profit_table",
        "weak_efficiency_table",
    ):
        if key == "fastest_recovery_table" and rec_d:
            # In buy-plan mode this table shows avg units/day (not payback); skip misleading payback heatmaps.
            continue
        b = layout_meta.get(key) or {}
        d0, d1 = b.get("data_start"), b.get("data_end")
        z = DASHBOARD_LAYOUT[key]
        if d0 is None or d1 is None or d1 <= d0:
            continue
        c_pay0 = z.c0() + 3
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, d0, d1, c_pay0, c_pay0 + 1)],
                        "gradientRule": {
                            "minpoint": {"color": {"red": 0.2, "green": 0.62, "blue": 0.38}, "type": "MIN"},
                            "maxpoint": {"color": {"red": 0.95, "green": 0.52, "blue": 0.32}, "type": "MAX"},
                        },
                    },
                    "index": idx,
                }
            }
        )
        idx += 1
        c_eff0 = z.c0() + 5
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, d0, d1, c_eff0, c_eff0 + 1)],
                        "gradientRule": {
                            "minpoint": {"color": {"red": 0.88, "green": 0.42, "blue": 0.42}, "type": "MIN"},
                            "maxpoint": {"color": {"red": 0.28, "green": 0.52, "blue": 0.42}, "type": "MAX"},
                        },
                    },
                    "index": idx,
                }
            }
        )
        idx += 1
    cat = layout_meta.get("category_perf_table") or {}
    cd0, cd1 = cat.get("data_start"), cat.get("data_end")
    zc = DASHBOARD_LAYOUT["category_perf_table"]
    if cd0 is not None and cd1 is not None and cd1 > cd0:
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, cd0, cd1, zc.c0() + 3, zc.c0() + 4)],
                        "gradientRule": {
                            "minpoint": {"color": {"red": 0.88, "green": 0.42, "blue": 0.42}, "type": "MIN"},
                            "maxpoint": {"color": {"red": 0.28, "green": 0.52, "blue": 0.42}, "type": "MAX"},
                        },
                    },
                    "index": idx,
                }
            }
        )
    return reqs


def build_dashboard_charts(
    dd_id: int,
    dash_id: int,
    meta: dict[str, Any],
    *,
    pie_category_count: int | None = None,
) -> list[dict[str, Any]]:
    ad0 = meta["alloc_data_start"]
    ad1 = min(meta["alloc_data_start"] + CHART_TOP_N, meta["alloc_data_end"] + 1)
    fr0, fr1 = meta["fast_recovery_data_start"], meta["fast_recovery_data_end"] + 1
    c0, c1 = meta["cat_data_start"], meta["cat_data_end"] + 1
    # Pie/donut: only rows with real category spill (padded blanks have non-numeric col B).
    # Prefer filtered distinct categories (matches visible spill); else meta from full push.
    if pie_category_count is not None:
        _nuc = max(int(pie_category_count), 1)
    else:
        _nuc = max(int(meta.get("n_unique_categories") or 0), 1)
    pie_row_excl = min(c0 + _nuc, c1)
    b0, b1 = meta["bucket_data_start"], meta["bucket_data_end"] + 1
    br0, br1 = meta["brand_data_start"], meta["brand_data_end"] + 1
    axis_days = bool(meta.get("recovery_axis_days"))
    pay_lbl = "Cash recovery (days)" if axis_days else "Payback (months)"
    pool_amt = meta.get("total_pool_alloc_usd")
    pool_phrase = f"${float(pool_amt):,.0f}" if isinstance(pool_amt, (int, float)) else "the pool"
    bucket_title = (
        "Line count by cash-cycle bucket (SAFE / WARNING / CAPITAL RISK)"
        if axis_days
        else "How many lines sit in each recovery-speed bucket?"
    )
    cat_rec_title = (
        "Recovery speed by category (avg cash recovery, meaningful $ only)"
        if axis_days
        else "Recovery speed by category (avg payback, meaningful $ only)"
    )

    pie = DASHBOARD_LAYOUT["pie_chart"]
    brc = DASHBOARD_LAYOUT["brand_chart"]
    alc = DASHBOARD_LAYOUT["allocation_chart"]
    combo = DASHBOARD_LAYOUT["alloc_vs_profit_chart"]
    fch = DASHBOARD_LAYOUT["fastest_recovery_chart"]
    rb = DASHBOARD_LAYOUT["recovery_bucket_chart"]
    cr = DASHBOARD_LAYOUT["category_recovery_chart"]

    def add_chart(req: dict[str, Any]) -> dict[str, Any]:
        return {"addChart": req}

    return [
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title="How the pool splits across product categories",
                            subtitle="Each slice = one category row · Legend on the right",
                            alt="Donut of allocated COG by category.",
                        ),
                        "pieChart": {
                            "legendPosition": "RIGHT_LEGEND",
                            "domain": {"sourceRange": source_range(dd_id, c0, pie_row_excl, 0, 1)},
                            "series": {"sourceRange": source_range(dd_id, c0, pie_row_excl, 1, 2)},
                            "pieHole": 0.52,
                            "threeDimensional": False,
                        },
                    },
                    "position": _chart_pos(dash_id, pie.r0(), pie.c0(), 430, 320),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title="Which brands hold the most allocated dollars?",
                            subtitle="Bars = sum of allocated COG per brand",
                            alt="Horizontal bars of allocated COG by brand.",
                        ),
                        "basicChart": {
                            "chartType": "BAR",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "LEFT_AXIS", "title": "Brand"},
                                {"position": "BOTTOM_AXIS", "title": "Total allocated COG ($)"},
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, br0, br1, 0, 1)}}],
                            "series": [
                                {
                                    "series": {"sourceRange": source_range(dd_id, br0, br1, 1, 2)},
                                    "targetAxis": "BOTTOM_AXIS",
                                    "color": SERIES_PRIMARY,
                                    "dataLabel": {
                                        "type": "DATA",
                                        "placement": "OUTSIDE_END",
                                        "textFormat": {"fontSize": 8},
                                    },
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, brc.r0(), brc.c0(), 500, 320),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title=f"Where {pool_phrase} is going — biggest allocation rows",
                            subtitle="Horizontal bars: allocated COG per brand × category",
                            alt="Top allocation lines by dollars.",
                        ),
                        "basicChart": {
                            "chartType": "BAR",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "LEFT_AXIS", "title": "Brand × category line"},
                                {"position": "BOTTOM_AXIS", "title": "Allocated COG (USD)"},
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, ad0, ad1, 0, 1)}}],
                            "series": [
                                {
                                    "series": {"sourceRange": source_range(dd_id, ad0, ad1, 3, 4)},
                                    "targetAxis": "BOTTOM_AXIS",
                                    "color": SERIES_PRIMARY,
                                    "dataLabel": {
                                        "type": "DATA",
                                        "placement": "OUTSIDE_END",
                                        "textFormat": {"fontSize": 8},
                                    },
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, alc.r0(), alc.c0(), 600, 720),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title="Dollars deployed vs projected gross profit",
                            subtitle="Blue columns = allocated COG · Copper line = projected gross profit",
                            alt="Combo chart of allocated COG and projected gross profit.",
                        ),
                        "basicChart": {
                            "chartType": "COMBO",
                            "legendPosition": "BOTTOM_LEGEND",
                            "compareMode": "CATEGORY",
                            "interpolateNulls": True,
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Brand × category line"},
                                {"position": "LEFT_AXIS", "title": "Allocated COG ($)"},
                                {"position": "RIGHT_AXIS", "title": "Projected gross profit ($)"},
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, ad0, ad1, 0, 1)}}],
                            "series": [
                                {
                                    "series": {"sourceRange": source_range(dd_id, ad0, ad1, 3, 4)},
                                    "targetAxis": "LEFT_AXIS",
                                    "type": "COLUMN",
                                    "color": SERIES_PRIMARY,
                                },
                                {
                                    "series": {"sourceRange": source_range(dd_id, ad0, ad1, 5, 6)},
                                    "targetAxis": "RIGHT_AXIS",
                                    "type": "LINE",
                                    "color": SERIES_SECONDARY,
                                    "lineStyle": {"width": 2, "type": "SOLID"},
                                },
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, combo.r0(), combo.c0(), 820, 420),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title=(
                                "Fastest sell velocity — avg units/day"
                                if axis_days
                                else "Fastest cash recovery — payback time (months)"
                            ),
                            subtitle=(
                                "Higher is faster · Same rows as Fastest sell velocity table"
                                if axis_days
                                else "Lower is faster · Same rows as Fastest cash recovery table"
                            ),
                            alt=(
                                "Column chart of avg units/day for fastest-selling lines."
                                if axis_days
                                else "Column chart of recovery time for fastest lines."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Line (brand / category)"},
                                {
                                    "position": "LEFT_AXIS",
                                    "title": ("Avg units / day" if axis_days else pay_lbl),
                                },
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, fr0, fr1, 0, 1)}}],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, fr0, fr1, 6, 7)
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                    "color": SERIES_PRIMARY,
                                    "dataLabel": {
                                        "type": "DATA",
                                        "placement": "OUTSIDE_END",
                                        "textFormat": {"fontSize": 8},
                                    },
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, fch.r0(), fch.c0(), 800, 400),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title=bucket_title,
                            subtitle="Column height = number of lines per bucket",
                            alt="Bucket line counts.",
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Bucket"},
                                {"position": "LEFT_AXIS", "title": "Number of lines"},
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, b0, b1, 0, 1)}}],
                            "series": [
                                {
                                    "series": {"sourceRange": source_range(dd_id, b0, b1, 1, 2)},
                                    "targetAxis": "LEFT_AXIS",
                                    "color": SERIES_PRIMARY,
                                    "dataLabel": {
                                        "type": "DATA",
                                        "placement": "OUTSIDE_END",
                                        "textFormat": {"bold": True, "fontSize": 9},
                                    },
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, rb.r0(), rb.c0(), 520, 300),
                }
            }
        ),
        add_chart(
            {
                "chart": {
                    "spec": {
                        **_chart_envelope(
                            title=cat_rec_title,
                            subtitle=f"Weighted average · rows with allocated COG ≥ {MEANINGFUL_USD:g}",
                            alt="Category average recovery or payback.",
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Category"},
                                {"position": "LEFT_AXIS", "title": pay_lbl},
                            ],
                            "domains": [{"domain": {"sourceRange": source_range(dd_id, c0, pie_row_excl, 0, 1)}}],
                            "series": [
                                {
                                    "series": {"sourceRange": source_range(dd_id, c0, pie_row_excl, 2, 3)},
                                    "targetAxis": "LEFT_AXIS",
                                    "color": SERIES_PRIMARY,
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": _chart_pos(dash_id, cr.r0(), cr.c0(), 540, 320),
                }
            }
        ),
    ]


def count_conditional_format_rules(service: Any, spreadsheet_id: str, sheet_id: int) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId),conditionalFormats)",
    ).execute()
    for sh in meta.get("sheets", []):
        if sh.get("properties", {}).get("sheetId") != sheet_id:
            continue
        return len(sh.get("conditionalFormats") or [])
    return 0


def delete_conditional_format_rules(sheet_id: int, n: int) -> list[dict[str, Any]]:
    return [{"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}} for i in range(n - 1, -1, -1)]


def refresh_projection_dashboard_sheet(
    service: Any,
    spreadsheet_id: str,
    *,
    meta: dict[str, Any],
    kpis: dict[str, Any],
    rows: list[dict[str, str]],
    kpi_col_letter: str,
    kpi_start_row_1based: int,
    insight_bullets: list[str],
    action_signals: list[str],
    filter_mode: str,
    filter_value: str,
    subtitle_text: str,
    update_subtitle: bool = True,
    update_narrative: bool = False,
) -> None:
    """
    Layout-preserving refresh: no sheet clear, no chart delete, no grid/formatting batchUpdate.

    Re-writes the deployment ledger block from Python (filtered). Optional subtitle and
    narrative/action blocks. Also re-pushes KPI labels (column A) and the full ranking +
    category table zones (title, headers, and INDEX bodies) so ``dashboard_data`` row
    changes never leave stale source ranges on the dashboard tab, without touching
    conditional formats or chart specs.
    """
    filtered = filter_rows_like_sheet(rows, filter_mode, filter_value)
    ledger = build_deployment_ledger_subtotal_rows(filtered)
    grid, _lm = build_dashboard_value_grid(
        meta=meta,
        kpis=kpis,
        kpi_col_letter=kpi_col_letter,
        kpi_start_row_1based=kpi_start_row_1based,
        insight_bullets=insight_bullets,
        action_signals=action_signals,
        ledger_rows=ledger,
        subtitle_text=subtitle_text,
        initial_filter_mode=filter_mode,
        initial_filter_value=filter_value,
    )
    data: list[dict[str, Any]] = []
    z_led = DASHBOARD_LAYOUT["detail_ledger_table"]
    data.append(
        {
            "range": _dashboard_zone_a1(z_led),
            "values": _extract_zone_subgrid(grid, z_led),
        }
    )
    if update_subtitle:
        zs = DASHBOARD_LAYOUT["subtitle"]
        data.append(
            {
                "range": _dashboard_zone_a1(zs),
                "values": _extract_zone_subgrid(grid, zs),
            }
        )
    zkb = DASHBOARD_LAYOUT["kpi_block"]
    data.append(
        {
            "range": _dashboard_zone_a1(zkb),
            "values": _extract_zone_subgrid(grid, zkb),
        }
    )
    # Re-push entire table zones (title + headers + INDEX rows) so dashboard_data row shifts
    # never leave stale 'dashboard_data'!$A$… ranges in the INDEX bodies after a refresh.
    for zone_key in (
        "largest_alloc_table",
        "fastest_recovery_table",
        "highest_profit_table",
        "weak_efficiency_table",
        "category_perf_table",
    ):
        z = DASHBOARD_LAYOUT[zone_key]
        if z.r0() >= len(grid):
            continue
        data.append(
            {
                "range": _dashboard_zone_a1(z),
                "values": _extract_zone_subgrid(grid, z),
            }
        )
    if update_narrative:
        zn = DASHBOARD_LAYOUT["narrative_block"]
        za = DASHBOARD_LAYOUT["action_block"]
        data.append(
            {
                "range": _dashboard_zone_a1(zn),
                "values": _extract_zone_subgrid(grid, zn),
            }
        )
        data.append(
            {
                "range": _dashboard_zone_a1(za),
                "values": _extract_zone_subgrid(grid, za),
            }
        )
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()


def rebuild_projection_dashboard_sheet(
    service: Any,
    spreadsheet_id: str,
    dashboard_sheet_id: int,
    dd_id: int,
    *,
    meta: dict[str, Any],
    kpis: dict[str, Any],
    rows: list[dict[str, str]],
    kpi_col_letter: str,
    kpi_start_row_1based: int,
    insight_bullets: list[str],
    action_signals: list[str],
    filter_mode: str,
    filter_value: str,
    subtitle_text: str,
) -> dict[str, Any]:
    """
    Full rebuild: clear tab, write values, grid props, formatting, CF, charts.
    Returns layout_meta for logging.
    """
    clear_dashboard_sheet(service, spreadsheet_id, dashboard_sheet_id)
    filtered = filter_rows_like_sheet(rows, filter_mode, filter_value)
    pie_cat_count = max(
        len(
            {
                (r.get("category") or "").strip()
                for r in filtered
                if (r.get("category") or "").strip()
            }
        ),
        1,
    )
    ledger = build_deployment_ledger_subtotal_rows(filtered)
    grid, layout_meta = build_dashboard_value_grid(
        meta=meta,
        kpis=kpis,
        kpi_col_letter=kpi_col_letter,
        kpi_start_row_1based=kpi_start_row_1based,
        insight_bullets=insight_bullets,
        action_signals=action_signals,
        ledger_rows=ledger,
        subtitle_text=subtitle_text,
        initial_filter_mode=filter_mode,
        initial_filter_value=filter_value,
    )
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="'dashboard'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": grid},
    ).execute()

    cf_n = count_conditional_format_rules(service, spreadsheet_id, dashboard_sheet_id)
    reqs: list[dict[str, Any]] = []
    reqs.extend(delete_conditional_format_rules(dashboard_sheet_id, cf_n))
    reqs.extend(apply_dashboard_grid(dashboard_sheet_id))
    reqs.extend(apply_dashboard_formatting(dashboard_sheet_id, layout_meta, kpis))
    reqs.extend(dashboard_conditional_formats(dashboard_sheet_id, layout_meta, kpis))
    reqs.extend(
        build_dashboard_charts(
            dd_id, dashboard_sheet_id, meta, pie_category_count=pie_cat_count
        )
    )
    if reqs:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": reqs}
        ).execute()
    return layout_meta


# Historical name (full dashboard regeneration).
build_projection_dashboard_sheet = rebuild_projection_dashboard_sheet
