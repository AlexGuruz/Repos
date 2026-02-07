#!/usr/bin/env python3
"""
Database Migration Script
Adds new columns needed for AI learning system
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_database():
    """Migrate the database to add new columns for AI learning."""
    print("🔄 DATABASE MIGRATION")
    print("=" * 50)
    
    db_path = Path("config/petty_cash.db")
    
    if not db_path.exists():
        print("❌ Database file not found. Please run the main system first to create the database.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"📋 Current columns: {columns}")
        
        # Add missing columns
        new_columns = [
            ('matched_rule_id', 'INTEGER'),
            ('target_sheet', 'TEXT'),
            ('target_header', 'TEXT'),
            ('notes', 'TEXT')
        ]
        
        added_columns = []
        for column_name, column_type in new_columns:
            if column_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE transactions ADD COLUMN {column_name} {column_type}")
                    added_columns.append(column_name)
                    print(f"✅ Added column: {column_name}")
                except Exception as e:
                    print(f"⚠️ Could not add column {column_name}: {e}")
        
        if added_columns:
            conn.commit()
            print(f"\n🎉 Successfully added {len(added_columns)} new columns: {added_columns}")
        else:
            print("\n✅ All required columns already exist")
        
        # Verify final schema
        cursor.execute("PRAGMA table_info(transactions)")
        final_columns = [column[1] for column in cursor.fetchall()]
        print(f"📋 Final columns: {final_columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def main():
    """Main migration function."""
    print("🔄 DATABASE MIGRATION TOOL")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n✅ Database migration completed successfully!")
        print("   The system is now ready for AI learning capabilities.")
    else:
        print("\n❌ Database migration failed.")
        print("   Please check the error messages above.")
    
    print("\n👋 Migration completed!")

if __name__ == "__main__":
    main() 