#!/usr/bin/env python3
"""
CSV Downloader for Petty Cash Sorter
Downloads PETTY CASH sheet data with calculated values
"""

import gspread
import pandas as pd
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional

class CSVDownloader:
    def __init__(self):
        # Google Sheets setup
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_file('config/service_account.json', scopes=self.scope)
        self.gc = gspread.authorize(self.creds)
        
        # Sheet configuration
        self.spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        self.worksheet_name = "PETTY CASH"
        
        # Column mapping (0-based index)
        self.columns = {
            'initials': 0,    # Column A
            'date': 1,        # Column B
            'company': 2,     # Column C
            'source': 3,      # Column D
            'amount': 18      # Column S
        }
        
        # Create directories
        Path("data/downloaded_csv").mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/csv_downloader.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING CSV DOWNLOADER")
        logging.info("=" * 50)
    
    def download_petty_cash_data(self) -> Optional[List[Dict]]:
        """Download PETTY CASH sheet data with calculated values."""
        try:
            logging.info(f"Downloading data from {self.worksheet_name} worksheet...")
            
            # Open the spreadsheet
            spreadsheet = self.gc.open_by_url(self.spreadsheet_url)
            worksheet = spreadsheet.worksheet(self.worksheet_name)
            
            # Get all data with calculated values (not formulas)
            all_data = worksheet.get_all_values(value_render_option='FORMATTED_VALUE')
            
            logging.info(f"Downloaded {len(all_data)} rows from {self.worksheet_name}")
            
            # Process the data starting from row 5 (index 4)
            transactions = []
            zero_amount_transactions = []
            start_row = 4  # Skip header rows, start from row 5
            
            for i, row_data in enumerate(all_data[start_row:], start=start_row + 1):
                row_number = i + 1  # 1-based row number
                
                # Extract data from specified columns
                try:
                    initials = row_data[self.columns['initials']] if len(row_data) > self.columns['initials'] else ''
                    date_val = row_data[self.columns['date']] if len(row_data) > self.columns['date'] else ''
                    company = row_data[self.columns['company']] if len(row_data) > self.columns['company'] else ''
                    source = row_data[self.columns['source']] if len(row_data) > self.columns['source'] else ''
                    amount_val = row_data[self.columns['amount']] if len(row_data) > self.columns['amount'] else ''
                    
                    # Skip empty rows
                    if not all([initials, date_val, company, source, amount_val]):
                        logging.debug(f"Skipping row {row_number}: missing data")
                        continue
                    
                    # Parse and validate data
                    parsed_date = self._parse_date(date_val)
                    parsed_amount = self._parse_amount(amount_val)
                    
                    if not parsed_date or parsed_amount is None:
                        logging.warning(f"Skipping row {row_number}: invalid date or amount")
                        continue
                    
                    # Create transaction ID
                    transaction_id = self._create_transaction_id(row_number, date_val, source, amount_val, company)
                    
                    # Create transaction record
                    transaction = {
                        'transaction_id': transaction_id,
                        'row_number': row_number,
                        'date': parsed_date,
                        'initials': initials.strip(),
                        'source': source.strip(),
                        'company': company.strip(),
                        'amount': parsed_amount,
                        'raw_data': {
                            'date': date_val,
                            'amount': amount_val
                        }
                    }
                    
                    # Check if zero amount and separate
                    if self._is_zero_amount(amount_val):
                        zero_amount_transactions.append(transaction)
                        logging.debug(f"Added zero amount transaction row {row_number}: {source}")
                    else:
                        transactions.append(transaction)
                        logging.debug(f"Processed row {row_number}: {source} - {parsed_amount}")
                    
                except Exception as e:
                    logging.error(f"Error processing row {row_number}: {e}")
                    continue
            
            logging.info(f"Successfully processed {len(transactions)} transactions")
            logging.info(f"Found {len(zero_amount_transactions)} zero-amount transactions")
            
            # Save regular transactions to CSV file
            self._save_to_csv(transactions)
            
            # Save zero-amount transactions to separate folder
            if zero_amount_transactions:
                self._save_zero_amount_transactions(zero_amount_transactions)
            
            return transactions
                    
                    # Parse and validate data
                    parsed_date = self._parse_date(date_val)
                    parsed_amount = self._parse_amount(amount_val)
                    
                    if not parsed_date or parsed_amount is None:
                        logging.warning(f"Skipping row {row_number}: invalid date or amount")
                        continue
                    
                    # Create transaction ID
                    transaction_id = self._create_transaction_id(row_number, date_val, source, amount_val, company)
                    
                    # Create transaction record
                    transaction = {
                        'transaction_id': transaction_id,
                        'row_number': row_number,
                        'date': parsed_date,
                        'initials': initials.strip(),
                        'source': source.strip(),
                        'company': company.strip(),
                        'amount': parsed_amount,
                        'raw_data': {
                            'date': date_val,
                            'amount': amount_val
                        }
                    }
                    
                    transactions.append(transaction)
                    logging.debug(f"Processed row {row_number}: {source} - {parsed_amount}")
                    
                except Exception as e:
                    logging.error(f"Error processing row {row_number}: {e}")
                    continue
            
            logging.info(f"Successfully processed {len(transactions)} transactions")
            
            # Save to CSV file
            self._save_to_csv(transactions)
            
            return transactions
            
        except Exception as e:
            logging.error(f"Error downloading PETTY CASH data: {e}")
            return None
    
    def _is_zero_amount(self, amount_str: str) -> bool:
        """Check if amount is zero or empty."""
        if not amount_str:
            return True
        
        amount_str = str(amount_str).strip()
        zero_patterns = [
            '$ -', '$ - ', '-', '0', '$0', '$ 0',
            '$0.00', '$ 0.00', '($0.00)', '($ 0.00)',
            '-$0.00', '-$ 0.00', '0.00', '0.0',
            '($0)', '($ 0)', '-$0', '-$ 0',
            '$0.0', '$ 0.0', '($0.0)', '($ 0.0)',
            '-$0.0', '-$ 0.0', '0', '0.0', '0.00'
        ]
        
        return amount_str in zero_patterns
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to consistent format."""
        try:
            if not date_str:
                return None
            
            # Handle MM/DD/YY format specifically
            if '/' in str(date_str):
                parsed_date = pd.to_datetime(date_str, format='%m/%d/%y', errors='coerce')
            else:
                parsed_date = pd.to_datetime(date_str, errors='coerce')
            
            if pd.notna(parsed_date):
                return parsed_date.strftime('%m/%d/%y')
            
            return None
            
        except Exception as e:
            logging.warning(f"Error parsing date '{date_str}': {e}")
            return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float."""
        try:
            if not amount_str:
                return None
            
            amount_str = str(amount_str).strip()
            
            # Handle negative format: $ (60.00)
            if '$ (' in amount_str and ')' in amount_str:
                number_str = amount_str.replace('$ (', '').replace(')', '').replace(',', '')
                return -float(number_str)
            
            # Handle negative format: (25.50) - parentheses without dollar sign
            elif amount_str.startswith('(') and amount_str.endswith(')'):
                number_str = amount_str[1:-1].replace(',', '')
                return -float(number_str)
            
            # Handle positive format: $1,500.00
            elif '$' in amount_str:
                number_str = amount_str.replace('$', '').replace(',', '').strip()
                return float(number_str)
            
            # Handle plain numbers
            else:
                return float(amount_str)
            
        except Exception as e:
            logging.warning(f"Error parsing amount '{amount_str}': {e}")
            return None
    
    def _create_transaction_id(self, row_number: int, date: str, source: str, amount: str, company: str) -> str:
        """Create a hash-based transaction ID."""
        # Create a string to hash
        id_string = f"{row_number}_{date}_{source}_{amount}_{company}"
        
        # Create hash
        hash_object = hashlib.md5(id_string.encode())
        return hash_object.hexdigest()[:12]  # Use first 12 characters
    
    def _save_to_csv(self, transactions: List[Dict]) -> None:
        """Save transactions to CSV file."""
        try:
            # Create DataFrame
            df_data = []
            for transaction in transactions:
                df_data.append({
                    'transaction_id': transaction['transaction_id'],
                    'row_number': transaction['row_number'],
                    'date': transaction['date'],
                    'initials': transaction['initials'],
                    'source': transaction['source'],
                    'company': transaction['company'],
                    'amount': transaction['amount'],
                    'raw_date': transaction['raw_data']['date'],
                    'raw_amount': transaction['raw_data']['amount']
                })
            
            df = pd.DataFrame(df_data)
            
            # Save to CSV
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"data/downloaded_csv/petty_cash_{timestamp}.csv"
            df.to_csv(filename, index=False)
            
            logging.info(f"Saved {len(transactions)} transactions to {filename}")
            
        except Exception as e:
            logging.error(f"Error saving to CSV: {e}")
    
    def _save_zero_amount_transactions(self, zero_amount_transactions: List[Dict]) -> None:
        """Save zero-amount transactions to separate folder."""
        try:
            # Create zero amount directory
            Path("data/zero_amount_transactions").mkdir(parents=True, exist_ok=True)
            
            # Create DataFrame
            df_data = []
            for transaction in zero_amount_transactions:
                df_data.append({
                    'transaction_id': transaction['transaction_id'],
                    'row_number': transaction['row_number'],
                    'date': transaction['date'],
                    'initials': transaction['initials'],
                    'source': transaction['source'],
                    'company': transaction['company'],
                    'amount': transaction['amount'],
                    'raw_date': transaction['raw_data']['date'],
                    'raw_amount': transaction['raw_data']['amount']
                })
            
            df = pd.DataFrame(df_data)
            
            # Save to CSV in zero amount folder
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"data/zero_amount_transactions/zero_amount_{timestamp}.csv"
            df.to_csv(filename, index=False)
            
            logging.info(f"Saved {len(zero_amount_transactions)} zero-amount transactions to {filename}")
            
        except Exception as e:
            logging.error(f"Error saving zero-amount transactions: {e}")
    
    def get_latest_csv_file(self) -> Optional[str]:
        """Get the path to the latest CSV file."""
        try:
            csv_dir = Path("data/downloaded_csv")
            if not csv_dir.exists():
                return None
            
            csv_files = list(csv_dir.glob("petty_cash_*.csv"))
            if not csv_files:
                return None
            
            # Return the most recent file
            latest_file = max(csv_files, key=lambda x: x.stat().st_mtime)
            return str(latest_file)
            
        except Exception as e:
            logging.error(f"Error getting latest CSV file: {e}")
            return None

def main():
    """Test CSV downloader."""
    print("CSV DOWNLOADER TEST")
    print("=" * 50)
    
    downloader = CSVDownloader()
    
    # Download data
    transactions = downloader.download_petty_cash_data()
    
    if transactions:
        print(f"✅ Successfully downloaded {len(transactions)} transactions")
        
        # Show first few transactions
        print("\nFirst 5 transactions:")
        for i, transaction in enumerate(transactions[:5]):
            print(f"  {i+1}. Row {transaction['row_number']}: {transaction['source']} - ${transaction['amount']:.2f}")
        
        # Get latest CSV file
        latest_file = downloader.get_latest_csv_file()
        if latest_file:
            print(f"\n📁 Latest CSV file: {latest_file}")
        
    else:
        print("❌ Failed to download transactions")

if __name__ == "__main__":
    main() 