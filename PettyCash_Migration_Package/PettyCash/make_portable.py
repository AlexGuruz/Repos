#!/usr/bin/env python3
"""Make the Petty Cash Sorter portable for use on different computers"""
import os
import shutil
from pathlib import Path
import json

def make_system_portable():
    """Make the system portable by updating paths and creating portable scripts"""
    
    print("PORTABLE PETTY CASH SORTER SETUP")
    print("=" * 50)
    
    # Get current directory (will be portable)
    current_dir = Path.cwd()
    
    print(f"Current directory: {current_dir}")
    print("Making system portable...")
    
    # Create portable autorun script
    portable_autorun_content = f'''@echo off
REM PORTABLE PETTY CASH SORTER - DAILY AUTORUN
REM This script will work from any location
REM Created: {Path.cwd()}

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Starting Portable Petty Cash Sorter - %date% %time% >> "LOCKDOWN\\autorun.log"

REM Run the main program
python petty_cash_sorter_final_comprehensive.py

echo Completed Portable Petty Cash Sorter - %date% %time% >> "LOCKDOWN\\autorun.log"
'''
    
    portable_autorun = current_dir / "portable_autorun.bat"
    with open(portable_autorun, 'w') as f:
        f.write(portable_autorun_content)
    
    print(f"✅ Created portable autorun: {portable_autorun.name}")
    
    # Create portable task scheduler setup
    portable_scheduler_content = f'''@echo off
echo PORTABLE PETTY CASH SORTER - TASK SCHEDULER SETUP
echo ================================================
echo.
echo This will create a Windows Task to run the Petty Cash Sorter daily at midnight
echo.
echo NOTE: This requires administrator privileges
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running as administrator - proceeding...
) else (
    echo ERROR: This script requires administrator privileges
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo.
echo Creating Windows Task Scheduler...
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Delete existing task if it exists
schtasks /delete /tn "PettyCashSorterDaily" /f >nul 2>&1

REM Create new task with portable path
schtasks /create /tn "PettyCashSorterDaily" /tr "%SCRIPT_DIR%portable_autorun.bat" /sc daily /st 00:00 /ru SYSTEM /f

if %errorLevel% == 0 (
    echo.
    echo SUCCESS: Portable task scheduler configured!
    echo.
    echo Task Details:
    echo - Name: PettyCashSorterDaily
    echo - Schedule: Daily at midnight (00:00)
    echo - Script: %SCRIPT_DIR%portable_autorun.bat
    echo.
    echo The Petty Cash Sorter will now run automatically every day at midnight.
    echo.
    echo To verify the task was created, run:
    echo schtasks /query /tn "PettyCashSorterDaily"
    echo.
) else (
    echo.
    echo ERROR: Failed to create task scheduler
    echo Please run this script as administrator
    echo.
)

pause
'''
    
    portable_scheduler = current_dir / "portable_setup_task_scheduler.bat"
    with open(portable_scheduler, 'w') as f:
        f.write(portable_scheduler_content)
    
    print(f"✅ Created portable scheduler setup: {portable_scheduler.name}")
    
    # Create portable run script
    portable_run_content = f'''@echo off
REM PORTABLE PETTY CASH SORTER - MANUAL RUN
REM This script will run the system from any location

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Running Portable Petty Cash Sorter...
echo Location: %SCRIPT_DIR%
echo.

python petty_cash_sorter_final_comprehensive.py

echo.
echo Petty Cash Sorter completed.
pause
'''
    
    portable_run = current_dir / "run_portable.bat"
    with open(portable_run, 'w') as f:
        f.write(portable_run_content)
    
    print(f"✅ Created portable run script: {portable_run.name}")
    
    # Create portable status check
    portable_status_content = f'''@echo off
REM PORTABLE PETTY CASH SORTER - STATUS CHECK
REM This script will check the system status from any location

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Checking Portable Petty Cash Sorter Status...
echo Location: %SCRIPT_DIR%
echo.

python check_lockdown_status.py

echo.
pause
'''
    
    portable_status = current_dir / "check_portable_status.bat"
    with open(portable_status, 'w') as f:
        f.write(portable_status_content)
    
    print(f"✅ Created portable status check: {portable_status.name}")
    
    # Create portable README
    portable_readme_content = f'''# PORTABLE PETTY CASH SORTER
====================================

## 🚀 PORTABLE OPERATION

This system is now portable and can run from any computer with Python installed.

## 📋 REQUIREMENTS

### On Target Computer:
- Python 3.7+ installed
- Internet connection (for Google Sheets API)
- Administrator access (for task scheduler setup)

### Required Python Packages:
```
pip install gspread pandas schedule
```

## 🚀 QUICK START

### 1. First Time Setup:
```bash
# Run as administrator
portable_setup_task_scheduler.bat
```

### 2. Manual Run:
```bash
run_portable.bat
```

### 3. Check Status:
```bash
check_portable_status.bat
```

## ⏰ AUTOMATIC OPERATION

After running the setup script as administrator:
- System will run automatically at midnight every day
- No user intervention required
- Complete logging and backup system

## 🔧 TROUBLESHOOTING

### If Task Scheduler Fails:
1. Right-click `portable_setup_task_scheduler.bat`
2. Select "Run as administrator"
3. Follow prompts

### If Python Not Found:
1. Install Python from python.org
2. Add Python to PATH during installation
3. Restart computer

### If Packages Missing:
```bash
pip install gspread pandas schedule
```

## 📁 SYSTEM FILES

- `petty_cash_sorter_final_comprehensive.py` - Main program
- `run_portable.bat` - Manual run script
- `portable_autorun.bat` - Automatic run script
- `check_portable_status.bat` - Status check
- `LOCKDOWN/` - Security and backup system

## 🔒 SECURITY

- All critical files are read-only
- File integrity monitoring active
- Automatic backups before each run
- Emergency recovery system available

---
**PORTABLE VERSION CREATED**: {Path.cwd()}
'''
    
    portable_readme = current_dir / "PORTABLE_README.md"
    with open(portable_readme, 'w') as f:
        f.write(portable_readme_content)
    
    print(f"✅ Created portable README: {portable_readme.name}")
    
    # Create requirements file
    requirements_content = '''gspread
pandas
schedule
'''
    
    requirements_file = current_dir / "requirements_portable.txt"
    with open(requirements_file, 'w') as f:
        f.write(requirements_content)
    
    print(f"✅ Created requirements file: {requirements_file.name}")
    
    print("\n" + "=" * 50)
    print("🎉 PORTABLE SYSTEM CREATED!")
    print("=" * 50)
    print("✅ System is now portable")
    print("✅ Can run from any computer")
    print("✅ All paths are relative")
    print("✅ Automatic setup scripts created")
    print()
    print("📋 TO USE ON ANOTHER COMPUTER:")
    print("1. Copy entire folder to target computer")
    print("2. Install Python and required packages")
    print("3. Run 'portable_setup_task_scheduler.bat' as administrator")
    print("4. System will run automatically at midnight")
    print()
    print("🚀 MANUAL RUN: 'run_portable.bat'")
    print("📊 STATUS CHECK: 'check_portable_status.bat'")

if __name__ == "__main__":
    make_system_portable() 