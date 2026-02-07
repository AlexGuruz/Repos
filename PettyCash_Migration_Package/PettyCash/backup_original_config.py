#!/usr/bin/env python3
"""Backup original configuration before switching to practice workbook"""

import shutil
from pathlib import Path

def backup_original_config():
    """Backup original configuration files."""
    
    print("📁 BACKING UP ORIGINAL CONFIGURATION")
    print("=" * 45)
    
    try:
        # Create backup directory
        backup_dir = Path("backup_original_config")
        backup_dir.mkdir(exist_ok=True)
        
        # Files to backup
        files_to_backup = [
            "google_sheets_integration.py",
            "config/system_config.json",
            "config/layout_map.json"
        ]
        
        backed_up_files = []
        
        for file_path in files_to_backup:
            source = Path(file_path)
            if source.exists():
                # Create subdirectories if needed
                dest = backup_dir / file_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source, dest)
                backed_up_files.append(file_path)
                print(f"✅ Backed up: {file_path}")
            else:
                print(f"⚠️  File not found: {file_path}")
        
        print()
        print("🎉 BACKUP COMPLETED!")
        print(f"📁 Backup location: {backup_dir}")
        print(f"📊 Files backed up: {len(backed_up_files)}")
        print()
        print("🔗 Practice workbook URL:")
        print("   https://docs.google.com/spreadsheets/d/1koQmnvfkSpCkKMX_9cc1EnN0z0NPn4x-GTOic3wqmEc")
        print()
        print("✅ Ready to test with practice workbook!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False

if __name__ == "__main__":
    backup_original_config() 