#!/usr/bin/env python3
"""Clear everything for a completely fresh start"""

import sqlite3
import os
import shutil
from pathlib import Path
import logging

def clear_everything_fresh_start():
    """Clear database, processed hashes, and CSV files for fresh start"""
    print("🔄 CLEARING EVERYTHING FOR FRESH START")
    print("=" * 60)
    
    try:
        # 1. Clear the database
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
        
        # 2. Clear processed hashes file
        print("\n🗑️ Clearing processed hashes...")
        hash_file = "data/processed_hashes.txt"
        if os.path.exists(hash_file):
            os.remove(hash_file)
            print("✅ Processed hashes file cleared")
        else:
            print("⚠️ Processed hashes file not found")
        
        # 3. Clear downloaded CSV files
        print("\n🗑️ Clearing downloaded CSV files...")
        csv_dir = Path("data/downloaded_csv")
        if csv_dir.exists():
            csv_files = list(csv_dir.glob("petty_cash_*.csv"))
            for csv_file in csv_files:
                csv_file.unlink()
            print(f"✅ Cleared {len(csv_files)} CSV files")
        else:
            print("⚠️ CSV directory not found")
        
        # 4. Clear zero amount transactions
        print("\n🗑️ Clearing zero amount transaction files...")
        zero_dir = Path("data/zero_amount_transactions")
        if zero_dir.exists():
            zero_files = list(zero_dir.glob("zero_amount_*.csv"))
            for zero_file in zero_files:
                zero_file.unlink()
            print(f"✅ Cleared {len(zero_files)} zero amount files")
        else:
            print("⚠️ Zero amount directory not found")
        
        # 5. Clear pending transactions
        print("\n🗑️ Clearing pending transaction files...")
        pending_dir = Path("pending_transactions")
        if pending_dir.exists():
            pending_files = list(pending_dir.glob("*.csv"))
            for pending_file in pending_files:
                pending_file.unlink()
            print(f"✅ Cleared {len(pending_files)} pending transaction files")
        else:
            print("⚠️ Pending transactions directory not found")
        
        print("\n🎯 EVERYTHING CLEARED!")
        print("📋 Next steps:")
        print("  1. Delete all inputs from your target Google Sheets")
        print("  2. Run: venv\\Scripts\\python.exe THe.py")
        print("  3. Watch the real-time processing at http://localhost:5000")
        print("  4. All transactions will be processed as NEW")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing everything: {e}")
        return False

if __name__ == "__main__":
    clear_everything_fresh_start() 