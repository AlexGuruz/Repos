# Simple startup with logs - starts services and shows Docker logs
Set-Location "D:\Project-Kylo"

# Start all Docker services
Write-Host "Starting Docker services..." -ForegroundColor Yellow
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.kafka.yml up -d
Start-Sleep -Seconds 5
docker network inspect remodel_default 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { docker network create remodel_default }
docker compose -f docker-compose.kafka-consumer.yml up -d

# Create topics
& "$PSScriptRoot\scripts\active\kafka_topics.ps1" @args

Write-Host "`n=== All services started! Showing logs (Ctrl+C to stop) ===`n" -ForegroundColor Green

# Show all logs
docker compose -f docker-compose.yml -f docker-compose.kafka.yml -f docker-compose.kafka-consumer.yml logs -f

