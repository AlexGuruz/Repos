@echo off
echo GENERATING FAILURE REPORT
echo =========================

cd /d "%~dp0"

echo.
echo Generating failure report...
python -c "
from petty_cash_sorter_final import FinalPettyCashSorter
import logging

# Configure logging to show on console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sorter = FinalPettyCashSorter()
report = sorter.generate_failure_report()

print('\n' + '='*60)
print('FAILURE REPORT')
print('='*60)
print(report)

# Also save to file
with open('pending_transactions/failure_report.txt', 'w') as f:
    f.write(report)
print('\nReport also saved to: pending_transactions/failure_report.txt')
"

echo.
echo Failure report generated!
pause 