@echo off
echo RETRYING FAILED PETTY CASH TRANSACTIONS
echo ======================================

cd /d "%~dp0"

echo.
echo Starting retry process...
python -c "
from petty_cash_sorter_final import FinalPettyCashSorter
import logging

# Configure logging to show on console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sorter = FinalPettyCashSorter()
sorter.retry_failed_cells(max_retries=3, retry_delay=5)

# Generate and display failure report
report = sorter.generate_failure_report()
print('\n' + '='*60)
print('FAILURE REPORT')
print('='*60)
print(report)
"

echo.
echo Retry process completed!
pause 