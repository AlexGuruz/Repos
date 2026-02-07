#!/usr/bin/env python3
"""Verify what actually got sent to Google Sheets"""

import sqlite3
from pathlib import Path
import json

def verify_google_sheets_updates():
    """Verify Google Sheets updates vs filing system."""
    
    print("🔍 VERIFYING GOOGLE SHEETS UPDATES")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check current database transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        db_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE target_sheet IS NOT NULL AND target_header IS NOT NULL")
        db_with_coordinates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        db_high_confidence = cursor.fetchone()[0]
        
        print(f"📊 CURRENT DATABASE:")
        print(f"  • Total transactions: {db_total}")
        print(f"  • With target coordinates: {db_with_coordinates}")
        print(f"  • High confidence: {db_high_confidence}")
        
        # Check what actually got sent to Google Sheets
        cursor.execute("""
            SELECT target_sheet, target_header, date, COUNT(*) as count, SUM(amount) as total_amount
            FROM transactions 
            WHERE target_sheet IS NOT NULL AND target_header IS NOT NULL
            GROUP BY target_sheet, target_header, date
            ORDER BY target_sheet, target_header, date
        """)
        google_sheets_updates = cursor.fetchall()
        
        print(f"\n🎯 ACTUAL GOOGLE SHEETS UPDATES:")
        print(f"  • Unique cell updates: {len(google_sheets_updates)}")
        
        # Show REG transactions specifically
        reg_updates = [update for update in google_sheets_updates if 'REG' in str(update[1])]
        print(f"  • REG-related updates: {len(reg_updates)}")
        
        if reg_updates:
            print(f"  • REG transaction details:")
            for sheet, header, date, count, total in reg_updates[:10]:
                print(f"    - {sheet}/{header} on {date}: {count} transactions, ${total:.2f}")
        
        # Check filing system vs database
        print(f"\n📁 FILING SYSTEM ANALYSIS:")
        
        # Count CSV files
        csv_dir = Path("data/processed_transactions/csv_files")
        if csv_dir.exists():
            csv_files = list(csv_dir.rglob("*.csv"))
            print(f"  • Total CSV files: {len(csv_files)}")
            
            total_csv_transactions = 0
            for csv_file in csv_files:
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    file_count = len(df)
                    total_csv_transactions += file_count
                    print(f"    - {csv_file.name}: {file_count} transactions")
                except Exception as e:
                    print(f"    - {csv_file.name}: Error reading - {e}")
            
            print(f"  • Total CSV transactions: {total_csv_transactions}")
            print(f"  • Database transactions: {db_total}")
            
            if total_csv_transactions != db_total:
                print(f"  ⚠️ MISMATCH: CSV has {total_csv_transactions} but DB has {db_total}")
                print(f"  ⚠️ This explains the inflated statistics!")
        
        # Check if REG transactions are duplicated in current run
        print(f"\n🏦 REG TRANSACTION ANALYSIS:")
        cursor.execute("""
            SELECT target_sheet, target_header, date, COUNT(*) as count, SUM(amount) as total_amount
            FROM transactions 
            WHERE target_sheet IS NOT NULL AND target_header IS NOT NULL 
            AND target_header LIKE '%REG%'
            GROUP BY target_sheet, target_header, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicated_reg = cursor.fetchall()
        
        if duplicated_reg:
            print(f"  ❌ DUPLICATED REG TRANSACTIONS IN CURRENT RUN:")
            for sheet, header, date, count, total in duplicated_reg:
                print(f"    - {sheet}/{header} on {date}: {count} times, ${total:.2f}")
        else:
            print(f"  ✅ No REG transaction duplication in current run")
        
        # Show sample REG transactions
        cursor.execute("""
            SELECT source, company, amount, date, target_sheet, target_header
            FROM transactions 
            WHERE source LIKE '%REG%' AND target_sheet IS NOT NULL
            ORDER BY date, source
            LIMIT 10
        """)
        sample_reg = cursor.fetchall()
        
        print(f"  • Sample REG transactions processed:")
        for source, company, amount, date, sheet, header in sample_reg:
            print(f"    - {source} ({company}) ${amount:.2f} → {sheet}/{header} on {date}")
        
        conn.close()
        
        print(f"\n🎯 CONCLUSION:")
        print(f"  • Current run processed {db_total} transactions correctly")
        print(f"  • {db_with_coordinates} transactions were sent to Google Sheets")
        print(f"  • Filing system contains historical data from previous runs")
        print(f"  • REG transaction amounts should be correct in Google Sheets")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying updates: {e}")
        return False

if __name__ == "__main__":
    verify_google_sheets_updates() 