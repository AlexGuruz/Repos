@echo off
REM PETTY CASH SORTER - DAILY AUTORUN
REM Created: 2025-07-21 21:26:32
REM DO NOT MODIFY - LOCKED SYSTEM

cd /d "D:\ScriptHub\PettyCash"
echo Starting Petty Cash Sorter - 2025-07-21 21:26:32 >> "D:\ScriptHub\PettyCash\LOCKDOWN\autorun.log"

REM Run the main program
python petty_cash_sorter_final_comprehensive.py

echo Completed Petty Cash Sorter - 2025-07-21 21:26:32 >> "D:\ScriptHub\PettyCash\LOCKDOWN\autorun.log"
