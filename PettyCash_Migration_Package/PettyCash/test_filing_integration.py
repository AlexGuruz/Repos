#!/usr/bin/env python3
"""
Test Filing System Integration
Tests the integration of the filing system with the main petty cash sorter
"""

import logging
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal
from processed_transaction_manager import ProcessedTransactionManager

def test_filing_system_standalone():
    """Test the filing system in isolation."""
    print("🧪 TESTING FILING SYSTEM STANDALONE")
    print("=" * 50)
    
    try:
        # Initialize filing manager
        filing_manager = ProcessedTransactionManager("test_data/filing_test")
        
        # Test transaction
        test_transaction = {
            'transaction_id': 'TEST_FILING_001',
            'row_number': 1,
            'date': '2025-01-15',
            'initials': 'JD',
            'source': 'Test Filing Source',
            'company': 'JGD',
            'amount': 150.75
        }
        
        test_match = {
            'matched_source': 'Test Filing Source',
            'target_sheet': 'JGD_data',
            'target_header': 'Test Filing Header',
            'confidence': 9.0
        }
        
        # Test successful filing
        print("📝 Testing successful transaction filing...")
        if filing_manager.file_transaction(test_transaction, test_match):
            print("✅ Successful transaction filed")
        else:
            print("❌ Failed to file successful transaction")
            return False
        
        # Test failed transaction filing
        print("📝 Testing failed transaction filing...")
        failed_transaction = {
            'transaction_id': 'TEST_FILING_002',
            'row_number': 2,
            'date': '2025-01-16',
            'initials': 'JD',
            'source': 'Failed Test Source',
            'company': 'NUGZ',
            'amount': 200.00
        }
        
        if filing_manager.file_failed_transaction(failed_transaction, "Test failure reason"):
            print("✅ Failed transaction filed")
        else:
            print("❌ Failed to file failed transaction")
            return False
        
        # Test unmatched transaction filing
        print("📝 Testing unmatched transaction filing...")
        unmatched_transaction = {
            'transaction_id': 'TEST_FILING_003',
            'row_number': 3,
            'date': '2025-01-17',
            'initials': 'JD',
            'source': 'Unknown Source',
            'company': 'PUFFIN',
            'amount': 75.25
        }
        
        if filing_manager.file_unmatched_transaction(unmatched_transaction):
            print("✅ Unmatched transaction filed")
        else:
            print("❌ Failed to file unmatched transaction")
            return False
        
        # Flush all pending
        print("📝 Flushing pending transactions...")
        filing_manager.flush_all_pending()
        
        # Get statistics
        stats = filing_manager.get_filing_statistics()
        print(f"📊 Filing statistics: {stats}")
        
        # Test search
        results = filing_manager.search_transactions(company='JGD')
        print(f"🔍 Found {len(results)} transactions for JGD")
        
        print("✅ Filing system standalone test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Filing system standalone test failed: {e}")
        logging.error(f"Filing system test error: {e}")
        return False

def test_filing_integration():
    """Test the filing system integration with main sorter."""
    print("\n🧪 TESTING FILING SYSTEM INTEGRATION")
    print("=" * 50)
    
    try:
        # Initialize main sorter
        print("🚀 Initializing main petty cash sorter...")
        sorter = PettyCashSorterFinal()
        
        # Check if filing manager was initialized
        if hasattr(sorter, 'filing_manager'):
            print("✅ Filing manager initialized successfully")
        else:
            print("❌ Filing manager not found in main sorter")
            return False
        
        # Test filing manager functionality
        filing_stats = sorter.filing_manager.get_filing_statistics()
        print(f"📊 Initial filing statistics: {filing_stats}")
        
        # Test system status includes filing system
        status = sorter.get_system_status()
        if 'filing_system' in status:
            print("✅ Filing system included in system status")
        else:
            print("❌ Filing system not found in system status")
            return False
        
        print("✅ Filing system integration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Filing system integration test failed: {e}")
        logging.error(f"Integration test error: {e}")
        return False

def test_filing_configuration():
    """Test filing system configuration."""
    print("\n🧪 TESTING FILING SYSTEM CONFIGURATION")
    print("=" * 50)
    
    try:
        from config_manager import ConfigManager
        
        # Load configuration
        config = ConfigManager()
        
        # Check filing system configuration
        filing_config = config.get_section('filing_system')
        if filing_config:
            print("✅ Filing system configuration found")
            print(f"📋 Filing config: {filing_config}")
        else:
            print("❌ Filing system configuration not found")
            return False
        
        # Check specific settings
        base_path = config.get('filing_system.base_path')
        if base_path:
            print(f"✅ Filing base path: {base_path}")
        else:
            print("❌ Filing base path not configured")
            return False
        
        batch_size = config.get('filing_system.batch_size')
        if batch_size:
            print(f"✅ Filing batch size: {batch_size}")
        else:
            print("❌ Filing batch size not configured")
            return False
        
        print("✅ Filing system configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Filing system configuration test failed: {e}")
        logging.error(f"Configuration test error: {e}")
        return False

def main():
    """Run all filing system tests."""
    print("FILING SYSTEM INTEGRATION TEST SUITE")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    tests = [
        ("Filing System Standalone", test_filing_system_standalone),
        ("Filing System Configuration", test_filing_configuration),
        ("Filing System Integration", test_filing_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
    
    print(f"\n{'='*60}")
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Filing system integration ready!")
        return True
    else:
        print("⚠️ Some tests failed - Review issues before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 