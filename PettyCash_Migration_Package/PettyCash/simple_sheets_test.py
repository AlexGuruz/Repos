#!/usr/bin/env python3
"""
Simple Google Sheets Test
Test direct cell updates without layout map dependency
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
        logging.FileHandler("logs/simple_sheets_test.log"),
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

def simple_sheets_test():
    """Simple test with direct cell updates."""
    print("SIMPLE GOOGLE SHEETS TEST")
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
        
        # Download transactions
        print("Downloading transactions...")
        all_transactions = csv_downloader.download_petty_cash_data()
        if not all_transactions:
            print("No transactions downloaded")
            return
        
        print(f"Downloaded {len(all_transactions)} total transactions")
        
        # Take first 20 transactions for testing
        test_transactions = all_transactions[:20]
        print(f"Testing with first {len(test_transactions)} transactions")
        
        # Process transactions
        print("Processing transactions...")
        matched_count = 0
        unmatched_count = 0
        sheets_updated_count = 0
        matched_examples = []
        
        for i, transaction in enumerate(test_transactions):
            print(f"\nProcessing transaction {i+1}: {transaction['source']} (${transaction['amount']:.2f})")
            
            # Add to database
            if db_manager.add_transaction(transaction):
                # Try to match
                match_result = ai_matcher.match_transaction(transaction)
                
                if match_result:
                    matched_count += 1
                    rule = match_result['rule']
                    
                    print(f"  ✅ MATCHED: {rule['target_sheet']}/{rule['target_header']}")
                    print(f"     Confidence: {match_result['confidence']}")
                    
                    if len(matched_examples) < 5:
                        matched_examples.append({
                            'source': transaction['source'],
                            'target_sheet': rule['target_sheet'],
                            'target_header': rule['target_header'],
                            'confidence': match_result['confidence'],
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
                    
                    # Try to update Google Sheets directly
                    try:
                        print(f"  📝 Attempting to update Google Sheets...")
                        
                        # Try to find the sheet and update a cell
                        success = sheets_integration.update_single_cell(
                            rule['target_sheet'],
                            10,  # Use row 10 as a test
                            5,   # Use column 5 as a test
                            transaction['amount']
                        )
                        
                        if success:
                            sheets_updated_count += 1
                            print(f"  ✅ SUCCESS: Updated {rule['target_sheet']} cell with ${transaction['amount']:.2f}")
                        else:
                            print(f"  ❌ FAILED: Could not update {rule['target_sheet']}")
                    
                    except Exception as e:
                        print(f"  ❌ ERROR updating sheet: {e}")
                
                else:
                    unmatched_count += 1
                    print(f"  ❌ NO MATCH found")
                    
                    # Mark as unmatched
                    db_manager.update_transaction_status(
                        transaction['transaction_id'],
                        'unmatched',
                        'No matching rule found'
                    )
            
            # Small delay between transactions
            time.sleep(1)
        
        # Show results
        print("\n" + "="*50)
        print("TEST RESULTS:")
        print("="*50)
        print(f"Total processed: {len(test_transactions)}")
        print(f"Matched: {matched_count}")
        print(f"Unmatched: {unmatched_count}")
        print(f"Match rate: {(matched_count/len(test_transactions)*100):.1f}%")
        print(f"Sheets updated: {sheets_updated_count}")
        
        if matched_examples:
            print(f"\nMATCHED EXAMPLES:")
            print("-" * 40)
            for i, example in enumerate(matched_examples, 1):
                print(f"  {i}. '{example['source']}' -> {example['target_sheet']}/{example['target_header']}")
                print(f"     Amount: ${example['amount']:.2f}, Confidence: {example['confidence']}")
        
        print(f"\nTEST COMPLETED!")
        print(f"  Processed {len(test_transactions)} transactions")
        print(f"  Match rate: {(matched_count/len(test_transactions)*100):.1f}%")
        print(f"  Updated {sheets_updated_count} Google Sheets cells")
        
        if sheets_updated_count > 0:
            print(f"  ✅ Google Sheets updates are working!")
        else:
            print(f"  ⚠️ Google Sheets updates need investigation")
        
    except Exception as e:
        print(f"Test failed: {e}")
        logging.error(f"Test failed: {e}")

def main():
    """Main function."""
    simple_sheets_test()

if __name__ == "__main__":
    main() 