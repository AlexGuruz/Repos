#!/usr/bin/env python3
"""Investigate REG transaction amounts to understand the issue"""

import sqlite3
from pathlib import Path

def investigate_reg_amounts():
    """Investigate REG transaction amounts."""
    
    print("🔍 INVESTIGATING REG TRANSACTION AMOUNTS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Get all REG transactions
        cursor.execute("""
            SELECT source, company, amount, date, target_sheet, target_header, status
            FROM transactions 
            WHERE source LIKE '%REG%'
            ORDER BY date, source
        """)
        reg_transactions = cursor.fetchall()
        
        print(f"🏦 ALL REG TRANSACTIONS:")
        print(f"  • Total REG transactions: {len(reg_transactions)}")
        
        # Group by date and type
        daily_regs = {}
        for source, company, amount, date, sheet, header, status in reg_transactions:
            if date not in daily_regs:
                daily_regs[date] = {'deposits': [], 'banks': [], 'withdrawals': []}
            
            if 'DEPOSIT' in source:
                daily_regs[date]['deposits'].append((source, company, amount, status))
            elif 'BANK' in source:
                daily_regs[date]['banks'].append((source, company, amount, status))
            elif 'WITHDRAW' in source:
                daily_regs[date]['withdrawals'].append((source, company, amount, status))
        
        print(f"\n📅 DAILY REG BREAKDOWN:")
        for date in sorted(daily_regs.keys()):
            deposits = daily_regs[date]['deposits']
            banks = daily_regs[date]['banks']
            withdrawals = daily_regs[date]['withdrawals']
            
            total_deposits = sum(d[2] for d in deposits)
            total_banks = sum(b[2] for b in banks)
            total_withdrawals = sum(w[2] for w in withdrawals)
            
            print(f"  • {date}:")
            print(f"    - Deposits: {len(deposits)} transactions, ${total_deposits:.2f}")
            print(f"    - Banks: {len(banks)} transactions, ${total_banks:.2f}")
            print(f"    - Withdrawals: {len(withdrawals)} transactions, ${total_withdrawals:.2f}")
            
            # Show individual transactions
            for source, company, amount, status in deposits:
                print(f"      * {source} ({company}): ${amount:.2f} [{status}]")
            for source, company, amount, status in banks:
                print(f"      * {source} ({company}): ${amount:.2f} [{status}]")
            for source, company, amount, status in withdrawals:
                print(f"      * {source} ({company}): ${amount:.2f} [{status}]")
        
        # Check for specific dates that might correspond to J184, J198
        print(f"\n🎯 SPECIFIC DATE ANALYSIS:")
        
        # Check what dates have the most REG activity
        cursor.execute("""
            SELECT date, COUNT(*) as count, SUM(amount) as total_amount
            FROM transactions 
            WHERE source LIKE '%REG%' AND target_sheet = 'INCOME'
            GROUP BY date
            ORDER BY count DESC
            LIMIT 10
        """)
        high_activity_dates = cursor.fetchall()
        
        print(f"  • Dates with highest REG activity:")
        for date, count, total in high_activity_dates:
            print(f"    - {date}: {count} transactions, ${total:.2f}")
        
        # Check for duplicate REG transactions on same date
        print(f"\n🔄 DUPLICATE REG TRANSACTIONS:")
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
            print(f"  ❌ FOUND DUPLICATE REG TRANSACTIONS:")
            for source, company, amount, date, count in duplicates:
                print(f"    - {source} ({company}) ${amount:.2f} on {date}: {count} times")
        else:
            print(f"  ✅ No duplicate REG transactions found")
        
        # Check the actual amounts being sent to Google Sheets
        print(f"\n📊 GOOGLE SHEETS TOTALS:")
        cursor.execute("""
            SELECT target_sheet, target_header, date, COUNT(*) as count, SUM(amount) as total
            FROM transactions 
            WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
            GROUP BY target_sheet, target_header, date
            ORDER BY date
        """)
        sheet_totals = cursor.fetchall()
        
        print(f"  • REG totals sent to Google Sheets:")
        for sheet, header, date, count, total in sheet_totals:
            print(f"    - {date}: {count} transactions → ${total:.2f}")
        
        # Check if there are any negative amounts that might be causing issues
        print(f"\n💰 NEGATIVE AMOUNTS:")
        cursor.execute("""
            SELECT source, company, amount, date
            FROM transactions 
            WHERE source LIKE '%REG%' AND amount < 0
            ORDER BY date, source
        """)
        negative_amounts = cursor.fetchall()
        
        if negative_amounts:
            print(f"  • REG transactions with negative amounts:")
            for source, company, amount, date in negative_amounts:
                print(f"    - {source} ({company}): ${amount:.2f} on {date}")
        else:
            print(f"  • No negative REG amounts found")
        
        conn.close()
        
        print(f"\n🎯 ANALYSIS:")
        print(f"  • If J184, J198 amounts are too high, check the daily totals above")
        print(f"  • The issue might be that multiple REG transactions are being added together")
        print(f"  • Or there might be duplicate transactions being processed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error investigating REG amounts: {e}")
        return False

if __name__ == "__main__":
    investigate_reg_amounts() 