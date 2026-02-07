from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_new_worksheet():
    """Check the new Google Sheets workbook with company tabs"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = meta.get("sheets", [])
        
        print("All tabs in new worksheet:")
        for sheet in sheets:
            props = sheet.get("properties", {})
            title = props.get("title", "")
            sheet_id = props.get("sheetId", "")
            print(f"  - {title} (ID: {sheet_id})")
        
        # Check for pending and active tabs for each company
        companies = ["NUGZ", "710 EMPIRE", "PUFFIN PURE", "JGD"]
        
        for company in companies:
            print(f"\n=== {company} ===")
            
            # Check pending tab
            pending_title = f"{company} Pending"
            try:
                result = service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=f"{pending_title}!A1:H10"
                ).execute()
                
                values = result.get('values', [])
                if values:
                    print(f"  {pending_title}: {len(values)-1} rules (headers: {values[0] if values else 'None'})")
                    if len(values) > 1:
                        print(f"    First rule: {values[1]}")
                else:
                    print(f"  {pending_title}: No data")
            except Exception as e:
                print(f"  {pending_title}: Error - {e}")
            
            # Check active tab
            active_title = f"{company} Active"
            try:
                result = service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=f"{active_title}!A1:H10"
                ).execute()
                
                values = result.get('values', [])
                if values:
                    print(f"  {active_title}: {len(values)-1} rules (headers: {values[0] if values else 'None'})")
                    if len(values) > 1:
                        print(f"    First rule: {values[1]}")
                else:
                    print(f"  {active_title}: No data")
            except Exception as e:
                print(f"  {active_title}: Error - {e}")
        
    except Exception as e:
        print(f"Error reading spreadsheet: {e}")


if __name__ == "__main__":
    check_new_worksheet()
