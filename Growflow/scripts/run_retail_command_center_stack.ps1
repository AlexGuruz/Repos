# Start Growflow Retail API + print verification URLs.
# ai-lab backend and Command Center frontend must be started separately (see docs/RETAIL_COMMAND_CENTER_RUNBOOK.md).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "."

Write-Host "Starting Growflow Retail API on http://127.0.0.1:8791 ..."
Write-Host "Endpoints: /api/health /api/retail/dashboard /api/retail/capital /api/retail/consignment /api/retail/reconciliation"
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8791
