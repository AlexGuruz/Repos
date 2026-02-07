#!/usr/bin/env python3
"""Clear database and start fresh for original spreadsheet run"""

import sqlite3
import os
from pathlib import Path

def clear_database_fresh_start():
    """Clear the database to start fresh."""
    
    print("🧹 CLEARING DATABASE FOR FRESH START")
    print("=" * 50)
    
    try:
        # Check if database exists
        db_path = "petty_cash.db"
        if os.path.exists(db_path):
            # Connect and clear all tables
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print(f"📋 Found {len(tables)} tables to clear:")
            
            # Clear each table
            for table in tables:
                table_name = table[0]
                if table_name != 'sqlite_sequence':  # Skip SQLite internal table
                    cursor.execute(f"DELETE FROM {table_name}")
                    print(f"  ✅ Cleared table: {table_name}")
            
            # Reset auto-increment counters
            cursor.execute("DELETE FROM sqlite_sequence")
            
            conn.commit()
            conn.close()
            
            print(f"✅ Database cleared successfully")
            
        else:
            print("ℹ️ Database doesn't exist yet - will be created on first run")
        
        # Clear any pending transaction files
        pending_dir = Path("pending_transactions")
        if pending_dir.exists():
            for file in pending_dir.glob("*.csv"):
                try:
                    file.unlink()
                    print(f"  ✅ Removed: {file.name}")
                except Exception as e:
                    print(f"  ⚠️ Could not remove {file.name}: {e}")
        
        print("🎉 Fresh start ready! Database and pending files cleared.")
        print("📝 Ready to run on original Google Sheet")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

if __name__ == "__main__":
    clear_database_fresh_start() 