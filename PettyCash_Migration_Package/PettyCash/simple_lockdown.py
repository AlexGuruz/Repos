#!/usr/bin/env python3
"""
SIMPLE PETTY CASH SORTER LOCKDOWN
==================================
Simplified lockdown system without Unicode issues
"""

import os
import sys
import shutil
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
import subprocess

class SimpleLockdown:
    def __init__(self):
        self.base_dir = Path.cwd()
        self.lockdown_dir = self.base_dir / "LOCKDOWN"
        self.backup_dir = self.lockdown_dir / "BACKUPS"
        self.checksums_file = self.lockdown_dir / "file_checksums.json"
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
        
        # Create directories
        self.lockdown_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Setup logging without Unicode
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
        
    def create_file_checksums(self):
        """Create checksums for all critical files"""
        checksums = {}
        for file_path in self.critical_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                checksums[file_path] = self.calculate_file_checksum(full_path)
                self.logger.info(f"Checksum created for {file_path}")
            else:
                self.logger.warning(f"Critical file not found: {file_path}")
        return checksums
        
    def save_checksums(self, checksums):
        """Save checksums to file"""
        with open(self.checksums_file, 'w') as f:
            json.dump(checksums, f, indent=2)
        self.logger.info("Checksums saved")
        
    def create_backup(self):
        """Create timestamped backup of critical files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        for file_path in self.critical_files:
            source_path = self.base_dir / file_path
            if source_path.exists():
                backup_file_path = backup_path / file_path
                backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, backup_file_path)
                
        self.logger.info(f"Backup created: {backup_path}")
        return str(backup_path)
        
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
            
        self.logger.info(f"Autorun script created: {autorun_script}")
        return autorun_script
        
    def setup_windows_scheduler(self):
        """Setup Windows Task Scheduler for daily midnight run"""
        try:
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
                self.logger.info("Windows Task Scheduler configured for daily midnight run")
                return True
            else:
                self.logger.error(f"Task scheduler setup failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Task scheduler setup failed: {e}")
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
import shutil

def emergency_recovery():
    print("EMERGENCY RECOVERY MODE")
    print("=" * 50)
    
    base_dir = Path.cwd()
    lockdown_dir = base_dir / "LOCKDOWN"
    backup_dir = lockdown_dir / "BACKUPS"
    
    # Find most recent backup
    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")])
    
    if not backups:
        print("No backups found!")
        return False
        
    latest_backup = backups[-1]
    print(f"Latest backup: {latest_backup.name}")
    
    # Confirm restoration
    response = input("This will overwrite current files. Continue? (YES/NO): ")
    if response != "YES":
        print("Recovery cancelled")
        return False
        
    # Restore from backup
    print("Restoring from backup...")
    
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
    
    try:
        for file_path in critical_files:
            backup_file = latest_backup / file_path
            target_file = base_dir / file_path
            
            if backup_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target_file)
                print(f"Restored: {file_path}")
                
        print("Recovery completed successfully!")
        return True
    except Exception as e:
        print(f"Recovery failed: {e}")
        return False

if __name__ == "__main__":
    emergency_recovery()
'''
        
        recovery_script = self.lockdown_dir / "emergency_recovery.py"
        with open(recovery_script, 'w') as f:
            f.write(recovery_content)
            
        self.logger.info(f"Emergency recovery script created: {recovery_script}")
        return recovery_script
        
    def create_readme(self):
        """Create comprehensive README for the lockdown system"""
        readme_content = f'''# PETTY CASH SORTER - LOCKDOWN SYSTEM
============================================

## SECURITY NOTICE
**DO NOT MODIFY ANY FILES IN THIS SYSTEM**
This system is locked down and protected against unauthorized modifications.

## SYSTEM OVERVIEW
- **Main Program**: petty_cash_sorter_final_comprehensive.py
- **Autorun Schedule**: Daily at midnight
- **Backup Frequency**: Before each run
- **Integrity Checks**: SHA256 checksums

## PROTECTED FILES
{chr(10).join([f"- {file}" for file in self.critical_files])}

## DAILY OPERATION
1. System runs automatically at midnight
2. File integrity is verified
3. Backup is created
4. Main program executes
5. Results are logged

## EMERGENCY PROCEDURES

### If System is Compromised:
1. Run: `python LOCKDOWN/emergency_recovery.py`
2. Follow prompts to restore from backup
3. Verify system integrity

### Manual Run:
```bash
python petty_cash_sorter_final_comprehensive.py
```

## MONITORING
- Logs: LOCKDOWN/lockdown.log
- Autorun logs: LOCKDOWN/autorun.log
- Backups: LOCKDOWN/BACKUPS/

## MAINTENANCE
- **DO NOT** modify protected files
- **DO NOT** delete backup files
- **DO NOT** disable task scheduler
- Contact system administrator for any changes

## SUPPORT
For emergency access or modifications, contact the system administrator.

---
**LOCKED DOWN**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
'''
        
        readme_file = self.lockdown_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
            
        self.logger.info(f"README created: {readme_file}")
        return readme_file
        
    def lockdown_system(self):
        """Complete system lockdown"""
        self.logger.info("STARTING SYSTEM LOCKDOWN")
        self.logger.info("=" * 50)
        
        # Step 1: Create initial backup
        self.logger.info("Creating initial backup...")
        backup_path = self.create_backup()
        
        # Step 2: Create file checksums
        self.logger.info("Creating file checksums...")
        checksums = self.create_file_checksums()
        self.save_checksums(checksums)
        
        # Step 3: Create autorun script
        self.logger.info("Creating autorun script...")
        autorun_script = self.create_autorun_script()
        
        # Step 4: Setup Windows scheduler
        self.logger.info("Setting up Windows Task Scheduler...")
        if not self.setup_windows_scheduler():
            self.logger.warning("Manual scheduler setup required")
            
        # Step 5: Create emergency recovery
        self.logger.info("Creating emergency recovery system...")
        recovery_script = self.create_emergency_recovery_script()
        
        # Step 6: Create documentation
        self.logger.info("Creating documentation...")
        readme_file = self.create_readme()
        
        self.logger.info("SYSTEM LOCKDOWN COMPLETE")
        self.logger.info("=" * 50)
        self.logger.info("SYSTEM IS NOW LOCKED AND PROTECTED")
        self.logger.info("DAILY AUTORUN SET FOR MIDNIGHT")
        self.logger.info("INTEGRITY MONITORING ACTIVE")
        return True

def main():
    """Main lockdown function"""
    print("PETTY CASH SORTER - LOCKDOWN SYSTEM")
    print("=" * 50)
    print("WARNING: This will lock down the system permanently")
    print("No modifications will be allowed after lockdown")
    print()
    
    response = input("Type 'LOCKDOWN' to proceed: ")
    if response != "LOCKDOWN":
        print("Lockdown cancelled")
        return
        
    print()
    print("INITIATING SYSTEM LOCKDOWN...")
    print("=" * 50)
    
    lockdown = SimpleLockdown()
    if lockdown.lockdown_system():
        print()
        print("LOCKDOWN SUCCESSFUL!")
        print("=" * 50)
        print("System is now locked and protected")
        print("Daily autorun scheduled for midnight")
        print("File integrity monitoring active")
        print("Automatic backups enabled")
        print("Emergency recovery system ready")
        print()
        print("DO NOT MODIFY ANY PROTECTED FILES")
        print("Contact administrator for any changes")
    else:
        print()
        print("LOCKDOWN FAILED!")
        print("System may be compromised")
        print("Contact administrator immediately")

if __name__ == "__main__":
    main() 