@echo off
set PYTHONPATH=C:\worker\worker_ai
set PYTHONUNBUFFERED=1
cd /d C:\worker\worker_ai
del C:\worker\logs\worker_assistant\trace.txt 2>nul
del C:\worker\logs\worker_assistant\api.log 2>nul
start "WorkerAssistant" /B C:\worker\worker_ai\.venv\Scripts\python.exe -u C:\worker\logs\worker_assistant\wa_serve.py
ping -n 16 127.0.0.1 >nul
if exist C:\worker\logs\worker_assistant\trace.txt type C:\worker\logs\worker_assistant\trace.txt
echo ---HEALTH---
curl.exe -s -m 5 http://127.0.0.1:8765/health
echo.
echo ---NET---
netstat -ano | findstr LISTENING | findstr 8765
