@echo off
echo ENHANCED FINAL PETTY CASH SORTER
echo =================================

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements (if needed)
echo Checking requirements...
venv\Scripts\pip.exe install -r requirements_downloader.txt

echo.
echo Choose mode:
echo 1. Dry Run (preview changes)
echo 2. Live Update (apply changes)
echo 3. Retry Failed Transactions
echo 4. Generate Failure Report
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Running DRY RUN...
    venv\Scripts\python.exe -c "
from petty_cash_sorter_final import FinalPettyCashSorter
import logging

# Configure logging to show on console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sorter = FinalPettyCashSorter()
sorter.run(dry_run=True)
"
) else if "%choice%"=="2" (
    echo.
    echo Running LIVE UPDATE...
    venv\Scripts\python.exe -c "
from petty_cash_sorter_final import FinalPettyCashSorter
import logging

# Configure logging to show on console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sorter = FinalPettyCashSorter()
sorter.run(dry_run=False)
"
) else if "%choice%"=="3" (
    echo.
    echo Running RETRY FAILED TRANSACTIONS...
    call run_retry_failed.bat
) else if "%choice%"=="4" (
    echo.
    echo Generating FAILURE REPORT...
    call generate_failure_report.bat
) else (
    echo Invalid choice!
    goto :end
)

echo.
echo Process completed!
echo Check the logs for details.

:end
pause 