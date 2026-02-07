# Manual start script that opens monitoring terminals
# Use this if you want to start manually instead of via Task Scheduler

Set-Location "D:\Project-Kylo"

Write-Host "Starting Kylo services with monitoring..." -ForegroundColor Cyan

# Run the auto-start script
& "$PSScriptRoot\auto_start_kylo.ps1" @args

Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

