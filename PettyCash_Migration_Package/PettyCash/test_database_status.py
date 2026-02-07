#!/usr/bin/env python3
"""
Test Database Status
Check what transactions are in the database and what's available to process
"""

from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader

def main():
    """Test database status."""
    print("TESTING DATABASE STATUS")
    print("=" * 30)
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Check database stats
        stats = db_manager.get_database_stats()
        print(f"Database stats: {stats}")
        
        # Check all transactions in database
        all_db_transactions = db_manager.get_all_transactions()
        print(f"Total transactions in database: {len(all_db_transactions)}")
        
        # Check pending transactions
        pending = db_manager.get_pending_transactions()
        print(f"Pending transactions: {len(pending)}")
        
        # Download fresh transactions
        downloader = CSVDownloader()
        fresh_transactions = downloader.download_petty_cash_data()
        print(f"Fresh transactions from Google Sheets: {len(fresh_transactions) if fresh_transactions else 0}")
        
        if fresh_transactions:
            print("Sample fresh transactions:")
            for i, transaction in enumerate(fresh_transactions[:3]):
                row_num = transaction.get('row_number', 'N/A')
                source = transaction.get('source', 'N/A')
                amount = transaction.get('amount', 'N/A')
                print(f"  {i+1}. Row {row_num}: {source} - ${amount}")
        
        # Check which transactions are new (not in database)
        if fresh_transactions:
            new_transactions = []
            for transaction in fresh_transactions:
                existing = db_manager.get_transaction_by_row(transaction['row_number'])
                if not existing:
                    new_transactions.append(transaction)
            
            print(f"New transactions (not in database): {len(new_transactions)}")
            
            if new_transactions:
                print("Sample new transactions:")
                for i, transaction in enumerate(new_transactions[:3]):
                    row_num = transaction.get('row_number', 'N/A')
                    source = transaction.get('source', 'N/A')
                    amount = transaction.get('amount', 'N/A')
                    print(f"  {i+1}. Row {row_num}: {source} - ${amount}")
            else:
                print("All transactions are already in the database!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 