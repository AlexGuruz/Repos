#!/usr/bin/env python3
"""
Test Data Loading
Check if CSV data is being loaded correctly
"""

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def main():
    """Test data loading."""
    print("TESTING DATA LOADING")
    print("=" * 30)
    
    try:
        # Initialize the sorter
        sorter = PettyCashSorterFinal()
        
        # Initialize system
        print("Initializing system...")
        if not sorter.initialize_system():
            print("System initialization failed")
            return
        
        print("System initialized successfully")
        
        # Check CSV files
        latest_csv = sorter.csv_downloader.get_latest_csv_file()
        print(f"Latest CSV file: {latest_csv}")
        
        # Download transactions directly
        print("Downloading transactions...")
        transactions = sorter.csv_downloader.download_petty_cash_data()
        print(f"Transactions downloaded: {len(transactions) if transactions else 0}")
        
        if transactions:
            print("Sample transactions:")
            for i, transaction in enumerate(transactions[:3]):
                print(f"  {i+1}. Row {transaction.get('row_number', 'N/A')}: {transaction.get('source', 'N/A')} - ${transaction.get('amount', 'N/A')}")
        
        # Check if there are any transactions to process
        if not transactions or len(transactions) == 0:
            print("WARNING: No transactions found to process!")
            print("This might be why the main program shows 0 processed transactions.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 