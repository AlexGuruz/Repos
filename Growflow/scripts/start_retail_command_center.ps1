# Start full Retail Command Center stack (3 separate PowerShell windows).
# Wait 2-4 minutes after this script for ai-lab backend startup.
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Growflow = Split-Path -Parent $PSScriptRoot
$AilabBackend = "E:\Repos\ai-lab\command-center\command-center\backend"
$AilabFrontend = "E:\Repos\ai-lab\command-center\command-center\frontend"

Write-Host "=== Growflow Retail API (:8791) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Growflow'; `$env:PYTHONPATH='.'; python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8791"
)

Write-Host "=== ai-lab Command Center API (:8000) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$AilabBackend'; python -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

Write-Host "=== Command Center UI (:5173) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$AilabFrontend'; npm run dev -- --host 127.0.0.1 --port 5173"
)

Write-Host ""
Write-Host "Stack launching in separate windows. Allow 2-4 minutes for full startup." -ForegroundColor Yellow
Write-Host "Open: http://127.0.0.1:5173/ (Retail tab)" -ForegroundColor Green
Write-Host "Verify API: http://127.0.0.1:8000/api/retail/health" -ForegroundColor Green
Write-Host "See docs/RETAIL_COMMAND_CENTER_RUNBOOK.md" -ForegroundColor Gray

if (-not $NoBrowser) {
    Start-Sleep -Seconds 8
    Start-Process "http://127.0.0.1:5173/"
}
