from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions


def col_to_a1(idx0: int) -> str:
    s = ""; n = idx0 + 1
    while n:
        n, r = divmod(n-1, 26)
        s = chr(65+r) + s
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--source", required=True, help="rule source, e.g. MOMENTUM")
    ap.add_argument("--date", required=True, help="M/D/YY, e.g. 10/6/25")
    ap.add_argument("--tab", required=True, help="target sheet/tab title")
    ap.add_argument("--header", required=True, help="target header text on row 19")
    args = ap.parse_args()

    cfg = load_config()
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper()==args.company.strip().upper()), None)
    if not comp:
        print("ERR: company not found in config")
        return 2
    intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
    sid = _extract_spreadsheet_id(str(intake_url))
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # Load BANK + TRANSACTIONS, but we will print BANK focus
    txns: List[Dict[str, Any]] = []
    for tab in ("TRANSACTIONS","BANK"):
        try:
            csv = download_petty_cash_csv(sid, sa, sheet_name_override=tab)
            part = parse_csv_transactions(csv, header_rows=int(cfg.get("intake.csv_processor.header_rows", 1)))
            for t in part:
                t["_tab"] = tab
            txns.extend(part)
        except Exception as e:
            print(f"WARN: load {tab} failed: {e}")

    # Build total case-insensitive contains for date
    # Convert to ISO expected (YYYY-MM-DD) based on M/D/YY
    m,d,y2 = args.date.split("/")
    iso = f"20{int(y2):02d}-{int(m):02d}-{int(d):02d}"
    total = 0.0
    rows = []
    for t in txns:
        if (t.get("company_id") or "").strip().upper() != args.company.strip().upper():
            continue
        if (t.get("posted_date") or "") != iso:
            continue
        desc = (t.get("description") or "")
        if args.source.strip().lower() in desc.strip().lower():
            total += float(t.get("amount_cents",0))/100.0
            rows.append((t.get("_tab"), t.get("row_index_0based"), desc, float(t.get("amount_cents",0))/100.0))

    print(f"matches={len(rows)} total={total:.2f}")
    for r in rows[:10]:
        print("row:", r)

    # Resolve target cell
    ssid = _extract_spreadsheet_id(str(comp.get("workbook_url")))
    service = _get_service()
    header_row = int(cfg.get("intake_static_dates.header_row",19))
    first_row = int(cfg.get("intake_static_dates.first_row",20))
    # header col
    res = service.spreadsheets().values().get(spreadsheetId=ssid, range=f"{args.tab}!{header_row}:{header_row}", valueRenderOption="UNFORMATTED_VALUE").execute()
    headers = [str(c).strip() for c in (res.get("values", [[]])[0] if res.get("values") else [])]
    try:
        idx = [h.lower() for h in headers].index(args.header.strip().lower())
    except Exception:
        print("ERR: header not found on row 19")
        return 1
    col = col_to_a1(idx)
    # date row
    static_dates: List[str] = (
        cfg.get("intake.static_dates") or cfg.get("intake_static_dates.dates", []) or []
    )
    try:
        off = static_dates.index(args.date)
    except ValueError:
        print("ERR: date not in static list")
        return 1
    row = first_row + off
    print(f"target_cell={args.tab}!{col}{row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


