#!/usr/bin/env python3
"""Test hash deduplication integration with CSV downloader"""

from csv_downloader_fixed import CSVDownloader
import logging

def test_hash_integration():
    """Test the hash deduplication integration."""
    
    print("🧪 TESTING HASH DEDUPLICATION INTEGRATION")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Create CSV downloader (should have hash deduplication)
        downloader = CSVDownloader()
        print("✅ CSV Downloader created with hash deduplication")
        
        # Test downloading data
        print("\n📥 DOWNLOADING TRANSACTIONS:")
        transactions = downloader.download_petty_cash_data()
        
        if transactions:
            print(f"✅ Downloaded {len(transactions)} new transactions")
            
            # Show sample transactions
            print(f"\n📋 SAMPLE TRANSACTIONS:")
            for i, transaction in enumerate(transactions[:5], 1):
                print(f"  {i}. {transaction['source']} ({transaction['company']}) ${transaction['amount']:.2f}")
                if 'hash_id' in transaction:
                    print(f"     Hash: {transaction['hash_id'][:8]}...")
        else:
            print("ℹ️ No new transactions to download (all processed before)")
        
        # Test running again (should find no new transactions)
        print(f"\n🔄 TESTING SECOND RUN:")
        transactions_again = downloader.download_petty_cash_data()
        
        if transactions_again:
            print(f"❌ Found {len(transactions_again)} transactions on second run (should be 0)")
        else:
            print(f"✅ No new transactions on second run (deduplication working)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing hash integration: {e}")
        return False

if __name__ == "__main__":
    test_hash_integration() 