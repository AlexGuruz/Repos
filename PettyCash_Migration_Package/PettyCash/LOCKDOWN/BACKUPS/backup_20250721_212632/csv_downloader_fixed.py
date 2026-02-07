#!/usr/bin/env python3
"""
CSV Downloader - Fixed Version
Downloads petty cash data from Google Sheets and processes it
"""

import gspread
import pandas as pd
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from google_sheets_integration import GoogleSheetsIntegration
from hash_deduplication import HashDeduplication

class CSVDownloader:
    """Downloads and processes petty cash data from Google Sheets."""
    
    def __init__(self):
        # Google Sheets setup
        try:
            self.sheets_integration = GoogleSheetsIntegration()
            logging.info("✅ Google Sheets integration initialized")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Google Sheets integration: {e}")
            raise
        
        # Hash deduplication
        self.hash_dedup = HashDeduplication()
        
        # Create necessary directories
        Path("data/downloaded_csv").mkdir(parents=True, exist_ok=True)
        Path("data/zero_amount_transactions").mkdir(parents=True, exist_ok=True)
        
        logging.info("✅ CSV Downloader initialized successfully")
    
    def download_petty_cash_data(self) -> Optional[List[Dict]]:
        """Download PETTY CASH sheet data with calculated values."""
        try:
            logging.info(f"Downloading data from {self.worksheet_name} worksheet...")
            
            # Open the spreadsheet
            spreadsheet = self.gc.open_by_url(self.spreadsheet_url)
            worksheet = spreadsheet.worksheet(self.worksheet_name)
            
            # Find the last row with actual data to avoid downloading empty rows
            last_data_row = self._find_last_data_row(worksheet)
            logging.info(f"Found last data row at position: {last_data_row}")
            
            # Only download rows up to the last data row
            if last_data_row <= 4:  # Only headers or no data
                logging.warning("No data rows found in worksheet")
                return []
            
            # Get data only up to the last row with data
            all_data = worksheet.get_all_values(value_render_option='FORMATTED_VALUE')
            data_rows = all_data[:last_data_row + 1]  # Include the last data row
            
            logging.info(f"Downloaded {len(data_rows)} rows (instead of {len(all_data)} total rows)")
            
            # Process the data starting from row 5 (index 4)
            transactions = []
            zero_amount_transactions = []
            start_row = 4  # Skip header rows, start from row 5
            
            for i, row_data in enumerate(data_rows[start_row:], start=start_row + 1):
                row_number = i + 1  # 1-based row number
                
                # Extract data from specified columns
                try:
                    initials = row_data[self.columns['initials']] if len(row_data) > self.columns['initials'] else ''
                    date_val = row_data[self.columns['date']] if len(row_data) > self.columns['date'] else ''
                    company = row_data[self.columns['company']] if len(row_data) > self.columns['company'] else ''
                    source = row_data[self.columns['source']] if len(row_data) > self.columns['source'] else ''
                    amount_val = row_data[self.columns['amount']] if len(row_data) > self.columns['amount'] else ''
                    
                    # Skip rows missing required fields (initials can be optional)
                    required_fields = [date_val, company, source, amount_val]
                    if not all(required_fields):
                        logging.debug(f"Skipping row {row_number}: missing required data")
                        continue
                    
                    # Parse and validate data
                    parsed_date = self._parse_date(date_val)
                    parsed_amount = self._parse_amount(amount_val)
                    
                    if not parsed_date:
                        logging.warning(f"Skipping row {row_number}: invalid date")
                        continue
                    
                    if parsed_amount is None:
                        logging.warning(f"Skipping row {row_number}: invalid amount")
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
            
            # Filter out already processed transactions using hash deduplication
            transactions = self.hash_dedup.filter_new_transactions(transactions)
            if not transactions:
                logging.info("No new transactions to process - all have been processed before")
                return []
            
            # Save regular transactions to CSV file
            self._save_to_csv(transactions)
            
            # Save zero-amount transactions to separate folder
            if zero_amount_transactions:
                self._save_zero_amount_transactions(zero_amount_transactions)
            
            # Mark transactions as processed
            self.hash_dedup.mark_transactions_processed(transactions)
            
            return transactions
            
        except Exception as e:
            logging.error(f"Error downloading PETTY CASH data: {e}")
            return None
    
    def _find_last_data_row(self, worksheet) -> int:
        """Find the last row that contains actual data (not empty)."""
        try:
            # Get all values to find the last row with data
            all_values = worksheet.get_all_values()
            
            # Start from the end and work backwards to find the last row with data
            for row_idx in range(len(all_values) - 1, 3, -1):  # Start from end, skip first 4 rows (headers)
                row_data = all_values[row_idx]
                
                # Check if this row has any meaningful data
                if self._row_has_meaningful_data(row_data):
                    logging.info(f"Found last meaningful data at row {row_idx + 1}")
                    return row_idx
            
            # If no data found, return 4 (just headers)
            logging.warning("No meaningful data found, returning header row only")
            return 4
            
        except Exception as e:
            logging.error(f"Error finding last data row: {e}")
            # Fallback: return a reasonable default
            return 1000  # Conservative default
    
    def _row_has_meaningful_data(self, row_data: List[str]) -> bool:
        """Check if a row contains meaningful transaction data."""
        if not row_data:
            return False
        
        # Check if any of the key columns have meaningful data
        key_columns = [
            self.columns['initials'],
            self.columns['date'], 
            self.columns['company'],
            self.columns['source'],
            self.columns['amount']
        ]
        
        meaningful_data_count = 0
        
        for col_idx in key_columns:
            if col_idx < len(row_data):
                cell_value = row_data[col_idx].strip()
                
                # Skip empty cells, formulas, and formatting-only cells
                if cell_value and not self._is_formula_or_formatting(cell_value):
                    meaningful_data_count += 1
        
        # Require at least 3 meaningful data points to consider it a real transaction row
        return meaningful_data_count >= 3
    
    def _is_formula_or_formatting(self, cell_value: str) -> bool:
        """Check if a cell contains only formulas or formatting."""
        if not cell_value:
            return True
        
        # Skip cells that are just formulas
        if cell_value.startswith('='):
            return True
        
        # Skip cells that are just formatting (common in spreadsheets)
        formatting_patterns = [
            '', ' ', '-', '--', '---', '____', '====', '****',
            'N/A', 'n/a', 'NA', 'na', 'TBD', 'tbd', 'PENDING', 'pending'
        ]
        
        if cell_value in formatting_patterns:
            return True
        
        # Skip cells that are just numbers without context (likely formatting)
        if cell_value.isdigit() and len(cell_value) <= 2:
            return True
        
        return False
    
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
            '-$0.0', '-$ 0.0', '0', '0.0', '0.00',
            '$ (0.00)', '$ (0)', '$ (0.0)',  # Add missing patterns
            '(0.00)', '(0)', '(0.0)'  # Add missing patterns
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
            
            # Handle zero/empty amounts first
            if self._is_zero_amount(amount_str):
                return 0.0
            
            # Handle negative format: $ (60.00) - parentheses with dollar sign
            if '$ (' in amount_str and ')' in amount_str:
                number_str = amount_str.replace('$ (', '').replace(')', '').replace(',', '')
                parsed_amount = float(number_str)
                return -parsed_amount  # Make it negative
            
            # Handle negative format: (25.50) - parentheses without dollar sign
            elif amount_str.startswith('(') and amount_str.endswith(')'):
                number_str = amount_str[1:-1].replace(',', '')
                parsed_amount = float(number_str)
                return -parsed_amount  # Make it negative
            
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