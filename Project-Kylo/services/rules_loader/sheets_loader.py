from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from services.rules_loader.loader import (
    PendingRow,
    _canonicalize_headers,
    _title_to_company_id,
    _bool_from_cell,
    load_pending_for_company,
)


def _strip(val: Any) -> str:
    return ("" if val is None else str(val)).strip()


def _compute_content_hash(rule_json: Dict[str, Any]) -> str:
    # Keep identical hash behavior with file-based loader
    from hashlib import sha256
    payload = json.dumps(rule_json, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _load_sheets_service(service_account_path: str):
    # Use full Sheets scope to support DataFilter reads reliably
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _extract_spreadsheet_id(url_or_id: str) -> str:
    if "/d/" in url_or_id:
        try:
            return url_or_id.split("/d/")[1].split("/")[0]
        except Exception:
            return url_or_id
    return url_or_id


def _list_pending_tabs(service, spreadsheet_id: str) -> List[Tuple[int, str]]:
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )
    out: List[Tuple[int, str]] = []
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        title = props.get("title", "")
        # Support both naming schemes: "Pending Rules – CID" and "CID Pending"
        if title.startswith("Pending Rules – ") or title.endswith(" Pending"):
            out.append((int(props.get("sheetId")), title))
    return out


def _batch_read_tabs(service, spreadsheet_id: str, tabs: List[Tuple[int, str]]) -> List[Tuple[str, List[List[Any]]]]:
    if not tabs:
        return []
    data_filters = [
        {"gridRange": {"sheetId": sid, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": 11}}
        for (sid, _title) in tabs
    ]
    resp = (
        service.spreadsheets()
        .values()
        .batchGetByDataFilter(
            spreadsheetId=spreadsheet_id, body={"dataFilters": data_filters, "valueRenderOption": "UNFORMATTED_VALUE"}
        )
        .execute()
    )
    matched = resp.get("valueRanges", [])
    return [(tabs[i][1], matched[i].get("valueRange", {}).get("values", [])) for i in range(len(tabs))]


def parse_sheets(service, spreadsheet_id: str, only_company: Optional[str] = None) -> Dict[str, List[PendingRow]]:
    tabs = _list_pending_tabs(service, spreadsheet_id)
    data = _batch_read_tabs(service, spreadsheet_id, tabs)
    out: Dict[str, List[PendingRow]] = {}
    for title, values in data:
        # Title may be "Pending Rules – CID" or "CID Pending"
        if title.endswith(" Pending"):
            title_company = title[:-len(" Pending")].strip()
        else:
            title_company = _title_to_company_id(title)
        if only_company and title_company != only_company:
            continue
        if not values:
            continue
        header = [str(c).strip() if c is not None else "" for c in values[0]]
        canon = _canonicalize_headers(header)
        # Require the minimal set per new spec
        required = ["Source", "Target_Sheet", "Target_Header", "Approved"]
        if not all(c in canon for c in required):
            continue
        rows: List[PendingRow] = []
        for r in values[1:]:
            # map row to dict by header
            row_map = {header[i]: (r[i] if i < len(r) else None) for i in range(len(header))}

            def get(cn: str) -> Any:
                raw = canon.get(cn)
                if raw is None:
                    return None
                return row_map.get(raw)

            source = _strip(get("Source"))  # PRESERVE ORIGINAL FORMAT (ALL CAPS)
            target_sheet = _strip(get("Target_Sheet"))
            target_header = _strip(get("Target_Header"))
            approved = _bool_from_cell(get("Approved"))

            # Enforce required (minimal)
            if any(v == "" for v in [source, target_sheet, target_header]):
                continue

            rule_json = {
                "source": source,
                "target_sheet": target_sheet,
                "target_header": target_header,
            }
            content_hash = _compute_content_hash(rule_json)
            rows.append(
                PendingRow(
                    source=source,
                    target_sheet=target_sheet,
                    target_header=target_header,
                    approved=approved,
                    content_hash=content_hash,
                )
            )
        if rows:
            out.setdefault(title_company, []).extend(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Load Pending Rules from Google Sheets into rules_pending_<cid>")
    ap.add_argument("--spreadsheet", required=True, help="Spreadsheet URL or ID of the rules workbook")
    ap.add_argument("--service-account", default=os.path.join("secrets", "service_account.json"))
    ap.add_argument("--company", help="Only process a single company (optional)")
    ap.add_argument("--dsn-map", help="JSON mapping of company_id -> DSN (overrides KYLO_DB_DSN_MAP)")
    ap.add_argument("--dsn-map-file", help="Path to JSON file with company_id -> DSN mapping")
    ap.add_argument("--copy-threshold", type=int, default=int(os.environ.get("KYLO_RULES_COPY_THRESHOLD", "5000")))
    args = ap.parse_args()

    if not os.path.exists(args.service_account):
        print(f"Service account not found: {args.service_account}")
        return 2

    sid = _extract_spreadsheet_id(args.spreadsheet)
    service = _load_sheets_service(args.service_account)

    dsn_map_env = None
    if args.dsn_map_file and os.path.exists(args.dsn_map_file):
        with open(args.dsn_map_file, "r", encoding="utf-8") as f:
            dsn_map_env = f.read()
    dsn_map_env = dsn_map_env or args.dsn_map or os.environ.get("KYLO_DB_DSN_MAP")
    if not dsn_map_env:
        print("KYLO_DB_DSN_MAP not set and --dsn-map not provided")
        return 2
    try:
        dsn_map: Dict[str, str] = json.loads(dsn_map_env)
    except Exception as e:
        print(f"Invalid DSN map: {e}")
        return 2

    parsed = parse_sheets(service, sid, only_company=args.company)
    total_inserted = 0
    for company_id, rows in parsed.items():
        dsn = dsn_map.get(company_id)
        if not dsn:
            print(f"Skip {company_id}: no DSN in DSN map")
            continue
        ins = load_pending_for_company(dsn, company_id, rows, copy_threshold=args.copy_threshold)
        print(f"{company_id}: inserted={ins} (pending from sheets)")
        total_inserted += ins

    print(f"Done. total_inserted={total_inserted}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())


