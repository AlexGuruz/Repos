#!/usr/bin/env python3
"""Fix REG transaction duplication issue"""

import sqlite3
from pathlib import Path

def fix_reg_duplication():
    """Fix REG transaction duplication."""
    
    print("🔧 FIXING REG TRANSACTION DUPLICATION")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Find all REG BANK transactions that appear multiple times
        cursor.execute("""
            SELECT row_number, source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%' AND source LIKE '%BANK%'
            GROUP BY row_number, source, company, amount, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicated_reg_banks = cursor.fetchall()
        
        print(f"🔍 DUPLICATED REG BANK TRANSACTIONS:")
        print(f"  • Found {len(duplicated_reg_banks)} duplicated groups")
        
        for row_num, source, company, amount, date, count in duplicated_reg_banks:
            print(f"    - {source} ({company}) ${amount:.2f} on {date} - {count} times")
        
        # Show the actual duplicate records
        print(f"\n📋 DETAILED DUPLICATE RECORDS:")
        for row_num, source, company, amount, date, count in duplicated_reg_banks:
            cursor.execute("""
                SELECT transaction_id, row_number, source, company, amount, date, status
                FROM transactions 
                WHERE row_number = ? AND source = ? AND company = ? AND amount = ? AND date = ?
                ORDER BY transaction_id
            """, (row_num, source, company, amount, date))
            
            records = cursor.fetchall()
            print(f"\n  {source} ({company}) ${amount:.2f} on {date}:")
            for record in records:
                print(f"    - ID: {record[0]}, Status: {record[6]}")
        
        # Check if these are from different processing runs
        print(f"\n🔍 ANALYZING DUPLICATION PATTERN:")
        
        # Check transaction IDs to see if they're sequential
        cursor.execute("""
            SELECT transaction_id, row_number, source, company, amount, date
            FROM transactions 
            WHERE source LIKE '%REG%' AND source LIKE '%BANK%'
            ORDER BY transaction_id
        """)
        all_reg_banks = cursor.fetchall()
        
        print(f"  • Total REG BANK transactions: {len(all_reg_banks)}")
        
        # Group by unique transaction
        unique_transactions = {}
        for record in all_reg_banks:
            key = (record[1], record[2], record[3], record[4], record[5])  # row, source, company, amount, date
            if key not in unique_transactions:
                unique_transactions[key] = []
            unique_transactions[key].append(record[0])  # transaction_id
        
        duplicates_found = 0
        for key, transaction_ids in unique_transactions.items():
            if len(transaction_ids) > 1:
                duplicates_found += 1
                row_num, source, company, amount, date = key
                print(f"    - {source} ({company}) ${amount:.2f} on {date}: IDs {transaction_ids}")
        
        print(f"  • Total duplicate groups: {duplicates_found}")
        
        # Check if this is a processing issue or data issue
        print(f"\n🎯 RECOMMENDED ACTION:")
        
        if duplicates_found > 0:
            print(f"  ❌ DUPLICATION DETECTED!")
            print(f"  • The same REG transactions are being processed multiple times")
            print(f"  • This is causing amounts to be doubled in Google Sheets")
            print(f"  • Need to clear Google Sheets and fix processing logic")
            
            # Show which cells are affected
            print(f"\n📍 AFFECTED GOOGLE SHEETS CELLS:")
            for key, transaction_ids in unique_transactions.items():
                if len(transaction_ids) > 1:
                    row_num, source, company, amount, date = key
                    print(f"    - {source} → INCOME/REGISTERS on {date} (${amount:.2f} × {len(transaction_ids)})")
        else:
            print(f"  ✅ No duplication detected in current database")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing duplication: {e}")
        return False

if __name__ == "__main__":
    fix_reg_duplication() 