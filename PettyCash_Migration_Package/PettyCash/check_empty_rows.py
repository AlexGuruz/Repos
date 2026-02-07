#!/usr/bin/env python3
"""
Check Empty Rows
Examine the supposedly empty rows to see what data they actually contain
"""

import gspread
from google.oauth2.service_account import Credentials

def check_empty_rows():
    """Check what's actually in the supposedly empty rows."""
    print("🔍 CHECKING EMPTY ROWS")
    print("=" * 50)
    
    try:
        # Google Sheets setup
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('config/service_account.json', scopes=scope)
        gc = gspread.authorize(creds)
        
        # Sheet configuration
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        worksheet_name = "PETTY CASH"
        
        # Column mapping (0-based index)
        columns = {
            'initials': 0,    # Column A
            'date': 1,        # Column B
            'company': 2,     # Column C
            'source': 3,      # Column D
            'amount': 18      # Column S
        }
        
        # Open the spreadsheet
        spreadsheet = gc.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Get ALL data from the worksheet
        all_data = worksheet.get_all_values(value_render_option='FORMATTED_VALUE')
        
        # Check the specific rows that were marked as empty
        empty_row_numbers = [930, 1803, 1804, 1805]
        
        print(f"📋 EXAMINING ROWS: {empty_row_numbers}")
        print("-" * 50)
        
        for row_number in empty_row_numbers:
            row_index = row_number - 1  # Convert to 0-based index
            if row_index < len(all_data):
                row_data = all_data[row_index]
                
                print(f"\n📊 ROW {row_number}:")
                print(f"  Column A (initials): '{row_data[0] if len(row_data) > 0 else 'EMPTY'}'")
                print(f"  Column B (date): '{row_data[1] if len(row_data) > 1 else 'EMPTY'}'")
                print(f"  Column C (company): '{row_data[2] if len(row_data) > 2 else 'EMPTY'}'")
                print(f"  Column D (source): '{row_data[3] if len(row_data) > 3 else 'EMPTY'}'")
                print(f"  Column S (amount): '{row_data[18] if len(row_data) > 18 else 'EMPTY'}'")
                
                # Check if this row actually has meaningful data
                meaningful_fields = 0
                if row_data[1] and row_data[1].strip():  # date
                    meaningful_fields += 1
                if row_data[2] and row_data[2].strip():  # company
                    meaningful_fields += 1
                if row_data[3] and row_data[3].strip():  # source
                    meaningful_fields += 1
                if row_data[18] and row_data[18].strip():  # amount
                    meaningful_fields += 1
                
                print(f"  Meaningful fields: {meaningful_fields}/4")
                
                if meaningful_fields >= 3:
                    print(f"  ✅ This row has enough data to be a valid transaction!")
                else:
                    print(f"  ❌ This row is truly empty or has insufficient data")
            else:
                print(f"\n❌ ROW {row_number}: Row index out of range")
        
        print(f"\n💡 RECOMMENDATION:")
        print(f"  If these rows have valid date, company, source, and amount data,")
        print(f"  we should modify the logic to not require initials (Column A).")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_empty_rows() 