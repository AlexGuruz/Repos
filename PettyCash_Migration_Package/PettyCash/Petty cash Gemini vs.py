#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FINAL PETTY CASH SORTER WITH AI-ENHANCED RULE MATCHING
Fully automated workflow using direct Google Sheets integration for data fetching and mapping.
"""

import logging
from pathlib import Path
import json
from datetime import datetime
import sys
import gspread
from google.oauth2.service_account import Credentials
import csv
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import io # Used to handle in-memory CSV data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/final_sorter.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

@dataclass
class MatchResult:
    """Result of a rule matching attempt."""
    matched: bool
    confidence: float
    matched_rule: Optional[Dict] = None
    original_source: str = ""
    normalized_source: str = ""
    match_type: str = "none"
    suggestions: List[str] = None

class AIEnhancedRuleMatcher:
    """AI-enhanced rule matcher with fuzzy logic and intelligent corrections."""
    
    def __init__(self):
        self.rules_cache = {}
        self.source_variations = {}
        self.confidence_threshold = 0.75
        self.max_suggestions = 5
        
        # Common patterns and corrections
        self.common_patterns = {
            r'\bINC\b': 'INCORPORATED',
            r'\bCO\b': 'COMPANY',
            r'\bLLC\b': 'LIMITED LIABILITY COMPANY',
            r'\bDIST\b': 'DISTRIBUTION',
            r'\bDISP\b': 'DISPENSARY',
            r'\bGUYZ\b': 'GUYS',
        }
        
        # Load learned variations
        self.load_learned_variations()
    
    def load_learned_variations(self):
        """Load previously learned source variations."""
        variations_file = Path("config/source_variations.json")
        if variations_file.exists():
            try:
                with open(variations_file, 'r') as f:
                    self.source_variations = json.load(f)
                logging.info(f"Loaded {len(self.source_variations)} learned source variations")
            except Exception as e:
                logging.warning(f"Could not load source variations: {e}")
    
    def save_learned_variations(self):
        """Save learned source variations for future use."""
        variations_file = Path("config/source_variations.json")
        variations_file.parent.mkdir(exist_ok=True)
        
        try:
            with open(variations_file, 'w') as f:
                json.dump(self.source_variations, f, indent=2)
            logging.info(f"Saved {len(self.source_variations)} source variations")
        except Exception as e:
            logging.error(f"Could not save source variations: {e}")
    
    def normalize_source(self, source: str) -> str:
        """Normalize source string for better matching."""
        if not source:
            return ""
        
        normalized = str(source).strip().upper()
        normalized = re.sub(r'\s+', ' ', normalized)
        
        for pattern, replacement in self.common_patterns.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def calculate_similarity(self, source1: str, source2: str) -> float:
        """Calculate similarity between two source strings."""
        if not source1 or not source2:
            return 0.0
        
        norm1 = self.normalize_source(source1)
        norm2 = self.normalize_source(source2)
        
        if norm1 == norm2:
            return 1.0
        
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        if norm1 in norm2 or norm2 in norm1:
            similarity += 0.2
        
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if len(words1) > 0 and len(words2) > 0:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
            similarity += word_overlap * 0.3
        
        return min(similarity, 1.0)
    
    def find_best_match(self, source: str, company: str) -> MatchResult:
        """Find the best matching rule for a given source and company."""
        if not source or not company:
            return MatchResult(matched=False, confidence=0.0, original_source=source)
        
        original_source = source
        normalized_source = self.normalize_source(source)
        
        exact_match = self._find_exact_match(normalized_source, company)
        if exact_match:
            return MatchResult(matched=True, confidence=1.0, matched_rule=exact_match, original_source=original_source, normalized_source=normalized_source, match_type="exact")
        
        variation_match = self._find_variation_match(source, company)
        if variation_match:
            return MatchResult(matched=True, confidence=0.95, matched_rule=variation_match, original_source=original_source, normalized_source=normalized_source, match_type="learned_variation")
        
        fuzzy_match = self._find_fuzzy_match(source, company)
        if fuzzy_match and fuzzy_match['confidence'] >= self.confidence_threshold:
            return MatchResult(matched=True, confidence=fuzzy_match['confidence'], matched_rule=fuzzy_match['rule'], original_source=original_source, normalized_source=normalized_source, match_type="fuzzy")
        
        suggestions = self._generate_suggestions(source, company)
        return MatchResult(matched=False, confidence=0.0, original_source=original_source, normalized_source=normalized_source, match_type="none", suggestions=suggestions)
    
    def _find_exact_match(self, normalized_source: str, company: str) -> Optional[Dict]:
        """Find exact match in rules cache."""
        for rule in self.rules_cache.get(company, []):
            if self.normalize_source(rule['source']) == normalized_source:
                return rule
        return None
    
    def _find_variation_match(self, source: str, company: str) -> Optional[Dict]:
        """Find match using learned variations."""
        if source in self.source_variations:
            canonical_source = self.source_variations[source]
            for rule in self.rules_cache.get(company, []):
                if self.normalize_source(rule['source']) == self.normalize_source(canonical_source):
                    return rule
        return None
    
    def _find_fuzzy_match(self, source: str, company: str) -> Optional[Dict]:
        """Find best fuzzy match."""
        best_match = None
        best_confidence = 0.0
        
        for rule in self.rules_cache.get(company, []):
            confidence = self.calculate_similarity(source, rule['source'])
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {'rule': rule, 'confidence': confidence}
        
        return best_match
    
    def _generate_suggestions(self, source: str, company: str) -> List[str]:
        """Generate suggestions for similar rules."""
        similar_rules = []
        for rule in self.rules_cache.get(company, []):
            similarity = self.calculate_similarity(source, rule['source'])
            if similarity > 0.3:
                similar_rules.append((rule['source'], similarity))
        
        similar_rules.sort(key=lambda x: x[1], reverse=True)
        return [rule[0] for rule in similar_rules[:self.max_suggestions]]
    
    def learn_variation(self, source: str, canonical_source: str):
        """Learn a new source variation."""
        self.source_variations[source] = canonical_source
        logging.info(f"Learned variation: '{source}' -> '{canonical_source}'")

class FinalPettyCashSorter:
    """Final Petty Cash Sorter with a fully automated workflow."""
    
    def __init__(self):
        # --- CHANGE POINT 1: REMOVE EXCEL FILE PATHS ---
        # These are no longer needed as we fetch data directly from Google Sheets.
        # self.jgd_financials_file = "2025 JGD Financials.xlsx" 
        self.jgd_truth_file = "JGD Truth Current.xlsx" # Still used for rules, but could be moved to a CSV/JSON.
        
        self.rules_cache = {}
        self.layout_map = {} # This will store our dynamic layout map.
        
        self.existing_transactions_cache = set()
        self.ai_matcher = AIEnhancedRuleMatcher()
        
        # Google Sheets setup
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_file('config/service_account.json', scopes=self.scope)
        self.gc = gspread.authorize(self.creds)
        self.financials_spreadsheet_url = "1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU" # Your main financials URL
        
        Path("logs").mkdir(exist_ok=True)
        Path("pending_transactions").mkdir(exist_ok=True)
        Path("config").mkdir(exist_ok=True)
        
        self.preprocessed_csv = "pending_transactions/Petty Cash PreProcessed.csv"
        self.needs_rules_csv = "pending_transactions/Petty Cash Needs Rules.csv"
        self.failed_csv = "pending_transactions/Petty Cash Failed.csv"
        self.ai_matches_csv = "pending_transactions/AI Matches.csv"
        
        self.initialize_csv_files()
        
        logging.info("INITIALIZING FINAL PETTY CASH SORTER - AUTOMATED WORKFLOW")
        logging.info("=" * 60)
    
    def initialize_csv_files(self):
        """Initialize CSV files with headers if they don't exist."""
        csv_files = [
            (self.preprocessed_csv, ['Row', 'Date', 'Initials', 'Source', 'Company', 'Amount', 'Status']),
            (self.needs_rules_csv, ['Row', 'Date', 'Initials', 'Source', 'Company', 'Amount', 'Suggestions']),
            (self.failed_csv, ['Row', 'Date', 'Initials', 'Source', 'Company', 'Amount', 'Error_Message']),
            (self.ai_matches_csv, ['Original_Source', 'Matched_Source', 'Company', 'Confidence', 'Match_Type', 'Target_Sheet', 'Target_Header'])
        ]
        
        for filepath, headers in csv_files:
            if not Path(filepath).exists():
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
    
    def load_existing_transactions_cache(self):
        """Load existing transactions from the preprocessed CSV for duplicate checking."""
        logging.info("Loading existing transactions cache...")
        if Path(self.preprocessed_csv).exists():
            with open(self.preprocessed_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Create a unique key for each transaction
                    key = (str(row['Row']), row['Source'].lower(), row['Amount'], row['Date'])
                    self.existing_transactions_cache.add(key)
        logging.info(f"Loaded {len(self.existing_transactions_cache)} transactions into cache.")

    # --- CHANGE POINT 2: NEW FUNCTION - CREATE LAYOUT MAP ---
    # This function replaces the need to read layout from a local Excel file.
    def create_layout_map(self):
        """
        Connects to Google Sheets to read the layout (headers and dates) of all target sheets.
        Saves this layout to a local JSON file for fast, offline processing.
        """
        logging.info("CREATING/UPDATING LAYOUT MAP FROM LIVE GOOGLE SHEETS")
        logging.info("=" * 60)
        
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            layout_map = {}
            
            # Define sheets to skip
            sheets_to_skip = ['PETTY CASH', 'Petty Cash KEY', 'EXPANSION CHECKLIST', 'Balance and Misc', 'SHIFT LOG', 'TIM', 'Copy of TIM', 'Info']

            for worksheet in spreadsheet.worksheets():
                sheet_title = worksheet.title
                if sheet_title in sheets_to_skip:
                    continue

                logging.info(f"Mapping layout for sheet: {sheet_title}")
                
                # Get all values to minimize API calls
                all_values = worksheet.get_all_values()
                
                # Map headers (from row 19) to column numbers
                headers = {}
                if len(all_values) >= 19:
                    header_row = all_values[18] # index 18 is row 19
                    for i, header in enumerate(header_row):
                        if header:
                            headers[header.strip()] = i + 1 # 1-based column index
                
                # Map dates (from column A) to row numbers
                dates = {}
                # Start from row 20 (index 19)
                for i, row in enumerate(all_values[19:]):
                    if row and row[0]: # Check if row and first cell exist
                        # Normalize date string for consistent matching
                        try:
                            date_obj = pd.to_datetime(row[0]).strftime('%m/%d/%y')
                            dates[date_obj] = i + 20 # 1-based row index
                        except Exception:
                            continue # Skip non-date values

                layout_map[sheet_title] = {'headers': headers, 'dates': dates}

            self.layout_map = layout_map
            # Save the map locally
            with open('config/layout_map.json', 'w') as f:
                json.dump(self.layout_map, f, indent=2)
            
            logging.info(f"Successfully created layout map for {len(layout_map)} sheets.")
            return True

        except Exception as e:
            logging.error(f"Failed to create layout map from Google Sheets: {e}")
            return False

    # --- CHANGE POINT 3: REMOVE `force_excel_calculation` ---
    # This entire function is no longer needed.
    # def force_excel_calculation(self): ...

    # --- CHANGE POINT 4: REWRITE `preprocess_petty_cash_transactions` ---
    # This function now downloads data directly, eliminating Excel.
    def preprocess_petty_cash_transactions(self):
        """
        Downloads transaction data from the 'PETTY CASH' sheet as a CSV.
        Processes new transactions and adds them to the local preprocessed CSV.
        """
        logging.info("DOWNLOADING AND PREPROCESSING TRANSACTIONS FROM GOOGLE SHEETS")
        logging.info("=" * 60)
        
        try:
            # Load cache of already processed transactions
            self.load_existing_transactions_cache()

            # Connect to the Google Sheet and get the PETTY CASH worksheet
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            worksheet = spreadsheet.worksheet("PETTY CASH")
            
            # Get all data from the sheet
            all_data = worksheet.get_all_values()

            new_transactions_count = 0
            # Open the preprocessed CSV in append mode
            with open(self.preprocessed_csv, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Process transactions starting from row 5 (index 4)
                for i, row_data in enumerate(all_data[4:]):
                    row_num = i + 5 # 1-based row number in the sheet
                    
                    if not all(row_data[0:4]): # Skip if essential fields are empty
                        continue

                    date_val, source, company, amount_val = row_data[1], row_data[3], row_data[2], row_data[18]
                    
                    # Normalize date
                    try:
                        date = pd.to_datetime(date_val).strftime('%m/%d/%y')
                    except Exception:
                        continue # Skip rows with invalid dates

                    # Check for duplicates using the cache
                    transaction_key = (str(row_num), str(source).lower(), str(amount_val), date)
                    if transaction_key in self.existing_transactions_cache:
                        continue

                    # If not a duplicate, process and write to CSV
                    initials = row_data[0]
                    
                    # Write new transaction to our local CSV
                    writer.writerow([row_num, date, initials, source, company, amount_val, 'preprocessed'])
                    
                    # Add to cache to avoid reprocessing in this run
                    self.existing_transactions_cache.add(transaction_key)
                    new_transactions_count += 1

            logging.info(f"PREPROCESSING SUMMARY: Found and saved {new_transactions_count} new transactions.")
            return True

        except Exception as e:
            logging.error(f"Error preprocessing transactions from Google Sheets: {e}")
            return False

    def read_preprocessed_transactions(self):
        """Read transactions from the local preprocessed CSV file."""
        logging.info("Reading preprocessed transactions from local CSV...")
        transactions = []
        if Path(self.preprocessed_csv).exists():
            with open(self.preprocessed_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Status') == 'preprocessed':
                        transactions.append({
                            'row': int(row['Row']),
                            'date': row['Date'],
                            'initials': row['Initials'],
                            'source': row['Source'],
                            'company': row['Company'],
                            'total': row['Amount']
                        })
        logging.info(f"Read {len(transactions)} new transactions to process.")
        return transactions

    def parse_amount(self, amount_str):
        """Convert various string formats to a float."""
        if pd.isna(amount_str) or amount_str is None: return 0.0
        amount_str = str(amount_str).strip()
        if '$ (' in amount_str and ')' in amount_str:
            return -float(amount_str.replace('$ (', '').replace(')', '').replace(',', ''))
        elif '$' in amount_str:
            return float(amount_str.replace('$', '').replace(',', '').strip())
        try:
            return float(amount_str)
        except (ValueError, TypeError):
            return 0.0

    def format_amount(self, amount):
        """Convert number back to accounting format string."""
        if amount < 0:
            return f"$ ({abs(amount):,.2f})"
        return f"${amount:,.2f}"

    def load_jgd_truth_rules(self):
        """Load rules from the local JGD Truth Excel file."""
        logging.info("LOADING JGD TRUTH RULES")
        try:
            # Using pandas for robust Excel reading
            df = pd.read_excel(self.jgd_truth_file, sheet_name=None)
            rules_cache = {}
            for sheet_name, sheet_df in df.items():
                rules_cache[sheet_name] = sheet_df.to_dict('records')
            
            self.rules_cache = rules_cache
            self.ai_matcher.rules_cache = rules_cache
            logging.info(f"Loaded {sum(len(rules) for rules in rules_cache.values())} rules from {self.jgd_truth_file}")
        except Exception as e:
            logging.error(f"Error loading JGD Truth rules: {e}")
            raise

    # --- CHANGE POINT 5: REMOVE `load_target_sheet_headers` ---
    # This is now handled by `create_layout_map`.
    # def load_target_sheet_headers(self): ...

    # --- CHANGE POINT 6: REWRITE `find_target_cell_coordinates` ---
    # This function now uses the fast, local layout map.
    def find_target_cell_coordinates(self, target_sheet, target_header, date_str):
        """Find target cell coordinates using the pre-loaded layout map."""
        try:
            sheet_map = self.layout_map.get(target_sheet)
            if not sheet_map:
                logging.warning(f"Layout map not found for sheet '{target_sheet}'")
                return None

            # Find column from header map (fast dictionary lookup)
            header_col = sheet_map['headers'].get(target_header)
            if not header_col:
                logging.warning(f"Header '{target_header}' not found in layout map for '{target_sheet}'")
                return None

            # Find row from date map (fast dictionary lookup)
            date_row = sheet_map['dates'].get(date_str)
            if not date_row:
                # This is a critical failure - the date doesn't exist in the target sheet.
                # In a real-world scenario, you might want to add a new row here via the API.
                logging.error(f"Date '{date_str}' not found in layout map for '{target_sheet}'. A new row may need to be added to the Google Sheet.")
                return None
            
            return (date_row, header_col)

        except Exception as e:
            logging.error(f"Error finding target cell coordinates from map: {e}")
            return None

    def group_transactions_by_sheet(self, transactions):
        """Group transactions by target sheet using AI-enhanced matching."""
        logging.info("GROUPING TRANSACTIONS BY TARGET SHEET WITH AI MATCHING")
        sheet_groups = {}
        
        for transaction in transactions:
            company = transaction['company']
            source = transaction['source']
            
            match_result = self.ai_matcher.find_best_match(source, company)
            
            if match_result.matched:
                if match_result.match_type == "fuzzy":
                    self.ai_matcher.learn_variation(source, match_result.matched_rule['source'])
                
                target_sheet = match_result.matched_rule['target_sheet']
                target_header = match_result.matched_rule['target_header']
                
                target_coords = self.find_target_cell_coordinates(target_sheet, target_header, transaction['date'])
                if not target_coords:
                    self.log_failed_transaction(transaction, f"Could not find cell for date {transaction['date']} and header {target_header} in {target_sheet}")
                    continue
                
                date_row, header_col = target_coords
                amount = self.parse_amount(transaction['total'])
                
                if target_sheet not in sheet_groups: sheet_groups[target_sheet] = {}
                cell_key = f"{date_row}_{header_col}"
                if cell_key not in sheet_groups[target_sheet]:
                    sheet_groups[target_sheet][cell_key] = {'row': date_row, 'col': header_col, 'amount': 0.0, 'transactions': []}
                
                sheet_groups[target_sheet][cell_key]['amount'] += amount
                sheet_groups[target_sheet][cell_key]['transactions'].append(transaction)
            else:
                self.log_needs_rule(transaction, match_result.suggestions)
        
        self.ai_matcher.save_learned_variations()
        return sheet_groups

    def batch_update_sheets(self, sheet_groups):
        """Update sheets with efficient batch operations."""
        logging.info("EXECUTING BATCH UPDATES TO GOOGLE SHEETS")
        
        try:
            spreadsheet = self.gc.open_by_url(self.financials_spreadsheet_url)
            
            for sheet_name, cell_updates in sheet_groups.items():
                worksheet = spreadsheet.worksheet(sheet_name)
                
                # Get current values in one API call
                cell_ranges = [f"{chr(64 + data['col'])}{data['row']}" for data in cell_updates.values()]
                current_values_list = worksheet.batch_get(cell_ranges)
                
                batch_update_data = []
                for i, (cell_key, cell_data) in enumerate(cell_updates.items()):
                    current_value_str = current_values_list[i][0][0] if current_values_list[i] else '0'
                    current_amount = self.parse_amount(current_value_str)
                    
                    final_amount = current_amount + cell_data['amount']
                    formatted_amount = self.format_amount(final_amount)
                    
                    cell_address = f"{chr(64 + cell_data['col'])}{cell_data['row']}"
                    batch_update_data.append({'range': cell_address, 'values': [[formatted_amount]]})

                # Update all cells for the sheet in one batch call
                if batch_update_data:
                    worksheet.batch_update(batch_update_data, value_input_option='USER_ENTERED')
                    logging.info(f"Batch update for {sheet_name} completed ({len(batch_update_data)} cells).")
                    
                    # Mark transactions as processed
                    for cell_data in cell_updates.values():
                        for trans in cell_data['transactions']:
                            self.mark_transaction_processed(trans['row'])

        except Exception as e:
            logging.error(f"Error during batch update: {e}")
            # Log all transactions in the failed group as failed
            for sheet_name, cell_updates in sheet_groups.items():
                 for cell_data in cell_updates.values():
                        for trans in cell_data['transactions']:
                            self.log_failed_transaction(trans, str(e))
    
    def mark_transaction_processed(self, row_num_to_mark):
        """Marks a transaction as processed in the preprocessed CSV."""
        # This can be optimized, but for now, it reads and rewrites the file.
        lines = []
        with open(self.preprocessed_csv, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            lines.append(header)
            for row in reader:
                if row[0] == str(row_num_to_mark):
                    row[6] = 'processed' # Update status column
                lines.append(row)
        
        with open(self.preprocessed_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(lines)

    def log_failed_transaction(self, transaction, error_message):
        with open(self.failed_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([transaction['row'], transaction['date'], transaction['initials'], transaction['source'], transaction['company'], transaction['total'], error_message])

    def log_needs_rule(self, transaction, suggestions):
        with open(self.needs_rules_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([transaction['row'], transaction['date'], transaction['initials'], transaction['source'], transaction['company'], transaction['total'], "; ".join(suggestions or [])])

    def run(self, dry_run=True):
        """Run the complete, fully automated sorting process."""
        start_time = datetime.now()
        logging.info("STARTING FULLY AUTOMATED PETTY CASH SORTING")
        logging.info("=" * 60)
        
        try:
            # Step 1: Create/Update the layout map from the live Google Sheet.
            logging.info("STEP 1/5: Updating layout map...")
            if not self.create_layout_map(): return False
            
            # Step 2: Download and preprocess new transactions.
            logging.info("STEP 2/5: Fetching and preprocessing new transactions...")
            if not self.preprocess_petty_cash_transactions(): return False
            
            # Step 3: Load local business rules.
            logging.info("STEP 3/5: Loading JGD Truth rules...")
            self.load_jgd_truth_rules()
            
            # Step 4: Read and group transactions using AI and the layout map.
            logging.info("STEP 4/5: Reading and grouping transactions...")
            transactions = self.read_preprocessed_transactions()
            if not transactions:
                logging.info("No new transactions to process.")
                return True
            
            sheet_groups = self.group_transactions_by_sheet(transactions)
            
            # Step 5: Execute updates or show dry run results.
            logging.info("STEP 5/5: Finalizing process...")
            if not sheet_groups:
                logging.info("No transactions grouped for processing.")
                return True

            if not dry_run:
                self.batch_update_sheets(sheet_groups)
                logging.info("Live update completed successfully.")
            else:
                logging.info("DRY RUN - Would update the following:")
                for sheet_name, cell_updates in sheet_groups.items():
                    logging.info(f"  Sheet: {sheet_name} ({len(cell_updates)} cells)")
            
            duration = datetime.now() - start_time
            logging.info(f"Process finished in {duration}.")
            return True
            
        except Exception as e:
            logging.error(f"Fatal error in sorting process: {e}", exc_info=True)
            return False

def main():
    """Main function to run the sorter."""
    print("🤖 FINAL PETTY CASH SORTER - AUTOMATED WORKFLOW")
    print("=" * 60)
    
    # --- CHANGE POINT 7: REMOVE LOCAL FILE CHECKS ---
    # The script no longer depends on local Excel files to run.
    # required_files = ["JGD Truth Current.xlsx", "2025 JGD Financials.xlsx"]
    
    sorter = FinalPettyCashSorter()
    
    print("\nRUNNING DRY RUN FIRST...")
    try:
        if sorter.run(dry_run=True):
            print("\nDry run completed successfully!")
            if input("\nProceed with live update? (y/N): ").strip().lower() == 'y':
                print("\nRUNNING LIVE UPDATE...")
                if sorter.run(dry_run=False):
                    print("\nLive update completed successfully!")
                else:
                    print("\nLive update FAILED!")
            else:
                print("Live update cancelled.")
        else:
            print("Dry run FAILED!")
            
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
