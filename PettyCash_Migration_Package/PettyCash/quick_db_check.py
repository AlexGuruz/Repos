#!/usr/bin/env python3
"""Quick database status check"""

import sqlite3

def check_db_status():
    """Check database status."""
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = cursor.fetchone()[0]
        
        # Check processed transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status IS NOT NULL")
        processed_count = cursor.fetchone()[0]
        
        # Check high confidence
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        high_confidence = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"📊 DATABASE STATUS:")
        print(f"  • Total transactions: {transaction_count}")
        print(f"  • Processed transactions: {processed_count}")
        print(f"  • High confidence: {high_confidence}")
        
        if transaction_count > 0:
            print(f"  • Processing progress: {processed_count/transaction_count*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

if __name__ == "__main__":
    check_db_status() 