#!/usr/bin/env python3
"""
Debug Layout Mapping
Tests the layout mapping functionality to identify issues
"""

import logging
from google_sheets_integration import GoogleSheetsIntegration
from config_manager import ConfigManager

def debug_layout_mapping():
    """Debug the layout mapping functionality."""
    print("🗺️ DEBUGGING LAYOUT MAPPING")
    print("=" * 50)
    
    try:
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
            
            # Show some sample mappings
            for sheet_name, sheet_map in list(layout_map.items())[:3]:
                print(f"\n📊 Sheet: {sheet_name}")
                print(f"  Headers: {len(sheet_map)}")
                
                # Show first few headers
                for header, info in list(sheet_map.items())[:3]:
                    print(f"    {header} → Row {info['row']}, Col {info['col']}")
            
            # Check that COMMISSION is excluded
            if 'COMMISSION' not in layout_map:
                print("\n✅ COMMISSION sheet properly excluded")
            else:
                print("\n❌ COMMISSION sheet not excluded")
                return False
            
            return True
        else:
            print("❌ Layout map creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Layout mapping debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_layout_mapping() 