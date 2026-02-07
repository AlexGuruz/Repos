#!/usr/bin/env python3
"""Clear Google Sheets before running the main program to prevent accumulation"""

import json
import logging
from pathlib import Path
from google_sheets_integration import GoogleSheetsIntegration

def setup_logging():
    """Setup logging for the clear operation."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/clear_sheets.log'),
            logging.StreamHandler()
        ]
    )

def load_layout_map():
    """Load the layout map to know which sheets and headers to clear."""
    try:
        with open('config/layout_map.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("❌ layout_map.json not found")
        return None
    except json.JSONDecodeError:
        logging.error("❌ Invalid JSON in layout_map.json")
        return None

def clear_google_sheets():
    """Clear all target cells in Google Sheets before processing."""
    
    logging.info("🧹 STARTING GOOGLE SHEETS CLEAR OPERATION")
    logging.info("=" * 50)
    
    # Load layout map
    layout_map = load_layout_map()
    if not layout_map:
        logging.error("❌ Cannot proceed without layout map")
        return False
    
    try:
        # Initialize Google Sheets integration
        sheets_integration = GoogleSheetsIntegration()
        
        # Get the target spreadsheet
        target_spreadsheet = sheets_integration.get_target_spreadsheet()
        if not target_spreadsheet:
            logging.error("❌ Cannot access target spreadsheet")
            return False
        
        logging.info(f"✅ Connected to spreadsheet: {target_spreadsheet.title}")
        
        total_cells_cleared = 0
        
        # Clear each sheet in the layout map
        for sheet_name, sheet_data in layout_map.items():
            logging.info(f"📋 Clearing sheet: {sheet_name}")
            
            try:
                # Get the worksheet
                worksheet = target_spreadsheet.worksheet(sheet_name)
                
                # Get all headers for this sheet
                headers = sheet_data.get('headers', [])
                
                # Clear each header column (starting from row 20, since headers are in row 19)
                for header in headers:
                    try:
                        # Find the column for this header
                        header_row = worksheet.row_values(19)  # Headers are in row 19
                        
                        if header in header_row:
                            col_index = header_row.index(header) + 1  # Convert to 1-based index
                            
                            # Clear the entire column from row 20 onwards
                            # Get the last row with data
                            all_values = worksheet.get_all_values()
                            last_row = len(all_values)
                            
                            if last_row > 19:  # Only clear if there are rows below headers
                                # Create range to clear (from row 20 to last row)
                                range_to_clear = f"{chr(64 + col_index)}20:{chr(64 + col_index)}{last_row}"
                                
                                # Clear the range
                                worksheet.batch_clear([range_to_clear])
                                
                                cells_in_column = last_row - 19
                                total_cells_cleared += cells_in_column
                                
                                logging.info(f"    ✅ Cleared {header} column ({cells_in_column} cells)")
                            else:
                                logging.info(f"    ⚠️  No data to clear for {header}")
                        else:
                            logging.warning(f"    ⚠️  Header '{header}' not found in sheet {sheet_name}")
                            
                    except Exception as e:
                        logging.error(f"    ❌ Error clearing header '{header}': {e}")
                        continue
                        
            except Exception as e:
                logging.error(f"❌ Error accessing sheet '{sheet_name}': {e}")
                continue
        
        logging.info("=" * 50)
        logging.info(f"✅ CLEAR OPERATION COMPLETED")
        logging.info(f"📊 Total cells cleared: {total_cells_cleared}")
        logging.info("🎯 Google Sheets are now ready for fresh data input")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Fatal error during clear operation: {e}")
        return False

def main():
    """Main function to clear Google Sheets."""
    setup_logging()
    
    print("🧹 GOOGLE SHEETS CLEAR OPERATION")
    print("=" * 40)
    print("This will clear all target cells in Google Sheets")
    print("to prevent data accumulation from partial runs.")
    print()
    
    # Ask for confirmation
    response = input("Do you want to proceed? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Operation cancelled")
        return False
    
    success = clear_google_sheets()
    
    if success:
        print("\n✅ Google Sheets cleared successfully!")
        print("🎯 Ready to run the main program with fresh sheets")
    else:
        print("\n❌ Clear operation failed!")
        print("⚠️  Please check the logs and try again")
    
    return success

if __name__ == "__main__":
    main() 