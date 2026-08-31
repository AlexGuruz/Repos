@echo off
set PYTHONPATH=C:\worker\worker_ai
set PYTHONUNBUFFERED=1
cd /d C:\worker\worker_ai
del C:\worker\logs\worker_assistant\trace.txt 2>nul
C:\worker\worker_ai\.venv\Scripts\python.exe -u C:\worker\logs\worker_assistant\wa_serve.py
