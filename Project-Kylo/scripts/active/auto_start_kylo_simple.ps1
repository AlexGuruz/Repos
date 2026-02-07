# Simple working version to get system running
$repoRoot = "D:\Project-Kylo"
Set-Location $repoRoot

$logDir = ".\.kylo\startup"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

Write-Log "=== Starting Kylo Services ==="

# Wait for Docker
Write-Log "Waiting for Docker Desktop..."
$waited = 0
while ($waited -lt 120) {
    try {
        docker ps | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
    } catch { }
    Start-Sleep -Seconds 5
    $waited += 5
}

# Start PostgreSQL
Write-Log "Starting PostgreSQL..."
docker compose -f docker-compose.yml up -d

# Start Kafka/Redpanda
Write-Log "Starting Kafka/Redpanda..."
docker compose -f docker-compose.kafka.yml up -d
Start-Sleep -Seconds 5

# Create network
docker network create remodel_default 2>&1 | Out-Null

# Create topics
Write-Log "Creating Kafka topics..."
& "$PSScriptRoot\kafka_topics.ps1" | Out-Null

# Start consumers
Write-Log "Starting Kafka consumers..."
docker compose -f docker-compose.kafka-consumer.yml up -d

# Start watcher
Write-Log "Starting Kylo watcher..."
$watcherRunning = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        $cmdLine -like "*watch_all*"
    } catch { $false }
}

if (-not $watcherRunning) {
    $logPath = ".\.kylo\watch.log"
    $env:KYLO_WATCH_INTERVAL_SECS = "300"
    $env:PYTHONUNBUFFERED = "1"
    
    # Create wrapper script to handle output redirection
    $wrapperScript = Join-Path $env:TEMP "kylo_watcher_wrapper.ps1"
    $scriptContent = @"
Set-Location "D:\Project-Kylo"
`$env:KYLO_WATCH_INTERVAL_SECS = "300"
`$env:PYTHONUNBUFFERED = "1"
python -u -m bin.watch_all *> "$logPath"
"@
    $scriptContent | Out-File -FilePath $wrapperScript -Encoding UTF8
    
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-File", $wrapperScript
    Write-Log "Watcher started"
} else {
    Write-Log "Watcher already running"
}

# Start ScriptHub server
Write-Log "Starting ScriptHub server..."
$scriptHubPath = Join-Path $repoRoot "tools\scripthub_legacy"
if (Test-Path $scriptHubPath) {
    $serverRunning = try { 
        $response = Invoke-WebRequest -Uri "http://localhost:8000/docs" -TimeoutSec 2 -UseBasicParsing -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        $response.StatusCode -eq 200
    } catch { $false }
    
    if (-not $serverRunning) {
        $serverLogPath = "$scriptHubPath\.logs"
        if (!(Test-Path $serverLogPath)) { New-Item -ItemType Directory -Force -Path $serverLogPath | Out-Null }
        $serverLogFile = "$serverLogPath\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
        
        Start-Job -ScriptBlock {
            param($path, $log)
            Set-Location $path
            $env:PYTHONPATH = $path
            python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> $log
        } -ArgumentList $scriptHubPath, $serverLogFile | Out-Null
        Write-Log "ScriptHub server started"
    } else {
        Write-Log "ScriptHub server already running"
    }
}

# Start sync runner
Write-Log "Starting sync runner..."
$syncLogDir = ".\.kylo\sync"
if (!(Test-Path $syncLogDir)) { New-Item -ItemType Directory -Force -Path $syncLogDir | Out-Null }
Start-Job -ScriptBlock {
    param($root, $logDir)
    Set-Location $root
    $env:KYLO_CONFIG_PATH = "config/global.yaml"
    $env:KYLO_SYNC_INTERVAL_SECS = "300"
    $env:PYTHONUNBUFFERED = "1"
    & "$root\.venv\Scripts\python.exe" -u .\tools\scripthub_legacy\sync_runner.py *> (Join-Path $logDir "sync_runner.log")
} -ArgumentList $repoRoot, $syncLogDir | Out-Null
Write-Log "Sync runner started"

Write-Log "=== Startup Complete ==="
Write-Log "Check Docker logs: docker compose logs -f"
Write-Log "Check watcher: Get-Content .\.kylo\watch.log -Tail 50 -Wait"

