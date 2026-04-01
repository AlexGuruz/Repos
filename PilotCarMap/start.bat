@echo off
cd /d "%~dp0"
echo Starting PilotCar Loads Map...
start "PilotCar Poller" cmd /c "python poller.py"
timeout /t 2 /nobreak >nul
start "PilotCar Server" cmd /c "python server.py"
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8080
echo Browser opened. Close this window when done; poller and server run in separate windows.
