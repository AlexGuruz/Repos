#!/usr/bin/env python3
"""
Simplified test of the comprehensive petty cash sorter
"""

import logging
import time
from pathlib import Path
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from rule_loader import RuleLoader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration

def main():
    print("🧪 SIMPLIFIED COMPREHENSIVE TEST")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    try:
        # Initialize components
        print("🔧 Initializing components...")
        
        db_manager = DatabaseManager()
        csv_downloader = CSVDownloader()
        rule_loader = RuleLoader()
        ai_matcher = AIRuleMatcher()
        sheets_integration = GoogleSheetsIntegration()
        
        # Test Google Sheets connection
        print("\n🔗 Testing Google Sheets connection...")
        if not sheets_integration.test_connection():
            print("❌ Google Sheets connection failed")
            return
        
        print("✅ Google Sheets connection successful")
        
        # Create database
        print("\n💾 Creating database...")
        if not db_manager.create_database():
            print("❌ Database creation failed")
            return
        
        print("✅ Database created successfully")
        
        # Load rules
        print("\n📋 Loading rules...")
        if not rule_loader.reload_rules():
            print("❌ Rules loading failed")
            return
        
        print("✅ Rules loaded successfully")
        
        # Load rules into AI matcher
        print("\n🤖 Loading rules into AI matcher...")
        if not ai_matcher.load_rules_from_database():
            print("❌ AI matcher loading failed")
            return
        
        print("✅ AI matcher loaded successfully")
        
        # Test layout map creation
        print("\n🗺️ Testing layout map creation...")
        try:
            layout_map = sheets_integration.create_layout_map()
            if layout_map:
                print(f"✅ Layout map created with {len(layout_map)} sheets")
                
                # Show some sample mappings
                for sheet_name, sheet_map in list(layout_map.items())[:3]:
                    print(f"  📊 {sheet_name}: {len(sheet_map)} headers")
                    for header, info in list(sheet_map.items())[:3]:
                        print(f"    {header} → Row {info['row']}, Col {info['col']}")
            else:
                print("❌ Layout map creation failed")
                return
        except Exception as e:
            print(f"❌ Layout map creation error: {e}")
            return
        
        # Test transaction download
        print("\n📥 Testing transaction download...")
        try:
            transactions = csv_downloader.download_petty_cash_data()
            if transactions:
                print(f"✅ Downloaded {len(transactions)} transactions")
                
                # Show sample transaction
                if transactions:
                    sample = transactions[0]
                    print(f"📝 Sample transaction: {sample.get('source', 'N/A')} - ${sample.get('amount', 0)}")
            else:
                print("❌ Transaction download failed")
                return
        except Exception as e:
            print(f"❌ Transaction download error: {e}")
            return
        
        # Test AI matching
        print("\n🧠 Testing AI matching...")
        try:
            # Test with a small sample
            test_transactions = transactions[:5]
            match_results = ai_matcher.batch_match_transactions(test_transactions)
            
            print(f"✅ AI matching completed:")
            print(f"  📊 Total: {len(test_transactions)}")
            print(f"  ✅ Matched: {len(match_results['matched'])}")
            print(f"  ❌ Unmatched: {len(match_results['unmatched'])}")
            
            if match_results['matched']:
                sample_match = match_results['matched'][0]
                print(f"  🎯 Sample match: {sample_match['match']['matched_source']} → {sample_match['match']['target_sheet']}")
        
        except Exception as e:
            print(f"❌ AI matching error: {e}")
            return
        
        print("\n🎉 All tests completed successfully!")
        print("✅ The comprehensive petty cash sorter is working correctly!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logging.error(f"Test error: {e}")

if __name__ == "__main__":
    main() 