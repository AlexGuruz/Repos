#!/usr/bin/env python3
"""
Dynamic Columns Script for JGDTRUTH
Reads headers and dates from Google Sheets dynamically to map columns
This script helps maintain dynamic column mapping for JGDTRUTH sheets

Author: ScriptHub AI Assistant
Date: 2025-01-XX
"""

import gspread
import logging
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import Optional

# Configuration
CONFIG = {
    'credentials_file': 'config/service_account.json',
    'financials_spreadsheet_url': '1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU',
    'sheets_to_skip': [
        'PETTY CASH', 
        'Petty Cash KEY', 
        'EXPANSION CHECKLIST', 
        'Balance and Misc', 
        'SHIFT LOG', 
        'TIM', 
        'Copy of TIM', 
        'Info'
    ],
    'header_row': 19,  # Row 19 contains headers (0-indexed: 18)
    'data_start_row': 20  # Row 20 is where data starts (0-indexed: 19)
}

class DynamicColumnsMapper:
    """Maps dynamic columns from Google Sheets for JGDTRUTH"""
    
    def __init__(self, credentials_path: str = None, verbose: bool = False):
        """
        Initialize the dynamic columns mapper
        
        Args:
            credentials_path: Path to Google service account credentials
            verbose: Enable detailed logging
        """
        # Use default credentials path if not provided
        if credentials_path is None:
            script_dir = Path(__file__).parent.parent
            credentials_path = script_dir / CONFIG['credentials_file']
        
        self.credentials_path = str(credentials_path)
        self.verbose = verbose
        
        # Setup logging
        self.setup_logging()
        
        # Initialize Google Sheets client
        self.initialize_client()
        
        self.layout_map = {}
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        # Create logs directory
        script_dir = Path(__file__).parent.parent
        logs_dir = script_dir / 'logs'
        logs_dir.mkdir(exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(logs_dir / f'dynamic_columns_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def initialize_client(self):
        """Initialize Google Sheets client with service account credentials"""
        try:
            self.logger.info(f"Initializing Google Sheets client with credentials: {self.credentials_path}")
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scope)
            self.gc = gspread.authorize(creds)
            self.logger.info("Successfully initialized Google Sheets client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            sys.exit(1)
    
    def create_layout_map(self):
        """
        Connects to Google Sheets to read the layout (headers and dates) of all target sheets.
        Saves this layout to a local JSON file for fast, offline processing.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info("CREATING/UPDATING LAYOUT MAP FROM LIVE GOOGLE SHEETS")
        self.logger.info("=" * 60)
        
        try:
            spreadsheet = self.gc.open_by_key(CONFIG['financials_spreadsheet_url'])
            layout_map = {}
            
            sheets_to_skip = CONFIG['sheets_to_skip']

            for worksheet in spreadsheet.worksheets():
                sheet_title = worksheet.title
                if sheet_title in sheets_to_skip:
                    self.logger.debug(f"Skipping sheet: {sheet_title}")
                    continue

                self.logger.info(f"Mapping layout for sheet: {sheet_title}")
                
                # Get all values to minimize API calls
                all_values = worksheet.get_all_values()
                
                # Map headers (from row 19) to column numbers
                headers = {}
                header_row_index = CONFIG['header_row'] - 1  # Convert to 0-based index
                if len(all_values) >= CONFIG['header_row']:
                    header_row = all_values[header_row_index]
                    for i, header in enumerate(header_row):
                        if header and str(header).strip():
                            headers[str(header).strip()] = i + 1  # 1-based column index
                            if self.verbose:
                                self.logger.debug(f"  Found header '{header}' at column {i + 1}")
                
                # Map dates (from column A) to row numbers
                dates = {}
                data_start_index = CONFIG['data_start_row'] - 1  # Convert to 0-based index
                for i, row in enumerate(all_values[data_start_index:]):
                    if row and row[0]:  # Check if row and first cell exist
                        # Normalize date string for consistent matching
                        try:
                            date_obj = pd.to_datetime(row[0]).strftime('%m/%d/%y')
                            dates[date_obj] = i + CONFIG['data_start_row']  # 1-based row index
                            if self.verbose:
                                self.logger.debug(f"  Found date '{date_obj}' at row {i + CONFIG['data_start_row']}")
                        except Exception:
                            continue  # Skip non-date values

                layout_map[sheet_title] = {
                    'headers': headers, 
                    'dates': dates,
                    'header_count': len(headers),
                    'date_count': len(dates)
                }
                
                self.logger.info(f"  Mapped {len(headers)} headers and {len(dates)} dates for '{sheet_title}'")

            self.layout_map = layout_map
            
            # Save the map locally
            script_dir = Path(__file__).parent.parent
            config_dir = script_dir / 'config'
            config_dir.mkdir(exist_ok=True)
            
            layout_file = config_dir / 'layout_map.json'
            with open(layout_file, 'w') as f:
                json.dump(self.layout_map, f, indent=2)
            
            self.logger.info(f"Successfully created layout map for {len(layout_map)} sheets.")
            self.logger.info(f"Layout map saved to: {layout_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create layout map from Google Sheets: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def get_column_for_header(self, sheet_name: str, header_name: str) -> Optional[int]:
        """
        Get the column number for a specific header in a sheet
        
        Args:
            sheet_name: Name of the sheet
            header_name: Name of the header to find
            
        Returns:
            int: Column number (1-based) or None if not found
        """
        if not self.layout_map:
            self.logger.warning("Layout map not loaded. Creating it now...")
            self.create_layout_map()
        
        sheet_data = self.layout_map.get(sheet_name)
        if not sheet_data:
            self.logger.warning(f"Sheet '{sheet_name}' not found in layout map")
            return None
        
        headers = sheet_data.get('headers', {})
        # Try exact match first
        if header_name in headers:
            return headers[header_name]
        
        # Try case-insensitive match
        header_name_lower = header_name.lower().strip()
        for header, col in headers.items():
            if header.lower().strip() == header_name_lower:
                return col
        
        self.logger.warning(f"Header '{header_name}' not found in sheet '{sheet_name}'")
        return None
    
    def get_row_for_date(self, sheet_name: str, date_str: str) -> Optional[int]:
        """
        Get the row number for a specific date in a sheet
        
        Args:
            sheet_name: Name of the sheet
            date_str: Date string in format 'MM/DD/YY'
            
        Returns:
            int: Row number (1-based) or None if not found
        """
        if not self.layout_map:
            self.logger.warning("Layout map not loaded. Creating it now...")
            self.create_layout_map()
        
        sheet_data = self.layout_map.get(sheet_name)
        if not sheet_data:
            self.logger.warning(f"Sheet '{sheet_name}' not found in layout map")
            return None
        
        dates = sheet_data.get('dates', {})
        return dates.get(date_str)
    
    def print_summary(self):
        """Print a summary of the layout map"""
        if not self.layout_map:
            self.logger.warning("No layout map to summarize")
            return
        
        print("\n" + "=" * 60)
        print("LAYOUT MAP SUMMARY")
        print("=" * 60)
        
        for sheet_name, sheet_data in self.layout_map.items():
            print(f"\nSheet: {sheet_name}")
            print(f"  Headers: {sheet_data.get('header_count', 0)}")
            print(f"  Dates: {sheet_data.get('date_count', 0)}")
            
            if self.verbose:
                print("  Sample headers:")
                headers = sheet_data.get('headers', {})
                for i, (header, col) in enumerate(list(headers.items())[:5]):
                    print(f"    - {header} (Column {col})")
                if len(headers) > 5:
                    print(f"    ... and {len(headers) - 5} more")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create dynamic column mapping for JGDTRUTH sheets')
    script_dir = Path(__file__).parent.parent
    default_creds = script_dir / 'config' / 'service_account.json'
    
    parser.add_argument('--credentials', '-c', default=str(default_creds),
                       help='Path to Google service account credentials file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--summary', '-s', action='store_true',
                       help='Print summary of layout map')
    
    args = parser.parse_args()
    
    try:
        # Initialize mapper
        mapper = DynamicColumnsMapper(
            credentials_path=args.credentials,
            verbose=args.verbose
        )
        
        # Create layout map
        success = mapper.create_layout_map()
        
        if success:
            print("\n[SUCCESS] Successfully created layout map!")
            if args.summary:
                mapper.print_summary()
            return 0
        else:
            print("\n[ERROR] Failed to create layout map")
            return 1
        
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

