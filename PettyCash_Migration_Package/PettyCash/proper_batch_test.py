#!/usr/bin/env python3
"""
Proper Batch Test
Test batch updates in the correct target sheets with proper structure
"""

import logging
import time
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/proper_batch_test.log"),
        logging.StreamHandler()
    ]
)

def proper_batch_test():
    """Test proper batch updates in correct target sheets."""
    print("PROPER BATCH TEST")
    print("=" * 80)
    
    try:
        # Initialize components
        print("Initializing components...")
        db_manager = DatabaseManager()
        csv_downloader = CSVDownloader()
        ai_matcher = AIEnhancedRuleMatcher()
        sheets_integration = GoogleSheetsIntegration()
        
        # Test Google Sheets connection
        print("Testing Google Sheets connection...")
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Google Sheets connection successful")
        
        # Download transactions
        print("Downloading transactions...")
        all_transactions = csv_downloader.download_petty_cash_data()
        if not all_transactions:
            print("No transactions downloaded")
            return
        
        print(f"Downloaded {len(all_transactions)} total transactions")
        
        # Load rules
        print("Loading rules...")
        if not ai_matcher.load_rules_from_database():
            print("Failed to load rules")
            return
        
        print(f"Loaded {len(ai_matcher.rules_cache)} rules")
        
        # Take first 10 transactions for testing
        test_transactions = all_transactions[:10]
        print(f"Testing with first {len(test_transactions)} transactions")
        
        # Process transactions and group by sheet for batch updates
        print("Processing transactions and grouping for batch updates...")
        sheet_groups = {}  # {sheet_name: {cell_key: {row, col, amount}}}
        
        for i, transaction in enumerate(test_transactions):
            print(f"\nProcessing transaction {i+1}: {transaction['source']} (${transaction['amount']:.2f})")
            
            # Match transaction
            match_result = ai_matcher.match_transaction(transaction)
            
            if match_result:
                rule = match_result['rule']
                target_sheet = rule['target_sheet']
                target_header = rule['target_header']
                
                print(f"  ✅ MATCHED: {target_sheet}/{target_header}")
                
                # For testing, use known sheet structure:
                # - Headers are in row 2
                # - Dates are in column A
                # - We need to find the correct column for the header
                
                try:
                    # Get the target sheet
                    spreadsheet = sheets_integration.gc.open_by_url(sheets_integration.petty_cash_url)
                    worksheet = None
                    
                    for ws in spreadsheet.worksheets():
                        if ws.title == target_sheet:
                            worksheet = ws
                            break
                    
                    if worksheet:
                        print(f"  📊 Found target sheet: {worksheet.title}")
                        
                        # Get headers from row 2
                        headers = worksheet.row_values(2)
                        print(f"  📋 Headers: {headers[:10]}...")  # First 10 headers
                        
                        # Find the column for our target header
                        target_col = None
                        for col_idx, header in enumerate(headers, 1):
                            if target_header in header:
                                target_col = col_idx
                                break
                        
                        if target_col:
                            print(f"  🎯 Found target header '{target_header}' in column {target_col}")
                            
                            # Find the row for the transaction date
                            # For testing, use row 3 (February-25) as an example
                            target_row = 3
                            
                            # Add to batch group
                            if target_sheet not in sheet_groups:
                                sheet_groups[target_sheet] = {}
                            
                            cell_key = f"{target_row}_{target_col}"
                            sheet_groups[target_sheet][cell_key] = {
                                'row': target_row,
                                'col': target_col,
                                'amount': transaction['amount']
                            }
                            
                            print(f"  📝 Queued: {target_sheet} cell ({target_row},{target_col}) = ${transaction['amount']:.2f}")
                        else:
                            print(f"  ❌ Target header '{target_header}' not found in sheet")
                    else:
                        print(f"  ❌ Target sheet '{target_sheet}' not found")
                        
                except Exception as e:
                    print(f"  ❌ Error processing sheet: {e}")
            else:
                print(f"  ❌ NO MATCH found")
        
        # Execute batch updates
        print(f"\nExecuting batch updates...")
        print(f"Sheet groups: {list(sheet_groups.keys())}")
        
        for sheet_name, cell_updates in sheet_groups.items():
            print(f"\nBatch updating {sheet_name} with {len(cell_updates)} cells:")
            for cell_key, cell_data in cell_updates.items():
                print(f"  - Cell ({cell_data['row']},{cell_data['col']}) = ${cell_data['amount']:.2f}")
        
        # Execute the batch update
        success = sheets_integration.batch_update_sheets(sheet_groups)
        
        if success:
            print(f"\n✅ Batch updates completed successfully!")
            print(f"Updated {sum(len(cells) for cells in sheet_groups.values())} cells across {len(sheet_groups)} sheets")
        else:
            print(f"\n❌ Batch updates failed")
        
        # Show what should have been updated
        print(f"\nSUMMARY:")
        print(f"  Processed {len(test_transactions)} transactions")
        print(f"  Matched transactions: {sum(1 for t in test_transactions if ai_matcher.match_transaction(t))}")
        print(f"  Target sheets: {list(sheet_groups.keys())}")
        print(f"  Total cells to update: {sum(len(cells) for cells in sheet_groups.values())}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        logging.error(f"Test failed: {e}")

def main():
    """Main function."""
    proper_batch_test()

if __name__ == "__main__":
    main() 