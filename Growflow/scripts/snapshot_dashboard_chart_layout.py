#!/usr/bin/env python3
"""Backward-compatible alias: fast chart export only. Prefer ``export_projection_dashboard_layout.py``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _run_export():
    import importlib.util

    p = Path(__file__).resolve().parent / "export_projection_dashboard_layout.py"
    spec = importlib.util.spec_from_file_location("_export_proj_dash_layout", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load export_projection_dashboard_layout.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_export


def main() -> int:
    ap = argparse.ArgumentParser(description="Charts-only layout snapshot (legacy entry point).")
    ap.add_argument("--spreadsheet-id", default=None)
    ap.add_argument("--sheets-service-account", default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "data" / "dashboard_chart_layout_snapshot.json",
    )
    ap.add_argument("--print", action="store_true", dest="print_human")
    args = ap.parse_args()

    from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID

    sid = args.spreadsheet_id or DEFAULT_SPREADSHEET_ID
    return _run_export()(
        spreadsheet_id=sid,
        service_account=args.sheets_service_account,
        out_path=args.out,
        tabs=("raw_layer2", "dashboard_data", "dashboard", "notes"),
        max_rows=1,
        max_format_cells=1,
        charts_only=True,
        print_human=bool(args.print_human),
    )


if __name__ == "__main__":
    raise SystemExit(main())
