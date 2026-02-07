#!/usr/bin/env python3
"""Hash deduplication system for transactions."""

import hashlib
import logging
from pathlib import Path
from typing import Set

class HashDeduplication:
    """Hash-based deduplication system for transactions."""
    
    def __init__(self, hash_file_path: str = "data/processed_hashes.txt"):
        self.hash_file_path = Path(hash_file_path)
        self.processed_hashes: Set[str] = set()
        self.load_processed_hashes()
    
    def load_processed_hashes(self) -> None:
        """Load previously processed hash IDs from file."""
        try:
            if self.hash_file_path.exists():
                with open(self.hash_file_path, 'r') as f:
                    self.processed_hashes = set(line.strip() for line in f)
                logging.info(f"Loaded {len(self.processed_hashes)} previously processed hashes")
            else:
                logging.info("No existing processed hashes file found - starting fresh")
        except Exception as e:
            logging.error(f"Error loading processed hashes: {e}")
            self.processed_hashes = set()
    
    def save_processed_hashes(self) -> None:
        """Save processed hash IDs to file."""
        try:
            self.hash_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.hash_file_path, 'w') as f:
                for hash_id in self.processed_hashes:
                    f.write(f"{hash_id}\n")
            logging.info(f"Saved {len(self.processed_hashes)} processed hashes")
        except Exception as e:
            logging.error(f"Error saving processed hashes: {e}")
    
    def generate_hash(self, date: str, source: str, company: str, amount: float, row_number: int) -> str:
        """Generate unique hash for transaction tracking."""
        # Match the CSV downloader's transaction_id format exactly
        hash_string = f"{row_number}_{date}_{source}_{amount}_{company}"
        return hashlib.md5(hash_string.encode()).hexdigest()[:12]  # Use first 12 characters like CSV downloader
    
    def is_processed(self, hash_id: str) -> bool:
        """Check if a transaction hash has been processed before."""
        return hash_id in self.processed_hashes
    
    def mark_processed(self, hash_id: str) -> None:
        """Mark a transaction hash as processed."""
        self.processed_hashes.add(hash_id)
    
    def filter_new_transactions(self, transactions: list) -> list:
        """Filter out transactions that have been processed before."""
        new_transactions = []
        duplicates_found = 0
        
        for transaction in transactions:
            # Generate hash for this transaction
            hash_id = self.generate_hash(
                transaction['date'],
                transaction['source'],
                transaction['company'],
                transaction['amount'],
                transaction['row_number']
            )
            
            if not self.is_processed(hash_id):
                # Add hash_id to transaction for tracking
                transaction['hash_id'] = hash_id
                new_transactions.append(transaction)
            else:
                duplicates_found += 1
        
        logging.info(f"Filtered transactions: {len(new_transactions)} new, {duplicates_found} duplicates")
        return new_transactions
    
    def mark_transactions_processed(self, transactions: list) -> None:
        """Mark a list of transactions as processed."""
        for transaction in transactions:
            if 'hash_id' in transaction:
                self.mark_processed(transaction['hash_id'])
        
        # Save updated hashes
        self.save_processed_hashes()
