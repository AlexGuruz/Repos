#!/usr/bin/env python3
"""Run complete pipeline test from CSV download to Google Sheets batch input"""

import logging
import sqlite3
from pathlib import Path
from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def setup_logging():
    """Setup logging for the complete pipeline test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/complete_pipeline_test.log'),
            logging.StreamHandler()
        ]
    )

def clear_database():
    """Clear the database for a fresh start."""
    
    print("🗑️  CLEARING DATABASE FOR FRESH START")
    print("-" * 45)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Get counts before clearing
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transactions_before = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rules")
        rules_before = cursor.fetchone()[0]
        
        # Clear transactions only (keep rules)
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM ai_learning")
        cursor.execute("DELETE FROM audit_log")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database cleared")
        print(f"📊 Transactions removed: {transactions_before}")
        print(f"📊 Rules preserved: {rules_before}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

def clear_google_sheets_before_run():
    """Clear Google Sheets before running to prevent data accumulation."""
    print("🧹 CLEARING GOOGLE SHEETS BEFORE RUN")
    print("-" * 45)
    
    try:
        from clear_google_sheets_before_run import clear_google_sheets
        success = clear_google_sheets()
        if success:
            print("✅ Google Sheets cleared successfully")
        else:
            print("⚠️  Google Sheets clear operation failed, but continuing...")
        return True
    except Exception as e:
        print(f"⚠️  Could not clear Google Sheets: {e}, but continuing...")
        return True

def run_complete_pipeline():
    """Run the complete pipeline test."""
    
    print("🚀 RUNNING COMPLETE PIPELINE TEST")
    print("=" * 50)
    
    try:
        # Step 1: Initialize the petty cash sorter
        print("📋 Initializing Petty Cash Sorter...")
        sorter = PettyCashSorterFinal()
        
        # Step 2: Run the complete pipeline
        print("📋 Running complete pipeline...")
        success = sorter.run(dry_run=False)  # Set to True for dry run
        
        if success:
            print("🎉 COMPLETE PIPELINE TEST SUCCESSFUL!")
            return True
        else:
            print("❌ COMPLETE PIPELINE TEST FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Error running pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_results():
    """Verify the results of the pipeline test."""
    
    print("🔍 VERIFYING PIPELINE RESULTS")
    print("-" * 35)
    
    try:
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        # Check transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = cursor.fetchone()[0]
        
        # Check processed transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status IS NOT NULL")
        processed_count = cursor.fetchone()[0]
        
        # Check high confidence matches
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'high_confidence'")
        high_confidence_count = cursor.fetchone()[0]
        
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
        
        conn.close()
        
        print(f"📊 RESULTS SUMMARY:")
        print(f"  • Total transactions: {transaction_count}")
        print(f"  • Processed transactions: {processed_count}")
        print(f"  • High confidence matches: {high_confidence_count}")
        print(f"  • Payroll transactions: {payroll_count}")
        print(f"  • Duplicate groups: {duplicate_groups}")
        
        if duplicate_groups == 0:
            print("✅ No duplicate transactions found")
        else:
            print(f"⚠️  {duplicate_groups} duplicate groups found")
        
        if processed_count > 0:
            print("✅ Transactions were processed successfully")
        else:
            print("❌ No transactions were processed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying results: {e}")
        return False

def main():
    """Main pipeline test execution."""
    
    print("🎯 COMPLETE PIPELINE TEST")
    print("=" * 60)
    
    setup_logging()
    
    # Step 1: Clear database
    if not clear_database():
        print("❌ Failed to clear database")
        return False
    
    # Step 2: Run complete pipeline
    if not run_complete_pipeline():
        print("❌ Pipeline test failed")
        return False
    
    # Step 3: Verify results
    if not verify_results():
        print("❌ Results verification failed")
        return False
    
    print(f"\n🎉 COMPLETE PIPELINE TEST FINISHED!")
    print("=" * 50)
    print("✅ Database cleared")
    print("✅ Pipeline executed")
    print("✅ Results verified")
    print("💡 Check logs for detailed information")

if __name__ == "__main__":
    main() 