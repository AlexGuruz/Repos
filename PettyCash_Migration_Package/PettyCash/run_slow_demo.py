#!/usr/bin/env python3
"""Slow demonstration script to show real-time processing"""

import time
import threading
from THe import PettyCashSorterFinal
from real_time_monitor_enhanced import EnhancedRealTimeMonitor

def run_slow_demo():
    """Run a slow demonstration of transaction processing"""
    print("🐌 SLOW DEMONSTRATION - WATCH REAL-TIME PROCESSING")
    print("=" * 60)
    
    try:
        # Initialize the main script
        print("🚀 Initializing PettyCashSorterFinal...")
        sorter = PettyCashSorterFinal()
        print("✅ PettyCashSorterFinal initialized successfully")
        
        # Initialize system
        print("🔧 Initializing system...")
        if not sorter.initialize_system():
            print("❌ System initialization failed")
            return False
        
        print("✅ System initialized successfully")
        
        # Create a separate monitor for better control
        print("🖥️ Starting dedicated monitor...")
        monitor_config = {
            'monitoring': {
                'enabled': True,
                'port': 5000,
                'host': 'localhost'
            }
        }
        
        monitor = EnhancedRealTimeMonitor(monitor_config)
        monitor.set_ai_matcher(sorter.ai_matcher)
        
        # Start monitor in background
        monitor_thread = threading.Thread(
            target=monitor.start_monitoring,
            kwargs={'port': 5000, 'host': 'localhost'},
            daemon=True
        )
        monitor_thread.start()
        
        print("✅ Monitor started at http://localhost:5000")
        print("📊 Dashboard is now live!")
        
        # Simulate slow processing
        print("\n🐌 Starting slow demonstration...")
        print("📋 You should see updates in the dashboard every 2 seconds")
        
        # Add initial log
        monitor.add_log_entry('INFO', 'Slow demonstration started')
        monitor.update_system_status('processing')
        
        # Simulate transaction processing
        total_transactions = 50  # Small batch for demo
        for i in range(total_transactions):
            # Update progress
            progress = (i + 1) / total_transactions * 100
            monitor.update_transaction_stats(i + 1, progress)
            
            # Add log entry
            monitor.add_log_entry('INFO', f'Processing transaction {i + 1}/{total_transactions}')
            
            # Update API stats
            api_success = 95 + (i % 5)  # Vary between 95-99%
            monitor.update_api_stats(api_success)
            
            print(f"📊 Processing transaction {i + 1}/{total_transactions} ({progress:.1f}%)")
            
            # Wait 2 seconds between each transaction
            time.sleep(2)
        
        # Final updates
        monitor.add_log_entry('SUCCESS', 'Slow demonstration completed successfully!')
        monitor.update_transaction_stats(total_transactions, 100.0)
        monitor.update_api_stats(98.5)
        monitor.update_system_status('healthy')
        
        print(f"\n✅ Slow demonstration completed!")
        print(f"📊 Processed {total_transactions} transactions")
        print(f"🌐 Dashboard still running at http://localhost:5000")
        print(f"⏰ Monitor will continue running...")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping demonstration...")
            monitor.stop_monitoring()
            print("✅ Demonstration stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ Demonstration error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_slow_demo() 