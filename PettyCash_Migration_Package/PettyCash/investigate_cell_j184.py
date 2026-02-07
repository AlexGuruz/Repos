#!/usr/bin/env python3
"""Investigate cell J184 and the REG transactions that should target it"""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime

def investigate_cell_j184():
    """Investigate what REG transactions should be targeting cell J184"""
    
    # Connect to database
    db_path = Path("petty_cash.db")
    if not db_path.exists():
        print("❌ Database not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔍 INVESTIGATING CELL J184")
    print("=" * 50)
    
    # First, let's understand what date corresponds to row 184
    # In Google Sheets, row 184 would be the 184th row
    # If headers are in row 19, then data starts at row 20
    # So row 184 would be the 165th data row (184 - 19 = 165)
    # This would correspond to a specific date
    
    print("📅 CALCULATING DATE FOR ROW 184:")
    print(f"  • Row 184 in Google Sheets")
    print(f"  • Headers are in row 19")
    print(f"  • Data starts at row 20")
    print(f"  • Row 184 = {184 - 19}th data row")
    
    # Let's find all REG transactions and their dates
    cursor.execute("""
        SELECT date, source, company, amount, status, target_sheet, target_header
        FROM transactions 
        WHERE source LIKE '%REG%' 
        ORDER BY date
    """)
    
    reg_transactions = cursor.fetchall()
    
    print(f"\n📊 FOUND {len(reg_transactions)} REG TRANSACTIONS")
    
    # Group by date
    date_groups = {}
    for row in reg_transactions:
        date, source, company, amount, status, target_sheet, target_header = row
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append({
            'source': source,
            'company': company,
            'amount': amount,
            'status': status,
            'target_sheet': target_sheet,
            'target_header': target_header
        })
    
    # Sort dates
    sorted_dates = sorted(date_groups.keys())
    
    print(f"\n📅 REG TRANSACTIONS BY DATE:")
    for i, date in enumerate(sorted_dates):
        transactions = date_groups[date]
        total_amount = sum(t['amount'] for t in transactions)
        reg_count = len([t for t in transactions if 'REG' in t['source']])
        
        print(f"  {i+1:2d}. {date}: {reg_count} REG transactions, Total: ${total_amount:,.2f}")
        
        # Show individual REG transactions for this date
        reg_transactions_for_date = [t for t in transactions if 'REG' in t['source']]
        for t in reg_transactions_for_date:
            print(f"      • {t['source']} ({t['company']}): ${t['amount']:,.2f}")
    
    # Now let's try to find which date corresponds to row 184
    # Let's look at the first few dates to understand the pattern
    print(f"\n🔍 ANALYZING FIRST 10 DATES:")
    for i, date in enumerate(sorted_dates[:10]):
        transactions = date_groups[date]
        reg_transactions_for_date = [t for t in transactions if 'REG' in t['source']]
        total_reg_amount = sum(t['amount'] for t in reg_transactions_for_date)
        
        print(f"  Row {20 + i}: {date} - REG Total: ${total_reg_amount:,.2f}")
        for t in reg_transactions_for_date:
            print(f"    • {t['source']}: ${t['amount']:,.2f}")
    
    # Let's also check if there are any transactions with specific row/column data
    cursor.execute("""
        SELECT date, source, company, amount, target_cell_row, target_cell_col, target_cell_address
        FROM transactions 
        WHERE source LIKE '%REG%' AND target_cell_row IS NOT NULL
        ORDER BY target_cell_row, date
    """)
    
    reg_with_coords = cursor.fetchall()
    
    print(f"\n📍 REG TRANSACTIONS WITH COORDINATES:")
    for row in reg_with_coords:
        date, source, company, amount, row_num, col_num, address = row
        print(f"  • {date}: {source} ({company}) ${amount:,.2f} → Row {row_num}, Col {col_num} ({address})")
    
    # Let's find transactions that might be targeting row 184
    cursor.execute("""
        SELECT date, source, company, amount, target_cell_row, target_cell_col, target_cell_address
        FROM transactions 
        WHERE target_cell_row = 184
        ORDER BY date, source
    """)
    
    row_184_transactions = cursor.fetchall()
    
    print(f"\n🎯 TRANSACTIONS TARGETING ROW 184:")
    if row_184_transactions:
        for row in row_184_transactions:
            date, source, company, amount, row_num, col_num, address = row
            print(f"  • {date}: {source} ({company}) ${amount:,.2f} → {address}")
    else:
        print("  ❌ No transactions found targeting row 184")
    
    # Let's check what the actual date for row 184 should be
    # If we have 165 data rows, let's see what the 165th date is
    if len(sorted_dates) >= 165:
        target_date = sorted_dates[164]  # 0-indexed, so 165th is at index 164
        print(f"\n🎯 PREDICTED DATE FOR ROW 184: {target_date}")
        
        if target_date in date_groups:
            reg_transactions_for_target_date = [t for t in date_groups[target_date] if 'REG' in t['source']]
            total_reg_amount = sum(t['amount'] for t in reg_transactions_for_target_date)
            
            print(f"📊 REG TRANSACTIONS FOR {target_date}:")
            for t in reg_transactions_for_target_date:
                print(f"  • {t['source']} ({t['company']}): ${t['amount']:,.2f}")
            print(f"💰 TOTAL REG AMOUNT FOR {target_date}: ${total_reg_amount:,.2f}")
    
    conn.close()

if __name__ == "__main__":
    investigate_cell_j184() 