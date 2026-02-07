#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST SCRIPT: 25 Random Transactions
Tests the complete petty cash sorter system from start to finish
"""

import openpyxl
import random
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/test_25_transactions.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class TransactionTester:
    def __init__(self):
        self.source_file = "2025 JGD FINANCIALS (3).xlsx"
        self.backup_file = "2025 JGD FINANCIALS (3)_BACKUP.xlsx"
        self.test_transactions = []
        
        # Sample data for random transactions
        self.sources = [
            "Starbucks", "McDonald's", "Walmart", "Target", "Amazon", 
            "Gas Station", "Grocery Store", "Restaurant", "Coffee Shop",
            "Office Supplies", "Hardware Store", "Pharmacy", "Convenience Store",
            "Fast Food", "Department Store", "Online Purchase", "Local Shop",
            "Food Truck", "Vending Machine", "Parking Meter"
        ]
        
        self.companies = ["NUGZ", "JGD", "PUFFIN"]
        self.initials = ["JD", "AB", "CD", "EF", "GH", "IJ", "KL", "MN", "OP", "QR"]
        
        logging.info("INITIALIZING TRANSACTION TESTER")
        logging.info("=" * 60)
    
    def create_backup(self):
        """Create a backup of the original file."""
        try:
            if Path(self.source_file).exists():
                shutil.copy2(self.source_file, self.backup_file)
                logging.info(f"Created backup: {self.backup_file}")
                return True
            else:
                logging.error(f"Source file not found: {self.source_file}")
                return False
        except Exception as e:
            logging.error(f"Error creating backup: {e}")
            return False
    
    def restore_backup(self):
        """Restore from backup."""
        try:
            if Path(self.backup_file).exists():
                shutil.copy2(self.backup_file, self.source_file)
                logging.info(f"Restored from backup: {self.backup_file}")
                return True
            else:
                logging.error(f"Backup file not found: {self.backup_file}")
                return False
        except Exception as e:
            logging.error(f"Error restoring backup: {e}")
            return False
    
    def generate_random_transactions(self, count=25):
        """Generate random transactions."""
        logging.info(f"GENERATING {count} RANDOM TRANSACTIONS")
        
        # Generate random dates in 2025
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 12, 31)
        
        for i in range(count):
            # Random date
            random_days = random.randint(0, (end_date - start_date).days)
            date = start_date + timedelta(days=random_days)
            
            # Random transaction data
            transaction = {
                'initials': random.choice(self.initials),
                'date': date.strftime('%m/%d/%y'),
                'company': random.choice(self.companies),
                'source': random.choice(self.sources),
                'amount': round(random.uniform(5.00, 150.00), 2)
            }
            
            self.test_transactions.append(transaction)
        
        logging.info(f"Generated {len(self.test_transactions)} random transactions")
        
        # Display sample transactions
        logging.info("Sample transactions:")
        for i, trans in enumerate(self.test_transactions[:5]):
            logging.info(f"  {i+1}. {trans['date']} - {trans['source']} ({trans['company']}) - ${trans['amount']}")
        if len(self.test_transactions) > 5:
            logging.info(f"  ... and {len(self.test_transactions) - 5} more")
    
    def add_transactions_to_excel(self):
        """Add test transactions to the Excel file."""
        logging.info("ADDING TRANSACTIONS TO EXCEL FILE")
        
        try:
            # Load workbook
            workbook = openpyxl.load_workbook(self.source_file)
            worksheet = workbook["PETTY CASH"]
            
            # Find the next empty row (starting from row 5)
            next_row = 5
            while worksheet[f'A{next_row}'].value is not None:
                next_row += 1
            
            logging.info(f"Adding transactions starting at row {next_row}")
            
            # Add transactions
            for i, transaction in enumerate(self.test_transactions):
                row_num = next_row + i
                
                # Column A: Initials
                worksheet[f'A{row_num}'] = transaction['initials']
                
                # Column B: Date
                worksheet[f'B{row_num}'] = transaction['date']
                
                # Column C: Company
                worksheet[f'C{row_num}'] = transaction['company']
                
                # Column D: Source
                worksheet[f'D{row_num}'] = transaction['source']
                
                # Column S: Amount (formatted as currency)
                worksheet[f'S{row_num}'] = f"$ {transaction['amount']:.2f}"
                
                logging.info(f"Added row {row_num}: {transaction['source']} - ${transaction['amount']}")
            
            # Save workbook
            workbook.save(self.source_file)
            workbook.close()
            
            logging.info(f"Successfully added {len(self.test_transactions)} transactions to Excel file")
            return True
            
        except Exception as e:
            logging.error(f"Error adding transactions to Excel: {e}")
            return False
    
    def run_petty_cash_sorter(self, dry_run=True):
        """Run the petty cash sorter."""
        logging.info("RUNNING PETTY CASH SORTER")
        logging.info("=" * 60)
        
        try:
            from petty_cash_sorter_final import FinalPettyCashSorter
            
            sorter = FinalPettyCashSorter()
            success = sorter.run(dry_run=dry_run)
            
            if success:
                logging.info("Petty cash sorter completed successfully")
                return True
            else:
                logging.error("Petty cash sorter failed")
                return False
                
        except Exception as e:
            logging.error(f"Error running petty cash sorter: {e}")
            return False
    
    def check_results(self):
        """Check the results of the processing."""
        logging.info("CHECKING RESULTS")
        logging.info("=" * 60)
        
        try:
            # Check preprocessed CSV
            preprocessed_file = "pending_transactions/Petty Cash PreProcessed.csv"
            if Path(preprocessed_file).exists():
                with open(preprocessed_file, 'r', encoding='utf-8') as f:
                    import csv
                    reader = csv.DictReader(f)
                    preprocessed_count = sum(1 for row in reader if row['Status'] == 'preprocessed')
                logging.info(f"Preprocessed transactions: {preprocessed_count}")
            else:
                logging.warning("Preprocessed CSV file not found")
            
            # Check processed CSV
            processed_file = "pending_transactions/Petty Cash Processed.csv"
            if Path(processed_file).exists():
                with open(processed_file, 'r', encoding='utf-8') as f:
                    import csv
                    reader = csv.DictReader(f)
                    processed_count = sum(1 for row in reader if row['Status'] == 'processed')
                logging.info(f"Processed transactions: {processed_count}")
            else:
                logging.warning("Processed CSV file not found")
            
            # Check failed CSV
            failed_file = "pending_transactions/Petty Cash Failed.csv"
            if Path(failed_file).exists():
                with open(failed_file, 'r', encoding='utf-8') as f:
                    import csv
                    reader = csv.DictReader(f)
                    failed_count = sum(1 for row in reader if row['Status'] == 'failed')
                logging.info(f"Failed transactions: {failed_count}")
            else:
                logging.info("No failed transactions found")
            
            # Check needs rules CSV
            needs_rules_file = "pending_transactions/Petty Cash Needs Rules.csv"
            if Path(needs_rules_file).exists():
                with open(needs_rules_file, 'r', encoding='utf-8') as f:
                    import csv
                    reader = csv.DictReader(f)
                    needs_rules_count = sum(1 for row in reader if row['Status'] == 'needs_rule')
                logging.info(f"Transactions needing rules: {needs_rules_count}")
            else:
                logging.info("No transactions needing rules found")
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking results: {e}")
            return False
    
    def run_complete_test(self):
        """Run the complete test from start to finish."""
        logging.info("STARTING COMPLETE TEST WITH 25 RANDOM TRANSACTIONS")
        logging.info("=" * 80)
        
        try:
            # Step 1: Create backup
            logging.info("STEP 1/6: Creating backup...")
            if not self.create_backup():
                return False
            
            # Step 2: Generate random transactions
            logging.info("STEP 2/6: Generating random transactions...")
            self.generate_random_transactions(25)
            
            # Step 3: Add transactions to Excel
            logging.info("STEP 3/6: Adding transactions to Excel file...")
            if not self.add_transactions_to_excel():
                return False
            
            # Step 4: Run dry run
            logging.info("STEP 4/6: Running dry run...")
            if not self.run_petty_cash_sorter(dry_run=True):
                return False
            
            # Step 5: Check results
            logging.info("STEP 5/6: Checking results...")
            if not self.check_results():
                return False
            
            # Step 6: Run live update (optional)
            logging.info("STEP 6/6: Running live update...")
            if not self.run_petty_cash_sorter(dry_run=False):
                return False
            
            # Final check
            logging.info("FINAL CHECK: Checking final results...")
            if not self.check_results():
                return False
            
            logging.info("COMPLETE TEST SUCCESSFULLY COMPLETED!")
            logging.info("=" * 80)
            
            return True
            
        except Exception as e:
            logging.error(f"Error in complete test: {e}")
            return False
        finally:
            # Always restore backup
            logging.info("Restoring original file from backup...")
            self.restore_backup()

def main():
    """Main function."""
    print("TEST SCRIPT: 25 Random Transactions")
    print("=" * 60)
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Create pending_transactions directory
    Path("pending_transactions").mkdir(exist_ok=True)
    
    tester = TransactionTester()
    success = tester.run_complete_test()
    
    if success:
        print("\n✅ Test completed successfully!")
        print("Check the logs for detailed information.")
    else:
        print("\n❌ Test failed!")
        print("Check the logs for error details.")
    
    print("\nPress Enter to continue...")
    input()

if __name__ == "__main__":
    main() 