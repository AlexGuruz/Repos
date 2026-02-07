$ErrorActionPreference = "Stop"

Set-Location "D:\Project-Kylo"

# Ensure hub uses layered config by default
$env:KYLO_CONFIG_PATH = "config/global.yaml"
$env:PYTHONUNBUFFERED = "1"

Write-Host "=== Kylo Hub (Supervisor) ===" -ForegroundColor Cyan
Write-Host "Registry: config/instances/index.yaml" -ForegroundColor Gray
Write-Host "Status: .kylo\\hub\\status.json" -ForegroundColor Gray
Write-Host "Log: .kylo\\hub\\hub.log" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the hub." -ForegroundColor Yellow

python -u .\bin\kylo_hub.py start --all

