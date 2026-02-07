#!/usr/bin/env python3
"""
Simple test script to check Google Sheets connection
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

def test_connection():
    print("🔍 Testing Google Sheets Connection")
    print("=" * 50)
    
    try:
        # Check if service account file exists
        service_account_file = 'config/service_account.json'
        if not Path(service_account_file).exists():
            print(f"❌ Service account file not found: {service_account_file}")
            return False
        
        print(f"✅ Service account file found: {service_account_file}")
        
        # Setup credentials
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(service_account_file, scopes=scope)
        gc = gspread.authorize(creds)
        
        print("✅ Credentials loaded successfully")
        
        # Test connection to spreadsheet
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        
        print(f"🔗 Connecting to spreadsheet: {spreadsheet_url}")
        spreadsheet = gc.open_by_url(spreadsheet_url)
        
        print("✅ Successfully connected to spreadsheet")
        
        # Get sheet names
        sheets = spreadsheet.worksheets()
        print(f"📋 Found {len(sheets)} sheets:")
        
        for i, sheet in enumerate(sheets[:10]):  # Show first 10
            print(f"  {i+1}. {sheet.title}")
        
        if len(sheets) > 10:
            print(f"  ... and {len(sheets) - 10} more")
        
        # Test reading from PETTY CASH sheet
        print("\n📊 Testing PETTY CASH sheet access...")
        petty_cash_sheet = None
        
        for sheet in sheets:
            if sheet.title == 'PETTY CASH':
                petty_cash_sheet = sheet
                break
        
        if petty_cash_sheet:
            print("✅ PETTY CASH sheet found")
            
            # Try to read some data
            try:
                values = petty_cash_sheet.get_all_values()
                print(f"✅ Successfully read {len(values)} rows from PETTY CASH sheet")
                
                if values:
                    print(f"📝 First row has {len(values[0])} columns")
                    print(f"📝 Sample data: {values[0][:5]}...")  # First 5 columns
                
            except Exception as e:
                print(f"❌ Error reading PETTY CASH sheet: {e}")
        else:
            print("❌ PETTY CASH sheet not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    if success:
        print("\n✅ All connection tests passed!")
    else:
        print("\n❌ Connection tests failed!") 