$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "."
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8791
