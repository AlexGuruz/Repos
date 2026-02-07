from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from typing import Any, Dict, Optional


def _compute_content_hash(rule_json: Dict[str, Any]) -> str:
    payload = json.dumps(rule_json, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _build_source_with_note(base: str, amount: Optional[str], date: Optional[str], ident: Optional[str]) -> str:
    parts = []
    if amount:
        parts.append(f"amt={amount}")
    if date:
        parts.append(f"date={date}")
    if ident:
        parts.append(f"id={ident}")
    note = f" [{', '.join(parts)}]" if parts else ""
    return (base or "").strip() + note


def _append_to_sheets(spreadsheet: str, service_account: str, company_id: str, row: list[str]) -> None:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    def extract_sid(url_or_id: str) -> str:
        return url_or_id.split("/d/")[1].split("/")[0] if "/d/" in url_or_id else url_or_id

    sid = extract_sid(spreadsheet)
    creds = Credentials.from_service_account_file(service_account, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    pending_title_variants = [f"Pending Rules – {company_id}", f"{company_id} Pending"]
    sheet_id = None
    for s in meta.get("sheets", []):
        title = s.get("properties", {}).get("title", "")
        if title in pending_title_variants:
            sheet_id = int(s.get("properties", {}).get("sheetId"))
            break
    if sheet_id is None:
        # no-op if sheet missing
        return

    # Find current row count by reading values
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=f"'{pending_title_variants[0]}'!A1:Z", valueRenderOption="UNFORMATTED_VALUE")
        .execute()
    )
    values = resp.get("values", [])
    start_row_index = max(len(values), 1)  # append after existing; account for header at row 1

    # Write one row via updateCells
    def to_cell(v: Any) -> Dict[str, Any]:
        return {"userEnteredValue": {"stringValue": "" if v is None else str(v)}}

    body = {
        "requests": [
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_index,
                        "startColumnIndex": 0,
                    },
                    "fields": "userEnteredValue",
                    "rows": [{"values": [to_cell(v) for v in row]}],
                }
            }
        ]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body=body).execute()


def main() -> int:
    ap = argparse.ArgumentParser(description="Add a pending rule with transaction metadata note")
    ap.add_argument("--company", required=True, help="Company ID (as used in DSN map)")
    ap.add_argument("--source", required=True, help="Base source text from the transaction")
    ap.add_argument("--amount", help="Transaction amount (as displayed)")
    ap.add_argument("--date", help="Transaction date (YYYY-MM-DD or free text)")
    ap.add_argument("--id", dest="ident", help="Internal identifier (e.g., txn uid or stream id)")
    ap.add_argument("--approved", action="store_true", help="Mark as approved (default: FALSE)")
    ap.add_argument("--target-sheet", default="", help="Optional target sheet (blank for pending)")
    ap.add_argument("--target-header", default="", help="Optional target header (blank for pending)")
    ap.add_argument("--dsn-map", help="Inline JSON map of company_id->DSN (overrides env)")
    ap.add_argument("--dsn-map-file", help="Path to JSON file with company_id->DSN map")
    ap.add_argument("--spreadsheet", help="Spreadsheet URL or ID to also append the row (optional)")
    ap.add_argument("--service-account", default=os.path.join("secrets", "service_account.json"))
    args = ap.parse_args()

    # Resolve DSN
    dsn_map_env = None
    if args.dsn_map_file and os.path.exists(args.dsn_map_file):
        with open(args.dsn_map_file, "r", encoding="utf-8") as f:
            dsn_map_env = f.read()
    dsn_map_env = dsn_map_env or args.dsn_map or os.environ.get("KYLO_DB_DSN_MAP")
    if not dsn_map_env:
        print("KYLO_DB_DSN_MAP not set and --dsn-map not provided")
        return 2
    dsn_map: Dict[str, str] = json.loads(dsn_map_env)
    dsn = dsn_map.get(args.company)
    if not dsn:
        print(f"Company not in DSN map: {args.company}")
        return 2

    # Compose source with metadata note and normalize for hashing
    source_with_note = _build_source_with_note(args.source, args.amount, args.date, args.ident)
    rule_json = {
        "source": (source_with_note or "").strip().lower(),
        "target_sheet": args.target_sheet or "",
        "target_header": args.target_header or "",
    }
    content_hash = _compute_content_hash(rule_json)

    # Insert into rules_pending_<cid>
    from services.rules_loader.loader import PendingRow, load_pending_for_company

    pr = PendingRow(
        source=rule_json["source"],
        target_sheet=rule_json["target_sheet"],
        target_header=rule_json["target_header"],
        approved=bool(args.approved),
        content_hash=content_hash,
    )
    inserted = load_pending_for_company(dsn, args.company, [pr], copy_threshold=1)
    print(json.dumps({
        "company": args.company,
        "inserted": inserted,
        "source": source_with_note,
        "approved": bool(args.approved),
    }))

    # Optionally append to Google Sheets
    if args.spreadsheet and os.path.exists(args.service_account):
        try:
            row = [source_with_note, args.target_sheet or "", args.target_header or "", str(bool(args.approved)).upper()]
            _append_to_sheets(args.spreadsheet, args.service_account, args.company, row)
        except Exception as e:
            print(json.dumps({"sheets_append": f"skipped: {e}"}))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


