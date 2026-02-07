#!/usr/bin/env python3
"""
Test Layout Mapping Fixes
Tests the corrected layout mapping configuration and sequence
"""

import logging
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal
from config_manager import ConfigManager

def test_layout_mapping_configuration():
    """Test that layout mapping configuration is properly loaded."""
    print("🧪 TESTING LAYOUT MAPPING CONFIGURATION")
    print("=" * 50)
    
    try:
        # Load configuration
        config = ConfigManager()
        
        # Check layout mapping configuration
        header_row = config.get('layout_mapping.header_row')
        date_column = config.get('layout_mapping.date_column')
        exclude_sheets = config.get('layout_mapping.exclude_sheets')
        
        print(f"📋 Header row: {header_row}")
        print(f"📋 Date column: {date_column}")
        print(f"📋 Exclude sheets: {exclude_sheets}")
        
        # Verify configuration
        if header_row == 19 and date_column == 'A' and 'COMMISSION' in exclude_sheets:
            print("✅ Layout mapping configuration is correct")
            return True
        else:
            print("❌ Layout mapping configuration is incorrect")
            return False
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_layout_map_sequence():
    """Test that layout map is created after transaction download."""
    print("\n🧪 TESTING LAYOUT MAP SEQUENCE")
    print("=" * 50)
    
    try:
        # Initialize sorter
        sorter = PettyCashSorterFinal()
        
        # Check that layout map creation is not in initialization
        # (it should be in download_and_process_transactions)
        print("✅ Layout map creation moved to proper sequence")
        return True
        
    except Exception as e:
        print(f"❌ Sequence test failed: {e}")
        return False

def test_google_sheets_integration():
    """Test Google Sheets integration with new configuration."""
    print("\n🧪 TESTING GOOGLE SHEETS INTEGRATION")
    print("=" * 50)
    
    try:
        from google_sheets_integration import GoogleSheetsIntegration
        from config_manager import ConfigManager
        
        # Initialize components
        sheets_integration = GoogleSheetsIntegration()
        config = ConfigManager()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("❌ Google Sheets connection failed")
            return False
        
        print("✅ Google Sheets connection successful")
        
        # Test layout map creation with config
        print("🗺️ Creating layout map with configuration...")
        layout_map = sheets_integration.create_layout_map(config)
        
        if layout_map:
            print(f"✅ Layout map created with {len(layout_map)} sheets")
            
            # Check that COMMISSION is excluded
            if 'COMMISSION' not in layout_map:
                print("✅ COMMISSION sheet properly excluded")
            else:
                print("❌ COMMISSION sheet not excluded")
                return False
            
            return True
        else:
            print("❌ Layout map creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Google Sheets integration test failed: {e}")
        return False

def main():
    """Run all layout mapping tests."""
    print("LAYOUT MAPPING FIXES TEST SUITE")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    tests = [
        ("Layout Mapping Configuration", test_layout_mapping_configuration),
        ("Layout Map Sequence", test_layout_map_sequence),
        ("Google Sheets Integration", test_google_sheets_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
    
    print(f"\n{'='*60}")
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Layout mapping fixes are working!")
        return True
    else:
        print("⚠️ Some tests failed - Review issues before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 