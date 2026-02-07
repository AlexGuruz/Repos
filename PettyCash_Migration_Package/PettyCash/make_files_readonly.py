#!/usr/bin/env python3
"""Make critical files read-only for additional security"""
import os
import stat
from pathlib import Path

def make_files_readonly():
    """Make critical files read-only"""
    
    critical_files = [
        "petty_cash_sorter_final_comprehensive.py",
        "database_manager.py", 
        "ai_rule_matcher_enhanced.py",
        "google_sheets_integration.py",
        "csv_downloader_fixed.py",
        "hash_deduplication.py",
        "config/system_config.json",
        "config/layout_map.json"
    ]
    
    print("🔒 MAKING CRITICAL FILES READ-ONLY")
    print("=" * 40)
    
    for file_path in critical_files:
        full_path = Path(file_path)
        if full_path.exists():
            # Make file read-only
            current_permissions = os.stat(full_path).st_mode
            new_permissions = current_permissions & ~stat.S_IWRITE
            os.chmod(full_path, new_permissions)
            print(f"✅ Made read-only: {file_path}")
        else:
            print(f"⚠️ File not found: {file_path}")
    
    print("\n🎯 ALL CRITICAL FILES ARE NOW READ-ONLY")
    print("🚨 MODIFICATIONS ARE BLOCKED")
    print("📞 Contact administrator to make changes")

if __name__ == "__main__":
    make_files_readonly() 