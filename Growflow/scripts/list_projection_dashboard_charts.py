#!/usr/bin/env python3
"""List embedded charts on the ``dashboard`` tab (chartId, title, subtitle, kind).

Use this to pick ``--patch-charts-matching`` needles when fixing charts one at a time
without ``--dashboard-mode rebuild``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402


def _spec_text_field(spec: dict[str, Any], key: str) -> str:
    t = spec.get(key)
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


def _chart_kind(spec: dict[str, Any]) -> str:
    for k in (
        "basicChart",
        "pieChart",
        "comboChart",
        "candlestickChart",
        "histogramChart",
        "waterfallChart",
        "treemapChart",
    ):
        if spec.get(k):
            return k
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description="List embedded charts on the dashboard sheet.")
    ap.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    ap.add_argument("--sheets-service-account", default=None)
    args = ap.parse_args()
    svc = sheets_service(args.sheets_service_account)
    sid = str(args.spreadsheet_id).strip()
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    dash_id: int | None = None
    for s in meta.get("sheets", []) or []:
        p = s.get("properties") or {}
        if (p.get("title") or "") == "dashboard":
            dash_id = int(p["sheetId"])
            break
    if dash_id is None:
        print("No sheet named 'dashboard' in this spreadsheet.", file=sys.stderr)
        return 2

    resp = svc.spreadsheets().get(
        spreadsheetId=sid,
        fields="sheets(properties(sheetId),charts(chartId,spec))",
    ).execute()
    rows: list[tuple[int, str, str, str]] = []
    for sh in resp.get("sheets", []) or []:
        if (sh.get("properties") or {}).get("sheetId") != dash_id:
            continue
        for ch in sh.get("charts") or []:
            cid = ch.get("chartId")
            spec = ch.get("spec") or {}
            if cid is None:
                continue
            rows.append(
                (
                    int(cid),
                    _spec_text_field(spec, "title"),
                    _spec_text_field(spec, "subtitle"),
                    _chart_kind(spec),
                )
            )
    rows.sort(key=lambda r: r[0])
    print("chart_id\ttitle\tsubtitle\tkind")
    for cid, title, subtitle, kind in rows:
        safe_title = title.replace("\t", " ").replace("\n", " ")
        safe_sub = subtitle.replace("\t", " ").replace("\n", " ")
        print(f"{cid}\t{safe_title}\t{safe_sub}\t{kind}")
    print(f"Total: {len(rows)} chart(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
