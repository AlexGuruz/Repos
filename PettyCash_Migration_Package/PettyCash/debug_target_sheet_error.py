#!/usr/bin/env python3
"""
Debug Target Sheet Error
Identifies the issue with 'target_sheet' missing from match data
"""

import logging
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from csv_downloader_fixed import CSVDownloader

def debug_match_structure():
    """Debug the match data structure to find the target_sheet issue."""
    print("🔍 DEBUGGING MATCH DATA STRUCTURE")
    print("=" * 50)
    
    try:
        # Initialize components
        ai_matcher = AIEnhancedRuleMatcher()
        csv_downloader = CSVDownloader()
        
        # Load rules
        if not ai_matcher.load_rules_from_database():
            print("❌ Failed to load rules")
            return
        
        print(f"✅ Loaded {len(ai_matcher.rules_cache)} rules")
        
        # Download a few transactions
        transactions = csv_downloader.download_petty_cash_data()
        if not transactions:
            print("❌ No transactions downloaded")
            return
        
        print(f"✅ Downloaded {len(transactions)} transactions")
        
        # Test matching with first few transactions
        test_transactions = transactions[:5]
        print(f"🧪 Testing with {len(test_transactions)} transactions")
        
        # Match transactions
        match_results = ai_matcher.batch_match_transactions(test_transactions)
        
        print(f"📊 Match results:")
        print(f"  - Total: {len(match_results.get('matched', [])) + len(match_results.get('unmatched', []))}")
        print(f"  - Matched: {len(match_results.get('matched', []))}")
        print(f"  - Unmatched: {len(match_results.get('unmatched', []))}")
        
        # Check match structure
        if 'matched' in match_results and match_results['matched']:
            first_match = match_results['matched'][0]
            print(f"\n📋 First match structure:")
            print(f"  - Keys: {list(first_match.keys())}")
            
            if 'match' in first_match:
                match_data = first_match['match']
                print(f"  - Match keys: {list(match_data.keys())}")
                
                # Check for target_sheet
                if 'target_sheet' in match_data:
                    print(f"  ✅ target_sheet found: {match_data['target_sheet']}")
                else:
                    print(f"  ❌ target_sheet missing!")
                    print(f"  - Available keys: {list(match_data.keys())}")
                    
                    # Check if it's under a different key
                    for key, value in match_data.items():
                        print(f"    {key}: {value}")
            else:
                print(f"  ❌ 'match' key missing from first_match")
        else:
            print("❌ No matched transactions to analyze")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_match_structure() 