@echo off
echo TEST SCRIPT: 25 Random Transactions
echo ===================================

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements_downloader.txt

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "pending_transactions" mkdir pending_transactions

echo.
echo Starting 25 transaction test...
echo This will:
echo 1. Create a backup of your Excel file
echo 2. Add 25 random transactions
echo 3. Test the complete petty cash sorter
echo 4. Restore the original file
echo.
echo Press any key to continue...
pause >nul

python test_25_transactions.py

echo.
echo Test completed!
pause 