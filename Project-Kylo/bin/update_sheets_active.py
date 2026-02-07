from __future__ import annotations

import argparse
import os
import sys
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _extract_spreadsheet_id, _get_service


def get_approved_rules_from_db(dsn: str) -> List[Dict[str, Any]]:
    """Get approved rules from database active table"""
    import psycopg2
    import json
    
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rule_json FROM app.rules_active ORDER BY applied_at")
            return [row[0] for row in cur.fetchall()]


def update_sheets_active_tab(spreadsheet_id: str, company_id: str, rules: List[Dict[str, Any]], service_account: str) -> None:
    """Update the active tab in Google Sheets with the rules from database"""
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    # Get spreadsheet metadata
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles_to_ids = {}
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        titles_to_ids[props.get("title")] = props.get("sheetId")
    
    active_title = f"Active Rules – {company_id}"
    active_id = titles_to_ids.get(active_title)
    
    if not active_id:
        print(f"Active tab '{active_title}' not found in spreadsheet")
        return
    
    # Prepare data for active tab
    # Format: [Ruleset_Version, Effective_At, Company_ID, Source, Target_Sheet, Target_Header, Match_Notes, Created_At]
    rows = []
    for rule in rules:
        rows.append([
            "1.0",  # Ruleset_Version
            "2025-01-01",  # Effective_At
            company_id,  # Company_ID
            rule.get("source", ""),  # Source
            rule.get("target_sheet", ""),  # Target_Sheet
            rule.get("target_header", ""),  # Target_Header
            "",  # Match_Notes
            "2025-01-01"  # Created_At
        ])
    
    # Clear existing data (keep header)
    clear_range = f"{active_title}!A2:H1000"
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=clear_range
    ).execute()
    
    # Write new data
    if rows:
        body = {
            "values": rows
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{active_title}!A2",
            valueInputOption="RAW",
            body=body
        ).execute()
    
    print(f"Updated {active_title} with {len(rows)} rules")


def main() -> int:
    p = argparse.ArgumentParser(description="Update Google Sheets active tab with rules from database")
    p.add_argument("--spreadsheet", required=True, help="Spreadsheet URL or ID")
    p.add_argument("--company", required=True, help="Company ID")
    p.add_argument("--dsn", required=True, help="Database connection string")
    p.add_argument("--service-account", default=os.path.join("secrets", "service_account.json"))
    args = p.parse_args()
    
    # Get rules from database
    rules = get_approved_rules_from_db(args.dsn)
    print(f"Found {len(rules)} active rules in database")
    
    # Update Google Sheets
    update_sheets_active_tab(args.spreadsheet, args.company, rules, args.service_account)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
