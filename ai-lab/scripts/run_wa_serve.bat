@echo off
REM Durable Worker Assistant start (worker-node / power-1).
set PYTHONPATH=C:\worker\worker_ai
set PYTHONUNBUFFERED=1
cd /d C:\worker\worker_ai
if not exist C:\worker\logs\worker_assistant mkdir C:\worker\logs\worker_assistant
C:\worker\worker_ai\.venv\Scripts\python.exe -u C:\worker\logs\worker_assistant\wa_serve.py
