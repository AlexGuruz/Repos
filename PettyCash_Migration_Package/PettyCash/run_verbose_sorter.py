#!/usr/bin/env python3
"""
Verbose Petty Cash Sorter
Run with detailed output showing target cell inputs
"""

import logging
from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

def main():
    """Run the sorter with verbose output."""
    print("🔍 VERBOSE PETTY CASH SORTER")
    print("=" * 50)
    
    # Set up verbose logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Output to console
        ]
    )
    
    # Initialize the sorter
    sorter = PettyCashSorterFinal()
    
    try:
        # Initialize system
        if not sorter.initialize_system():
            print("❌ System initialization failed")
            return
        
        print("✅ System initialized successfully")
        
        # Test with a small batch first to see output
        print("\n🧪 Testing with 5 transactions first...")
        test_result = sorter.test_small_batch(5)
        
        if test_result.get('status') == 'success':
            print("✅ Test successful! Now running full processing...")
            
            # Process all transactions
            print("\n🚀 Starting full transaction processing...")
            result = sorter.process_all_transactions()
            
            if result['status'] == 'success':
                print("✅ Processing completed successfully")
                print(f"📈 Final stats: {result['final_stats']}")
            else:
                print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"❌ Test failed: {test_result}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logging.error(f"Unexpected error in main: {e}")
    finally:
        # Cleanup
        sorter.cleanup_and_shutdown()
        print("👋 Goodbye!")

if __name__ == "__main__":
    main() 