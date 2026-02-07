# PowerShell script to restart all Kylo services
# This stops everything and starts it back up

Set-Location "D:\Project-Kylo"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restarting Kylo System Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop all Python processes (Kafka consumers)
Write-Host "Step 1: Stopping Kafka consumers..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "Found $($pythonProcesses.Count) Python process(es), stopping..." -ForegroundColor Gray
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "Kafka consumers stopped" -ForegroundColor Green
} else {
    Write-Host "No Python processes found" -ForegroundColor Gray
}
Write-Host ""

# Step 2: Stop all Docker containers
Write-Host "Step 2: Stopping Docker containers..." -ForegroundColor Yellow
docker compose -f docker-compose.kafka-consumer.yml down 2>&1 | Out-Null
docker compose -f docker-compose.kafka.yml down 2>&1 | Out-Null
docker compose -f docker-compose.yml down 2>&1 | Out-Null
Write-Host "Docker containers stopped" -ForegroundColor Green
Start-Sleep -Seconds 3
Write-Host ""

# Step 3: Start all services using the startup script
Write-Host "Step 3: Starting all services..." -ForegroundColor Yellow
Write-Host ""
& ".\start_all_services.ps1"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "System restart complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

