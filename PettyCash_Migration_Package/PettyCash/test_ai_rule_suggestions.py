#!/usr/bin/env python3
"""
Test AI Rule Suggestion System
Tests the enhanced AI rule suggestion system with sheet/header analysis
"""

import logging
import json
from pathlib import Path
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ai_rule_suggestions():
    """Test the AI rule suggestion system."""
    print("🧪 TESTING AI RULE SUGGESTION SYSTEM")
    print("=" * 50)
    
    try:
        # Initialize components
        ai_matcher = AIEnhancedRuleMatcher()
        sheets_integration = GoogleSheetsIntegration()
        
        # Test 1: Load rules from database
        print("\n1️⃣ Testing rule loading from database...")
        if ai_matcher.load_rules_from_database():
            print(f"✅ Loaded {len(ai_matcher.rules_cache)} rules from database")
        else:
            print("❌ Failed to load rules from database")
            return False
        
        # Test 2: Get layout map
        print("\n2️⃣ Testing layout map retrieval...")
        layout_map = sheets_integration.get_layout_map()
        if layout_map:
            print(f"✅ Retrieved layout map with {len(layout_map)} sheets")
            for sheet, headers in list(layout_map.items())[:3]:  # Show first 3
                print(f"   • {sheet}: {len(headers)} headers")
        else:
            print("❌ Failed to get layout map")
            return False
        
        # Test 3: Create sample unmatched transactions
        print("\n3️⃣ Testing rule suggestion generation...")
        sample_transactions = [
            {
                'source': 'NUGZ WHOLESALE PAYMENT',
                'company': 'NUGZ',
                'amount': 1500.00,
                'date': '2025-01-15'
            },
            {
                'source': 'LAB TESTING SERVICES',
                'company': 'JGD',
                'amount': 250.00,
                'date': '2025-01-16'
            },
            {
                'source': 'EMPLOYEE PAYROLL',
                'company': 'PUFFIN',
                'amount': 800.00,
                'date': '2025-01-17'
            },
            {
                'source': 'REGISTER CASH DEPOSIT',
                'company': 'NUGZ',
                'amount': 1200.00,
                'date': '2025-01-18'
            }
        ]
        
        # Generate suggestions
        suggestions = ai_matcher.analyze_unmatched_transactions(sample_transactions, sheets_integration)
        
        if suggestions:
            print(f"✅ Generated {len(suggestions)} rule suggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"   {i}. {suggestion['source']} → {suggestion['target_sheet']}/{suggestion['target_header']}")
                print(f"      Confidence: {suggestion['confidence']:.2f}, Reason: {suggestion['reason']}")
        else:
            print("❌ No suggestions generated")
            return False
        
        # Test 4: Save suggestions
        print("\n4️⃣ Testing suggestion saving...")
        ai_matcher.save_rule_suggestions(suggestions)
        print("✅ Suggestions saved to pending queue")
        
        # Test 5: Retrieve pending suggestions
        print("\n5️⃣ Testing suggestion retrieval...")
        pending_suggestions = ai_matcher.get_pending_rule_suggestions()
        if pending_suggestions:
            print(f"✅ Retrieved {len(pending_suggestions)} pending suggestions")
        else:
            print("❌ No pending suggestions found")
            return False
        
        # Test 6: Test suggestion approval (simulate)
        print("\n6️⃣ Testing suggestion approval system...")
        if pending_suggestions:
            test_suggestion = pending_suggestions[0]
            print(f"   Testing approval for: {test_suggestion['source']}")
            
            # Note: We won't actually approve in test to avoid changing database
            print("   ✅ Approval system ready (not executed in test)")
        
        print("\n🎉 All tests passed! AI rule suggestion system is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logging.error(f"Test error: {e}")
        return False

def test_suggestion_interface():
    """Test the suggestion interface functions."""
    print("\n🧪 TESTING SUGGESTION INTERFACE")
    print("=" * 40)
    
    try:
        ai_matcher = AIEnhancedRuleMatcher()
        
        # Test getting pending suggestions
        suggestions = ai_matcher.get_pending_rule_suggestions()
        print(f"📋 Found {len(suggestions)} pending suggestions")
        
        if suggestions:
            print("\n📝 Sample suggestion details:")
            sample = suggestions[0]
            print(f"   ID: {sample.get('id', 'N/A')}")
            print(f"   Source: {sample['source']}")
            print(f"   Target: {sample['target_sheet']} → {sample['target_header']}")
            print(f"   Confidence: {sample['confidence']:.2f}")
            print(f"   Status: {sample.get('status', 'N/A')}")
        
        print("✅ Suggestion interface working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Interface test failed: {e}")
        return False

def cleanup_test_suggestions():
    """Clean up test suggestions."""
    suggestions_file = Path("config/pending_rule_suggestions.json")
    
    if suggestions_file.exists():
        try:
            with open(suggestions_file, 'r') as f:
                suggestions = json.load(f)
            
            # Remove test suggestions (those with test sources)
            test_sources = ['NUGZ WHOLESALE PAYMENT', 'LAB TESTING SERVICES', 'EMPLOYEE PAYROLL', 'REGISTER CASH DEPOSIT']
            filtered_suggestions = [s for s in suggestions if s['source'] not in test_sources]
            
            with open(suggestions_file, 'w') as f:
                json.dump(filtered_suggestions, f, indent=2)
            
            print(f"🧹 Cleaned up {len(suggestions) - len(filtered_suggestions)} test suggestions")
            
        except Exception as e:
            print(f"⚠️ Could not clean up test suggestions: {e}")

def main():
    """Main test function."""
    print("🧪 AI RULE SUGGESTION SYSTEM TEST")
    print("=" * 60)
    
    # Run tests
    test1_passed = test_ai_rule_suggestions()
    test2_passed = test_suggestion_interface()
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 30)
    print(f"Rule suggestion generation: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Suggestion interface: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! AI rule suggestion system is ready for use.")
        
        # Ask if user wants to clean up test data
        cleanup = input("\n🧹 Clean up test suggestions? (y/n): ").strip().lower()
        if cleanup == 'y':
            cleanup_test_suggestions()
    else:
        print("\n❌ Some tests failed. Please check the system configuration.")
    
    print("\n👋 Test completed!")

if __name__ == "__main__":
    main() 