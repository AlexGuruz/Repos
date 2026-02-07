#!/usr/bin/env python3
"""Clear database and restart processing to demonstrate the system"""

import sqlite3
import os
from pathlib import Path

def clear_database_and_restart():
    """Clear the database and restart processing"""
    print("🔄 CLEARING DATABASE FOR FRESH START")
    print("=" * 50)
    
    try:
        # Clear the database
        print("🗑️ Clearing database...")
        db_path = "petty_cash.db"
        
        if os.path.exists(db_path):
            # Connect and clear all tables
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print(f"📋 Found {len(tables)} tables to clear:")
            for table in tables:
                table_name = table[0]
                print(f"  • {table_name}")
                cursor.execute(f"DELETE FROM {table_name}")
            
            conn.commit()
            conn.close()
            print("✅ Database cleared successfully")
        else:
            print("⚠️ Database file not found - nothing to clear")
        
        # Clear processed hashes file if it exists
        hash_file = "data/processed_hashes.txt"
        if os.path.exists(hash_file):
            os.remove(hash_file)
            print("✅ Processed hashes file cleared")
        
        print("\n🎯 DATABASE CLEARED!")
        print("📋 Next steps:")
        print("  1. Run: venv\\Scripts\\python.exe THe.py")
        print("  2. Watch the real-time processing at http://localhost:5000")
        print("  3. See transactions being processed live!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

if __name__ == "__main__":
    clear_database_and_restart() 