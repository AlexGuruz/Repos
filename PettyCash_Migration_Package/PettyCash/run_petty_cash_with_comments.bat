@echo off
echo ========================================
echo Petty Cash Processing with Comments
echo ========================================
echo.

echo Phase 1: Processing transactions...
python petty_cash_sorter_optimized.py
if %errorlevel% neq 0 (
    echo ERROR: Transaction processing failed!
    pause
    exit /b 1
)

echo.
echo Phase 2: Processing comments...
python comment_processor.py
if %errorlevel% neq 0 (
    echo WARNING: Comment processing had issues, but transactions were processed successfully.
    pause
    exit /b 0
)

echo.
echo ========================================
echo Processing completed successfully!
echo ========================================
pause 