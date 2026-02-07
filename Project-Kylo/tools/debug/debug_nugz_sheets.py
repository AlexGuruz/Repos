from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def debug_nugz_sheets():
    """Debug NUGZ Google Sheets data structure"""
    spreadsheet_id = "1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco"
    company_id = "NUGZ"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    # Get rules from Google Sheets Pending tab
    pending_title = f"Pending Rules – {company_id}"
    try:
        # Try to get more columns
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{pending_title}!A1:H10"
        ).execute()
        
        values = result.get('values', [])
        print(f"Found {len(values)} rows in {pending_title}")
        print("Headers:", values[0] if values else "No headers")
        print("\nFirst 5 data rows:")
        for i, row in enumerate(values[1:6], 1):
            print(f"Row {i}: {row}")
        
        # Check if there's an Approved column
        if values and len(values[0]) >= 8:
            print(f"\nApproved column (column 8): {values[0][7] if len(values[0]) > 7 else 'Not found'}")
            for i, row in enumerate(values[1:6], 1):
                approved = row[7] if len(row) > 7 else "Not found"
                print(f"Row {i} Approved: {approved}")
        
    except Exception as e:
        print(f"Error reading Google Sheets: {e}")


if __name__ == "__main__":
    debug_nugz_sheets()
