#!/usr/bin/env python3
"""
Test Layout Coordinates
Test in-memory coordinate calculation using the layout map
"""

import json
from google_sheets_integration import GoogleSheetsIntegration

def main():
    """Test in-memory coordinate calculation with layout map."""
    print("TESTING LAYOUT COORDINATES")
    print("=" * 40)
    
    try:
        # Load layout map directly
        print("Loading layout map...")
        with open('config/layout_map.json', 'r') as f:
            layout_map = json.load(f)
        
        print(f"Loaded layout map with {len(layout_map)} sheets")
        
        # Test specific sheets
        test_cases = [
            ('INCOME', 'REGISTERS', '01/01/25'),
            ('INCOME', '(N) WHOLESALE', '01/01/25'),
            ('NUGZ C.O.G.', 'WALMART', '01/01/25'),
            ('INCOME', 'REGISTERS', '01/25/25'),
            ('NUGZ C.O.G.', 'WALMART', '01/25/25'),
        ]
        
        print("\nTesting coordinate calculation:")
        for sheet, header, date in test_cases:
            print(f"\n{sheet} -> {header} for {date}:")
            
            # Check if sheet exists
            if sheet not in layout_map:
                print(f"  ❌ Sheet '{sheet}' not found in layout map")
                continue
            
            sheet_data = layout_map[sheet]
            headers = sheet_data.get('headers', {})
            dates = sheet_data.get('dates', {})
            
            # Check if header exists
            if header not in headers:
                print(f"  ❌ Header '{header}' not found in sheet '{sheet}'")
                print(f"  Available headers: {list(headers.keys())}")
                continue
            
            # Check if date exists
            if date not in dates:
                print(f"  ❌ Date '{date}' not found in sheet '{sheet}'")
                print(f"  Available dates: {list(dates.keys())[:10]}...")
                continue
            
            # Calculate coordinates
            col = headers[header]
            row = dates[date]
            
            print(f"  ✅ Found coordinates: Row {row}, Col {col}")
            print(f"  📍 Cell: {chr(64+col)}{row}")
        
        # Test with Google Sheets integration
        print("\nTesting with Google Sheets integration:")
        sheets_integration = GoogleSheetsIntegration()
        
        for sheet, header, date in test_cases[:3]:  # Test first 3
            print(f"\n{sheet} -> {header} for {date}:")
            
            coords = sheets_integration.calculate_target_coordinates_in_memory(sheet, header, date)
            if coords:
                print(f"  ✅ Calculated: Row {coords['row']}, Col {coords['col']}")
                print(f"  📍 Cell: {chr(64+coords['col'])}{coords['row']}")
            else:
                print(f"  ❌ Not found")
        
        # Test batch calculation
        print("\nTesting batch calculation:")
        coordinate_requests = []
        for sheet, header, date in test_cases:
            coordinate_requests.append({
                'target_sheet': sheet,
                'target_header': header,
                'date': date
            })
        
        batch_results = sheets_integration.batch_calculate_coordinates_in_memory(coordinate_requests)
        
        successful = 0
        for request_key, coords in batch_results.items():
            if coords:
                successful += 1
                print(f"  ✅ {request_key}: Row {coords['row']}, Col {coords['col']}")
            else:
                print(f"  ❌ {request_key}: Not found")
        
        print(f"\nBatch results: {successful}/{len(batch_results)} successful ({successful/len(batch_results)*100:.1f}%)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 