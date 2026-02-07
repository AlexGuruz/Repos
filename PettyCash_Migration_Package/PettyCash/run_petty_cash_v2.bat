@echo off
echo ========================================
echo PETTY CASH SORTER V2
echo ========================================
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the petty cash sorter
python petty_cash_sorter_v2.py

REM Pause to see results
echo.
echo Press any key to exit...
pause > nul 