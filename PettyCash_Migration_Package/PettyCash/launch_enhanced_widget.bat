@echo off
echo Starting JGD Enhanced Systems Monitor...
echo.
echo This widget combines:
echo - Header Monitor (updates dropdowns every 12 hours)
echo - Petty Cash Monitor (processes new transactions every 5 minutes)
echo.
echo Both systems are independently tracked and configurable.
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade required packages
echo Installing required packages...
pip install --upgrade pip
pip install gspread gspread-formatting pillow

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "config" mkdir config
if not exist "data" mkdir data

REM Check for required configuration files
if not exist "config\service_account.json" (
    echo.
    echo WARNING: service_account.json not found in config folder
    echo Please ensure your Google Sheets API credentials are properly configured
    echo.
)

if not exist "config\email.env" (
    echo.
    echo WARNING: email.env not found in config folder
    echo Email notifications will not be available
    echo.
)

echo.
echo Starting Enhanced Desktop Widget...
echo Press Ctrl+C to stop the application
echo.

REM Run the enhanced widget
python desktop_widget_enhanced.py

REM If we get here, the application has closed
echo.
echo Enhanced widget has been closed.
pause 