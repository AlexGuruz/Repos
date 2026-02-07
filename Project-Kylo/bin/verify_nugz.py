from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def verify_nugz_rules():
    """Verify NUGZ's rules in both database and Google Sheets"""
    spreadsheet_id = "1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco"
    company_id = "NUGZ"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    # Check Google Sheets Active tab
    active_title = f"Active Rules – {company_id}"
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{active_title}!A2:H10"
        ).execute()
        
        values = result.get('values', [])
        print(f"Google Sheets {active_title}:")
        if values:
            for i, row in enumerate(values, 1):
                if len(row) >= 5:  # At least source, target_sheet, target_header
                    print(f"  Row {i}: {row[3]} → {row[4]} / {row[5]}")
        else:
            print("  No data found")
            
    except Exception as e:
        print(f"Error reading Google Sheets: {e}")
    
    # Check Google Sheets Pending tab
    pending_title = f"Pending Rules – {company_id}"
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{pending_title}!A2:G10"
        ).execute()
        
        values = result.get('values', [])
        print(f"\nGoogle Sheets {pending_title}:")
        if values:
            for i, row in enumerate(values, 1):
                if len(row) >= 6:  # At least source, target_sheet, target_header, approved
                    approved = row[6] if len(row) > 6 else "FALSE"
                    print(f"  Row {i}: {row[1]} → {row[4]} / {row[5]} (Approved: {approved})")
        else:
            print("  No data found")
            
    except Exception as e:
        print(f"Error reading Google Sheets: {e}")


if __name__ == "__main__":
    verify_nugz_rules()
