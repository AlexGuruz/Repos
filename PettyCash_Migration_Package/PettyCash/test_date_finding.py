#!/usr/bin/env python3
"""
Test Date Finding
Test if the date finding logic is working correctly
"""

from google_sheets_integration import GoogleSheetsIntegration

def main():
    """Test date finding logic."""
    print("TESTING DATE FINDING LOGIC")
    print("=" * 40)
    
    try:
        # Initialize Google Sheets integration
        sheets_integration = GoogleSheetsIntegration()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Connected to Google Sheets successfully")
        
        # Test specific date finding scenarios
        test_cases = [
            ('INCOME', '(N) WHOLESALE', '01/01/25'),
            ('NUGZ C.O.G.', 'WALMART', '01/01/25'),
            ('INCOME', 'REGISTERS', '01/01/25'),
        ]
        
        for sheet_name, header_name, date_str in test_cases:
            print(f"\nTesting: {sheet_name} -> {header_name} for date {date_str}")
            print("-" * 50)
            
            # Find target cell coordinates
            coords = sheets_integration.find_target_cell_coordinates(sheet_name, header_name, date_str)
            
            if coords:
                print(f"SUCCESS: Found coordinates")
                print(f"  Sheet: {coords['sheet']}")
                print(f"  Row: {coords['row']}")
                print(f"  Column: {coords['col']}")
                print(f"  Header: {coords['header']}")
            else:
                print(f"FAILED: Could not find coordinates")
        
        print(f"\nDate finding test completed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 