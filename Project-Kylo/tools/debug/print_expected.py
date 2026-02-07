from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions
from services.sheets.poster import _extract_spreadsheet_id


def mdy_to_iso(mdy: str) -> str:
    m, d, y2 = mdy.split("/")
    return f"20{int(y2):02d}-{int(m):02d}-{int(d):02d}"


def main() -> int:
    cfg = load_config()
    company = "NUGZ"

    # Resolve intake spreadsheet id
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == company), None)
    if not comp:
        print("ERR company not found in config")
        return 2
    intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
    intake_sid = _extract_spreadsheet_id(str(intake_url))
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    header_rows = int(cfg.get("intake.csv_processor.header_rows", 1))

    # Load both TRANSACTIONS and BANK
    txns_all: List[Dict] = []
    for tab in ("TRANSACTIONS", "BANK"):
        try:
            csv_content = download_petty_cash_csv(intake_sid, sa, sheet_name_override=tab)
            txns_all.extend(parse_csv_transactions(csv_content, header_rows=header_rows))
        except Exception as e:
            # Skip missing tabs
            pass

    # Compute totals for exact case-sensitive description match
    targets = {"7/18/25", "9/17/25"}
    totals: Dict[str, float] = defaultdict(float)
    for t in txns_all:
        if (t.get("company_id") or "") != company:
            continue
        desc = t.get("description") or ""
        # exact string
        if desc != "OEC":
            continue
        dt_iso = t.get("posted_date") or ""
        # convert iso to m/d/yy
        if len(dt_iso) == 10 and dt_iso.count("-") == 2:
            y, m, d = dt_iso.split("-")
            key = f"{int(m)}/{int(d)}/{int(y)%100:02d}"
        else:
            continue
        totals[key] += float(t.get("amount_cents", 0)) / 100.0

    # Also compute static row indices from YAML dates
    static_dates: List[str] = (
        cfg.get("intake.static_dates") or cfg.get("intake_static_dates.dates", []) or []
    )
    first_row = int(cfg.get("intake_static_dates.first_row", 20))

    def to_row(date_key: str) -> int | None:
        try:
            idx = static_dates.index(date_key)
            return first_row + idx
        except ValueError:
            return None

    for key in sorted(totals.keys()):
        row = to_row(key)
        print(f"date={key} row={row} total={totals[key]:.2f}")

    # Explicitly print the asked dates even if zero
    for key in ("7/18/25", "9/17/25"):
        row = to_row(key)
        print(f"ASKED date={key} row={row} total={totals.get(key, 0.0):.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


