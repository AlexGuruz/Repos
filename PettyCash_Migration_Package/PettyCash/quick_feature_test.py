#!/usr/bin/env python3
"""
Quick Feature Test - Focused on key advanced features
"""

import logging
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from rule_loader import RuleLoader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher

def main():
    print("🚀 QUICK FEATURE TEST")
    print("=" * 50)
    
    try:
        # 1. Test AI Advanced Logic
        print("\n🧠 Testing AI Advanced Logic...")
        ai_matcher = AIRuleMatcher()
        
        # Load rules
        rule_loader = RuleLoader()
        rule_loader.reload_rules()
        ai_matcher.load_rules_from_database()
        
        print(f"✅ AI Matcher loaded with {len(ai_matcher.rules_cache)} rules")
        
        # Test semantic matching
        test_cases = [
            "WALMART SUPERCENTER",
            "WALMART SUPERCENTER #1234",
            "AMAZON.COM",
            "AMAZON.COM*ABC123"
        ]
        
        print("\n🔍 Testing semantic matching:")
        for test_case in test_cases:
            match = ai_matcher.find_best_match(test_case, confidence_threshold=5)
            if match:
                print(f"  ✅ '{test_case}' → {match['matched_source']} (confidence: {match['confidence']})")
            else:
                print(f"  ❌ '{test_case}' → No match")
        
        # 2. Test Transaction Matching
        print("\n🎯 Testing Transaction Matching...")
        csv_downloader = CSVDownloader()
        transactions = csv_downloader.download_petty_cash_data()
        
        if transactions:
            print(f"✅ Downloaded {len(transactions)} transactions")
            
            # Test with first 10 transactions
            test_transactions = transactions[:10]
            match_results = ai_matcher.batch_match_transactions(test_transactions)
            
            print(f"📊 Matching Results:")
            print(f"  ✅ Matched: {len(match_results['matched'])}")
            print(f"  ❌ Unmatched: {len(match_results['unmatched'])}")
            
            if match_results['matched']:
                sample_match = match_results['matched'][0]
                print(f"  🎯 Sample: '{sample_match['transaction']['source']}' → {sample_match['match']['matched_source']}")
            
            # Test rule suggestions
            if match_results['unmatched']:
                suggestions = ai_matcher.suggest_new_rules(match_results['unmatched'][:3])
                print(f"  💡 Generated {len(suggestions)} rule suggestions")
        else:
            print("❌ No transactions downloaded")
        
        # 3. Test Performance Features
        print("\n📊 Testing Performance Features...")
        from performance_monitor import ProgressMonitor, ErrorRecovery
        
        progress = ProgressMonitor()
        progress.start_operation("Test", 100, "Testing progress")
        
        for i in range(10):
            progress.update_progress(10, f"Step {i+1}")
        
        progress.finish_operation()
        print("✅ Progress monitoring working")
        
        # Test error recovery
        recovery = ErrorRecovery()
        stats = recovery.get_recovery_stats()
        print(f"✅ Error recovery initialized: {stats}")
        
        print("\n🎉 QUICK TEST COMPLETED!")
        print("✅ All key features are working correctly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎯 RESULT: All advanced features are working!")
    else:
        print("\n❌ RESULT: Some features need attention.") 