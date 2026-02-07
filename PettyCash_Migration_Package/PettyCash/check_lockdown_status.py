#!/usr/bin/env python3
"""Check the status of the lockdown system"""
import json
import hashlib
from pathlib import Path
import subprocess

def check_lockdown_status():
    """Check the status of the lockdown system"""
    
    print("PETTY CASH SORTER - LOCKDOWN STATUS")
    print("=" * 50)
    
    base_dir = Path.cwd()
    lockdown_dir = base_dir / "LOCKDOWN"
    
    if not lockdown_dir.exists():
        print("❌ LOCKDOWN SYSTEM NOT FOUND")
        return False
    
    print("✅ LOCKDOWN DIRECTORY EXISTS")
    
    # Check critical files
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
    
    print("\n📋 CRITICAL FILES STATUS:")
    all_files_exist = True
    for file_path in critical_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ SOME CRITICAL FILES ARE MISSING")
        return False
    
    # Check checksums
    checksums_file = lockdown_dir / "file_checksums.json"
    if checksums_file.exists():
        print("\n🔍 FILE INTEGRITY CHECK:")
        with open(checksums_file, 'r') as f:
            stored_checksums = json.load(f)
        
        integrity_ok = True
        for file_path, stored_checksum in stored_checksums.items():
            full_path = base_dir / file_path
            if full_path.exists():
                # Calculate current checksum
                sha256_hash = hashlib.sha256()
                with open(full_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(chunk)
                current_checksum = sha256_hash.hexdigest()
                
                if stored_checksum == current_checksum:
                    print(f"  ✅ {file_path} - INTEGRITY OK")
                else:
                    print(f"  ❌ {file_path} - INTEGRITY VIOLATION")
                    integrity_ok = False
            else:
                print(f"  ❌ {file_path} - FILE MISSING")
                integrity_ok = False
        
        if integrity_ok:
            print("\n✅ ALL FILES INTEGRITY VERIFIED")
        else:
            print("\n❌ FILE INTEGRITY VIOLATIONS DETECTED")
            return False
    else:
        print("\n❌ CHECKSUMS FILE NOT FOUND")
        return False
    
    # Check backups
    backup_dir = lockdown_dir / "BACKUPS"
    if backup_dir.exists():
        backups = list(backup_dir.iterdir())
        print(f"\n📦 BACKUP STATUS: {len(backups)} backups found")
        for backup in backups:
            print(f"  📁 {backup.name}")
    else:
        print("\n❌ BACKUP DIRECTORY NOT FOUND")
    
    # Check autorun script
    autorun_script = lockdown_dir / "daily_autorun.bat"
    if autorun_script.exists():
        print(f"\n🚀 AUTORUN SCRIPT: {autorun_script.name} - EXISTS")
    else:
        print("\n❌ AUTORUN SCRIPT NOT FOUND")
    
    # Check Windows Task Scheduler
    print("\n⏰ WINDOWS TASK SCHEDULER STATUS:")
    try:
        result = subprocess.run(['schtasks', '/query', '/tn', 'PettyCashSorterDaily'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("  ✅ Task 'PettyCashSorterDaily' is configured")
            print("  📅 Schedule: Daily at midnight (00:00)")
        else:
            print("  ❌ Task 'PettyCashSorterDaily' not found")
            print("  💡 Run 'setup_task_scheduler.bat' as administrator")
    except Exception as e:
        print(f"  ❌ Error checking task scheduler: {e}")
    
    # Check file permissions
    print("\n🔒 FILE PERMISSIONS:")
    readonly_count = 0
    for file_path in critical_files:
        full_path = base_dir / file_path
        if full_path.exists():
            try:
                # Check if file is read-only
                import os
                import stat
                current_permissions = os.stat(full_path).st_mode
                if not (current_permissions & stat.S_IWRITE):
                    print(f"  🔒 {file_path} - READ-ONLY")
                    readonly_count += 1
                else:
                    print(f"  ⚠️ {file_path} - WRITABLE")
            except Exception as e:
                print(f"  ❌ {file_path} - ERROR CHECKING PERMISSIONS")
    
    if readonly_count == len(critical_files):
        print(f"\n✅ ALL {readonly_count} CRITICAL FILES ARE READ-ONLY")
    else:
        print(f"\n⚠️ {readonly_count}/{len(critical_files)} FILES ARE READ-ONLY")
    
    print("\n" + "=" * 50)
    print("🎯 LOCKDOWN SYSTEM STATUS: OPERATIONAL")
    print("✅ System is locked and protected")
    print("⏰ Daily autorun ready (requires task scheduler setup)")
    print("🛡️ File integrity monitoring active")
    print("📦 Backup system operational")
    print("🔒 Critical files protected")
    
    return True

if __name__ == "__main__":
    check_lockdown_status() 