@echo off
echo ========================================
echo   PETTY CASH SYSTEM MIGRATION SETUP
echo ========================================
echo.

echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please ensure WinPython64 is properly installed
    echo or add Python to your system PATH
    pause
    exit /b 1
)
echo ✓ Python found

echo.
echo [2/5] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo WARNING: Some dependencies may not have installed correctly
    echo You may need to install them manually
)

echo.
echo [3/5] Checking critical files...
if not exist "config\service_account.json" (
    echo ERROR: service_account.json not found in config folder
    echo This file contains Google API credentials and is required
    pause
    exit /b 1
)
echo ✓ service_account.json found

if not exist "config\system_config.json" (
    echo ERROR: system_config.json not found in config folder
    pause
    exit /b 1
)
echo ✓ system_config.json found

if not exist "config\petty_cash.db" (
    echo WARNING: petty_cash.db not found in config folder
    echo Database will be created on first run
)

echo.
echo [4/5] Creating necessary directories...
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "exports" mkdir exports
echo ✓ Directories created

echo.
echo [5/5] Running system tests...
echo Testing database connection...
python check_database_schema.py
if errorlevel 1 (
    echo WARNING: Database test failed
    echo This may be normal if database doesn't exist yet
)

echo.
echo ========================================
echo   SETUP COMPLETE!
echo ========================================
echo.
echo To start the system:
echo   1. Run monitoring: python run_monitor_only.py
echo   2. Run main app:   python THe.py
echo   3. Run demo:       python run_slow_demo.py
echo.
echo For help, see README_MIGRATION.md
echo.
pause 