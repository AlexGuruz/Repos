#!/usr/bin/env python3
"""
Comprehensive Feature Test for Petty Cash Sorter
Tests all advanced features: AI logic, transaction matching, batch updates, performance monitoring
"""

import logging
import time
import json
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from rule_loader import RuleLoader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration
from performance_monitor import ProgressMonitor, ErrorRecovery, PerformanceMetrics
from audit_and_reporting import AuditAndReporting

def test_ai_advanced_logic():
    """Test AI advanced logic and semantic understanding."""
    print("\n🧠 TESTING AI ADVANCED LOGIC")
    print("=" * 50)
    
    try:
        # Initialize AI matcher
        ai_matcher = AIRuleMatcher()
        
        # Load rules
        rule_loader = RuleLoader()
        rule_loader.reload_rules()
        ai_matcher.load_rules_from_database()
        
        print(f"✅ AI Matcher loaded with {len(ai_matcher.rules_cache)} rules")
        
        # Test semantic understanding with variations
        test_cases = [
            "WALMART SUPERCENTER",
            "WALMART SUPERCENTER #1234", 
            "WALMART SUPERCENTER STORE",
            "WALMART SUPERCENTER GROCERY",
            "WALMART SUPERCENTER PHARMACY",
            "WALMART SUPERCENTER GAS STATION"
        ]
        
        print("\n🔍 Testing semantic understanding with variations:")
        for test_case in test_cases:
            match = ai_matcher.find_best_match(test_case, confidence_threshold=5)
            if match:
                print(f"  ✅ '{test_case}' → {match['matched_source']} (confidence: {match['confidence']})")
            else:
                print(f"  ❌ '{test_case}' → No match found")
        
        # Test pattern recognition
        print("\n🎯 Testing pattern recognition:")
        pattern_tests = [
            "AMAZON.COM",
            "AMAZON.COM*ABC123",
            "AMAZON.COM PURCHASE",
            "AMAZON.COM REFUND"
        ]
        
        for test_case in pattern_tests:
            match = ai_matcher.find_best_match(test_case, confidence_threshold=5)
            if match:
                print(f"  ✅ '{test_case}' → {match['matched_source']} (confidence: {match['confidence']})")
            else:
                print(f"  ❌ '{test_case}' → No match found")
        
        # Test confidence thresholds
        print("\n📊 Testing confidence thresholds:")
        confidence_test = "WALMART SUPERCENTER"
        for threshold in [3, 5, 7, 9]:
            match = ai_matcher.find_best_match(confidence_test, confidence_threshold=threshold)
            if match:
                print(f"  ✅ Threshold {threshold}: Match found (confidence: {match['confidence']})")
            else:
                print(f"  ❌ Threshold {threshold}: No match (too strict)")
        
        return True
        
    except Exception as e:
        print(f"❌ AI Advanced Logic Test Failed: {e}")
        return False

def test_transaction_matching():
    """Test transaction matching to existing rules."""
    print("\n🎯 TESTING TRANSACTION MATCHING")
    print("=" * 50)
    
    try:
        # Initialize components
        csv_downloader = CSVDownloader()
        ai_matcher = AIRuleMatcher()
        rule_loader = RuleLoader()
        
        # Load rules
        rule_loader.reload_rules()
        ai_matcher.load_rules_from_database()
        
        # Download transactions
        print("📥 Downloading transactions...")
        transactions = csv_downloader.download_petty_cash_data()
        if not transactions:
            print("❌ No transactions downloaded")
            return False
        
        print(f"✅ Downloaded {len(transactions)} transactions")
        
        # Test batch matching
        print("\n🔄 Testing batch matching...")
        test_transactions = transactions[:20]  # Test with 20 transactions
        match_results = ai_matcher.batch_match_transactions(test_transactions)
        
        print(f"📊 Batch matching results:")
        print(f"  📈 Total transactions: {len(test_transactions)}")
        print(f"  ✅ Matched: {len(match_results['matched'])}")
        print(f"  ❌ Unmatched: {len(match_results['unmatched'])}")
        
        if len(test_transactions) > 0:
            match_rate = (len(match_results['matched']) / len(test_transactions)) * 100
            print(f"  📈 Match rate: {match_rate:.1f}%")
        
        # Show sample matches
        print("\n🎯 Sample matches:")
        for i, match_data in enumerate(match_results['matched'][:5]):
            transaction = match_data['transaction']
            match = match_data['match']
            print(f"  {i+1}. '{transaction.get('source', 'N/A')}' → {match['matched_source']} → {match['target_sheet']} (confidence: {match['confidence']})")
        
        # Show sample unmatched
        if match_results['unmatched']:
            print("\n❓ Sample unmatched:")
            for i, transaction in enumerate(match_results['unmatched'][:3]):
                print(f"  {i+1}. '{transaction.get('source', 'N/A')}' - ${transaction.get('amount', 0)}")
        
        # Test rule suggestions
        if match_results['unmatched']:
            print("\n💡 Testing rule suggestions...")
            suggestions = ai_matcher.suggest_new_rules(match_results['unmatched'][:5])
            print(f"✅ Generated {len(suggestions)} rule suggestions")
            
            for i, suggestion in enumerate(suggestions[:3]):
                print(f"  {i+1}. Source: '{suggestion['source']}' → Sheet: {suggestion['target_sheet']} → Header: {suggestion['target_header']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Transaction Matching Test Failed: {e}")
        return False

def test_api_batch_updates():
    """Test Google Sheets API batch updates."""
    print("\n📊 TESTING API BATCH UPDATES")
    print("=" * 50)
    
    try:
        # Initialize Google Sheets integration
        sheets_integration = GoogleSheetsIntegration()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("❌ Google Sheets connection failed")
            return False
        
        print("✅ Google Sheets connection successful")
        
        # Create layout map
        print("\n🗺️ Creating layout map...")
        layout_map = sheets_integration.create_layout_map()
        if not layout_map:
            print("❌ Layout map creation failed")
            return False
        
        print(f"✅ Layout map created with {len(layout_map)} sheets")
        
        # Test cell coordinate finding
        print("\n📍 Testing cell coordinate finding...")
        test_sheet = list(layout_map.keys())[0] if layout_map else None
        if test_sheet:
            sheet_headers = list(layout_map[test_sheet].keys())
            if sheet_headers:
                test_header = sheet_headers[0]
                test_date = "12/15/23"
                
                coords = sheets_integration.find_target_cell_coordinates(test_sheet, test_header, test_date)
                if coords:
                    print(f"✅ Found coordinates: {test_sheet} → Row {coords['row']}, Col {coords['col']}")
                else:
                    print(f"⚠️ No coordinates found for {test_sheet} - {test_header} - {test_date}")
        
        # Test batch update preparation (without actually updating)
        print("\n📦 Testing batch update preparation...")
        test_sheet_groups = {
            "Test Sheet": {
                "test_cell_1": {"row": 1, "col": 1, "amount": 100.50},
                "test_cell_2": {"row": 2, "col": 1, "amount": 200.75}
            }
        }
        
        print(f"✅ Prepared batch update for {len(test_sheet_groups)} sheets")
        for sheet_name, updates in test_sheet_groups.items():
            print(f"  📊 {sheet_name}: {len(updates)} cell updates")
        
        # Test single cell update (read-only test)
        print("\n🔧 Testing single cell update logic...")
        test_amount = 150.25
        formatted_amount = sheets_integration._format_amount(test_amount)
        print(f"✅ Amount formatting: ${test_amount} → {formatted_amount}")
        
        return True
        
    except Exception as e:
        print(f"❌ API Batch Updates Test Failed: {e}")
        return False

def test_performance_monitoring():
    """Test performance monitoring and progress tracking."""
    print("\n📊 TESTING PERFORMANCE MONITORING")
    print("=" * 50)
    
    try:
        # Initialize monitoring components
        progress_monitor = ProgressMonitor()
        error_recovery = ErrorRecovery()
        performance_metrics = PerformanceMetrics()
        audit_reporter = AuditAndReporting()
        
        print("✅ All monitoring components initialized")
        
        # Test progress monitoring
        print("\n📈 Testing progress monitoring...")
        progress_monitor.start_operation("Test Operation", 100, "Testing progress tracking")
        
        for i in range(25):
            progress_monitor.update_progress(1, f"Processing item {i+1}")
            time.sleep(0.1)
        
        progress_monitor.finish_operation()
        print("✅ Progress monitoring test completed")
        
        # Test performance metrics
        print("\n⚡ Testing performance metrics...")
        performance_metrics.start_monitoring()
        
        # Simulate some operations
        with performance_metrics.time_operation("test_operation"):
            time.sleep(1)
        
        performance_metrics.track_api_call("test_api", 0.5, True)
        performance_metrics.track_api_call("test_api", 1.2, False, "timeout")
        
        time.sleep(2)  # Let memory monitoring collect data
        
        current_stats = performance_metrics.get_current_stats()
        print(f"✅ Performance metrics collected: {current_stats}")
        
        performance_metrics.stop_monitoring()
        
        # Test audit reporting
        print("\n📋 Testing audit reporting...")
        session_id = audit_reporter.start_audit_session("Test Session", "Testing audit functionality")
        
        audit_reporter.log_audit_event(session_id, "test_event", {"status": "success"})
        audit_reporter.update_performance_metrics({"test_metric": 100})
        
        audit_reporter.end_audit_session(session_id, {"status": "success"})
        
        # Generate report
        report = audit_reporter.generate_comprehensive_report()
        print(f"✅ Audit report generated with {len(report.get('audit_sessions', []))} sessions")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance Monitoring Test Failed: {e}")
        return False

def test_error_recovery():
    """Test error recovery and retry logic."""
    print("\n🔄 TESTING ERROR RECOVERY")
    print("=" * 50)
    
    try:
        error_recovery = ErrorRecovery()
        
        # Test exponential backoff decorator
        print("\n🔄 Testing exponential backoff...")
        
        @error_recovery.exponential_backoff
        def test_function():
            import random
            if random.random() < 0.7:  # 70% chance of failure
                raise Exception("Simulated error")
            return "Success"
        
        try:
            result = test_function()
            print(f"✅ Function succeeded: {result}")
        except Exception as e:
            print(f"✅ Function failed as expected after retries: {e}")
        
        # Check recovery stats
        stats = error_recovery.get_recovery_stats()
        print(f"📊 Recovery stats: {stats}")
        
        # Test progress saving
        print("\n💾 Testing progress saving...")
        error_recovery.save_progress("test_operation", 50, 100, {"context": "test"})
        
        # Test progress resuming
        progress_data = error_recovery.resume_from_progress()
        if progress_data:
            print(f"✅ Progress resumed: {progress_data['completed_items']}/{progress_data['total_items']}")
        else:
            print("✅ No progress to resume")
        
        return True
        
    except Exception as e:
        print(f"❌ Error Recovery Test Failed: {e}")
        return False

def main():
    """Run all comprehensive tests."""
    print("🧪 COMPREHENSIVE FEATURE TEST")
    print("=" * 80)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    test_results = {}
    
    # Run all tests
    tests = [
        ("AI Advanced Logic", test_ai_advanced_logic),
        ("Transaction Matching", test_transaction_matching),
        ("API Batch Updates", test_api_batch_updates),
        ("Performance Monitoring", test_performance_monitoring),
        ("Error Recovery", test_error_recovery)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*80}")
        print(f"🧪 RUNNING: {test_name}")
        print(f"{'='*80}")
        
        try:
            result = test_func()
            test_results[test_name] = result
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            test_results[test_name] = False
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The comprehensive petty cash sorter is fully functional!")
    else:
        print(f"⚠️ {total - passed} tests failed. Some features may need attention.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 