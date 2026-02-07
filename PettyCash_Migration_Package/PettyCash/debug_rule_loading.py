#!/usr/bin/env python3
"""
Debug Rule Loading
Investigates why only 133 rules are loaded instead of 154
"""

import logging
from database_manager import DatabaseManager
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def debug_rule_loading():
    """Debug the rule loading process."""
    print("🔍 DEBUGGING RULE LOADING")
    print("=" * 50)
    
    try:
        # Get all rules from database
        db_manager = DatabaseManager()
        all_rules = db_manager.get_all_rules()
        
        print(f"📊 Total rules in database: {len(all_rules)}")
        
        # Check for rules with empty or invalid sources
        empty_sources = []
        invalid_sources = []
        valid_rules = []
        
        for rule in all_rules:
            source = rule.get('source', '').strip()
            
            if not source:
                empty_sources.append(rule)
            elif len(source) < 2:  # Very short sources might be invalid
                invalid_sources.append(rule)
            else:
                valid_rules.append(rule)
        
        print(f"\n📋 Rule Analysis:")
        print(f"   Valid rules: {len(valid_rules)}")
        print(f"   Empty sources: {len(empty_sources)}")
        print(f"   Invalid sources: {len(invalid_sources)}")
        
        # Show examples of problematic rules
        if empty_sources:
            print(f"\n❌ Rules with empty sources:")
            for i, rule in enumerate(empty_sources[:5], 1):
                print(f"   {i}. ID: {rule.get('id')}, Source: '{rule.get('source')}'")
        
        if invalid_sources:
            print(f"\n⚠️ Rules with invalid sources:")
            for i, rule in enumerate(invalid_sources[:5], 1):
                print(f"   {i}. ID: {rule.get('id')}, Source: '{rule.get('source')}'")
        
        # Test AI matcher loading
        print(f"\n🧠 Testing AI Matcher Loading:")
        ai_matcher = AIEnhancedRuleMatcher()
        
        # Load rules
        success = ai_matcher.load_rules_from_database()
        print(f"   Loading success: {success}")
        print(f"   Rules loaded into cache: {len(ai_matcher.rules_cache)}")
        
        # Check for duplicates
        sources = [rule.get('source', '').strip() for rule in valid_rules]
        unique_sources = set(sources)
        duplicates = len(sources) - len(unique_sources)
        
        print(f"\n🔍 Duplicate Analysis:")
        print(f"   Total sources: {len(sources)}")
        print(f"   Unique sources: {len(unique_sources)}")
        print(f"   Duplicates: {duplicates}")
        
        if duplicates > 0:
            # Find duplicate sources
            from collections import Counter
            source_counts = Counter(sources)
            duplicates_found = [source for source, count in source_counts.items() if count > 1]
            
            print(f"\n📋 Duplicate sources found:")
            for source in duplicates_found[:5]:
                print(f"   • '{source}' (appears {source_counts[source]} times)")
        
        # Check for rules that might be filtered out
        print(f"\n🔍 Rules that might be filtered out:")
        filtered_rules = []
        
        for rule in all_rules:
            source = rule.get('source', '').strip()
            if source and source not in ai_matcher.rules_cache:
                filtered_rules.append(rule)
        
        print(f"   Rules not in cache: {len(filtered_rules)}")
        
        if filtered_rules:
            print(f"   Examples of filtered rules:")
            for i, rule in enumerate(filtered_rules[:5], 1):
                print(f"     {i}. '{rule.get('source')}' -> {rule.get('target_sheet')}/{rule.get('target_header')}")
        
        return {
            'total_rules': len(all_rules),
            'valid_rules': len(valid_rules),
            'empty_sources': len(empty_sources),
            'invalid_sources': len(invalid_sources),
            'loaded_into_cache': len(ai_matcher.rules_cache),
            'duplicates': duplicates,
            'filtered_rules': len(filtered_rules)
        }
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        return None

def main():
    """Main debug function."""
    print("🔍 RULE LOADING DEBUG")
    print("=" * 60)
    
    results = debug_rule_loading()
    
    if results:
        print(f"\n📊 SUMMARY:")
        print(f"   Database rules: {results['total_rules']}")
        print(f"   Valid rules: {results['valid_rules']}")
        print(f"   Loaded into cache: {results['loaded_into_cache']}")
        print(f"   Missing: {results['total_rules'] - results['loaded_into_cache']}")
        
        if results['duplicates'] > 0:
            print(f"   Note: {results['duplicates']} duplicate sources found")
        
        if results['filtered_rules'] > 0:
            print(f"   Note: {results['filtered_rules']} rules not loaded into cache")
    
    print("\n👋 Debug completed!")

if __name__ == "__main__":
    main() 