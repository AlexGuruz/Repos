#!/usr/bin/env python3
"""Check how many transactions actually got updated in Google Sheets"""

import sqlite3
from pathlib import Path

def check_actual_updates():
    """Check how many transactions actually got updated."""
    
    print("🔍 CHECKING ACTUAL GOOGLE SHEETS UPDATES")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check transactions that were actually sent to Google Sheets
        cursor.execute("""
            SELECT COUNT(*) FROM transactions 
            WHERE status = 'high_confidence' OR status = 'medium_confidence'
        """)
        matched_transactions = cursor.fetchone()[0]
        
        # Check transactions that have target coordinates
        cursor.execute("""
            SELECT COUNT(*) FROM transactions 
            WHERE target_sheet IS NOT NULL AND target_header IS NOT NULL
        """)
        with_targets = cursor.fetchone()[0]
        
        # Check transactions that were actually processed
        cursor.execute("""
            SELECT COUNT(*) FROM transactions 
            WHERE status IS NOT NULL AND status != 'pending'
        """)
        processed_transactions = cursor.fetchone()[0]
        
        # Get sample of high confidence transactions
        cursor.execute("""
            SELECT source, company, amount, target_sheet, target_header, status
            FROM transactions 
            WHERE status = 'high_confidence'
            LIMIT 10
        """)
        sample_high_confidence = cursor.fetchall()
        
        # Get sample of transactions with target coordinates
        cursor.execute("""
            SELECT source, company, amount, target_sheet, target_header, status
            FROM transactions 
            WHERE target_sheet IS NOT NULL AND target_header IS NOT NULL
            LIMIT 10
        """)
        sample_with_targets = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 TRANSACTION ANALYSIS:")
        print("-" * 30)
        print(f"  • Total transactions: 1959")
        print(f"  • High/Medium confidence: {matched_transactions}")
        print(f"  • With target coordinates: {with_targets}")
        print(f"  • Processed (non-pending): {processed_transactions}")
        
        print(f"\n📋 SAMPLE HIGH CONFIDENCE TRANSACTIONS:")
        print("-" * 40)
        for source, company, amount, target_sheet, target_header, status in sample_high_confidence:
            print(f"  {source} ({company}) - ${amount} -> {target_sheet}/{target_header}")
        
        print(f"\n📋 SAMPLE TRANSACTIONS WITH TARGETS:")
        print("-" * 40)
        for source, company, amount, target_sheet, target_header, status in sample_with_targets:
            print(f"  {source} ({company}) - ${amount} -> {target_sheet}/{target_header}")
        
        # Check if there were any Google Sheets API calls
        print(f"\n🔍 GOOGLE SHEETS INTEGRATION STATUS:")
        print("-" * 40)
        
        # Look for Google Sheets logs
        logs_dir = Path("logs")
        if logs_dir.exists():
            google_sheets_logs = list(logs_dir.glob("*google_sheets*"))
            if google_sheets_logs:
                print(f"  • Google Sheets logs found: {len(google_sheets_logs)}")
                for log_file in google_sheets_logs:
                    print(f"    - {log_file.name}")
            else:
                print("  • No Google Sheets logs found")
        
        # Check for batch update results
        print(f"\n🎯 ESTIMATED GOOGLE SHEETS UPDATES:")
        print("-" * 40)
        
        if with_targets > 0:
            print(f"  ✅ Approximately {with_targets} transactions should have been updated")
            print(f"  📊 This represents {with_targets/1959*100:.1f}% of total transactions")
        else:
            print("  ❌ No transactions had target coordinates")
            print("  ⚠️  This suggests the Google Sheets update step may not have run")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking updates: {e}")
        return False

if __name__ == "__main__":
    check_actual_updates() 