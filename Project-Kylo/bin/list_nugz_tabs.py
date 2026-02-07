from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def list_nugz_tabs():
    """List all tabs in the NUGZ spreadsheet"""
    spreadsheet_id = "1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = meta.get("sheets", [])
        
        print("All tabs in NUGZ spreadsheet:")
        for sheet in sheets:
            props = sheet.get("properties", {})
            title = props.get("title", "")
            sheet_id = props.get("sheetId", "")
            print(f"  - {title} (ID: {sheet_id})")
        
    except Exception as e:
        print(f"Error reading spreadsheet: {e}")


if __name__ == "__main__":
    list_nugz_tabs()
