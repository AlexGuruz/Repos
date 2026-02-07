#!/usr/bin/env python3
"""
Processed Transaction Manager
Handles filing of processed transactions to database and CSV files
"""

import sqlite3
import csv
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import time

class ProcessedTransactionManager:
    """Manages filing of processed transactions with hybrid database/CSV approach."""
    
    def __init__(self, base_path: str = "data/processed_transactions"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Database path
        self.db_path = self.base_path / "filing_system.db"
        
        # CSV directory
        self.csv_dir = self.base_path / "csv_files"
        self.csv_dir.mkdir(exist_ok=True)
        
        # Batch writing
        self.batch_size = 50
        self.pending_transactions = []
        self.batch_lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        logging.info("INITIALIZING PROCESSED TRANSACTION MANAGER")
        logging.info("=" * 60)
    
    def _init_database(self):
        """Initialize the filing database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Processed transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    row_number INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    initials TEXT,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    matched_source TEXT,
                    target_sheet TEXT,
                    target_header TEXT,
                    confidence REAL,
                    processing_notes TEXT,
                    csv_file_path TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # CSV file tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS csv_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    company TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    transaction_count INTEGER DEFAULT 0,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transaction_id ON processed_transactions(transaction_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_company_date ON processed_transactions(company, date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON processed_transactions(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_csv_file ON csv_files(file_path)')
            
            conn.commit()
            conn.close()
            
            logging.info(f"✅ Filing database initialized: {self.db_path}")
            
        except Exception as e:
            logging.error(f"❌ Error initializing filing database: {e}")
            raise
    
    def file_transaction(self, transaction: Dict, match_data: Optional[Dict] = None, 
                        status: str = "processed", notes: str = "") -> bool:
        """File a single transaction with optional match data."""
        try:
            # Prepare transaction data
            filing_data = {
                'transaction_id': transaction['transaction_id'],
                'row_number': transaction['row_number'],
                'date': transaction['date'],
                'initials': transaction.get('initials', ''),
                'source': transaction['source'],
                'company': transaction['company'],
                'amount': transaction['amount'],
                'status': status,
                'matched_source': match_data.get('matched_source', '') if match_data else '',
                'target_sheet': match_data.get('target_sheet', '') if match_data else '',
                'target_header': match_data.get('target_header', '') if match_data else '',
                'confidence': match_data.get('confidence', 0.0) if match_data else 0.0,
                'processing_notes': notes
            }
            
            # Add to batch
            with self.batch_lock:
                self.pending_transactions.append(filing_data)
                
                # Flush batch if full
                if len(self.pending_transactions) >= self.batch_size:
                    self._flush_batch()
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Error filing transaction {transaction.get('transaction_id', 'unknown')}: {e}")
            return False
    
    def file_failed_transaction(self, transaction: Dict, error_message: str) -> bool:
        """File a transaction that failed processing."""
        return self.file_transaction(
            transaction, 
            status="failed", 
            notes=f"Processing failed: {error_message}"
        )
    
    def file_unmatched_transaction(self, transaction: Dict) -> bool:
        """File a transaction that couldn't be matched to any rule."""
        return self.file_transaction(
            transaction, 
            status="unmatched", 
            notes="No matching rule found"
        )
    
    def _flush_batch(self):
        """Flush pending transactions to database and CSV files."""
        if not self.pending_transactions:
            return
        
        try:
            # Group by company and date for CSV organization
            company_groups = {}
            
            for transaction in self.pending_transactions:
                company = transaction['company']
                # Handle different date formats
                date_str = transaction['date']
                try:
                    # Try YYYY-MM-DD format first
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    try:
                        # Try MM/DD/YY format
                        date_obj = datetime.strptime(date_str, '%m/%d/%y')
                    except ValueError:
                        try:
                            # Try MM/DD/YYYY format
                            date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                        except ValueError:
                            logging.error(f"Unsupported date format: {date_str}")
                            continue
                
                year_month = f"{date_obj.year}_{date_obj.month:02d}"
                
                if company not in company_groups:
                    company_groups[company] = {}
                
                if year_month not in company_groups[company]:
                    company_groups[company][year_month] = []
                
                company_groups[company][year_month].append(transaction)
            
            # Write to database
            self._write_to_database(self.pending_transactions)
            
            # Write to CSV files
            for company, year_months in company_groups.items():
                for year_month, transactions in year_months.items():
                    self._write_to_csv(company, year_month, transactions)
            
            # Clear pending transactions
            self.pending_transactions = []
            
            logging.info(f"✅ Flushed batch of {len(self.pending_transactions)} transactions")
            
        except Exception as e:
            logging.error(f"❌ Error flushing batch: {e}")
            # Keep transactions in pending for retry
            return False
    
    def _write_to_database(self, transactions: List[Dict]):
        """Write transactions to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for transaction in transactions:
                cursor.execute('''
                    INSERT OR REPLACE INTO processed_transactions 
                    (transaction_id, row_number, date, initials, source, company, amount,
                     status, matched_source, target_sheet, target_header, confidence, processing_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction['transaction_id'],
                    transaction['row_number'],
                    transaction['date'],
                    transaction['initials'],
                    transaction['source'],
                    transaction['company'],
                    transaction['amount'],
                    transaction['status'],
                    transaction['matched_source'],
                    transaction['target_sheet'],
                    transaction['target_header'],
                    transaction['confidence'],
                    transaction['processing_notes']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"❌ Error writing to database: {e}")
            raise
    
    def _write_to_csv(self, company: str, year_month: str, transactions: List[Dict]):
        """Write transactions to CSV file."""
        try:
            # Create company directory
            company_dir = self.csv_dir / company
            company_dir.mkdir(exist_ok=True)
            
            # CSV file path
            csv_file = company_dir / f"{year_month}_transactions.csv"
            
            # Check if file exists to determine if we need headers
            file_exists = csv_file.exists()
            
            # Write to CSV
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers if new file
                if not file_exists:
                    headers = [
                        'transaction_id', 'row_number', 'date', 'initials', 'source', 
                        'company', 'amount', 'status', 'matched_source', 'target_sheet', 
                        'target_header', 'confidence', 'processing_notes', 'filed_date'
                    ]
                    writer.writerow(headers)
                
                # Write transactions
                for transaction in transactions:
                    row = [
                        transaction['transaction_id'],
                        transaction['row_number'],
                        transaction['date'],
                        transaction['initials'],
                        transaction['source'],
                        transaction['company'],
                        transaction['amount'],
                        transaction['status'],
                        transaction['matched_source'],
                        transaction['target_sheet'],
                        transaction['target_header'],
                        transaction['confidence'],
                        transaction['processing_notes'],
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ]
                    writer.writerow(row)
            
            # Update CSV file tracking in database
            self._update_csv_tracking(csv_file, company, year_month, len(transactions))
            
        except Exception as e:
            logging.error(f"❌ Error writing to CSV {csv_file}: {e}")
            raise
    
    def _update_csv_tracking(self, csv_file: Path, company: str, year_month: str, transaction_count: int):
        """Update CSV file tracking in database."""
        try:
            year, month = year_month.split('_')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO csv_files 
                (file_path, company, year, month, transaction_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(csv_file),
                company,
                int(year),
                int(month),
                transaction_count,
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"❌ Error updating CSV tracking: {e}")
    
    def flush_all_pending(self):
        """Flush all pending transactions."""
        with self.batch_lock:
            if self.pending_transactions:
                self._flush_batch()
    
    def get_filing_statistics(self) -> Dict:
        """Get filing system statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Total transactions by status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM processed_transactions 
                GROUP BY status
            ''')
            status_counts = cursor.fetchall()
            stats['transactions_by_status'] = dict(status_counts)
            
            # Total transactions
            cursor.execute('SELECT COUNT(*) FROM processed_transactions')
            stats['total_transactions'] = cursor.fetchone()[0]
            
            # Transactions by company
            cursor.execute('''
                SELECT company, COUNT(*) as count 
                FROM processed_transactions 
                GROUP BY company
            ''')
            company_counts = cursor.fetchall()
            stats['transactions_by_company'] = dict(company_counts)
            
            # CSV files
            cursor.execute('SELECT COUNT(*) FROM csv_files')
            stats['total_csv_files'] = cursor.fetchone()[0]
            
            # Pending transactions
            with self.batch_lock:
                stats['pending_transactions'] = len(self.pending_transactions)
            
            conn.close()
            return stats
            
        except Exception as e:
            logging.error(f"❌ Error getting filing statistics: {e}")
            return {}
    
    def cleanup_old_csv_files(self, max_age_days: int = 365):
        """Clean up CSV files older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get old CSV files
            cursor.execute('''
                SELECT file_path FROM csv_files 
                WHERE last_updated < ?
            ''', (cutoff_date,))
            
            old_files = cursor.fetchall()
            
            for (file_path,) in old_files:
                try:
                    # Delete file
                    Path(file_path).unlink(missing_ok=True)
                    
                    # Remove from database
                    cursor.execute('DELETE FROM csv_files WHERE file_path = ?', (file_path,))
                    
                    logging.info(f"🗑️ Cleaned up old CSV file: {file_path}")
                    
                except Exception as e:
                    logging.warning(f"⚠️ Could not clean up {file_path}: {e}")
            
            conn.commit()
            conn.close()
            
            logging.info(f"✅ Cleaned up {len(old_files)} old CSV files")
            
        except Exception as e:
            logging.error(f"❌ Error cleaning up old CSV files: {e}")
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM processed_transactions 
                WHERE transaction_id = ?
            ''', (transaction_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Error getting transaction {transaction_id}: {e}")
            return None
    
    def search_transactions(self, company: str = None, status: str = None, 
                          date_from: str = None, date_to: str = None) -> List[Dict]:
        """Search transactions with filters."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM processed_transactions WHERE 1=1"
            params = []
            
            if company:
                query += " AND company = ?"
                params.append(company)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if date_from:
                query += " AND date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= ?"
                params.append(date_to)
            
            query += " ORDER BY date DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
            return []
            
        except Exception as e:
            logging.error(f"❌ Error searching transactions: {e}")
            return []

def main():
    """Test the ProcessedTransactionManager."""
    print("PROCESSED TRANSACTION MANAGER TEST")
    print("=" * 50)
    
    manager = ProcessedTransactionManager()
    
    # Test transaction
    test_transaction = {
        'transaction_id': 'TEST_001',
        'row_number': 1,
        'date': '2025-01-15',
        'initials': 'JD',
        'source': 'Test Source',
        'company': 'JGD',
        'amount': 100.50
    }
    
    test_match = {
        'matched_source': 'Test Source',
        'target_sheet': 'JGD_data',
        'target_header': 'Test Header',
        'confidence': 8.5
    }
    
    # File transaction
    if manager.file_transaction(test_transaction, test_match):
        print("✅ Transaction filed successfully")
    
    # Flush pending
    manager.flush_all_pending()
    
    # Get statistics
    stats = manager.get_filing_statistics()
    print(f"📊 Filing statistics: {stats}")
    
    # Search transactions
    results = manager.search_transactions(company='JGD')
    print(f"🔍 Found {len(results)} transactions for JGD")

if __name__ == "__main__":
    main() 