# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Google Sheets Header Monitoring System
Monitors Google Sheets for new headers and sheets, updates JGD Truth dropdowns automatically.
"""

import sqlite3
import logging
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import gspread
from gspread_formatting import set_data_validation_for_cell_range, DataValidationRule, BooleanCondition

# Configuration
PETTY_CASH_URL = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU/edit?pli=1&gid=1785437689#gid=1785437689"
JGD_TRUTH_URL = "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit?gid=1349136605#gid=1349136605"
MONITOR_INTERVAL = 30 * 60  # 30 minutes in seconds
DATABASE_PATH = Path("data/header_monitor.db")
LOG_PATH = Path("logs/header_monitor.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

class DatabaseManager:
    """Manages SQLite database for header monitoring and metadata."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Headers table - stores all headers from all sheets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sheet_headers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sheet_name TEXT NOT NULL,
                    header_name TEXT NOT NULL,
                    header_position INTEGER,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sheet_name, header_name)
                )
            ''')
            
            # Sheets table - stores all sheet names
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sheet_names (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sheet_name TEXT UNIQUE NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Monitoring history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monitoring_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # System status table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY,
                    last_check TIMESTAMP,
                    last_processing TIMESTAMP,
                    status TEXT,
                    error_message TEXT
                )
            ''')
            
            conn.commit()
    
    def store_headers(self, sheet_name: str, headers: List[str]):
        """Store headers for a sheet."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Store sheet name
                cursor.execute('''
                    INSERT OR REPLACE INTO sheet_names (sheet_name, last_updated)
                    VALUES (?, ?)
                ''', (sheet_name, datetime.now()))
                
                # Store headers
                for position, header in enumerate(headers):
                    cursor.execute('''
                        INSERT OR REPLACE INTO sheet_headers 
                        (sheet_name, header_name, header_position, last_updated)
                        VALUES (?, ?, ?, ?)
                    ''', (sheet_name, header, position, datetime.now()))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error storing headers: {e}")
            return False
    
    def get_all_headers(self) -> Dict[str, List[str]]:
        """Get all headers organized by sheet."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sheet_name, header_name, header_position
                FROM sheet_headers
                ORDER BY sheet_name, header_position
            ''')
            rows = cursor.fetchall()
            
            headers_by_sheet = {}
            for row in rows:
                sheet_name, header_name, position = row
                if sheet_name not in headers_by_sheet:
                    headers_by_sheet[sheet_name] = []
                headers_by_sheet[sheet_name].append(header_name)
            
            return headers_by_sheet
    
    def get_all_sheet_names(self) -> List[str]:
        """Get all sheet names."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT sheet_name FROM sheet_names ORDER BY sheet_name')
            return [row[0] for row in cursor.fetchall()]
    
    def log_action(self, action: str, details: str):
        """Log monitoring actions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO monitoring_history (action, details)
                VALUES (?, ?)
            ''', (action, details))
            conn.commit()
    
    def update_system_status(self, status: str, error_message: Optional[str] = None):
        """Update system status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO system_status (id, last_check, status, error_message)
                VALUES (1, ?, ?, ?)
            ''', (datetime.now(), status, error_message or ""))
            conn.commit()

class GoogleSheetsManager:
    """Manages Google Sheets connections and operations."""
    
    def __init__(self, service_account_path: str = "config/service_account.json"):
        self.service_account_path = service_account_path
        self.gc = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Sheets."""
        try:
            self.gc = gspread.service_account(filename=self.service_account_path)
            logging.info("Successfully authenticated with Google Sheets")
            return True
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            self.gc = None
            return False
    
    def get_all_sheets_and_headers(self, spreadsheet_url: str) -> Dict[str, List[str]]:
        """Get all sheets and their headers from a spreadsheet."""
        try:
            if not self.gc:
                logging.error("Google Sheets client not authenticated")
                return {}
                
            spreadsheet = self.gc.open_by_url(spreadsheet_url)
            sheets_and_headers = {}
            
            # Sheets to ignore (no headers or sheet names from these)
            IGNORED_SHEETS = {
                'EXPANSION CHECKLIST', 'Balance and Misc', 'Petty Cash KEY', 'TIM', 
                'SHIFT LOG', 'Copy of TIM', 'EQUIPMENT UPGRADES', 'Info', 'C-Store', 
                'All Time Resale', 'Monthly Burn', 'Trimming', '2022 1099s', 
                'Bills Need Moved to Alt Acct', 'Nydam Credit Card Debt Excluded', 
                'TIMELESS 4 SUNDAY', 'ORG CHART', 'PREROLLS', 'Paystub', 'Sheet1', 
                'Colorado Cures', '2023 1099s'
            }
            
            # Patterns for non-header values (should be excluded)
            NON_HEADER_PATTERNS = [
                r'^\s*\$\s*[\d,]+\.?\d*\s*$',  # Dollar amounts like "$ 1,500.00"
                r'^\s*\$\s*\([\d,]+\.?\d*\)\s*$',  # Negative dollar amounts like "$ (1,240.00)"
                r'^\s*[\d,]+\.?\d*\s*%?\s*$',  # Percentages like "40%" or numbers
                r'^\s*[\d,]+\.?\d*\s*PER\s+\d+\s*$',  # Like "20 PER 1000"
                r'^\s*[\d,]+\.?\d*\s*$',  # Plain numbers
                r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$',  # Timestamps
                r'^New source from.*$',  # "New source from..." entries
                r'^\s*$',  # Empty or whitespace only
            ]
            
            # Words that indicate this is likely a header (keep these)
            HEADER_INDICATORS = [
                'total', 'amount', 'date', 'name', 'description', 'category', 'type', 
                'status', 'id', 'number', 'code', 'account', 'balance', 'payment',
                'receipt', 'invoice', 'transaction', 'entry', 'record', 'item',
                'product', 'service', 'cost', 'price', 'fee', 'charge', 'credit',
                'debit', 'deposit', 'withdrawal', 'transfer', 'adjustment', 'correction',
                'note', 'comment', 'reference', 'source', 'destination', 'location',
                'department', 'division', 'section', 'group', 'team', 'manager',
                'employee', 'customer', 'vendor', 'supplier', 'client', 'partner'
            ]
            
            import re
            
            for worksheet in spreadsheet.worksheets():
                sheet_name = worksheet.title
                
                # Skip ignored sheets
                if sheet_name in IGNORED_SHEETS:
                    logging.info(f"Skipping ignored sheet '{sheet_name}'")
                    continue
                
                try:
                    # Get headers from row 19 (as per existing mapping system)
                    headers = worksheet.row_values(19)
                    # Filter out empty headers and non-header values
                    filtered_headers = []
                    
                    for header in headers:
                        if not header or not header.strip():
                            continue
                            
                        header_clean = header.strip()
                        
                        # Check if it matches non-header patterns
                        is_non_header = False
                        for pattern in NON_HEADER_PATTERNS:
                            if re.match(pattern, header_clean, re.IGNORECASE):
                                is_non_header = True
                                break
                        
                        # If it doesn't match non-header patterns, check if it looks like a header
                        if not is_non_header:
                            # Check if it contains header indicator words
                            header_lower = header_clean.lower()
                            has_header_indicators = any(indicator in header_lower for indicator in HEADER_INDICATORS)
                            
                            # Keep if it has header indicators or is short (likely a header)
                            if has_header_indicators or len(header_clean) <= 30:
                                filtered_headers.append(header_clean)
                            else:
                                # For longer text, be more selective - only exclude if it's clearly not a header
                                if not any(char.isdigit() for char in header_clean[:10]):  # Doesn't start with numbers
                                    filtered_headers.append(header_clean)
                    
                    sheets_and_headers[sheet_name] = filtered_headers
                    logging.info(f"Retrieved {len(filtered_headers)} valid headers from sheet '{sheet_name}' (row 19)")
                    
                except Exception as e:
                    logging.warning(f"Could not get headers from sheet '{sheet_name}': {e}")
                    sheets_and_headers[sheet_name] = []
            
            return sheets_and_headers
        except Exception as e:
            logging.error(f"Error getting sheets and headers: {e}")
            return {}
    
    def update_jgd_truth_dropdowns(self, sheet_names: List[str], all_headers: Dict[str, List[str]]):
        """Update JGD Truth sheet dropdowns with new sheets and headers."""
        try:
            if not self.gc:
                logging.error("Google Sheets client not authenticated")
                return False
                
            spreadsheet = self.gc.open_by_url(JGD_TRUTH_URL)
            
            # Get all worksheets that need dropdowns
            target_sheets = ['NUGZ', 'JGD', 'PUFFIN']
            worksheets = {}
            
            for sheet_name in target_sheets:
                try:
                    worksheets[sheet_name] = spreadsheet.worksheet(sheet_name)
                    logging.info(f"Found {sheet_name} worksheet")
                except Exception as e:
                    logging.warning(f"Could not find {sheet_name} worksheet: {e}")
                    continue
            
            logging.info(f"Updating JGD Truth dropdowns with {len(sheet_names)} sheets and headers from {len(all_headers)} sheets")
            
            # Create separate lists for sheet names and headers
            sheet_name_options = []
            header_options = []
            
            # Sheets to ignore (same list as above)
            IGNORED_SHEETS = {
                'EXPANSION CHECKLIST', 'Balance and Misc', 'Petty Cash KEY', 'TIM', 
                'SHIFT LOG', 'Copy of TIM', 'EQUIPMENT UPGRADES', 'Info', 'C-Store', 
                'All Time Resale', 'Monthly Burn', 'Trimming', '2022 1099s', 
                'Bills Need Moved to Alt Acct', 'Nydam Credit Card Debt Excluded', 
                'TIMELESS 4 SUNDAY', 'ORG CHART', 'PREROLLS', 'Paystub', 'Sheet1', 
                'Colorado Cures', '2023 1099s'
            }
            
            for sheet_name in sheet_names:
                # Skip ignored sheets for sheet name dropdown
                if sheet_name in IGNORED_SHEETS:
                    continue
                    
                if sheet_name in all_headers:
                    # Add sheet name to sheet options
                    sheet_name_options.append(sheet_name)
                    # Add headers to header options (without sheet prefix)
                    for header in all_headers[sheet_name]:
                        header_options.append(header)
            
            # Sort the options for consistency
            sheet_name_options.sort()
            header_options.sort()
            
            # Remove duplicates from header options
            header_options = list(set(header_options))
            header_options.sort()
            
            logging.info(f"Sheet name options: {len(sheet_name_options)}")
            logging.info(f"Header options: {len(header_options)}")
            
            # Get actual sheet dimensions - use 988 as the actual limit
            max_row = 988
            logging.info(f"Applying dropdowns to rows 2-{max_row} on all target sheets")
            
            # Update dropdowns on all target worksheets
            for sheet_name, worksheet in worksheets.items():
                logging.info(f"Updating dropdowns on {sheet_name} sheet...")
                
                # Update dropdown in column B for sheet names (starting from row 2)
                if sheet_name_options:
                    sheet_rule = DataValidationRule(
                        BooleanCondition('ONE_OF_LIST', sheet_name_options),
                        showCustomUi=True,
                        strict=True
                    )
                    set_data_validation_for_cell_range(worksheet, f'B2:B{max_row}', sheet_rule)
                    logging.info(f"✅ Updated {sheet_name} Column B dropdown with {len(sheet_name_options)} sheet names")
                
                # Update dropdown in column C for headers (starting from row 2)
                if header_options:
                    header_rule = DataValidationRule(
                        BooleanCondition('ONE_OF_LIST', header_options),
                        showCustomUi=True,
                        strict=True
                    )
                    set_data_validation_for_cell_range(worksheet, f'C2:C{max_row}', header_rule)
                    logging.info(f"✅ Updated {sheet_name} Column C dropdown with {len(header_options)} headers")
                    
                    # Check if REGISTERS is in the header options
                    if "REGISTERS" in header_options:
                        position = header_options.index("REGISTERS") + 1
                        logging.info(f"✅ REGISTERS header found at position {position} out of {len(header_options)} in {sheet_name}")
                    else:
                        logging.warning(f"❌ REGISTERS header NOT found in {sheet_name} dropdown options!")
                
                # Update summary cells on each sheet
                try:
                    worksheet.update_cell(1, 2, f'Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                    worksheet.update_cell(1, 3, f'Total Options: {len(header_options)}')
                    logging.info(f"Summary cells updated successfully on {sheet_name}")
                except Exception as e:
                    logging.warning(f"Could not update summary cells on {sheet_name} (non-critical): {e}")
            
            return True
                
        except Exception as e:
            logging.error(f"Error updating JGD Truth dropdowns: {e}")
            return False

class HeaderMonitor:
    """Monitors headers and sheets for changes."""
    
    def __init__(self, db_manager: DatabaseManager, sheets_manager: GoogleSheetsManager):
        self.db_manager = db_manager
        self.sheets_manager = sheets_manager
    
    def check_for_changes(self, spreadsheet_url: str) -> Dict:
        """Check for new sheets and headers."""
        try:
            # Get current sheets and headers from Google Sheets
            current_sheets_headers = self.sheets_manager.get_all_sheets_and_headers(spreadsheet_url)
            
            # Get stored sheets and headers from database
            stored_headers = self.db_manager.get_all_headers()
            stored_sheets = self.db_manager.get_all_sheet_names()
            
            changes = {
                'new_sheets': [],
                'new_headers': [],
                'removed_sheets': [],
                'removed_headers': [],
                'updated': False
            }
            
            # Check for new sheets
            current_sheets = list(current_sheets_headers.keys())
            for sheet in current_sheets:
                if sheet not in stored_sheets:
                    changes['new_sheets'].append(sheet)
                    changes['updated'] = True
            
            # Check for removed sheets
            for sheet in stored_sheets:
                if sheet not in current_sheets:
                    changes['removed_sheets'].append(sheet)
                    changes['updated'] = True
            
            # Check for new headers
            for sheet_name, headers in current_sheets_headers.items():
                if sheet_name in stored_headers:
                    stored_headers_for_sheet = stored_headers[sheet_name]
                    for header in headers:
                        if header not in stored_headers_for_sheet:
                            changes['new_headers'].append(f"{sheet_name}:{header}")
                            changes['updated'] = True
                else:
                    # New sheet, all headers are new
                    for header in headers:
                        changes['new_headers'].append(f"{sheet_name}:{header}")
                    changes['updated'] = True
            
            # Check for removed headers
            for sheet_name, stored_headers_for_sheet in stored_headers.items():
                if sheet_name in current_sheets_headers:
                    current_headers = current_sheets_headers[sheet_name]
                    for header in stored_headers_for_sheet:
                        if header not in current_headers:
                            changes['removed_headers'].append(f"{sheet_name}:{header}")
                            changes['updated'] = True
            
            return changes
            
        except Exception as e:
            logging.error(f"Error checking for changes: {e}")
            return {'updated': False, 'error': str(e)}
    
    def update_database(self, spreadsheet_url: str):
        """Update database with current sheets and headers."""
        try:
            current_sheets_headers = self.sheets_manager.get_all_sheets_and_headers(spreadsheet_url)
            
            for sheet_name, headers in current_sheets_headers.items():
                self.db_manager.store_headers(sheet_name, headers)
            
            logging.info(f"Updated database with {len(current_sheets_headers)} sheets")
            return True
        except Exception as e:
            logging.error(f"Error updating database: {e}")
            return False

class MonitorSystem:
    """Main monitoring system."""
    
    def __init__(self):
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.sheets_manager = GoogleSheetsManager()
        self.header_monitor = HeaderMonitor(self.db_manager, self.sheets_manager)
        self.running = False
    
    def run_monitoring_cycle(self):
        """Run one monitoring cycle."""
        try:
            logging.info("Starting header monitoring cycle")
            
            # Update system status
            self.db_manager.update_system_status("RUNNING")
            
            # Check for changes in Petty Cash spreadsheet
            changes = self.header_monitor.check_for_changes(PETTY_CASH_URL)
            
            if changes['updated']:
                logging.info("Changes detected:")
                if changes['new_sheets']:
                    logging.info(f"New sheets: {changes['new_sheets']}")
                if changes['new_headers']:
                    logging.info(f"New headers: {changes['new_headers']}")
                if changes['removed_sheets']:
                    logging.info(f"Removed sheets: {changes['removed_sheets']}")
                if changes['removed_headers']:
                    logging.info(f"Removed headers: {changes['removed_headers']}")
                
                # Update database with current state
                self.header_monitor.update_database(PETTY_CASH_URL)
                
                # Get all current sheets and headers
                all_headers = self.db_manager.get_all_headers()
                all_sheets = self.db_manager.get_all_sheet_names()
                
                # Update JGD Truth dropdowns
                self.sheets_manager.update_jgd_truth_dropdowns(all_sheets, all_headers)
                
                # Log the action
                self.db_manager.log_action("HEADERS_UPDATED", f"Updated {len(changes['new_headers'])} new headers, {len(changes['new_sheets'])} new sheets")
                
                logging.info("Header monitoring cycle completed with updates")
                return len(changes['new_headers']) + len(changes['new_sheets'])
            else:
                logging.info("No changes detected in header monitoring cycle")
                return 0
            
        except Exception as e:
            logging.error(f"Error in monitoring cycle: {e}")
            self.db_manager.update_system_status("ERROR", str(e))
            return 0
        finally:
            # Update system status
            self.db_manager.update_system_status("IDLE")
    
    def start_monitoring(self):
        """Start continuous monitoring."""
        self.running = True
        logging.info(f"Starting header monitoring system (checking every {MONITOR_INTERVAL} seconds)")
        
        while self.running:
            try:
                self.run_monitoring_cycle()
                time.sleep(MONITOR_INTERVAL)
            except KeyboardInterrupt:
                logging.info("Header monitoring stopped by user")
                self.running = False
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.running = False
        logging.info("Header monitoring system stopped")

def main():
    """Main function."""
    monitor = MonitorSystem()
    
    try:
        monitor.start_monitoring()
    except KeyboardInterrupt:
        monitor.stop_monitoring()

if __name__ == "__main__":
    main() 