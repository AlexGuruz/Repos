#!/usr/bin/env python3
"""
Diagnostic Test - Identify and fix specific failures
"""

import traceback
import sys

def test_imports():
    """Test all imports."""
    print("🔍 Testing imports...")
    
    try:
        from database_manager import DatabaseManager
        print("✅ DatabaseManager imported")
    except Exception as e:
        print(f"❌ DatabaseManager import failed: {e}")
        return False
    
    try:
        from csv_downloader_fixed import CSVDownloader
        print("✅ CSVDownloader imported")
    except Exception as e:
        print(f"❌ CSVDownloader import failed: {e}")
        return False
    
    try:
        from rule_loader import RuleLoader
        print("✅ RuleLoader imported")
    except Exception as e:
        print(f"❌ RuleLoader import failed: {e}")
        return False
    
    try:
        from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
        print("✅ AIEnhancedRuleMatcher imported")
    except Exception as e:
        print(f"❌ AIEnhancedRuleMatcher import failed: {e}")
        return False
    
    try:
        from performance_monitor import ProgressMonitor, ErrorRecovery
        print("✅ PerformanceMonitor imported")
    except Exception as e:
        print(f"❌ PerformanceMonitor import failed: {e}")
        return False
    
    return True

def test_database():
    """Test database operations."""
    print("\n💾 Testing database...")
    
    try:
        from database_manager import DatabaseManager
        db = DatabaseManager()
        result = db.create_database()
        print(f"✅ Database creation: {result}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        traceback.print_exc()
        return False

def test_rule_loading():
    """Test rule loading."""
    print("\n📋 Testing rule loading...")
    
    try:
        from rule_loader import RuleLoader
        loader = RuleLoader()
        result = loader.reload_rules()
        print(f"✅ Rule loading: {result}")
        return True
    except Exception as e:
        print(f"❌ Rule loading failed: {e}")
        traceback.print_exc()
        return False

def test_ai_matcher():
    """Test AI matcher."""
    print("\n🧠 Testing AI matcher...")
    
    try:
        from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
        ai = AIEnhancedRuleMatcher()
        result = ai.load_rules_from_database()
        print(f"✅ AI matcher loading: {result}")
        print(f"✅ Rules loaded: {len(ai.rules_cache)}")
        return True
    except Exception as e:
        print(f"❌ AI matcher failed: {e}")
        traceback.print_exc()
        return False

def test_csv_download():
    """Test CSV download."""
    print("\n📥 Testing CSV download...")
    
    try:
        from csv_downloader_fixed import CSVDownloader
        downloader = CSVDownloader()
        transactions = downloader.download_petty_cash_data()
        if transactions:
            print(f"✅ Downloaded {len(transactions)} transactions")
            return True
        else:
            print("❌ No transactions downloaded")
            return False
    except Exception as e:
        print(f"❌ CSV download failed: {e}")
        traceback.print_exc()
        return False

def test_matching():
    """Test transaction matching."""
    print("\n🎯 Testing transaction matching...")
    
    try:
        from csv_downloader_fixed import CSVDownloader
        from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
        
        # Get transactions
        downloader = CSVDownloader()
        transactions = downloader.download_petty_cash_data()
        
        if not transactions:
            print("❌ No transactions to test")
            return False
        
        # Setup AI matcher
        ai = AIEnhancedRuleMatcher()
        ai.load_rules_from_database()
        
        # Test matching
        test_transactions = transactions[:5]
        results = ai.batch_match_transactions(test_transactions)
        
        print(f"✅ Matching test: {len(results['matched'])} matched, {len(results['unmatched'])} unmatched")
        return True
        
    except Exception as e:
        print(f"❌ Matching test failed: {e}")
        traceback.print_exc()
        return False

def test_performance():
    """Test performance monitoring."""
    print("\n📊 Testing performance monitoring...")
    
    try:
        from performance_monitor import ProgressMonitor, ErrorRecovery
        
        # Test progress monitor
        progress = ProgressMonitor()
        progress.start_operation("Test", 10, "Testing")
        progress.update_progress(5, "Halfway")
        progress.finish_operation()
        print("✅ Progress monitor working")
        
        # Test error recovery
        recovery = ErrorRecovery()
        stats = recovery.get_recovery_stats()
        print(f"✅ Error recovery working: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        traceback.print_exc()
        return False

def main():
    print("🔧 DIAGNOSTIC TEST")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Database", test_database),
        ("Rule Loading", test_rule_loading),
        ("AI Matcher", test_ai_matcher),
        ("CSV Download", test_csv_download),
        ("Matching", test_matching),
        ("Performance", test_performance)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 {test_name}")
        print(f"{'='*50}")
        
        try:
            result = test_func()
            results[test_name] = result
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 DIAGNOSTIC SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is working correctly.")
    else:
        print(f"⚠️ {total - passed} tests failed. Issues need to be fixed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 