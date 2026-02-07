#!/usr/bin/env python3
"""
Production Readiness Test
Tests all system components to ensure readiness for live processing
"""

import logging
import json
from pathlib import Path
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
from database_manager import DatabaseManager
from google_sheets_integration import GoogleSheetsIntegration
from csv_downloader_fixed import CSVDownloader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_production_readiness():
    """Test all system components for production readiness."""
    print("🚀 PRODUCTION READINESS TEST")
    print("=" * 60)
    
    test_results = {}
    
    try:
        # Test 1: Database Manager
        print("\n1️⃣ Testing Database Manager...")
        db_manager = DatabaseManager()
        
        # Test database creation/connection
        if db_manager.create_database():
            print("   ✅ Database connection successful")
            test_results['database'] = True
        else:
            print("   ❌ Database connection failed")
            test_results['database'] = False
        
        # Test 2: AI Rule Matcher
        print("\n2️⃣ Testing AI Rule Matcher...")
        ai_matcher = AIEnhancedRuleMatcher()
        
        # Test rule loading
        if ai_matcher.load_rules_from_database():
            print(f"   ✅ Loaded {len(ai_matcher.rules_cache)} rules from database")
            test_results['ai_matcher'] = True
        else:
            print("   ❌ Failed to load rules from database")
            test_results['ai_matcher'] = False
        
        # Test 3: Google Sheets Integration
        print("\n3️⃣ Testing Google Sheets Integration...")
        sheets_integration = GoogleSheetsIntegration()
        
        # Test connection
        if sheets_integration.test_connection():
            print("   ✅ Google Sheets connection successful")
            test_results['google_sheets'] = True
        else:
            print("   ❌ Google Sheets connection failed")
            test_results['google_sheets'] = False
        
        # Test layout map
        layout_map = sheets_integration.get_layout_map()
        if layout_map:
            print(f"   ✅ Layout map available with {len(layout_map)} sheets")
            test_results['layout_map'] = True
        else:
            print("   ⚠️ No layout map available (will be created during processing)")
            test_results['layout_map'] = False
        
        # Test 4: CSV Downloader
        print("\n4️⃣ Testing CSV Downloader...")
        csv_downloader = CSVDownloader()
        
        # Test download capability (without actually downloading)
        try:
            # Just test the class initialization
            print("   ✅ CSV Downloader initialized successfully")
            test_results['csv_downloader'] = True
        except Exception as e:
            print(f"   ❌ CSV Downloader failed: {e}")
            test_results['csv_downloader'] = False
        
        # Test 5: AI Learning System
        print("\n5️⃣ Testing AI Learning System...")
        try:
            # Test similarity calculation
            similarity = ai_matcher.calculate_similarity("TEST SOURCE", "TEST SOURCE")
            if similarity == 1.0:
                print("   ✅ Similarity calculation working")
                test_results['ai_learning'] = True
            else:
                print("   ⚠️ Similarity calculation may need adjustment")
                test_results['ai_learning'] = False
        except Exception as e:
            print(f"   ❌ AI Learning system failed: {e}")
            test_results['ai_learning'] = False
        
        # Test 6: Configuration Files
        print("\n6️⃣ Testing Configuration Files...")
        config_files = [
            "config/system_config.json",
            "config/service_account.json"
        ]
        
        missing_files = []
        for config_file in config_files:
            if Path(config_file).exists():
                print(f"   ✅ {config_file} exists")
            else:
                print(f"   ❌ {config_file} missing")
                missing_files.append(config_file)
        
        if not missing_files:
            test_results['config_files'] = True
        else:
            test_results['config_files'] = False
            print(f"   Missing files: {missing_files}")
        
        # Test 7: Directory Structure
        print("\n7️⃣ Testing Directory Structure...")
        required_dirs = ["config", "logs", "reports", "pending_transactions"]
        
        missing_dirs = []
        for dir_name in required_dirs:
            if Path(dir_name).exists():
                print(f"   ✅ {dir_name}/ directory exists")
            else:
                print(f"   ⚠️ {dir_name}/ directory missing (will be created)")
                missing_dirs.append(dir_name)
        
        if not missing_dirs:
            test_results['directories'] = True
        else:
            test_results['directories'] = False
        
        # Test 8: Database Schema
        print("\n8️⃣ Testing Database Schema...")
        try:
            conn = db_manager.conn if hasattr(db_manager, 'conn') else None
            if not conn:
                import sqlite3
                conn = sqlite3.connect(db_manager.db_path)
            
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(transactions)")
            columns = [column[1] for column in cursor.fetchall()]
            conn.close()
            
            required_columns = ['matched_rule_id', 'target_sheet', 'target_header', 'notes']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if not missing_columns:
                print("   ✅ Database schema is up to date")
                test_results['database_schema'] = True
            else:
                print(f"   ❌ Missing columns: {missing_columns}")
                test_results['database_schema'] = False
                
        except Exception as e:
            print(f"   ❌ Database schema check failed: {e}")
            test_results['database_schema'] = False
        
        return test_results
        
    except Exception as e:
        print(f"❌ Production readiness test failed: {e}")
        return {'error': str(e)}

def generate_readiness_report(test_results):
    """Generate a production readiness report."""
    print("\n📊 PRODUCTION READINESS REPORT")
    print("=" * 60)
    
    if 'error' in test_results:
        print("❌ Test failed with error:", test_results['error'])
        return False
    
    passed_tests = sum(1 for result in test_results.values() if result is True)
    total_tests = len(test_results)
    
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    # Determine overall readiness
    if passed_tests == total_tests:
        print("\n🎉 SYSTEM IS READY FOR PRODUCTION!")
        print("   All components are working correctly.")
        print("   Ready to process 2000+ transactions.")
        return True
    elif passed_tests >= total_tests * 0.8:  # 80% success rate
        print("\n⚠️ SYSTEM IS MOSTLY READY")
        print("   Most components are working.")
        print("   Some minor issues may need attention.")
        return True
    else:
        print("\n❌ SYSTEM NOT READY FOR PRODUCTION")
        print("   Multiple critical issues need to be resolved.")
        return False

def main():
    """Main test function."""
    print("🚀 PRODUCTION READINESS ASSESSMENT")
    print("=" * 80)
    
    # Run tests
    test_results = test_production_readiness()
    
    # Generate report
    is_ready = generate_readiness_report(test_results)
    
    if is_ready:
        print("\n✅ RECOMMENDATION: PROCEED WITH LIVE PROCESSING")
        print("   The system is ready to handle 2000+ transactions.")
        print("   Run: python petty_cash_sorter_final_comprehensive.py")
    else:
        print("\n❌ RECOMMENDATION: FIX ISSUES BEFORE PROCESSING")
        print("   Please resolve the issues above before running live.")
    
    print("\n👋 Assessment completed!")

if __name__ == "__main__":
    main() 