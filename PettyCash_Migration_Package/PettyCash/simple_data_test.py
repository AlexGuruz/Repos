#!/usr/bin/env python3
"""
Simple Data Test
Test CSV downloader without full system initialization
"""

from csv_downloader_fixed import CSVDownloader

def main():
    """Test CSV downloader directly."""
    print("SIMPLE DATA TEST")
    print("=" * 20)
    
    try:
        # Create CSV downloader
        downloader = CSVDownloader()
        
        # Download transactions
        print("Downloading transactions...")
        transactions = downloader.download_petty_cash_data()
        
        print(f"Transactions downloaded: {len(transactions) if transactions else 0}")
        
        if transactions:
            print("Sample transactions:")
            for i, transaction in enumerate(transactions[:5]):
                print(f"  {i+1}. Row {transaction.get('row_number', 'N/A')}: {transaction.get('source', 'N/A')} - ${transaction.get('amount', 'N/A')}")
        
        # Check latest CSV file
        latest_csv = downloader.get_latest_csv_file()
        print(f"Latest CSV file: {latest_csv}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 