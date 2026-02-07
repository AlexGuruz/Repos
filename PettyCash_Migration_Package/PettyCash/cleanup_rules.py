#!/usr/bin/env python3
"""Clean up database to keep only the original 156 user-created rules"""

from database_manager import DatabaseManager
import json

def cleanup_rules():
    """Remove auto-generated rules and keep only original 156."""
    print("🧹 CLEANING UP DATABASE RULES")
    print("=" * 50)
    
    try:
        # Connect to database
        db = DatabaseManager("config/petty_cash.db")
        rules = db.get_all_rules()
        
        print(f"📊 Current rules in database: {len(rules)}")
        
        # Identify rules to remove (the ones I added during testing)
        rules_to_remove = [
            'SALE TO EMERALDS WELLNESS',
            'SALE TO GUYS WHOLESALE', 
            'PAYROLL WEEK 1',
            'REG 1',
            'SALE TO CANNABIS DIST',
            'PAYROLL JGD',
            'ORDER LAB SUPPLIES',
            'LAB TESTING'
        ]
        
        print(f"\n🗑️  Removing {len(rules_to_remove)} auto-generated rules:")
        removed_count = 0
        
        for rule_source in rules_to_remove:
            # Remove the rule by source
            if db.delete_rule_by_source(rule_source):
                print(f"  ✅ Removed: {rule_source}")
                removed_count += 1
            else:
                print(f"  ⚠️  Not found: {rule_source}")
        
        # Verify final count
        final_rules = db.get_all_rules()
        print(f"\n📊 Final rules in database: {len(final_rules)}")
        
        if len(final_rules) == 156:
            print("✅ Successfully restored to 156 user-created rules!")
        else:
            print(f"⚠️  Still have {len(final_rules)} rules (expected 156)")
        
        return len(final_rules) == 156
        
    except Exception as e:
        print(f"❌ Error cleaning up rules: {e}")
        return False

if __name__ == "__main__":
    cleanup_rules() 