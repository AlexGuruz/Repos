#!/usr/bin/env python3
"""
Google Sheets Transaction Sync
Syncs Company ID values from BANK sheet to CLEAN TRANSACTIONS sheet
Based on unique transaction keys

Author: ScriptHub AI Assistant
Date: 2025-09-19
"""

import gspread
import logging
import argparse
import sys
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
from pathlib import Path

# Configuration
CONFIG = {
    'source_sheet': {
        'spreadsheet_id': '10RC11WsFtlgIUEdq3cpOqBs6hVpZOyPCLkjEnfho7Wk',
        'sheet_name': 'BANK',
        'transaction_key_col': 8,  # Column H
        'company_id_col': 2        # Column B
    },
    'target_sheet': {
        'spreadsheet_id': '1ZxzOvP14M7syKuZ3EoqaHJUkZoOEcMpgk5adHP9p2no',
        'sheet_name': 'CLEAN TRANSACTIONS',
        'transaction_key_col': 10, # Column J
        'company_id_col': 2        # Column B
    },
    'credentials_file': 'config/service_account.json'
}

class GoogleSheetsSync:
    """Main class for syncing Company IDs between Google Sheets"""
    
    def __init__(self, credentials_path: str = None, dry_run: bool = False, verbose: bool = False):
        """
        Initialize the sync system
        
        Args:
            credentials_path: Path to Google service account credentials
            dry_run: If True, preview changes without applying them
            verbose: Enable detailed logging
        """
        # Use default credentials path if not provided
        if credentials_path is None:
            script_dir = Path(__file__).parent.parent
            credentials_path = script_dir / CONFIG['credentials_file']
        
        self.credentials_path = str(credentials_path)
        self.dry_run = dry_run
        self.verbose = verbose
        self.client = None
        
        # Setup logging
        self.setup_logging()
        
        # Initialize Google Sheets client
        self.initialize_client()
    
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
                logging.FileHandler(logs_dir / f'sync_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def initialize_client(self):
        """Initialize Google Sheets client with service account credentials"""
        try:
            self.logger.info(f"Initializing Google Sheets client with credentials: {self.credentials_path}")
            self.client = gspread.service_account(filename=self.credentials_path)
            self.logger.info("Successfully initialized Google Sheets client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            sys.exit(1)
    
    def get_state_sheet(self):
        """Get or create the state sheet used to persist key->company_id mapping."""
        source_config = CONFIG['source_sheet']
        spreadsheet = self.client.open_by_key(source_config['spreadsheet_id'])
        state_title = '_KYLO_STATE'
        try:
            return spreadsheet.worksheet(state_title)
        except Exception:
            # Create state worksheet with header
            sheet = spreadsheet.add_worksheet(title=state_title, rows=1000, cols=2)
            sheet.update(range_name='A1:B1', values=[['transaction_key', 'company_id']])
            # Optional: could hide via batch_update if needed
            return sheet
    
    def read_state_mapping(self) -> Dict[str, str]:
        """Read persisted mapping from state sheet."""
        try:
            sheet = self.get_state_sheet()
            values = sheet.get_all_values()
            mapping: Dict[str, str] = {}
            for row in values[1:]:
                if len(row) >= 2:
                    key = (row[0] or '').strip()
                    cid = (row[1] or '').strip()
                    if key:
                        mapping[key] = cid
            return mapping
        except Exception as e:
            self.logger.warning(f"Failed to read state sheet: {str(e)}")
            return {}
    
    def write_state_mapping(self, mapping: Dict[str, str]) -> None:
        """Persist mapping to state sheet, overwriting existing content."""
        try:
            sheet = self.get_state_sheet()
            rows = [['transaction_key', 'company_id']] + [[k, mapping.get(k, '')] for k in mapping.keys()]
            sheet.clear()
            sheet.update(range_name='A1', values=rows)
        except Exception as e:
            self.logger.warning(f"Failed to write state sheet: {str(e)}")
    
    def get_sheet(self, spreadsheet_id: str, sheet_name: str):
        """
        Get a specific sheet from a spreadsheet
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            sheet_name: Name of the sheet within the spreadsheet
            
        Returns:
            gspread.Worksheet: The requested worksheet
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            sheet = spreadsheet.worksheet(sheet_name)
            self.logger.debug(f"Successfully opened sheet '{sheet_name}' from spreadsheet {spreadsheet_id}")
            return sheet
        except Exception as e:
            self.logger.error(f"Failed to open sheet '{sheet_name}': {str(e)}")
            raise
    
    def read_bank_data(self) -> Dict[str, str]:
        """
        Read transaction keys and company IDs from the BANK sheet
        
        Returns:
            Dict mapping transaction_key -> company_id
        """
        self.logger.info("Reading data from BANK sheet...")
        
        source_config = CONFIG['source_sheet']
        bank_sheet = self.get_sheet(source_config['spreadsheet_id'], source_config['sheet_name'])
        
        # Get all values from the sheet
        all_values = bank_sheet.get_all_values()
        
        transaction_map = {}
        skipped_rows = 0
        
        for row_idx, row in enumerate(all_values[1:], start=2):  # Skip header row
            try:
                # Get transaction key (column H, index 7)
                transaction_key = row[source_config['transaction_key_col'] - 1] if len(row) > source_config['transaction_key_col'] - 1 else ""
                
                # Get company ID (column B, index 1)
                company_id = row[source_config['company_id_col'] - 1] if len(row) > source_config['company_id_col'] - 1 else ""
                
                # Skip rows without transaction key
                if not transaction_key.strip():
                    skipped_rows += 1
                    continue
                
                # Store mapping (even if company_id is empty, we want to track the key exists)
                transaction_map[transaction_key.strip()] = company_id.strip()
                
                if self.verbose:
                    self.logger.debug(f"Row {row_idx}: Key='{transaction_key}' -> Company ID='{company_id}'")
                    
            except IndexError as e:
                self.logger.warning(f"Row {row_idx} has insufficient columns: {str(e)}")
                skipped_rows += 1
                continue
        
        self.logger.info(f"Read {len(transaction_map)} transaction mappings from BANK sheet")
        if skipped_rows > 0:
            self.logger.info(f"Skipped {skipped_rows} rows (missing transaction key or insufficient columns)")
        
        return transaction_map
    
    def align_bank_company_ids(self) -> Tuple[int, List[str]]:
        """
        Align BANK sheet Company IDs using a durable previous mapping by transaction key.
        If a previous mapping exists (saved from the last successful run), we reapply
        those Company IDs to the current BANK rows by matching on transaction key.
        This naturally handles any number of new transactions added at the top.
        
        If no previous mapping exists, we make no changes (first baseline run) and
        rely on saving the current BANK mapping for future runs.
        
        Returns:
            Tuple of (updates_made, unmatched_keys)
        """
        self.logger.info("Aligning BANK Company IDs using durable previous mapping (by transaction key)...")
        
        source_config = CONFIG['source_sheet']
        
        # Open sheets
        bank_sheet = self.get_sheet(source_config['spreadsheet_id'], source_config['sheet_name'])
        
        # Read all values
        bank_values = bank_sheet.get_all_values()

        # Load previous durable mapping and keys order from state sheet first; file is fallback
        prev_map: Dict[str, str] = self.read_state_mapping()
        prev_keys: List[str] = list(prev_map.keys())
        if prev_map:
            self.logger.info(f"Loaded previous mapping with {len(prev_map)} entries from state sheet")
        else:
            # Fallback to local file if state sheet is empty
            script_dir = Path(__file__).parent.parent
            state_file = script_dir / 'sync_state.json'
            try:
                if state_file.exists():
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                        if isinstance(state, dict) and 'transaction_map' in state and isinstance(state['transaction_map'], dict):
                            prev_map = {str(k): str(v) for k, v in state['transaction_map'].items() if str(k).strip()}
                        if isinstance(state, dict) and 'keys_order' in state and isinstance(state['keys_order'], list):
                            prev_keys = [str(k) for k in state['keys_order'] if str(k).strip()]
                    if prev_map:
                        self.logger.info(f"Loaded previous mapping with {len(prev_map)} entries from sync_state.json (fallback)")
                    else:
                        self.logger.info("No previous mapping found; skipping alignment (baseline run)")
                else:
                    self.logger.info("No previous mapping found; skipping alignment (baseline run)")
            except Exception:
                self.logger.info("No previous mapping found; skipping alignment (baseline run)")

        # If still no prev_map, nothing to align
        if not prev_map:
            return 0, []
        
        updates_made = 0
        unmatched_keys: List[str] = []
        batch_updates: List[Dict] = []

        # Build current keys order and key -> row index mapping
        current_keys: List[str] = []
        current_key_to_row: Dict[str, int] = {}
        for row_idx, row in enumerate(bank_values[1:], start=2):
            try:
                k = row[source_config['transaction_key_col'] - 1] if len(row) > source_config['transaction_key_col'] - 1 else ""
                if k and k.strip():
                    k = k.strip()
                    current_keys.append(k)
                    # Only set first occurrence to avoid duplicates overriding
                    if k not in current_key_to_row:
                        current_key_to_row[k] = row_idx
            except Exception:
                continue

        # Detect top insertion offset: find prev_keys[0] position in current_keys
        offset = None
        if prev_keys:
            try:
                pos = current_keys.index(prev_keys[0])
                offset = pos
            except ValueError:
                offset = None

        # If offset detected and sequence largely matches, override per-key using prev_map
        def sequences_align_with_offset(prev: List[str], curr: List[str], off: int, sample: int = 50) -> bool:
            if off is None or off < 0:
                return False
            # Check a sample of the sequence to validate alignment
            matches = 0
            limit = min(sample, len(prev), max(0, len(curr) - off))
            for i in range(limit):
                if prev[i] == curr[off + i]:
                    matches += 1
            return matches >= max(5, int(0.8 * limit))

        if offset is not None and sequences_align_with_offset(prev_keys, current_keys, offset):
            self.logger.info(f"Detected {offset} new rows added at top; realigning Company IDs by key")
            # For every previous key, set BANK B at the row of the same key now
            for key in prev_keys:
                desired_cid = prev_map.get(key, "")
                row_idx = current_key_to_row.get(key)
                if row_idx is None:
                    unmatched_keys.append(key)
                    continue
                # Read current cid from bank_values: compute index relative to values list
                try:
                    current_row = bank_values[row_idx - 1]
                    current_cid = current_row[source_config['company_id_col'] - 1] if len(current_row) > source_config['company_id_col'] - 1 else ""
                except Exception:
                    current_cid = ""
                if current_cid != desired_cid:
                    cell_range = f"B{row_idx}"
                    if self.dry_run:
                        self.logger.info(f"[DRY RUN] Would set BANK {cell_range}: '{current_cid}' -> '{desired_cid}' (key={key})")
                    else:
                        batch_updates.append({'range': cell_range, 'values': [[desired_cid]]})
                        self.logger.debug(f"Queued BANK update {cell_range}: '{current_cid}' -> '{desired_cid}' (key={key})")
                    updates_made += 1
        else:
            # Conservative fallback: fill empties only using prev_map
            self.logger.info("No reliable top insertion detected; filling empty Company IDs from previous mapping")
            for row_idx, row in enumerate(bank_values[1:], start=2):
                try:
                    key = row[source_config['transaction_key_col'] - 1] if len(row) > source_config['transaction_key_col'] - 1 else ""
                    current_bank_cid = row[source_config['company_id_col'] - 1] if len(row) > source_config['company_id_col'] - 1 else ""
                    if not key or not key.strip():
                        continue
                    key = key.strip()
                    current_bank_cid = (current_bank_cid or "").strip()
                    desired_cid = prev_map.get(key)
                    if (not current_bank_cid) and desired_cid:
                        cell_range = f"B{row_idx}"
                        if self.dry_run:
                            self.logger.info(f"[DRY RUN] Would set BANK {cell_range}: '' -> '{desired_cid}' (key={key})")
                        else:
                            batch_updates.append({'range': cell_range, 'values': [[desired_cid]]})
                            self.logger.debug(f"Queued BANK update {cell_range}: '' -> '{desired_cid}' (key={key})")
                        updates_made += 1
                except Exception as e:
                    self.logger.warning(f"BANK Row {row_idx} alignment skipped due to error: {str(e)}")
                    continue
        
        # Apply
        if not self.dry_run and batch_updates:
            try:
                self.logger.info(f"Applying {len(batch_updates)} BANK Company ID updates...")
                bank_sheet.batch_update(batch_updates)
                self.logger.info("BANK Company ID alignment applied successfully")
            except Exception as e:
                self.logger.error(f"Failed applying BANK alignment: {str(e)}")
                raise
        
        return updates_made, unmatched_keys
    
    def sync_clean_transactions(self, transaction_map: Dict[str, str]) -> Tuple[int, List[str]]:
        """
        Sync company IDs from properly aligned BANK sheet to CLEAN TRANSACTIONS sheet
        
        Args:
            transaction_map: Dictionary mapping transaction_key -> company_id
            
        Returns:
            Tuple of (updates_made, unmatched_keys)
        """
        self.logger.info("Syncing data to CLEAN TRANSACTIONS sheet...")
        
        target_config = CONFIG['target_sheet']
        clean_sheet = self.get_sheet(target_config['spreadsheet_id'], target_config['sheet_name'])
        
        # Get all values from the sheet
        all_values = clean_sheet.get_all_values()
        
        updates_made = 0
        unmatched_keys = []
        batch_updates = []
        
        # Process each row in the CLEAN TRANSACTIONS sheet (skip header)
        for row_idx, row in enumerate(all_values[1:], start=2):
            try:
                # Get transaction key (column J, index 9)
                transaction_key = row[target_config['transaction_key_col'] - 1] if len(row) > target_config['transaction_key_col'] - 1 else ""
                
                # Get current company ID (column B, index 1)
                current_company_id = row[target_config['company_id_col'] - 1] if len(row) > target_config['company_id_col'] - 1 else ""
                
                # Skip rows without transaction key
                if not transaction_key.strip():
                    continue
                
                transaction_key = transaction_key.strip()
                current_company_id = current_company_id.strip()
                
                # Get the corresponding Company ID from BANK sheet by transaction key
                # Since BANK sheet is now properly aligned, we can match directly by key
                new_company_id = transaction_map.get(transaction_key, "")
                
                # Update ONLY when there's a meaningful Company ID to sync from BANK
                # Never clear existing dropdown values - preserve dropdown functionality
                if current_company_id != new_company_id and new_company_id.strip():
                    cell_address = f"B{row_idx}"
                    
                    if self.dry_run:
                        self.logger.info(f"[DRY RUN] Would update {cell_address}: '{current_company_id}' -> '{new_company_id}'")
                    else:
                        batch_updates.append({
                            'range': cell_address,
                            'values': [[new_company_id]]
                        })
                        self.logger.debug(f"Queued update for {cell_address}: '{current_company_id}' -> '{new_company_id}'")
                    
                    updates_made += 1
                elif transaction_key not in transaction_map:
                    # Track unmatched keys for reporting
                    unmatched_keys.append(transaction_key)
                    if self.verbose:
                        self.logger.debug(f"No match found for transaction key: '{transaction_key}'")
                        
            except IndexError as e:
                self.logger.warning(f"Row {row_idx} has insufficient columns: {str(e)}")
                continue
        
        # Apply batch updates if not in dry run mode
        if not self.dry_run and batch_updates:
            try:
                self.logger.info(f"Applying {len(batch_updates)} updates to CLEAN TRANSACTIONS sheet...")
                clean_sheet.batch_update(batch_updates)
                self.logger.info("Batch update completed successfully")
            except Exception as e:
                self.logger.error(f"Failed to apply batch updates: {str(e)}")
                raise
        
        return updates_made, unmatched_keys
    
    def run_sync(self) -> Dict:
        """
        Run the complete sync process
        
        Returns:
            Dictionary with sync results
        """
        start_time = datetime.now()
        self.logger.info("=" * 50)
        self.logger.info("Starting Google Sheets Transaction Sync")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        self.logger.info("=" * 50)
        
        try:
            # Step 1: Read BANK data
            transaction_map = self.read_bank_data()
            
            # Step 2: Align Company IDs in BANK sheet first
            bank_updates, bank_unmatched = self.align_bank_company_ids()
            
            # Step 3: Re-read BANK data after alignment (if not dry run)
            if not self.dry_run and bank_updates > 0:
                self.logger.info("Re-reading BANK data after alignment...")
                transaction_map = self.read_bank_data()
            
            # Step 4: Sync to CLEAN TRANSACTIONS
            clean_updates, clean_unmatched = self.sync_clean_transactions(transaction_map)
            
            # Step 5: Persist durable mapping (always save BANK mapping as latest baseline)
            # Persist to state sheet and local file for redundancy
            try:
                self.write_state_mapping(transaction_map)
                self.logger.info(f"Saved {len(transaction_map)} BANK mappings to state sheet for future alignment")
            except Exception:
                pass
            try:
                script_dir = Path(__file__).parent.parent
                state_file = script_dir / 'sync_state.json'
                keys_order = list(transaction_map.keys())
                with open(state_file, 'w') as f:
                    json.dump({'transaction_map': transaction_map, 'keys_order': keys_order, 'saved_at': datetime.now().isoformat()}, f)
            except Exception:
                pass
            
            # Combine results
            updates_made = bank_updates + clean_updates
            unmatched_keys = bank_unmatched + clean_unmatched
            
            # Step 3: Generate summary
            end_time = datetime.now()
            duration = end_time - start_time
            
            results = {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'total_bank_records': len(transaction_map),
                'updates_made': updates_made,
                'unmatched_keys_count': len(unmatched_keys),
                'unmatched_keys': unmatched_keys[:10],  # First 10 for brevity
                'dry_run': self.dry_run
            }
            
            self.logger.info("=" * 50)
            self.logger.info("SYNC COMPLETED")
            self.logger.info("=" * 50)
            self.logger.info(f"Total BANK records processed: {results['total_bank_records']}")
            self.logger.info(f"Updates {'queued' if self.dry_run else 'made'}: {results['updates_made']}")
            self.logger.info(f"Unmatched transaction keys: {results['unmatched_keys_count']}")
            self.logger.info(f"Duration: {duration.total_seconds():.2f} seconds")
            
            if unmatched_keys and self.verbose:
                self.logger.info(f"First 10 unmatched keys: {unmatched_keys[:10]}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Sync failed: {str(e)}")
            raise

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Sync Company IDs between Google Sheets')
    script_dir = Path(__file__).parent.parent
    default_creds = script_dir / 'config' / 'service_account.json'
    
    parser.add_argument('--credentials', '-c', default=str(default_creds),
                       help='Path to Google service account credentials file')
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help='Preview changes without applying them')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--output-json', '-o', 
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    try:
        # Initialize and run sync
        sync = GoogleSheetsSync(
            credentials_path=args.credentials,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        results = sync.run_sync()
        
        # Save results to JSON if requested
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output_json}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nSync interrupted by user")
        return 1
    except Exception as e:
        print(f"Sync failed: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())

