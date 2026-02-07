#!/usr/bin/env python3
"""
Check Rebuilt Rules
Verify the rules that were rebuilt from JGD Truth
"""

import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_rebuilt_rules():
    """Check the rebuilt rules from JGD Truth."""
    print("🔍 CHECKING REBUILT RULES")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Get total rules
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        print(f"📊 Total rules: {total_rules}")
        
        # Get rules by company
        cursor.execute("SELECT company, COUNT(*) FROM rules GROUP BY company ORDER BY COUNT(*) DESC")
        company_stats = cursor.fetchall()
        
        print(f"\n📋 Rules by company:")
        for company, count in company_stats:
            print(f"   {company}: {count} rules")
        
        # Check for duplicates
        cursor.execute("""
            SELECT source, company, COUNT(*) 
            FROM rules 
            GROUP BY source, company 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"\n⚠️ Found {len(duplicates)} duplicate source+company combinations:")
            for source, company, count in duplicates[:5]:
                print(f"   '{source}' for {company}: {count} times")
        else:
            print("\n✅ No duplicate source+company combinations found")
        
        # Show sample rules from each company
        print(f"\n📝 Sample rules by company:")
        
        for company, count in company_stats:
            print(f"\n   {company} ({count} rules):")
            cursor.execute("""
                SELECT source, target_sheet, target_header 
                FROM rules 
                WHERE company = ? 
                LIMIT 5
            """, (company,))
            
            sample_rules = cursor.fetchall()
            for i, (source, sheet, header) in enumerate(sample_rules, 1):
                print(f"     {i}. '{source}' -> {sheet}/{header}")
        
        # Verify unique combinations
        cursor.execute("SELECT COUNT(DISTINCT source, company) FROM rules")
        unique_combinations = cursor.fetchone()[0]
        
        if total_rules == unique_combinations:
            print(f"\n✅ Perfect! {total_rules} rules, {unique_combinations} unique source+company combinations")
        else:
            print(f"\n⚠️ Issue: {total_rules} rules, {unique_combinations} unique combinations")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking rules: {e}")

def main():
    """Main function."""
    check_rebuilt_rules()

if __name__ == "__main__":
    main() 