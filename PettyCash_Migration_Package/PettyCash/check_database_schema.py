#!/usr/bin/env python3
"""Check database schema to understand available columns"""

import sqlite3

def check_database_schema():
    """Check the database schema."""
    
    print("🔍 CHECKING DATABASE SCHEMA")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = cursor.fetchall()
        
        print(f"📊 TRANSACTIONS TABLE COLUMNS:")
        for col in columns:
            print(f"  • {col[1]} ({col[2]})")
        
        # Check sample data
        cursor.execute("SELECT * FROM transactions LIMIT 1")
        sample = cursor.fetchone()
        
        if sample:
            print(f"\n📋 SAMPLE TRANSACTION:")
            for i, col in enumerate(columns):
                print(f"  • {col[1]}: {sample[i]}")
        
        # Check what columns contain REG data
        cursor.execute("SELECT * FROM transactions WHERE source LIKE '%REG%' LIMIT 1")
        reg_sample = cursor.fetchone()
        
        if reg_sample:
            print(f"\n🏦 SAMPLE REG TRANSACTION:")
            for i, col in enumerate(columns):
                print(f"  • {col[1]}: {reg_sample[i]}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False

if __name__ == "__main__":
    check_database_schema() 