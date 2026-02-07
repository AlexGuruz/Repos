#!/usr/bin/env python3
"""
Show Target Cells
Simple script to show target cell inputs as transactions are processed
"""

import time
from csv_downloader_fixed import CSVDownloader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def main():
    """Show target cell inputs for transactions."""
    print("SHOWING TARGET CELL INPUTS")
    print("=" * 50)
    
    try:
        # Initialize components
        print("Initializing...")
        downloader = CSVDownloader()
        matcher = AIEnhancedRuleMatcher()
        
        # Download transactions
        print("Downloading transactions...")
        transactions = downloader.download_petty_cash_data()
        
        if not transactions:
            print("No transactions found")
            return
        
        print(f"Found {len(transactions)} transactions")
        print("\nProcessing transactions and showing target cells:")
        print("-" * 50)
        
        # Process each transaction and show target cells
        for i, transaction in enumerate(transactions):
            row_num = transaction['row_number']
            source = transaction['source']
            amount = transaction['amount']
            company = transaction['company']
            
            # Try to match the transaction
            try:
                match_result = matcher.find_best_match(source, company)
                
                if match_result.matched and match_result.matched_rule:
                    target_sheet = match_result.matched_rule.get('target_sheet', '')
                    target_header = match_result.matched_rule.get('target_header', '')
                    confidence = match_result.confidence
                    
                    print(f"Row {row_num:4d} | {source:25s} | ${amount:8.2f} | TARGET: {target_sheet:15s} -> {target_header:20s} | Confidence: {confidence:.1f}")
                else:
                    print(f"Row {row_num:4d} | {source:25s} | ${amount:8.2f} | TARGET: NO MATCH FOUND")
                    
            except Exception as e:
                print(f"Row {row_num:4d} | {source:25s} | ${amount:8.2f} | TARGET: ERROR - {str(e)[:30]}")
            
            # Show progress every 100 transactions
            if (i + 1) % 100 == 0:
                print(f"\nProcessed {i + 1}/{len(transactions)} transactions...")
                print("-" * 50)
            
            # Small delay to make it visible
            time.sleep(0.01)
        
        print(f"\nCompleted! Processed {len(transactions)} transactions")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 