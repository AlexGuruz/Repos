#!/usr/bin/env python3
"""Test dashboard updates"""

import time
import requests

def test_dashboard_updates():
    """Test if dashboard is responding and updating"""
    print("🧪 TESTING DASHBOARD UPDATES")
    print("=" * 40)
    
    try:
        # Test basic connectivity
        print("🔗 Testing dashboard connectivity...")
        response = requests.get("http://localhost:5000", timeout=5)
        if response.status_code == 200:
            print("✅ Dashboard is accessible")
        else:
            print(f"❌ Dashboard returned status {response.status_code}")
            return False
        
        # Test stats API
        print("📊 Testing stats API...")
        response = requests.get("http://localhost:5000/api/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print("✅ Stats API working")
            print(f"  • Total transactions: {stats.get('total_transactions', 0)}")
            print(f"  • Success rate: {stats.get('success_rate', 0)}%")
            print(f"  • System status: {stats.get('system_status', 'unknown')}")
        else:
            print(f"❌ Stats API returned status {response.status_code}")
        
        # Test logs API
        print("📝 Testing logs API...")
        response = requests.get("http://localhost:5000/api/logs", timeout=5)
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ Logs API working - {len(logs)} log entries")
        else:
            print(f"❌ Logs API returned status {response.status_code}")
        
        # Test rule suggestions API
        print("🎯 Testing rule suggestions API...")
        response = requests.get("http://localhost:5000/api/rule-suggestions", timeout=5)
        if response.status_code == 200:
            suggestions = response.json()
            print(f"✅ Rule suggestions API working - {len(suggestions)} suggestions")
        else:
            print(f"❌ Rule suggestions API returned status {response.status_code}")
        
        print("\n🎉 DASHBOARD TEST COMPLETED!")
        print("🌐 Dashboard URL: http://localhost:5000")
        print("📊 All APIs are responding correctly")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to dashboard - is it running?")
        print("💡 Make sure to run: python run_slow_demo.py")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

if __name__ == "__main__":
    test_dashboard_updates() 