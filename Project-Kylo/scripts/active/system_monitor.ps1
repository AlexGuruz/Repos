# Comprehensive System Monitor
# Continuously monitors and ensures all required Kylo and ScriptHub services stay running
# This script runs in a loop, checking services every 60 seconds

param(
    [int]$CheckIntervalSeconds = 60,
    [int]$SyncIntervalMinutes = 5
)

Set-Location "D:\Project-Kylo"

# Setup logging
$logDir = ".\.kylo"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logFile = "$logDir\monitor.log"

# Rotate log if it gets too large (>10MB)
if (Test-Path $logFile) {
    $logSize = (Get-Item $logFile).Length
    if ($logSize -gt 10MB) {
        $backupFile = "$logFile.$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
        Move-Item $logFile $backupFile -Force
        # Keep only last 7 days of backups
        Get-ChildItem "$logDir\monitor.log.*" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Write-Host $logMessage
    Add-Content -Path $logFile -Value $logMessage -ErrorAction SilentlyContinue
}

# Function to check if a Docker container is running
function Test-DockerContainer {
    param([string]$ContainerName)
    try {
        $container = docker ps --filter "name=$ContainerName" --format "{{.Names}}" 2>&1
        return ($container -eq $ContainerName)
    } catch {
        return $false
    }
}

# Function to check if a process is running by command line pattern
function Test-ProcessRunning {
    param([string]$Pattern)
    try {
        $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                $cmdLine -like $Pattern
            } catch {
                $false
            }
        }
        return ($processes.Count -gt 0)
    } catch {
        return $false
    }
}

# Function to check if a service is accessible via HTTP
function Test-HttpService {
    param([string]$Url, [int]$TimeoutSeconds = 2)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        return ($response.StatusCode -eq 200)
    } catch {
        return $false
    }
}

# Function to start Docker services
function Start-KyloServices {
    Write-Log "Checking Docker services..."
    
    $requiredContainers = @{
        "kylo-pg" = @{ ComposeFile = "docker-compose.yml"; ServiceName = "PostgreSQL" }
        "kylo-redpanda" = @{ ComposeFile = "docker-compose.kafka.yml"; ServiceName = "Redpanda" }
        "kylo-kafka-consumer-txns" = @{ ComposeFile = "docker-compose.kafka-consumer.yml"; ServiceName = "Kafka Consumer (Txns)" }
        "kylo-kafka-consumer-promote" = @{ ComposeFile = "docker-compose.kafka-consumer.yml"; ServiceName = "Kafka Consumer (Promote)" }
    }
    
    # Group by compose file to avoid running the same file multiple times
    $composeFilesToRun = @{}
    $started = @()
    
    foreach ($container in $requiredContainers.Keys) {
        if (-not (Test-DockerContainer -ContainerName $container)) {
            $composeFile = $requiredContainers[$container].ComposeFile
            if (-not $composeFilesToRun.ContainsKey($composeFile)) {
                $composeFilesToRun[$composeFile] = @()
            }
            $composeFilesToRun[$composeFile] += $requiredContainers[$container].ServiceName
        }
    }
    
    # Run each compose file only once
    foreach ($composeFile in $composeFilesToRun.Keys) {
        $services = $composeFilesToRun[$composeFile] -join ", "
        Write-Log "Starting $services..."
        docker compose -f $composeFile up -d 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Started $services" -Level "SUCCESS"
            $started += $composeFile
        } else {
            Write-Log "Failed to start $services" -Level "ERROR"
        }
    }
    
    # Wait for Redpanda health check if we just started it
    if ($started -contains "docker-compose.kafka.yml") {
        Write-Log "Waiting for Redpanda to be healthy..."
        $maxAttempts = 30
        $attempt = 0
        while ($attempt -lt $maxAttempts) {
            if (Test-HttpService -Url "http://localhost:9644/v1/status/ready") {
                Write-Log "Redpanda is healthy" -Level "SUCCESS"
                break
            }
            Start-Sleep -Seconds 2
            $attempt++
        }
        if ($attempt -ge $maxAttempts) {
            Write-Log "Warning: Redpanda health check timeout" -Level "WARN"
        }
    }
    
    return $started.Count -gt 0
}

# Function to start watcher
function Start-Watcher {
    if (Test-ProcessRunning -Pattern "*watch_all*") {
        return $true
    }
    
    Write-Log "Starting Kylo watcher..."
    $watcherLogDir = ".\.kylo"
    if (!(Test-Path $watcherLogDir)) { New-Item -ItemType Directory -Force -Path $watcherLogDir | Out-Null }
    $logPath = "$watcherLogDir\watch.log"
    $tempDir = $env:TEMP
    $watcherWrapperFile = "$tempDir/kylo_watcher_wrapper.ps1"
    
    $watcherWrapperScript = "Set-Location `"D:\Project-Kylo`"`n"
    $watcherWrapperScript += "`$env:KYLO_WATCH_INTERVAL_SECS = `"300`"`n"
    $watcherWrapperScript += "`$env:PYTHONUNBUFFERED = `"1`"`n"
    $watcherWrapperScript += "python -u -m bin.watch_all *> `"$logPath`"`n"
    
    $watcherWrapperScript | Out-File -FilePath $watcherWrapperFile -Encoding UTF8
    $watcherProcess = Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-File", $watcherWrapperFile `
        -PassThru
    
    Start-Sleep -Seconds 3
    if (Test-ProcessRunning -Pattern "*watch_all*") {
        Write-Log "Watcher started successfully (PID: $($watcherProcess.Id))" -Level "SUCCESS"
        return $true
    } else {
        Write-Log "Failed to start watcher" -Level "ERROR"
        return $false
    }
}

# Function to start ScriptHub FastAPI server
function Start-ScriptHubServer {
    if (Test-HttpService -Url "http://localhost:8000/docs") {
        return $true
    }
    
    # Check if process is running but not responding
    if (Test-ProcessRunning -Pattern "*uvicorn*server*") {
        Write-Log "ScriptHub server process found but not responding, will restart..." -Level "WARN"
        # Kill existing process
        Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                $cmdLine -like "*uvicorn*server*"
            } catch {
                $false
            }
        } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    Write-Log "Starting ScriptHub FastAPI server..."
    $scriptHubDir = "D:\Project-Kylo\tools\scripthub_legacy"
    $logsDir = "$scriptHubDir\.logs"
    if (!(Test-Path $logsDir)) { New-Item -ItemType Directory -Force -Path $logsDir | Out-Null }
    $serverLog = "$logsDir\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
    
    $serverWrapperFile = "$env:TEMP\scriptHub_server_wrapper.ps1"
    $serverWrapperScript = "Set-Location `"$scriptHubDir`"`n"
    $serverWrapperScript += "`$env:PYTHONPATH = `"$scriptHubDir`"`n"
    $serverWrapperScript += "python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> `"$serverLog`"`n"
    
    $serverWrapperScript | Out-File -FilePath $serverWrapperFile -Encoding UTF8
    $serverProcess = Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-File", $serverWrapperFile `
        -PassThru
    
    Start-Sleep -Seconds 5
    if (Test-HttpService -Url "http://localhost:8000/docs") {
        Write-Log "ScriptHub server started successfully (PID: $($serverProcess.Id))" -Level "SUCCESS"
        return $true
    } else {
        Write-Log "Failed to start ScriptHub server or server not responding" -Level "ERROR"
        return $false
    }
}

# Function to run ScriptHub sync scripts
function Run-ScriptHubSyncs {
    Write-Log "Running ScriptHub sync scripts..."
    $scriptHubDir = "D:\Project-Kylo\tools\scripthub_legacy"
    $logsDir = "$scriptHubDir\logs"
    if (!(Test-Path $logsDir)) { New-Item -ItemType Directory -Force -Path $logsDir | Out-Null }
    $syncLog = "$logsDir\sync_log_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
    
    $env:PYTHONPATH = $scriptHubDir
    $syncScript = "$scriptHubDir\run_both_syncs.py"
    
    try {
        $errorLog = "$logsDir\sync_error_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
        $process = Start-Process -FilePath "python" `
            -ArgumentList $syncScript `
            -WorkingDirectory $scriptHubDir `
            -NoNewWindow `
            -RedirectStandardOutput $syncLog `
            -RedirectStandardError $errorLog `
            -PassThru `
            -Wait `
            -Environment @{"PYTHONPATH"=$scriptHubDir}
        
        if ($process.ExitCode -eq 0) {
            Write-Log "ScriptHub sync scripts completed successfully" -Level "SUCCESS"
            return $true
        } else {
            Write-Log "ScriptHub sync scripts failed with exit code $($process.ExitCode)" -Level "ERROR"
            if (Test-Path $errorLog) {
                $errorContent = Get-Content $errorLog -Tail 5 -ErrorAction SilentlyContinue
                if ($errorContent) {
                    Write-Log "Error output: $($errorContent -join '; ')" -Level "ERROR"
                }
            }
            return $false
        }
    } catch {
        Write-Log "Error running ScriptHub sync scripts: $_" -Level "ERROR"
        return $false
    }
}

# Main monitoring loop
function Main-Loop {
    Write-Log "=== System Monitor Started ===" -Level "INFO"
    Write-Log "Check interval: $CheckIntervalSeconds seconds" -Level "INFO"
    Write-Log "Sync interval: $SyncIntervalMinutes minutes" -Level "INFO"
    
    # Wait for Docker Desktop
    Write-Log "Waiting for Docker Desktop..."
    $maxWait = 120
    $waited = 0
    while ($waited -lt $maxWait) {
        try {
            docker ps | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Docker Desktop is ready" -Level "SUCCESS"
                break
            }
        } catch {
            # Docker not ready yet
        }
        Start-Sleep -Seconds 5
        $waited += 5
        if ($waited % 30 -eq 0) {
            Write-Log "Still waiting for Docker Desktop... ($waited/$maxWait seconds)" -Level "WARN"
        }
    }
    
    if ($waited -ge $maxWait) {
        Write-Log "ERROR: Docker Desktop did not start in time" -Level "ERROR"
        return
    }
    
    # Initial startup
    Write-Log "Performing initial service startup..."
    Start-KyloServices | Out-Null
    Start-Sleep -Seconds 5
    Start-Watcher | Out-Null
    # ScriptHub server is offline on purpose - skip startup
    # Start-ScriptHubServer | Out-Null
    
    # Track last sync time
    $lastSyncTime = Get-Date
    $lastStatusLog = Get-Date
    
    # Main monitoring loop
    Write-Log "Entering monitoring loop..." -Level "INFO"
    
    while ($true) {
        try {
            $now = Get-Date
            
            # Check Docker containers every loop - check all before restarting
            $containersOk = $true
            $requiredContainers = @("kylo-pg", "kylo-redpanda", "kylo-kafka-consumer-txns", "kylo-kafka-consumer-promote")
            $missingContainers = @()
            foreach ($container in $requiredContainers) {
                if (-not (Test-DockerContainer -ContainerName $container)) {
                    $missingContainers += $container
                    $containersOk = $false
                }
            }
            
            if ($missingContainers.Count -gt 0) {
                Write-Log "Containers not running: $($missingContainers -join ', '), attempting to start..." -Level "WARN"
                Start-KyloServices | Out-Null
            }
            
            # Check watcher every loop
            if (-not (Test-ProcessRunning -Pattern "*watch_all*")) {
                Write-Log "Watcher is not running, attempting to start..." -Level "WARN"
                Start-Watcher | Out-Null
            }
            
            # Check ScriptHub server every loop (optional - server may be offline on purpose)
            # Skip monitoring if server is intentionally offline
            # Uncomment below to enable ScriptHub server monitoring:
            # if (-not (Test-HttpService -Url "http://localhost:8000/docs")) {
            #     Write-Log "ScriptHub server is not responding, attempting to start..." -Level "WARN"
            #     Start-ScriptHubServer | Out-Null
            # }
            
            # Run sync scripts at specified interval
            $timeSinceLastSync = ($now - $lastSyncTime).TotalMinutes
            if ($timeSinceLastSync -ge $SyncIntervalMinutes) {
                Write-Log "Sync interval reached ($([math]::Round($timeSinceLastSync, 1)) minutes), running sync scripts..."
                Run-ScriptHubSyncs | Out-Null
                $lastSyncTime = $now
            }
            
            # Log status summary every 5 minutes
            $timeSinceLastStatus = ($now - $lastStatusLog).TotalMinutes
            if ($timeSinceLastStatus -ge 5) {
                Write-Log "=== Status Summary ===" -Level "INFO"
                Write-Log "Docker containers: $(if ($containersOk) { 'All running' } else { 'Some issues detected' })" -Level "INFO"
                Write-Log "Watcher: $(if (Test-ProcessRunning -Pattern "*watch_all*") { 'Running' } else { 'Not running' })" -Level "INFO"
                Write-Log "ScriptHub server: Offline (intentional)" -Level "INFO"
                Write-Log "Last sync: $([math]::Round($timeSinceLastSync, 1)) minutes ago" -Level "INFO"
                $lastStatusLog = $now
            }
            
        } catch {
            Write-Log "Error in monitoring loop: $_" -Level "ERROR"
        }
        
        Start-Sleep -Seconds $CheckIntervalSeconds
    }
}

# Handle Ctrl+C gracefully
$null = Register-EngineEvent PowerShell.Exiting -Action {
    Write-Log "=== System Monitor Stopped ===" -Level "INFO"
}

# Run main loop
try {
    Main-Loop
} catch {
    Write-Log "Fatal error: $_" -Level "ERROR"
    exit 1
}

