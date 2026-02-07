#!/usr/bin/env python3
"""
Test CSV Downloader
Test the CSV downloader directly to see how many transactions it processes
"""

from csv_downloader_fixed import CSVDownloader

def test_csv_downloader():
    """Test the CSV downloader directly."""
    print("🧪 TESTING CSV DOWNLOADER")
    print("=" * 40)
    
    try:
        # Initialize the CSV downloader
        downloader = CSVDownloader()
        
        # Download the data
        print("📥 Downloading petty cash data...")
        transactions = downloader.download_petty_cash_data()
        
        if transactions:
            print(f"✅ Successfully downloaded {len(transactions)} transactions")
            
            # Check if row 1805 is in the transactions
            row_1805_found = False
            for transaction in transactions:
                if transaction['row_number'] == 1805:
                    row_1805_found = True
                    print(f"\n📊 ROW 1805 FOUND IN TRANSACTIONS:")
                    print(f"  Transaction ID: {transaction['transaction_id']}")
                    print(f"  Date: {transaction['date']}")
                    print(f"  Source: {transaction['source']}")
                    print(f"  Company: {transaction['company']}")
                    print(f"  Amount: {transaction['amount']}")
                    print(f"  Initials: {transaction['initials']}")
                    break
            
            if not row_1805_found:
                print(f"\n❌ ROW 1805 NOT FOUND IN TRANSACTIONS")
                print(f"  This means it was skipped during processing")
            
            # Show some sample transactions
            print(f"\n📋 SAMPLE TRANSACTIONS:")
            for i, transaction in enumerate(transactions[:5]):
                print(f"  {i+1}. Row {transaction['row_number']}: {transaction['source']} - ${transaction['amount']}")
            
            if len(transactions) > 5:
                print(f"  ... and {len(transactions) - 5} more transactions")
                
        else:
            print("❌ No transactions downloaded")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_downloader() 