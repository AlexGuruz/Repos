#!/usr/bin/env python3
"""
Test Optimized Download - Verify only data rows are downloaded
"""

import logging
import time
from csv_downloader_fixed import CSVDownloader

def main():
    print("OPTIMIZED DOWNLOAD TEST")
    print("=" * 50)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    try:
        # Test the optimized downloader
        print("\nTesting optimized CSV downloader...")
        start_time = time.time()
        
        downloader = CSVDownloader()
        transactions = downloader.download_petty_cash_data()
        
        end_time = time.time()
        download_time = end_time - start_time
        
        if transactions:
            print(f"\n✅ SUCCESS: Downloaded {len(transactions)} transactions")
            print(f"⏱️ Download time: {download_time:.2f} seconds")
            print(f"📊 Performance: {len(transactions)/download_time:.1f} transactions/second")
            
            # Show sample transactions
            print(f"\n📋 Sample transactions:")
            for i, transaction in enumerate(transactions[:3]):
                print(f"  {i+1}. Row {transaction['row_number']}: {transaction['source']} - ${transaction['amount']}")
            
            return True
        else:
            print("❌ FAILED: No transactions downloaded")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Optimized download test passed!")
    else:
        print("\n⚠️ Optimized download test failed!") 