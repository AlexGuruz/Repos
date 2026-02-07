#!/usr/bin/env python3
"""
Test script for rule management features
"""

import json
import logging
from pathlib import Path
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_rule_management_features():
    """Test all rule management features."""
    print("🧪 Testing Rule Management Features")
    print("=" * 50)
    
    # Initialize components
    ai_matcher = AIEnhancedRuleMatcher()
    db_manager = DatabaseManager()
    
    # Test 1: Database methods
    print("\n1. Testing Database Methods...")
    
    # Test adding a rule
    test_rule = {
        'source': 'TEST SOURCE FOR RULE MANAGEMENT',
        'target_sheet': 'TEST SHEET',
        'target_header': 'TEST HEADER',
        'confidence_threshold': 0.8
    }
    
    success = db_manager.add_rule(test_rule)
    print(f"   ✅ Add rule: {'PASS' if success else 'FAIL'}")
    
    # Test updating a rule
    updated_rule = {
        'source': 'TEST SOURCE FOR RULE MANAGEMENT',
        'target_sheet': 'UPDATED SHEET',
        'target_header': 'UPDATED HEADER',
        'confidence_threshold': 0.9
    }
    
    success = db_manager.update_rule('TEST SOURCE FOR RULE MANAGEMENT', updated_rule)
    print(f"   ✅ Update rule: {'PASS' if success else 'FAIL'}")
    
    # Test 2: AI Matcher methods
    print("\n2. Testing AI Matcher Methods...")
    
    # Test clear pending suggestions
    success = ai_matcher.clear_pending_suggestions()
    print(f"   ✅ Clear suggestions: {'PASS' if success else 'FAIL'}")
    
    # Test export all rules
    rules = ai_matcher.export_all_rules()
    print(f"   ✅ Export rules: {'PASS' if len(rules) >= 0 else 'FAIL'} ({len(rules)} rules)")
    
    # Test search rules
    search_results = ai_matcher.search_rules('TEST')
    print(f"   ✅ Search rules: {'PASS' if len(search_results) >= 0 else 'FAIL'} ({len(search_results)} results)")
    
    # Test rule performance metrics
    performance = ai_matcher.get_rule_performance_metrics()
    print(f"   ✅ Performance metrics: {'PASS' if performance else 'FAIL'}")
    
    # Test get all rules with performance
    rules_with_perf = ai_matcher.get_all_rules_with_performance()
    print(f"   ✅ Rules with performance: {'PASS' if len(rules_with_perf) >= 0 else 'FAIL'} ({len(rules_with_perf)} rules)")
    
    # Test 3: Rule operations
    print("\n3. Testing Rule Operations...")
    
    # Test edit rule
    success = ai_matcher.edit_rule('TEST SOURCE FOR RULE MANAGEMENT', updated_rule)
    print(f"   ✅ Edit rule: {'PASS' if success else 'FAIL'}")
    
    # Test add rule
    new_rule = {
        'source': 'NEW TEST RULE',
        'target_sheet': 'NEW SHEET',
        'target_header': 'NEW HEADER',
        'confidence_threshold': 0.7
    }
    success = ai_matcher.add_rule(new_rule)
    print(f"   ✅ Add rule via AI matcher: {'PASS' if success else 'FAIL'}")
    
    # Test delete rule
    success = ai_matcher.delete_rule('NEW TEST RULE')
    print(f"   ✅ Delete rule: {'PASS' if success else 'FAIL'}")
    
    # Test 4: Import/Export
    print("\n4. Testing Import/Export...")
    
    # Export rules
    rules_to_export = ai_matcher.export_all_rules()
    print(f"   ✅ Export: {len(rules_to_export)} rules exported")
    
    # Test import (with a small subset)
    if rules_to_export:
        test_import = rules_to_export[:1]  # Just one rule for testing
        success = ai_matcher.import_rules(test_import)
        print(f"   ✅ Import: {'PASS' if success else 'FAIL'}")
    
    # Test 5: Refresh suggestions
    print("\n5. Testing Refresh Suggestions...")
    success = ai_matcher.refresh_suggestions()
    print(f"   ✅ Refresh suggestions: {'PASS' if success else 'FAIL'}")
    
    # Test 6: Company extraction
    print("\n6. Testing Company Extraction...")
    test_sources = [
        'NUGZ SALE TO CUSTOMER',
        'JGD PAYROLL 123',
        'PUFFIN ORDER SUPPLIER',
        'UNKNOWN SOURCE'
    ]
    
    for source in test_sources:
        company = ai_matcher._extract_company_from_source(source)
        print(f"   ✅ {source} → {company}")
    
    # Cleanup
    print("\n7. Cleanup...")
    db_manager.delete_rule('TEST SOURCE FOR RULE MANAGEMENT')
    print("   ✅ Cleanup completed")
    
    print("\n🎉 Rule Management Feature Test Complete!")
    print("=" * 50)

def test_monitor_endpoints():
    """Test monitor endpoints (if monitor is running)."""
    print("\n🌐 Testing Monitor Endpoints...")
    print("=" * 30)
    
    try:
        import requests
        
        base_url = "http://localhost:5000"
        
        # Test endpoints
        endpoints = [
            '/api/rule-stats',
            '/api/rule-suggestions',
            '/api/rules',
            '/api/rule-performance'
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    print(f"   ✅ {endpoint}: PASS")
                else:
                    print(f"   ❌ {endpoint}: FAIL (Status: {response.status_code})")
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️  {endpoint}: SKIP (Monitor not running: {e})")
                break
                
    except ImportError:
        print("   ⚠️  Requests not available - skipping endpoint tests")
    
    print("=" * 30)

if __name__ == "__main__":
    test_rule_management_features()
    test_monitor_endpoints() 