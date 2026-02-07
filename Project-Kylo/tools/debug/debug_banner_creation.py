from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rules_promoter.service import _sheets_writeback


def debug_banner_creation():
    """Debug why banner rows aren't being created"""
    
    print("=== Debugging Banner Row Creation ===\n")
    
    # Test with NUGZ
    company_id = "NUGZ"
    promoted_count = 104
    
    print(f"🔍 Testing banner row creation for {company_id}")
    print(f"   📊 Promoted count: {promoted_count}")
    
    try:
        # Call the sheets writeback function with detailed error handling
        print(f"   🎯 Calling _sheets_writeback...")
        result = _sheets_writeback(company_id, promoted_count)
        print(f"   📋 Result: {result}")
        
        if result == "ok":
            print("   ✅ Function returned 'ok'")
        else:
            print(f"   ❌ Function failed: {result}")
            
    except Exception as e:
        print(f"   ❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    
    # Test with JGD
    company_id = "JGD"
    promoted_count = 26
    
    print(f"🔍 Testing banner row creation for {company_id}")
    print(f"   📊 Promoted count: {promoted_count}")
    
    try:
        # Call the sheets writeback function with detailed error handling
        print(f"   🎯 Calling _sheets_writeback...")
        result = _sheets_writeback(company_id, promoted_count)
        print(f"   📋 Result: {result}")
        
        if result == "ok":
            print("   ✅ Function returned 'ok'")
        else:
            print(f"   ❌ Function failed: {result}")
            
    except Exception as e:
        print(f"   ❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()


def check_actual_sheet_content():
    """Check what's actually in the sheets after banner creation attempt"""
    
    print("\n=== Checking Actual Sheet Content ===\n")
    
    from services.sheets.poster import _get_service, _extract_spreadsheet_id
    from scaffold.tools.sheets_cli import load_companies_config
    
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
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for checking rule management tabs
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        pending_title = f"{company_id} Pending"
        
        try:
            # Get the last 10 rows to see what was actually added
            data_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A:A"
            ).execute()
            
            data_rows = data_result.get('values', [])
            if data_rows:
                print(f"🔍 {company_id} - Last 10 rows:")
                for i in range(max(1, len(data_rows) - 9), len(data_rows) + 1):
                    if i <= len(data_rows) and data_rows[i-1]:
                        content = str(data_rows[i-1][0])[:80]
                        print(f"   Row {i}: {content}")
                    else:
                        print(f"   Row {i}: (empty)")
            else:
                print(f"🔍 {company_id} - No data found")
                
        except Exception as e:
            print(f"❌ Error checking {company_id}: {e}")
        
        print()


if __name__ == "__main__":
    debug_banner_creation()
    check_actual_sheet_content()
