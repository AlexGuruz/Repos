#!/usr/bin/env python3
"""Check current rules in database"""

from database_manager import DatabaseManager
import json

def check_rules():
    """Check and display current rules in database."""
    print("🔍 CHECKING DATABASE RULES")
    print("=" * 50)
    
    try:
        # Connect to database
        db = DatabaseManager("config/petty_cash.db")
        rules = db.get_all_rules()
        
        print(f"📊 Total rules in database: {len(rules)}")
        
        if len(rules) != 156:
            print(f"⚠️  WARNING: Expected 156 rules, found {len(rules)}")
        else:
            print("✅ Correct number of rules found (156)")
        
        # Group by company
        companies = {}
        for rule in rules:
            company = rule.get('company', 'Unknown')
            if company not in companies:
                companies[company] = []
            companies[company].append(rule)
        
        print(f"\n📋 Rules by company:")
        for company, company_rules in companies.items():
            print(f"  {company}: {len(company_rules)} rules")
        
        # Show sample rules
        print(f"\n📝 Sample rules (first 5):")
        for i, rule in enumerate(rules[:5]):
            print(f"  {i+1}. {rule.get('source', 'N/A')} -> {rule.get('target_sheet', 'N/A')}/{rule.get('target_header', 'N/A')}")
        
        # Check for any auto-generated rules
        print(f"\n🔍 Checking for auto-generated rules...")
        auto_generated = 0
        for rule in rules:
            source = rule.get('source', '').lower()
            # Look for patterns that might indicate auto-generation
            if any(pattern in source for pattern in ['test', 'sample', 'auto', 'generated']):
                auto_generated += 1
                print(f"  ⚠️  Potential auto-generated rule: {rule.get('source')}")
        
        if auto_generated == 0:
            print("✅ No auto-generated rules detected")
        else:
            print(f"⚠️  Found {auto_generated} potential auto-generated rules")
        
        return len(rules) == 156
        
    except Exception as e:
        print(f"❌ Error checking rules: {e}")
        return False

if __name__ == "__main__":
    check_rules() 