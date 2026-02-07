#!/usr/bin/env python3
"""
Petty Cash Sorter with Live Display
Shows real-time processing in the terminal
"""

import logging
import time
import threading
from datetime import datetime
from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

class LiveDisplay:
    """Simple live display for processing progress."""
    
    def __init__(self):
        self.current_row = 0
        self.current_source = ""
        self.current_amount = 0
        self.current_target = ""
        self.processed_count = 0
        self.total_count = 0
        self.start_time = None
        self.lock = threading.Lock()
    
    def update_progress(self, row, source, amount, target_sheet="", target_header=""):
        """Update the current processing status."""
        with self.lock:
            self.current_row = row
            self.current_source = source
            self.current_amount = amount
            self.current_target = f"{target_sheet} -> {target_header}" if target_sheet else "No match"
            self.processed_count += 1
    
    def set_total(self, total):
        """Set the total number of transactions."""
        with self.lock:
            self.total_count = total
            self.start_time = datetime.now()
    
    def display_status(self):
        """Display the current status."""
        with self.lock:
            if self.start_time:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                rate = self.processed_count / elapsed if elapsed > 0 else 0
                eta = (self.total_count - self.processed_count) / rate if rate > 0 else 0
                
                print(f"\r🔄 Processing: Row {self.current_row} | {self.current_source} | ${self.current_amount:.2f} | Target: {self.current_target} | Progress: {self.processed_count}/{self.total_count} ({self.processed_count/self.total_count*100:.1f}%) | Rate: {rate:.1f}/sec | ETA: {eta:.0f}s", end="", flush=True)
            else:
                print(f"\r⏳ Waiting to start... | {self.current_source}", end="", flush=True)

def main():
    """Run the sorter with live display."""
    print("🎯 PETTY CASH SORTER - LIVE DISPLAY")
    print("=" * 60)
    
    # Set up logging to file only (not console)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/live_sorter.log'),
        ]
    )
    
    # Initialize the sorter
    sorter = PettyCashSorterFinal()
    
    # Create live display
    display = LiveDisplay()
    
    try:
        # Initialize system
        print("🔧 Initializing system...")
        if not sorter.initialize_system():
            print("❌ System initialization failed")
            return
        
        print("✅ System initialized successfully")
        
        # Download transactions
        print("📥 Downloading transactions...")
        transactions = sorter.csv_downloader.download_petty_cash_data()
        
        if not transactions:
            print("❌ No transactions downloaded")
            return
        
        print(f"📊 Downloaded {len(transactions)} transactions")
        display.set_total(len(transactions))
        
        # Start display thread
        display_thread = threading.Thread(target=display_loop, args=(display,), daemon=True)
        display_thread.start()
        
        # Process transactions in small batches for live display
        batch_size = 10
        total_processed = 0
        
        print(f"\n🚀 Starting live processing (batch size: {batch_size})...")
        print("=" * 60)
        
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i + batch_size]
            
            # Process each transaction in the batch
            for transaction in batch:
                # Update display
                display.update_progress(
                    transaction['row_number'],
                    transaction['source'],
                    transaction['amount']
                )
                
                # Try to match the transaction
                try:
                    match_result = sorter.ai_matcher.find_best_match(
                        transaction['source'], 
                        transaction['company']
                    )
                    
                    if match_result.matched and match_result.matched_rule:
                        target_sheet = match_result.matched_rule.get('target_sheet', '')
                        target_header = match_result.matched_rule.get('target_header', '')
                        display.update_progress(
                            transaction['row_number'],
                            transaction['source'],
                            transaction['amount'],
                            target_sheet,
                            target_header
                        )
                        
                        # Simulate processing time
                        time.sleep(0.1)
                    else:
                        display.update_progress(
                            transaction['row_number'],
                            transaction['source'],
                            transaction['amount'],
                            "NO MATCH",
                            "NO MATCH"
                        )
                        
                except Exception as e:
                    display.update_progress(
                        transaction['row_number'],
                        transaction['source'],
                        transaction['amount'],
                        "ERROR",
                        str(e)[:20]
                    )
                
                total_processed += 1
            
            # Small delay between batches
            time.sleep(0.5)
        
        print(f"\n\n✅ Processing complete! Processed {total_processed} transactions")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        logging.error(f"Unexpected error in main: {e}")
    finally:
        # Cleanup
        sorter.cleanup_and_shutdown()
        print("\n👋 Goodbye!")

def display_loop(display):
    """Display loop that updates the status every 0.1 seconds."""
    while True:
        display.display_status()
        time.sleep(0.1)

if __name__ == "__main__":
    main() 