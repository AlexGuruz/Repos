# Service Control Functions
# Provides functions to start, stop, and restart services

function Start-DockerService {
    param(
        [string]$ServiceName,
        [string]$ComposeFile
    )
    
    try {
        Set-Location "D:\Project-Kylo"
        docker compose -f $ComposeFile up -d 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            return @{ Success = $true; Message = "Service started successfully" }
        } else {
            return @{ Success = $false; Message = "Failed to start service" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Stop-DockerService {
    param([string]$ServiceName)
    
    try {
        docker stop $ServiceName 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            return @{ Success = $true; Message = "Service stopped successfully" }
        } else {
            return @{ Success = $false; Message = "Failed to stop service" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Restart-DockerService {
    param(
        [string]$ServiceName,
        [string]$ComposeFile
    )
    
    try {
        docker restart $ServiceName 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            return @{ Success = $true; Message = "Service restarted successfully" }
        } else {
            return @{ Success = $false; Message = "Failed to restart service" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Start-AllDockerServices {
    try {
        Set-Location "D:\Project-Kylo"
        
        docker compose -f docker-compose.yml up -d 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { return @{ Success = $false; Message = "Failed to start PostgreSQL" } }
        
        docker compose -f docker-compose.kafka.yml up -d 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { return @{ Success = $false; Message = "Failed to start Redpanda" } }
        
        docker compose -f docker-compose.kafka-consumer.yml up -d 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { return @{ Success = $false; Message = "Failed to start Kafka consumers" } }
        
        return @{ Success = $true; Message = "All services started successfully" }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Stop-AllDockerServices {
    try {
        $containers = @("kylo-kafka-consumer-promote", "kylo-kafka-consumer-txns", "kylo-redpanda", "kylo-pg")
        foreach ($container in $containers) {
            docker stop $container 2>&1 | Out-Null
        }
        return @{ Success = $true; Message = "All services stopped successfully" }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Start-WatcherService {
    try {
        Set-Location "D:\Project-Kylo"
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
        
        # Check if started
        $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                $cmdLine -like "*watch_all*"
            } catch {
                $false
            }
        }
        
        if ($processes.Count -gt 0) {
            return @{ Success = $true; Message = "Watcher started successfully" }
        } else {
            return @{ Success = $false; Message = "Watcher failed to start" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Stop-WatcherService {
    try {
        $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                $cmdLine -like "*watch_all*"
            } catch {
                $false
            }
        }
        
        if ($processes.Count -gt 0) {
            $processes | Stop-Process -Force -ErrorAction SilentlyContinue
            return @{ Success = $true; Message = "Watcher stopped successfully" }
        } else {
            return @{ Success = $false; Message = "Watcher not running" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

function Run-ScriptHubSync {
    try {
        $scriptHubDir = "D:\Project-Kylo\tools\scripthub_legacy"
        $env:PYTHONPATH = $scriptHubDir
        
        $process = Start-Process -FilePath "python" `
            -ArgumentList "$scriptHubDir\run_both_syncs.py" `
            -WorkingDirectory $scriptHubDir `
            -NoNewWindow `
            -PassThru `
            -Wait `
            -Environment @{"PYTHONPATH"=$scriptHubDir}
        
        if ($process.ExitCode -eq 0) {
            return @{ Success = $true; Message = "Sync completed successfully" }
        } else {
            return @{ Success = $false; Message = "Sync failed with exit code $($process.ExitCode)" }
        }
    } catch {
        return @{ Success = $false; Message = "Error: $_" }
    }
}

# Functions are available after dot-sourcing this file

