#!/usr/bin/env python3
"""Check what transactions are available for processing"""

import pandas as pd
from pathlib import Path

def check_available_transactions():
    """Check what transactions are available"""
    print("📊 CHECKING AVAILABLE TRANSACTIONS")
    print("=" * 50)
    
    try:
        # Check for CSV files
        csv_files = list(Path(".").glob("*.csv"))
        print(f"📁 Found {len(csv_files)} CSV files:")
        
        for csv_file in csv_files:
            print(f"  • {csv_file.name}")
            
            try:
                # Read CSV and show info
                df = pd.read_csv(csv_file)
                print(f"    - Rows: {len(df)}")
                print(f"    - Columns: {list(df.columns)}")
                
                # Show sample data
                if len(df) > 0:
                    print(f"    - Sample data:")
                    sample = df.head(3)
                    for idx, row in sample.iterrows():
                        print(f"      Row {idx+1}: {row.get('source', 'N/A')} - ${row.get('amount', 0):.2f}")
                print()
                
            except Exception as e:
                print(f"    - Error reading file: {e}")
        
        # Check database status
        print("🗄️ Database Status:")
        try:
            import sqlite3
            conn = sqlite3.connect("petty_cash.db")
            cursor = conn.cursor()
            
            # Check transactions table
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total_transactions = cursor.fetchone()[0]
            print(f"  • Total transactions in database: {total_transactions}")
            
            # Check by status
            cursor.execute("SELECT status, COUNT(*) FROM transactions GROUP BY status")
            status_counts = cursor.fetchall()
            for status, count in status_counts:
                print(f"    - {status}: {count}")
            
            conn.close()
            
        except Exception as e:
            print(f"  • Database error: {e}")
        
        print("\n💡 To see processing in action:")
        print("  1. Clear database: python clear_and_restart.py")
        print("  2. Run main script: python THe.py")
        print("  3. Watch real-time processing at http://localhost:5000")
        
    except Exception as e:
        print(f"❌ Error checking transactions: {e}")

if __name__ == "__main__":
    check_available_transactions() 