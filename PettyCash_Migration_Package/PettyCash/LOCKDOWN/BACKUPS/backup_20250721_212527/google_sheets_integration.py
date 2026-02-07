#!/usr/bin/env python3
"""
Google Sheets Integration Module
Handles layout mapping, batch updates, and cell coordinate finding
"""

import gspread
import logging
import json
import time
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional, Tuple

class GoogleSheetsIntegration:
    """Handles all Google Sheets operations including layout mapping and batch updates."""
    
    def __init__(self):
        # Google Sheets setup
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_file('config/service_account.json', scopes=self.scope)
        self.gc = gspread.authorize(self.creds)
        
        # Spreadsheet URLs
        self.petty_cash_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        self.financials_spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        
        # Layout map cache for fast cell coordinate lookups
        self.layout_map_cache = {}
        self.layout_map_file = "config/layout_map.json"  # Use the correct layout map file
        
        # Failed transactions tracking
        self.failed_transactions = []
        self.failed_transactions_file = "logs/failed_transactions.json"
        
        # Create directories
        Path("config").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/google_sheets_integration.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING GOOGLE SHEETS INTEGRATION")
        logging.info("=" * 60)
        
        # Load layout map cache
        self.load_layout_map_cache()
    
    def create_layout_map(self, config_manager=None) -> Dict:
        """Create/update layout map from live Google Sheets using configuration guidelines."""
        logging.info("CREATING/UPDATING LAYOUT MAP FROM LIVE GOOGLE SHEETS")
        logging.info("=" * 60)
        
        try:
            # Load configuration from main config or fallback to sheet structure config
            if config_manager:
                # Use main configuration
                header_row = config_manager.get('layout_mapping.header_row', 19)
                date_column = config_manager.get('layout_mapping.date_column', 'A')
                exclude_sheets = config_manager.get('layout_mapping.exclude_sheets', ['COMMISSION'])
                sheets_to_skip = config_manager.get('sheets_to_skip', [])
                
                # Combine exclude sheets
                all_excluded = list(set(exclude_sheets + sheets_to_skip))
                
                logging.info(f"Using main config - header row: {header_row}, date column: {date_column}")
                logging.info(f"Excluding sheets: {all_excluded}")
            else:
                # Fallback to sheet structure configuration
                config = self._load_sheet_structure_config()
                if not config:
                    logging.error("Failed to load sheet structure configuration")
                    return {}
                
                header_row = config.get('sheet_structure', {}).get('header_row', 19)
                date_column = config.get('sheet_structure', {}).get('date_column', 'A')
                all_excluded = config.get('target_sheets', {}).get('ignored', [])
            
            # Open the live Google spreadsheet
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            layout_map = {}
            
            for worksheet in spreadsheet.worksheets():
                sheet_name = worksheet.title
                
                # Skip excluded sheets
                if sheet_name in all_excluded:
                    logging.debug(f"Skipping excluded sheet: {sheet_name}")
                    continue
                
                logging.info(f"Processing sheet: {sheet_name}")
                sheet_map = {}
                
                try:
                    # Get all values from the worksheet
                    all_values = worksheet.get_all_values()
                    
                    if not all_values:
                        logging.warning(f"Sheet {sheet_name} is empty")
                        continue
                    
                    # Check if header row exists
                    if len(all_values) < header_row:
                        logging.warning(f"Sheet {sheet_name} has fewer rows than expected header row {header_row}")
                        continue
                    
                    # Get headers from the specified row
                    headers = all_values[header_row - 1]  # Convert to 0-based index
                    logging.info(f"Found headers in row {header_row}: {headers[:10]}...")  # Show first 10 headers
                    
                    # Map each header to its column index
                    for col_idx, header in enumerate(headers):
                        if header and str(header).strip():
                            header_clean = str(header).strip()
                            sheet_map[header_clean] = {
                                'row': header_row,  # 1-based row
                                'col': col_idx + 1,    # 1-based column
                                'sheet': sheet_name
                            }
                    
                    layout_map[sheet_name] = sheet_map
                    logging.info(f"Mapped {len(sheet_map)} headers in {sheet_name}")
                    
                except Exception as e:
                    logging.error(f"Error processing sheet {sheet_name}: {e}")
                    continue
            
            # Save layout map to cache
            self.layout_map_cache = layout_map
            self.save_layout_map_cache()
            
            logging.info(f"Layout map created successfully with {len(layout_map)} target sheets")
            return layout_map
            
        except Exception as e:
            logging.error(f"Error creating layout map: {e}")
            return {}
    
    def _load_sheet_structure_config(self) -> Dict:
        """Load sheet structure configuration from file."""
        try:
            config_file = "config/sheet_structure_config.json"
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                logging.info("Loaded sheet structure configuration")
                return config
            else:
                logging.error(f"Sheet structure configuration file not found: {config_file}")
                return {}
        except Exception as e:
            logging.error(f"Error loading sheet structure configuration: {e}")
            return {}
    
    def save_layout_map_cache(self):
        """Save layout map to cache file."""
        try:
            with open(self.layout_map_file, 'w') as f:
                json.dump(self.layout_map_cache, f, indent=2)
            logging.info(f"Layout map cache saved to {self.layout_map_file}")
        except Exception as e:
            logging.error(f"Error saving layout map cache: {e}")
    
    def load_layout_map_cache(self):
        """Load layout map from cache file."""
        try:
            if Path(self.layout_map_file).exists():
                with open(self.layout_map_file, 'r') as f:
                    self.layout_map_cache = json.load(f)
                logging.info(f"Loaded layout map cache with {len(self.layout_map_cache)} sheets")
            else:
                logging.info("No layout map cache found, will create new one")
                self.layout_map_cache = {}
        except Exception as e:
            logging.error(f"Error loading layout map cache: {e}")
            self.layout_map_cache = {}
    
    def get_layout_map(self) -> Dict:
        """Get the current layout map cache."""
        return self.layout_map_cache
    
    def find_target_cell_coordinates(self, target_sheet: str, target_header: str, date_str: str) -> Optional[Dict]:
        """Find target cell coordinates based on sheet, header, and date."""
        try:
            if target_sheet not in self.layout_map_cache:
                logging.warning(f"Sheet '{target_sheet}' not found in layout map")
                return None
            
            sheet_map = self.layout_map_cache[target_sheet]
            
            if target_header not in sheet_map:
                logging.warning(f"Header '{target_header}' not found in sheet '{target_sheet}'")
                return None
            
            header_info = sheet_map[target_header]
            
            # Parse date to find the correct row
            try:
                date_obj = datetime.strptime(date_str, '%m/%d/%y')
                month = date_obj.month
                year = date_obj.year
                
                # Find the row for this month/year
                target_row = self._find_date_row(target_sheet, month, year, header_info['row'])
                
                if target_row:
                    return {
                        'sheet': target_sheet,
                        'row': target_row,
                        'col': header_info['col'],
                        'header': target_header
                    }
                else:
                    logging.warning(f"Could not find row for date {date_str} in sheet {target_sheet}")
                    return None
                    
            except Exception as e:
                logging.error(f"Error parsing date {date_str}: {e}")
                return None
                
        except Exception as e:
            logging.error(f"Error finding target cell coordinates: {e}")
            return None
    
    def _find_date_row(self, sheet_name: str, month: int, year: int, header_row: int) -> Optional[int]:
        """Find the row for a specific month/year in a sheet."""
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            worksheet = None
            
            for ws in spreadsheet.worksheets():
                if ws.title == sheet_name:
                    worksheet = ws
                    break
            
            if not worksheet:
                return None
            
            # Get all values
            all_values = worksheet.get_all_values()
            if len(all_values) < 20:  # Need at least 20 rows
                return None
            
            # Start looking from row 20 (where dates actually begin)
            # Dates start on row 20 with last two days of previous year, then current year
            start_row = 19  # 0-based index for row 20
            
            # Look for the month/year in the first column (date column)
            for row_idx in range(start_row, len(all_values)):
                row = all_values[row_idx]
                if row and len(row) > 0:
                    first_cell = str(row[0]).strip()
                    
                    # Try to parse the cell as a date
                    try:
                        # Handle different date formats
                        if '/' in first_cell:
                            # Try parsing as m/d/yy or m/d/yyyy
                            if len(first_cell.split('/')) == 3:
                                parts = first_cell.split('/')
                                cell_month = int(parts[0])
                                cell_day = int(parts[1])
                                cell_year_str = parts[2]
                                
                                # Handle 2-digit years
                                if len(cell_year_str) == 2:
                                    cell_year = 2000 + int(cell_year_str)
                                else:
                                    cell_year = int(cell_year_str)
                                
                                # Check if this matches our target month/year
                                if cell_month == month and cell_year == year:
                                    return row_idx + 1  # Convert to 1-based
                    except (ValueError, IndexError):
                        # If parsing fails, continue to next row
                        continue
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding date row: {e}")
            return None
    
    def batch_find_target_cell_coordinates(self, coordinate_requests: List[Dict]) -> Dict[str, Optional[Dict]]:
        """Find target cell coordinates for multiple transactions in batch to reduce API calls."""
        results = {}
        
        try:
            # Group requests by sheet to minimize API calls
            sheet_requests = {}
            for request in coordinate_requests:
                sheet_name = request['target_sheet']
                if sheet_name not in sheet_requests:
                    sheet_requests[sheet_name] = []
                sheet_requests[sheet_name].append(request)
            
            # Process each sheet
            for sheet_name, requests in sheet_requests.items():
                logging.info(f"Finding coordinates for {len(requests)} transactions in sheet: {sheet_name}")
                
                # Get sheet data once for all requests to this sheet
                sheet_data = self._get_sheet_data(sheet_name)
                if not sheet_data:
                    # Mark all requests for this sheet as failed
                    for request in requests:
                        request_key = f"{request['target_sheet']}_{request['target_header']}_{request['date']}"
                        results[request_key] = None
                    continue
                
                # Process each request for this sheet
                for request in requests:
                    request_key = f"{request['target_sheet']}_{request['target_header']}_{request['date']}"
                    
                    try:
                        coords = self._find_coordinates_in_sheet_data(
                            sheet_data, 
                            request['target_header'], 
                            request['date']
                        )
                        results[request_key] = coords
                    except Exception as e:
                        logging.warning(f"Error finding coordinates for {request_key}: {e}")
                        results[request_key] = None
            
            return results
            
        except Exception as e:
            logging.error(f"Error in batch coordinate finding: {e}")
            # Return None for all requests on error
            for request in coordinate_requests:
                request_key = f"{request['target_sheet']}_{request['target_header']}_{request['date']}"
                results[request_key] = None
            return results
    
    def _get_sheet_data(self, sheet_name: str) -> Optional[List[List[str]]]:
        """Get all data from a sheet once to avoid multiple API calls."""
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            worksheet = None
            
            for ws in spreadsheet.worksheets():
                if ws.title == sheet_name:
                    worksheet = ws
                    break
            
            if not worksheet:
                return None
            
            # Get all values from the sheet
            all_values = worksheet.get_all_values()
            return all_values
            
        except Exception as e:
            logging.error(f"Error getting sheet data for {sheet_name}: {e}")
            return None
    
    def _find_coordinates_in_sheet_data(self, sheet_data: List[List[str]], target_header: str, date_str: str) -> Optional[Dict]:
        """Find coordinates using pre-loaded sheet data."""
        try:
            if len(sheet_data) < 20:  # Need at least 20 rows
                return None
            
            # Find header row (row 19, 0-based index 18)
            header_row = 18
            if len(sheet_data) <= header_row:
                return None
            
            # Find target header column
            header_cells = sheet_data[header_row]
            target_col = None
            for col_idx, cell in enumerate(header_cells):
                if str(cell).strip().upper() == target_header.upper():
                    target_col = col_idx + 1  # Convert to 1-based
                    break
            
            if not target_col:
                return None
            
            # Parse date
            if '/' in date_str and len(date_str.split('/')) == 3:
                parts = date_str.split('/')
                month = int(parts[0])
                day = int(parts[1])
                year_str = parts[2]
                
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
            else:
                return None
            
            # Find date row starting from row 20 (0-based index 19)
            start_row = 19
            target_row = None
            
            for row_idx in range(start_row, len(sheet_data)):
                row = sheet_data[row_idx]
                if row and len(row) > 0:
                    first_cell = str(row[0]).strip()
                    
                    try:
                        if '/' in first_cell and len(first_cell.split('/')) == 3:
                            parts = first_cell.split('/')
                            cell_month = int(parts[0])
                            cell_year_str = parts[2]
                            
                            if len(cell_year_str) == 2:
                                cell_year = 2000 + int(cell_year_str)
                            else:
                                cell_year = int(cell_year_str)
                            
                            if cell_month == month and cell_year == year:
                                target_row = row_idx + 1  # Convert to 1-based
                                break
                    except (ValueError, IndexError):
                        continue
            
            if not target_row:
                return None
            
            return {
                'sheet': sheet_data[0][0] if sheet_data and sheet_data[0] else 'Unknown',
                'row': target_row,
                'col': target_col,
                'header': target_header
            }
            
        except Exception as e:
            logging.error(f"Error finding coordinates in sheet data: {e}")
            return None
    
    def batch_update_sheets_by_tab(self, sheet_groups: Dict) -> Dict:
        """Update sheets with batch operations grouped by tab/sheet."""
        logging.info("EXECUTING BATCH UPDATES BY TAB")
        logging.info("=" * 60)
        
        results = {
            'successful_updates': 0,
            'failed_updates': 0,
            'sheets_updated': 0,
            'total_cells_updated': 0,
            'errors': []
        }
        
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            
            for sheet_name, cell_updates in sheet_groups.items():
                logging.info(f"Processing batch update for sheet '{sheet_name}' with {len(cell_updates)} target cells")
                
                # Get worksheet
                worksheet = None
                for ws in spreadsheet.worksheets():
                    if ws.title == sheet_name:
                        worksheet = ws
                        break
                
                if not worksheet:
                    error_msg = f"Target sheet '{sheet_name}' not found"
                    logging.error(error_msg)
                    results['errors'].append(error_msg)
                    results['failed_updates'] += len(cell_updates)
                    continue
                
                # Prepare batch update data for this sheet
                batch_data = []
                
                # Batch read all current values for this sheet to minimize API calls
                try:
                    # Get all unique rows and columns that need to be read
                    unique_cells = set()
                    for cell_key, cell_data in cell_updates.items():
                        unique_cells.add((cell_data['row'], cell_data['col']))
                    
                    # Batch read all current values in one API call
                    current_values = {}
                    if unique_cells:
                        # Get the range that covers all cells
                        min_row = min(cell[0] for cell in unique_cells)
                        max_row = max(cell[0] for cell in unique_cells)
                        min_col = min(cell[1] for cell in unique_cells)
                        max_col = max(cell[1] for cell in unique_cells)
                        
                        # Convert to letter format
                        def col_to_letter(col_num):
                            """Convert column number to letter (A, B, ..., Z, AA, AB, etc.)"""
                            result = ""
                            while col_num > 0:
                                col_num -= 1
                                result = chr(65 + (col_num % 26)) + result
                                col_num //= 26
                            return result
                        
                        range_name = f"{col_to_letter(min_col)}{min_row}:{col_to_letter(max_col)}{max_row}"
                        logging.info(f"Batch reading range {range_name} for {len(unique_cells)} cells")
                        
                        # Read all values in one API call
                        range_data = worksheet.get(range_name)
                        if range_data:
                            for row_idx, row_data in enumerate(range_data):
                                for col_idx, cell_value in enumerate(row_data):
                                    actual_row = min_row + row_idx
                                    actual_col = min_col + col_idx
                                    if (actual_row, actual_col) in unique_cells:
                                        current_values[(actual_row, actual_col)] = cell_value
                    
                    logging.info(f"✅ Batch read {len(current_values)} current values for {sheet_name}")
                    
                except Exception as e:
                    logging.warning(f"Error batch reading current values for {sheet_name}: {e}")
                    current_values = {}
                
                # Process each cell update
                for cell_key, cell_data in cell_updates.items():
                    row = cell_data['row']
                    col = cell_data['col']
                    new_amount = cell_data['amount']
                    
                    # Get current value from batch read data
                    current_value = current_values.get((row, col), 0)
                    current_amount = self._parse_amount(current_value)
                    
                    # REPLACE current amount with new amount (don't add)
                    final_amount = new_amount
                    
                    # Send raw numeric value to Google Sheets (let Sheets handle formatting)
                    # Add to batch update - Fix range format to handle columns beyond Z
                    def col_to_letter(col_num):
                        """Convert column number to letter (A, B, ..., Z, AA, AB, etc.)"""
                        result = ""
                        while col_num > 0:
                            col_num -= 1
                            result = chr(65 + (col_num % 26)) + result
                            col_num //= 26
                        return result
                    
                    cell_range = f"{col_to_letter(col)}{row}"
                    batch_data.append({
                        'range': cell_range,
                        'values': [[final_amount]]  # Send raw number, not formatted string
                    })
                    
                    logging.info(f"Queued: {sheet_name} cell ({row},{col}) = {final_amount}")
                
                # Execute batch update for this sheet
                if batch_data:
                    try:
                        # Use the correct gspread batch_update format with USER_ENTERED to preserve formatting
                        # gspread expects a list of dictionaries with 'range' and 'values'
                        result = worksheet.batch_update(batch_data, value_input_option='USER_ENTERED')
                        logging.info(f"✅ Batch update completed for {sheet_name}: {len(batch_data)} cells updated")
                        
                        results['successful_updates'] += len(batch_data)
                        results['sheets_updated'] += 1
                        results['total_cells_updated'] += len(batch_data)
                        
                    except Exception as e:
                        error_msg = f"Error executing batch update for {sheet_name}: {e}"
                        logging.error(error_msg)
                        results['errors'].append(error_msg)
                        results['failed_updates'] += len(batch_data)
                        
                        # Fallback to individual updates
                        logging.info(f"Attempting individual updates for {sheet_name}...")
                        individual_success = 0
                        for update_data in batch_data:
                            try:
                                range_name = update_data['range']
                                values = update_data['values']
                                worksheet.update(range_name, values, value_input_option='USER_ENTERED')
                                individual_success += 1
                                logging.info(f"Individual update: {range_name} = {values}")
                            except Exception as fallback_error:
                                logging.error(f"Fallback update failed for {range_name}: {fallback_error}")
                        
                        results['successful_updates'] += individual_success
                        results['failed_updates'] -= individual_success
                        results['total_cells_updated'] += individual_success
                        
                        if individual_success > 0:
                            results['sheets_updated'] += 1
                else:
                    logging.warning(f"No batch data to update for sheet '{sheet_name}'")
            
            logging.info(f"All batch updates completed. Results: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in batch update: {e}"
            logging.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def log_failed_transaction(self, transaction: Dict, error_message: str, cell_info: Dict = None):
        """Log a failed transaction for later retry."""
        failed_entry = {
            'transaction': transaction,
            'error_message': error_message,
            'cell_info': cell_info,
            'timestamp': datetime.now().isoformat(),
            'retry_count': 0
        }
        
        self.failed_transactions.append(failed_entry)
        
        # Save to file
        try:
            with open(self.failed_transactions_file, 'w') as f:
                json.dump(self.failed_transactions, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving failed transactions: {e}")
        
        logging.warning(f"Failed transaction logged: {error_message}")
    
    def retry_failed_cells(self, max_retries: int = 3, retry_delay: int = 5) -> Dict:
        """Retry failed cell updates using batch operations."""
        logging.info(f"Retrying {len(self.failed_transactions)} failed transactions using batch updates")
        
        successful_retries = 0
        failed_retries = 0
        
        # Group failed transactions by sheet for batch processing
        sheet_groups = {}
        
        for failed_entry in self.failed_transactions[:]:  # Copy list to avoid modification during iteration
            if failed_entry['retry_count'] >= max_retries:
                logging.warning(f"Transaction {failed_entry['transaction'].get('transaction_id', 'unknown')} "
                              f"exceeded max retries")
                failed_retries += 1
                continue
            
            # Increment retry count
            failed_entry['retry_count'] += 1
            
            # Add to batch group
            if 'cell_info' in failed_entry and failed_entry['cell_info']:
                sheet_name = failed_entry['cell_info']['sheet']
                row = failed_entry['cell_info']['row']
                col = failed_entry['cell_info']['col']
                amount = failed_entry['transaction']['amount']
                
                if sheet_name not in sheet_groups:
                    sheet_groups[sheet_name] = {}
                
                cell_key = f"{row}_{col}"
                if cell_key in sheet_groups[sheet_name]:
                    # Accumulate amounts for same cell
                    sheet_groups[sheet_name][cell_key]['amount'] += amount
                else:
                    sheet_groups[sheet_name][cell_key] = {
                        'row': row,
                        'col': col,
                        'amount': amount,
                        'failed_entries': [failed_entry]
                    }
            else:
                # No cell info available
                failed_retries += 1
        
        # Wait before retry
        time.sleep(retry_delay)
        
        # Execute batch retry
        if sheet_groups:
            try:
                update_results = self.batch_update_sheets_by_tab(sheet_groups)
                
                if update_results.get('successful_updates', 0) > 0:
                    # Remove successful transactions from failed list
                    for sheet_name, cell_updates in sheet_groups.items():
                        for cell_key, cell_data in cell_updates.items():
                            if 'failed_entries' in cell_data:
                                for failed_entry in cell_data['failed_entries']:
                                    if failed_entry in self.failed_transactions:
                                        self.failed_transactions.remove(failed_entry)
                                        successful_retries += 1
                                        logging.info(f"✅ Batch retry successful for transaction {failed_entry['transaction'].get('transaction_id', 'unknown')}")
                
                failed_retries += update_results.get('failed_updates', 0)
                
            except Exception as e:
                logging.error(f"Error during batch retry: {e}")
                failed_retries += len(self.failed_transactions)
        
        # Save updated failed transactions
        try:
            with open(self.failed_transactions_file, 'w') as f:
                json.dump(self.failed_transactions, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving updated failed transactions: {e}")
        
        return {
            'successful_retries': successful_retries,
            'failed_retries': failed_retries,
            'remaining_failed': len(self.failed_transactions)
        }
    
    def generate_failure_report(self) -> Dict:
        """Generate a report of failed transactions."""
        if not self.failed_transactions:
            return {'status': 'no_failures', 'message': 'No failed transactions to report'}
        
        # Group failures by error type
        error_groups = {}
        for failed_entry in self.failed_transactions:
            error_type = failed_entry['error_message']
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(failed_entry)
        
        # Calculate statistics
        total_failures = len(self.failed_transactions)
        avg_retry_count = sum(f['retry_count'] for f in self.failed_transactions) / total_failures
        
        report = {
            'total_failures': total_failures,
            'error_types': len(error_groups),
            'average_retry_count': avg_retry_count,
            'error_breakdown': {},
            'recent_failures': []
        }
        
        # Add error breakdown
        for error_type, failures in error_groups.items():
            report['error_breakdown'][error_type] = {
                'count': len(failures),
                'percentage': (len(failures) / total_failures) * 100
            }
        
        # Add recent failures (last 10)
        recent_failures = sorted(self.failed_transactions, 
                               key=lambda x: x['timestamp'], 
                               reverse=True)[:10]
        
        for failure in recent_failures:
            report['recent_failures'].append({
                'transaction_id': failure['transaction'].get('transaction_id', 'unknown'),
                'error': failure['error_message'],
                'retry_count': failure['retry_count'],
                'timestamp': failure['timestamp']
            })
        
        return report
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float."""
        try:
            if not amount_str:
                return 0.0
            
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
            
            # Handle plain numbers (with or without commas)
            else:
                number_str = amount_str.replace(',', '')
                return float(number_str)
            
        except Exception as e:
            logging.warning(f"Error parsing amount '{amount_str}': {e}")
            return 0.0
    
    def _format_amount(self, amount: float) -> str:
        """Format amount to Google Sheets currency format."""
        try:
            if amount == 0:
                return "$ -"
            elif amount < 0:
                return f"$ ({abs(amount):.2f})"
            else:
                return f"${amount:,.2f}"
        except Exception as e:
            logging.error(f"Error formatting amount {amount}: {e}")
            return str(amount)
    
    def test_connection(self) -> bool:
        """Test Google Sheets connection."""
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            sheets = spreadsheet.worksheets()
            logging.info(f"✅ Google Sheets connection successful. Found {len(sheets)} sheets.")
            return True
        except Exception as e:
            logging.error(f"❌ Google Sheets connection failed: {e}")
            return False

    def calculate_target_coordinates_in_memory(self, target_sheet: str, target_header: str, date_str: str) -> Optional[Dict]:
        """Calculate target cell coordinates in memory using layout mapper and rules."""
        try:
            # Get layout map for the target sheet
            layout_map = self.get_layout_map()
            if target_sheet not in layout_map:
                logging.warning(f"Sheet '{target_sheet}' not found in layout map")
                return None
            
            sheet_layout = layout_map[target_sheet]
            
            # Check if this is the new format (with headers and dates)
            if isinstance(sheet_layout, dict) and 'headers' in sheet_layout and 'dates' in sheet_layout:
                # New format
                headers = sheet_layout.get('headers', {})
                dates = sheet_layout.get('dates', {})
                
                # Find target header column
                target_col = None
                for col_name, col_number in headers.items():
                    if col_name.upper() == target_header.upper():
                        target_col = col_number
                        break
                
                if not target_col:
                    logging.warning(f"Header '{target_header}' not found in sheet '{target_sheet}'")
                    return None
                
                # Find target row using date
                target_row = dates.get(date_str)
                if not target_row:
                    logging.warning(f"Date '{date_str}' not found in sheet '{target_sheet}'")
                    return None
                
                return {
                    'sheet': target_sheet,
                    'row': target_row,
                    'col': target_col,
                    'header': target_header
                }
            
            else:
                # Old format - fallback to API method
                logging.warning(f"Using fallback API method for sheet '{target_sheet}' (old format)")
                return self.find_target_cell_coordinates(target_sheet, target_header, date_str)
            
        except Exception as e:
            logging.error(f"Error calculating coordinates in memory: {e}")
            return None
    
    def batch_calculate_coordinates_in_memory(self, coordinate_requests: List[Dict]) -> Dict[str, Optional[Dict]]:
        """Calculate target cell coordinates for multiple transactions in memory."""
        results = {}
        
        try:
            logging.info(f"Calculating coordinates in memory for {len(coordinate_requests)} transactions...")
            
            for request in coordinate_requests:
                request_key = f"{request['target_sheet']}_{request['target_header']}_{request['date']}"
                
                coords = self.calculate_target_coordinates_in_memory(
                    request['target_sheet'],
                    request['target_header'],
                    request['date']
                )
                
                results[request_key] = coords
                
                if coords:
                    logging.debug(f"✅ Calculated: {request_key} -> Row {coords['row']}, Col {coords['col']}")
                else:
                    logging.debug(f"❌ Not found: {request_key}")
            
            successful_calculations = len([r for r in results.values() if r])
            logging.info(f"✅ Calculated coordinates for {successful_calculations}/{len(coordinate_requests)} transactions")
            
            return results
            
        except Exception as e:
            logging.error(f"Error in batch coordinate calculation: {e}")
            # Return None for all requests on error
            for request in coordinate_requests:
                request_key = f"{request['target_sheet']}_{request['target_header']}_{request['date']}"
                results[request_key] = None
            return results

def main():
    """Test Google Sheets integration."""
    print("GOOGLE SHEETS INTEGRATION TEST")
    print("=" * 60)
    
    integration = GoogleSheetsIntegration()
    
    # Test connection
    if integration.test_connection():
        print("✅ Connection successful")
        
        # Create layout map
        print(f"\n🗺️ Creating layout map...")
        layout_map = integration.create_layout_map()
        
        if layout_map:
            print(f"✅ Layout map created with {len(layout_map)} sheets")
            
            # Test cell coordinate finding
            print(f"\n📍 Testing cell coordinate finding...")
            test_coords = integration.find_target_cell_coordinates("Test Sheet", "Test Header", "12/15/23")
            if test_coords:
                print(f"✅ Found coordinates: {test_coords}")
            else:
                print("⚠️ No coordinates found (expected for test data)")
        
        else:
            print("❌ Failed to create layout map")
    
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    main() 