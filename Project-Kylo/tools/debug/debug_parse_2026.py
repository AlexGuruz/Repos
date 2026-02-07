from __future__ import annotations

import os
from collections import Counter

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.sheets.poster import _extract_spreadsheet_id


def _year_from_posted_date(dt: str) -> int | None:
    dt = (dt or "").strip()
    if len(dt) >= 4 and dt[:4].isdigit():
        return int(dt[:4])
    if "/" in dt:
        parts = dt.split("/")
        tail = parts[-1].strip()
        if tail.isdigit():
            if len(tail) == 2:
                return 2000 + int(tail)
            if len(tail) == 4:
                return int(tail)
    return None


def main() -> int:
    os.environ["KYLO_INSTANCE_ID"] = "JGD_2026"
    os.environ["KYLO_ACTIVE_YEARS"] = "2026"

    cfg = load_config()
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    sid = _extract_spreadsheet_id(cfg.get("year_workbooks.2026.intake_workbook_url"))

    for tab in ["TRANSACTIONS", "BANK"]:
        csv = download_petty_cash_csv(sid, sa, sheet_name_override=tab)
        proc = PettyCashCSVProcessor(
            csv,
            header_rows=int(cfg.get("intake.csv_processor.header_rows", 19)),
            source_tab=tab,
            source_spreadsheet_id=sid,
        )
        txns = list(proc.parse_transactions())
        years = Counter(_year_from_posted_date(str(t.get("posted_date") or "")) for t in txns)
        non_null_amount = sum(1 for t in txns if t.get("amount") not in (None, "", 0, 0.0))
        print(
            f"tab={tab} parsed={len(txns)} non_null_amount={non_null_amount} "
            f"year_counts={dict(sorted(years.items(), key=lambda x: (x[0] is None, x[0])))}"
        )
        for t in txns[:5]:
            print(
                "  ",
                {
                    "posted_date": t.get("posted_date"),
                    "description": t.get("description"),
                    "amount": t.get("amount"),
                    "row_index_0based": t.get("row_index_0based"),
                },
            )
        for t in txns:
            if t.get("amount") not in (None, "", 0, 0.0):
                print("  first_with_amount", {"posted_date": t.get("posted_date"), "description": t.get("description"), "amount": t.get("amount")})
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

