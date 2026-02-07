#!/usr/bin/env python3
"""Comprehensive data analysis to check data handling and identify unmatched transactions"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict, Counter

def analyze_data_handling():
    """Comprehensive analysis of data handling and unmatched transactions."""
    
    print("🔍 COMPREHENSIVE DATA ANALYSIS")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # 1. Overall transaction statistics
        print("\n📊 OVERALL TRANSACTION STATISTICS")
        print("-" * 40)
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status IS NOT NULL")
        processed_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        high_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'medium_confidence'")
        medium_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'low_confidence'")
        low_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'unmatched'")
        unmatched = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        print(f"  • Total transactions: {total_transactions:,}")
        print(f"  • Processed transactions: {processed_transactions:,}")
        print(f"  • High confidence: {high_confidence:,}")
        print(f"  • Medium confidence: {medium_confidence:,}")
        print(f"  • Low confidence: {low_confidence:,}")
        print(f"  • Unmatched: {unmatched:,}")
        print(f"  • Pending: {pending:,}")
        
        # 2. Data quality checks
        print("\n🔍 DATA QUALITY CHECKS")
        print("-" * 40)
        
        # Check for null amounts
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE amount IS NULL OR amount = 0")
        null_amounts = cursor.fetchone()[0]
        
        # Check for missing dates
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE date IS NULL OR date = ''")
        missing_dates = cursor.fetchone()[0]
        
        # Check for missing sources
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE source IS NULL OR source = ''")
        missing_sources = cursor.fetchone()[0]
        
        # Check for missing companies
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE company IS NULL OR company = ''")
        missing_companies = cursor.fetchone()[0]
        
        print(f"  • Null/zero amounts: {null_amounts}")
        print(f"  • Missing dates: {missing_dates}")
        print(f"  • Missing sources: {missing_sources}")
        print(f"  • Missing companies: {missing_companies}")
        
        # 3. Amount analysis
        print("\n💰 AMOUNT ANALYSIS")
        print("-" * 40)
        
        cursor.execute("SELECT MIN(amount), MAX(amount), AVG(amount) FROM transactions WHERE amount IS NOT NULL")
        min_amount, max_amount, avg_amount = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE amount < 0")
        negative_amounts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE amount > 10000")
        large_amounts = cursor.fetchone()[0]
        
        print(f"  • Amount range: ${min_amount:,.2f} to ${max_amount:,.2f}")
        print(f"  • Average amount: ${avg_amount:,.2f}")
        print(f"  • Negative amounts: {negative_amounts}")
        print(f"  • Large amounts (>$10k): {large_amounts}")
        
        # 4. Company distribution
        print("\n🏢 COMPANY DISTRIBUTION")
        print("-" * 40)
        
        cursor.execute("SELECT company, COUNT(*) FROM transactions GROUP BY company ORDER BY COUNT(*) DESC LIMIT 10")
        company_distribution = cursor.fetchall()
        
        for company, count in company_distribution:
            print(f"  • {company}: {count:,} transactions")
        
        # 5. Unmatched transactions analysis
        print("\n❌ UNMATCHED TRANSACTIONS ANALYSIS")
        print("-" * 40)
        
        # Get unmatched transactions
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE status = 'unmatched'
            GROUP BY source, company, amount, date
            ORDER BY count DESC
        """)
        unmatched_groups = cursor.fetchall()
        
        print(f"  • Total unmatched transaction groups: {len(unmatched_groups)}")
        
        # Analyze unmatched by company
        cursor.execute("""
            SELECT company, COUNT(*) 
            FROM transactions 
            WHERE status = 'unmatched'
            GROUP BY company 
            ORDER BY COUNT(*) DESC
        """)
        unmatched_by_company = cursor.fetchall()
        
        print(f"  • Unmatched by company:")
        for company, count in unmatched_by_company:
            print(f"    - {company}: {count} transactions")
        
        # 6. Low confidence transactions
        print("\n⚠️ LOW CONFIDENCE TRANSACTIONS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT source, company, amount, date, COUNT(*) as count
            FROM transactions 
            WHERE status = 'low_confidence'
            GROUP BY source, company, amount, date
            ORDER BY count DESC
            LIMIT 10
        """)
        low_confidence_groups = cursor.fetchall()
        
        print(f"  • Low confidence transaction groups: {len(low_confidence_groups)}")
        
        # 7. Target sheet distribution
        print("\n📋 TARGET SHEET DISTRIBUTION")
        print("-" * 40)
        
        cursor.execute("""
            SELECT target_sheet, COUNT(*) 
            FROM transactions 
            WHERE target_sheet IS NOT NULL
            GROUP BY target_sheet 
            ORDER BY COUNT(*) DESC
        """)
        sheet_distribution = cursor.fetchall()
        
        for sheet, count in sheet_distribution:
            print(f"  • {sheet}: {count:,} transactions")
        
        # 8. Date range analysis
        print("\n📅 DATE RANGE ANALYSIS")
        print("-" * 40)
        
        cursor.execute("SELECT MIN(date), MAX(date) FROM transactions WHERE date IS NOT NULL")
        min_date, max_date = cursor.fetchone()
        
        cursor.execute("""
            SELECT strftime('%Y-%m', date) as month, COUNT(*) 
            FROM transactions 
            WHERE date IS NOT NULL
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
        """)
        monthly_distribution = cursor.fetchall()
        
        print(f"  • Date range: {min_date} to {max_date}")
        print(f"  • Monthly distribution:")
        for month, count in monthly_distribution:
            print(f"    - {month}: {count:,} transactions")
        
        # 9. Duplicate analysis
        print("\n🔄 DUPLICATE ANALYSIS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT row_number, source, company, amount, COUNT(*) as count
            FROM transactions 
            GROUP BY row_number, source, company, amount
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        
        print(f"  • Duplicate transaction groups: {len(duplicates)}")
        if duplicates:
            print(f"  • Sample duplicates:")
            for row_num, source, company, amount, count in duplicates[:5]:
                print(f"    - Row {row_num}: {source} ({company}) ${amount:.2f} - {count} times")
        
        # 10. Generate user inspection list
        print("\n📋 USER INSPECTION LIST")
        print("-" * 40)
        
        # Get all unmatched transactions for user review
        cursor.execute("""
            SELECT DISTINCT source, company, amount, date, COUNT(*) as frequency
            FROM transactions 
            WHERE status = 'unmatched'
            GROUP BY source, company, amount, date
            ORDER BY frequency DESC, source
        """)
        unmatched_for_review = cursor.fetchall()
        
        print(f"  • Unmatched transactions requiring user review: {len(unmatched_for_review)}")
        
        # Get low confidence transactions for user review
        cursor.execute("""
            SELECT DISTINCT source, company, amount, date, COUNT(*) as frequency
            FROM transactions 
            WHERE status = 'low_confidence'
            GROUP BY source, company, amount, date
            ORDER BY frequency DESC, source
        """)
        low_confidence_for_review = cursor.fetchall()
        
        print(f"  • Low confidence transactions requiring review: {len(low_confidence_for_review)}")
        
        # Save detailed inspection lists
        inspection_data = {
            'summary': {
                'total_transactions': total_transactions,
                'processed_transactions': processed_transactions,
                'unmatched_count': unmatched,
                'low_confidence_count': low_confidence,
                'success_rate': f"{((high_confidence + medium_confidence) / total_transactions * 100):.1f}%"
            },
            'unmatched_transactions': [
                {
                    'source': source,
                    'company': company,
                    'amount': amount,
                    'date': date,
                    'frequency': frequency
                }
                for source, company, amount, date, frequency in unmatched_for_review
            ],
            'low_confidence_transactions': [
                {
                    'source': source,
                    'company': company,
                    'amount': amount,
                    'date': date,
                    'frequency': frequency
                }
                for source, company, amount, date, frequency in low_confidence_for_review
            ]
        }
        
        # Save to file
        with open('user_inspection_list.json', 'w') as f:
            json.dump(inspection_data, f, indent=2, default=str)
        
        print(f"  • Detailed inspection list saved to: user_inspection_list.json")
        
        # 11. Data handling assessment
        print("\n✅ DATA HANDLING ASSESSMENT")
        print("-" * 40)
        
        issues = []
        if null_amounts > 0:
            issues.append(f"Null/zero amounts: {null_amounts}")
        if missing_dates > 0:
            issues.append(f"Missing dates: {missing_dates}")
        if missing_sources > 0:
            issues.append(f"Missing sources: {missing_sources}")
        if missing_companies > 0:
            issues.append(f"Missing companies: {missing_companies}")
        if len(duplicates) > 0:
            issues.append(f"Duplicate transactions: {len(duplicates)} groups")
        
        if issues:
            print("  ⚠️ Issues found:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✅ No data quality issues found")
        
        success_rate = ((high_confidence + medium_confidence) / total_transactions * 100) if total_transactions > 0 else 0
        print(f"  • Overall success rate: {success_rate:.1f}%")
        
        if success_rate >= 95:
            print("  ✅ Excellent data handling")
        elif success_rate >= 90:
            print("  ✅ Good data handling")
        elif success_rate >= 80:
            print("  ⚠️ Fair data handling - review recommended")
        else:
            print("  ❌ Poor data handling - immediate review required")
        
        conn.close()
        
        return inspection_data
        
    except Exception as e:
        print(f"❌ Error in analysis: {e}")
        return None

if __name__ == "__main__":
    analyze_data_handling() 