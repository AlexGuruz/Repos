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
import os
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from src.gsheets import ensure_id, load_cfg

# Configuration
CONFIG = {
    'credentials_file': 'config/service_account.json',
    # Legacy fallback (only used if year_workbooks/instances are unavailable)
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
    
    def __init__(self, credentials_path: str = None, verbose: bool = False, years: Optional[List[str]] = None):
        """
        Initialize the dynamic columns mapper
        
        Args:
            credentials_path: Path to Google service account credentials
            verbose: Enable detailed logging
        """
        # Use default credentials path if not provided
        if credentials_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            cfg_path = repo_root / "tools" / "scripthub_legacy" / "config.json"
            if cfg_path.exists():
                try:
                    cfg = load_cfg(str(cfg_path))
                    svc_path = cfg.get("service_account")
                    if svc_path:
                        credentials_path = (repo_root / svc_path) if not os.path.isabs(svc_path) else Path(svc_path)
                except Exception:
                    credentials_path = None
            if not credentials_path:
                credentials_path = repo_root / "scripts" / "config" / "service_account.json"
        
        self.credentials_path = str(credentials_path)
        self.verbose = verbose
        self.years = years or []
        
        # Setup logging
        self.setup_logging()
        
        # Initialize Google Sheets client
        self.initialize_client()
        
        self.layout_map = {}

    def _load_enabled_years(self) -> List[str]:
        """Load enabled years from config/instances/index.yaml."""
        if yaml is None:
            self.logger.warning("PyYAML not installed; cannot load instances/index.yaml")
            return []
        idx_path = Path(__file__).resolve().parents[2] / "config" / "instances" / "index.yaml"
        if not idx_path.exists():
            return []
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.warning(f"Failed to read {idx_path}: {e}")
            return []
        items = data.get("instances") or []
        years: List[str] = []
        for it in items:
            if isinstance(it, dict) and it.get("enabled", True):
                raw_years = str(it.get("years", "")).strip()
                for part in raw_years.replace(";", ",").split(","):
                    y = part.strip()
                    if y:
                        years.append(y)
        return sorted(set(years))

    def _resolve_workbooks(self, years: List[str]) -> List[Tuple[str, str]]:
        """Resolve year -> workbook URL using config/global.yaml."""
        if not years:
            years = self._load_enabled_years()
        if not years:
            return []
        try:
            from services.common.config_loader import load_config  # type: ignore

            cfg = load_config(path=os.environ.get("KYLO_CONFIG_PATH") or os.path.join("config", "global.yaml"))
            year_workbooks = cfg.data.get("year_workbooks", {}) if hasattr(cfg, "data") else {}
        except Exception as e:
            self.logger.warning(f"Failed to load year_workbooks from config/global.yaml: {e}")
            return []
        out: List[Tuple[str, str]] = []
        for year in years:
            wb = year_workbooks.get(str(year), {}) if isinstance(year_workbooks, dict) else {}
            url = (wb or {}).get("output_workbook_url") or (wb or {}).get("intake_workbook_url")
            if url:
                out.append((str(year), str(url)))
        return out
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        # Create logs directory
        script_dir = Path(__file__).parent
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
            workbooks = self._resolve_workbooks(self.years)
            if not workbooks:
                legacy_url = CONFIG.get("financials_spreadsheet_url")
                if not legacy_url:
                    raise RuntimeError("No year workbooks found and no legacy spreadsheet URL configured.")
                workbooks = [("legacy", legacy_url)]

            layout_map: Dict[str, Dict] = {
                "by_year": {},
                "workbooks": {},
                "generated_at": datetime.now().isoformat(),
            }

            sheets_to_skip = CONFIG['sheets_to_skip']

            for year, url in workbooks:
                spreadsheet = self.gc.open_by_key(ensure_id(url))
                layout_map["workbooks"][year] = ensure_id(url)
                year_map: Dict[str, Dict] = {}

                for worksheet in spreadsheet.worksheets():
                    sheet_title = worksheet.title
                    if sheet_title in sheets_to_skip:
                        self.logger.debug(f"Skipping sheet: {sheet_title}")
                        continue

                    self.logger.info(f"[{year}] Mapping layout for sheet: {sheet_title}")

                    # Get all values to minimize API calls
                    all_values = worksheet.get_all_values()

                    # Map headers (from row 19) to column numbers
                    headers: Dict[str, int] = {}
                    header_row_index = CONFIG['header_row'] - 1  # Convert to 0-based index
                    if len(all_values) >= CONFIG['header_row']:
                        header_row = all_values[header_row_index]
                        for i, header in enumerate(header_row):
                            if header and str(header).strip():
                                headers[str(header).strip()] = i + 1  # 1-based column index
                                if self.verbose:
                                    self.logger.debug(f"  Found header '{header}' at column {i + 1}")

                    # Map dates (from column A) to row numbers
                    dates: Dict[str, int] = {}
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

                    year_map[sheet_title] = {
                        'headers': headers,
                        'dates': dates,
                        'header_count': len(headers),
                        'date_count': len(dates)
                    }

                    self.logger.info(f"  Mapped {len(headers)} headers and {len(dates)} dates for '{sheet_title}'")

                layout_map["by_year"][year] = year_map

            self.layout_map = layout_map
            
            # Save the map locally
            script_dir = Path(__file__).parent
            config_dir = script_dir / 'config'
            config_dir.mkdir(exist_ok=True)
            
            layout_file = config_dir / 'layout_map.json'
            with open(layout_file, 'w') as f:
                json.dump(self.layout_map, f, indent=2)
            
            total_sheets = sum(len(v) for v in self.layout_map.get("by_year", {}).values())
            self.logger.info(f"Successfully created layout map for {total_sheets} sheets.")
            self.logger.info(f"Layout map saved to: {layout_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create layout map from Google Sheets: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def _resolve_sheet_data(self, sheet_name: str, year: Optional[str] = None) -> Optional[Dict]:
        if not self.layout_map:
            self.logger.warning("Layout map not loaded. Creating it now...")
            self.create_layout_map()

        if "by_year" in self.layout_map:
            year_key = year
            if not year_key and ":" in sheet_name:
                year_key, sheet_name = sheet_name.split(":", 1)
            if not year_key:
                years = list((self.layout_map.get("by_year") or {}).keys())
                if len(years) == 1:
                    year_key = years[0]
                else:
                    self.logger.warning("Multiple years available; pass year explicitly (or use YEAR:SheetName).")
                    return None
            sheet_data = (self.layout_map.get("by_year") or {}).get(year_key, {}).get(sheet_name)
            if not sheet_data:
                self.logger.warning(f"Sheet '{sheet_name}' not found in layout map for year '{year_key}'")
            return sheet_data

        sheet_data = self.layout_map.get(sheet_name)
        if not sheet_data:
            self.logger.warning(f"Sheet '{sheet_name}' not found in layout map")
        return sheet_data

    def get_column_for_header(self, sheet_name: str, header_name: str, year: Optional[str] = None) -> Optional[int]:
        """
        Get the column number for a specific header in a sheet
        
        Args:
            sheet_name: Name of the sheet
            header_name: Name of the header to find
            
        Returns:
            int: Column number (1-based) or None if not found
        """
        sheet_data = self._resolve_sheet_data(sheet_name, year=year)
        if not sheet_data:
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
    
    def get_row_for_date(self, sheet_name: str, date_str: str, year: Optional[str] = None) -> Optional[int]:
        """
        Get the row number for a specific date in a sheet
        
        Args:
            sheet_name: Name of the sheet
            date_str: Date string in format 'MM/DD/YY'
            
        Returns:
            int: Row number (1-based) or None if not found
        """
        sheet_data = self._resolve_sheet_data(sheet_name, year=year)
        if not sheet_data:
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
        
        if "by_year" in self.layout_map:
            for year, sheets in (self.layout_map.get("by_year") or {}).items():
                print(f"\nYear: {year}")
                for sheet_name, sheet_data in sheets.items():
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
        else:
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
    parser.add_argument('--credentials', '-c', default=None,
                       help='Path to Google service account credentials file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--years', default=None,
                       help='Comma-separated years to target (default: enabled instances)')
    parser.add_argument('--summary', '-s', action='store_true',
                       help='Print summary of layout map')
    
    args = parser.parse_args()
    
    try:
        # Initialize mapper
        years = []
        if args.years:
            years = [y.strip() for y in args.years.replace(";", ",").split(",") if y.strip()]
        mapper = DynamicColumnsMapper(
            credentials_path=args.credentials,
            verbose=args.verbose,
            years=years
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

