from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_formatting():
    """Check the current formatting in the Google Sheets"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        # Check NUGZ Pending format
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="NUGZ Pending!A2:D5"
        ).execute()
        
        values = result.get('values', [])
        print("NUGZ Pending format (first 3 rules):")
        for i, row in enumerate(values[:3], 1):
            if len(row) >= 4:
                print(f"  {i}. Source: '{row[0]}' | Sheet: '{row[1]}' | Header: '{row[2]}' | Approved: '{row[3]}'")
        
        # Check NUGZ Active format
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="NUGZ Active!A2:D5"
        ).execute()
        
        values = result.get('values', [])
        print("\nNUGZ Active format (first 3 rules):")
        for i, row in enumerate(values[:3], 1):
            if len(row) >= 4:
                print(f"  {i}. Source: '{row[0]}' | Sheet: '{row[1]}' | Header: '{row[2]}' | Approved: '{row[3]}'")
        
    except Exception as e:
        print(f"Error checking formatting: {e}")


if __name__ == "__main__":
    check_formatting()
