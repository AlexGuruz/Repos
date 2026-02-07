#!/usr/bin/env python3
"""
Google Sheets Manager for Petty Cash Sorter
Handles all Google Sheets operations including layout mapping and batch updates
"""

import gspread
import logging
import json
import csv
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional, Tuple

class GoogleSheetsManager:
    """Manages all Google Sheets operations including layout mapping and batch updates."""
    
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
        self.layout_map_file = "config/layout_map_cache.json"
        
        # Create directories
        Path("config").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/google_sheets_manager.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING GOOGLE SHEETS MANAGER")
        logging.info("=" * 60)
        
        # Load layout map cache
        self.load_layout_map_cache()
    
    def create_layout_map(self) -> Dict:
        """Create/update layout map from live Google Sheets."""
        logging.info("CREATING/UPDATING LAYOUT MAP FROM LIVE GOOGLE SHEETS")
        logging.info("=" * 60)
        
        try:
            # Open the live Google spreadsheet
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            layout_map = {}
            
            # Define sheets to skip
            sheets_to_skip = ['PETTY CASH', 'Petty Cash KEY', 'EXPANSION CHECKLIST', 'Balance and Misc', 'SHIFT LOG', 'TIM', 'Copy of TIM', 'Info']
            
            for worksheet in spreadsheet.worksheets():
                sheet_name = worksheet.title
                
                if sheet_name in sheets_to_skip:
                    logging.debug(f"Skipping sheet: {sheet_name}")
                    continue
                
                logging.info(f"Processing sheet: {sheet_name}")
                sheet_map = {}
                
                try:
                    # Get all values from the worksheet
                    all_values = worksheet.get_all_values()
                    
                    if not all_values:
                        logging.warning(f"Sheet {sheet_name} is empty")
                        continue
                    
                    # Find headers (usually in first few rows)
                    header_row = None
                    for row_idx, row in enumerate(all_values[:10]):  # Check first 10 rows
                        if any('date' in str(cell).lower() for cell in row):
                            header_row = row_idx
                            break
                    
                    if header_row is None:
                        logging.warning(f"No date header found in sheet {sheet_name}")
                        continue
                    
                    headers = all_values[header_row]
                    logging.info(f"Found headers in row {header_row + 1}: {headers}")
                    
                    # Map each header to its column index
                    for col_idx, header in enumerate(headers):
                        if header and str(header).strip():
                            header_clean = str(header).strip()
                            sheet_map[header_clean] = {
                                'row': header_row + 1,  # 1-based row
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
            
            logging.info(f"Layout map created successfully with {len(layout_map)} sheets")
            return layout_map
            
        except Exception as e:
            logging.error(f"Error creating layout map: {e}")
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
            
            # Get values starting from header row
            all_values = worksheet.get_all_values()
            if len(all_values) <= header_row:
                return None
            
            # Look for the month/year in the first column (date column)
            for row_idx in range(header_row, len(all_values)):
                row = all_values[row_idx]
                if row and len(row) > 0:
                    first_cell = str(row[0]).strip()
                    
                    # Check if this cell contains the month/year
                    if str(month) in first_cell and str(year) in first_cell:
                        return row_idx + 1  # Convert to 1-based
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding date row: {e}")
            return None
    
    def batch_update_sheets(self, sheet_groups: Dict) -> bool:
        """Update sheets with batch operations."""
        logging.info("EXECUTING BATCH UPDATES")
        
        failed_transactions = []
        
        try:
            spreadsheet = self.gc.open_by_url(self.petty_cash_url)
            
            for sheet_name, cell_updates in sheet_groups.items():
                logging.info(f"Processing batch update for {sheet_name} with {len(cell_updates)} target cells")
                
                # Get worksheet
                worksheet = None
                for ws in spreadsheet.worksheets():
                    if ws.title == sheet_name:
                        worksheet = ws
                        break
                
                if not worksheet:
                    logging.error(f"Target sheet '{sheet_name}' not found")
                    continue
                
                # Prepare batch update data
                batch_data = []
                
                for cell_key, cell_data in cell_updates.items():
                    row = cell_data['row']
                    col = cell_data['col']
                    new_amount = cell_data['amount']
                    
                    # Get current value from target cell
                    try:
                        current_cell = worksheet.cell(row, col)
                        current_value = current_cell.value
                        current_amount = self._parse_amount(current_value)
                        
                        # Add new amount to current
                        final_amount = current_amount + new_amount
                        
                    except Exception as e:
                        logging.warning(f"Error reading current value for {sheet_name} cell ({row},{col}): {e}")
                        final_amount = new_amount
                    
                    # Format final amount
                    formatted_amount = self._format_amount(final_amount)
                    
                    # Add to batch update
                    batch_data.append({
                        'range': f"{sheet_name}!{chr(64+col)}{row}",
                        'values': [[formatted_amount]]
                    })
                    
                    logging.info(f"Queued: {sheet_name} cell ({row},{col}) = {formatted_amount}")
                
                # Execute batch update
                if batch_data:
                    try:
                        # Use batchUpdate for true batch processing
                        body = {
                            'valueInputOption': 'USER_ENTERED',
                            'data': batch_data
                        }
                        
                        result = spreadsheet.batch_update(body)
                        logging.info(f"Batch update completed for {sheet_name}: {len(batch_data)} cells updated")
                        
                    except Exception as e:
                        logging.error(f"Error executing batch update for {sheet_name}: {e}")
                        continue
            
            logging.info("All batch updates completed")
            return True
            
        except Exception as e:
            logging.error(f"Error in batch update: {e}")
            return False
    
    def update_single_cell(self, sheet_name: str, row: int, col: int, new_amount: float) -> bool:
        """Update a single cell in Google Sheets."""
        try:
            spreadsheet = self.gc.open_by_url(self.petty_cash_url)
            worksheet = None
            
            for ws in spreadsheet.worksheets():
                if ws.title == sheet_name:
                    worksheet = ws
                    break
            
            if not worksheet:
                logging.error(f"Target sheet '{sheet_name}' not found")
                return False
            
            # Get current value
            current_cell = worksheet.cell(row, col)
            current_value = current_cell.value
            current_amount = self._parse_amount(current_value)
            
            # Add new amount
            final_amount = current_amount + new_amount
            formatted_amount = self._format_amount(final_amount)
            
            # Update cell
            worksheet.update_cell(row, col, formatted_amount)
            
            logging.info(f"Updated {sheet_name} cell ({row},{col}) = {formatted_amount}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating single cell: {e}")
            return False
    
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
            
            # Handle plain numbers
            else:
                return float(amount_str)
            
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
    
    def get_sheet_names(self) -> List[str]:
        """Get all sheet names from the spreadsheet."""
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            return [ws.title for ws in spreadsheet.worksheets()]
        except Exception as e:
            logging.error(f"Error getting sheet names: {e}")
            return []
    
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

def main():
    """Test Google Sheets manager."""
    print("GOOGLE SHEETS MANAGER TEST")
    print("=" * 60)
    
    manager = GoogleSheetsManager()
    
    # Test connection
    if manager.test_connection():
        print("✅ Connection successful")
        
        # Get sheet names
        sheets = manager.get_sheet_names()
        print(f"📋 Found {len(sheets)} sheets:")
        for sheet in sheets[:5]:  # Show first 5
            print(f"  - {sheet}")
        
        # Create layout map
        print(f"\n🗺️ Creating layout map...")
        layout_map = manager.create_layout_map()
        
        if layout_map:
            print(f"✅ Layout map created with {len(layout_map)} sheets")
            
            # Show sample mappings
            for sheet_name, sheet_map in list(layout_map.items())[:3]:
                print(f"\n📊 Sheet: {sheet_name}")
                for header, info in list(sheet_map.items())[:3]:
                    print(f"  {header} → Row {info['row']}, Col {info['col']}")
        
        else:
            print("❌ Failed to create layout map")
    
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    main() 