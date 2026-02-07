#!/usr/bin/env python3
"""Check the results of the program run"""

import sqlite3
from pathlib import Path

def check_program_results():
    """Check what happened during the program run."""
    
    print("🔍 CHECKING PROGRAM RESULTS")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        # Check processed transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status IS NOT NULL")
        processed_transactions = cursor.fetchone()[0]
        
        # Check high confidence matches
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        high_confidence = cursor.fetchone()[0]
        
        # Check medium confidence matches
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'medium_confidence'")
        medium_confidence = cursor.fetchone()[0]
        
        # Check low confidence matches
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'low_confidence'")
        low_confidence = cursor.fetchone()[0]
        
        # Check pending transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        # Check payroll transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE source LIKE '%PAYROLL%'")
        payroll_count = cursor.fetchone()[0]
        
        # Check for duplicates
        cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT row_number, source, company, amount, COUNT(*) as count
                FROM transactions 
                GROUP BY row_number, source, company, amount
                HAVING COUNT(*) > 1
            )
        ''')
        duplicate_groups = cursor.fetchone()[0]
        
        # Get sample transactions
        cursor.execute("""
            SELECT source, company, amount, status 
            FROM transactions 
            ORDER BY created_date 
            LIMIT 10
        """)
        sample_transactions = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 TRANSACTION RESULTS:")
        print("-" * 25)
        print(f"  Total transactions: {total_transactions}")
        print(f"  Processed transactions: {processed_transactions}")
        print(f"  High confidence: {high_confidence}")
        print(f"  Medium confidence: {medium_confidence}")
        print(f"  Low confidence: {low_confidence}")
        print(f"  Pending: {pending}")
        print(f"  Payroll transactions: {payroll_count}")
        print(f"  Duplicate groups: {duplicate_groups}")
        
        print(f"\n📋 SAMPLE TRANSACTIONS:")
        print("-" * 25)
        for source, company, amount, status in sample_transactions:
            print(f"  {source} ({company}) - ${amount} - {status}")
        
        # Check if any transactions were sent to Google Sheets
        print(f"\n🔍 GOOGLE SHEETS UPDATES:")
        print("-" * 25)
        
        # Look for any files that might indicate Google Sheets updates
        pending_dir = Path("pending_transactions")
        if pending_dir.exists():
            files = list(pending_dir.glob("*.csv"))
            print(f"  Pending transaction files: {len(files)}")
            for file in files:
                print(f"    {file.name}")
        
        # Check logs
        logs_dir = Path("logs")
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            print(f"\n📋 LOG FILES:")
            print("-" * 15)
            for log_file in log_files:
                print(f"  {log_file.name}")
        
        # Overall assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        print("-" * 25)
        
        if total_transactions > 0:
            print("✅ Transactions were loaded from CSV")
        else:
            print("❌ No transactions were loaded")
        
        if processed_transactions > 0:
            print("✅ Transactions were processed by AI")
        else:
            print("❌ No transactions were processed")
        
        if high_confidence > 0:
            print("✅ High confidence matches found")
        else:
            print("⚠️  No high confidence matches")
        
        if duplicate_groups == 0:
            print("✅ No duplicate transactions")
        else:
            print(f"⚠️  {duplicate_groups} duplicate groups found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking results: {e}")
        return False

if __name__ == "__main__":
    check_program_results() 