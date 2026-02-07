from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service, _extract_spreadsheet_id
from scaffold.tools.sheets_cli import load_companies_config


def check_banner_rows_extended():
    """Check for banner rows in a much larger range"""
    
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
    
    print("=== Extended Banner Row Check ===\n")
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for checking rule management tabs
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        print(f"🔍 Checking {company_id} (Spreadsheet ID: {spreadsheet_id})")
        
        try:
            # Check pending tab for banner rows in a much larger range
            pending_title = f"{company_id} Pending"
            
            # Check first 1000 rows for banner rows
            try:
                data_result = service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=f"{pending_title}!A1:A1000"
                ).execute()
                
                data_rows = data_result.get('values', [])
                banner_rows = []
                
                print(f"  📋 {pending_title}:")
                print(f"    📊 Total rows checked: {len(data_rows)}")
                
                for i, row in enumerate(data_rows, start=1):
                    if row and "Promoted" in str(row[0]):
                        banner_rows.append((i, row[0]))
                
                if banner_rows:
                    print(f"    🎯 Banner rows found: {len(banner_rows)}")
                    for row_num, content in banner_rows:
                        print(f"      Row {row_num}: {content}")
                else:
                    print(f"    ⚠️  No banner rows found")
                    
                    # Show the last few rows to see what's there
                    if len(data_rows) > 1:
                        print(f"    📋 Last few rows:")
                        for i in range(max(1, len(data_rows) - 10), len(data_rows)):
                            if data_rows[i]:
                                print(f"      Row {i+1}: {data_rows[i][0] if data_rows[i] else '(empty)'}")
                
            except Exception as e:
                print(f"    ❌ Error checking banner rows: {e}")
                
        except Exception as e:
            print(f"  ❌ Error accessing spreadsheet: {e}")
        
        print()  # Empty line between companies


if __name__ == "__main__":
    check_banner_rows_extended()
