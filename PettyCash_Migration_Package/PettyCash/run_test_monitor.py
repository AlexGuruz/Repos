#!/usr/bin/env python3
"""Run test monitor on port 5001"""

import time
from real_time_monitor_enhanced import EnhancedRealTimeMonitor
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def run_test_monitor():
    """Run the test monitor on port 5001"""
    print("🧪 STARTING TEST MONITOR")
    print("=" * 40)
    
    # Initialize AI matcher
    print("📋 Initializing AI Rule Matcher...")
    ai_matcher = AIEnhancedRuleMatcher()
    
    # Initialize enhanced monitor on port 5001
    print("🖥️ Initializing Test Monitor...")
    config = {
        'monitoring': {
            'enabled': True,
            'port': 5001,
            'host': 'localhost'
        }
    }
    
    monitor = EnhancedRealTimeMonitor(config)
    
    # Set AI matcher reference
    print("🔗 Connecting AI Matcher to Monitor...")
    monitor.set_ai_matcher(ai_matcher)
    
    # Add test log entries
    print("📝 Adding test log entries...")
    monitor.add_log_entry('INFO', 'Test monitor started')
    monitor.add_log_entry('SUCCESS', 'AI matcher connected successfully')
    monitor.add_log_entry('INFO', 'Rule management interface ready')
    
    # Update test stats
    print("📊 Updating test statistics...")
    monitor.update_transaction_stats(1500, 95.5)
    monitor.update_api_stats(98.2)
    monitor.update_system_status('healthy')
    
    print("\n✅ TEST MONITOR IS RUNNING!")
    print("🌐 Test Dashboard URL: http://localhost:5001")
    print("📋 Test features available:")
    print("  • Real-time dashboard")
    print("  • Rule suggestion management")
    print("  • System logs")
    print("  • Performance metrics")
    print("\n⏰ Test monitor will run for 60 seconds...")
    
    # Run for 60 seconds
    time.sleep(60)
    
    print("🛑 Stopping test monitor...")
    monitor.stop_monitoring()
    print("✅ Test monitor stopped successfully!")

if __name__ == "__main__":
    run_test_monitor() 