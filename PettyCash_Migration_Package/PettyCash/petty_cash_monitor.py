
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Petty Cash Monitor - Detects and processes only new transactions
"""

import gspread
import logging
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from petty_cash_sorter_optimized import PettyCashSorter, HashGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/petty_cash_monitor.log'),
        logging.StreamHandler()
    ]
)

# Configuration
PETTY_CASH_URL = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU/edit?pli=1&gid=1785437689#gid=1785437689"
MONITOR_INTERVAL = 300  # 5 minutes
LAST_CHECK_FILE = "data/last_check.json"

class PettyCashMonitor:
    """Monitors PETTY CASH for new transactions and processes only new ones."""
    
    def __init__(self):
        self.sorter = PettyCashSorter()
        self.hash_generator = HashGenerator()
        self.processed_hashes = self.load_processed_hashes()
        self.last_check_time = self.load_last_check_time()
        self.gc = None
        self.authenticate()
        
    def authenticate(self):
        """Authenticate with Google Sheets."""
        try:
            self.gc = gspread.service_account(filename="config/service_account.json")
            logging.info("Successfully authenticated with Google Sheets (Monitor)")
            return True
        except Exception as e:
            logging.error(f"Authentication failed (Monitor): {e}")
            self.gc = None
            return False
    
    def load_processed_hashes(self) -> Set[str]:
        """Load previously processed hash IDs."""
        try:
            hash_file = Path("data/processed_hashes.txt")
            if hash_file.exists():
                with open(hash_file, 'r') as f:
                    hashes = set(line.strip() for line in f)
                logging.info(f"Loaded {len(hashes)} processed hashes")
                return hashes
            return set()
        except Exception as e:
            logging.error(f"Error loading processed hashes: {e}")
            return set()
    
    def load_last_check_time(self) -> datetime:
        """Load the last check time."""
        try:
            if Path(LAST_CHECK_FILE).exists():
                with open(LAST_CHECK_FILE, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
            return datetime.now() - timedelta(hours=24)  # Default to 24 hours ago
        except Exception as e:
            logging.error(f"Error loading last check time: {e}")
            return datetime.now() - timedelta(hours=24)
    
    def save_last_check_time(self):
        """Save the current check time."""
        try:
            Path(LAST_CHECK_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(LAST_CHECK_FILE, 'w') as f:
                json.dump({'last_check': datetime.now().isoformat()}, f)
        except Exception as e:
            logging.error(f"Error saving last check time: {e}")
    
    def get_new_transactions(self) -> List[Dict]:
        """Get only new transactions since last check."""
        try:
            if not self.gc:
                return []
            
            spreadsheet = self.gc.open_by_url(PETTY_CASH_URL)
            
            # Find the PETTY CASH worksheet
            petty_cash_worksheet = None
            for worksheet in spreadsheet.worksheets():
                if worksheet.title == "PETTY CASH":
                    petty_cash_worksheet = worksheet
                    break
            
            if not petty_cash_worksheet:
                logging.error("PETTY CASH worksheet not found")
                return []
            
            # Get all data
            all_data = petty_cash_worksheet.get_all_values()
            
            if len(all_data) < 5:
                logging.error("PETTY CASH sheet has insufficient data")
                return []
            
            # Headers are in row 4 (index 3)
            headers = all_data[3]
            data_start_row = 4
            
            # Column mapping
            date_col = 1      # Column B - 'DATE'
            company_col = 2   # Column C - ' COMPANY '
            source_col = 3    # Column D - ' SOURCE '
            total_col = 18    # Column S - ' Total '
            int_col = 0       # Column A - ' INT '
            
            new_transactions = []
            
            # Process transactions starting from row 5
            for row_idx, row in enumerate(all_data[data_start_row:], start=data_start_row + 1):
                if len(row) < max(date_col, source_col, total_col, int_col):
                    continue
                
                try:
                    # Extract transaction data
                    intials = row[int_col] if len(row) > int_col else ""
                    date = row[date_col] if len(row) > date_col else ""
                    company = row[company_col] if len(row) > company_col else ""
                    source = row[source_col] if len(row) > source_col else ""
                    amount_str = row[total_col] if len(row) > total_col else "0"
                    
                    # Clean and validate data
                    if not date or not source or not amount_str:
                        continue
                    
                    # Convert amount to float
                    try:
                        amount = float(amount_str.replace('$', '').replace(',', ''))
                    except:
                        amount = 0.0
                    
                    # Generate hash for this transaction
                    hash_id = self.hash_generator.generate_hash(
                        date, source, company, amount, row_idx
                    )
                    
                    # Check if this transaction is new (not already processed)
                    if hash_id not in self.processed_hashes:
                        # Create transaction record
                        transaction = {
                            'sheet': petty_cash_worksheet.title,
                            'row': row_idx,
                            'date': date,
                            'source': source.strip(),
                            'amount': amount,
                            'company': company.strip(),
                            'initials': intials.strip(),
                            'comment': "",  # Will be extracted later if needed
                            'hyperlink': None,  # Will be extracted later if needed
                            'hash_id': hash_id
                        }
                        
                        new_transactions.append(transaction)
                        logging.info(f"Found new transaction: {source} - ${amount} - {company}")
                    
                except Exception as e:
                    logging.warning(f"Error processing row {row_idx}: {e}")
                    continue
            
            logging.info(f"Found {len(new_transactions)} new transactions")
            return new_transactions
            
        except Exception as e:
            logging.error(f"Error getting new transactions: {e}")
            return []
    
    def process_new_transactions(self, new_transactions: List[Dict]) -> dict:
        """Process only the new transactions and return detailed results."""
        try:
            if not new_transactions:
                logging.info("No new transactions to process")
                return {
                    'success': True,
                    'processed_count': 0,
                    'new_sources_added': 0,
                    'message': 'No new transactions to process'
                }
            
            logging.info(f"Processing {len(new_transactions)} new transactions...")
            
            # Group by company for efficient rule loading
            transactions_by_company = {}
            for transaction in new_transactions:
                company = transaction['company']
                if company not in transactions_by_company:
                    transactions_by_company[company] = []
                transactions_by_company[company].append(transaction)
            
            processed_count = 0
            new_sources = set()
            
            # Process each company's transactions
            for company, transactions in transactions_by_company.items():
                logging.info(f"Processing {len(transactions)} transactions for {company}")
                
                # Load rules for this company
                rules = self.sorter.jgd_truth_manager.load_key_phrase_rules(company)
                
                for transaction in transactions:
                    # Check if source has rule
                    if transaction['source'] in rules:
                        rule = rules[transaction['source']]
                        target_sheet = rule['target_sheet']
                        target_header = rule['target_header']
                        
                        # Get target cell
                        col, row = self.sorter.jgd_truth_manager.get_target_cell(
                            target_sheet, target_header, transaction['date']
                        )
                        
                        if col is not None and row is not None:
                            # Create cell comment
                            comment = f"{transaction['source']}\n{transaction['initials']}"
                            if transaction.get('comment'):
                                comment += f"\n{transaction['comment']}"
                            
                            # Write to target cell
                            success = self.write_transaction_to_cell(
                                target_sheet, col, row, transaction, comment
                            )
                            
                            if success:
                                self.processed_hashes.add(transaction['hash_id'])
                                processed_count += 1
                                logging.info(f"Processed: {transaction['source']} -> {target_sheet}/{target_header}")
                            else:
                                logging.error(f"Failed to write transaction: {transaction['source']}")
                        else:
                            logging.warning(f"No target cell found for: {transaction['source']}")
                    else:
                        # New source - add to JGD Truth
                        new_sources.add((company, transaction['source']))
                        logging.warning(f"No rule found for: {transaction['source']} in {company}")
            
            # Add new sources to JGD Truth
            if new_sources:
                logging.info(f"Adding {len(new_sources)} new sources to JGD Truth...")
                for company, source in new_sources:
                    self.sorter.jgd_truth_manager.add_new_source_to_jgd_truth(company, source)
            
            # Save processed hashes
            self.save_processed_hashes()
            
            logging.info(f"New transaction processing complete!")
            logging.info(f"   Processed: {processed_count}")
            logging.info(f"   New sources added: {len(new_sources)}")
            logging.info(f"   Total new transactions: {len(new_transactions)}")
            
            return {
                'success': True,
                'processed_count': processed_count,
                'new_sources_added': len(new_sources),
                'message': f"Processed {processed_count} transactions, added {len(new_sources)} new sources"
            }
            
        except Exception as e:
            logging.error(f"Error processing new transactions: {e}")
            return {
                'success': False,
                'processed_count': 0,
                'new_sources_added': 0,
                'message': f"Error processing transactions: {e}"
            }
    
    def write_transaction_to_cell(self, target_sheet: str, col: int, row: int, transaction: Dict, comment: str) -> bool:
        """Write transaction to target cell."""
        try:
            if not self.gc:
                return False
            
            # Open 2025 JGD FINANCIALS spreadsheet
            spreadsheet = self.gc.open_by_url(PETTY_CASH_URL)
            
            # Find the target worksheet
            target_worksheet = None
            for worksheet in spreadsheet.worksheets():
                if worksheet.title == target_sheet:
                    target_worksheet = worksheet
                    break
            
            if not target_worksheet:
                logging.error(f"Target worksheet '{target_sheet}' not found")
                return False
            
            # Get current value in the cell
            current_value = target_worksheet.cell(row, col).value or "0"
            
            # Add transaction amount to current value
            try:
                current_amount = float(current_value.replace('$', '').replace(',', ''))
                new_amount = current_amount + transaction['amount']
                
                # Format the new amount
                formatted_amount = f"${new_amount:,.2f}"
                
                # Write amount to cell
                target_worksheet.update_cell(row, col, formatted_amount)
                
                # Handle comment merging
                if comment:
                    self._merge_cell_comment(target_worksheet, row, col, comment)
                
                logging.info(f"Updated {target_sheet} cell ({row},{col}): {current_amount} + {transaction['amount']} = {new_amount}")
                return True
                
            except ValueError:
                logging.error(f"Invalid amount format in cell: {current_value}")
                return False
            
        except Exception as e:
            logging.error(f"Error writing transaction to cell: {e}")
            return False
    
    def _merge_cell_comment(self, worksheet, row: int, col: int, new_comment: str):
        """Merge new comment with existing comment in the cell."""
        try:
            cell_address = f"{chr(64 + col)}{row}"
            
            # Try to get existing comment
            existing_comment = None
            try:
                # This is a placeholder - actual comment retrieval depends on Google Sheets API
                # For now, we'll log the merge operation
                existing_comment = "EXISTING_COMMENT"  # Placeholder
            except Exception as e:
                logging.debug(f"Could not retrieve existing comment for {cell_address}: {e}")
            
            # Merge comments
            if existing_comment and existing_comment.strip():
                # Add separator and new comment
                merged_comment = f"{existing_comment}\n\n--- Petty Cash Transaction ---\n{new_comment}"
                logging.info(f"Merged comment for {cell_address}: {merged_comment}")
            else:
                # No existing comment, just use new comment
                merged_comment = new_comment
                logging.info(f"New comment for {cell_address}: {merged_comment}")
            
            # Log the comment for manual addition (since Google Sheets API comment writing is limited)
            logging.info(f"COMMENT FOR {cell_address}: {merged_comment}")
            
        except Exception as e:
            logging.error(f"Error merging comment for cell {cell_address}: {e}")
    
    def save_processed_hashes(self):
        """Save processed hash IDs to file."""
        try:
            hash_file = Path("data/processed_hashes.txt")
            hash_file.parent.mkdir(parents=True, exist_ok=True)
            with open(hash_file, 'w') as f:
                for hash_id in self.processed_hashes:
                    f.write(f"{hash_id}\n")
            logging.info(f"Saved {len(self.processed_hashes)} processed hashes")
        except Exception as e:
            logging.error(f"Error saving processed hashes: {e}")
    
    def run_monitor_loop(self, interval_seconds: int = MONITOR_INTERVAL):
        """Run the monitoring loop continuously."""
        logging.info(f"Starting Petty Cash Monitor (checking every {interval_seconds} seconds)")
        
        try:
            while True:
                try:
                    logging.info("Checking for new transactions...")
                    
                    # Get new transactions
                    new_transactions = self.get_new_transactions()
                    
                    if new_transactions:
                        logging.info(f"Found {len(new_transactions)} new transactions")
                        
                        # Process new transactions
                        success = self.process_new_transactions(new_transactions)
                        
                        if success:
                            logging.info("Successfully processed new transactions")
                        else:
                            logging.error("Failed to process new transactions")
                    else:
                        logging.info("No new transactions found")
                    
                    # Save check time
                    self.save_last_check_time()
                    
                    # Wait for next check
                    logging.info(f"Waiting {interval_seconds} seconds until next check...")
                    time.sleep(interval_seconds)
                    
                except KeyboardInterrupt:
                    logging.info("Monitor stopped by user")
                    break
                except Exception as e:
                    logging.error(f"Error in monitor loop: {e}")
                    logging.info("Waiting 60 seconds before retry...")
                    time.sleep(60)
                    
        except Exception as e:
            logging.error(f"Fatal error in monitor: {e}")
    
    def run_single_check(self) -> dict:
        """Run a single check for new transactions and return detailed results."""
        try:
            logging.info("Running single check for new transactions...")
            
            # Get new transactions
            new_transactions = self.get_new_transactions()
            
            result = {
                'success': True,
                'new_transactions_found': len(new_transactions),
                'processed_count': 0,
                'new_sources_added': 0,
                'message': ''
            }
            
            if new_transactions:
                logging.info(f"Found {len(new_transactions)} new transactions")
                result['message'] = f"Found {len(new_transactions)} new transactions"
                
                # Process new transactions
                process_result = self.process_new_transactions(new_transactions)
                
                if process_result['success']:
                    logging.info("Successfully processed new transactions")
                    result['processed_count'] = process_result['processed_count']
                    result['new_sources_added'] = process_result['new_sources_added']
                    result['message'] = process_result['message']
                else:
                    logging.error("Failed to process new transactions")
                    result['success'] = False
                    result['message'] = process_result['message']
                    return result
            else:
                logging.info("No new transactions found")
                result['message'] = "No new transactions found"
            
            # Save check time
            self.save_last_check_time()
            
            return result
            
        except Exception as e:
            logging.error(f"Error in single check: {e}")
            return {
                'success': False,
                'new_transactions_found': 0,
                'processed_count': 0,
                'new_sources_added': 0,
                'message': f"Error: {e}"
            }

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Petty Cash Monitor")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=MONITOR_INTERVAL, help="Check interval in seconds")
    parser.add_argument("--single", action="store_true", help="Run single check only")
    args = parser.parse_args()
    
    print("Petty Cash Monitor")
    print("=" * 50)
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Initialize monitor
    monitor = PettyCashMonitor()
    
    if args.single:
        # Run single check
        success = monitor.run_single_check()
        if success:
            print("Single check completed successfully!")
        else:
            print("Single check failed!")
            return 1
    else:
        # Run continuous monitoring
        monitor.run_monitor_loop(args.interval)
    
    return 0

if __name__ == "__main__":
    exit(main()) 