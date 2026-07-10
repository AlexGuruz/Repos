#!/usr/bin/env python3
"""
Export a **layout map** of the projection capital Google Sheet: chart placement (incl. full chart spec),
per-tab merges, conditional formats, grid/frozen settings, and sampled cell-level formats.

**Env:** Copy ``config/dashboard_sheets.env.example`` → ``config/dashboard_sheets.env`` and set
``STASHBOX_SERVICE_ACCOUNT`` (or use env / CLI). See ``lib/stashbox_sheets_auth.py``.

**Routine dashboard pushes** (``build_projection_dashboard_google_sheet.py`` without ``--full-refresh``)
only use the Values API and do not apply this snapshot; keep this JSON as a **baseline** to diff after changes.

Usage (repo root):
  PYTHONPATH=. python scripts/export_projection_dashboard_layout.py
  PYTHONPATH=. python scripts/export_projection_dashboard_layout.py --charts-only --out exports/dashboard_charts.json
  PYTHONPATH=. python scripts/export_projection_dashboard_layout.py --max-rows 250 --max-format-cells 800
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402

DEFAULT_TABS = ("raw_layer2", "dashboard_data", "dashboard", "notes")


def _col_letters_0based(c: int) -> str:
    c += 1
    s = ""
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def _a1(row_0: int, col_0: int) -> str:
    return f"{_col_letters_0based(col_0)}{row_0 + 1}"


def _chart_title(spec: dict) -> str:
    if not spec:
        return ""
    return (spec.get("title") or "").strip() or "(no title)"


def _position_summary(pos: dict | None) -> dict:
    if not pos:
        return {}
    ov = pos.get("overlayPosition") or {}
    ac = ov.get("anchorCell") or {}
    return {
        "anchor_sheet_id": ac.get("sheetId"),
        "anchor_row_0based": ac.get("rowIndex"),
        "anchor_col_0based": ac.get("columnIndex"),
        "offset_x_px": ov.get("offsetXPixels"),
        "offset_y_px": ov.get("offsetYPixels"),
        "width_px": ov.get("widthPixels"),
        "height_px": ov.get("heightPixels"),
    }


def _summarize_sheet_for_export(sh: dict) -> dict[str, Any]:
    props = sh.get("properties") or {}
    gp = props.get("gridProperties") or {}
    out: dict[str, Any] = {
        "sheet_id": props.get("sheetId"),
        "title": props.get("title") or "",
        "grid_properties": {
            "row_count": gp.get("rowCount"),
            "column_count": gp.get("columnCount"),
            "frozen_row_count": gp.get("frozenRowCount"),
            "frozen_column_count": gp.get("frozenColumnCount"),
            "hide_gridlines": gp.get("hideGridlines"),
        },
        "merges": sh.get("merges") or [],
        "conditional_formats": sh.get("conditionalFormats") or [],
        "banded_ranges": sh.get("bandedRanges") or [],
        "protected_ranges": sh.get("protectedRanges") or [],
        "charts": [],
    }
    for ch in sh.get("charts") or []:
        spec = ch.get("spec") or {}
        out["charts"].append(
            {
                "chart_id": ch.get("chartId"),
                "title": _chart_title(spec),
                "subtitle": (spec.get("subtitle") or "").strip(),
                "position": _position_summary(ch.get("position")),
                "spec": spec,
            }
        )
    return out


def _extract_format_cells(
    sh: dict,
    *,
    max_cells: int,
) -> tuple[list[dict[str, Any]], int]:
    """Return (sample list, total count with any userEnteredFormat)."""
    sample: list[dict[str, Any]] = []
    total = 0
    title = (sh.get("properties") or {}).get("title") or ""
    for gd in sh.get("data") or []:
        start_row = int(gd.get("startRow") or 0)
        start_col = int(gd.get("startColumn") or 0)
        for r_i, row in enumerate(gd.get("rowData") or []):
            vals = row.get("values") or []
            for c_i, cell in enumerate(vals):
                fmt = cell.get("userEnteredFormat")
                if not fmt:
                    continue
                total += 1
                if len(sample) >= max_cells:
                    continue
                r = start_row + r_i
                c = start_col + c_i
                sample.append(
                    {
                        "sheet": title,
                        "a1": _a1(r, c),
                        "row_0based": r,
                        "col_0based": c,
                        "user_entered_format": fmt,
                    }
                )
    return sample, total


def run_export(
    *,
    spreadsheet_id: str,
    service_account: str | None,
    out_path: Path,
    tabs: tuple[str, ...],
    max_rows: int,
    max_format_cells: int,
    charts_only: bool,
    print_human: bool,
) -> int:
    service = sheets_service(service_account)

    id_map = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties(title),sheets(properties(sheetId,title))",
    ).execute()
    doc_title = (id_map.get("properties") or {}).get("title") or ""
    title_to_id = {
        (s.get("properties") or {}).get("title", ""): (s.get("properties") or {}).get("sheetId")
        for s in id_map.get("sheets") or []
    }

    missing = [t for t in tabs if t not in title_to_id]
    if missing:
        print(f"WARNING: tabs not in workbook (skipped): {missing}", file=sys.stderr)

    present_tabs = [t for t in tabs if t in title_to_id]

    fields_meta = (
        "properties(title),"
        "sheets("
        "properties(sheetId,title,gridProperties),"
        "merges,"
        "conditionalFormats,"
        "bandedRanges,"
        "protectedRanges,"
        "charts(chartId,position,spec))"
    )
    meta_resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields=fields_meta,
    ).execute()

    sheets_by_title: dict[str, dict] = {}
    for sh in meta_resp.get("sheets") or []:
        t = (sh.get("properties") or {}).get("title") or ""
        if t in present_tabs:
            sheets_by_title[t] = sh

    payload: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_title": doc_title,
        "dashboard_tabs": list(present_tabs),
        "export_note": (
            "build_projection_dashboard_google_sheet.py default run uses Values API clear+update only; "
            "does not batchUpdate charts/formatting. Layout reset requires --full-refresh AND --confirm-layout-reset."
        ),
        "tabs": [],
        "charts_total": 0,
    }

    for t in present_tabs:
        sh = sheets_by_title[t]
        block = _summarize_sheet_for_export(sh)
        payload["charts_total"] += len(block["charts"])
        if not charts_only:
            block["format_cells_sample"] = []
            block["format_cells_total_on_grid"] = 0
        payload["tabs"].append(block)

    if not charts_only and present_tabs:
        ranges = [f"'{t}'!A1:ZZ{max_rows}" for t in present_tabs]
        fields_grid = (
            "sheets(properties(sheetId,title),"
            "data(rowData(values(userEnteredFormat,userEnteredValue,effectiveFormat))))"
        )
        grid_resp = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            includeGridData=True,
            fields=fields_grid,
        ).execute()

        for sh in grid_resp.get("sheets") or []:
            title = (sh.get("properties") or {}).get("title") or ""
            if title not in sheets_by_title:
                continue
            sample, total = _extract_format_cells(sh, max_cells=max_format_cells)
            for block in payload["tabs"]:
                if block["title"] == title:
                    block["format_cells_sample"] = sample
                    block["format_cells_total_on_grid"] = total
                    block["grid_scan_note"] = (
                        f"Scanned A1:ZZ{max_rows}; stored up to {max_format_cells} formatted cells; "
                        f"total cells with userEnteredFormat in scan: {total}"
                    )
                    break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path.resolve()}", flush=True)
    print(f"  tabs: {len(present_tabs)}  charts: {payload['charts_total']}", flush=True)

    if print_human:
        print(f"\nWorkbook: {doc_title!r}\n")
        for block in payload["tabs"]:
            print(f"=== {block['title']} (sheetId={block['sheet_id']}) ===")
            fr = block["grid_properties"].get("frozen_row_count")
            fc = block["grid_properties"].get("frozen_column_count")
            print(f"  frozen: rows={fr} cols={fc}")
            print(f"  merges: {len(block['merges'])}  conditional_format_rules: {len(block['conditional_formats'])}")
            print(f"  charts: {len(block['charts'])}")
            for c in block["charts"]:
                p = c.get("position") or {}
                print(
                    f"    chartId={c['chart_id']}  {c['title']!r}  "
                    f"anchor(r,c)={p.get('anchor_row_0based')},{p.get('anchor_col_0based')}  "
                    f"{p.get('width_px')}x{p.get('height_px')}px"
                )
            if not charts_only and block.get("format_cells_total_on_grid") is not None:
                print(
                    f"  formatted cells in scan: {block['format_cells_total_on_grid']} "
                    f"(sample stored: {len(block.get('format_cells_sample') or [])})"
                )
            print()

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export chart placement, sheet structure, conditional formats, merges, and sampled cell formats."
    )
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "exports" / "projection_dashboard_layout_snapshot.json",
    )
    ap.add_argument(
        "--tabs",
        default=",".join(DEFAULT_TABS),
        help="Comma-separated tab names (default: four projection dashboard tabs).",
    )
    ap.add_argument(
        "--max-rows",
        type=int,
        default=400,
        help="Rows per tab to scan for cell formats (A1:ZZ{max-rows}). Ignored with --charts-only.",
    )
    ap.add_argument(
        "--max-format-cells",
        type=int,
        default=1500,
        help="Max formatted cells to store in JSON sample per tab. Ignored with --charts-only.",
    )
    ap.add_argument(
        "--charts-only",
        action="store_true",
        help="Skip grid scan (smaller/faster); charts still include full spec.",
    )
    ap.add_argument("--print", action="store_true", dest="print_human")
    args = ap.parse_args()

    tabs = tuple(x.strip() for x in args.tabs.split(",") if x.strip())
    return run_export(
        spreadsheet_id=args.spreadsheet_id,
        service_account=args.sheets_service_account,
        out_path=args.out,
        tabs=tabs,
        max_rows=max(1, int(args.max_rows)),
        max_format_cells=max(1, int(args.max_format_cells)),
        charts_only=bool(args.charts_only),
        print_human=bool(args.print_human),
    )


if __name__ == "__main__":
    raise SystemExit(main())
