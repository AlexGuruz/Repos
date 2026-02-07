#!/usr/bin/env python3
"""Investigate specific target cells to see what's happening with amounts"""

import sqlite3
from pathlib import Path

def investigate_target_cells():
    """Investigate specific target cells for amount issues."""
    
    print("🔍 INVESTIGATING TARGET CELLS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check what transactions are targeting REGISTERS column
        cursor.execute("""
            SELECT source, company, amount, date, target_sheet, target_header, target_cell
            FROM transactions 
            WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
            ORDER BY date, source
        """)
        reg_transactions = cursor.fetchall()
        
        print(f"🏦 REG TRANSACTIONS TARGETING INCOME/REGISTERS:")
        print(f"  • Total REG transactions: {len(reg_transactions)}")
        
        # Group by date to see daily totals
        daily_totals = {}
        for source, company, amount, date, sheet, header, cell in reg_transactions:
            if date not in daily_totals:
                daily_totals[date] = []
            daily_totals[date].append((source, company, amount, cell))
        
        print(f"\n📅 DAILY REG TRANSACTION TOTALS:")
        for date in sorted(daily_totals.keys()):
            transactions = daily_totals[date]
            total_amount = sum(t[2] for t in transactions)
            print(f"  • {date}: {len(transactions)} transactions, ${total_amount:.2f}")
            
            # Show individual transactions for this date
            for source, company, amount, cell in transactions:
                print(f"    - {source} ({company}): ${amount:.2f} → {cell}")
        
        # Check for specific cells mentioned (J184, J198)
        print(f"\n🎯 SPECIFIC CELL ANALYSIS:")
        
        # Find what dates correspond to J184 and J198
        cursor.execute("""
            SELECT DISTINCT date, target_cell
            FROM transactions 
            WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
            AND target_cell IN ('J184', 'J198')
            ORDER BY date
        """)
        specific_cells = cursor.fetchall()
        
        for date, cell in specific_cells:
            print(f"  • {cell} corresponds to date: {date}")
            
            # Get all transactions for this date
            cursor.execute("""
                SELECT source, company, amount, target_cell
                FROM transactions 
                WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
                AND date = ?
                ORDER BY source
            """, (date,))
            
            day_transactions = cursor.fetchall()
            total_day = sum(t[2] for t in day_transactions)
            
            print(f"    - Total for {date}: ${total_day:.2f}")
            for source, company, amount, target_cell in day_transactions:
                print(f"      * {source} ({company}): ${amount:.2f} → {target_cell}")
        
        # Check if there are multiple transactions targeting the same cell
        print(f"\n🔄 DUPLICATE CELL TARGETS:")
        cursor.execute("""
            SELECT target_cell, date, COUNT(*) as count, SUM(amount) as total_amount
            FROM transactions 
            WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
            GROUP BY target_cell, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicate_cells = cursor.fetchall()
        
        if duplicate_cells:
            print(f"  ❌ FOUND DUPLICATE CELL TARGETS:")
            for cell, date, count, total in duplicate_cells:
                print(f"    - {cell} on {date}: {count} transactions, ${total:.2f}")
                
                # Show the specific transactions
                cursor.execute("""
                    SELECT source, company, amount
                    FROM transactions 
                    WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
                    AND target_cell = ? AND date = ?
                    ORDER BY source
                """, (cell, date))
                
                transactions = cursor.fetchall()
                for source, company, amount in transactions:
                    print(f"      * {source} ({company}): ${amount:.2f}")
        else:
            print(f"  ✅ No duplicate cell targets found")
        
        # Check the actual Google Sheets update logic
        print(f"\n📊 GOOGLE SHEETS UPDATE ANALYSIS:")
        cursor.execute("""
            SELECT target_sheet, target_header, date, COUNT(*) as transaction_count, SUM(amount) as total_amount
            FROM transactions 
            WHERE target_header LIKE '%REG%' AND target_sheet = 'INCOME'
            GROUP BY target_sheet, target_header, date
            ORDER BY date
        """)
        sheet_updates = cursor.fetchall()
        
        print(f"  • REG updates to Google Sheets:")
        for sheet, header, date, count, total in sheet_updates:
            print(f"    - {date}: {count} transactions → ${total:.2f}")
        
        conn.close()
        
        print(f"\n🎯 CONCLUSION:")
        print(f"  • If amounts are too high, it means multiple transactions are targeting the same cell")
        print(f"  • The program should be ADDING amounts, not replacing them")
        print(f"  • Check if the Google Sheets update logic is working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error investigating target cells: {e}")
        return False

if __name__ == "__main__":
    investigate_target_cells() 