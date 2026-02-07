@echo off
echo FILING SYSTEM INTEGRATION TEST
echo ==============================

python test_filing_integration.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ FILING SYSTEM INTEGRATION TEST PASSED
    echo The filing system is ready for production use.
) else (
    echo.
    echo ❌ FILING SYSTEM INTEGRATION TEST FAILED
    echo Please review the errors above before proceeding.
)

pause 