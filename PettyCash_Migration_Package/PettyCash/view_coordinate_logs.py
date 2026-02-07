#!/usr/bin/env python3
"""View coordinate logs from the database"""

import sqlite3
from pathlib import Path

def view_coordinate_logs():
    """View coordinate logs from the database."""
    
    print("📊 VIEWING COORDINATE LOGS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check if coordinate columns exist
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'target_cell_row' not in columns:
            print("❌ Coordinate columns not found in database")
            print("  • Run the program first to create the new schema")
            return False
        
        # Get transactions with coordinates
        cursor.execute("""
            SELECT transaction_id, source, company, amount, date, 
                   target_sheet, target_header, target_cell_row, target_cell_col, target_cell_address,
                   status, notes
            FROM transactions 
            WHERE target_cell_row IS NOT NULL AND target_cell_col IS NOT NULL
            ORDER BY date, source
        """)
        
        transactions_with_coords = cursor.fetchall()
        
        print(f"📍 TRANSACTIONS WITH COORDINATES: {len(transactions_with_coords)}")
        
        if transactions_with_coords:
            print(f"\n📋 SAMPLE TRANSACTIONS WITH COORDINATES:")
            for i, transaction in enumerate(transactions_with_coords[:10], 1):
                trans_id, source, company, amount, date, sheet, header, row, col, address, status, notes = transaction
                print(f"  {i}. {source} ({company}) ${amount:.2f} on {date}")
                print(f"     → {sheet}/{header} → Cell({row},{col})")
                if address:
                    print(f"     → Address: {address}")
                print(f"     → Status: {status}")
                print()
        
        # Get audit log entries with coordinates
        cursor.execute("""
            SELECT transaction_id, status_from, status_to, message, timestamp
            FROM audit_log 
            WHERE message LIKE '%Cell(%' OR message LIKE '%→ %'
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        audit_entries = cursor.fetchall()
        
        print(f"📝 AUDIT LOG ENTRIES WITH COORDINATES: {len(audit_entries)}")
        
        if audit_entries:
            print(f"\n📋 RECENT COORDINATE AUDIT ENTRIES:")
            for i, entry in enumerate(audit_entries[:10], 1):
                trans_id, status_from, status_to, message, timestamp = entry
                print(f"  {i}. {trans_id} ({status_from} → {status_to})")
                print(f"     → {message}")
                print(f"     → {timestamp}")
                print()
        
        # Get coordinate statistics
        cursor.execute("""
            SELECT target_sheet, target_header, COUNT(*) as count
            FROM transactions 
            WHERE target_cell_row IS NOT NULL AND target_cell_col IS NOT NULL
            GROUP BY target_sheet, target_header
            ORDER BY count DESC
        """)
        
        coord_stats = cursor.fetchall()
        
        print(f"📊 COORDINATE STATISTICS:")
        for sheet, header, count in coord_stats:
            print(f"  • {sheet}/{header}: {count} transactions")
        
        # Get REG transactions specifically
        cursor.execute("""
            SELECT source, company, amount, date, target_cell_row, target_cell_col, target_cell_address
            FROM transactions 
            WHERE source LIKE '%REG%' AND target_cell_row IS NOT NULL
            ORDER BY date, source
        """)
        
        reg_transactions = cursor.fetchall()
        
        print(f"\n🏦 REG TRANSACTIONS WITH COORDINATES: {len(reg_transactions)}")
        
        if reg_transactions:
            print(f"📋 REG TRANSACTION COORDINATES:")
            for source, company, amount, date, row, col, address in reg_transactions[:10]:
                print(f"  • {source} ({company}) ${amount:.2f} on {date}")
                print(f"    → Cell({row},{col})")
                if address:
                    print(f"    → Address: {address}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error viewing coordinate logs: {e}")
        return False

if __name__ == "__main__":
    view_coordinate_logs() 