# PowerShell script to start all Kylo services after system restart
# Run this from the project root directory

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Kylo System Services" -ForegroundColor Cyan
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

# Create Docker network for Kafka (must exist before Kafka compose)
$networkCheck = docker network inspect remodel_default 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Docker network 'remodel_default'..." -ForegroundColor Yellow
    docker network create remodel_default
}

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

# Step 5: Start Kafka consumers
Write-Host "Step 5: Starting Kafka consumers..." -ForegroundColor Yellow
& "$PSScriptRoot\scripts\active\start_kafka_consumers.ps1" -SheetsPost "0"
Write-Host "Kafka consumers started" -ForegroundColor Green

# Step 6: Start Kafka consumer containers (if using Docker)
Write-Host "Step 6: Starting Kafka consumer containers..." -ForegroundColor Yellow
$consumerArgs = @("-f", "docker-compose.kafka-consumer.yml")
if (Test-Path "docker-compose.kafka-consumer.override.yml") {
    $consumerArgs += @("-f", "docker-compose.kafka-consumer.override.yml")
}
docker compose @consumerArgs up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "Kafka consumer containers started" -ForegroundColor Green
} else {
    Write-Host "Warning: Kafka consumer containers may have failed to start" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services Status:" -ForegroundColor Yellow
Write-Host "  - PostgreSQL: docker ps | findstr kylo-pg" -ForegroundColor Gray
Write-Host "  - Redpanda: docker ps | findstr kylo-redpanda" -ForegroundColor Gray
Write-Host "  - Console: http://localhost:8080" -ForegroundColor Gray
Write-Host "  - Consumers: Get-Process python" -ForegroundColor Gray
Write-Host ""
Write-Host "To start the watch script (optional):" -ForegroundColor Yellow
Write-Host "  .\bin\watch.ps1" -ForegroundColor Gray
Write-Host ""

