from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service, _extract_spreadsheet_id
from scaffold.tools.sheets_cli import load_companies_config


def verify_sheets_directly():
    """Directly verify what's in the Google Sheets"""
    
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
    
    print("=== Direct Google Sheets Verification ===\n")
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for checking rule management tabs
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        print(f"🔍 Checking {company_id}")
        print(f"   📋 Spreadsheet ID: {spreadsheet_id}")
        print(f"   🔗 URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
        
        try:
            # Get all sheet names first
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = meta.get("sheets", [])
            
            print(f"   📊 All tabs in spreadsheet:")
            for sheet in sheets:
                props = sheet.get("properties", {})
                title = props.get("title", "")
                sheet_id = props.get("sheetId", "")
                print(f"      - {title} (ID: {sheet_id})")
            
            # Look for pending and active tabs with new naming convention
            pending_patterns = [
                f"{company_id} Pending"
            ]
            
            active_patterns = [
                f"{company_id} Active"
            ]
            
            pending_tab = None
            active_tab = None
            
            for sheet in sheets:
                props = sheet.get("properties", {})
                title = props.get("title", "")
                
                if title in pending_patterns:
                    pending_tab = title
                elif title in active_patterns:
                    active_tab = title
            
            print(f"\n   🎯 Found tabs:")
            print(f"      Pending: {pending_tab or 'NOT FOUND'}")
            print(f"      Active: {active_tab or 'NOT FOUND'}")
            
            # Check pending tab if found
            if pending_tab:
                print(f"\n   📋 Checking {pending_tab}:")
                try:
                    # Get first 20 rows to see what's actually there
                    data_result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"{pending_tab}!A1:A20"
                    ).execute()
                    
                    data_rows = data_result.get('values', [])
                    print(f"      📊 First 20 rows:")
                    for i, row in enumerate(data_rows, start=1):
                        if row:
                            content = str(row[0])[:100]  # Truncate long content
                            print(f"        Row {i}: {content}")
                        else:
                            print(f"        Row {i}: (empty)")
                    
                    # Also check for any rows with "Promoted" in the entire sheet
                    print(f"\n      🔍 Searching for promotion messages...")
                    full_result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"{pending_tab}!A:A"
                    ).execute()
                    
                    full_rows = full_result.get('values', [])
                    promotion_rows = []
                    for i, row in enumerate(full_rows, start=1):
                        if row and "Promoted" in str(row[0]):
                            promotion_rows.append((i, str(row[0])))
                    
                    if promotion_rows:
                        print(f"      ✅ Found {len(promotion_rows)} promotion messages:")
                        for row_num, content in promotion_rows:
                            print(f"        Row {row_num}: {content}")
                    else:
                        print(f"      ❌ No promotion messages found")
                        
                except Exception as e:
                    print(f"      ❌ Error reading {pending_tab}: {e}")
            
            # Check active tab if found
            if active_tab:
                print(f"\n   📊 Checking {active_tab}:")
                try:
                    # Get first 10 rows
                    data_result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"{active_tab}!A1:H10"
                    ).execute()
                    
                    data_rows = data_result.get('values', [])
                    print(f"      📊 First 10 rows:")
                    for i, row in enumerate(data_rows, start=1):
                        if row:
                            content = str(row)[:100]  # Truncate long content
                            print(f"        Row {i}: {content}")
                        else:
                            print(f"        Row {i}: (empty)")
                            
                except Exception as e:
                    print(f"      ❌ Error reading {active_tab}: {e}")
            
        except Exception as e:
            print(f"  ❌ Error accessing spreadsheet: {e}")
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    verify_sheets_directly()
