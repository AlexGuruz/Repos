#!/usr/bin/env python3
"""Safe Google Sheets reset - reads existing values and subtracts them before adding new ones"""

import json
import logging
from pathlib import Path
from google_sheets_integration import GoogleSheetsIntegration

def setup_logging():
    """Setup logging for the safe reset operation."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/safe_sheets_reset.log'),
            logging.StreamHandler()
        ]
    )

def load_layout_map():
    """Load the layout map to know which sheets and headers to process."""
    try:
        with open('config/layout_map.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("❌ layout_map.json not found")
        return None
    except json.JSONDecodeError:
        logging.error("❌ Invalid JSON in layout_map.json")
        return None

def create_compensation_file():
    """Create a file with existing values that need to be subtracted."""
    
    logging.info("🔄 CREATING COMPENSATION FILE FOR SAFE RESET")
    logging.info("=" * 55)
    
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
        
        compensation_data = {}
        total_cells_read = 0
        
        # Read each sheet in the layout map
        for sheet_name, sheet_data in layout_map.items():
            logging.info(f"📋 Reading sheet: {sheet_name}")
            
            try:
                # Get the worksheet
                worksheet = target_spreadsheet.worksheet(sheet_name)
                
                # Get all headers for this sheet
                headers = sheet_data.get('headers', [])
                
                sheet_compensation = {}
                
                # Read each header column (starting from row 20, since headers are in row 19)
                for header in headers:
                    try:
                        # Find the column for this header
                        header_row = worksheet.row_values(19)  # Headers are in row 19
                        
                        if header in header_row:
                            col_index = header_row.index(header) + 1  # Convert to 1-based index
                            
                            # Read the entire column from row 20 onwards
                            all_values = worksheet.get_all_values()
                            last_row = len(all_values)
                            
                            if last_row > 19:  # Only read if there are rows below headers
                                # Read the column values
                                col_letter = chr(64 + col_index)
                                range_to_read = f"{col_letter}20:{col_letter}{last_row}"
                                
                                try:
                                    # Read the values
                                    values = worksheet.get(range_to_read)
                                    
                                    if values:
                                        # Store the values that need to be compensated
                                        compensation_values = []
                                        for i, row in enumerate(values):
                                            if row and row[0]:  # If cell has a value
                                                try:
                                                    # Try to convert to float (for amounts)
                                                    value = float(row[0])
                                                    compensation_values.append({
                                                        'row': i + 20,  # Actual row number
                                                        'value': value
                                                    })
                                                except (ValueError, TypeError):
                                                    # Skip non-numeric values
                                                    continue
                                        
                                        if compensation_values:
                                            sheet_compensation[header] = compensation_values
                                            total_cells_read += len(compensation_values)
                                            logging.info(f"    ✅ Read {header} column ({len(compensation_values)} values)")
                                        else:
                                            logging.info(f"    ⚠️  No numeric values found for {header}")
                                    else:
                                        logging.info(f"    ⚠️  No data found for {header}")
                                        
                                except Exception as e:
                                    logging.error(f"    ❌ Error reading {header}: {e}")
                                    continue
                            else:
                                logging.info(f"    ⚠️  No data to read for {header}")
                        else:
                            logging.warning(f"    ⚠️  Header '{header}' not found in sheet {sheet_name}")
                            
                    except Exception as e:
                        logging.error(f"    ❌ Error processing header '{header}': {e}")
                        continue
                
                if sheet_compensation:
                    compensation_data[sheet_name] = sheet_compensation
                        
            except Exception as e:
                logging.error(f"❌ Error accessing sheet '{sheet_name}': {e}")
                continue
        
        # Save compensation data to file
        compensation_file = Path("config/compensation_data.json")
        compensation_file.parent.mkdir(exist_ok=True)
        
        with open(compensation_file, 'w') as f:
            json.dump(compensation_data, f, indent=2)
        
        logging.info("=" * 55)
        logging.info(f"✅ COMPENSATION FILE CREATED")
        logging.info(f"📊 Total values to compensate: {total_cells_read}")
        logging.info(f"📁 Saved to: {compensation_file}")
        logging.info("🎯 Ready for safe processing - existing values will be subtracted")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Fatal error during compensation file creation: {e}")
        return False

def main():
    """Main function to create compensation file."""
    setup_logging()
    
    print("🔄 SAFE GOOGLE SHEETS RESET")
    print("=" * 40)
    print("This will read existing values and create a")
    print("compensation file to prevent data accumulation.")
    print("NO CELLS WILL BE CLEARED - your formulas are safe!")
    print()
    
    # Ask for confirmation
    response = input("Do you want to proceed? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Operation cancelled")
        return False
    
    success = create_compensation_file()
    
    if success:
        print("\n✅ Compensation file created successfully!")
        print("🎯 Your formulas and data are completely safe")
        print("📁 Check config/compensation_data.json for details")
    else:
        print("\n❌ Compensation file creation failed!")
        print("⚠️  Please check the logs and try again")
    
    return success

if __name__ == "__main__":
    main() 