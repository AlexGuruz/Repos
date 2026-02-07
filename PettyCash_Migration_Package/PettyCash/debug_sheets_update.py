#!/usr/bin/env python3
"""
Debug Google Sheets Updates
Investigate why updates aren't visible in Google Sheets
"""

import logging
import time
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/debug_sheets.log"),
        logging.StreamHandler()
    ]
)

def debug_sheets_update():
    """Debug Google Sheets updates."""
    print("DEBUG GOOGLE SHEETS UPDATES")
    print("=" * 80)
    
    try:
        # Initialize components
        print("Initializing components...")
        db_manager = DatabaseManager()
        csv_downloader = CSVDownloader()
        ai_matcher = AIEnhancedRuleMatcher()
        sheets_integration = GoogleSheetsIntegration()
        
        # Test Google Sheets connection
        print("Testing Google Sheets connection...")
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Google Sheets connection successful")
        
        # List all available sheets
        print("\nAvailable sheets:")
        print("-" * 40)
        try:
            spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
            for ws in spreadsheet.worksheets():
                print(f"  - {ws.title}")
        except Exception as e:
            print(f"Error listing sheets: {e}")
        
        # Download one transaction for testing
        print("\nDownloading one transaction for testing...")
        all_transactions = csv_downloader.download_petty_cash_data()
        if not all_transactions:
            print("No transactions downloaded")
            return
        
        test_transaction = all_transactions[1]  # Use second transaction
        print(f"Testing with: {test_transaction['source']} (${test_transaction['amount']:.2f})")
        print(f"Date: {test_transaction['date']}")
        
        # Load rules
        print("Loading rules...")
        if not ai_matcher.load_rules_from_database():
            print("Failed to load rules")
            return
        
        # Match transaction
        match_result = ai_matcher.match_transaction(test_transaction)
        if not match_result:
            print("No match found for test transaction")
            return
        
        rule = match_result['rule']
        print(f"Matched to: {rule['target_sheet']}/{rule['target_header']}")
        
        # Try to find the actual target cell coordinates
        print(f"\nLooking for target cell coordinates...")
        cell_coords = sheets_integration.find_target_cell_coordinates(
            rule['target_sheet'],
            rule['target_header'],
            test_transaction['date']
        )
        
        if cell_coords:
            print(f"Found coordinates: Sheet={cell_coords['sheet']}, Row={cell_coords['row']}, Col={cell_coords['col']}")
            
            # Check what's currently in that cell
            try:
                spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
                worksheet = None
                
                for ws in spreadsheet.worksheets():
                    if ws.title == cell_coords['sheet']:
                        worksheet = ws
                        break
                
                if worksheet:
                    current_value = worksheet.cell(cell_coords['row'], cell_coords['col']).value
                    print(f"Current value in cell: '{current_value}'")
                    
                    # Try to update the cell
                    print(f"Attempting to update cell...")
                    success = sheets_integration.update_single_cell(
                        cell_coords['sheet'],
                        cell_coords['row'],
                        cell_coords['col'],
                        test_transaction['amount']
                    )
                    
                    if success:
                        print("✅ Cell update reported successful")
                        
                        # Check the cell again
                        time.sleep(2)  # Wait a moment
                        new_value = worksheet.cell(cell_coords['row'], cell_coords['col']).value
                        print(f"New value in cell: '{new_value}'")
                        
                        if new_value != current_value:
                            print("✅ Cell value actually changed!")
                        else:
                            print("❌ Cell value did not change")
                    else:
                        print("❌ Cell update failed")
                else:
                    print(f"❌ Could not find worksheet: {cell_coords['sheet']}")
                    
            except Exception as e:
                print(f"❌ Error checking/updating cell: {e}")
        else:
            print("❌ Could not find target cell coordinates")
            
            # Try to examine the sheet structure
            print(f"\nExamining sheet structure for: {rule['target_sheet']}")
            try:
                spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
                worksheet = None
                
                for ws in spreadsheet.worksheets():
                    if ws.title == rule['target_sheet']:
                        worksheet = ws
                        break
                
                if worksheet:
                    print(f"Sheet found: {worksheet.title}")
                    print(f"Sheet dimensions: {worksheet.row_count} rows x {worksheet.col_count} columns")
                    
                    # Show first few rows
                    print("\nFirst 5 rows:")
                    for i in range(1, min(6, worksheet.row_count + 1)):
                        row_values = worksheet.row_values(i)
                        print(f"  Row {i}: {row_values[:10]}...")  # First 10 columns
                else:
                    print(f"❌ Sheet not found: {rule['target_sheet']}")
                    
            except Exception as e:
                print(f"❌ Error examining sheet: {e}")
        
    except Exception as e:
        print(f"Debug failed: {e}")
        logging.error(f"Debug failed: {e}")

def main():
    """Main function."""
    debug_sheets_update()

if __name__ == "__main__":
    main() 