from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_nugz_pending():
    """Check NUGZ pending rules in the main workbook"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        # Get NUGZ pending rules
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="NUGZ Pending!A2:D20"
        ).execute()
        
        values = result.get('values', [])
        print(f"NUGZ Pending Rules ({len(values)} total):")
        
        approved_count = 0
        for i, row in enumerate(values, 1):
            if len(row) >= 4:
                source = row[0]
                target_sheet = row[1] 
                target_header = row[2]
                approved = row[3].upper() == "TRUE"
                
                status = "✅ APPROVED" if approved else "❌ NOT APPROVED"
                if approved:
                    approved_count += 1
                
                print(f"  {i}. {source} → {target_sheet} / {target_header} ({status})")
        
        print(f"\nSummary: {approved_count} approved out of {len(values)} total rules")
        
    except Exception as e:
        print(f"Error reading NUGZ pending rules: {e}")


if __name__ == "__main__":
    check_nugz_pending()
