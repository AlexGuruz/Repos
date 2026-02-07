from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def check_all_active_counts():
    """Check the actual counts in all active tabs"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    companies = ["NUGZ", "710 EMPIRE", "PUFFIN PURE", "JGD"]
    
    for company in companies:
        try:
            # Get ALL rules from active tab
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{company} Active!A2:D500"  # Increased range to get all rules
            ).execute()
            
            values = result.get('values', [])
            print(f"{company} Active: {len(values)} rules")
            
        except Exception as e:
            print(f"{company} Active: Error - {e}")


if __name__ == "__main__":
    check_all_active_counts()
