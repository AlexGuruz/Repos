#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct check of what's actually in the dropdown by reading data validation rules
"""

from monitor_system import GoogleSheetsManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def direct_dropdown_check():
    print("🔍 Direct Dropdown Check...")
    print("=" * 60)
    
    # Initialize Google Sheets Manager
    gsm = GoogleSheetsManager()
    
    try:
        if not gsm.gc:
            print("❌ Google Sheets client not authenticated")
            return
            
        # Get the JGD Truth spreadsheet
        jgd_truth_url = "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit?gid=1349136605#gid=1349136605"
        spreadsheet = gsm.gc.open_by_url(jgd_truth_url)
        worksheet = spreadsheet.sheet1
        
        print(f"📊 Sheet Title: {worksheet.title}")
        
        # Let's check what's actually in the sheet currently
        print(f"\n📋 Current data in JGD Truth sheet:")
        print("-" * 60)
        
        # Read first 10 rows
        for row in range(1, 11):
            try:
                a_value = worksheet.acell(f'A{row}').value or ''
                b_value = worksheet.acell(f'B{row}').value or ''
                c_value = worksheet.acell(f'C{row}').value or ''
                print(f"Row {row:2d}: A='{a_value}' | B='{b_value}' | C='{c_value}'")
            except Exception as e:
                print(f"Row {row}: Error reading - {e}")
        
        # Let's try to manually test the dropdown by setting a value
        print(f"\n🧪 Testing dropdown by trying to set a value...")
        
        try:
            # Try to set a test value in column C to see if validation works
            test_value = "REGISTERS"
            worksheet.update_cell(999, 3, test_value)  # Row 999, Column C
            print(f"✅ Successfully set '{test_value}' in C999")
            
            # Read it back to confirm
            read_value = worksheet.acell('C999').value
            print(f"Read back from C999: '{read_value}'")
            
            # Clean up - clear the test value
            worksheet.update_cell(999, 3, '')
            print("Cleaned up test value")
            
        except Exception as e:
            print(f"❌ Error testing dropdown: {e}")
        
        # Let's also try to set a value that should NOT be in the dropdown
        print(f"\n🧪 Testing with invalid value...")
        
        try:
            # Set a value that should trigger validation
            invalid_value = "INVALID_TEST_VALUE_12345"
            worksheet.update_cell(998, 3, invalid_value)
            print(f"Set invalid test value: '{invalid_value}'")
            
            # Read it back
            read_value = worksheet.acell('C998').value
            print(f"Read back: '{read_value}'")
            
            # Clean up
            worksheet.update_cell(998, 3, '')
            
        except Exception as e:
            print(f"Error testing validation: {e}")
        
    except Exception as e:
        print(f"❌ Error in direct dropdown check: {e}")

if __name__ == "__main__":
    direct_dropdown_check() 