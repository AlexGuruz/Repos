#!/usr/bin/env python3
"""
Test Full Update
Test that Google Sheets are actually being updated with real data
"""

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def main():
    """Test full Google Sheets updates."""
    print("TESTING FULL GOOGLE SHEETS UPDATES")
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
        
        # Test with a small batch
        print("\nTesting with 3 transactions...")
        result = sorter.test_small_batch(3)
        
        print(f"Test result: {result}")
        
        if result.get('status') == 'success':
            print("Small batch test successful!")
            
            # Check if any sheets were updated
            sheets_updated = result.get('sheets_updated', 0)
            print(f"Sheets updated: {sheets_updated}")
            
            if sheets_updated > 0:
                print("SUCCESS: Google Sheets updates are working!")
                print("You should now see data in your target sheets!")
                
                # Show what was matched and updated
                if 'match_results' in result:
                    matched = result['match_results'].get('matched', [])
                    print(f"\nMatched transactions: {len(matched)}")
                    
                    for match_data in matched:
                        transaction = match_data['transaction']
                        match = match_data['match']
                        target_sheet = match['rule'].get('target_sheet', 'N/A')
                        target_header = match['rule'].get('target_header', 'N/A')
                        amount = transaction['amount']
                        
                        print(f"  Row {transaction['row_number']}: {transaction['source']} (${amount:.2f}) -> {target_sheet} -> {target_header}")
            else:
                print("WARNING: No sheets were updated - there may still be an issue")
        else:
            print(f"Test failed: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 