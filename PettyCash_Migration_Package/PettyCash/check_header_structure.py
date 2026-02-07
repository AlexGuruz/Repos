#!/usr/bin/env python3
"""
Check Header Structure
Examine the actual header structure of target sheets
"""

import logging
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/check_headers.log"),
        logging.StreamHandler()
    ]
)

def check_header_structure():
    """Check the actual header structure of target sheets."""
    print("CHECK HEADER STRUCTURE")
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
        
        # Target sheets to examine
        target_sheets = ['INCOME', 'NUGZ C.O.G.', '(A) CANNABIS DIST.', '(B) CANNABIS DIST.', 'NON CANNABIS']
        
        for sheet_name in target_sheets:
            print(f"\n{'='*60}")
            print(f"EXAMINING SHEET: {sheet_name}")
            print(f"{'='*60}")
            
            try:
                spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
                worksheet = None
                
                for ws in spreadsheet.worksheets():
                    if ws.title == sheet_name:
                        worksheet = ws
                        break
                
                if worksheet:
                    print(f"Sheet found: {worksheet.title}")
                    print(f"Dimensions: {worksheet.row_count} rows x {worksheet.col_count} columns")
                    
                    # Show first 10 rows to find headers
                    print(f"\nFirst 10 rows:")
                    for i in range(1, min(11, worksheet.row_count + 1)):
                        row_values = worksheet.row_values(i)
                        print(f"  Row {i:2d}: {row_values[:15]}...")  # First 15 columns
                    
                    # Look for potential header rows (rows with text that might be headers)
                    print(f"\nLooking for header patterns...")
                    for i in range(1, min(21, worksheet.row_count + 1)):
                        row_values = worksheet.row_values(i)
                        
                        # Check if this row contains potential header text
                        header_indicators = ['REGISTER', 'WHOLESALE', 'SQUARE', 'WALMART', 'CANNABIS', 'DIST', 'PAYROLL']
                        found_headers = []
                        
                        for col_idx, cell_value in enumerate(row_values):
                            if cell_value and isinstance(cell_value, str):
                                cell_upper = cell_value.upper()
                                for indicator in header_indicators:
                                    if indicator in cell_upper:
                                        found_headers.append(f"Col{col_idx+1}: '{cell_value}'")
                                        break
                        
                        if found_headers:
                            print(f"  Row {i:2d} potential headers: {found_headers}")
                    
                else:
                    print(f"❌ Sheet not found: {sheet_name}")
                    
            except Exception as e:
                print(f"❌ Error examining sheet {sheet_name}: {e}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        logging.error(f"Test failed: {e}")

def main():
    """Main function."""
    check_header_structure()

if __name__ == "__main__":
    main() 