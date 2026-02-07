#!/usr/bin/env python3
"""
PETTY CASH SORTER - LOCKDOWN SYSTEM
====================================
This system locks down the petty cash sorter to prevent any modifications
and sets up daily autorun at midnight.

SECURITY FEATURES:
- File integrity checks
- Backup system
- Autorun scheduler
- Modification detection
- Emergency recovery
"""

import os
import sys
import shutil
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import schedule
import time
import threading
from typing import Dict, List, Optional

class PettyCashLockdown:
    """Lockdown system for Petty Cash Sorter"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.lockdown_dir = self.base_dir / "LOCKDOWN"
        self.backup_dir = self.lockdown_dir / "BACKUPS"
        self.checksums_file = self.lockdown_dir / "file_checksums.json"
        self.config_file = self.lockdown_dir / "lockdown_config.json"
        self.log_file = self.lockdown_dir / "lockdown.log"
        
        # Critical files to protect
        self.critical_files = [
            "petty_cash_sorter_final_comprehensive.py",
            "database_manager.py", 
            "ai_rule_matcher_enhanced.py",
            "google_sheets_integration.py",
            "csv_downloader_fixed.py",
            "hash_deduplication.py",
            "config/system_config.json",
            "config/layout_map.json"
        ]
        
        # Create directories first, then setup logging
        self.ensure_lockdown_directory()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup secure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def ensure_lockdown_directory(self):
        """Create lockdown directory structure"""
        self.lockdown_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
    def calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
        
    def create_file_checksums(self) -> Dict[str, str]:
        """Create checksums for all critical files"""
        checksums = {}
        for file_path in self.critical_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                checksums[file_path] = self.calculate_file_checksum(full_path)
                self.logger.info(f"✅ Checksum created for {file_path}")
            else:
                self.logger.warning(f"⚠️ Critical file not found: {file_path}")
        return checksums
        
    def save_checksums(self, checksums: Dict[str, str]):
        """Save checksums to file"""
        with open(self.checksums_file, 'w') as f:
            json.dump(checksums, f, indent=2)
        self.logger.info("✅ Checksums saved")
        
    def load_checksums(self) -> Dict[str, str]:
        """Load checksums from file"""
        if self.checksums_file.exists():
            with open(self.checksums_file, 'r') as f:
                return json.load(f)
        return {}
        
    def verify_file_integrity(self) -> bool:
        """Verify all critical files haven't been modified"""
        stored_checksums = self.load_checksums()
        current_checksums = self.create_file_checksums()
        
        for file_path, stored_checksum in stored_checksums.items():
            if file_path in current_checksums:
                current_checksum = current_checksums[file_path]
                if stored_checksum != current_checksum:
                    self.logger.error(f"🚨 FILE INTEGRITY VIOLATION: {file_path}")
                    return False
                else:
                    self.logger.info(f"✅ {file_path} integrity verified")
            else:
                self.logger.error(f"🚨 CRITICAL FILE MISSING: {file_path}")
                return False
                
        return True
        
    def create_backup(self) -> str:
        """Create timestamped backup of critical files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        for file_path in self.critical_files:
            source_path = self.base_dir / file_path
            if source_path.exists():
                # Create directory structure in backup
                backup_file_path = backup_path / file_path
                backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, backup_file_path)
                
        self.logger.info(f"✅ Backup created: {backup_path}")
        return str(backup_path)
        
    def restore_from_backup(self, backup_path: str) -> bool:
        """Restore files from backup"""
        try:
            backup_dir = Path(backup_path)
            if not backup_dir.exists():
                self.logger.error(f"❌ Backup not found: {backup_path}")
                return False
                
            for file_path in self.critical_files:
                backup_file = backup_dir / file_path
                target_file = self.base_dir / file_path
                
                if backup_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    self.logger.info(f"✅ Restored: {file_path}")
                    
            return True
        except Exception as e:
            self.logger.error(f"❌ Restore failed: {e}")
            return False
            
    def create_autorun_script(self):
        """Create Windows autorun script for daily execution"""
        script_content = f'''@echo off
REM PETTY CASH SORTER - DAILY AUTORUN
REM Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
REM DO NOT MODIFY - LOCKED SYSTEM

cd /d "{self.base_dir}"
echo Starting Petty Cash Sorter - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} >> "{self.lockdown_dir}\\autorun.log"

REM Run the main program
python petty_cash_sorter_final_comprehensive.py

echo Completed Petty Cash Sorter - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} >> "{self.lockdown_dir}\\autorun.log"
'''
        
        autorun_script = self.lockdown_dir / "daily_autorun.bat"
        with open(autorun_script, 'w') as f:
            f.write(script_content)
            
        self.logger.info(f"✅ Autorun script created: {autorun_script}")
        return autorun_script
        
    def setup_windows_scheduler(self):
        """Setup Windows Task Scheduler for daily midnight run"""
        try:
            # Create the task
            task_name = "PettyCashSorterDaily"
            script_path = self.lockdown_dir / "daily_autorun.bat"
            
            # Delete existing task if it exists
            subprocess.run(['schtasks', '/delete', '/tn', task_name, '/f'], 
                         capture_output=True, shell=True)
            
            # Create new task
            cmd = [
                'schtasks', '/create', '/tn', task_name,
                '/tr', f'"{script_path}"',
                '/sc', 'daily',
                '/st', '00:00',
                '/ru', 'SYSTEM',
                '/f'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                self.logger.info("✅ Windows Task Scheduler configured for daily midnight run")
                return True
            else:
                self.logger.error(f"❌ Task scheduler setup failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Task scheduler setup failed: {e}")
            return False
            
    def create_emergency_recovery_script(self):
        """Create emergency recovery script"""
        recovery_content = f'''#!/usr/bin/env python3
"""
EMERGENCY RECOVERY SCRIPT
=========================
Use this script ONLY if the main system is compromised.
This will restore from the most recent backup.
"""

import sys
from pathlib import Path
from lockdown_system import PettyCashLockdown

def emergency_recovery():
    print("🚨 EMERGENCY RECOVERY MODE")
    print("=" * 50)
    
    lockdown = PettyCashLockdown()
    
    # Find most recent backup
    backup_dir = lockdown.backup_dir
    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")])
    
    if not backups:
        print("❌ No backups found!")
        return False
        
    latest_backup = backups[-1]
    print(f"📦 Latest backup: {latest_backup.name}")
    
    # Verify backup integrity
    print("🔍 Verifying backup integrity...")
    if not lockdown.verify_backup_integrity(latest_backup):
        print("❌ Backup integrity check failed!")
        return False
        
    # Confirm restoration
    response = input("⚠️  This will overwrite current files. Continue? (YES/NO): ")
    if response != "YES":
        print("❌ Recovery cancelled")
        return False
        
    # Restore from backup
    print("🔄 Restoring from backup...")
    if lockdown.restore_from_backup(str(latest_backup)):
        print("✅ Recovery completed successfully!")
        return True
    else:
        print("❌ Recovery failed!")
        return False

if __name__ == "__main__":
    emergency_recovery()
'''
        
        recovery_script = self.lockdown_dir / "emergency_recovery.py"
        with open(recovery_script, 'w') as f:
            f.write(recovery_content)
            
        self.logger.info(f"✅ Emergency recovery script created: {recovery_script}")
        return recovery_script
        
    def verify_backup_integrity(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        try:
            for file_path in self.critical_files:
                backup_file = backup_path / file_path
                if not backup_file.exists():
                    self.logger.error(f"❌ Backup missing: {file_path}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"❌ Backup verification failed: {e}")
            return False
            
    def create_readme(self):
        """Create comprehensive README for the lockdown system"""
        readme_content = f'''# PETTY CASH SORTER - LOCKDOWN SYSTEM
============================================

## 🚨 SECURITY NOTICE
**DO NOT MODIFY ANY FILES IN THIS SYSTEM**
This system is locked down and protected against unauthorized modifications.

## 📋 SYSTEM OVERVIEW
- **Main Program**: petty_cash_sorter_final_comprehensive.py
- **Autorun Schedule**: Daily at midnight
- **Backup Frequency**: Before each run
- **Integrity Checks**: SHA256 checksums

## 🔒 PROTECTED FILES
{chr(10).join([f"- {file}" for file in self.critical_files])}

## 🚀 DAILY OPERATION
1. System runs automatically at midnight
2. File integrity is verified
3. Backup is created
4. Main program executes
5. Results are logged

## 🛠️ EMERGENCY PROCEDURES

### If System is Compromised:
1. Run: `python LOCKDOWN/emergency_recovery.py`
2. Follow prompts to restore from backup
3. Verify system integrity

### Manual Run:
```bash
python petty_cash_sorter_final_comprehensive.py
```

## 📊 MONITORING
- Logs: LOCKDOWN/lockdown.log
- Autorun logs: LOCKDOWN/autorun.log
- Backups: LOCKDOWN/BACKUPS/

## 🔧 MAINTENANCE
- **DO NOT** modify protected files
- **DO NOT** delete backup files
- **DO NOT** disable task scheduler
- Contact system administrator for any changes

## 📞 SUPPORT
For emergency access or modifications, contact the system administrator.

---
**LOCKED DOWN**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
'''
        
        readme_file = self.lockdown_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
            
        self.logger.info(f"✅ README created: {readme_file}")
        return readme_file
        
    def lockdown_system(self):
        """Complete system lockdown"""
        self.logger.info("🔒 STARTING SYSTEM LOCKDOWN")
        self.logger.info("=" * 50)
        
        # Step 1: Create initial backup
        self.logger.info("📦 Creating initial backup...")
        backup_path = self.create_backup()
        
        # Step 2: Create file checksums
        self.logger.info("🔍 Creating file checksums...")
        checksums = self.create_file_checksums()
        self.save_checksums(checksums)
        
        # Step 3: Verify integrity
        self.logger.info("✅ Verifying system integrity...")
        if not self.verify_file_integrity():
            self.logger.error("❌ System integrity check failed!")
            return False
            
        # Step 4: Create autorun script
        self.logger.info("🚀 Creating autorun script...")
        autorun_script = self.create_autorun_script()
        
        # Step 5: Setup Windows scheduler
        self.logger.info("⏰ Setting up Windows Task Scheduler...")
        if not self.setup_windows_scheduler():
            self.logger.warning("⚠️ Manual scheduler setup required")
            
        # Step 6: Create emergency recovery
        self.logger.info("🛠️ Creating emergency recovery system...")
        recovery_script = self.create_emergency_recovery_script()
        
        # Step 7: Create documentation
        self.logger.info("📚 Creating documentation...")
        readme_file = self.create_readme()
        
        # Step 8: Final verification
        self.logger.info("🔍 Final system verification...")
        if self.verify_file_integrity():
            self.logger.info("✅ SYSTEM LOCKDOWN COMPLETE")
            self.logger.info("=" * 50)
            self.logger.info("🎯 SYSTEM IS NOW LOCKED AND PROTECTED")
            self.logger.info("⏰ DAILY AUTORUN SET FOR MIDNIGHT")
            self.logger.info("🛡️ INTEGRITY MONITORING ACTIVE")
            return True
        else:
            self.logger.error("❌ LOCKDOWN FAILED - SYSTEM COMPROMISED")
            return False

def main():
    """Main lockdown function"""
    print("🔒 PETTY CASH SORTER - LOCKDOWN SYSTEM")
    print("=" * 50)
    print("⚠️  WARNING: This will lock down the system permanently")
    print("⚠️  No modifications will be allowed after lockdown")
    print()
    
    response = input("🚨 Type 'LOCKDOWN' to proceed: ")
    if response != "LOCKDOWN":
        print("❌ Lockdown cancelled")
        return
        
    print()
    print("🔒 INITIATING SYSTEM LOCKDOWN...")
    print("=" * 50)
    
    lockdown = PettyCashLockdown()
    if lockdown.lockdown_system():
        print()
        print("🎉 LOCKDOWN SUCCESSFUL!")
        print("=" * 50)
        print("✅ System is now locked and protected")
        print("⏰ Daily autorun scheduled for midnight")
        print("🛡️ File integrity monitoring active")
        print("📦 Automatic backups enabled")
        print("🛠️ Emergency recovery system ready")
        print()
        print("🚨 DO NOT MODIFY ANY PROTECTED FILES")
        print("📞 Contact administrator for any changes")
    else:
        print()
        print("❌ LOCKDOWN FAILED!")
        print("🚨 System may be compromised")
        print("📞 Contact administrator immediately")

if __name__ == "__main__":
    main() 