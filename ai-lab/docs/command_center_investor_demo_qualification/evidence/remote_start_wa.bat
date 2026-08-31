@echo off
set PYTHONPATH=C:\worker\worker_ai
set PYTHONUNBUFFERED=1
cd /d C:\worker\worker_ai
start "WorkerAssistant" /MIN cmd /c "C:\worker\worker_ai\.venv\Scripts\python.exe -u C:\worker\logs\worker_assistant\wa_serve.py >> C:\worker\logs\worker_assistant\api.log 2>>&1"
timeout /t 12 /nobreak >nul
type C:\worker\logs\worker_assistant\trace.txt
echo ---
curl.exe -s -m 5 http://127.0.0.1:8765/health
echo.
netstat -ano | findstr :8765
