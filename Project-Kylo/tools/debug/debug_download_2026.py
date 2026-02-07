from __future__ import annotations

import os

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.sheets.poster import _extract_spreadsheet_id


def main() -> int:
    os.environ["KYLO_INSTANCE_ID"] = "JGD_2026"
    os.environ["KYLO_ACTIVE_YEARS"] = "2026"
    cfg = load_config()
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    sid = _extract_spreadsheet_id(cfg.get("year_workbooks.2026.intake_workbook_url"))
    print("sid", sid, "sa", sa)
    for tab in ["TRANSACTIONS", "BANK", "PETTY CASH"]:
        try:
            c = download_petty_cash_csv(sid, sa, sheet_name_override=tab)
            print(tab, "bytes", len(c))
        except Exception as e:
            print(tab, "ERROR", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

