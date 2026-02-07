#!/usr/bin/env python3
"""
Cleanup Duplicate Rules
Removes duplicate source+company combinations, keeping the most recent rule
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cleanup_duplicate_rules():
    """Clean up duplicate rules, keeping the most recent one for each source+company combination."""
    print("🧹 CLEANING UP DUPLICATE RULES")
    print("=" * 50)
    
    db_path = Path("config/petty_cash.db")
    
    if not db_path.exists():
        print("❌ Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find duplicate source+company combinations
        cursor.execute("""
            SELECT source, company, COUNT(*) 
            FROM rules 
            GROUP BY source, company 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("✅ No duplicate rules found!")
            return True
        
        print(f"📊 Found {len(duplicates)} duplicate source+company combinations:")
        for source, company, count in duplicates[:10]:
            print(f"   '{source}' for {company}: {count} times")
        
        if len(duplicates) > 10:
            print(f"   ... and {len(duplicates) - 10} more")
        
        # For each duplicate combination, keep the most recent rule
        removed_count = 0
        
        for source, company, count in duplicates:
            # Get all rules for this source+company combination
            cursor.execute("""
                SELECT id, created_date, updated_date 
                FROM rules 
                WHERE source = ? AND company = ? 
                ORDER BY updated_date DESC, created_date DESC
            """, (source, company))
            
            rules = cursor.fetchall()
            
            # Keep the first (most recent) rule, remove the rest
            for rule_id, created_date, updated_date in rules[1:]:
                cursor.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
                removed_count += 1
                print(f"   Removed rule ID {rule_id} (duplicate of '{source}' for {company})")
        
        conn.commit()
        
        print(f"\n📊 CLEANUP RESULTS:")
        print(f"   Duplicate combinations found: {len(duplicates)}")
        print(f"   Rules removed: {removed_count}")
        
        # Verify cleanup
        cursor.execute("""
            SELECT source, company, COUNT(*) 
            FROM rules 
            GROUP BY source, company 
            HAVING COUNT(*) > 1
        """)
        remaining_duplicates = cursor.fetchall()
        
        if not remaining_duplicates:
            print("✅ All duplicates removed successfully!")
        else:
            print(f"⚠️ Still have {len(remaining_duplicates)} duplicate combinations")
        
        # Show final stats
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        print(f"📊 Total rules remaining: {total_rules}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False

def create_unique_index():
    """Create unique index on source+company after cleanup."""
    print("\n🔧 CREATING UNIQUE INDEX")
    print("=" * 30)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Create unique index
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rules_source_company ON rules(source, company)")
        print("✅ Unique index created successfully")
        
        # Create company index for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_company ON rules(company)")
        print("✅ Company index created")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create unique index: {e}")
        return False

def show_final_stats():
    """Show final statistics after cleanup."""
    print("\n📊 FINAL STATISTICS")
    print("=" * 30)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Total rules
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        print(f"📊 Total rules: {total_rules}")
        
        # Rules by company
        cursor.execute("SELECT company, COUNT(*) FROM rules GROUP BY company ORDER BY COUNT(*) DESC")
        company_stats = cursor.fetchall()
        
        print(f"\n📋 Rules by company:")
        for company, count in company_stats:
            print(f"   {company}: {count} rules")
        
        # Verify no duplicates
        cursor.execute("SELECT COUNT(DISTINCT source, company) FROM rules")
        unique_combinations = cursor.fetchone()[0]
        
        if total_rules == unique_combinations:
            print(f"\n✅ Perfect! {total_rules} rules, {unique_combinations} unique source+company combinations")
        else:
            print(f"\n⚠️ Issue: {total_rules} rules, {unique_combinations} unique combinations")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting final stats: {e}")

def main():
    """Main cleanup function."""
    print("🧹 DUPLICATE RULES CLEANUP")
    print("=" * 60)
    
    # Clean up duplicates
    cleanup_success = cleanup_duplicate_rules()
    
    if cleanup_success:
        # Create unique index
        index_success = create_unique_index()
        
        if index_success:
            print("\n🎉 CLEANUP COMPLETED SUCCESSFULLY!")
            print("   All duplicate rules removed.")
            print("   Unique index created.")
            print("   Rules are now properly company-specific.")
        else:
            print("\n⚠️ Cleanup completed but index creation failed.")
    else:
        print("\n❌ Cleanup failed.")
    
    # Show final statistics
    show_final_stats()
    
    print("\n👋 Cleanup completed!")

if __name__ == "__main__":
    main() 