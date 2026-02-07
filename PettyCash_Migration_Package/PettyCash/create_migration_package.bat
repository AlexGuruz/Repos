@echo off
echo ========================================
echo PETTY CASH SORTER - MIGRATION PACKAGE
echo ========================================
echo.

echo Creating migration package...
echo.

REM Create migration directory
if not exist "PettyCash_Migration_Package" mkdir PettyCash_Migration_Package

REM Copy all files except venv and temporary files
echo Copying project files...
xcopy /E /I /H /Y /EXCLUDE:exclude_list.txt "." "PettyCash_Migration_Package"

REM Export current Python environment
echo.
echo Exporting Python environment...
venv\Scripts\pip freeze > PettyCash_Migration_Package\requirements_migration.txt

REM Create exclude list for next time
echo Creating exclude list...
(
echo venv\
echo __pycache__\
echo *.pyc
echo .git\
echo logs\*.log
echo temp\
echo test_*.py
echo *test*.py
echo backup_*
echo LOCKDOWN\
echo exports\
echo cache\
echo data\
echo reports\
) > exclude_list.txt

echo.
echo ========================================
echo MIGRATION PACKAGE CREATED SUCCESSFULLY!
echo ========================================
echo.
echo Package location: PettyCash_Migration_Package\
echo.
echo Next steps:
echo 1. Copy PettyCash_Migration_Package to your PC
echo 2. Follow the instructions in MIGRATION_PLAN.md
echo 3. Run create_migration_verification.py on your PC
echo.
pause 