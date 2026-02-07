$ErrorActionPreference = "Stop"

Set-Location "D:\Project-Kylo"

Write-Host "Stopping all hub-managed watcher instances..." -ForegroundColor Cyan
python .\bin\kylo_hub.py stop --all
Write-Host "Done. (If the hub process itself is running, stop it with Ctrl+C in its window.)" -ForegroundColor Gray

