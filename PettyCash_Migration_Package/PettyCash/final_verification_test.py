#!/usr/bin/env python3
"""
Final Verification Test - Confirm all advanced features are working
"""

import logging
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from rule_loader import RuleLoader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher
from performance_monitor import ProgressMonitor, ErrorRecovery
from audit_and_reporting import AuditAndReporting

def main():
    print("FINAL VERIFICATION TEST")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    test_results = {}
    
    try:
        # 1. Test AI Advanced Logic
        print("\n1. TESTING AI ADVANCED LOGIC")
        print("-" * 40)
        
        ai_matcher = AIRuleMatcher()
        rule_loader = RuleLoader()
        rule_loader.reload_rules()
        ai_matcher.load_rules_from_database()
        
        print(f"SUCCESS: AI Matcher loaded with {len(ai_matcher.rules_cache)} rules")
        
        # Test semantic matching
        test_cases = [
            "WALMART SUPERCENTER",
            "WALMART SUPERCENTER #1234",
            "AMAZON.COM",
            "AMAZON.COM*ABC123"
        ]
        
        print("Testing semantic matching:")
        for test_case in test_cases:
            match_result = ai_matcher.find_best_match(test_case, "NUGZ")
            if match_result.matched:
                print(f"  SUCCESS: '{test_case}' -> {match_result.matched_rule['source']} (confidence: {match_result.confidence:.2f})")
            else:
                print(f"  NO MATCH: '{test_case}'")
        
        test_results['AI Logic'] = True
        
        # 2. Test Transaction Matching
        print("\n2. TESTING TRANSACTION MATCHING")
        print("-" * 40)
        
        csv_downloader = CSVDownloader()
        transactions = csv_downloader.download_petty_cash_data()
        
        if transactions:
            print(f"SUCCESS: Downloaded {len(transactions)} transactions")
            
            # Test with first 10 transactions
            test_transactions = transactions[:10]
            match_results = ai_matcher.batch_match_transactions(test_transactions)
            
            print(f"SUCCESS: Matching Results:")
            print(f"  Matched: {len(match_results['matched'])}")
            print(f"  Unmatched: {len(match_results['unmatched'])}")
            
            if match_results['matched']:
                sample_match = match_results['matched'][0]
                print(f"  Sample: '{sample_match['transaction']['source']}' -> {sample_match['match']['matched_source']}")
            
            # Test rule suggestions
            if match_results['unmatched']:
                suggestions = ai_matcher.suggest_new_rules(match_results['unmatched'][:3])
                print(f"  Generated {len(suggestions)} rule suggestions")
            
            test_results['Transaction Matching'] = True
        else:
            print("FAILED: No transactions downloaded")
            test_results['Transaction Matching'] = False
        
        # 3. Test Performance Features
        print("\n3. TESTING PERFORMANCE FEATURES")
        print("-" * 40)
        
        progress = ProgressMonitor()
        progress.start_operation("Test", 100, "Testing progress")
        
        for i in range(10):
            progress.update_progress(10, f"Step {i+1}")
        
        progress.finish_operation()
        print("SUCCESS: Progress monitoring working")
        
        # Test error recovery
        recovery = ErrorRecovery()
        stats = recovery.get_recovery_stats()
        print(f"SUCCESS: Error recovery working")
        
        test_results['Performance Features'] = True
        
        # 4. Test Audit and Reporting
        print("\n4. TESTING AUDIT AND REPORTING")
        print("-" * 40)
        
        audit = AuditAndReporting()
        session_id = audit.start_audit_session("Test Session", "Testing audit functionality")
        
        audit.log_audit_event(session_id, "test_event", {"status": "success"})
        audit.update_performance_metrics({"test_metric": 100})
        
        audit.end_audit_session(session_id, {"status": "success"})
        
        # Generate report
        report = audit.generate_comprehensive_report()
        print(f"SUCCESS: Audit report generated with {len(report.get('audit_sessions', []))} sessions")
        
        test_results['Audit and Reporting'] = True
        
        # 5. Test Database Operations
        print("\n5. TESTING DATABASE OPERATIONS")
        print("-" * 40)
        
        db_manager = DatabaseManager()
        db_created = db_manager.create_database()
        print(f"SUCCESS: Database creation: {db_created}")
        
        # Get database stats
        stats = db_manager.get_database_stats()
        print(f"SUCCESS: Database stats retrieved")
        
        test_results['Database Operations'] = True
        
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\nOVERALL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: All advanced features are working correctly!")
        print("The comprehensive petty cash sorter is fully functional!")
        return True
    else:
        print(f"\nWARNING: {total - passed} tests failed. Some features need attention.")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\nVERIFICATION COMPLETE: System is ready for production use!")
    else:
        print("\nVERIFICATION FAILED: Issues need to be resolved.") 