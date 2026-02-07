# PowerShell script to start all Kylo services with visible terminal logs
# Run this from the project root directory

Set-Location "D:\Project-Kylo"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Kylo System Services (with logs)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed"
    }
    Write-Host "Docker is running" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "ERROR: Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
Write-Host ""

# Step 1: Start PostgreSQL
Write-Host "Step 1: Starting PostgreSQL..." -ForegroundColor Yellow
docker compose -f docker-compose.yml up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start PostgreSQL" -ForegroundColor Red
    exit 1
}
Write-Host "PostgreSQL started" -ForegroundColor Green
Start-Sleep -Seconds 3

# Step 2: Start Kafka/Redpanda infrastructure
Write-Host "Step 2: Starting Kafka/Redpanda..." -ForegroundColor Yellow
docker compose -f docker-compose.kafka.yml up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start Kafka/Redpanda" -ForegroundColor Red
    exit 1
}
Write-Host "Kafka/Redpanda started" -ForegroundColor Green

# Step 3: Wait for Redpanda to be healthy
Write-Host "Step 3: Waiting for Redpanda to be healthy..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts -and -not $healthy) {
    Start-Sleep -Seconds 2
    $attempt++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9644/v1/status/ready" -TimeoutSec 2 -UseBasicParsing -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            Write-Host "Redpanda is healthy" -ForegroundColor Green
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

if (-not $healthy) {
    Write-Host ""
    Write-Host "Redpanda did not become healthy in time" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Create Kafka topics
Write-Host "Step 4: Creating Kafka topics..." -ForegroundColor Yellow
& "$PSScriptRoot\scripts\active\kafka_topics.ps1" @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Topic creation may have failed (topics might already exist)" -ForegroundColor Yellow
}

# Step 5: Start Kafka consumer containers (if using Docker)
Write-Host "Step 5: Starting Kafka consumer containers..." -ForegroundColor Yellow
# Create network if it doesn't exist
$networkCheck = docker network inspect remodel_default 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Docker network 'remodel_default'..." -ForegroundColor Yellow
    docker network create remodel_default
}
docker compose -f docker-compose.kafka-consumer.yml up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "Kafka consumer containers started" -ForegroundColor Green
} else {
    Write-Host "Warning: Kafka consumer containers may have failed to start" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All services started! Showing logs..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop viewing logs (services will continue running)" -ForegroundColor Yellow
Write-Host ""

# Show logs from all Docker services
docker compose -f docker-compose.yml -f docker-compose.kafka.yml -f docker-compose.kafka-consumer.yml logs -f

