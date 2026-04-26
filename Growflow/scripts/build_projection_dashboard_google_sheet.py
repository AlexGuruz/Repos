#!/usr/bin/env python3
"""
Capital deployment dashboard: 4 tabs (raw_layer2, dashboard_data, dashboard, notes).
Reads layer2 CSV, validates ledger vs nominal pool (default $18k; buy-plan: deployed + unused), writes helper tables.
Executive KPI column on ``dashboard_data`` (AC) is **static values** from ``lib.projection_exec_kpis`` (full CSV), not array formulas.

**Two dashboard modes (``--dashboard-mode``; default ``refresh``):**

- **refresh** — Script-owned data: clears/rewrites ``raw_layer2``, ``dashboard_data`` (plus spill tail), ``notes``. Does **not** clear the ``dashboard`` tab, does **not** delete or recreate embedded charts, does **not** reapply dashboard grid/formatting/conditional formats. Updates the **deployment ledger** (and by default the **subtitle** row) via targeted ``values.batchUpdate``. KPI cells and INDEX ranking tables on ``dashboard`` are left unchanged and recalc from ``dashboard_data``. After ``dashboard_data`` is written, runs ``updateChartSpec`` on matching embedded charts (unless ``--no-patch-chart-sources``) so **data ranges** track the new meta **without** moving or resizing charts. First-time or broken layout: use **rebuild** once.

- **rebuild** — Full regeneration: clear ``dashboard`` working area, delete charts, rewrite the full dashboard grid, frozen panes, column widths, merges, borders, conditional formats, and recreate charts (same as ``lib.projection_dashboard_sheet_rebuilt``). Use for bootstrap or after you change dashboard layout code. Pair with ``--full-refresh`` + ``--confirm-layout-reset`` only when you also want raw-layer formatting and ``dashboard_data`` column tweaks from the script.

**Layout reset on raw / helper tabs:** ``--full-refresh`` requires ``--confirm-layout-reset``. In **refresh** mode, that path does **not** delete charts on the ``dashboard`` tab (only rebuild does).

**Optional smaller clear:** ``--bounded-clear`` limits clears on data tabs to the payload rectangle + pad. For ``dashboard_data``, clear depth still covers ``filtered_layer2`` spill. In **refresh** mode, the dashboard tab is never included in this clear.

**Maintaining a hand-tuned dashboard:** Run ``--dashboard-mode rebuild`` until structure is acceptable, adjust charts/spacing in Sheets, then use default ``refresh`` for routine CSV pushes. Capture a layout snapshot with ``scripts/export_projection_dashboard_layout.py --print``.

**Optional transfer landed COG (Growflow):** ``scripts/build_transfer_receipts_db.py`` writes SQLite + can export ``product_landed_cost_current.csv`` (see ``lib/product_landed_cost_sqlite.py``). That file is **SKU / Product.objectId** truth and is **not** merged into ``raw_layer2`` automatically; the **Notes** tab explains presence/absence next to the pushed layer2 CSV path so operators do not confuse dashboard dollars with transfer-line costs until the planner joins them.

**Fix one chart at a time (no layout wipe):** Stay on default ``refresh`` (never ``rebuild``). List titles with ``scripts/list_projection_dashboard_charts.py``, then pass ``--patch-charts-matching Substring`` (repeatable) so only charts whose title contains one of those substrings get ``updateChartSpec``. Other embedded charts and all dashboard cell formatting stay untouched.

Usage (repo root):
  PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py
  PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py --dashboard-mode rebuild
  PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py \\
    --spreadsheet-id YOUR_ID --sheets-service-account E:/secrets/gcp/stashbox.json
  # Raw tab reformat + destructive ops (requires confirm); use with rebuild when resetting everything:
  PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py \\
    --dashboard-mode rebuild --full-refresh --confirm-layout-reset
"""
from __future__ import annotations

import argparse
import copy
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.projection_dashboard_sheet_rebuilt import (  # noqa: E402
    DASHBOARD_ROW_COUNT as REBUILT_DASH_ROWS,
    filter_rows_like_sheet,
    read_dashboard_filter as read_dash_filter,
    rebuild_projection_dashboard_sheet,
    refresh_projection_dashboard_sheet,
)
from lib.projection_dashboard_sheet_dynamic import (  # noqa: E402
    FILTER_HELPERS_ROW_1BASED,
    FILTERED_LAYER2_ROW_1BASED,
    FILTERED_LAYER2_TAIL_ROWS,
    build_dashboard_data_formula_grid,
)
from lib.product_landed_cost_sqlite import dashboard_notes_transfer_cost_rows  # noqa: E402
from lib.projection_exec_kpis import compute_kpis, kpi_ac_column_values  # noqa: E402
DEFAULT_CSV = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"
MEANINGFUL_USD = 25.0
HIGH_DOLLAR_USD = 500.0
CHART_TOP_N = 15
TABLE_TOP_N = 20
# Dashboard tab: fixed-height table windows (INDEX into dashboard_data — no spill on presentation layer)
DASH_RANK_VISIBLE_ROWS = TABLE_TOP_N
DASH_CATEGORY_VISIBLE_ROWS = 35
DASH_VELOCITY_VISIBLE_ROWS = 40
DASH_LEDGER_VISIBLE_ROWS = 220
SCATTER_MAX_MONTHS = 36.0  # hide extreme noise in scatter (e.g. micro topical)
SCATTER_MAX_DAYS = 120.0  # buy-plan scatter: cash_recovery_days cap

# Line-count chart order when using cash_cycle_status (buy-plan)
_CASH_STATUS_BUCKET_ORDER = ("SAFE", "WARNING", "CAPITAL RISK")

# Theme colors (RGB 0-1 for Sheets API)
HDR = {"red": 0.27, "green": 0.45, "blue": 0.69}
HDR_FG = {"red": 1, "green": 1, "blue": 1}
ALT_ROW = {"red": 0.97, "green": 0.98, "blue": 1.0}
# Banner text on colored bars only (do not blanket-paint the sheet — follows spreadsheet / browser theme)
BANNER_FG = {"red": 1, "green": 1, "blue": 1}
SECTION_BAR = {"red": 0.22, "green": 0.32, "blue": 0.42}
SECTION_BAR_FG = BANNER_FG
SUBHDR = {"red": 0.12, "green": 0.16, "blue": 0.22}  # section title strip (dark blue)
DASH_COLS = 10  # A–J

# Embedded chart polish — dark plot panel, bright bars (gold standard)
CHART_BG = {"rgbColor": {"red": 0.05, "green": 0.05, "blue": 0.06}}
CHART_TITLE_FG = {"red": 0.95, "green": 0.96, "blue": 0.98}
CHART_SUBTITLE_FG = {"red": 0.72, "green": 0.76, "blue": 0.82}
SERIES_PRIMARY = {"red": 0.39, "green": 0.72, "blue": 1.0}  # bright blue bars on dark
SERIES_SECONDARY = {"red": 0.86, "green": 0.44, "blue": 0.18}  # copper line
SERIES_ACCENT = {"red": 0.35, "green": 0.78, "blue": 0.92}


def _chart_visual_envelope(
    title: str,
    *,
    subtitle: str | None,
    alt_text: str,
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "title": title,
        "altText": alt_text,
        "titleTextFormat": {
            "bold": True,
            "fontSize": 14,
            "foregroundColor": CHART_TITLE_FG,
        },
        "backgroundColorStyle": CHART_BG,
    }
    if subtitle:
        spec["subtitle"] = subtitle
        spec["subtitleTextFormat"] = {
            "fontSize": 10,
            "foregroundColor": CHART_SUBTITLE_FG,
        }
    return spec


def _service(sa: str | None):
    from lib.stashbox_sheets_auth import sheets_service

    return sheets_service(sa)


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        headers = list(r.fieldnames or [])
        rows = list(r)
    return headers, rows


def _configure_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError on Windows (cp1252) when printing en-dashes, arrows, etc."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if not callable(reconf):
            continue
        try:
            reconf(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError, TypeError):
            pass


def _use_cash_recovery_days_axis(rows: list[dict[str, str]]) -> bool:
    """Buy-plan + CSV has cash_recovery_days → charts/tables use days, not months_to_recover_cog."""
    if not rows or (rows[0].get("allocation_mode") or "").strip() != "buy-plan":
        return False
    return any(fnum(r.get("cash_recovery_days")) is not None for r in rows)


def fnum(x: str | None) -> float | None:
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _sheet_title_key(name: str) -> str:
    """Google Sheet names are unique case-insensitively; normalize for lookups."""
    return str(name or "").strip().casefold()


def ensure_sheets(
    service: Any, spreadsheet_id: str, titles: list[str]
) -> dict[str, int]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    # casefold key -> sheetId (last wins if API ever returned duplicates)
    by_key: dict[str, int] = {}
    for s in meta.get("sheets", []):
        p = s.get("properties", {})
        raw = p.get("title", "")
        by_key[_sheet_title_key(raw)] = p["sheetId"]

    requests: list[dict[str, Any]] = []
    for t in titles:
        if _sheet_title_key(t) not in by_key:
            requests.append({"addSheet": {"properties": {"title": t}}})
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        by_key.clear()
        for s in meta.get("sheets", []):
            p = s.get("properties", {})
            raw = p.get("title", "")
            by_key[_sheet_title_key(raw)] = p["sheetId"]
    out: dict[str, int] = {}
    for t in titles:
        k = _sheet_title_key(t)
        if k not in by_key:
            raise KeyError(f"Missing sheet after ensure: {t!r} (normalized {k!r})")
        out[t] = by_key[k]
    return out


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


def grid_range(sid: int, r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
    return {
        "sheetId": sid,
        "startRowIndex": r0,
        "endRowIndex": r1,
        "startColumnIndex": c0,
        "endColumnIndex": c1,
    }


def unmerge_dashboard_before_values_update(*, dashboard_sheet_id: int, last_row: int) -> dict[str, Any]:
    """Splits merged A:J (etc.) rows so Values API can write KPI links into column B.

    batch_format_executive_dashboard also unmerges, but that runs only on --full-refresh.
    Without this, merged KPI rows keep only the top-left cell and B stays empty on push.
    """
    last = max(120, int(last_row) + 5)
    # Through column R (18) so merges touching the L:Q filter strip are cleared.
    return {"unmergeCells": {"range": grid_range(dashboard_sheet_id, 0, last, 0, 18)}}


def batch_filter_control_validations(dashboard_sheet_id: int) -> list[dict[str, Any]]:
    """L1:Q1 filter: M1 mode list, O1 values from dashboard_data AB spill (same row as FILTER_HELPERS_ROW_1BASED).

    Freeze panes are set by ``projection_dashboard_sheet_rebuilt.apply_dashboard_grid`` (rows 3; no frozen column).
    """
    ab_row = FILTER_HELPERS_ROW_1BASED
    o1_range = f"='dashboard_data'!$AB${ab_row}:$AB$800"
    return [
        {
            "setDataValidation": {
                "range": grid_range(dashboard_sheet_id, 0, 1, 12, 13),
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": "None"},
                            {"userEnteredValue": "Brand"},
                            {"userEnteredValue": "Category"},
                            {"userEnteredValue": "Brand+Category"},
                        ],
                    },
                    # Strict mode flags harmless whitespace / casing drift on M1 (still offers the four modes).
                    "strict": False,
                    "showCustomUi": True,
                },
            }
        },
        {
            "setDataValidation": {
                "range": grid_range(dashboard_sheet_id, 0, 1, 14, 15),
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [{"userEnteredValue": o1_range}],
                    },
                    "strict": False,
                    "showCustomUi": True,
                    "inputMessage": "Suggestions from the list; you can type any value. "
                    "Exclude multiple brands or categories: separate with | (pipe). "
                    "Brand+Category mode: separate full pairs like Brand A | Vapes||Brand B | Edibles using || between pairs.",
                },
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": dashboard_sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 10,
                    "endIndex": 18,
                },
                "properties": {"pixelSize": 120},
                "fields": "pixelSize",
            }
        },
    ]


def source_range(sid: int, r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
    return {"sources": [grid_range(sid, r0, r1, c0, c1)]}


class _ChartRangeParams(NamedTuple):
    dd_id: int
    ad0: int
    ad1: int
    fr0: int
    fr1: int
    c0: int
    c1: int
    # Exclusive end row (0-based) for pie + category recovery charts; trims padded blank tail rows.
    pie_row_excl: int
    v0: int
    v1: int
    s0: int
    s1: int
    b0: int
    b1: int
    br0: int
    br1: int


def _chart_range_params(
    dd_id: int,
    meta: dict[str, Any],
    *,
    pie_category_count: int | None = None,
) -> _ChartRangeParams:
    c0 = meta["cat_data_start"]
    c1 = meta["cat_data_end"] + 1
    if pie_category_count is not None:
        _nuc = max(int(pie_category_count), 1)
    else:
        _nuc = max(int(meta.get("n_unique_categories") or 0), 1)
    pie_row_excl = min(c0 + _nuc, c1)
    return _ChartRangeParams(
        dd_id=dd_id,
        ad0=meta["alloc_data_start"],
        ad1=min(meta["alloc_data_start"] + CHART_TOP_N, meta["alloc_data_end"] + 1),
        fr0=meta["fast_recovery_data_start"],
        fr1=meta["fast_recovery_data_end"] + 1,
        c0=c0,
        c1=c1,
        pie_row_excl=pie_row_excl,
        v0=meta["vel_chart_data_start"],
        v1=meta["vel_chart_data_end"] + 1,
        s0=meta["scatter_data_start"],
        s1=meta["scatter_data_end"] + 1,
        b0=meta["bucket_data_start"],
        b1=meta["bucket_data_end"] + 1,
        br0=meta["brand_data_start"],
        br1=meta["brand_data_end"] + 1,
    )


def _a1_column_letter(zero_based_index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    n = zero_based_index + 1
    letters = ""
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def bounded_clear_a1_range(
    sheet_title: str,
    values: list[list[Any]],
    pad_rows: int,
    *,
    min_clear_rows: int | None = None,
) -> str:
    """A1 range covering the payload plus pad rows (clears a shrinking tail without wiping the whole tab)."""
    if not values:
        n_rows, n_cols = 1, 1
    else:
        n_rows = len(values) + max(0, pad_rows)
        if min_clear_rows is not None:
            n_rows = max(n_rows, min_clear_rows)
        n_cols = max(len(row) for row in values)
        n_cols = max(n_cols, 1)
    end_col = _a1_column_letter(n_cols - 1)
    return f"'{sheet_title}'!A1:{end_col}{n_rows}"


def write_projection_data_tabs(
    service: Any,
    sid: str,
    *,
    raw_values: list[list[Any]],
    dd_values: list[list[Any]],
    notes_v: list[list[Any]],
    clear_dashboard_tab: bool,
    bounded_clear: bool,
    bounded_pad: int,
) -> None:
    """
    Clear and rewrite script-owned tabs: raw_layer2, dashboard_data, notes.
    Optionally clears the dashboard tab (rebuild path only; refresh skips).
    Always clears the filtered_layer2 spill band on dashboard_data.
    """
    value_sets: list[tuple[str, list[list[Any]]]] = [
        ("raw_layer2", raw_values),
        ("dashboard_data", dd_values),
        ("notes", notes_v),
    ]
    pad = max(0, int(bounded_pad))
    if bounded_clear:
        dd_clear_floor = FILTERED_LAYER2_ROW_1BASED + FILTERED_LAYER2_TAIL_ROWS
        for sheet_title, vals in value_sets:
            min_r = dd_clear_floor if sheet_title == "dashboard_data" else None
            cr = bounded_clear_a1_range(sheet_title, vals, pad, min_clear_rows=min_r)
            service.spreadsheets().values().clear(spreadsheetId=sid, range=cr, body={}).execute()
        if clear_dashboard_tab:
            service.spreadsheets().values().clear(
                spreadsheetId=sid,
                range=f"'dashboard'!A1:AJ{REBUILT_DASH_ROWS}",
                body={},
            ).execute()
    else:
        for sheet_title, _vals in value_sets:
            service.spreadsheets().values().clear(
                spreadsheetId=sid, range=f"'{sheet_title}'!A:ZZ", body={}
            ).execute()
        if clear_dashboard_tab:
            service.spreadsheets().values().clear(
                spreadsheetId=sid, range="'dashboard'!A:ZZ", body={}
            ).execute()

    _dd_spill_clear_last_row = 4000
    service.spreadsheets().values().clear(
        spreadsheetId=sid,
        range=(
            f"'dashboard_data'!A{FILTERED_LAYER2_ROW_1BASED}:ZZ{_dd_spill_clear_last_row}"
        ),
        body={},
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range="'raw_layer2'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": raw_values},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range="'dashboard_data'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": dd_values},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range="'notes'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": notes_v},
    ).execute()


def _basic_chart_ready(bc: dict[str, Any], min_series: int) -> bool:
    doms = bc.get("domains") or []
    ser = bc.get("series") or []
    if len(doms) < 1 or len(ser) < min_series:
        return False
    d0 = doms[0].get("domain") or {}
    if not d0.get("sourceRange"):
        return False
    for i in range(min_series):
        if not (ser[i].get("series") or {}).get("sourceRange"):
            return False
    return True


def _chart_spec_title(spec: dict[str, Any]) -> str:
    """Best-effort title string for matching (Sheets may return a string or ChartText-like dict)."""
    t = spec.get("title")
    if t is None:
        return ""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        tx = t.get("text")
        if isinstance(tx, str) and tx.strip():
            return tx
        return str(t.get("content") or t.get("runs") or "").strip() or str(t)
    return str(t)


def _chart_spec_subtitle(spec: dict[str, Any]) -> str:
    """Subtitle field from ChartSpec (same shapes as ``title``)."""
    t = spec.get("subtitle")
    if t is None:
        return ""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        tx = t.get("text")
        if isinstance(tx, str) and tx.strip():
            return tx
        return str(t.get("content") or t.get("runs") or "").strip() or str(t)
    return str(t)


def _chart_spec_match_text(spec: dict[str, Any]) -> str:
    """Title and subtitle concatenated for substring matching (many charts expose key text in subtitle)."""
    parts = [_chart_spec_title(spec).strip(), _chart_spec_subtitle(spec).strip()]
    return " ".join(p for p in parts if p)


def _title_matches_any_substring(title: str, needles: tuple[str, ...]) -> bool:
    tl = title.casefold()
    return any(n.strip() and n.casefold() in tl for n in needles)


def _build_patched_chart_spec_if_match(
    spec: dict[str, Any], p: _ChartRangeParams
) -> dict[str, Any] | None:
    """Return a full ChartSpec copy with dashboard_data ranges updated, or None if unrecognized."""
    mt = _chart_spec_match_text(spec)
    out = copy.deepcopy(spec)
    bc = out.get("basicChart")
    pie = out.get("pieChart")

    def sr(r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
        return source_range(p.dd_id, r0, r1, c0, c1)

    if (
        (
            "Capital concentration" in mt
            or "biggest allocation rows" in mt.lower()
            or ("Where" in mt and "going" in mt)
            or (
                "horizontal bars" in mt.lower()
                and "allocated cog" in mt.lower()
                and "brand" in mt.lower()
                and ("category" in mt.lower() or "×" in mt or " x " in mt.lower())
            )
        )
        and bc
        and _basic_chart_ready(bc, 1)
    ):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.ad0, p.ad1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.ad0, p.ad1, 3, 4)
        return out
    if (
        ("Deploy $ vs upside" in mt or "Dollars deployed" in mt)
        and bc
        and _basic_chart_ready(bc, 2)
    ):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.ad0, p.ad1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.ad0, p.ad1, 3, 4)
        bc["series"][1]["series"]["sourceRange"] = sr(p.ad0, p.ad1, 5, 6)
        return out
    if (
        (
            "Fastest payback" in mt
            or "Fastest cash recovery" in mt
            or "Fastest sell velocity" in mt
        )
        and bc
        and _basic_chart_ready(bc, 1)
    ):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.fr0, p.fr1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.fr0, p.fr1, 6, 7)
        return out
    if ("Deployment mix" in mt or "How the pool splits" in mt) and pie:
        dom = pie.get("domain") or {}
        ser = pie.get("series") or {}
        if not dom.get("sourceRange") or not ser.get("sourceRange"):
            return None
        pie["domain"]["sourceRange"] = sr(p.c0, p.pie_row_excl, 0, 1)
        pie["series"]["sourceRange"] = sr(p.c0, p.pie_row_excl, 1, 2)
        return out
    if (
        mt.startswith("Weighted avg")
        or "Recovery speed by category" in mt
    ) and bc and _basic_chart_ready(bc, 1):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.c0, p.pie_row_excl, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.c0, p.pie_row_excl, 2, 3)
        return out
    if "Efficiency vs speed" in mt and bc and _basic_chart_ready(bc, 1):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.s0, p.s1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.s0, p.s1, 1, 2)
        return out
    if ("Line count by" in mt or "recovery-speed bucket" in mt.lower()) and bc and _basic_chart_ready(bc, 1):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.b0, p.b1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.b0, p.b1, 1, 2)
        return out
    if (
        "Brand share of deployed capital" in mt or "Which brands hold" in mt
    ) and bc and _basic_chart_ready(bc, 1):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.br0, p.br1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.br0, p.br1, 1, 2)
        return out
    if "Velocity profile" in mt and bc and _basic_chart_ready(bc, 2):
        bc["domains"][0]["domain"]["sourceRange"] = sr(p.v0, p.v1, 0, 1)
        bc["series"][0]["series"]["sourceRange"] = sr(p.v0, p.v1, 4, 5)
        bc["series"][1]["series"]["sourceRange"] = sr(p.v0, p.v1, 6, 7)
        return out
    return None


def patch_dashboard_chart_sources(
    service: Any,
    spreadsheet_id: str,
    dash_sheet_id: int,
    dd_id: int,
    meta: dict[str, Any],
    *,
    pie_category_count: int | None = None,
    chart_title_substrings: tuple[str, ...] | None = None,
) -> tuple[int, int]:
    """Update embedded chart data ranges via the API; position and pixel size are unchanged.

    If ``chart_title_substrings`` is set, only charts whose **title or subtitle** contains
    at least one needle (case-insensitive) are updated. Unrecognized charts are never touched.
    """
    p = _chart_range_params(dd_id, meta, pie_category_count=pie_category_count)
    meta_resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId),charts(chartId,spec))",
    ).execute()
    reqs: list[dict[str, Any]] = []
    total = 0
    def _strip_unsupported_update_fields(obj: Any) -> Any:
        # Google Sheets rejects some fields on updateChartSpec even if they exist on read specs.
        if isinstance(obj, dict):
            obj.pop("lineSmoothing", None)
            # COLUMN charts reject threeDimensional on updateChartSpec (read spec may include it).
            obj.pop("threeDimensional", None)
            return {k: _strip_unsupported_update_fields(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_strip_unsupported_update_fields(x) for x in obj]
        return obj

    for sh in meta_resp.get("sheets", []):
        if sh.get("properties", {}).get("sheetId") != dash_sheet_id:
            continue
        for ch in sh.get("charts") or []:
            cid = ch.get("chartId")
            spec = ch.get("spec")
            if cid is None or not spec:
                continue
            total += 1
            patched = _build_patched_chart_spec_if_match(spec, p)
            if patched is not None:
                match_text = _chart_spec_match_text(spec)
                if chart_title_substrings and not _title_matches_any_substring(
                    match_text, chart_title_substrings
                ):
                    continue
                reqs.append(
                    {
                        "updateChartSpec": {
                            "chartId": int(cid),
                            "spec": _strip_unsupported_update_fields(patched),
                        }
                    }
                )
    if reqs:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": reqs}
        ).execute()
    return len(reqs), total


def build_dashboard_data_values(rows: list[dict[str, str]]) -> tuple[list[list[Any]], dict[str, Any]]:
    """Returns flat values for dashboard_data + meta with row indices for charts (0-based)."""
    meta: dict[str, Any] = {}
    use_days = _use_cash_recovery_days_axis(rows)
    meta["recovery_axis_days"] = use_days
    meta["total_pool_alloc_usd"] = sum(fnum(r.get("allocated_cog_usd")) or 0 for r in rows)

    def sort_key_alloc(r: dict) -> float:
        return fnum(r.get("allocated_cog_usd")) or 0.0

    def recovery_metric(r: dict) -> float | None:
        return fnum(r.get("cash_recovery_days")) if use_days else fnum(r.get("months_to_recover_cog"))

    top_alloc = sorted(rows, key=sort_key_alloc, reverse=True)[:TABLE_TOP_N]
    top_gp = sorted(
        rows, key=lambda r: fnum(r.get("projected_gross_profit_usd")) or -1e18, reverse=True
    )[:TABLE_TOP_N]
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    top_eff = sorted(
        meaningful,
        key=lambda r: fnum(r.get("allocation_efficiency")) or -1,
        reverse=True,
    )[:TABLE_TOP_N]
    worst = sorted(
        meaningful,
        key=lambda r: recovery_metric(r) or -1,
        reverse=True,
    )[:TABLE_TOP_N]

    # Category summary (means use meaningful rows only for recovery & efficiency)
    cat_alloc: dict[str, float] = defaultdict(float)
    cat_rev: dict[str, float] = defaultdict(float)
    cat_gp: dict[str, float] = defaultdict(float)
    cat_mo_w: dict[str, float] = defaultdict(float)
    cat_eff_w: dict[str, float] = defaultdict(float)
    cat_mo_den: dict[str, float] = defaultdict(float)
    cat_eff_den: dict[str, float] = defaultdict(float)
    cat_cnt: dict[str, int] = defaultdict(int)
    for r in rows:
        c = r.get("category") or ""
        a = fnum(r.get("allocated_cog_usd")) or 0
        cat_alloc[c] += a
        cat_rev[c] += fnum(r.get("projected_revenue_from_allocated_units_usd")) or 0
        cat_gp[c] += fnum(r.get("projected_gross_profit_usd")) or 0
        cat_cnt[c] += 1
        if a >= MEANINGFUL_USD:
            mo = fnum(r.get("cash_recovery_days")) if use_days else fnum(r.get("months_to_recover_cog"))
            ef = fnum(r.get("allocation_efficiency"))
            if mo is not None:
                cat_mo_w[c] += mo * a
                cat_mo_den[c] += a
            if ef is not None:
                cat_eff_w[c] += ef * a
                cat_eff_den[c] += a

    # Brand summary (top 20 by allocation)
    b_alloc: dict[str, float] = defaultdict(float)
    b_gp: dict[str, float] = defaultdict(float)
    b_mo_w: dict[str, float] = defaultdict(float)
    b_mo_den: dict[str, float] = defaultdict(float)
    b_ef_w: dict[str, float] = defaultdict(float)
    b_ef_den: dict[str, float] = defaultdict(float)
    for r in rows:
        b = r.get("brand") or ""
        a = fnum(r.get("allocated_cog_usd")) or 0
        b_alloc[b] += a
        b_gp[b] += fnum(r.get("projected_gross_profit_usd")) or 0
        if a >= MEANINGFUL_USD:
            mo = fnum(r.get("cash_recovery_days")) if use_days else fnum(r.get("months_to_recover_cog"))
            ef = fnum(r.get("allocation_efficiency"))
            if mo is not None:
                b_mo_w[b] += mo * a
                b_mo_den[b] += a
            if ef is not None:
                b_ef_w[b] += ef * a
                b_ef_den[b] += a

    top_brands = sorted(b_alloc.keys(), key=lambda x: -b_alloc[x])[:TABLE_TOP_N]

    # Line counts per recovery-speed bucket (buy-plan: cash_cycle_status; else legacy recovery_bucket)
    use_status_buckets = use_days and any((r.get("cash_cycle_status") or "").strip() for r in rows)
    buck_cnt: dict[str, int] = defaultdict(int)
    buck_alloc: dict[str, float] = defaultdict(float)
    for r in rows:
        if use_status_buckets:
            k = (r.get("cash_cycle_status") or "").strip() or "(no status)"
        else:
            k = (r.get("recovery_bucket") or "").strip() or "(none)"
        buck_cnt[k] += 1
        buck_alloc[k] += fnum(r.get("allocated_cog_usd")) or 0

    # Scatter: meaningful, capped axis (days or months)
    scat: list[dict] = []
    for r in meaningful:
        x = fnum(r.get("cash_recovery_days")) if use_days else fnum(r.get("months_to_recover_cog"))
        ef = fnum(r.get("allocation_efficiency"))
        if x is None or ef is None:
            continue
        if use_days and x > SCATTER_MAX_DAYS:
            continue
        if not use_days and x > SCATTER_MAX_MONTHS:
            continue
        scat.append(r)

    out: list[list[Any]] = []
    row = 0

    def append_section(title: str, header: list[Any], data_rows: list[list[Any]]) -> int:
        nonlocal row, out
        start = row
        out.append([title])
        row += 1
        out.append(header)
        row += 1
        out.extend(data_rows)
        row += len(data_rows)
        out.append([])
        row += 1
        return start

    # --- alloc top 20 for table; chart uses first 15
    rec_col = "cash_recovery_days" if use_days else "months_to_recover_cog"
    h1 = [
        "label",
        "brand",
        "category",
        "allocated_cog_usd",
        "projected_revenue_from_allocated_units_usd",
        "projected_gross_profit_usd",
        rec_col,
        "allocation_efficiency",
    ]
    d1 = []
    for r in top_alloc:
        b = r.get("brand", "")
        c = r.get("category", "")
        lab = f"{b[:18]} / {c[:14]}"
        d1.append(
            [
                lab,
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("projected_revenue_from_allocated_units_usd")),
                fnum(r.get("projected_gross_profit_usd")),
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
            ]
        )
    s_alloc = append_section("ALLOC_TOP (sorted by allocated_cog_usd)", h1, d1)
    meta["alloc_header_row"] = s_alloc + 1
    meta["alloc_data_start"] = s_alloc + 2
    meta["alloc_data_end"] = s_alloc + 1 + len(d1)

    h2 = list(h1)
    d2 = []
    for r in top_gp:
        b = r.get("brand", "")
        c = r.get("category", "")
        d2.append(
            [
                f"{b[:18]} / {c[:14]}",
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("projected_revenue_from_allocated_units_usd")),
                fnum(r.get("projected_gross_profit_usd")),
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
            ]
        )
    append_section("GP_TOP (sorted by projected_gross_profit_usd)", h2, d2)

    h3 = list(h1)
    d3 = []
    for r in top_eff:
        b = r.get("brand", "")
        c = r.get("category", "")
        d3.append(
            [
                f"{b[:18]} / {c[:14]}",
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("projected_revenue_from_allocated_units_usd")),
                fnum(r.get("projected_gross_profit_usd")),
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
            ]
        )
    append_section(
        f"EFF_TOP_MEANINGFUL (allocated_cog_usd >= {MEANINGFUL_USD:g})", h3, d3
    )

    h4 = list(h1)
    d4 = []
    for r in worst:
        b = r.get("brand", "")
        c = r.get("category", "")
        d4.append(
            [
                f"{b[:18]} / {c[:14]}",
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("projected_revenue_from_allocated_units_usd")),
                fnum(r.get("projected_gross_profit_usd")),
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
            ]
        )
    append_section(
        f"WORST_RECOVERY_MEANINGFUL (allocated_cog_usd >= {MEANINGFUL_USD:g})", h4, d4
    )

    h_cat = [
        "category",
        "total_allocated_usd",
        "wavg_cash_recovery_days_meaningful" if use_days else "wavg_months_recover_meaningful",
        "wavg_efficiency_meaningful",
        "projected_revenue_usd",
        "projected_gross_profit_usd",
        "row_count",
    ]
    d_cat = []
    for c in sorted(cat_alloc.keys(), key=lambda x: -cat_alloc[x]):
        wa_m = cat_mo_w[c] / cat_mo_den[c] if cat_mo_den[c] > 0 else ""
        wa_e = cat_eff_w[c] / cat_eff_den[c] if cat_eff_den[c] > 0 else ""
        d_cat.append(
            [
                c,
                round(cat_alloc[c], 2),
                round(wa_m, 4) if isinstance(wa_m, float) else wa_m,
                round(wa_e, 4) if isinstance(wa_e, float) else wa_e,
                round(cat_rev[c], 2),
                round(cat_gp[c], 2),
                cat_cnt[c],
            ]
        )
    s_cat = append_section("CATEGORY_SUMMARY", h_cat, d_cat)
    meta["cat_header_row"] = s_cat + 1
    meta["cat_data_start"] = s_cat + 2
    meta["cat_data_end"] = s_cat + 1 + len(d_cat)

    h_br = [
        "brand",
        "total_allocated_usd",
        "projected_gross_profit_usd",
        "wavg_cash_recovery_days_meaningful" if use_days else "wavg_months_recover_meaningful",
        "wavg_efficiency_meaningful",
    ]
    d_br = []
    for b in top_brands:
        wa_m = b_mo_w[b] / b_mo_den[b] if b_mo_den[b] > 0 else ""
        wa_e = b_ef_w[b] / b_ef_den[b] if b_ef_den[b] > 0 else ""
        d_br.append(
            [
                b,
                round(b_alloc[b], 2),
                round(b_gp[b], 2),
                round(wa_m, 4) if isinstance(wa_m, float) else wa_m,
                round(wa_e, 4) if isinstance(wa_e, float) else wa_e,
            ]
        )
    s_br = append_section("BRAND_SUMMARY_TOP20", h_br, d_br)
    meta["brand_header_row"] = s_br + 1
    meta["brand_data_start"] = s_br + 2
    meta["brand_data_end"] = s_br + 1 + len(d_br)

    h_bk = [
        "cash_cycle_status" if use_status_buckets else "recovery_bucket",
        "row_count",
        "total_allocated_usd",
    ]
    keys_bk = list(buck_alloc.keys())

    def _bucket_sort_key(k: str) -> tuple[int, str]:
        if use_status_buckets:
            if k in _CASH_STATUS_BUCKET_ORDER:
                return (_CASH_STATUS_BUCKET_ORDER.index(k), k)
            return (99, k)
        return (-buck_alloc[k], k)

    d_bk = [[k, buck_cnt[k], round(buck_alloc[k], 2)] for k in sorted(keys_bk, key=_bucket_sort_key)]
    bk_title = (
        "LINE_COUNT_BY_CASH_CYCLE_STATUS (SAFE / WARNING / CAPITAL RISK = funded lines)"
        if use_status_buckets
        else "LINE_COUNT_BY_RECOVERY_BUCKET (month-based thresholds from layer2)"
    )
    s_bk = append_section(bk_title, h_bk, d_bk)
    meta["bucket_header_row"] = s_bk + 1
    meta["bucket_data_start"] = s_bk + 2
    meta["bucket_data_end"] = s_bk + 1 + len(d_bk)

    h_sc = [
        "cash_recovery_days" if use_days else "months_to_recover_cog",
        "allocation_efficiency",
        "allocated_cog_usd",
        "brand",
        "category",
    ]
    d_sc = []
    for r in sorted(scat, key=lambda x: -(fnum(x.get("allocated_cog_usd")) or 0))[:80]:
        d_sc.append(
            [
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
                fnum(r.get("allocated_cog_usd")),
                r.get("brand"),
                r.get("category"),
            ]
        )
    scat_sub = (
        f"days<={SCATTER_MAX_DAYS:g}"
        if use_days
        else f"months<={SCATTER_MAX_MONTHS:g}"
    )
    s_sc = append_section(
        f"SCATTER_MEANINGFUL (alloc>={MEANINGFUL_USD:g}, {scat_sub})", h_sc, d_sc
    )
    meta["scatter_header_row"] = s_sc + 1
    meta["scatter_data_start"] = s_sc + 2
    meta["scatter_data_end"] = s_sc + 1 + len(d_sc)

    # Fastest-recovery column chart: meaningful $ rows with a defined recovery metric only (matches dashboard table)
    meaningful_with_recovery = [r for r in meaningful if recovery_metric(r) is not None]
    fr_rows = sorted(
        meaningful_with_recovery,
        key=lambda r: (
            recovery_metric(r) or 1e9,
            -(fnum(r.get("allocated_cog_usd")) or 0),
        ),
    )[:CHART_TOP_N]
    d_fr: list[list[Any]] = []
    for r in fr_rows:
        b = r.get("brand", "")
        c = r.get("category", "")
        d_fr.append(
            [
                f"{b[:18]} / {c[:14]}",
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("projected_revenue_from_allocated_units_usd")),
                fnum(r.get("projected_gross_profit_usd")),
                recovery_metric(r),
                fnum(r.get("allocation_efficiency")),
            ]
        )
    s_fr = append_section(
        f"FAST_RECOVERY_TOP_{CHART_TOP_N}_FOR_CHART (meaningful alloc>={MEANINGFUL_USD:g}, fastest first)",
        list(h1),
        d_fr,
    )
    meta["fast_recovery_header_row"] = s_fr + 1
    meta["fast_recovery_data_start"] = s_fr + 2
    meta["fast_recovery_data_end"] = s_fr + 1 + len(d_fr)

    # Chart helper: top 15 alloc only (narrow range)
    meta["chart_alloc_top"] = top_alloc[:CHART_TOP_N]

    def _velocity_window_days_cell(r: dict) -> float | None:
        return fnum(r.get("velocity_window_days")) or fnum(r.get("velocity_window_days_run"))

    # Brand → category sale velocity (all funded lines, CSV projection fields)
    h_vel = [
        "brand",
        "category",
        "allocated_cog_usd",
        "avg_units_per_day",
        "avg_units_per_week",
        "weeks_to_sell_through",
        "velocity_window_days",
    ]
    vel_sorted = sorted(
        rows,
        key=lambda r: (
            (r.get("brand") or "").strip().lower(),
            (r.get("category") or "").strip().lower(),
        ),
    )
    d_vel = []
    for r in vel_sorted:
        a = fnum(r.get("allocated_cog_usd"))
        if a is None or a <= 0:
            continue
        d_vel.append(
            [
                r.get("brand"),
                r.get("category"),
                round(a, 2),
                fnum(r.get("avg_units_per_day")),
                fnum(r.get("avg_units_per_week")),
                fnum(r.get("weeks_to_sell_through")),
                _velocity_window_days_cell(r),
            ]
        )
    s_vel = append_section(
        "BRAND_CATEGORY_VELOCITY (recent-window units/day & week; weeks to sell this buy)",
        h_vel,
        d_vel,
    )
    meta["velocity_header_row"] = s_vel + 1
    meta["velocity_data_start"] = s_vel + 2
    meta["velocity_data_end"] = s_vel + 1 + len(d_vel)

    h_vel_c = [
        "label",
        "brand",
        "category",
        "allocated_cog_usd",
        "avg_units_per_day",
        "avg_units_per_week",
        "weeks_to_sell_through",
        "velocity_window_days",
    ]
    d_vel_c = []
    for r in sorted(rows, key=sort_key_alloc, reverse=True)[:CHART_TOP_N]:
        b = r.get("brand", "")
        c = r.get("category", "")
        d_vel_c.append(
            [
                f"{b[:16]} / {c[:12]}",
                b,
                c,
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("avg_units_per_day")),
                fnum(r.get("avg_units_per_week")),
                fnum(r.get("weeks_to_sell_through")),
                _velocity_window_days_cell(r),
            ]
        )
    s_vel_c = append_section(
        "VELOCITY_TOP_FOR_CHART (top allocated rows; same projection as bar chart above)",
        h_vel_c,
        d_vel_c,
    )
    meta["vel_chart_header_row"] = s_vel_c + 1
    meta["vel_chart_data_start"] = s_vel_c + 2
    meta["vel_chart_data_end"] = s_vel_c + 1 + len(d_vel_c)

    # Back-stock demand by time (buy-plan CSV columns when present)
    h_bd = [
        "brand",
        "category",
        "allocated_cog_usd",
        "avg_units_per_day",
        "units_needed_7d",
        "units_needed_14d",
        "units_needed_21d",
        "units_from_allocation",
        "days_of_cover",
        "cover_status",
        "cash_recovery_days",
        "cash_cycle_status",
        "max_cog_allowed_usd",
        "capped_by_cash_cycle",
    ]
    d_bd = []
    for r in sorted(rows, key=sort_key_alloc, reverse=True)[:TABLE_TOP_N]:
        if not (r.get("units_needed_7d") or "").strip() and not fnum(r.get("avg_units_per_day")):
            continue
        d_bd.append(
            [
                r.get("brand"),
                r.get("category"),
                fnum(r.get("allocated_cog_usd")),
                fnum(r.get("avg_units_per_day")),
                fnum(r.get("units_needed_7d")),
                fnum(r.get("units_needed_14d")),
                fnum(r.get("units_needed_21d")),
                fnum(r.get("units_from_allocation")),
                fnum(r.get("days_of_cover")),
                r.get("cover_status"),
                fnum(r.get("cash_recovery_days")),
                r.get("cash_cycle_status"),
                fnum(r.get("max_cog_allowed_usd")),
                r.get("capped_by_cash_cycle"),
            ]
        )
    if d_bd:
        append_section("BACK_STOCK_DEMAND_BY_TIME (buy-plan metrics)", h_bd, d_bd)

    # Pie chart reads CATEGORY_SUMMARY cols A–B (set in add_charts); no separate PIE block (avoids truncated ranges).
    meta["pie_data_start"] = meta["cat_data_start"]
    meta["pie_data_end"] = meta["cat_data_end"]

    return out, meta


def _pad_row(cells: list[Any], width: int = DASH_COLS) -> list[Any]:
    r = list(cells)
    while len(r) < width:
        r.append("")
    return r[:width]


def _dash_index_cell(anchor_row_1based: int, dd_block_ref: str, source_col_1based: int) -> str:
    """Single cell on the dashboard tab: pull one value from a fixed ``dashboard_data`` block (no spill here)."""
    return (
        f"=LET(i,ROW()-{anchor_row_1based}+1,src,{dd_block_ref},"
        f'IF(OR(i<1,i>ROWS(src)),"",IFERROR(INDEX(src,i,{source_col_1based}),"")))'
    )


def build_insight_bullets(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[str]:
    """4–6 plain-English bullets from actual CSV data."""
    bullets: list[str] = []
    total = kpis["total_pool"]
    if kpis.get("is_buy_plan"):
        wk = kpis.get("w_avg_weeks")
        wk_s = f"{wk:.1f} weeks" if isinstance(wk, (int, float)) else "n/a"
        bullets.append(
            f"This CSV is a **velocity-driven buy plan** at **brand × category** grain: **{kpis['n_rows']}** funded lines "
            f"concentrate the **${total:,.0f}** pool; weighted sell-through ≈ **{wk_s}** at recent velocity. "
            "**Not** exact SKU purchase instructions — see Notes tab and `docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md`."
        )
    elif abs(total - 18000) < 1:
        bullets.append(f"The full **${total:,.0f}** pool is assigned across {kpis['n_rows']} brand × category lines in this run.")
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    fast = 0.0
    slow = 0.0
    for r in meaningful:
        a = fnum(r.get("allocated_cog_usd")) or 0
        if kpis.get("recovery_uses_days"):
            crd = fnum(r.get("cash_recovery_days"))
            if crd is None:
                continue
            if crd <= 14.0:
                fast += a
            elif crd > 21.0:
                slow += a
        else:
            mo = fnum(r.get("months_to_recover_cog"))
            if mo is None:
                continue
            if mo <= 0.5:
                fast += a
            elif mo > 2.0:
                slow += a
    if total > 0 and meaningful:
        if kpis.get("recovery_uses_days"):
            bullets.append(
                f"About **{100.0 * fast / total:.0f}%** of deployed $ is **SAFE** (cash recovery ≤14 days); "
                f"**{100.0 * slow / total:.0f}%** in **CAPITAL RISK** (>21 days) by dollar weight."
            )
        else:
            bullets.append(
                f"About **{100.0 * fast / total:.0f}%** of the pool sits in rows with payback under ~2 weeks; "
                f"**{100.0 * slow / total:.0f}%** in rows over ~2 months payback (weighted by dollars)."
            )
    # Top category by allocation
    by_cat: dict[str, float] = defaultdict(float)
    for r in rows:
        by_cat[r.get("category") or ""] += fnum(r.get("allocated_cog_usd")) or 0
    if by_cat:
        top_c = max(by_cat, key=lambda k: by_cat[k])
        bullets.append(
            f"**{top_c}** carries the largest share of allocated capital (**${by_cat[top_c]:,.0f}**)."
        )
    if kpis.get("recovery_uses_days"):
        if kpis["slow_dollars"] < 100:
            bullets.append(
                "Almost no deployed dollars sit in **CAPITAL RISK** rows (cash recovery >21 days)."
            )
        else:
            bullets.append(
                f"**${kpis['slow_dollars']:,.0f}** in **CAPITAL RISK** rows (>21 day recovery) — worth a second look."
            )
    elif kpis["slow_dollars"] < 100:
        bullets.append(
            "Almost no dollars sit in **slow-payback** rows (over 4 months); capital is not trapped in this slice."
        )
    else:
        bullets.append(
            f"**${kpis['slow_dollars']:,.0f}** remains in slower rows (>4 mo payback) — worth a second look."
        )
    effs = [fnum(r.get("allocation_efficiency")) for r in meaningful if fnum(r.get("allocation_efficiency"))]
    if len(effs) >= 2:
        spread = max(effs) - min(effs)
        bullets.append(
            f"Revenue per $1 of COG ranges from **{min(effs):.2f}** to **{max(effs):.2f}** among meaningful rows "
            f"(spread **{spread:.2f}**) — large lines can still differ on profit efficiency."
        )
    micro = sum(1 for r in rows if 0 < (fnum(r.get("allocated_cog_usd")) or 0) < MEANINGFUL_USD)
    if micro:
        bullets.append(
            f"**{micro}** tiny-allocation rows (under ${MEANINGFUL_USD:g}) are kept in raw data but **excluded** from "
            "meaningful efficiency rankings on this dashboard."
        )
    return bullets[:6]


def build_action_signals(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[str]:
    """Plain-English decision support."""
    out: list[str] = []
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    # Strong recycler: high alloc + fast recovery (days or months)
    scored: list[tuple[float, dict]] = []
    for r in meaningful:
        a = fnum(r.get("allocated_cog_usd")) or 0
        ef = fnum(r.get("allocation_efficiency"))
        if kpis.get("recovery_uses_days"):
            crd = fnum(r.get("cash_recovery_days"))
            if crd is None or crd <= 0:
                continue
            score = a * (ef or 1.0) / (crd + 1.0)
        else:
            mo = fnum(r.get("months_to_recover_cog"))
            if mo is None or mo <= 0:
                continue
            score = a / (mo + 0.1) * (ef or 1.0)
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    if scored:
        r = scored[0][1]
        if kpis.get("recovery_uses_days"):
            out.append(
                f"**Strong cash cycle:** {r.get('brand')} / {r.get('category')} combines solid allocation with "
                f"fast recovery (~{fnum(r.get('cash_recovery_days')):.1f} days) and healthy revenue per $1 COG."
            )
        else:
            out.append(
                f"**Strong cash cycle:** {r.get('brand')} / {r.get('category')} combines solid allocation with "
                f"fast payback (~{fnum(r.get('months_to_recover_cog')):.2f} mo) and healthy revenue per $1 COG."
            )
    # Margin pressure: high $, lower efficiency
    hi_d = [
        r
        for r in meaningful
        if (fnum(r.get("allocated_cog_usd")) or 0) >= HIGH_DOLLAR_USD
        and fnum(r.get("allocation_efficiency")) is not None
    ]
    if len(hi_d) >= 2:
        hi_d.sort(key=lambda r: fnum(r.get("allocation_efficiency")) or 1e9)
        w = hi_d[0]
        out.append(
            f"**Watch margin efficiency:** {w.get('brand')} / {w.get('category')} is a larger line "
            f"(${fnum(w.get('allocated_cog_usd')):,.0f}) but on the **lower end** of revenue per $1 COG among big rows."
        )
    if kpis.get("recovery_uses_days"):
        if kpis["slow_dollars"] < MEANINGFUL_USD:
            if kpis.get("is_buy_plan"):
                out.append(
                    "**No meaningful capital trap** — negligible dollars in **CAPITAL RISK** (>21 day GP payback)."
                )
            else:
                out.append(
                    "**No meaningful capital trap** — negligible dollars in **CAPITAL RISK** (>21 day recovery)."
                )
        else:
            if kpis.get("is_buy_plan"):
                out.append(
                    f"**Some capital moves slowly:** ${kpis['slow_dollars']:,.0f} with **>21 day** GP-based payback — monitor if that grows."
                )
            else:
                out.append(
                    f"**Some capital moves slowly:** ${kpis['slow_dollars']:,.0f} with cash recovery **>21 days** — monitor if that grows."
                )
    elif kpis["slow_dollars"] < MEANINGFUL_USD:
        out.append("**No meaningful capital trap** in this allocation set — slow-payback dollars are negligible.")
    else:
        out.append(
            f"**Some capital moves slowly:** ${kpis['slow_dollars']:,.0f} tied to payback beyond 4 months — monitor if that grows."
        )
    best_eff = max(meaningful, key=lambda r: fnum(r.get("allocation_efficiency")) or -1, default=None)
    if best_eff and fnum(best_eff.get("allocation_efficiency")):
        out.append(
            f"**Best profit leverage (meaningful $):** {best_eff.get('brand')} / {best_eff.get('category')} "
            f"at **{fnum(best_eff.get('allocation_efficiency')):.2f}** revenue per $1 COG."
        )
    return out[:5]


def build_executive_dashboard_values(
    rows: list[dict[str, str]], kpis: dict[str, Any], dd_meta: dict[str, Any]
) -> tuple[list[list[Any]], dict[str, Any]]:
    """
    Dashboard tab: **fixed-size** INDEX windows into ``dashboard_data`` (no dynamic spill on this tab).
    Filter L1:Q1; KPI column B → ``dashboard_data`` AC (static values from Python).
    """
    layout: dict[str, Any] = {"sections": []}
    L: list[list[Any]] = []
    kcl = str(dd_meta.get("kpi_formula_col_letter", "AC"))
    ksr = int(dd_meta["kpi_formula_start_row"])
    kpi_i = 0

    def push(row: list[Any]) -> int:
        L.append(_pad_row(row))
        return len(L) - 1

    def push18(row: list[Any]) -> int:
        r = list(row)
        while len(r) < 18:
            r.append("")
        L.append(r[:18])
        return len(L) - 1

    def r1(idx0: int) -> int:
        return idx0 + 1

    def add_fixed_ranking_table(title: str, headers: list[str], key: str, prefix: str) -> None:
        d0, d1 = int(dd_meta[f"{prefix}_data_start"]), int(dd_meta[f"{prefix}_data_end"])
        ref = f"'dashboard_data'!$A${r1(d0)}:$H${r1(d1)}"
        cols_1based = (2, 3, 4, 7, 6, 8)
        push([])
        tr = push([title])
        hr = push(headers)
        dr0 = len(L)
        anchor = dr0 + 1
        for _ in range(DASH_RANK_VISIBLE_ROWS):
            push(_pad_row([_dash_index_cell(anchor, ref, c) for c in cols_1based]))
        layout[key] = {
            "title_row": tr,
            "header_row": hr,
            "data_start": dr0,
            "data_end": dr0 + DASH_RANK_VISIBLE_ROWS,
        }

    def add_fixed_category_table(title: str, headers: list[str]) -> None:
        c0, c1 = int(dd_meta["cat_data_start"]), int(dd_meta["cat_data_end"])
        ref = f"'dashboard_data'!$A${r1(c0)}:$G${r1(c1)}"
        push([])
        tr = push([title])
        hr = push(headers)
        dr0 = len(L)
        anchor = dr0 + 1
        for _ in range(DASH_CATEGORY_VISIBLE_ROWS):
            push(_pad_row([_dash_index_cell(anchor, ref, j) for j in range(1, 7)]))
        layout["category"] = {
            "title_row": tr,
            "header_row": hr,
            "data_start": dr0,
            "data_end": dr0 + DASH_CATEGORY_VISIBLE_ROWS,
        }

    def add_fixed_velocity_table(title: str, headers: list[str]) -> None:
        v0, v1 = int(dd_meta["velocity_data_start"]), int(dd_meta["velocity_data_end"])
        ref = f"'dashboard_data'!$A${r1(v0)}:$G${r1(v1)}"
        push([])
        tr = push([title])
        hr = push(headers)
        dr0 = len(L)
        anchor = dr0 + 1
        for _ in range(DASH_VELOCITY_VISIBLE_ROWS):
            push(_pad_row([_dash_index_cell(anchor, ref, j) for j in range(1, 8)]))
        layout["velocity"] = {
            "title_row": tr,
            "header_row": hr,
            "data_start": dr0,
            "data_end": dr0 + DASH_VELOCITY_VISIBLE_ROWS,
        }

    row0 = [""] * 18
    row0[0] = "Projection Dashboard — Executive Summary"
    row0[10] = ""
    row0[11] = "Mode"
    row0[12] = "None"
    row0[13] = "Value"
    row0[14] = ""
    row0[15] = "Active"
    row0[16] = (
        '=IF(OR(TRIM($M$1)="",LOWER(TRIM($M$1))="none",TRIM($O$1)=""),'
        '"None","Excluding: "&TRIM($O$1))'
    )
    push18(row0)
    layout["title_row"] = 0

    sub = (
        "$18K velocity buy plan · brand×category grain · not SKU POs · units · weeks · payback · profit"
        if kpis.get("is_buy_plan")
        else "$18K capital plan · where money goes · payback · profit · what to do"
    )
    push18([sub] + [""] * 17)
    push18([""] * 18)
    layout["subtitle_row"] = 1

    layout["kpi_banner_row"] = push(
        [
            "KPI snapshot — at a glance (full CSV run via Python; tables & ledger still follow L1:Q1 filter)"
        ]
    )

    kpi_defs: list[tuple[str, Any, str]] = [
        ("Total allocation pool", kpis["total_pool"], "money"),
        ("Total projected revenue", kpis["total_rev"], "money"),
        ("Total projected gross profit", kpis["total_gp"], "money"),
    ]
    if kpis.get("is_buy_plan"):
        kpi_defs.append(
            (
                "Total units to purchase (funded rows)",
                round(kpis["total_units_buy"], 2) if kpis.get("total_units_buy") is not None else "",
                "num",
            )
        )
        kpi_defs.append(
            (
                "Weighted avg weeks to sell through",
                round(kpis["w_avg_weeks"], 2) if kpis.get("w_avg_weeks") is not None else "",
                "wk",
            )
        )
    if kpis.get("recovery_uses_days"):
        kpi_defs.extend(
            [
                (
                    "Average cash recovery time (weighted by $)",
                    round(kpis["w_avg_cash_days"], 2) if kpis.get("w_avg_cash_days") else "",
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
        kpi_defs.extend(
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
    layout["kpi_rows"] = []
    layout["kpi_kind_by_row"] = []
    for lab, _val, kind in kpi_defs:
        kr = ksr + kpi_i
        kpi_i += 1
        layout["kpi_rows"].append(
            push([lab, f"='dashboard_data'!{kcl}{kr}", "", "", "", "", "", "", "", ""])
        )
        layout["kpi_kind_by_row"].append(kind)

    push([])
    push(["What This Dashboard Says"])
    layout["insight_banner"] = len(L) - 1
    layout["insight_rows"] = []
    layout["insight_rows"].append(
        push(
            [
                "• Filter scope: KPI numbers/text in column B (dashboard_data AC) are the full CSV snapshot from "
                "the push script, not the active filter. Ranking tables, category performance, deployment ledger, "
                "sale velocity, and chart data follow the L1:Q1 exclusion filter (filtered_layer2). "
                "Deployment ledger is a flat sorted list—no repeated brand subtotal rows.",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    )
    layout["insight_rows"].append(
        push(
            [
                "• What This Dashboard Says and Action Signals are generated from the full CSV when you run "
                "the push script—they describe the complete export, not the filtered subset. "
                "Re-run the script after a new CSV to refresh that narrative.",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    )
    for b in build_insight_bullets(rows, kpis):
        layout["insight_rows"].append(push(["• " + b.replace("**", ""), "", "", "", "", "", "", "", "", ""]))

    push([])
    push(["Action Signals"])
    layout["action_banner"] = len(L) - 1
    layout["action_rows"] = []
    for s in build_action_signals(rows, kpis):
        layout["action_rows"].append(push(["• " + s.replace("**", ""), "", "", "", "", "", "", "", "", ""]))

    rec_uses_d = bool(kpis.get("recovery_uses_days"))
    payback_hdr = (
        "COG payback via gross profit (days)"
        if rec_uses_d
        else "Payback (months)"
    )
    big_h = ["Brand", "Category", "Allocated COG", payback_hdr, "Projected gross profit", "Revenue per $1 of COG"]

    add_fixed_ranking_table("Biggest allocation rows", big_h, "biggest", "alloc")
    add_fixed_ranking_table(
        f"Fastest cash recovery (Allocated COG ≥ ${MEANINGFUL_USD:g}; rows with payback data only)",
        big_h,
        "fastest",
        "fast_recovery",
    )
    add_fixed_ranking_table("Highest projected gross profit (meaningful $)", big_h, "highest_gp", "gp")
    add_fixed_ranking_table(
        f"High-dollar rows with weaker efficiency (Allocated COG ≥ ${HIGH_DOLLAR_USD:g})",
        big_h,
        "weak_eff",
        "weak_margin",
    )

    ch = [
        "Category",
        "Total allocation",
        (
            "Avg COG payback via GP (days)"
            if rec_uses_d
            else "Avg payback (mo)"
        ),
        "Avg revenue per $1 COG",
        "Projected revenue",
        "Projected gross profit",
    ]
    add_fixed_category_table(
        "Category performance (payback & efficiency use rows with Allocated COG ≥ "
        f"${MEANINGFUL_USD:g} only)".replace("${MEANINGFUL_USD:g}", f"{MEANINGFUL_USD:g}"),
        ch,
    )

    push([])
    st = push(
        [
            "Detail — full deployment ledger (filtered view · sorted by brand then $ · no per-brand subtotal rows)"
        ]
    )
    push([])
    sh = push(["Brand", "Category", "Pool spend (Allocated COG)"])
    s0, s1 = dd_meta["spend_ledger_data_start"], dd_meta["spend_ledger_data_end"]
    spend_ref = f"'dashboard_data'!$A${r1(s0)}:$C${r1(s1)}"
    layout["spend_title_row"] = st
    layout["spend_header_row"] = sh
    layout["spend_data_start"] = len(L)
    spend_anchor = layout["spend_data_start"] + 1
    for _ in range(DASH_LEDGER_VISIBLE_ROWS):
        push(
            _pad_row(
                [
                    _dash_index_cell(spend_anchor, spend_ref, 1),
                    _dash_index_cell(spend_anchor, spend_ref, 2),
                    _dash_index_cell(spend_anchor, spend_ref, 3),
                ]
            )
        )
    layout["spend_data_end"] = layout["spend_data_start"] + DASH_LEDGER_VISIBLE_ROWS

    vh = [
        "Brand",
        "Category",
        "Avg units / day",
        "Avg units / week",
        "Weeks to sell this buy",
        "Velocity window (days)",
        "Allocated COG",
    ]
    add_fixed_velocity_table(
        "Sale velocity by brand × category (projection window from CSV; units/day & week from trailing sales)",
        vh,
    )

    layout["last_row"] = len(L)
    return L, layout


def build_spend_plan_rows(rows: list[dict[str, str]]) -> list[list[Any]]:
    """
    Plain-language deployment table: every brand × category row from the CSV plus
    a subtotal after each brand and a final pool total.
    """
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


def build_notes(
    csv_path: Path,
    pool_ok: bool,
    pool_sum: float,
    *,
    expected_pool_usd: float,
    unallocated_usd: float,
    allocation_mode: str,
) -> list[list[str]]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows: list[list[str]] = [
        ["Projection capital dashboard — notes"],
        [""],
        ["Data source", str(csv_path.resolve())],
        ["Run date (UTC)", today],
        ["Window end date", "See Summary tab / regenerate from build_projection_by_category_brand.py"],
        [
            "Exclusions (dashboard L1:Q1)",
            "M1=None: show all lines. Brand or Category: O1 lists names to exclude; use | between multiple "
            "(e.g. BrandA|BrandB). Brand+Category: exclude pairs; separate pairs with || (double pipe). "
            "Pool display only: enter a number in S1 (row 1) to override the Total allocation pool KPI in "
            "dashboard_data column AC; leave blank for CSV total. This does not change raw_layer2 dollars.",
        ],
        [
            "Meaningful filter",
            f"Rankings and weighted category/brand averages for recovery & efficiency use allocated_cog_usd >= {MEANINGFUL_USD:g} where noted.",
        ],
        [
            "Buy plan CSV",
            "If allocation_mode=buy-plan: velocity uses velocity_window_days per row; see avg_units_per_week, weeks_to_sell_through, planner_score. "
            "Column unit_model_note states the 1-line-1-unit assumption until schema validates qty.",
        ],
        [
            "Planner metadata columns",
            "Each layer2 row repeats: allocation_mode, velocity_window_days_run, grouping_level (brand_category), "
            "schema_validated (false until SDL/playground), schema_source, unit_model_note (1 line = 1 unit until validated).",
        ],
        [
            "Buy plan honesty",
            "Velocity-grounded, approximate at brand×category grain — not exact SKU purchase orders. "
            "See markdown Planning metadata and docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md.",
        ],
    ]
    rows.extend(dashboard_notes_transfer_cost_rows(csv_path))
    rows.extend(
        [
            [
                "Schema truth",
                "Production Retail blocks introspection; do not assume find* field shapes — see docs/GROWFLOW_RETAIL_SCHEMA_MAP.md and docs/GROWFLOW_NEXT_DATA_REQUEST.md.",
            ],
            [
                "Scatter filter",
                (
                    f"Scatter: buy-plan uses cash_recovery_days (capped at {SCATTER_MAX_DAYS:g}); "
                    f"other modes use months_to_recover_cog (cap {SCATTER_MAX_MONTHS:g})."
                ),
            ],
            [
                "Validation",
                (
                    f"buy-plan: deployed ${pool_sum:,.2f} + unused ${unallocated_usd:,.2f} "
                    f"= ${pool_sum + unallocated_usd:,.2f} vs budget ${expected_pool_usd:,.2f} — "
                    f"{'PASS' if pool_ok else 'CHECK'}"
                    if allocation_mode == "buy-plan"
                    else f"Sum allocated_cog_usd = ${pool_sum:,.2f} (expected ${expected_pool_usd:,.2f}) — "
                    f"{'PASS' if pool_ok else 'CHECK'}"
                ),
            ],
            [""],
            [
                "Chart / layout reset (one-time)",
                "Default is --dashboard-mode refresh: data tabs + ledger; updateChartSpec on dashboard charts "
                "(unless --no-patch-chart-sources). For a full dashboard tab rewrite: --dashboard-mode rebuild. "
                "For raw_layer2 reformat: --full-refresh and --confirm-layout-reset.",
            ],
            [
                "L1:Q1 filter vs narrative",
                "Executive KPIs on dashboard_data column AC are static values from Python (full CSV). Tables, "
                "deployment ledger, velocity, and chart helpers follow the active filter (filtered_layer2). "
                "What This Dashboard Says + Action Signals are static text from the full CSV at push time.",
            ],
            [
                "Deployment ledger",
                "On dashboard_data: DEPLOYMENT_LEDGER_SORTED—filtered rows only, sorted by brand then $, "
                "no per-brand subtotal lines (flat three-column list).",
            ],
            ["Emphasis", "Capital deployment: where $ sits, payback, GP, efficiency — not a generic sales dashboard."],
            ["Raw layer2", "All CSV rows preserved; charts use dashboard_data helpers."],
            [
                "Dashboard tab layout",
                "Filter controls (L1:Q1) → KPI snapshot → What This Dashboard Says → Action Signals → ranking tables → "
                "category → deployment ledger → sale velocity. Charts anchor column J.",
            ],
            [
                "Charts",
                "Plain-English titles; sources are dashboard_data. BAR/COMBO use ALLOC_TOP (by $). "
                f"Fastest-payback column uses FAST_RECOVERY_TOP_{CHART_TOP_N}_FOR_CHART (meaningful $ + recovery present; "
                "same sort as Fastest table). Pie uses CATEGORY_SUMMARY columns A–B (same rows as category table). "
                "Velocity combo uses VELOCITY_TOP_FOR_CHART. In refresh mode, updateChartSpec rewires ranges without "
                "moving charts (--no-patch-chart-sources to skip). Rebuild mode recreates charts. "
                "Optional --bounded-clear limits clears on data tabs.",
            ],
            [
                "Exclusion filter",
                "Dashboard L1:Q1 — Mode M1 (None / Brand / Category / Brand+Category), value O1 from "
                "dashboard_data AB column (spill row matches FILTER_HELPERS_ROW_1BASED in code). "
                "filtered_layer2 spills from dashboard_data A2500 (FILTER on raw_layer2). "
                "KPI snapshot (AC) is computed in Python from the full CSV; filtered tables follow the filter. "
                "Insight/action narrative is written from the full CSV when you run the push script.",
            ],
            [
                "Velocity tables",
                "BRAND_CATEGORY_VELOCITY on dashboard_data (near sheet end) and Sale velocity on dashboard tab "
                "(after deployment ledger): brand→category sort; avg_units_per_day, avg_units_per_week, "
                "weeks_to_sell_through from projection CSV (buy-plan window).",
            ],
        ]
    )
    return rows


def count_conditional_format_rules(
    service: Any, spreadsheet_id: str, sheet_id: int
) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId),conditionalFormats)",
    ).execute()
    for sh in meta.get("sheets", []):
        if sh.get("properties", {}).get("sheetId") != sheet_id:
            continue
        return len(sh.get("conditionalFormats") or [])
    return 0


def delete_conditional_format_rule_requests(
    sheet_id: int, n_rules: int
) -> list[dict[str, Any]]:
    return [
        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
        for i in range(n_rules - 1, -1, -1)
    ]


def batch_format_raw_layer2(
    spreadsheet_id: str, sheet_id: int, n_rows: int, n_cols: int
) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, 0, 1, 0, n_cols),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HDR,
                        "textFormat": {"bold": True, "foregroundColor": HDR_FG},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        }
    )
    reqs.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )
    if n_rows > 1:
        # First: projected_gross_profit_usd < 0 (not a gain) — wins before GP gradient
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, 1, n_rows, 14, 15)],
                        "booleanRule": {
                            "condition": {
                                "type": "NUMBER_LESS",
                                "values": [{"userEnteredValue": "0"}],
                            },
                            "format": {
                                "backgroundColor": {"red": 0.75, "green": 0.75, "blue": 0.78},
                                "textFormat": {"foregroundColor": {"red": 0.4, "green": 0.1, "blue": 0.1}},
                            },
                        },
                    },
                    "index": 0,
                }
            }
        )
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, 1, n_rows, 10, 11)],
                        "booleanRule": {
                            "condition": {
                                "type": "NUMBER_GREATER",
                                "values": [{"userEnteredValue": "4"}],
                            },
                            "format": {
                                "backgroundColor": {"red": 1.0, "green": 0.85, "blue": 0.8}
                            },
                        },
                    },
                    "index": 1,
                }
            }
        )
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, 1, n_rows, 14, 15)],
                        "gradientRule": {
                            "minpoint": {
                                "color": {"red": 0.85, "green": 0.2, "blue": 0.2},
                                "type": "MIN",
                            },
                            "midpoint": {
                                "color": {"red": 1, "green": 0.9, "blue": 0.4},
                                "type": "PERCENTILE",
                                "value": "50",
                            },
                            "maxpoint": {
                                "color": {"red": 0.2, "green": 0.6, "blue": 0.3},
                                "type": "MAX",
                            },
                        },
                    },
                    "index": 2,
                }
            }
        )
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, 1, n_rows, 15, 16)],
                        "gradientRule": {
                            "minpoint": {
                                "color": {"red": 0.9, "green": 0.5, "blue": 0.5},
                                "type": "MIN",
                            },
                            "maxpoint": {
                                "color": {"red": 0.3, "green": 0.5, "blue": 0.85},
                                "type": "MAX",
                            },
                        },
                    },
                    "index": 3,
                }
            }
        )
    reqs.append(
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": n_cols,
                }
            }
        }
    )
    return reqs


def batch_format_executive_dashboard(sheet_id: int, layout: dict[str, Any]) -> list[dict[str, Any]]:
    """Executive dashboard: merges, section bars, KPI emphasis, tables, ledger."""
    reqs: list[dict[str, Any]] = []
    last = max(120, int(layout.get("last_row", 80)) + 5)
    reqs.append({"unmergeCells": {"range": grid_range(sheet_id, 0, last, 0, 12)}})

    def merge_section_row(r: int) -> None:
        reqs.append(
            {
                "mergeCells": {
                    "range": grid_range(sheet_id, r, r + 1, 0, DASH_COLS),
                    "mergeType": "MERGE_ALL",
                }
            }
        )

    def style_section_row(r: int) -> None:
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, r, r + 1, 0, DASH_COLS),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": SECTION_BAR_FG,
                                "fontSize": 11,
                            },
                            "backgroundColor": SECTION_BAR,
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment)",
                }
            }
        )

    merge_section_row(layout["title_row"])
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, layout["title_row"], layout["title_row"] + 1, 0, DASH_COLS),
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": True,
                            "fontSize": 18,
                            "foregroundColor": BANNER_FG,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "backgroundColor": SUBHDR,
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment,backgroundColor)",
            }
        }
    )
    merge_section_row(layout["subtitle_row"])
    reqs.append(
        {
            "repeatCell": {
                "range": grid_range(sheet_id, layout["subtitle_row"], layout["subtitle_row"] + 1, 0, DASH_COLS),
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
    merge_section_row(layout["kpi_banner_row"])
    style_section_row(layout["kpi_banner_row"])
    for ri in layout.get("kpi_rows", []):
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, ri, ri + 1, 0, 1),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 10},
                        }
                    },
                    "fields": "userEnteredFormat.textFormat",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, ri, ri + 1, 1, 2),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 12},
                            "horizontalAlignment": "LEFT",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
                }
            }
        )
    for key in ("insight_banner", "action_banner"):
        r = layout.get(key)
        if r is not None:
            merge_section_row(r)
            style_section_row(r)
    for key in ("insight_rows", "action_rows"):
        for ri in layout.get(key, []):
            merge_section_row(ri)
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, ri, ri + 1, 0, DASH_COLS),
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

    def format_ranking_table(block: dict[str, Any]) -> None:
        tr, hr, d0, d1 = block["title_row"], block["header_row"], block["data_start"], block["data_end"]
        ncols = 6
        merge_section_row(tr)
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, tr, tr + 1, 0, DASH_COLS),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "fontSize": 11,
                                "foregroundColor": BANNER_FG,
                            },
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, hr, hr + 1, 0, ncols),
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
        if d1 > d0:
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, 0, ncols),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"fontSize": 9},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,verticalAlignment)",
                    }
                }
            )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, 2, 3),
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
                        "range": grid_range(sheet_id, d0, d1, 3, 4),
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
                        "range": grid_range(sheet_id, d0, d1, 4, 5),
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
                        "range": grid_range(sheet_id, d0, d1, 5, 6),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    for name in ("biggest", "fastest", "highest_gp", "weak_eff"):
        b = layout.get(name)
        if b:
            format_ranking_table(b)

    def format_velocity_table(block: dict[str, Any]) -> None:
        tr, hr, d0, d1 = block["title_row"], block["header_row"], block["data_start"], block["data_end"]
        merge_section_row(tr)
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, tr, tr + 1, 0, DASH_COLS),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "fontSize": 11,
                                "foregroundColor": BANNER_FG,
                            },
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, hr, hr + 1, 0, 7),
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
        if d1 > d0:
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, 0, 7),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"fontSize": 9},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,verticalAlignment)",
                    }
                }
            )
            for c0, c1, pat in (
                (2, 3, "0.00"),
                (3, 4, "0.00"),
                (4, 5, "0.00"),
                (5, 6, "0"),
            ):
                reqs.append(
                    {
                        "repeatCell": {
                            "range": grid_range(sheet_id, d0, d1, c0, c1),
                            "cell": {
                                "userEnteredFormat": {
                                    "numberFormat": {"type": "NUMBER", "pattern": pat},
                                }
                            },
                            "fields": "userEnteredFormat.numberFormat",
                        }
                    }
                )
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, 6, 7),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    vel_b = layout.get("velocity")
    if vel_b:
        format_velocity_table(vel_b)

    cat_b = layout.get("category")
    if cat_b:
        tr, hr, d0, d1 = cat_b["title_row"], cat_b["header_row"], cat_b["data_start"], cat_b["data_end"]
        merge_section_row(tr)
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, tr, tr + 1, 0, DASH_COLS),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "fontSize": 11,
                                "foregroundColor": BANNER_FG,
                            },
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, hr, hr + 1, 0, 6),
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
        if d1 > d0:
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, d0, d1, 0, 6),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"fontSize": 9},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,verticalAlignment)",
                    }
                }
            )
            for c0, c1 in ((1, 2), (4, 5), (5, 6)):
                reqs.append(
                    {
                        "repeatCell": {
                            "range": grid_range(sheet_id, d0, d1, c0, c1),
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
                        "range": grid_range(sheet_id, d0, d1, 2, 4),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "0.000"},
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    st = layout.get("spend_title_row")
    sh = layout.get("spend_header_row")
    sd0, sd1 = layout.get("spend_data_start"), layout.get("spend_data_end")
    if st is not None:
        merge_section_row(st)
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, st, st + 1, 0, DASH_COLS),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "fontSize": 11,
                                "foregroundColor": BANNER_FG,
                            },
                            "backgroundColor": SUBHDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
    if sh is not None and sd0 is not None and sd1 and sd1 > sd0:
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, sh, sh + 1, 0, 3),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": HDR_FG},
                            "backgroundColor": HDR,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            }
        )
        reqs.append(
            {
                "repeatCell": {
                    "range": grid_range(sheet_id, sd0, sd1, 2, 3),
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
                    "range": grid_range(sheet_id, sd0, sd1, 0, 3),
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 9},
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,verticalAlignment)",
                }
            }
        )
    kinds = layout.get("kpi_kind_by_row") or []
    for i, ri in enumerate(layout.get("kpi_rows", [])):
        kind = kinds[i] if i < len(kinds) else "text"
        if kind == "money":
            reqs.append(
                {
                    "repeatCell": {
                        "range": grid_range(sheet_id, ri, ri + 1, 1, 2),
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
                        "range": grid_range(sheet_id, ri, ri + 1, 1, 2),
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
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 0,
                        "frozenColumnCount": 0,
                        "hideGridlines": False,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount,gridProperties.hideGridlines",
            }
        }
    )
    reqs.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 230},
                "fields": "pixelSize",
            }
        }
    )
    reqs.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 1,
                    "endIndex": 2,
                },
                "properties": {"pixelSize": 340},
                "fields": "pixelSize",
            }
        }
    )
    return reqs


def dashboard_table_conditional_formats(sheet_id: int, layout: dict[str, Any]) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    idx = 0
    for name in ("biggest", "fastest", "highest_gp", "weak_eff"):
        b = layout.get(name)
        if not b or b["data_end"] <= b["data_start"]:
            continue
        d0, d1 = b["data_start"], b["data_end"]
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, d0, d1, 3, 4)],
                        "gradientRule": {
                            "minpoint": {
                                "color": {"red": 0.2, "green": 0.62, "blue": 0.38},
                                "type": "MIN",
                            },
                            "maxpoint": {
                                "color": {"red": 0.95, "green": 0.52, "blue": 0.32},
                                "type": "MAX",
                            },
                        },
                    },
                    "index": idx,
                }
            }
        )
        idx += 1
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, d0, d1, 5, 6)],
                        "gradientRule": {
                            "minpoint": {
                                "color": {"red": 0.88, "green": 0.42, "blue": 0.42},
                                "type": "MIN",
                            },
                            "maxpoint": {
                                "color": {"red": 0.28, "green": 0.52, "blue": 0.42},
                                "type": "MAX",
                            },
                        },
                    },
                    "index": idx,
                }
            }
        )
        idx += 1
    cat = layout.get("category")
    if cat and cat["data_end"] > cat["data_start"]:
        cd0, cd1 = cat["data_start"], cat["data_end"]
        reqs.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [grid_range(sheet_id, cd0, cd1, 3, 4)],
                        "gradientRule": {
                            "minpoint": {
                                "color": {"red": 0.88, "green": 0.42, "blue": 0.42},
                                "type": "MIN",
                            },
                            "maxpoint": {
                                "color": {"red": 0.28, "green": 0.52, "blue": 0.42},
                                "type": "MAX",
                            },
                        },
                    },
                    "index": idx,
                }
            }
        )
        idx += 1
    return reqs


def _dashboard_chart_layout_rows(layout: dict[str, Any] | None) -> dict[str, int]:
    """0-based row anchors for overlay charts (aligned with build_executive_dashboard_values)."""
    if not layout:
        return {
            "top": 3,
            "combo": 24,
            "fast_col": 50,
            "scatter": 74,
            "bottom_pair": 120,
            "velocity": 162,
        }
    kb = int(layout.get("kpi_banner_row", 3))
    big = layout.get("biggest") or {}
    weak = layout.get("weak_eff") or {}
    cat = layout.get("category") or {}
    vel = layout.get("velocity") or {}
    spend_ds = int(layout.get("spend_data_start", kb + 95))
    vtr = int(vel.get("title_row", spend_ds + 18))
    return {
        "top": kb,
        "combo": int(big.get("title_row", kb + 18)),
        "fast_col": int(weak.get("title_row", kb + 52)),
        "scatter": int(cat.get("title_row", kb + 72)),
        "bottom_pair": min(spend_ds + 2, max(vtr - 4, kb + 85)),
        "velocity": vtr,
    }


def add_charts(
    dd_id: int,
    dash_id: int,
    meta: dict[str, Any],
    dash_layout: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Charts read dashboard_data; positions match dashboard screenshot (donut | brand | tall bars on top row)."""
    reqs: list[dict[str, Any]] = []
    axis_days = bool(meta.get("recovery_axis_days"))
    p = _chart_range_params(dd_id, meta)
    ad0, ad1 = p.ad0, p.ad1
    fr0, fr1 = p.fr0, p.fr1
    c0, c1 = p.c0, p.c1
    pie_ex = p.pie_row_excl
    v0, v1 = p.v0, p.v1
    s0, s1 = p.s0, p.s1
    b0, b1 = p.b0, p.b1
    br0, br1 = p.br0, p.br1
    pool_amt = meta.get("total_pool_alloc_usd")
    pool_phrase = (
        f"${float(pool_amt):,.0f}" if isinstance(pool_amt, (int, float)) else "the pool"
    )
    payback_axis_lbl = "Cash recovery (days)" if axis_days else "Payback (months)"
    cr = _dashboard_chart_layout_rows(dash_layout)

    def chart_pos(row: int, col: int, w: int, h: int) -> dict[str, Any]:
        return {
            "overlayPosition": {
                "anchorCell": {"sheetId": dash_id, "rowIndex": row, "columnIndex": col},
                "offsetXPixels": 0,
                "offsetYPixels": 0,
                "widthPixels": w,
                "heightPixels": h,
            }
        }

    # --- 1) Donut (top row, left of brand / biggest) ---
    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title="How the pool splits across product categories",
                            subtitle=(
                                "Each slice = one CATEGORY_SUMMARY row · "
                                "Legend on the right; thin slices can be hard to read"
                            ),
                            alt_text=(
                                "Donut chart of total allocated cost of goods by product category; "
                                "data from category summary table."
                            ),
                        ),
                        "pieChart": {
                            "legendPosition": "RIGHT_LEGEND",
                            "domain": {
                                "sourceRange": source_range(dd_id, c0, pie_ex, 0, 1)
                            },
                            "series": {
                                "sourceRange": source_range(dd_id, c0, pie_ex, 1, 2)
                            },
                            "pieHole": 0.52,
                            "threeDimensional": False,
                        },
                    },
                    "position": chart_pos(cr["top"], 4, 405, 315),
                }
            }
        }
    )

    # --- 2) Brand share (top row, center) ---
    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title="Which brands hold the most allocated dollars?",
                            subtitle=(
                                "Bars = sum of allocated COG across categories per brand · "
                                "Matches BRAND_SUMMARY_TOP20 on dashboard_data"
                            ),
                            alt_text="Horizontal bar chart of total allocated cost of goods by brand.",
                        ),
                        "basicChart": {
                            "chartType": "BAR",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "LEFT_AXIS", "title": "Brand"},
                                {"position": "BOTTOM_AXIS", "title": "Total allocated COG ($)"},
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, br0, br1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, br0, br1, 1, 2)
                                    },
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
                    "position": chart_pos(cr["top"], 8, 500, 310),
                }
            }
        }
    )

    # --- 3) Biggest allocation rows — tall bar chart (far right) ---
    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title=f"Where {pool_phrase} is going — biggest allocation rows",
                            subtitle=(
                                "Horizontal bars: allocated COG per brand × category · "
                                "Sorted by dollars (matches Biggest allocation table)"
                            ),
                            alt_text=(
                                f"Horizontal bar chart of top {CHART_TOP_N} allocation lines by allocated COG in dollars."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "BAR",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {
                                    "position": "LEFT_AXIS",
                                    "title": "Brand × category line",
                                },
                                {
                                    "position": "BOTTOM_AXIS",
                                    "title": "Allocated COG (USD)",
                                },
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, ad0, ad1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, ad0, ad1, 3, 4)
                                    },
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
                    "position": chart_pos(cr["top"], 13, 600, 720),
                }
            }
        }
    )

    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title="Dollars deployed vs projected gross profit",
                            subtitle=(
                                "Blue columns = allocated COG (left scale) · "
                                "Copper line = projected gross profit (right scale) · Same top-by-$ lines"
                            ),
                            alt_text=(
                                "Combo chart: columns show allocated cost of goods, line shows projected gross profit."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "COMBO",
                            "legendPosition": "BOTTOM_LEGEND",
                            "compareMode": "CATEGORY",
                            "interpolateNulls": True,
                            "axis": [
                                {
                                    "position": "BOTTOM_AXIS",
                                    "title": "Brand × category line",
                                },
                                {
                                    "position": "LEFT_AXIS",
                                    "title": "Allocated COG ($)",
                                },
                                {
                                    "position": "RIGHT_AXIS",
                                    "title": "Projected gross profit ($)",
                                },
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, ad0, ad1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, ad0, ad1, 3, 4)
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                    "type": "COLUMN",
                                    "color": SERIES_PRIMARY,
                                },
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, ad0, ad1, 5, 6)
                                    },
                                    "targetAxis": "RIGHT_AXIS",
                                    "type": "LINE",
                                    "color": SERIES_SECONDARY,
                                    "lineStyle": {"width": 2, "type": "SOLID"},
                                },
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": chart_pos(cr["combo"], 7, 608, 330),
                }
            }
        }
    )

    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title=(
                                f"Fastest cash recovery — payback time ({'days' if axis_days else 'months'})"
                            ),
                            subtitle=(
                                "Lower is faster · Same rows as Fastest cash recovery table above"
                            ),
                            alt_text=(
                                f"Column chart of {payback_axis_lbl} for the fastest-recovering meaningful allocation lines."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {
                                    "position": "BOTTOM_AXIS",
                                    "title": "Line (brand / category)",
                                },
                                {
                                    "position": "LEFT_AXIS",
                                    "title": payback_axis_lbl,
                                },
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, fr0, fr1, 0, 1)
                                    }
                                }
                            ],
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
                    "position": chart_pos(cr["fast_col"], 7, 592, 300),
                }
            }
        }
    )

    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title="Efficiency vs speed — revenue leverage against payback",
                            subtitle=(
                                f"Each point = funded line (alloc ≥ {MEANINGFUL_USD:g}) · "
                                "Right / high = more revenue per $1 COG · "
                                + (
                                    f"X capped at {SCATTER_MAX_DAYS:g} days"
                                    if axis_days
                                    else f"X capped at {SCATTER_MAX_MONTHS:g} months"
                                )
                            ),
                            alt_text=(
                                "Scatter plot of payback or recovery time versus allocation efficiency."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "SCATTER",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "DATUM",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": payback_axis_lbl},
                                {
                                    "position": "LEFT_AXIS",
                                    "title": "Revenue per $1 COG (allocation efficiency)",
                                },
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, s0, s1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, s0, s1, 1, 2)
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                    "color": SERIES_PRIMARY,
                                    "pointStyle": {"size": 7, "shape": "CIRCLE"},
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": chart_pos(cr["scatter"], 10, 512, 308),
                }
            }
        }
    )

    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title=(
                                "Line count by cash-cycle bucket (SAFE / WARNING / CAPITAL RISK)"
                                if axis_days
                                else "How many lines sit in each recovery-speed bucket?"
                            ),
                            subtitle=(
                                "Column height = number of funded brand×category lines in each bucket · "
                                "Not dollars — see adjacent column on dashboard_data for $ by bucket"
                                if axis_days
                                else "Medium / Moderate / Slow — line counts from recovery_bucket on projection CSV"
                            ),
                            alt_text="Column chart of how many allocation lines fall in each recovery bucket.",
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Bucket"},
                                {"position": "LEFT_AXIS", "title": "Number of lines"},
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, b0, b1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, b0, b1, 1, 2)
                                    },
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
                    "position": chart_pos(cr["bottom_pair"], 7, 508, 292),
                }
            }
        }
    )

    cat_rec_title = (
        "Recovery speed by category (avg cash recovery, meaningful $ only)"
        if axis_days
        else "Recovery speed by category (avg payback, meaningful $ only)"
    )
    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title=cat_rec_title,
                            subtitle=(
                                "Each column = category · Height = $-weighted average from rows with "
                                f"allocated COG ≥ {MEANINGFUL_USD:g} · Same weights as Category performance table"
                            ),
                            alt_text=(
                                "Column chart of weighted average recovery or payback time by product category."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "NO_LEGEND",
                            "compareMode": "CATEGORY",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Category"},
                                {"position": "LEFT_AXIS", "title": payback_axis_lbl},
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, c0, pie_ex, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, c0, pie_ex, 2, 3)
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                    "color": SERIES_PRIMARY,
                                }
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": chart_pos(cr["bottom_pair"], 12, 548, 292),
                }
            }
        }
    )

    reqs.append(
        {
            "addChart": {
                "chart": {
                    "spec": {
                        **_chart_visual_envelope(
                            title="Velocity profile — biggest buys vs recent sell-through",
                            subtitle=(
                                "Teal columns = trailing avg units/day (velocity window) · "
                                "Copper line = weeks to sell through allocated units at that pace · "
                                "Top lines by allocated COG (VELOCITY_TOP_FOR_CHART)"
                            ),
                            alt_text=(
                                "Combo chart of average units sold per day and weeks to sell through for top lines."
                            ),
                        ),
                        "basicChart": {
                            "chartType": "COMBO",
                            "legendPosition": "BOTTOM_LEGEND",
                            "compareMode": "CATEGORY",
                            "interpolateNulls": True,
                            "axis": [
                                {
                                    "position": "BOTTOM_AXIS",
                                    "title": "Brand × category (top by $)",
                                },
                                {
                                    "position": "LEFT_AXIS",
                                    "title": "Avg units / day",
                                },
                                {
                                    "position": "RIGHT_AXIS",
                                    "title": "Weeks to sell this buy",
                                },
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": source_range(dd_id, v0, v1, 0, 1)
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, v0, v1, 4, 5)
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                    "type": "COLUMN",
                                    "color": SERIES_PRIMARY,
                                },
                                {
                                    "series": {
                                        "sourceRange": source_range(dd_id, v0, v1, 6, 7)
                                    },
                                    "targetAxis": "RIGHT_AXIS",
                                    "type": "LINE",
                                    "color": SERIES_SECONDARY,
                                    "lineStyle": {"width": 2, "type": "SOLID"},
                                },
                            ],
                            "headerCount": 0,
                        },
                    },
                    "position": chart_pos(cr["velocity"], 8, 598, 318),
                }
            }
        }
    )

    return reqs


def main() -> int:
    _configure_stdio_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument(
        "--expected-pool",
        type=float,
        default=18_000.0,
        help="Nominal budget USD for validation (buy-plan: must equal sum(allocated)+unused from CSV).",
    )
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument(
        "--dashboard-mode",
        choices=("refresh", "rebuild"),
        default="refresh",
        help="refresh (default) = preserve dashboard layout/charts/formatting; rewrite data tabs + ledger (+ subtitle). "
        "rebuild = full dashboard tab regeneration (charts, merges, formats). First-time setup: rebuild once.",
    )
    ap.add_argument(
        "--rebuild-dashboard-layout",
        action="store_true",
        help="Same as --dashboard-mode rebuild.",
    )
    ap.add_argument(
        "--refresh-dashboard-narrative",
        action="store_true",
        help="With refresh mode, also overwrite What This Dashboard Says + Action Signals from the current CSV.",
    )
    ap.add_argument(
        "--no-refresh-subtitle",
        action="store_true",
        help="With refresh mode, do not overwrite the subtitle row.",
    )
    ap.add_argument(
        "--full-refresh",
        "--reset-charts-and-formatting",
        action="store_true",
        dest="full_refresh",
        help="Part 1 of layout reset: delete charts + reapply script formatting. **Ignored unless you also pass "
        "--confirm-layout-reset.**",
    )
    ap.add_argument(
        "--confirm-layout-reset",
        action="store_true",
        help="Part 2 of layout reset: required with --full-refresh; acknowledges manual chart placement and "
        "formatting on the four tabs will be removed and replaced by script defaults.",
    )
    ap.add_argument(
        "--preserve-charts",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    ap.add_argument(
        "--bounded-clear",
        action="store_true",
        help="Clear only the A1 range that fits each tab's new values plus pad rows, instead of 'A:ZZ' (keeps cells outside that box).",
    )
    ap.add_argument(
        "--bounded-clear-pad-rows",
        type=int,
        default=400,
        metavar="N",
        help="Extra rows cleared below the payload when using --bounded-clear (default 400).",
    )
    ap.add_argument(
        "--no-patch-chart-sources",
        dest="patch_chart_sources",
        action="store_false",
        help="Do not run updateChartSpec on embedded dashboard charts (refresh mode only; rebuild builds new charts).",
    )
    ap.add_argument(
        "--patch-charts-matching",
        action="append",
        default=None,
        metavar="SUBSTRING",
        help="Refresh mode only: only update embedded charts whose title or subtitle contains any of these "
        "substrings (case-insensitive). Repeat the flag for multiple needles. Omit to patch every "
        "chart the script recognizes.",
    )
    ap.set_defaults(patch_chart_sources=True)
    args = ap.parse_args()
    dashboard_mode: str = (
        "rebuild" if bool(getattr(args, "rebuild_dashboard_layout", False)) else str(args.dashboard_mode)
    )

    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1

    if bool(getattr(args, "full_refresh", False)) and not bool(getattr(args, "confirm_layout_reset", False)):
        print(
            "ERROR: --full-refresh / --reset-charts-and-formatting was given without --confirm-layout-reset.\n"
            "Refusing to delete charts or reapply formatting. Add --confirm-layout-reset if you mean it.",
            file=sys.stderr,
        )
        return 2

    full_refresh = bool(getattr(args, "full_refresh", False)) and bool(
        getattr(args, "confirm_layout_reset", False)
    )

    headers, rows = load_csv(args.csv)
    pool_sum = sum(fnum(r.get("allocated_cog_usd")) or 0 for r in rows)
    mode0 = (rows[0].get("allocation_mode") or "").strip() if rows else ""
    unallocated = 0.0
    if rows:
        u = fnum(rows[0].get("remaining_pool_unallocated_usd"))
        if u is not None:
            unallocated = max(0.0, u)
    exp = float(args.expected_pool)
    if mode0 == "buy-plan":
        pool_ok = abs(pool_sum + unallocated - exp) < 0.05
    else:
        pool_ok = abs(pool_sum - exp) < 0.05

    service = _service(args.sheets_service_account)
    sid = args.spreadsheet_id
    titles = ["raw_layer2", "dashboard_data", "dashboard", "notes"]
    sheet_ids = ensure_sheets(service, sid, titles)
    raw_id = sheet_ids["raw_layer2"]
    dd_id = sheet_ids["dashboard_data"]
    dash_id = sheet_ids["dashboard"]

    filter_mode, filter_value = read_dash_filter(service, sid)
    filtered_for_charts = filter_rows_like_sheet(rows, filter_mode, filter_value)
    pie_cat_count = max(
        len(
            {
                (r.get("category") or "").strip()
                for r in filtered_for_charts
                if (r.get("category") or "").strip()
            }
        ),
        1,
    )

    raw_values = [headers] + [[r.get(h, "") for h in headers] for r in rows]
    kpis = compute_kpis(
        rows, meaningful_usd=MEANINGFUL_USD, high_dollar_usd=HIGH_DOLLAR_USD
    )
    kpi_ac = kpi_ac_column_values(kpis)
    dd_values, meta = build_dashboard_data_formula_grid(
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
    notes_v = build_notes(
        args.csv,
        pool_ok,
        pool_sum,
        expected_pool_usd=exp,
        unallocated_usd=unallocated,
        allocation_mode=mode0,
    )

    clear_dashboard_tab = dashboard_mode == "rebuild"

    for t in titles:
        if not full_refresh:
            continue
        if t == "dashboard" and dashboard_mode == "refresh":
            continue
        delete_charts_on_sheet(service, sid, sheet_ids[t])

    write_projection_data_tabs(
        service,
        sid,
        raw_values=raw_values,
        dd_values=dd_values,
        notes_v=notes_v,
        clear_dashboard_tab=clear_dashboard_tab,
        bounded_clear=bool(args.bounded_clear),
        bounded_pad=int(args.bounded_clear_pad_rows),
    )

    sub = (
        "$18K velocity buy plan · brand×category grain · not SKU POs · units · weeks · payback · profit"
        if kpis.get("is_buy_plan")
        else "$18K capital plan · where money goes · payback · profit · what to do"
    )
    insight_bullets = build_insight_bullets(rows, kpis)
    action_signals = build_action_signals(rows, kpis)
    kpi_col = str(meta.get("kpi_formula_col_letter", "AC"))
    kpi_sr = int(meta["kpi_formula_start_row"])

    if dashboard_mode == "refresh":
        refresh_projection_dashboard_sheet(
            service,
            sid,
            meta=meta,
            kpis=kpis,
            rows=rows,
            kpi_col_letter=kpi_col,
            kpi_start_row_1based=kpi_sr,
            insight_bullets=insight_bullets,
            action_signals=action_signals,
            filter_mode=filter_mode,
            filter_value=filter_value,
            subtitle_text=sub,
            update_subtitle=not bool(args.no_refresh_subtitle),
            update_narrative=bool(args.refresh_dashboard_narrative),
        )
        if args.patch_chart_sources:
            pcm = getattr(args, "patch_charts_matching", None) or None
            title_substrings: tuple[str, ...] | None = (
                tuple(s for s in pcm if str(s).strip()) if pcm else None
            )
            patched, total = patch_dashboard_chart_sources(
                service,
                sid,
                dash_id,
                dd_id,
                meta,
                pie_category_count=pie_cat_count,
                chart_title_substrings=title_substrings,
            )
            filt = (
                f" (title filter: {', '.join(repr(s) for s in title_substrings)})"
                if title_substrings
                else ""
            )
            print(
                f"Chart sources: patched {patched} of {total} embedded dashboard chart(s) via updateChartSpec{filt}."
            )
        else:
            print("Chart sources: skipped (--no-patch-chart-sources).")
    else:
        rebuild_projection_dashboard_sheet(
            service,
            sid,
            dash_id,
            dd_id,
            meta=meta,
            kpis=kpis,
            rows=rows,
            kpi_col_letter=kpi_col,
            kpi_start_row_1based=kpi_sr,
            insight_bullets=insight_bullets,
            action_signals=action_signals,
            filter_mode=filter_mode,
            filter_value=filter_value,
            subtitle_text=sub,
        )

    if full_refresh:
        n_cols = len(headers)
        n_rows = len(rows) + 1
        fmt_reqs: list[dict[str, Any]] = []
        raw_cf_n = count_conditional_format_rules(service, sid, raw_id)
        fmt_reqs.extend(delete_conditional_format_rule_requests(raw_id, raw_cf_n))
        fmt_reqs.extend(batch_format_raw_layer2(sid, raw_id, n_rows, n_cols))
        fmt_reqs.extend(
            [
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": dd_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": 16,
                        }
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": dd_id,
                            "gridProperties": {"frozenRowCount": 0},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]
        )
        service.spreadsheets().batchUpdate(
            spreadsheetId=sid, body={"requests": fmt_reqs}
        ).execute()

    # Always last: M1/O1 validations (after dashboard writes so DV is not overwritten).
    service.spreadsheets().batchUpdate(
        spreadsheetId=sid,
        body={"requests": batch_filter_control_validations(dash_id)},
    ).execute()
    print(
        f"Filters: M1/O1 validation (O1 = dashboard_data!AB{FILTER_HELPERS_ROW_1BASED}:AB800)."
    )
    if dashboard_mode == "refresh":
        print(
            "Dashboard tab: refresh mode — layout/charts/formatting preserved; "
            "ledger (+ optional subtitle/narrative) updated; ranking/KPI formulas recalc from dashboard_data."
        )
    else:
        print(
            "Dashboard tab: rebuild mode — full layout (lib.projection_dashboard_sheet_rebuilt), "
            "freeze rows 3 (no frozen column; merges span A+), charts recreated."
        )

    url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    print(url)
    print("Tabs updated:", ", ".join(titles))
    if full_refresh:
        print(
            "WARNING: --full-refresh + --confirm-layout-reset: script formatting reapplied on raw_layer2 "
            "and dashboard_data helpers; charts on non-dashboard tabs removed if present. "
            "Dashboard charts were only cleared if this run used --dashboard-mode rebuild."
        )
    elif dashboard_mode == "rebuild":
        print(
            "Dashboard was fully rebuilt; raw_layer2 formatting unchanged unless you pass "
            "--full-refresh --confirm-layout-reset."
        )
    else:
        print(
            "Dashboard presentation preserved (refresh). Use --dashboard-mode rebuild to regenerate the tab; "
            "use --full-refresh --confirm-layout-reset to reformat raw_layer2."
        )
    print("Major dashboard sections: Executive summary KPIs, What This Dashboard Says, Action Signals,")
    print(
        "  Biggest / Fastest / Highest GP / Weak-efficiency, Category performance, "
        "Deployment ledger (brand subtotals), rebuilt chart row."
    )
    print(
        f"Meaningful-$ filter (where noted on tables & category weighted metrics): allocated_cog_usd >= {MEANINGFUL_USD:g}"
    )
    print("Chart data sources (dashboard_data, 0-based rows):")
    print(
        f"  filtered_layer2 + O1 unique lists: raw_layer2 body ends row "
        f"{meta.get('raw_data_end_row_1based', '?')} (1-based; must match CSV rows after each push)"
    )
    print(f"  Top allocations BAR/COMBO: rows {meta['alloc_data_start']}-{meta['alloc_data_end']}, cols A-G")
    print(
        f"  Fastest recovery COLUMN (meaningful $, by payback): rows "
        f"{meta['fast_recovery_data_start']}-{meta['fast_recovery_data_end']}, cols A-H"
    )
    print(
        f"  Category pie (allocated $): same rows as CATEGORY_SUMMARY, cols A–B "
        f"(rows {meta['cat_data_start']}-{meta['cat_data_end']})"
    )
    print(
        f"  Category recovery COLUMN (weighted avg payback): rows {meta['cat_data_start']}-{meta['cat_data_end']}, cols A-G"
    )
    print(
        f"  Velocity COMBO (units/day + weeks to sell): rows {meta['vel_chart_data_start']}-"
        f"{meta['vel_chart_data_end']}, cols A-H"
    )
    print(
        f"  Full velocity table (brand→category): rows {meta['velocity_data_start']}-{meta['velocity_data_end']}"
    )
    scat_x = (
        "cash recovery days"
        if meta.get("recovery_axis_days")
        else "payback months"
    )
    print(
        f"  Scatter: rows {meta['scatter_data_start']}-{meta['scatter_data_end']}, cols A-B "
        f"(X = {scat_x}, Y = revenue per $1 COG)"
    )
    print(
        f"  Bucket column: rows {meta['bucket_data_start']}-{meta['bucket_data_end']}, cols A-C"
    )
    print(
        f"  Brand bar: rows {meta['brand_data_start']}-{meta['brand_data_end']}, cols A-B"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
