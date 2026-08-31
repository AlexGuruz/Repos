# Run backend in foreground - use this to see startup errors
# IMPORTANT: do not use --reload on Windows (zombie workers / wrong listener).
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$AI_LAB_ROOT = Split-Path -Parent (Split-Path -Parent $Root)
$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$backendDir = Join-Path $Root "backend"
$env:PYTHONPATH = $AI_LAB_ROOT
$env:OPERATOR_DESK_ENABLED = "1"
Set-Location $backendDir
& $venvPython -m uvicorn main:app --host 127.0.0.1 --port 8000
