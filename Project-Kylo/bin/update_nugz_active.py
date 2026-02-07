from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _extract_spreadsheet_id, _get_service


def update_nugz_active_tab():
    """Update NUGZ's active tab with the approved rule"""
    spreadsheet_id = "1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco"
    company_id = "NUGZ"
    service_account = os.path.join("secrets", "service_account.json")
    
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
    
    # The approved rule from database
    rule = {
        "source": "cash:atm fee",
        "target_sheet": "Cash", 
        "target_header": "ATM Fees"
    }
    
    # Prepare data for active tab
    # Format: [Ruleset_Version, Effective_At, Company_ID, Source, Target_Sheet, Target_Header, Match_Notes, Created_At]
    rows = [[
        "1.0",  # Ruleset_Version
        "2025-01-01",  # Effective_At
        company_id,  # Company_ID
        rule["source"],  # Source
        rule["target_sheet"],  # Target_Sheet
        rule["target_header"],  # Target_Header
        "",  # Match_Notes
        "2025-01-01"  # Created_At
    ]]
    
    # Clear existing data (keep header)
    clear_range = f"{active_title}!A2:H1000"
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=clear_range
    ).execute()
    
    # Write new data
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
    print(f"Rule: {rule['source']} → {rule['target_sheet']} / {rule['target_header']}")


if __name__ == "__main__":
    update_nugz_active_tab()
