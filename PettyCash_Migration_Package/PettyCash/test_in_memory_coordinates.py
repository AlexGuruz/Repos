#!/usr/bin/env python3
"""
Test In-Memory Coordinates
Test the new in-memory coordinate calculation functionality
"""

from google_sheets_integration import GoogleSheetsIntegration
from csv_downloader_fixed import CSVDownloader

def main():
    """Test in-memory coordinate calculation."""
    print("TESTING IN-MEMORY COORDINATE CALCULATION")
    print("=" * 50)
    
    try:
        # Initialize components
        sheets_integration = GoogleSheetsIntegration()
        downloader = CSVDownloader()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Connected to Google Sheets successfully")
        
        # Download some transactions
        transactions = downloader.download_petty_cash_data()
        if not transactions:
            print("No transactions found")
            return
        
        print(f"Downloaded {len(transactions)} transactions")
        
        # Test in-memory coordinate calculation
        print("\nTesting in-memory coordinate calculation...")
        
        # Test individual calculation
        test_cases = [
            ('INCOME', 'REGISTERS', '01/01/25'),
            ('INCOME', '(N) WHOLESALE', '01/01/25'),
            ('NUGZ C.O.G.', 'WALMART', '01/01/25'),
        ]
        
        print("Individual calculations:")
        for sheet, header, date in test_cases:
            coords = sheets_integration.calculate_target_coordinates_in_memory(sheet, header, date)
            if coords:
                print(f"✅ {sheet} -> {header}: Row {coords['row']}, Col {coords['col']}")
            else:
                print(f"❌ {sheet} -> {header}: Not found")
        
        # Test batch calculation
        print("\nBatch calculations:")
        coordinate_requests = []
        for sheet, header, date in test_cases:
            coordinate_requests.append({
                'target_sheet': sheet,
                'target_header': header,
                'date': date
            })
        
        batch_results = sheets_integration.batch_calculate_coordinates_in_memory(coordinate_requests)
        
        for request_key, coords in batch_results.items():
            if coords:
                print(f"✅ {request_key}: Row {coords['row']}, Col {coords['col']}")
            else:
                print(f"❌ {request_key}: Not found")
        
        # Compare with API method (if available)
        print("\nComparing with API method (if available):")
        for sheet, header, date in test_cases[:1]:  # Test just one to avoid rate limits
            try:
                api_coords = sheets_integration.find_target_cell_coordinates(sheet, header, date)
                memory_coords = sheets_integration.calculate_target_coordinates_in_memory(sheet, header, date)
                
                if api_coords and memory_coords:
                    print(f"✅ {sheet} -> {header}:")
                    print(f"  API: Row {api_coords['row']}, Col {api_coords['col']}")
                    print(f"  Memory: Row {memory_coords['row']}, Col {memory_coords['col']}")
                    print(f"  Match: {api_coords['row'] == memory_coords['row'] and api_coords['col'] == memory_coords['col']}")
                elif api_coords:
                    print(f"⚠️ {sheet} -> {header}: API found, Memory not found")
                elif memory_coords:
                    print(f"⚠️ {sheet} -> {header}: Memory found, API not found")
                else:
                    print(f"❌ {sheet} -> {header}: Neither method found")
            except Exception as e:
                print(f"⚠️ API method failed for {sheet} -> {header}: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 