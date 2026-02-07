#!/usr/bin/env python3
"""
Check Sheet Dates
Check what dates are available in the target sheets
"""

from google_sheets_integration import GoogleSheetsIntegration

def main():
    """Check dates in target sheets."""
    print("CHECKING DATES IN TARGET SHEETS")
    print("=" * 40)
    
    try:
        # Initialize Google Sheets integration
        sheets_integration = GoogleSheetsIntegration()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        # Check specific sheets that should have dates
        target_sheets = ['INCOME', 'NUGZ C.O.G.', 'JGD C.O.G.', 'PUFFIN C.O.G.']
        
        for sheet_name in target_sheets:
            print(f"\nChecking sheet: {sheet_name}")
            print("-" * 30)
            
            try:
                # Get the worksheet using the correct method
                spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.financials_spreadsheet_url)
                worksheet = spreadsheet.worksheet(sheet_name)
                if not worksheet:
                    print(f"  Sheet '{sheet_name}' not found")
                    continue
                
                # Get all values
                all_values = worksheet.get_all_values()
                
                if not all_values:
                    print(f"  Sheet '{sheet_name}' is empty")
                    continue
                
                # Look for date column (usually column A or B)
                date_column = 0  # Assume dates are in column A
                
                # Check first 20 rows for dates
                print(f"  First 20 rows in column {date_column + 1}:")
                for i, row in enumerate(all_values[:20]):
                    if len(row) > date_column:
                        cell_value = row[date_column]
                        if cell_value:
                            print(f"    Row {i+1}: '{cell_value}'")
                        else:
                            print(f"    Row {i+1}: (empty)")
                    else:
                        print(f"    Row {i+1}: (no data)")
                
                # Also check if there are any dates in the sheet
                all_dates = []
                for i, row in enumerate(all_values):
                    if len(row) > date_column:
                        cell_value = row[date_column]
                        if cell_value and '/' in str(cell_value):
                            all_dates.append((i+1, cell_value))
                
                if all_dates:
                    print(f"  Found {len(all_dates)} date entries:")
                    for row_num, date_val in all_dates[:10]:  # Show first 10
                        print(f"    Row {row_num}: {date_val}")
                    if len(all_dates) > 10:
                        print(f"    ... and {len(all_dates) - 10} more")
                else:
                    print(f"  No date entries found in column {date_column + 1}")
                
            except Exception as e:
                print(f"  Error checking sheet '{sheet_name}': {e}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 