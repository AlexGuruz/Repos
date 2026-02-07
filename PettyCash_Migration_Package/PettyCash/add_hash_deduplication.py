#!/usr/bin/env python3
"""Add hash deduplication to the current petty cash sorter"""

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
        hash_string = f"{date}_{source}_{company}_{amount}_{row_number}"
        return hashlib.md5(hash_string.encode()).hexdigest()
    
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

def add_hash_deduplication_to_csv_downloader():
    """Add hash deduplication to the CSV downloader."""
    
    print("🔧 ADDING HASH DEDUPLICATION TO CSV DOWNLOADER")
    print("=" * 60)
    
    # Read the current CSV downloader
    with open("csv_downloader_fixed.py", "r") as f:
        content = f.read()
    
    # Add hash deduplication import
    if "from hash_deduplication import HashDeduplication" not in content:
        # Find the import section
        import_section_end = content.find("class CSVDownloader:")
        
        # Add the import
        new_import = "from hash_deduplication import HashDeduplication\n"
        content = content[:import_section_end] + new_import + content[import_section_end:]
    
    # Add hash deduplication to the class
    if "self.hash_dedup = HashDeduplication()" not in content:
        # Find the __init__ method
        init_start = content.find("def __init__(self):")
        init_end = content.find("def download_petty_cash_data", init_start)
        
        # Add hash deduplication initialization
        hash_init = "        # Hash deduplication\n        self.hash_dedup = HashDeduplication()\n"
        content = content[:init_end] + hash_init + content[init_end:]
    
    # Add hash filtering to the download method
    if "filter_new_transactions" not in content:
        # Find where transactions are processed
        process_section = content.find("        # Process transactions")
        if process_section != -1:
            # Add hash filtering
            hash_filter = """
        # Filter out already processed transactions
        transactions = self.hash_dedup.filter_new_transactions(transactions)
        if not transactions:
            logging.info("No new transactions to process")
            return []
"""
            content = content[:process_section] + hash_filter + content[process_section:]
    
    # Add hash marking after successful processing
    if "mark_transactions_processed" not in content:
        # Find the end of the download method
        method_end = content.find("        return transactions", content.find("def download_petty_cash_data"))
        if method_end != -1:
            # Add hash marking
            hash_marking = """
        # Mark transactions as processed
        self.hash_dedup.mark_transactions_processed(transactions)
"""
            content = content[:method_end] + hash_marking + content[method_end:]
    
    # Save the updated file
    with open("csv_downloader_fixed.py", "w") as f:
        f.write(content)
    
    print("✅ Hash deduplication added to CSV downloader")
    print("  • Added HashDeduplication import")
    print("  • Added hash deduplication initialization")
    print("  • Added transaction filtering")
    print("  • Added hash marking after processing")
    
    return True

if __name__ == "__main__":
    # First create the hash deduplication module
    hash_content = '''#!/usr/bin/env python3
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
                    f.write(f"{hash_id}\\n")
            logging.info(f"Saved {len(self.processed_hashes)} processed hashes")
        except Exception as e:
            logging.error(f"Error saving processed hashes: {e}")
    
    def generate_hash(self, date: str, source: str, company: str, amount: float, row_number: int) -> str:
        """Generate unique hash for transaction tracking."""
        hash_string = f"{date}_{source}_{company}_{amount}_{row_number}"
        return hashlib.md5(hash_string.encode()).hexdigest()
    
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
'''
    
    with open("hash_deduplication.py", "w") as f:
        f.write(hash_content)
    
    print("✅ Created hash_deduplication.py module")
    
    # Now add it to the CSV downloader
    add_hash_deduplication_to_csv_downloader()
    
    print("\n🎯 HASH DEDUPLICATION SYSTEM READY!")
    print("  • Created hash_deduplication.py module")
    print("  • Updated csv_downloader_fixed.py")
    print("  • Next run will prevent duplicate processing") 