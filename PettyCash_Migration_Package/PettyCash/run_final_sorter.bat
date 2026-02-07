@echo off
echo ========================================
echo FINAL PETTY CASH SORTER
echo ========================================
echo.
echo This will process all PETTY CASH transactions
echo and sort them into target sheets using the
echo actual Excel files as the source of truth.
echo.
echo Press any key to start...
pause >nul

python petty_cash_sorter_final.py

echo.
echo ========================================
echo PROCESSING COMPLETE
echo ========================================
echo.
echo Check the logs/final_sorter.log file for details.
echo.
pause 