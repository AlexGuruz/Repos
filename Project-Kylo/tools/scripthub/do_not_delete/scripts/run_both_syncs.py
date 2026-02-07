#!/usr/bin/env python3
"""
Bundled Script: Runs JGDTRUTH Dynamic Columns, Sync Bank, and Company ID Sync
Runs all scripts sequentially with proper error handling:
1. JGDTRUTH Dynamic Columns - Maps headers/dates for JGDTRUTH sheets
2. Sync Bank - Applies Kylo_Config rules to CLEAN TRANSACTIONS tab (Clean Key → Company ID)
3. Company ID Sync - Syncs Company IDs from BANK to CLEAN TRANSACTIONS
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

def run_script(script_name, args=None):
    """Run a Python script and return success status"""
    script_dir = Path(__file__).parent
    script_path = script_dir / script_name
    
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print(f"{'='*60}")
    
    try:
        # Set PYTHONPATH to include parent directory for src module imports
        env = os.environ.copy()
        env['PYTHONPATH'] = str(script_dir.parent)
        result = subprocess.run(cmd, cwd=script_dir.parent, env=env, capture_output=False)
        if result.returncode == 0:
            print(f"[SUCCESS] {script_name} completed successfully")
            return True
        else:
            print(f"[FAILED] {script_name} failed with exit code {result.returncode}")
            return False
    except Exception as e:
        print(f"[ERROR] Error running {script_name}: {e}")
        return False

def main():
    """Main entry point"""
    print(f"\n{'='*60}")
    print(f"BUNDLED SYNC SCRIPT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    import time
    
    # Step 1: Run JGDTRUTH Dynamic Columns (independent, can run first)
    success1 = run_script("dynamic_columns_jgdtruth.py", ["--summary"])
    time.sleep(2)
    
    # Step 2: Run sync_bank.py - Applies Kylo_Config rules to BANK sheet
    success2 = run_script("sync_bank.py")
    time.sleep(2)
    
    # Step 3: Run Company ID Sync - Syncs from BANK to CLEAN TRANSACTIONS
    success3 = run_script("sync_company_ids.py")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"JGDTRUTH Dynamic Columns: {'[SUCCESS]' if success1 else '[FAILED]'}")
    print(f"Sync Bank (Kylo_Config -> CLEAN TRANSACTIONS): {'[SUCCESS]' if success2 else '[FAILED]'}")
    print(f"Company ID Sync (BANK -> CLEAN): {'[SUCCESS]' if success3 else '[FAILED]'}")
    
    if success1 and success2 and success3:
        print("\n[SUCCESS] All scripts completed successfully!")
        return 0
    else:
        print("\n[WARNING] One or more scripts failed. Check logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

