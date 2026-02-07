#!/usr/bin/env python3
"""Fix duplicate transactions in the database"""

import sqlite3
from pathlib import Path

def fix_duplicate_transactions():
    """Remove duplicate transactions from the database."""
    
    print("🔧 FIXING DUPLICATE TRANSACTIONS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Find duplicate transactions
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%'
            GROUP BY source, company, amount, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print(f"✅ No duplicate transactions found")
            return True
        
        print(f"❌ FOUND DUPLICATE TRANSACTIONS:")
        for source, company, amount, date, count in duplicates:
            print(f"  • {source} ({company}) ${amount:.2f} on {date}: {count} times")
        
        # Remove duplicates (keep the first occurrence, delete the rest)
        print(f"\n🗑️ REMOVING DUPLICATES:")
        
        for source, company, amount, date, count in duplicates:
            # Get all transaction IDs for this duplicate
            cursor.execute("""
                SELECT id, transaction_id, created_date
                FROM transactions 
                WHERE source = ? AND company = ? AND amount = ? AND date = ?
                ORDER BY created_date
            """, (source, company, amount, date))
            
            transaction_records = cursor.fetchall()
            
            # Keep the first one, delete the rest
            if len(transaction_records) > 1:
                first_id = transaction_records[0][0]
                duplicate_ids = [record[0] for record in transaction_records[1:]]
                
                print(f"  • Keeping first occurrence (ID: {first_id})")
                print(f"  • Deleting {len(duplicate_ids)} duplicates")
                
                # Delete duplicate records
                placeholders = ','.join(['?' for _ in duplicate_ids])
                cursor.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", duplicate_ids)
                
                print(f"    - Deleted IDs: {duplicate_ids}")
        
        # Commit the changes
        conn.commit()
        
        # Verify duplicates are removed
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE source LIKE '%REG%'
            GROUP BY source, company, amount, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        remaining_duplicates = cursor.fetchall()
        
        if not remaining_duplicates:
            print(f"\n✅ ALL DUPLICATES REMOVED!")
        else:
            print(f"\n❌ SOME DUPLICATES REMAIN:")
            for source, company, amount, date, count in remaining_duplicates:
                print(f"  • {source} ({company}) ${amount:.2f} on {date}: {count} times")
        
        # Show final counts
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE source LIKE '%REG%'")
        reg_transactions = cursor.fetchone()[0]
        
        print(f"\n📊 FINAL DATABASE STATE:")
        print(f"  • Total transactions: {total_transactions}")
        print(f"  • REG transactions: {reg_transactions}")
        
        conn.close()
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"  • Clear Google Sheets to remove accumulated amounts")
        print(f"  • Re-run the program with clean data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing duplicate transactions: {e}")
        return False

if __name__ == "__main__":
    fix_duplicate_transactions() 