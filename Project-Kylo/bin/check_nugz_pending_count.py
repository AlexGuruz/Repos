from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_nugz_pending_count():
    """Check the actual count of approved rules in NUGZ Pending tab"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        # Get ALL NUGZ pending rules
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="NUGZ Pending!A2:D200"  # Increased range to get all rules
        ).execute()
        
        values = result.get('values', [])
        print(f"Total rules found in NUGZ Pending: {len(values)}")
        
        approved_count = 0
        approved_rules = []
        
        for i, row in enumerate(values, 1):
            if len(row) >= 4:
                source = row[0]
                target_sheet = row[1] 
                target_header = row[2]
                approved = row[3].upper() == "TRUE"
                
                if approved:
                    approved_count += 1
                    approved_rules.append((source, target_sheet, target_header))
        
        print(f"Approved rules: {approved_count}")
        print(f"Not approved rules: {len(values) - approved_count}")
        
        print(f"\nFirst 10 approved rules:")
        for i, (source, target_sheet, target_header) in enumerate(approved_rules[:10], 1):
            print(f"  {i}. {source} → {target_sheet} / {target_header}")
        
        print(f"\nLast 10 approved rules:")
        for i, (source, target_sheet, target_header) in enumerate(approved_rules[-10:], len(approved_rules)-9):
            print(f"  {i}. {source} → {target_sheet} / {target_header}")
        
    except Exception as e:
        print(f"Error reading NUGZ pending rules: {e}")


if __name__ == "__main__":
    check_nugz_pending_count()
