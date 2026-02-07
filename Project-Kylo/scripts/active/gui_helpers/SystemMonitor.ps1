# System Status Monitoring Functions
# Provides functions to check status of all Kylo systems

function Test-DockerAvailable {
    try {
        docker ps 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-DockerContainerStatus {
    param([string]$ContainerName)
    
    $status = @{
        Running = $false
        Status = "Unknown"
        Health = "Unknown"
        Uptime = $null
        Error = $null
    }
    
    if (-not (Test-DockerAvailable)) {
        $status.Error = "Docker not available"
        $status.Status = "Docker Not Available"
        return $status
    }
    
    try {
        $containerJson = docker ps -a --filter "name=$ContainerName" --format '{{json .}}' 2>&1
        if ($LASTEXITCODE -eq 0 -and $containerJson -and -not [string]::IsNullOrWhiteSpace($containerJson)) {
            $container = $containerJson | ConvertFrom-Json
            $status.Running = ($container.State -eq "running")
            $status.Status = $container.Status
            
            if ($status.Running) {
                $startedAt = docker inspect --format='{{.State.StartedAt}}' $ContainerName 2>&1
                if ($LASTEXITCODE -eq 0 -and $startedAt -and -not [string]::IsNullOrWhiteSpace($startedAt)) {
                    try {
                        $startTime = [DateTime]::Parse($startedAt)
                        $status.Uptime = (Get-Date) - $startTime
                    } catch {
                        $status.Uptime = $null
                    }
                }
            }
        } else {
            $status.Status = "Not Found"
            $status.Error = "Container not found"
        }
    } catch {
        $status.Error = $_.Exception.Message
        $status.Status = "Error"
    }
    
    return $status
}

function Test-PostgreSQLConnection {
    param([int]$Port = 5433)
    
    try {
        # Try using psql command first (more reliable)
        $result = & psql -h localhost -p $Port -U postgres -d postgres -c "SELECT 1;" 2>&1
        if ($LASTEXITCODE -eq 0) {
            return "Healthy"
        }
        return "Unhealthy"
    } catch {
        return "Unknown"
    }
}

function Test-RedpandaHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9644/v1/status/ready" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return if ($response.StatusCode -eq 200) { "Healthy" } else { "Unhealthy" }
    } catch {
        return "Unhealthy"
    }
}

function Get-PostgreSQLStatus {
    $status = @{
        ContainerName = "kylo-pg"
        Running = $false
        Status = "Unknown"
        Health = "Unknown"
        Uptime = $null
        Port = "5433"
        LastCheck = Get-Date
        Error = $null
    }
    
    if (-not (Test-DockerAvailable)) {
        $status.Status = "Docker Not Available"
        $status.Error = "Docker Desktop is not running"
        return $status
    }
    
    try {
        $containerJson = docker ps -a --filter "name=kylo-pg" --format '{{json .}}' 2>&1
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerJson)) {
            $status.Status = "Not Found"
            $status.Error = "Container not found"
            return $status
        }
        
        $container = $containerJson | ConvertFrom-Json
        
        $status.Running = ($container.State -eq "running")
        $status.Status = $container.Status
        
        if ($status.Running) {
            $startedAt = docker inspect --format='{{.State.StartedAt}}' "kylo-pg" 2>&1
            if ($LASTEXITCODE -eq 0 -and $startedAt -and -not [string]::IsNullOrWhiteSpace($startedAt)) {
                try {
                    $startTime = [DateTime]::Parse($startedAt)
                    $status.Uptime = (Get-Date) - $startTime
                } catch {
                    $status.Uptime = $null
                }
            }
            
            $status.Health = Test-PostgreSQLConnection -Port 5433
        } else {
            $status.Health = "Stopped"
        }
        
    } catch {
        $status.Status = "Error"
        $status.Error = $_.Exception.Message
    }
    
    return $status
}

function Get-RedpandaStatus {
    $status = @{
        ContainerName = "kylo-redpanda"
        Running = $false
        Status = "Unknown"
        Health = "Unknown"
        Uptime = $null
        Ports = "9092, 9644"
        LastCheck = Get-Date
        Error = $null
    }
    
    if (-not (Test-DockerAvailable)) {
        $status.Status = "Docker Not Available"
        $status.Error = "Docker Desktop is not running"
        return $status
    }
    
    try {
        $containerJson = docker ps -a --filter "name=kylo-redpanda" --format '{{json .}}' 2>&1
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerJson)) {
            $status.Status = "Not Found"
            $status.Error = "Container not found"
            return $status
        }
        
        $container = $containerJson | ConvertFrom-Json
        
        $status.Running = ($container.State -eq "running")
        $status.Status = $container.Status
        
        if ($status.Running) {
            $startedAt = docker inspect --format='{{.State.StartedAt}}' "kylo-redpanda" 2>&1
            if ($LASTEXITCODE -eq 0 -and $startedAt -and -not [string]::IsNullOrWhiteSpace($startedAt)) {
                try {
                    $startTime = [DateTime]::Parse($startedAt)
                    $status.Uptime = (Get-Date) - $startTime
                } catch {
                    $status.Uptime = $null
                }
            }
            
            $status.Health = Test-RedpandaHealth
        } else {
            $status.Health = "Stopped"
        }
        
    } catch {
        $status.Status = "Error"
        $status.Error = $_.Exception.Message
    }
    
    return $status
}

function Get-KafkaConsumerStatus {
    param([string]$ContainerName)
    
    $status = Get-DockerContainerStatus -ContainerName $ContainerName
    $status.ContainerName = $ContainerName
    $status.MessageCount = 0
    $status.LastMessage = "No messages"
    $status.Topic = if ($ContainerName -like "*txns*") { "txns.company.batches" } else { "rules.promote.batches" }
    
    # Parse log for message processing info
    if ($status.Running) {
        try {
            $logTail = docker logs --tail 50 $ContainerName 2>&1
            if ($LASTEXITCODE -eq 0) {
                $processedCount = ($logTail | Select-String -Pattern "Processed message|✅ Processed").Count
                $lastProcessed = $logTail | Select-String -Pattern "Processed message for company" | Select-Object -Last 1
                
                $status.MessageCount = $processedCount
                $status.LastMessage = if ($lastProcessed) { $lastProcessed.Line } else { "No messages" }
            }
        } catch {
            # Log parsing failed, continue with basic status
        }
    }
    
    return $status
}

function Get-WatcherStatus {
    $status = @{
        Running = $false
        PID = $null
        ProcessName = "watch_all"
        LastCheck = Get-Date
        WatchInterval = 300
        CompaniesWatched = "Unknown"
        LastActivity = $null
        LastActivityTime = $null
        Error = $null
    }
    
    # Check if process is running
    $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        try {
            $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            $cmdLine -like "*watch_all*"
        } catch {
            $false
        }
    }
    
    if ($processes.Count -gt 0) {
        $status.Running = $true
        $status.PID = $processes[0].Id
        $status.ProcessName = "python -m bin.watch_all"
        
        # Parse watch.log for last activity
        $logFile = "D:\Project-Kylo\.kylo\watch.log"
        if (Test-Path $logFile) {
            try {
                $lastLine = Get-Content $logFile -Tail 1 -ErrorAction SilentlyContinue
                if ($lastLine) {
                    $status.LastActivity = $lastLine
                    # Extract timestamp if present
                    if ($lastLine -match '\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
                        try {
                            $status.LastActivityTime = [DateTime]::Parse($matches[1])
                        } catch {}
                    }
                }
            } catch {}
        }
        
        # Get watch interval from environment or config
        $status.WatchInterval = [int]$env:KYLO_WATCH_INTERVAL_SECS
        if (-not $status.WatchInterval -or $status.WatchInterval -eq 0) { 
            $status.WatchInterval = 300 
        }
        
        # Get companies from config
        try {
            $configPath = "D:\Project-Kylo\config\companies.json"
            if (Test-Path $configPath) {
                $config = Get-Content $configPath | ConvertFrom-Json
                $status.CompaniesWatched = ($config.companies | ForEach-Object { $_.key }) -join ", "
            }
        } catch {
            $status.CompaniesWatched = "Unknown"
        }
    } else {
        $status.Error = "Process not found"
    }
    
    return $status
}

function Get-ScriptHubSyncStatus {
    $status = @{
        LastSync = $null
        NextSync = $null
        LastResult = "Unknown"
        RowsUpdated = 0
        SyncDuration = $null
        Error = $null
    }
    
    $logsDir = "D:\Project-Kylo\tools\scripthub_legacy\logs"
    if (-not (Test-Path $logsDir)) {
        $status.Error = "Logs directory not found"
        return $status
    }
    
    # Get most recent sync log
    $latestLog = Get-ChildItem "$logsDir\sync_log_*.log" -ErrorAction SilentlyContinue | 
        Sort-Object LastWriteTime -Descending | 
        Select-Object -First 1
    
    if ($latestLog) {
        $status.LastSync = $latestLog.LastWriteTime
        
        # Parse log for results
        try {
            $logContent = Get-Content $latestLog.FullName -Tail 50 -ErrorAction SilentlyContinue
            $summaryLine = $logContent | Select-String -Pattern "SUMMARY|SUCCESS|FAILED" | Select-Object -Last 1
            
            if ($summaryLine -and $summaryLine.Line -match "SUCCESS") {
                $status.LastResult = "Success"
            } elseif ($summaryLine -and $summaryLine.Line -match "FAILED") {
                $status.LastResult = "Failed"
            }
            
            # Extract rows updated
            $rowsLine = $logContent | Select-String -Pattern "rows|Updated|cells_written" | Select-Object -Last 1
            if ($rowsLine -and $rowsLine.Line -match '(\d+)\s*(rows|Updated|cells)') {
                $status.RowsUpdated = [int]$matches[1]
            }
            
            # Calculate next sync (5 minutes after last)
            $status.NextSync = $status.LastSync.AddMinutes(5)
        } catch {
            $status.Error = "Error parsing log: $_"
        }
    }
    
    return $status
}

function Get-SystemMonitorStatus {
    $status = @{
        Running = $false
        TaskName = "KyloSystemMonitor"
        ServicesMonitored = 7
        LastStatusCheck = $null
        Uptime = $null
        CheckInterval = 60
        Error = $null
    }
    
    # Check if scheduled task is running
    try {
        $task = Get-ScheduledTask -TaskName $status.TaskName -ErrorAction SilentlyContinue
        if ($task) {
            $status.Running = ($task.State -eq "Running" -or $task.State -eq "Ready")
            
            # Check if monitor process is running
            $monitorProcess = Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {
                try {
                    $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                    $cmdLine -like "*system_monitor*"
                } catch {
                    $false
                }
            }
            
            if ($monitorProcess) {
                $status.Running = $true
                $status.Uptime = (Get-Date) - $monitorProcess[0].StartTime
            }
        } else {
            $status.Error = "Scheduled task not found"
        }
    } catch {
        $status.Error = $_.Exception.Message
    }
    
    # Parse monitor.log for last check
    $monitorLog = "D:\Project-Kylo\.kylo\monitor.log"
    if (Test-Path $monitorLog) {
        try {
            $lastLine = Get-Content $monitorLog -Tail 1 -ErrorAction SilentlyContinue
            if ($lastLine -and $lastLine -match '\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
                try {
                    $status.LastStatusCheck = [DateTime]::Parse($matches[1])
                } catch {}
            }
        } catch {}
    }
    
    return $status
}

function Format-Uptime {
    param([TimeSpan]$Uptime)
    
    if (-not $Uptime) { return "N/A" }
    
    if ($Uptime.Days -gt 0) {
        return "$($Uptime.Days)d $($Uptime.Hours)h $($Uptime.Minutes)m"
    } elseif ($Uptime.Hours -gt 0) {
        return "$($Uptime.Hours)h $($Uptime.Minutes)m"
    } else {
        return "$($Uptime.Minutes)m $($Uptime.Seconds)s"
    }
}

# Functions are available after dot-sourcing this file

