#!/usr/bin/env python3
"""Migrate database to add coordinate columns"""

import sqlite3
import logging
from pathlib import Path

def migrate_coordinate_columns():
    """Add coordinate columns to existing database."""
    
    print("🔧 MIGRATING DATABASE FOR COORDINATE COLUMNS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"📊 CURRENT COLUMNS: {columns}")
        
        # Add coordinate columns if they don't exist
        new_columns = [
            ('target_cell_row', 'INTEGER'),
            ('target_cell_col', 'INTEGER'), 
            ('target_cell_address', 'TEXT')
        ]
        
        added_columns = []
        for col_name, col_type in new_columns:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
                    added_columns.append(col_name)
                    print(f"✅ Added column: {col_name}")
                except Exception as e:
                    print(f"❌ Failed to add column {col_name}: {e}")
            else:
                print(f"ℹ️ Column {col_name} already exists")
        
        if added_columns:
            conn.commit()
            print(f"\n✅ MIGRATION COMPLETE!")
            print(f"  • Added {len(added_columns)} new columns: {added_columns}")
        else:
            print(f"\nℹ️ No migration needed - all columns already exist")
        
        # Verify new schema
        cursor.execute("PRAGMA table_info(transactions)")
        final_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"\n📊 FINAL SCHEMA:")
        for col in final_columns:
            print(f"  • {col}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_coordinate_columns() 