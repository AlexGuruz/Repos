@echo off
echo PETTY CASH SORTER - TASK SCHEDULER SETUP
echo ========================================
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

REM Delete existing task if it exists
schtasks /delete /tn "PettyCashSorterDaily" /f >nul 2>&1

REM Create new task
schtasks /create /tn "PettyCashSorterDaily" /tr "D:\ScriptHub\PettyCash\LOCKDOWN\daily_autorun.bat" /sc daily /st 00:00 /ru SYSTEM /f

if %errorLevel% == 0 (
    echo.
    echo SUCCESS: Task scheduler configured!
    echo.
    echo Task Details:
    echo - Name: PettyCashSorterDaily
    echo - Schedule: Daily at midnight (00:00)
    echo - Script: LOCKDOWN\daily_autorun.bat
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