from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service, _extract_spreadsheet_id
from scaffold.tools.sheets_cli import load_companies_config


def check_banner_placement():
    """Check if banner rows are placed correctly below headers"""
    
    # Load companies configuration
    cfg_path = os.environ.get("KYLO_COMPANIES_CONFIG", os.path.join("config", "companies.json"))
    if not os.path.exists(cfg_path):
        print(f"Error: Companies config not found at {cfg_path}")
        return
    
    cfg = load_companies_config(cfg_path)
    service_account = os.path.join("secrets", "service_account.json")
    
    if not os.path.exists(service_account):
        print(f"Error: Service account not found at {service_account}")
        return
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    service = _get_service()
    
    print("=== Checking Banner Row Placement ===\n")
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for checking rule management tabs
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        pending_title = f"{company_id} Pending"
        
        try:
            # Get first 10 rows to see the header and banner placement
            data_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A1:A10"
            ).execute()
            
            data_rows = data_result.get('values', [])
            print(f"🔍 {company_id} - First 10 rows:")
            
            banner_found = False
            for i, row in enumerate(data_rows, start=1):
                if row:
                    content = str(row[0])[:80]
                    if "Promoted" in content:
                        print(f"   Row {i}: 🎯 BANNER ROW - {content}")
                        banner_found = True
                    else:
                        print(f"   Row {i}: {content}")
                else:
                    print(f"   Row {i}: (empty)")
            
            if not banner_found:
                print(f"   ⚠️  No banner row found in first 10 rows")
            
            # Also check if there are any banner rows anywhere in the sheet
            full_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A:A"
            ).execute()
            
            full_rows = full_result.get('values', [])
            promotion_rows = []
            for i, row in enumerate(full_rows, start=1):
                if row and "Promoted" in str(row[0]):
                    promotion_rows.append((i, str(row[0])))
            
            if promotion_rows:
                print(f"   📊 Found {len(promotion_rows)} banner rows total:")
                for row_num, content in promotion_rows:
                    print(f"      Row {row_num}: {content[:60]}...")
            else:
                print(f"   ❌ No banner rows found anywhere")
                
        except Exception as e:
            print(f"❌ Error checking {company_id}: {e}")
        
        print()


if __name__ == "__main__":
    check_banner_placement()
