#!/usr/bin/env python3
"""
Direct Cell Test
Test direct Google Sheets cell updates
"""

import logging
import time
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/direct_cell_test.log"),
        logging.StreamHandler()
    ]
)

def direct_cell_test():
    """Test direct cell updates."""
    print("DIRECT CELL TEST")
    print("=" * 80)
    
    try:
        # Initialize Google Sheets integration
        print("Initializing Google Sheets integration...")
        sheets_integration = GoogleSheetsIntegration()
        
        # Test connection
        print("Testing connection...")
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Connection successful")
        
        # List all sheets
        print("\nAvailable sheets:")
        print("-" * 40)
        try:
            spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
            for ws in spreadsheet.worksheets():
                print(f"  - {ws.title}")
        except Exception as e:
            print(f"Error listing sheets: {e}")
            return
        
        # Try to update a cell in the first sheet
        print(f"\nTesting direct cell update...")
        try:
            spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
            first_sheet = spreadsheet.worksheets()[0]
            
            print(f"Using sheet: {first_sheet.title}")
            print(f"Sheet dimensions: {first_sheet.row_count} rows x {first_sheet.col_count} columns")
            
            # Check current value in cell A1
            current_value = first_sheet.cell(1, 1).value
            print(f"Current value in A1: '{current_value}'")
            
            # Try to update cell A1 with a test value
            test_value = "TEST UPDATE " + str(int(time.time()))
            print(f"Attempting to update A1 with: '{test_value}'")
            
            first_sheet.update_cell(1, 1, test_value)
            print("✅ Direct update completed")
            
            # Check if it worked
            time.sleep(2)
            new_value = first_sheet.cell(1, 1).value
            print(f"New value in A1: '{new_value}'")
            
            if new_value == test_value:
                print("✅ Direct cell update WORKED!")
            else:
                print("❌ Direct cell update failed")
                
        except Exception as e:
            print(f"❌ Error with direct update: {e}")
        
        # Now test the update_single_cell method
        print(f"\nTesting update_single_cell method...")
        try:
            success = sheets_integration.update_single_cell(
                first_sheet.title,
                2,  # Row 2
                2,  # Column 2 (B2)
                123.45
            )
            
            if success:
                print("✅ update_single_cell reported success")
                
                # Check the cell
                time.sleep(2)
                cell_value = first_sheet.cell(2, 2).value
                print(f"Value in B2: '{cell_value}'")
            else:
                print("❌ update_single_cell failed")
                
        except Exception as e:
            print(f"❌ Error with update_single_cell: {e}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        logging.error(f"Test failed: {e}")

def main():
    """Main function."""
    direct_cell_test()

if __name__ == "__main__":
    main() 