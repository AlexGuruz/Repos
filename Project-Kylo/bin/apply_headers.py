from __future__ import annotations

import argparse
import os
from typing import List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _extract_spreadsheet_id, _get_service, ensure_company_tabs


def apply_headers(spreadsheet: str, companies: List[str], service_account: str | None) -> None:
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    sid = _extract_spreadsheet_id(spreadsheet)
    service = _get_service()
    body = ensure_company_tabs(sid, companies)
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body=body).execute()
    print(f"headers-applied {sid} for {len(companies)} companies")


def main() -> int:
    p = argparse.ArgumentParser(description="Apply header/banner rows and freeze to company tabs")
    p.add_argument("--spreadsheet", action="append", required=True, help="Spreadsheet URL or ID (can be repeated)")
    p.add_argument("--companies", required=True, help="Comma-separated company IDs (as used in tab titles)")
    p.add_argument("--service-account", default=os.path.join("secrets", "service_account.json"))
    args = p.parse_args()

    companies = [c.strip() for c in args.companies.split(",") if c.strip()]
    for sp in args.spreadsheet:
        apply_headers(sp, companies, args.service_account)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


