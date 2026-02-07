#!/usr/bin/env python3
"""
Demonstration of Rule Management Features
"""

import time
import logging
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from real_time_monitor_enhanced import EnhancedRealTimeMonitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def demo_rule_management():
    """Demonstrate the rule management features."""
    print("🎯 Rule Management Features Demonstration")
    print("=" * 50)
    
    # Initialize components
    ai_matcher = AIEnhancedRuleMatcher()
    
    # Initialize monitor
    config = {
        'monitoring': {
            'enabled': True,
            'update_interval': 5,
            'port': 5000,
            'host': 'localhost'
        }
    }
    
    monitor = EnhancedRealTimeMonitor(config)
    monitor.set_ai_matcher(ai_matcher)
    
    print("\n📊 Current Rule Statistics:")
    stats = ai_matcher.get_match_statistics()
    print(f"   • Total Rules: {stats.get('total_rules', 0)}")
    print(f"   • Companies: {stats.get('companies_count', 0)}")
    print(f"   • Success Rate: {stats.get('overall_success_rate', 0):.1f}%")
    
    print("\n🔍 Rule Search Demo:")
    search_results = ai_matcher.search_rules('NUGZ')
    print(f"   • Found {len(search_results)} rules containing 'NUGZ'")
    for rule in search_results[:3]:  # Show first 3
        print(f"     - {rule.get('source', 'Unknown')} → {rule.get('target_sheet', 'Unknown')}")
    
    print("\n📈 Performance Metrics:")
    performance = ai_matcher.get_rule_performance_metrics()
    if performance.get('success_rates'):
        for company, stats in performance['success_rates'].items():
            rate = stats.get('rate', 0)
            total = stats.get('total', 0)
            print(f"   • {company}: {rate:.1f}% ({total} matches)")
    
    print("\n📋 Export/Import Demo:")
    rules = ai_matcher.export_all_rules()
    print(f"   • Exported {len(rules)} rules")
    
    # Show sample rule structure
    if rules:
        sample_rule = rules[0]
        print(f"   • Sample rule structure:")
        print(f"     Source: {sample_rule.get('source', 'Unknown')}")
        print(f"     Target: {sample_rule.get('target_sheet', 'Unknown')} → {sample_rule.get('target_header', 'Unknown')}")
        print(f"     Confidence: {sample_rule.get('confidence_threshold', 0) * 100:.1f}%")
    
    print("\n🎛️  Rule Management Operations:")
    
    # Test clear suggestions
    success = ai_matcher.clear_pending_suggestions()
    print(f"   • Clear suggestions: {'✅ Success' if success else '❌ Failed'}")
    
    # Test refresh suggestions
    success = ai_matcher.refresh_suggestions()
    print(f"   • Refresh suggestions: {'✅ Success' if success else '❌ Failed'}")
    
    print("\n🌐 Monitor Integration:")
    print("   • Starting enhanced monitor on http://localhost:5000")
    print("   • Rule management features available in the web interface:")
    print("     - View all rules with performance data")
    print("     - Search and filter rules")
    print("     - Export/import rules")
    print("     - Clear pending suggestions")
    print("     - Rule performance analytics")
    
    # Start the monitor
    try:
        monitor.start_monitoring(port=5000, host='localhost')
        print("\n✅ Monitor started successfully!")
        print("   Open http://localhost:5000 in your browser")
        print("   Click on 'Rule Management' tab to see all features")
        
        # Keep running for a while
        print("\n⏳ Monitor will run for 60 seconds...")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopping monitor...")
    except Exception as e:
        print(f"\n❌ Error starting monitor: {e}")
    finally:
        monitor.stop_monitoring()
        print("✅ Monitor stopped")

if __name__ == "__main__":
    demo_rule_management() 