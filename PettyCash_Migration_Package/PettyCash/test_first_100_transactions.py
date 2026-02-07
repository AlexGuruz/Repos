#!/usr/bin/env python3
"""
Test First 100 Transactions
Process only the first 100 transactions to verify system is working correctly
"""

import logging
import time
from pathlib import Path
from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/test_first_100.log"),
        logging.StreamHandler()
    ]
)

def test_first_100_transactions():
    """Test the system with only the first 100 transactions."""
    print("🧪 TESTING FIRST 100 TRANSACTIONS")
    print("=" * 80)
    
    # Initialize the sorter
    sorter = PettyCashSorterFinal()
    
    try:
        # Initialize system
        print("🚀 Initializing system...")
        if not sorter.initialize_system():
            print("❌ System initialization failed")
            return
        
        print("✅ System initialized successfully")
        
        # Get system status
        status = sorter.get_system_status()
        print(f"📊 System Health: {status['system_health']['status']} ({status['system_health']['health_score']}/100)")
        print(f"📋 Rules loaded: {status['ai_matcher_rules_loaded']}")
        
        # Download all transactions
        print("\n📥 Downloading transactions...")
        all_transactions = sorter.download_and_process_transactions()
        if not all_transactions:
            print("❌ No transactions downloaded")
            return
        
        print(f"📊 Downloaded {len(all_transactions)} total transactions")
        
        # Take only the first 100
        test_transactions = all_transactions[:100]
        print(f"🧪 Processing first {len(test_transactions)} transactions for testing")
        
        # Process the test batch
        print("\n⚙️ Processing test batch...")
        result = sorter.process_transactions_batch(test_transactions)
        
        if 'error' in result:
            print(f"❌ Processing failed: {result['error']}")
            return
        
        # Show results
        print("\n📊 TEST RESULTS:")
        print("=" * 50)
        
        stats = result.get('statistics', {})
        print(f"📈 Total processed: {stats.get('total_transactions', 0)}")
        print(f"✅ Matched: {stats.get('matched_count', 0)}")
        print(f"❌ Unmatched: {stats.get('unmatched_count', 0)}")
        print(f"📊 Match rate: {stats.get('match_rate_percent', 0):.1f}%")
        print(f"💾 Added to database: {result.get('added_to_db', 0)}")
        print(f"📄 Sheets updated: {result.get('sheets_updated', 0)}")
        
        # Show match details
        match_results = result.get('match_results', {})
        if match_results.get('matched'):
            print(f"\n📋 MATCHED TRANSACTIONS (first 10):")
            print("-" * 60)
            for i, match_data in enumerate(match_results['matched'][:10], 1):
                transaction = match_data['transaction']
                match = match_data['match']
                print(f"   {i}. '{transaction['source']}' -> {match['target_sheet']}/{match['target_header']} (Confidence: {match['confidence']})")
        
        if match_results.get('unmatched'):
            print(f"\n❌ UNMATCHED TRANSACTIONS (first 10):")
            print("-" * 60)
            for i, transaction in enumerate(match_results['unmatched'][:10], 1):
                print(f"   {i}. '{transaction['source']}' (Company: {transaction.get('company', 'Unknown')})")
        
        # Generate rule suggestions for unmatched
        unmatched_transactions = match_results.get('unmatched', [])
        if unmatched_transactions:
            print(f"\n💡 Generating rule suggestions for {len(unmatched_transactions)} unmatched transactions...")
            
            suggestions = sorter.ai_matcher.analyze_unmatched_transactions(
                unmatched_transactions, 
                sorter.sheets_integration,
                sorter.db_manager
            )
            
            if suggestions:
                sorter.ai_matcher.save_rule_suggestions(suggestions)
                print(f"💡 Generated {len(suggestions)} rule suggestions for user review")
                
                # Show first few suggestions
                print(f"\n📝 SAMPLE SUGGESTIONS (first 5):")
                print("-" * 60)
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"   {i}. '{suggestion['source']}' -> {suggestion['target_sheet']}/{suggestion['target_header']}")
                    print(f"      Company: {suggestion.get('company', 'Unknown')}, Confidence: {suggestion['confidence']:.2f}")
            else:
                print("💡 No rule suggestions generated")
        
        # Generate test report
        print("\n📄 Generating test report...")
        report_file = sorter.generate_comprehensive_report()
        if report_file:
            print(f"📄 Test report saved: {report_file}")
        
        # Show final system status
        final_status = sorter.get_system_status()
        print(f"\n📊 FINAL SYSTEM STATUS:")
        print(f"   Database transactions: {final_status['database'].get('total_transactions', 0)}")
        print(f"   Pending transactions: {final_status['pending_transactions']}")
        print(f"   System health: {final_status['system_health']['status']}")
        
        print(f"\n🎉 TEST COMPLETED SUCCESSFULLY!")
        print(f"   Processed {len(test_transactions)} transactions")
        print(f"   Match rate: {stats.get('match_rate_percent', 0):.1f}%")
        print(f"   Ready for full processing!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logging.error(f"Test failed: {e}")
    finally:
        # Cleanup
        sorter.cleanup_and_shutdown()
        print("👋 Test completed!")

def main():
    """Main function."""
    test_first_100_transactions()

if __name__ == "__main__":
    main() 