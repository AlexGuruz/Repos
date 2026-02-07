#!/usr/bin/env python3
"""Run only the real-time monitor for dashboard access"""

import time
from real_time_monitor_enhanced import EnhancedRealTimeMonitor
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def run_monitor_only():
    """Run the monitor without the main processing"""
    print("🖥️ STARTING REAL-TIME MONITOR ONLY")
    print("=" * 50)
    
    # Initialize AI matcher
    print("📋 Initializing AI Rule Matcher...")
    ai_matcher = AIEnhancedRuleMatcher()
    
    # Initialize enhanced monitor
    print("🖥️ Initializing Enhanced Monitor...")
    config = {
        'monitoring': {
            'enabled': True,
            'port': 5000,
            'host': 'localhost'
        }
    }
    
    monitor = EnhancedRealTimeMonitor(config)
    
    # Set AI matcher reference
    print("🔗 Connecting AI Matcher to Monitor...")
    monitor.set_ai_matcher(ai_matcher)
    
    # Add some initial log entries
    print("📝 Adding initial log entries...")
    monitor.add_log_entry('INFO', 'Monitor started successfully')
    monitor.add_log_entry('SUCCESS', 'AI matcher connected')
    monitor.add_log_entry('INFO', 'Dashboard ready for access')
    
    # Update some stats
    print("📊 Setting initial statistics...")
    monitor.update_transaction_stats(1894, 95.5)  # From your database
    monitor.update_api_stats(98.2)
    monitor.update_system_status('healthy')
    
    print("\n✅ MONITOR IS RUNNING!")
    print("🌐 Dashboard URL: http://localhost:5000")
    print("📋 Available features:")
    print("  • Real-time dashboard")
    print("  • Rule suggestion management")
    print("  • System logs")
    print("  • Performance metrics")
    print("\n⏰ Monitor will run until you press Ctrl+C...")
    
    try:
        # Keep the monitor running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        monitor.stop_monitoring()
        print("✅ Monitor stopped successfully!")

if __name__ == "__main__":
    run_monitor_only() 