#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live monitoring system that checks for new sheets and headers every 12 hours
and updates JGD Truth dropdowns automatically.
"""

from monitor_system import MonitorSystem
import logging
import time
import signal
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/live_monitor.log')
    ]
)

class LiveMonitor:
    def __init__(self, check_interval_minutes=720):  # 12 hours
        self.monitor = MonitorSystem()
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self.running = False
        self.cycle_count = 0
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def start_monitoring(self):
        """Start the live monitoring system."""
        print("🚀 Starting Live JGD Header Monitor...")
        print("=" * 60)
        print(f"📊 Check interval: {self.check_interval // 60} minutes ({self.check_interval // 3600} hours)")
        print(f"📝 Logs saved to: logs/live_monitor.log")
        print("🔄 Press Ctrl+C to stop monitoring")
        print("=" * 60)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        self.cycle_count = 0
        
        try:
            while self.running:
                self.cycle_count += 1
                cycle_start = datetime.now()
                
                print(f"\n🔄 Cycle #{self.cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 50)
                
                try:
                    # Run monitoring cycle
                    changes = self.monitor.run_monitoring_cycle()
                    
                    if changes > 0:
                        print(f"🎉 Changes detected! Updated JGD Truth dropdowns.")
                    else:
                        print(f"✅ No changes detected - dropdowns are up to date.")
                        
                except Exception as e:
                    logging.error(f"Error in monitoring cycle: {e}")
                    print(f"❌ Error in cycle: {e}")
                
                # Calculate time for this cycle
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                print(f"⏱️  Cycle completed in {cycle_time:.1f} seconds")
                
                if self.running:
                    print(f"⏳ Waiting {self.check_interval // 60} minutes ({self.check_interval // 3600} hours) until next check...")
                    print(f"🕐 Next check at: {(datetime.now() + timedelta(seconds=self.check_interval)).strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Sleep until next cycle
                    time.sleep(self.check_interval)
                    
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            logging.error(f"Fatal error in monitoring: {e}")
            print(f"❌ Fatal error: {e}")
        finally:
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """Stop the monitoring system."""
        self.running = False
        print(f"\n📊 Monitoring Summary:")
        print(f"   Total cycles: {self.cycle_count}")
        print(f"   Monitoring stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("👋 Live monitor stopped.")

def main():
    # Create logs directory if it doesn't exist
    import os
    os.makedirs('logs', exist_ok=True)
    
    # Start live monitoring with 12-hour intervals
    live_monitor = LiveMonitor(check_interval_minutes=720)
    live_monitor.start_monitoring()

if __name__ == "__main__":
    main() 