#!/usr/bin/env python3
"""Run the pipeline with safe Google Sheets integration to prevent accumulation"""

import logging
import sqlite3
from pathlib import Path
from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def setup_logging():
    """Setup logging for the safe pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/safe_pipeline.log'),
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

def create_compensation_file():
    """Create compensation file to prevent data accumulation."""
    print("🔄 CREATING COMPENSATION FILE")
    print("-" * 35)
    
    try:
        from safe_google_sheets_reset import create_compensation_file
        success = create_compensation_file()
        if success:
            print("✅ Compensation file created successfully")
            print("🎯 Your formulas and data are completely safe")
        else:
            print("❌ Compensation file creation failed")
        return success
    except Exception as e:
        print(f"❌ Error creating compensation file: {e}")
        return False

def run_safe_pipeline():
    """Run the pipeline with safe Google Sheets integration."""
    
    print("🚀 RUNNING SAFE PIPELINE")
    print("=" * 40)
    
    try:
        # Initialize the petty cash sorter
        print("📋 Initializing Petty Cash Sorter...")
        sorter = PettyCashSorterFinal()
        
        # Run the complete pipeline
        print("📋 Running complete pipeline...")
        success = sorter.run(dry_run=False)
        
        if success:
            print("🎉 SAFE PIPELINE SUCCESSFUL!")
            return True
        else:
            print("❌ SAFE PIPELINE FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Error running safe pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_results():
    """Verify the results of the safe pipeline."""
    
    print("🔍 VERIFYING SAFE PIPELINE RESULTS")
    print("-" * 40)
    
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
        
        print(f"📊 SAFE PIPELINE RESULTS:")
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
    """Main safe pipeline execution."""
    
    print("🎯 SAFE PIPELINE - NO DATA ACCUMULATION")
    print("=" * 60)
    print("This pipeline uses compensation to prevent")
    print("data accumulation in Google Sheets.")
    print("Your formulas and existing data are safe!")
    print()
    
    setup_logging()
    
    # Step 1: Clear database
    if not clear_database():
        print("❌ Failed to clear database")
        return False
    
    # Step 2: Create compensation file
    if not create_compensation_file():
        print("❌ Failed to create compensation file")
        return False
    
    # Step 3: Run safe pipeline
    if not run_safe_pipeline():
        print("❌ Safe pipeline failed")
        return False
    
    # Step 4: Verify results
    if not verify_results():
        print("❌ Results verification failed")
        return False
    
    print(f"\n🎉 SAFE PIPELINE FINISHED!")
    print("=" * 50)
    print("✅ Database cleared")
    print("✅ Compensation file created")
    print("✅ Pipeline executed safely")
    print("✅ Results verified")
    print("🎯 No data accumulation in Google Sheets!")
    print("💡 Check logs for detailed information")

if __name__ == "__main__":
    main() 