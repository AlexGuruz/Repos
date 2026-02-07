@echo off
echo GOOGLE SHEETS XLSX DOWNLOADER - ONE TIME RUN
echo ============================================

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

REM Run downloader once
echo Running one-time download...
python google_sheets_downloader.py --once

pause 