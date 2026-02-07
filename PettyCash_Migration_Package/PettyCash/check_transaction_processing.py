#!/usr/bin/env python3
"""Check if the same transactions are being processed multiple times"""

import sqlite3
from pathlib import Path

def check_transaction_processing():
    """Check for duplicate transaction processing."""
    
    print("🔍 CHECKING TRANSACTION PROCESSING")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check if transactions are being processed multiple times
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%'
            GROUP BY source, company, amount, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"❌ DUPLICATE TRANSACTIONS FOUND:")
            for source, company, amount, date, count in duplicates:
                print(f"  • {source} ({company}) ${amount:.2f} on {date}: {count} times")
        else:
            print(f"✅ No duplicate transactions found in database")
        
        # Check if the same transactions are being downloaded multiple times
        print(f"\n📥 DOWNLOAD ANALYSIS:")
        
        # Check if there are multiple CSV files with the same data
        csv_dir = Path("data/downloaded_csv")
        if csv_dir.exists():
            csv_files = list(csv_dir.glob("*.csv"))
            print(f"  • Downloaded CSV files: {len(csv_files)}")
            
            for csv_file in csv_files:
                print(f"    - {csv_file.name}")
        
        # Check if the program is running multiple times on the same data
        print(f"\n🔄 PROCESSING HISTORY:")
        
        # Check if there are multiple runs with the same transaction data
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%'
            GROUP BY date
            ORDER BY count DESC
            LIMIT 10
        """)
        daily_counts = cursor.fetchall()
        
        print(f"  • REG transactions per day:")
        for date, count in daily_counts:
            print(f"    - {date}: {count} transactions")
        
        # Check if the same row numbers are being processed multiple times
        cursor.execute("""
            SELECT row_number, source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%'
            GROUP BY row_number, source, company, amount, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        row_duplicates = cursor.fetchall()
        
        if row_duplicates:
            print(f"\n❌ DUPLICATE ROW PROCESSING:")
            for row_num, source, company, amount, date, count in row_duplicates:
                print(f"  • Row {row_num}: {source} ({company}) ${amount:.2f} on {date}: {count} times")
        else:
            print(f"\n✅ No duplicate row processing found")
        
        # Check if the program is being run multiple times without clearing the database
        print(f"\n📊 DATABASE STATE:")
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE source LIKE '%REG%'")
        reg_transactions = cursor.fetchone()[0]
        
        print(f"  • Total transactions: {total_transactions}")
        print(f"  • REG transactions: {reg_transactions}")
        
        # Check if this is a fresh run or accumulated data
        if total_transactions > 2000:  # Assuming fresh data should be around 1959
            print(f"  ⚠️ Database appears to have accumulated data from multiple runs")
        else:
            print(f"  ✅ Database appears to have fresh data from single run")
        
        conn.close()
        
        print(f"\n🎯 CONCLUSION:")
        print(f"  • If amounts are too high, it's because the same transactions were processed multiple times")
        print(f"  • The program should only process each transaction once")
        print(f"  • Check if the database was cleared between runs")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking transaction processing: {e}")
        return False

if __name__ == "__main__":
    check_transaction_processing() 