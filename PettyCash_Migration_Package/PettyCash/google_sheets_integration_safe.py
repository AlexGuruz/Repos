#!/usr/bin/env python3
"""
Safe Google Sheets Integration Module
Handles layout mapping, batch updates, and cell coordinate finding
WITH COMPENSATION TO PREVENT ACCUMULATION
"""

import gspread
import logging
import json
import time
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional, Tuple

class SafeGoogleSheetsIntegration:
    """Handles all Google Sheets operations with compensation to prevent accumulation."""
    
    def __init__(self):
        # Google Sheets setup
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_file('config/service_account.json', scopes=self.scope)
        self.gc = gspread.authorize(self.creds)
        
        # Spreadsheet URLs
        self.petty_cash_url = "https://docs.google.com/spreadsheets/d/1koQmnvfkSpCkKMX_9cc1EnN0z0NPn4x-GTOic3wqmEc"
        self.financials_spreadsheet_url = "https://docs.google.com/spreadsheets/d/1koQmnvfkSpCkKMX_9cc1EnN0z0NPn4x-GTOic3wqmEc"
        
        # Layout map cache for fast cell coordinate lookups
        self.layout_map_cache = {}
        self.layout_map_file = "config/layout_map.json"
        
        # Compensation data for safe updates
        self.compensation_data = {}
        self.compensation_file = "config/compensation_data.json"
        
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
                logging.FileHandler('logs/safe_google_sheets_integration.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING SAFE GOOGLE SHEETS INTEGRATION")
        logging.info("=" * 60)
        
        # Load layout map cache
        self.load_layout_map_cache()
        
        # Load compensation data
        self.load_compensation_data()
    
    def load_compensation_data(self):
        """Load compensation data to prevent accumulation."""
        try:
            if Path(self.compensation_file).exists():
                with open(self.compensation_file, 'r') as f:
                    self.compensation_data = json.load(f)
                logging.info(f"✅ Loaded compensation data: {len(self.compensation_data)} sheets")
            else:
                logging.warning("⚠️  No compensation data found - will use current values as baseline")
                self.compensation_data = {}
        except Exception as e:
            logging.error(f"❌ Error loading compensation data: {e}")
            self.compensation_data = {}
    
    def get_compensation_value(self, sheet_name: str, header: str, row: int) -> float:
        """Get the compensation value for a specific cell."""
        try:
            if sheet_name in self.compensation_data:
                if header in self.compensation_data[sheet_name]:
                    for comp_item in self.compensation_data[sheet_name][header]:
                        if comp_item['row'] == row:
                            return comp_item['value']
            return 0.0
        except Exception as e:
            logging.warning(f"Error getting compensation value for {sheet_name}/{header}/{row}: {e}")
            return 0.0
    
    def batch_update_sheets_by_tab_safe(self, sheet_groups: Dict) -> Dict:
        """Update sheets with batch operations using compensation to prevent accumulation."""
        logging.info("EXECUTING SAFE BATCH UPDATES BY TAB")
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
                logging.info(f"Processing safe batch update for sheet '{sheet_name}' with {len(cell_updates)} target cells")
                
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
                
                # Process each cell update with compensation
                for cell_key, cell_data in cell_updates.items():
                    row = cell_data['row']
                    col = cell_data['col']
                    new_amount = cell_data['amount']
                    header = cell_data.get('header', '')  # Get header for compensation lookup
                    
                    # Get current value from batch read data
                    current_value = current_values.get((row, col), 0)
                    current_amount = self._parse_amount(current_value)
                    
                    # Get compensation value (what was there before our previous runs)
                    compensation_amount = self.get_compensation_value(sheet_name, header, row)
                    
                    # Calculate final amount: current - compensation + new
                    # This ensures we don't accumulate values from multiple runs
                    final_amount = current_amount - compensation_amount + new_amount
                    
                    # Send raw numeric value to Google Sheets
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
                    
                    logging.info(f"Safe update: {sheet_name} cell ({row},{col}) = {final_amount} (current: {current_amount}, compensation: {compensation_amount}, new: {new_amount})")
                
                # Execute batch update for this sheet
                if batch_data:
                    try:
                        # Use the correct gspread batch_update format with USER_ENTERED to preserve formatting
                        result = worksheet.batch_update(batch_data, value_input_option='USER_ENTERED')
                        logging.info(f"✅ Safe batch update completed for {sheet_name}: {len(batch_data)} cells updated")
                        
                        results['successful_updates'] += len(batch_data)
                        results['sheets_updated'] += 1
                        results['total_cells_updated'] += len(batch_data)
                        
                    except Exception as e:
                        error_msg = f"Error executing safe batch update for {sheet_name}: {e}"
                        logging.error(error_msg)
                        results['errors'].append(error_msg)
                        results['failed_updates'] += len(batch_data)
                        
                        # Fallback to individual updates
                        logging.info(f"Attempting individual safe updates for {sheet_name}...")
                        individual_success = 0
                        for update_data in batch_data:
                            try:
                                range_name = update_data['range']
                                values = update_data['values']
                                worksheet.update(range_name, values, value_input_option='USER_ENTERED')
                                individual_success += 1
                                logging.info(f"Individual safe update: {range_name} = {values}")
                            except Exception as fallback_error:
                                logging.error(f"Fallback safe update failed for {range_name}: {fallback_error}")
                        
                        results['successful_updates'] += individual_success
                        results['failed_updates'] -= individual_success
                        results['total_cells_updated'] += individual_success
                        
                        if individual_success > 0:
                            results['sheets_updated'] += 1
                else:
                    logging.warning(f"No batch data to update for sheet '{sheet_name}'")
            
            logging.info(f"All safe batch updates completed. Results: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in safe batch update: {e}"
            logging.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float, handling various formats."""
        if not amount_str:
            return 0.0
        
        try:
            # Remove common currency symbols and formatting
            cleaned = str(amount_str).replace('$', '').replace(',', '').replace(' ', '')
            
            # Handle negative amounts in parentheses
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = '-' + cleaned[1:-1]
            
            return float(cleaned)
        except (ValueError, TypeError):
            logging.warning(f"Could not parse amount: {amount_str}")
            return 0.0
    
    def load_layout_map_cache(self):
        """Load layout map from cache file."""
        try:
            if Path(self.layout_map_file).exists():
                with open(self.layout_map_file, 'r') as f:
                    self.layout_map_cache = json.load(f)
                logging.info(f"✅ Layout map cache loaded: {len(self.layout_map_cache)} sheets")
            else:
                logging.warning("⚠️  No layout map cache found")
                self.layout_map_cache = {}
        except Exception as e:
            logging.error(f"❌ Error loading layout map cache: {e}")
            self.layout_map_cache = {}
    
    def get_layout_map(self) -> Dict:
        """Get the current layout map."""
        return self.layout_map_cache
    
    def test_connection(self) -> bool:
        """Test Google Sheets connection."""
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            logging.info(f"✅ Connected to spreadsheet: {spreadsheet.title}")
            return True
        except Exception as e:
            logging.error(f"❌ Connection test failed: {e}")
            return False

def main():
    """Test the safe Google Sheets integration."""
    integration = SafeGoogleSheetsIntegration()
    
    if integration.test_connection():
        print("✅ Safe Google Sheets integration test successful")
    else:
        print("❌ Safe Google Sheets integration test failed")

if __name__ == "__main__":
    main() 