#!/usr/bin/env python3
"""
Migrate Rules to Company-Specific
Adds company field to rules table and updates existing rules
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_rules_to_company_specific():
    """Migrate rules to be company-specific."""
    print("🔄 MIGRATING RULES TO COMPANY-SPECIFIC")
    print("=" * 60)
    
    db_path = Path("config/petty_cash.db")
    
    if not db_path.exists():
        print("❌ Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(rules)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"📋 Current rules table columns: {columns}")
        
        # Add company column if it doesn't exist
        if 'company' not in columns:
            print("➕ Adding company column to rules table...")
            cursor.execute("ALTER TABLE rules ADD COLUMN company TEXT DEFAULT 'Unknown'")
            print("✅ Company column added")
        else:
            print("✅ Company column already exists")
        
        # Get all current rules
        cursor.execute("SELECT * FROM rules")
        all_rules = cursor.fetchall()
        
        print(f"📊 Found {len(all_rules)} rules to migrate")
        
        # Get column names for rules table
        cursor.execute("PRAGMA table_info(rules)")
        rule_columns = [column[1] for column in cursor.fetchall()]
        
        # Update rules based on target sheet patterns
        updated_count = 0
        
        for rule in all_rules:
            rule_dict = dict(zip(rule_columns, rule))
            rule_id = rule_dict['id']
            target_sheet = rule_dict.get('target_sheet', '')
            
            # Determine company based on target sheet
            company = 'Unknown'
            
            if target_sheet:
                target_sheet_upper = target_sheet.upper()
                
                if 'NUGZ' in target_sheet_upper:
                    company = 'NUGZ'
                elif 'JGD' in target_sheet_upper:
                    company = 'JGD'
                elif 'PUFFIN' in target_sheet_upper:
                    company = 'PUFFIN'
                elif '710' in target_sheet_upper or 'EMPIRE' in target_sheet_upper:
                    company = '710 EMPIRE'
                elif 'PAYROLL' in target_sheet_upper:
                    company = 'GENERAL'
                elif 'COMMISSION' in target_sheet_upper:
                    company = 'GENERAL'
                elif 'BALANCE' in target_sheet_upper:
                    company = 'GENERAL'
                elif 'INCOME' in target_sheet_upper:
                    company = 'GENERAL'
                elif 'NON CANNABIS' in target_sheet_upper:
                    company = 'GENERAL'
                else:
                    # Try to infer from source
                    source = rule_dict.get('source', '').upper()
                    if 'NUGZ' in source or 'EMERALDS' in source or 'GUYS' in source:
                        company = 'NUGZ'
                    elif 'JGD' in source or 'CANNABIS' in source:
                        company = 'JGD'
                    elif 'PUFFIN' in source:
                        company = 'PUFFIN'
                    elif '710' in source or 'EMPIRE' in source:
                        company = '710 EMPIRE'
                    else:
                        company = 'GENERAL'
            
            # Update the rule with company
            cursor.execute("UPDATE rules SET company = ? WHERE id = ?", (company, rule_id))
            updated_count += 1
            
            if updated_count % 20 == 0:
                print(f"   Updated {updated_count} rules...")
        
        # Create unique index on source + company
        print("🔧 Creating unique index on source + company...")
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rules_source_company ON rules(source, company)")
            print("✅ Unique index created")
        except Exception as e:
            print(f"⚠️ Could not create unique index: {e}")
        
        # Create index on company for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_company ON rules(company)")
        print("✅ Company index created")
        
        conn.commit()
        
        # Show migration results
        print(f"\n📊 MIGRATION RESULTS:")
        print(f"   Total rules processed: {len(all_rules)}")
        print(f"   Rules updated: {updated_count}")
        
        # Show company distribution
        cursor.execute("SELECT company, COUNT(*) FROM rules GROUP BY company ORDER BY COUNT(*) DESC")
        company_stats = cursor.fetchall()
        
        print(f"\n📋 Rules by company:")
        for company, count in company_stats:
            print(f"   {company}: {count} rules")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def verify_migration():
    """Verify the migration was successful."""
    print("\n🔍 VERIFYING MIGRATION")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Check for duplicate source+company combinations
        cursor.execute("""
            SELECT source, company, COUNT(*) 
            FROM rules 
            GROUP BY source, company 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"⚠️ Found {len(duplicates)} duplicate source+company combinations:")
            for source, company, count in duplicates[:5]:
                print(f"   '{source}' for {company}: {count} times")
        else:
            print("✅ No duplicate source+company combinations found")
        
        # Check total rules
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        print(f"📊 Total rules: {total_rules}")
        
        # Check unique source+company combinations
        cursor.execute("SELECT COUNT(DISTINCT source, company) FROM rules")
        unique_combinations = cursor.fetchone()[0]
        print(f"📊 Unique source+company combinations: {unique_combinations}")
        
        conn.close()
        
        if total_rules == unique_combinations:
            print("✅ Migration successful - no duplicates!")
            return True
        else:
            print(f"⚠️ Still have {total_rules - unique_combinations} duplicates")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main migration function."""
    print("🔄 RULES TO COMPANY-SPECIFIC MIGRATION")
    print("=" * 80)
    
    # Run migration
    success = migrate_rules_to_company_specific()
    
    if success:
        # Verify migration
        verify_success = verify_migration()
        
        if verify_success:
            print("\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            print("   Rules are now company-specific.")
            print("   No more duplicate source issues.")
        else:
            print("\n⚠️ Migration completed but verification failed.")
            print("   Some duplicates may still exist.")
    else:
        print("\n❌ Migration failed.")
    
    print("\n👋 Migration completed!")

if __name__ == "__main__":
    main() 