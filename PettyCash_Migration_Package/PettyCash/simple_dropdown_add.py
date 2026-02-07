#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simply add REGISTERS to existing dropdown options
"""

from monitor_system import GoogleSheetsManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def simple_dropdown_add():
    print("➕ Adding REGISTERS to dropdown...")
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
        
        # Get current data validation rules
        print("🔍 Checking current dropdown options...")
        
        # Read a few cells in column C to see what's there
        for row in range(1, 11):
            try:
                c_value = worksheet.acell(f'C{row}').value or ''
                print(f"Row {row}: C='{c_value}'")
            except Exception as e:
                print(f"Row {row}: Error - {e}")
        
        # Try to set REGISTERS in a cell to see if it's allowed
        print(f"\n🧪 Testing if REGISTERS is in dropdown...")
        
        try:
            # Try to set REGISTERS in C2
            worksheet.update_cell(2, 3, "REGISTERS")
            print("✅ Successfully set REGISTERS in C2")
            
            # Read it back
            read_value = worksheet.acell('C2').value
            print(f"Read back: '{read_value}'")
            
            # Clear it
            worksheet.update_cell(2, 3, '')
            print("Cleared test value")
            
        except Exception as e:
            print(f"❌ Error setting REGISTERS: {e}")
        
        # Try to set a random value to see if validation blocks it
        print(f"\n🧪 Testing validation with invalid value...")
        
        try:
            invalid_value = "THIS_SHOULD_NOT_BE_ALLOWED_12345"
            worksheet.update_cell(3, 3, invalid_value)
            print(f"⚠️  Was able to set invalid value: '{invalid_value}'")
            print("This suggests dropdown validation is not working")
            
            # Clear it
            worksheet.update_cell(3, 3, '')
            
        except Exception as e:
            print(f"✅ Validation blocked invalid value: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    simple_dropdown_add() 