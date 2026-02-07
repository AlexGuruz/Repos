@echo off
echo ========================================
echo PETTY CASH SORTER - COPY TO DESKTOP
echo ========================================
echo.

echo Creating complete copy for desktop transfer...
echo.

REM Create desktop transfer folder
if not exist "PettyCash_For_Desktop" mkdir PettyCash_For_Desktop

REM Copy EVERYTHING including database, venv, and all files
echo Copying complete project (including database and virtual environment)...
xcopy /E /I /H /Y "." "PettyCash_For_Desktop"

echo.
echo ========================================
echo COPY COMPLETE!
echo ========================================
echo.
echo Folder created: PettyCash_For_Desktop\
echo.
echo Next steps:
echo 1. Copy PettyCash_For_Desktop folder to your desktop PC
echo 2. On desktop PC, navigate to the folder
echo 3. Run: venv\Scripts\activate
echo 4. Run: python demo_rule_management.py
echo 5. Open browser to: http://localhost:5000
echo.
echo That's it! Everything including your database will work.
echo.
pause 