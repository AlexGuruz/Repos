#!/usr/bin/env python3
"""
Test Date Format
Check what date format is being used and test date finding
"""

from google_sheets_integration import GoogleSheetsIntegration
from csv_downloader_fixed import CSVDownloader

def main():
    """Test date format and finding."""
    print("TESTING DATE FORMAT")
    print("=" * 30)
    
    try:
        # Initialize components
        sheets_integration = GoogleSheetsIntegration()
        downloader = CSVDownloader()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Connected to Google Sheets successfully")
        
        # Download some transactions to see date format
        transactions = downloader.download_petty_cash_data()
        if not transactions:
            print("No transactions found")
            return
        
        print(f"Downloaded {len(transactions)} transactions")
        
        # Check date formats in transactions
        print("\nDate formats found in transactions:")
        date_formats = set()
        for i, transaction in enumerate(transactions[:10]):
            date_str = transaction.get('date', 'N/A')
            date_formats.add(date_str)
            print(f"  {i+1}. Row {transaction.get('row_number', 'N/A')}: {date_str}")
        
        print(f"\nUnique date formats: {date_formats}")
        
        # Test date finding with a specific date
        test_date = "1/25/25"  # Format from Google Sheets
        print(f"\nTesting date finding for: {test_date}")
        
        # Parse the test date
        if '/' in test_date and len(test_date.split('/')) == 3:
            parts = test_date.split('/')
            month = int(parts[0])
            day = int(parts[1])
            year_str = parts[2]
            
            if len(year_str) == 2:
                year = 2000 + int(year_str)
            else:
                year = int(year_str)
            
            print(f"Parsed: Month={month}, Day={day}, Year={year}")
            
            # Test finding this date in a sheet
            test_sheet = "INCOME"
            test_header = "REGISTERS"
            
            print(f"\nTesting date row finding for {test_sheet} -> {test_header}")
            coords = sheets_integration.find_target_cell_coordinates(test_sheet, test_header, test_date)
            
            if coords:
                print(f"SUCCESS: Found coordinates")
                print(f"  Sheet: {coords['sheet']}")
                print(f"  Row: {coords['row']}")
                print(f"  Column: {coords['col']}")
                print(f"  Header: {coords['header']}")
            else:
                print(f"FAILED: Could not find coordinates")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 