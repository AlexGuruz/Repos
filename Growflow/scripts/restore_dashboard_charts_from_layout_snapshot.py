#!/usr/bin/env python3
"""
Restore embedded charts on the ``dashboard`` tab from a layout snapshot JSON.

Use this when an accidental ``--dashboard-mode rebuild`` replaced hand-tuned chart placement/specs.

This script:
  - Deletes **all** embedded charts on ``dashboard``
  - Re-adds charts from the snapshot's stored ``spec`` + ``position`` (same as export_projection_dashboard_layout.py)

Notes:
  - Chart IDs will change (Google assigns new IDs on add).
  - Snapshot must be from the same spreadsheet (sheetId values must still match).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.projection_dashboard_sheet_rebuilt import delete_charts_on_sheet  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402


def _strip_chart_ids(obj: Any) -> Any:
    """Remove fields that must not be sent on addChart (chartId, etc.)."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in {"chartId"}:
                continue
            out[k] = _strip_chart_ids(v)
        return out
    if isinstance(obj, list):
        return [_strip_chart_ids(x) for x in obj]
    return obj


def _position_from_export_summary(
    *,
    dashboard_sheet_id: int,
    pos: dict[str, Any],
) -> dict[str, Any]:
    """Convert export_projection_dashboard_layout.py position summary → Sheets API overlayPosition."""
    return {
        "overlayPosition": {
            "anchorCell": {
                "sheetId": int(dashboard_sheet_id),
                "rowIndex": int(pos.get("anchor_row_0based") or 0),
                "columnIndex": int(pos.get("anchor_col_0based") or 0),
            },
            "offsetXPixels": int(pos.get("offset_x_px") or 0),
            "offsetYPixels": int(pos.get("offset_y_px") or 0),
            "widthPixels": int(pos.get("width_px") or 0),
            "heightPixels": int(pos.get("height_px") or 0),
        }
    }


def _deep_drop_keys(obj: Any, drop: set[str]) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_drop_keys(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [_deep_drop_keys(x, drop) for x in obj]
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore dashboard embedded charts from a layout snapshot JSON.")
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument(
        "--snapshot",
        type=Path,
        default=REPO / "exports" / "projection_dashboard_layout_baseline.json",
        help="JSON produced by scripts/export_projection_dashboard_layout.py (charts included).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without calling batchUpdate.",
    )
    args = ap.parse_args()

    if not args.snapshot.is_file():
        print(f"Snapshot not found: {args.snapshot}", file=sys.stderr)
        return 1

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    tabs = payload.get("tabs") or []
    dash = next((t for t in tabs if (t.get("title") or "") == "dashboard"), None)
    if not dash:
        print("Snapshot missing dashboard tab", file=sys.stderr)
        return 2

    charts = dash.get("charts") or []
    if not charts:
        print("Snapshot has no charts on dashboard tab", file=sys.stderr)
        return 3

    svc = sheets_service(args.sheets_service_account)
    sid = args.spreadsheet_id
    meta = svc.spreadsheets().get(spreadsheetId=sid, fields="sheets(properties(sheetId,title))").execute()
    dash_id = None
    for sh in meta.get("sheets", []):
        p = sh.get("properties") or {}
        if (p.get("title") or "") == "dashboard":
            dash_id = int(p["sheetId"])
            break
    if dash_id is None:
        print("Spreadsheet missing dashboard tab", file=sys.stderr)
        return 4

    print(f"Restoring {len(charts)} chart(s) on dashboard (sheetId={dash_id}) from {args.snapshot}", flush=True)
    if args.dry_run:
        for c in charts:
            print(f"- would add: {c.get('title')!r}", flush=True)
        return 0

    delete_charts_on_sheet(svc, sid, dash_id)

    reqs: list[dict[str, Any]] = []
    for c in charts:
        spec = _deep_drop_keys(_strip_chart_ids(c.get("spec") or {}), {"lineSmoothing"})
        pos = c.get("position") or {}
        if not spec or not pos:
            continue
        reqs.append(
            {
                "addChart": {
                    "chart": {
                        "spec": spec,
                        "position": _position_from_export_summary(
                            dashboard_sheet_id=dash_id, pos=pos
                        ),
                    }
                }
            }
        )

    if not reqs:
        print("No valid chart specs found in snapshot", file=sys.stderr)
        return 5

    svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
    print("OK: charts restored from snapshot", flush=True)
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
