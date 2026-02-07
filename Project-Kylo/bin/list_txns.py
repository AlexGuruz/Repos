from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions
from services.sheets.poster import _extract_spreadsheet_id


def main() -> int:
    cfg = load_config()
    company = "NUGZ"
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == company), None)
    if not comp:
        print("ERR company not found")
        return 2
    intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
    intake_sid = _extract_spreadsheet_id(str(intake_url))
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    header_rows = int(cfg.get("intake.csv_processor.header_rows", 1))

    txns_all: List[Dict] = []
    for tab in ("TRANSACTIONS", "BANK"):
        try:
            csv_content = download_petty_cash_csv(intake_sid, sa, sheet_name_override=tab)
            part = parse_csv_transactions(csv_content, header_rows=header_rows)
            for t in part:
                t["_tab"] = tab
            txns_all.extend(part)
        except Exception:
            pass

    dates = {"2025-07-18", "2025-09-17"}
    rows = [t for t in txns_all if (t.get("company_id") or "") == company and (t.get("posted_date") or "") in dates]
    print(f"found_rows {len(rows)}")
    # Print a compact summary
    for t in rows:
        try:
            amt = float(t.get("amount_cents", 0))/100.0
        except Exception:
            amt = 0.0
        print(f"{t.get('_tab')} {t.get('posted_date')} desc={t.get('description')} amount={amt:.2f}")
    # Unique descriptions per date
    by_date: Dict[str, set] = {}
    for t in rows:
        by_date.setdefault(t.get("posted_date"), set()).add(t.get("description"))
    for d, descs in sorted(by_date.items()):
        print(f"date {d} unique_descriptions: {sorted([str(x) for x in descs])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


