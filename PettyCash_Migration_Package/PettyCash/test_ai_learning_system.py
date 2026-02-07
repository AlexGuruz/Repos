#!/usr/bin/env python3
"""
Test AI Learning System
Tests the enhanced AI system that learns from processed transactions
"""

import logging
import json
from pathlib import Path
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from database_manager import DatabaseManager
from google_sheets_integration import GoogleSheetsIntegration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ai_learning_system():
    """Test the AI learning system that learns from processed transactions."""
    print("🧪 TESTING AI LEARNING SYSTEM")
    print("=" * 50)
    
    try:
        # Initialize components
        ai_matcher = AIEnhancedRuleMatcher()
        db_manager = DatabaseManager()
        sheets_integration = GoogleSheetsIntegration()
        
        # Test 1: Load rules from database
        print("\n1️⃣ Testing rule loading from database...")
        if ai_matcher.load_rules_from_database():
            print(f"✅ Loaded {len(ai_matcher.rules_cache)} rules from database")
        else:
            print("❌ Failed to load rules from database")
            return False
        
        # Test 2: Create sample processed transactions for learning
        print("\n2️⃣ Creating sample processed transactions for learning...")
        sample_processed_transactions = [
            {
                'transaction_id': 'TEST001',
                'source': 'NUGZ WHOLESALE PAYMENT',
                'company': 'NUGZ',
                'status': 'high_confidence',
                'target_sheet': 'NUGZ C.O.G.',
                'target_header': 'WHOLESALE',
                'notes': 'Matched to NUGZ WHOLESALE rule'
            },
            {
                'transaction_id': 'TEST002',
                'source': 'LAB TESTING SERVICES',
                'company': 'JGD',
                'status': 'high_confidence',
                'target_sheet': 'JGD',
                'target_header': 'LAB EXPENSES',
                'notes': 'Matched to LAB TESTING rule'
            },
            {
                'transaction_id': 'TEST003',
                'source': 'EMPLOYEE PAYROLL',
                'company': 'PUFFIN',
                'status': 'high_confidence',
                'target_sheet': 'PAYROLL',
                'target_header': 'SALARIES',
                'notes': 'Matched to PAYROLL rule'
            }
        ]
        
        # Add these to database (simulate processed transactions)
        for tx in sample_processed_transactions:
            # First add as a transaction
            db_manager.add_transaction({
                'transaction_id': tx['transaction_id'],
                'row_number': 999,  # Test row
                'date': '2025-01-15',
                'source': tx['source'],
                'company': tx['company'],
                'amount': 1000.00
            })
            
            # Then update with match information
            db_manager.update_transaction_with_match(
                tx['transaction_id'],
                tx['status'],
                tx['source'],  # matched_source
                tx['target_sheet'],
                tx['target_header'],
                tx['notes']
            )
        
        print(f"✅ Created {len(sample_processed_transactions)} sample processed transactions")
        
        # Test 3: Test learning from processed transactions
        print("\n3️⃣ Testing learning from processed transactions...")
        unmatched_transactions = [
            {
                'source': 'NUGZ WHOLESALE ORDER',  # Similar to TEST001
                'company': 'NUGZ',
                'amount': 1500.00,
                'date': '2025-01-16'
            },
            {
                'source': 'LAB ANALYSIS SERVICES',  # Similar to TEST002
                'company': 'JGD',
                'amount': 250.00,
                'date': '2025-01-17'
            },
            {
                'source': 'STAFF PAYROLL',  # Similar to TEST003
                'company': 'PUFFIN',
                'amount': 800.00,
                'date': '2025-01-18'
            }
        ]
        
        # Generate suggestions using the learning system
        suggestions = ai_matcher.analyze_unmatched_transactions(
            unmatched_transactions,
            sheets_integration,
            db_manager
        )
        
        if suggestions:
            print(f"✅ Generated {len(suggestions)} suggestions using learning system:")
            
            # Group suggestions by type
            learning_suggestions = [s for s in suggestions if 'Learning from similar' in s.get('reason', '')]
            pattern_suggestions = [s for s in suggestions if 'Learning from similar' not in s.get('reason', '')]
            
            print(f"   📚 Learning-based suggestions: {len(learning_suggestions)}")
            print(f"   🎯 Pattern-based suggestions: {len(pattern_suggestions)}")
            
            # Show learning suggestions
            if learning_suggestions:
                print("\n   📚 Learning-based suggestions:")
                for i, suggestion in enumerate(learning_suggestions[:3], 1):
                    print(f"     {i}. {suggestion['source']} → {suggestion['target_sheet']}/{suggestion['target_header']}")
                    print(f"        Confidence: {suggestion['confidence']:.2f}")
                    print(f"        Reason: {suggestion['reason']}")
                    print(f"        Similarity: {suggestion.get('similarity_score', 'N/A')}")
        else:
            print("❌ No suggestions generated")
            return False
        
        # Test 4: Test similarity calculation
        print("\n4️⃣ Testing similarity calculation...")
        test_source = "NUGZ WHOLESALE ORDER"
        reference_source = "NUGZ WHOLESALE PAYMENT"
        similarity = ai_matcher.calculate_similarity(test_source, reference_source)
        print(f"   Similarity between '{test_source}' and '{reference_source}': {similarity:.2f}")
        
        if similarity > 0.5:
            print("   ✅ High similarity detected - learning should work")
        else:
            print("   ⚠️ Low similarity - may need adjustment")
        
        # Test 5: Test finding similar processed transactions
        print("\n5️⃣ Testing similar transaction finding...")
        similar_transactions = ai_matcher._find_similar_processed_transactions(
            "NUGZ WHOLESALE ORDER",
            db_manager.get_processed_transactions_by_company('NUGZ')
        )
        
        if similar_transactions:
            print(f"   ✅ Found {len(similar_transactions)} similar transactions")
            for tx in similar_transactions[:2]:
                print(f"     • {tx['source']} (similarity: {tx['similarity_score']:.2f})")
        else:
            print("   ❌ No similar transactions found")
        
        print("\n🎉 AI learning system test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logging.error(f"Test error: {e}")
        return False

def cleanup_test_data():
    """Clean up test data from database."""
    try:
        db_manager = DatabaseManager()
        
        # Remove test transactions
        test_transaction_ids = ['TEST001', 'TEST002', 'TEST003']
        
        for tx_id in test_transaction_ids:
            # Delete from audit log
            conn = db_manager.conn if hasattr(db_manager, 'conn') else None
            if not conn:
                import sqlite3
                conn = sqlite3.connect(db_manager.db_path)
            
            cursor = conn.cursor()
            cursor.execute('DELETE FROM audit_log WHERE transaction_id = ?', (tx_id,))
            cursor.execute('DELETE FROM transactions WHERE transaction_id = ?', (tx_id,))
            conn.commit()
            conn.close()
        
        print("🧹 Cleaned up test data")
        
    except Exception as e:
        print(f"⚠️ Could not clean up test data: {e}")

def main():
    """Main test function."""
    print("🧪 AI LEARNING SYSTEM TEST")
    print("=" * 60)
    
    # Run test
    test_passed = test_ai_learning_system()
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 30)
    print(f"AI Learning System: {'✅ PASS' if test_passed else '❌ FAIL'}")
    
    if test_passed:
        print("\n🎉 AI learning system is working correctly!")
        print("   The AI can now learn from processed transactions to suggest new rules.")
        
        # Ask if user wants to clean up test data
        cleanup = input("\n🧹 Clean up test data? (y/n): ").strip().lower()
        if cleanup == 'y':
            cleanup_test_data()
    else:
        print("\n❌ Test failed. Please check the system configuration.")
    
    print("\n👋 Test completed!")

if __name__ == "__main__":
    main() 