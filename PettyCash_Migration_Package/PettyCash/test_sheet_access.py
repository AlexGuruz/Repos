#!/usr/bin/env python3
import gspread
from google.oauth2.service_account import Credentials

def test_sheet_access():
    print("Testing Google Sheets API Access")
    print("=" * 40)
    
    try:
        # Setup credentials
        creds = Credentials.from_service_account_file(
            'config/service_account.json', 
            scopes=['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
        gc = gspread.authorize(creds)
        
        print("✅ Service account authenticated successfully")
        
        # Test Financials sheet
        print("\nTesting Financials sheet access...")
        sheet = gc.open_by_key('1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU')
        print(f"✅ Successfully opened Financials sheet")
        print(f"   Title: {sheet.title}")
        print(f"   URL: {sheet.url}")
        
        # List worksheets
        worksheets = sheet.worksheets()
        print(f"   Worksheets: {[ws.title for ws in worksheets]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_sheet_access() 