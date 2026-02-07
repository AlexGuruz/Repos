#!/usr/bin/env python3
"""
Database Manager for Petty Cash Sorter
Handles SQLite database creation, migrations, and management
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class DatabaseManager:
    def __init__(self, db_path: str = "config/petty_cash.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        logging.info("INITIALIZING DATABASE MANAGER")
        logging.info("=" * 50)
    
    def create_database(self) -> bool:
        """Create the SQLite database with all required tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            logging.info("Creating database tables...")
            
            # Create transactions table with unique constraint on transaction_id
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    row_number INTEGER,
                    date TEXT,
                    initials TEXT,
                    source TEXT,
                    company TEXT,
                    amount REAL,
                    status TEXT DEFAULT 'pending',
                    confidence REAL,
                    matched_rule TEXT,
                    target_sheet TEXT,
                    target_header TEXT,
                    target_cell_row INTEGER,
                    target_cell_col INTEGER,
                    target_cell_address TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            ''')
            
            # Rules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target_sheet TEXT NOT NULL,
                    target_header TEXT NOT NULL,
                    confidence_threshold REAL DEFAULT 0.7,
                    company TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # AI Learning table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_learning (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_pattern TEXT NOT NULL,
                    successful_matches INTEGER DEFAULT 0,
                    failed_matches INTEGER DEFAULT 0,
                    confidence_adjustments REAL DEFAULT 0.0,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Audit Log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT,
                    status_from TEXT,
                    status_to TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for efficient querying
            logging.info("Creating database indexes...")
            
            # Transactions indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_row_number ON transactions(row_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source)')
            
            # Rules indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rules_source ON rules(source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rules_target_sheet ON rules(target_sheet)')
            
            # AI Learning indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_learning_pattern ON ai_learning(source_pattern)')
            
            # Audit Log indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_transaction_id ON audit_log(transaction_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)')
            
            conn.commit()
            conn.close()
            
            logging.info(f"Database created successfully at {self.db_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating database: {e}")
            return False
    
    def add_transaction(self, transaction_data: Dict) -> bool:
        """Add a new transaction to the database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # Check if transaction already exists
            cursor.execute('SELECT transaction_id FROM transactions WHERE transaction_id = ?', 
                         (transaction_data['transaction_id'],))
            
            if cursor.fetchone():
                logging.debug(f"Transaction already exists, skipping: {transaction_data['transaction_id']}")
                conn.close()
                return True  # Return True since this is expected behavior with hash deduplication
            
            cursor.execute('''
                INSERT INTO transactions (
                    transaction_id, row_number, date, initials, source, company, 
                    amount, status, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            ''', (
                transaction_data['transaction_id'],
                transaction_data.get('row_number'),
                transaction_data.get('date'),
                transaction_data.get('initials', ''),
                transaction_data.get('source'),
                transaction_data.get('company'),
                transaction_data.get('amount')
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            logging.debug(f"Transaction already exists (IntegrityError), skipping: {transaction_data['transaction_id']}")
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error adding transaction to database: {e}")
            return False
    
    def get_transaction_by_row(self, row_number: int) -> Optional[Dict]:
        """Get transaction by row number."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM transactions WHERE row_number = ?
            ''', (row_number,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting transaction by row: {e}")
            return None
    
    def update_transaction_status(self, transaction_id: str, new_status: str, message: str = "") -> bool:
        """Update transaction status and log to audit trail."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current status
            cursor.execute('SELECT status FROM transactions WHERE transaction_id = ?', (transaction_id,))
            result = cursor.fetchone()
            
            if not result:
                logging.warning(f"Transaction not found: {transaction_id}")
                return False
            
            old_status = result[0]
            
            # Update transaction status
            cursor.execute('''
                UPDATE transactions 
                SET status = ?, updated_date = CURRENT_TIMESTAMP 
                WHERE transaction_id = ?
            ''', (new_status, transaction_id))
            
            # Add to audit log
            cursor.execute('''
                INSERT INTO audit_log (transaction_id, status_from, status_to, message)
                VALUES (?, ?, ?, ?)
            ''', (transaction_id, old_status, new_status, message))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Updated transaction {transaction_id}: {old_status} → {new_status}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating transaction status: {e}")
            return False
    
    def update_transaction_with_match(self, transaction_id: str, new_status: str, matched_source: str, 
                                    target_sheet: str, target_header: str, message: str = "", 
                                    target_cell_row: int = None, target_cell_col: int = None, 
                                    target_cell_address: str = None) -> bool:
        """Update transaction with match information and add audit log entry."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current status and rule ID
            cursor.execute('SELECT status FROM transactions WHERE transaction_id = ?', (transaction_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return False
            
            old_status = result[0]
            
            # Get rule ID for the matched source
            cursor.execute('SELECT id FROM rules WHERE source = ?', (matched_source,))
            rule_result = cursor.fetchone()
            matched_rule_id = rule_result[0] if rule_result else None
            
            # Update transaction with match information including coordinates
            cursor.execute('''
                UPDATE transactions 
                SET status = ?, matched_rule_id = ?, target_sheet = ?, target_header = ?, 
                    target_cell_row = ?, target_cell_col = ?, target_cell_address = ?,
                    notes = ?, updated_date = CURRENT_TIMESTAMP 
                WHERE transaction_id = ?
            ''', (new_status, matched_rule_id, target_sheet, target_header, 
                  target_cell_row, target_cell_col, target_cell_address, message, transaction_id))
            
            # Add audit log entry with coordinate information
            coordinate_info = ""
            if target_cell_row and target_cell_col:
                coordinate_info = f" → Cell({target_cell_row},{target_cell_col})"
            if target_cell_address:
                coordinate_info = f" → {target_cell_address}"
            
            audit_message = f"{message}{coordinate_info}"
            
            cursor.execute('''
                INSERT INTO audit_log (transaction_id, status_from, status_to, message)
                VALUES (?, ?, ?, ?)
            ''', (transaction_id, old_status, new_status, audit_message))
            
            conn.commit()
            conn.close()
            
            # Log with coordinate information
            coord_log = ""
            if target_cell_row and target_cell_col:
                coord_log = f" → Cell({target_cell_row},{target_cell_col})"
            if target_cell_address:
                coord_log = f" → {target_cell_address}"
            
            logging.info(f"Updated transaction {transaction_id} with match: {matched_source} → {target_sheet}/{target_header}{coord_log}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating transaction with match: {e}")
            return False
    
    def add_rule(self, rule_data: Dict) -> bool:
        """Add a new rule to the database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            cursor = conn.cursor()
            
            # Extract company from source if not provided
            company = rule_data.get('company', '')
            if not company:
                source_upper = rule_data['source'].upper()
                if 'NUGZ' in source_upper:
                    company = 'NUGZ'
                elif 'JGD' in source_upper:
                    company = 'JGD'
                elif 'PUFFIN' in source_upper:
                    company = 'PUFFIN'
                else:
                    company = 'UNKNOWN'
            
            cursor.execute('''
                INSERT INTO rules (source, target_sheet, target_header, confidence_threshold, company)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                rule_data['source'],
                rule_data['target_sheet'],
                rule_data['target_header'],
                rule_data.get('confidence_threshold', 0.7),
                company
            ))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Added rule: {rule_data['source']} → {rule_data['target_sheet']}/{rule_data['target_header']}")
            return True
            
        except Exception as e:
            logging.error(f"Error adding rule: {e}")
            return False
    
    def get_all_rules(self) -> List[Dict]:
        """Get all rules from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM rules')
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting rules: {e}")
            return []
    
    def delete_rule(self, rule_id: int) -> bool:
        """Delete a rule by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            if deleted:
                logging.info(f"Deleted rule with ID: {rule_id}")
            else:
                logging.warning(f"Rule with ID {rule_id} not found")
            
            return deleted
            
        except Exception as e:
            logging.error(f"Error deleting rule: {e}")
            return False
    
    def delete_rule_by_source(self, source: str) -> bool:
        """Delete a rule by source text."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM rules WHERE source = ?', (source,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            if deleted:
                logging.info(f"Deleted rule with source: {source}")
            else:
                logging.warning(f"Rule with source '{source}' not found")
            
            return deleted
            
        except Exception as e:
            logging.error(f"Error deleting rule by source: {e}")
            return False
    
    def get_pending_transactions(self) -> List[Dict]:
        """Get all pending transactions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM transactions WHERE status = "pending"')
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting pending transactions: {e}")
            return []
    
    def get_processed_transactions_by_company(self, company: str) -> List[Dict]:
        """Get processed transactions for a specific company for AI learning."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE company = ? AND status IN ('high_confidence', 'medium_confidence', 'low_confidence')
                ORDER BY date DESC
                LIMIT 100
            """, (company,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                columns = [description[0] for description in cursor.description]
                transactions = [dict(zip(columns, row)) for row in rows]
                logging.info(f"Retrieved {len(transactions)} processed transactions for {company}")
                return transactions
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting processed transactions for {company}: {e}")
            return []
    
    def get_transaction_with_rule_info(self, transaction_id: str) -> Optional[Dict]:
        """Get transaction with its associated rule information."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.*, r.target_sheet, r.target_header
                FROM transactions t
                LEFT JOIN rules r ON t.matched_rule_id = r.id
                WHERE t.transaction_id = ?
            """, (transaction_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting transaction with rule info: {e}")
            return None
    
    def get_audit_log(self, transaction_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get audit log entries."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if transaction_id:
                cursor.execute('''
                    SELECT * FROM audit_log 
                    WHERE transaction_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (transaction_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM audit_log 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting audit log: {e}")
            return []
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Transaction counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM transactions 
                GROUP BY status
            ''')
            status_counts = cursor.fetchall()
            stats['transactions_by_status'] = dict(status_counts)
            
            # Total rules
            cursor.execute('SELECT COUNT(*) FROM rules')
            stats['total_rules'] = cursor.fetchone()[0]
            
            # Total audit log entries
            cursor.execute('SELECT COUNT(*) FROM audit_log')
            stats['total_audit_entries'] = cursor.fetchone()[0]
            
            conn.close()
            return stats
            
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")
            return {}

    def update_rule(self, rule_id: str, rule_data: Dict) -> bool:
        """Update an existing rule in the database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            cursor = conn.cursor()
            
            # Extract company from source if not provided
            company = rule_data.get('company', '')
            if not company:
                source_upper = rule_data['source'].upper()
                if 'NUGZ' in source_upper:
                    company = 'NUGZ'
                elif 'JGD' in source_upper:
                    company = 'JGD'
                elif 'PUFFIN' in source_upper:
                    company = 'PUFFIN'
                else:
                    company = 'UNKNOWN'
            
            cursor.execute('''
                UPDATE rules 
                SET source = ?, target_sheet = ?, target_header = ?, confidence_threshold = ?, company = ?
                WHERE source = ?
            ''', (
                rule_data['source'],
                rule_data['target_sheet'],
                rule_data['target_header'],
                rule_data.get('confidence_threshold', 0.7),
                company,
                rule_id.split('|')[0] if '|' in rule_id else rule_id
            ))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                logging.info(f"Updated rule: {rule_id}")
                return True
            else:
                conn.close()
                logging.warning(f"Rule not found for update: {rule_id}")
                return False
                
        except Exception as e:
            logging.error(f"Error updating rule: {e}")
            return False
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule from the database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            cursor = conn.cursor()
            
            # Extract source from rule_id (format: "source|company")
            source = rule_id.split('|')[0] if '|' in rule_id else rule_id
            
            cursor.execute('DELETE FROM rules WHERE source = ?', (source,))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                logging.info(f"Deleted rule: {rule_id}")
                return True
            else:
                conn.close()
                logging.warning(f"Rule not found for deletion: {rule_id}")
                return False
                
        except Exception as e:
            logging.error(f"Error deleting rule: {e}")
            return False

def main():
    """Test database creation and basic operations."""
    print("DATABASE MANAGER TEST")
    print("=" * 50)
    
    db_manager = DatabaseManager()
    
    # Create database
    if db_manager.create_database():
        print("✅ Database created successfully")
        
        # Test adding a rule
        test_rule = {
            'source': 'TEST SOURCE',
            'target_sheet': 'TEST SHEET',
            'target_header': 'TEST HEADER',
            'confidence_threshold': 0.8
        }
        
        if db_manager.add_rule(test_rule):
            print("✅ Test rule added successfully")
        
        # Get database stats
        stats = db_manager.get_database_stats()
        print(f"📊 Database stats: {stats}")
        
    else:
        print("❌ Failed to create database")

if __name__ == "__main__":
    main() 