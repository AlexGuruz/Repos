#!/usr/bin/env python3
"""
Test 100 Transactions with Google Sheets Updates
Process first 100 transactions and actually update target cells
"""

import logging
import time
import sqlite3
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging without emojis to avoid Unicode issues
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/test_100_with_sheets.log"),
        logging.StreamHandler()
    ]
)

def clear_database():
    """Clear all transactions from database."""
    print("Clearing database...")
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Clear transactions table
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM audit_log")
        
        # Reset auto-increment
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='audit_log'")
        
        conn.commit()
        conn.close()
        print("Database cleared successfully")
        return True
    except Exception as e:
        print(f"Error clearing database: {e}")
        return False

def test_100_with_sheets_update():
    """Test with first 100 transactions and update Google Sheets."""
    print("TEST 100 TRANSACTIONS WITH GOOGLE SHEETS UPDATES")
    print("=" * 80)
    
    try:
        # Clear database first
        if not clear_database():
            print("Failed to clear database")
            return
        
        # Initialize components
        print("Initializing components...")
        db_manager = DatabaseManager()
        csv_downloader = CSVDownloader()
        ai_matcher = AIEnhancedRuleMatcher()
        sheets_integration = GoogleSheetsIntegration()
        
        # Create database
        print("Creating database...")
        if not db_manager.create_database():
            print("Failed to create database")
            return
        
        # Load rules
        print("Loading rules...")
        if not ai_matcher.load_rules_from_database():
            print("Failed to load rules")
            return
        
        print(f"Loaded {len(ai_matcher.rules_cache)} rules")
        
        # Test Google Sheets connection
        print("Testing Google Sheets connection...")
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Google Sheets connection successful")
        
        # Create layout map
        print("Creating layout map...")
        layout_map = sheets_integration.create_layout_map()
        if not layout_map:
            print("Failed to create layout map")
            return
        
        print(f"Layout map created with {len(layout_map)} sheets")
        
        # Download transactions
        print("Downloading transactions...")
        all_transactions = csv_downloader.download_petty_cash_data()
        if not all_transactions:
            print("No transactions downloaded")
            return
        
        print(f"Downloaded {len(all_transactions)} total transactions")
        
        # Take first 100
        test_transactions = all_transactions[:100]
        print(f"Testing with first {len(test_transactions)} transactions")
        
        # Process transactions
        print("Processing transactions...")
        matched_count = 0
        unmatched_count = 0
        sheets_updated_count = 0
        matched_examples = []
        unmatched_examples = []
        
        for i, transaction in enumerate(test_transactions):
            # Add to database
            if db_manager.add_transaction(transaction):
                # Try to match
                match_result = ai_matcher.match_transaction(transaction)
                
                if match_result:
                    matched_count += 1
                    rule = match_result['rule']
                    
                    if len(matched_examples) < 5:
                        matched_examples.append({
                            'source': transaction['source'],
                            'target_sheet': rule['target_sheet'],
                            'target_header': rule['target_header'],
                            'confidence': match_result['confidence'],
                            'company': transaction.get('company', 'Unknown'),
                            'amount': transaction['amount']
                        })
                    
                    # Update transaction with match
                    db_manager.update_transaction_with_match(
                        transaction['transaction_id'],
                        'matched',
                        match_result['matched_source'],
                        rule['target_sheet'],
                        rule['target_header'],
                        f"Matched with confidence {match_result['confidence']}"
                    )
                    
                    # Find target cell coordinates
                    try:
                        cell_coords = sheets_integration.find_target_cell_coordinates(
                            rule['target_sheet'],
                            rule['target_header'],
                            transaction['date']
                        )
                        
                        if cell_coords:
                            # Update the cell with the amount
                            success = sheets_integration.update_cell_value(
                                cell_coords['sheet'],
                                cell_coords['row'],
                                cell_coords['col'],
                                transaction['amount']
                            )
                            
                            if success:
                                sheets_updated_count += 1
                                print(f"  Updated {rule['target_sheet']}/{rule['target_header']} with ${transaction['amount']:.2f}")
                            else:
                                print(f"  Failed to update {rule['target_sheet']}/{rule['target_header']}")
                        else:
                            print(f"  Could not find cell coordinates for {rule['target_sheet']}/{rule['target_header']}")
                    
                    except Exception as e:
                        print(f"  Error updating sheet: {e}")
                
                else:
                    unmatched_count += 1
                    if len(unmatched_examples) < 5:
                        unmatched_examples.append({
                            'source': transaction['source'],
                            'company': transaction.get('company', 'Unknown')
                        })
                    
                    # Mark as unmatched
                    db_manager.update_transaction_status(
                        transaction['transaction_id'],
                        'unmatched',
                        'No matching rule found'
                    )
            
            # Progress update
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(test_transactions)} transactions...")
        
        # Show results
        print("\nTEST RESULTS:")
        print("=" * 50)
        print(f"Total processed: {len(test_transactions)}")
        print(f"Matched: {matched_count}")
        print(f"Unmatched: {unmatched_count}")
        print(f"Match rate: {(matched_count/len(test_transactions)*100):.1f}%")
        print(f"Sheets updated: {sheets_updated_count}")
        
        if matched_examples:
            print(f"\nMATCHED EXAMPLES (with amounts):")
            print("-" * 50)
            for i, example in enumerate(matched_examples, 1):
                print(f"  {i}. '{example['source']}' -> {example['target_sheet']}/{example['target_header']}")
                print(f"     Company: {example['company']}, Confidence: {example['confidence']}")
                print(f"     Amount: ${example['amount']:.2f}")
                print()
        
        if unmatched_examples:
            print(f"\nUNMATCHED EXAMPLES:")
            print("-" * 40)
            for i, example in enumerate(unmatched_examples, 1):
                print(f"  {i}. '{example['source']}' (Company: {example['company']})")
        
        # Generate rule suggestions for unmatched
        unmatched_transactions = [t for t in test_transactions if not ai_matcher.match_transaction(t)]
        if unmatched_transactions:
            print(f"\nGenerating rule suggestions for {len(unmatched_transactions)} unmatched transactions...")
            
            suggestions = ai_matcher.analyze_unmatched_transactions(
                unmatched_transactions, 
                sheets_integration,
                db_manager
            )
            
            if suggestions:
                ai_matcher.save_rule_suggestions(suggestions)
                print(f"Generated {len(suggestions)} rule suggestions")
                
                print(f"\nSAMPLE SUGGESTIONS:")
                print("-" * 40)
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"  {i}. '{suggestion['source']}' -> {suggestion['target_sheet']}/{suggestion['target_header']}")
                    print(f"     Company: {suggestion.get('company', 'Unknown')}, Confidence: {suggestion['confidence']:.2f}")
            else:
                print("No rule suggestions generated")
        
        # Database stats
        db_stats = db_manager.get_database_stats()
        print(f"\nDATABASE STATISTICS:")
        print(f"  Total transactions: {db_stats.get('total_transactions', 0)}")
        print(f"  Matched transactions: {db_stats.get('matched_transactions', 0)}")
        print(f"  Unmatched transactions: {db_stats.get('unmatched_transactions', 0)}")
        
        print(f"\nGOOGLE SHEETS UPDATE SUMMARY:")
        print(f"  Successfully updated {sheets_updated_count} cells")
        print(f"  Failed updates: {matched_count - sheets_updated_count}")
        
        print(f"\nTEST COMPLETED SUCCESSFULLY!")
        print(f"  Processed {len(test_transactions)} transactions")
        print(f"  Match rate: {(matched_count/len(test_transactions)*100):.1f}%")
        print(f"  Updated {sheets_updated_count} Google Sheets cells")
        print(f"  Ready for full processing!")
        
        # Show rule suggestion interface info
        if suggestions:
            print(f"\nRULE SUGGESTIONS READY FOR REVIEW:")
            print(f"  Run: python review_rule_suggestions.py")
            print(f"  Or double-click: review_suggestions.bat")
        
    except Exception as e:
        print(f"Test failed: {e}")
        logging.error(f"Test failed: {e}")

def main():
    """Main function."""
    test_100_with_sheets_update()

if __name__ == "__main__":
    main() 