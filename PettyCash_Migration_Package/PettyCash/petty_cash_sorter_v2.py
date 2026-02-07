#!/usr/bin/env python3
"""
Petty Cash Sorter V2 - Complete Integration
Integrates database, CSV downloader, rule loader, AI matcher, and Google Sheets
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Optional
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from rule_loader import RuleLoader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher

class PettyCashSorterV2:
    def __init__(self):
        # Initialize components
        self.db_manager = DatabaseManager()
        self.csv_downloader = CSVDownloader()
        self.rule_loader = RuleLoader()
        self.ai_matcher = AIRuleMatcher()
        
        # Configuration
        self.batch_size = 100  # Process transactions in batches
        self.min_confidence = 5  # Minimum confidence for matching
        
        # Create directories
        Path("logs").mkdir(exist_ok=True)
        Path("data/processed_data").mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/petty_cash_sorter_v2.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING PETTY CASH SORTER V2")
        logging.info("=" * 60)
    
    def initialize_system(self) -> bool:
        """Initialize the complete system."""
        try:
            logging.info("Initializing system components...")
            
            # 1. Create database
            if not self.db_manager.create_database():
                logging.error("Failed to create database")
                return False
            
            # 2. Load rules from JGD Truth
            if not self.rule_loader.reload_rules():
                logging.error("Failed to load rules from JGD Truth")
                return False
            
            # 3. Load rules into AI matcher
            if not self.ai_matcher.load_rules_from_database():
                logging.error("Failed to load rules into AI matcher")
                return False
            
            logging.info("✅ System initialization complete")
            return True
            
        except Exception as e:
            logging.error(f"Error initializing system: {e}")
            return False
    
    def download_and_process_transactions(self) -> Optional[List[Dict]]:
        """Download transactions and identify new ones."""
        try:
            logging.info("Downloading transactions from Google Sheets...")
            
            # Download all transactions
            all_transactions = self.csv_downloader.download_petty_cash_data()
            if not all_transactions:
                logging.error("Failed to download transactions")
                return None
            
            logging.info(f"Downloaded {len(all_transactions)} total transactions")
            
            # Identify new transactions (not in database)
            new_transactions = []
            for transaction in all_transactions:
                existing = self.db_manager.get_transaction_by_row(transaction['row_number'])
                if not existing:
                    new_transactions.append(transaction)
            
            logging.info(f"Found {len(new_transactions)} new transactions to process")
            return new_transactions
            
        except Exception as e:
            logging.error(f"Error downloading and processing transactions: {e}")
            return None
    
    def process_transactions_batch(self, transactions: List[Dict]) -> Dict:
        """Process a batch of transactions."""
        try:
            logging.info(f"Processing batch of {len(transactions)} transactions...")
            
            # Add transactions to database
            added_count = 0
            for transaction in transactions:
                if self.db_manager.add_transaction(transaction):
                    added_count += 1
                    # Update status to pending
                    self.db_manager.update_transaction_status(
                        transaction['transaction_id'], 
                        'pending', 
                        'Added to processing queue'
                    )
            
            logging.info(f"Added {added_count}/{len(transactions)} transactions to database")
            
            # Match transactions to rules
            match_results = self.ai_matcher.batch_match_transactions(transactions)
            
            # Process matched transactions
            processed_count = 0
            for match_data in match_results['matched']:
                transaction = match_data['transaction']
                match = match_data['match']
                
                # Update status based on confidence
                if match['confidence'] >= 9:
                    status = 'high_confidence'
                elif match['confidence'] >= 7:
                    status = 'medium_confidence'
                else:
                    status = 'low_confidence'
                
                self.db_manager.update_transaction_status(
                    transaction['transaction_id'],
                    status,
                    f"Matched to '{match['matched_source']}' with confidence {match['confidence']}"
                )
                processed_count += 1
            
            # Mark unmatched transactions
            for transaction in match_results['unmatched']:
                self.db_manager.update_transaction_status(
                    transaction['transaction_id'],
                    'unmatched',
                    'No matching rule found'
                )
            
            # Get statistics
            stats = self.ai_matcher.get_matching_statistics(match_results)
            
            logging.info(f"Batch processing complete:")
            logging.info(f"  Total: {stats['total_transactions']}")
            logging.info(f"  Matched: {stats['matched_count']}")
            logging.info(f"  Unmatched: {stats['unmatched_count']}")
            logging.info(f"  Match rate: {stats['match_rate_percent']}%")
            
            return {
                'batch_size': len(transactions),
                'added_to_db': added_count,
                'match_results': match_results,
                'statistics': stats
            }
            
        except Exception as e:
            logging.error(f"Error processing transaction batch: {e}")
            return {'error': str(e)}
    
    def process_all_transactions(self, max_batch_size: int = None) -> Dict:
        """Process all new transactions in batches."""
        try:
            if max_batch_size:
                self.batch_size = max_batch_size
            
            logging.info(f"Starting full transaction processing (batch size: {self.batch_size})")
            
            # Download and identify new transactions
            new_transactions = self.download_and_process_transactions()
            if not new_transactions:
                logging.info("No new transactions to process")
                return {'status': 'no_new_transactions'}
            
            # Process in batches
            total_processed = 0
            batch_results = []
            
            for i in range(0, len(new_transactions), self.batch_size):
                batch = new_transactions[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(new_transactions) + self.batch_size - 1) // self.batch_size
                
                logging.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} transactions)")
                
                batch_result = self.process_transactions_batch(batch)
                batch_results.append(batch_result)
                total_processed += len(batch)
                
                # Small delay between batches
                time.sleep(1)
            
            # Generate rule suggestions for unmatched transactions
            unmatched_transactions = []
            for batch_result in batch_results:
                if 'match_results' in batch_result:
                    unmatched_transactions.extend(batch_result['match_results']['unmatched'])
            
            if unmatched_transactions:
                suggestions = self.ai_matcher.suggest_new_rules(unmatched_transactions)
                logging.info(f"Generated {len(suggestions)} rule suggestions for unmatched transactions")
            
            # Final statistics
            final_stats = {
                'total_transactions_processed': total_processed,
                'total_batches': len(batch_results),
                'batch_size_used': self.batch_size,
                'rule_suggestions': len(suggestions) if unmatched_transactions else 0
            }
            
            logging.info("✅ Full transaction processing complete")
            logging.info(f"Final stats: {final_stats}")
            
            return {
                'status': 'success',
                'final_stats': final_stats,
                'batch_results': batch_results,
                'rule_suggestions': suggestions if unmatched_transactions else []
            }
            
        except Exception as e:
            logging.error(f"Error in full transaction processing: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_system_status(self) -> Dict:
        """Get current system status."""
        try:
            # Database stats
            db_stats = self.db_manager.get_database_stats()
            
            # Rule stats
            rule_stats = self.rule_loader.get_rule_statistics()
            
            # Get pending transactions
            pending_transactions = self.db_manager.get_pending_transactions()
            
            status = {
                'database': db_stats,
                'rules': rule_stats,
                'pending_transactions': len(pending_transactions),
                'ai_matcher_rules_loaded': len(self.ai_matcher.rules_cache)
            }
            
            return status
            
        except Exception as e:
            logging.error(f"Error getting system status: {e}")
            return {'error': str(e)}
    
    def test_small_batch(self, sample_size: int = 10) -> Dict:
        """Test the system with a small batch of transactions."""
        try:
            logging.info(f"Testing system with {sample_size} transactions...")
            
            # Download transactions
            all_transactions = self.csv_downloader.download_petty_cash_data()
            if not all_transactions:
                return {'status': 'error', 'message': 'Failed to download transactions'}
            
            # Take a small sample
            test_transactions = all_transactions[:sample_size]
            
            # Process the test batch
            result = self.process_transactions_batch(test_transactions)
            
            logging.info("✅ Small batch test complete")
            return {
                'status': 'success',
                'test_size': sample_size,
                'result': result
            }
            
        except Exception as e:
            logging.error(f"Error in small batch test: {e}")
            return {'status': 'error', 'error': str(e)}

def main():
    """Main function to run the petty cash sorter."""
    print("PETTY CASH SORTER V2")
    print("=" * 60)
    
    sorter = PettyCashSorterV2()
    
    # Initialize system
    if not sorter.initialize_system():
        print("❌ Failed to initialize system")
        return
    
    print("✅ System initialized successfully")
    
    # Get system status
    status = sorter.get_system_status()
    print(f"\n📊 System Status:")
    print(f"  Database transactions: {status.get('database', {}).get('transactions_by_status', {})}")
    print(f"  Rules loaded: {status.get('rules', {}).get('total_rules', 0)}")
    print(f"  AI matcher rules: {status.get('ai_matcher_rules_loaded', 0)}")
    print(f"  Pending transactions: {status.get('pending_transactions', 0)}")
    
    # Ask user what to do
    print(f"\nWhat would you like to do?")
    print(f"  1. Test with small batch (10 transactions)")
    print(f"  2. Process all new transactions")
    print(f"  3. Show system status only")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        print(f"\nRunning small batch test...")
        result = sorter.test_small_batch(10)
        if result['status'] == 'success':
            print(f"✅ Test completed successfully")
            stats = result['result']['statistics']
            print(f"  Match rate: {stats['match_rate_percent']}%")
            print(f"  Matched: {stats['matched_count']}")
            print(f"  Unmatched: {stats['unmatched_count']}")
        else:
            print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
    
    elif choice == "2":
        print(f"\nProcessing all new transactions...")
        result = sorter.process_all_transactions()
        if result['status'] == 'success':
            print(f"✅ Processing completed successfully")
            final_stats = result['final_stats']
            print(f"  Total processed: {final_stats['total_transactions_processed']}")
            print(f"  Batches: {final_stats['total_batches']}")
            print(f"  Rule suggestions: {final_stats['rule_suggestions']}")
        else:
            print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
    
    elif choice == "3":
        print(f"\nSystem status displayed above")
    
    else:
        print(f"Invalid choice")

if __name__ == "__main__":
    main() 