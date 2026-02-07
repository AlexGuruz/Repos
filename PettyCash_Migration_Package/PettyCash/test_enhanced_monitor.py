#!/usr/bin/env python3
"""Test the enhanced real-time monitor with rule management"""
import time
from real_time_monitor_enhanced import EnhancedRealTimeMonitor
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def test_enhanced_monitor():
    """Test the enhanced monitor functionality"""
    
    print("🧪 TESTING ENHANCED REAL-TIME MONITOR")
    print("=" * 50)
    
    # Initialize AI matcher
    print("📋 Initializing AI Rule Matcher...")
    ai_matcher = AIEnhancedRuleMatcher()
    
    # Initialize enhanced monitor
    print("🖥️ Initializing Enhanced Monitor...")
    config = {
        'monitoring': {
            'enabled': True,
            'port': 5001,  # Use different port for testing
            'host': 'localhost'
        }
    }
    
    monitor = EnhancedRealTimeMonitor(config)
    
    # Set AI matcher reference
    print("🔗 Connecting AI Matcher to Monitor...")
    monitor.set_ai_matcher(ai_matcher)
    
    # Add some test log entries
    print("📝 Adding test log entries...")
    monitor.add_log_entry('INFO', 'Enhanced monitor test started')
    monitor.add_log_entry('SUCCESS', 'AI matcher connected successfully')
    monitor.add_log_entry('INFO', 'Rule management interface ready')
    
    # Update some stats
    print("📊 Updating test statistics...")
    monitor.update_transaction_stats(1500, 95.5)
    monitor.update_api_stats(98.2)
    monitor.update_system_status('healthy')
    
    print("\n✅ Enhanced Monitor Test Complete!")
    print("🌐 Monitor should be running at: http://localhost:5001")
    print("📋 Features available:")
    print("  • Real-time dashboard")
    print("  • Rule suggestion management")
    print("  • System logs")
    print("  • Performance metrics")
    
    print("\n⏰ Monitor will run for 30 seconds...")
    time.sleep(30)
    
    print("🛑 Stopping monitor...")
    monitor.stop_monitoring()
    print("✅ Test completed successfully!")

if __name__ == "__main__":
    test_enhanced_monitor() 