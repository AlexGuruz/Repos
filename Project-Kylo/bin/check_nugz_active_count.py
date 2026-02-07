from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_nugz_active_count():
    """Check the actual count in NUGZ Active tab"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        # Get ALL NUGZ active rules
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="NUGZ Active!A2:D200"  # Increased range to get all rules
        ).execute()
        
        values = result.get('values', [])
        print(f"Total rules found in NUGZ Active: {len(values)}")
        
        if values:
            print(f"First 5 rules:")
            for i, row in enumerate(values[:5], 1):
                if len(row) >= 4:
                    print(f"  {i}. {row[0]} → {row[1]} / {row[2]} ({row[3]})")
            
            print(f"\nLast 5 rules:")
            for i, row in enumerate(values[-5:], len(values)-4):
                if len(row) >= 4:
                    print(f"  {i}. {row[0]} → {row[1]} / {row[2]} ({row[3]})")
        
    except Exception as e:
        print(f"Error reading NUGZ active rules: {e}")


if __name__ == "__main__":
    check_nugz_active_count()
