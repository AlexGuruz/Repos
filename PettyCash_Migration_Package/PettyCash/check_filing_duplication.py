#!/usr/bin/env python3
"""Check for duplication issues in the filing system"""

import sqlite3
from pathlib import Path
import json

def check_filing_duplication():
    """Check for duplication issues."""
    
    print("🔍 CHECKING FOR DUPLICATION ISSUES")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check database transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        db_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        db_high_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'low_confidence'")
        db_low_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'unmatched'")
        db_unmatched = cursor.fetchone()[0]
        
        print(f"📊 DATABASE TRANSACTIONS:")
        print(f"  • Total: {db_transactions}")
        print(f"  • High confidence: {db_high_confidence}")
        print(f"  • Low confidence: {db_low_confidence}")
        print(f"  • Unmatched: {db_unmatched}")
        
        # Check for duplicates in database
        cursor.execute("""
            SELECT row_number, source, company, amount, COUNT(*) as count
            FROM transactions 
            GROUP BY row_number, source, company, amount
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        
        print(f"\n🔄 DUPLICATES IN DATABASE:")
        print(f"  • Duplicate groups: {len(duplicates)}")
        if duplicates:
            print(f"  • Sample duplicates:")
            for row_num, source, company, amount, count in duplicates[:5]:
                print(f"    - Row {row_num}: {source} ({company}) ${amount:.2f} - {count} times")
        
        # Check filing system
        filing_dir = Path("data/processed_transactions")
        if filing_dir.exists():
            csv_files = list(filing_dir.glob("*.csv"))
            print(f"\n📁 FILING SYSTEM:")
            print(f"  • CSV files found: {len(csv_files)}")
            
            total_filed = 0
            for csv_file in csv_files:
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    file_count = len(df)
                    total_filed += file_count
                    print(f"    - {csv_file.name}: {file_count} transactions")
                except Exception as e:
                    print(f"    - {csv_file.name}: Error reading - {e}")
            
            print(f"  • Total filed transactions: {total_filed}")
            
            # Check if filing count matches database
            if total_filed != db_transactions:
                print(f"  ⚠️ MISMATCH: Database has {db_transactions} but filing has {total_filed}")
                print(f"  ⚠️ This suggests transactions are being counted multiple times!")
        
        # Check specific REG transactions
        print(f"\n🏦 REG TRANSACTIONS ANALYSIS:")
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%' AND source LIKE '%DEPOSIT%'
            GROUP BY source, company, amount, date
            ORDER BY count DESC
            LIMIT 10
        """)
        reg_deposits = cursor.fetchall()
        
        print(f"  • REG DEPOSIT transactions:")
        for source, company, amount, date, count in reg_deposits:
            print(f"    - {source} ({company}) ${amount:.2f} on {date} - {count} times")
        
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%' AND source LIKE '%BANK%'
            GROUP BY source, company, amount, date
            ORDER BY count DESC
            LIMIT 10
        """)
        reg_banks = cursor.fetchall()
        
        print(f"  • REG BANK transactions:")
        for source, company, amount, date, count in reg_banks:
            print(f"    - {source} ({company}) ${amount:.2f} on {date} - {count} times")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking duplication: {e}")
        return False

if __name__ == "__main__":
    check_filing_duplication() 