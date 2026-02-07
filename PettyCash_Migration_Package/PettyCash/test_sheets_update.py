#!/usr/bin/env python3
"""
Test Google Sheets Update
Test if the Google Sheets integration is actually updating sheets
"""

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def main():
    """Test Google Sheets updates."""
    print("TESTING GOOGLE SHEETS UPDATES")
    print("=" * 40)
    
    try:
        # Initialize the sorter
        sorter = PettyCashSorterFinal()
        
        # Initialize system
        print("Initializing system...")
        if not sorter.initialize_system():
            print("System initialization failed")
            return
        
        print("System initialized successfully")
        
        # Test with a small batch first
        print("\nTesting with 5 transactions...")
        result = sorter.test_small_batch(5)
        
        print(f"Test result: {result}")
        
        if result.get('status') == 'success':
            print("Small batch test successful!")
            
            # Check if any sheets were updated
            sheets_updated = result.get('sheets_updated', 0)
            print(f"Sheets updated: {sheets_updated}")
            
            if sheets_updated > 0:
                print("SUCCESS: Google Sheets updates are working!")
            else:
                print("WARNING: No sheets were updated - there may be an issue")
                
            # Show detailed results
            if 'match_results' in result:
                matched = result['match_results'].get('matched', [])
                unmatched = result['match_results'].get('unmatched', [])
                print(f"Matched transactions: {len(matched)}")
                print(f"Unmatched transactions: {len(unmatched)}")
                
                # Show what was matched
                for match_data in matched[:3]:  # Show first 3
                    transaction = match_data['transaction']
                    match = match_data['match']
                    print(f"  Row {transaction['row_number']}: {transaction['source']} -> {match['rule'].get('target_sheet', 'N/A')}")
        else:
            print(f"Test failed: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 