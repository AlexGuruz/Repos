#!/usr/bin/env python3
"""Test the fixes to ensure system only processes new transactions"""

import logging
from csv_downloader_fixed import CSVDownloader

def test_fixes():
    """Test that the system correctly identifies new vs processed transactions"""
    print("🧪 TESTING FIXES")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Test CSV downloader
    print("📥 Testing CSV downloader...")
    downloader = CSVDownloader()
    
    # First run - should download all transactions
    print("\n🔄 First run (should download all transactions):")
    transactions1 = downloader.download_petty_cash_data()
    
    if transactions1:
        print(f"✅ Downloaded {len(transactions1)} transactions")
    else:
        print("❌ No transactions downloaded")
        return
    
    # Second run - should download 0 new transactions (all already processed)
    print("\n🔄 Second run (should download 0 new transactions):")
    transactions2 = downloader.download_petty_cash_data()
    
    if transactions2:
        print(f"❌ ERROR: Downloaded {len(transactions2)} transactions (should be 0)")
        return False
    else:
        print("✅ Correctly found 0 new transactions")
    
    print("\n🎯 TEST PASSED!")
    print("✅ Hash deduplication is working correctly")
    print("✅ System will only process new transactions")
    
    return True

if __name__ == "__main__":
    test_fixes() 