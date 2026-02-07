# Smart restart script - detects code changes and restarts only affected services
param(
    [switch]$Force,  # Force restart all services regardless of changes
    [switch]$CheckOnly  # Only check what would be restarted, don't actually restart
)

Set-Location "D:\Project-Kylo"

$stateFile = ".\.kylo\code_change_state.json"
$stateDir = ".\.kylo"
if (!(Test-Path $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }

# Service-to-code mapping
$serviceCodeMap = @{
    "kafka-consumer-txns" = @{
        Type = "docker"
        ContainerName = "kylo-kafka-consumer-txns"
        CodePaths = @(
            "services/bus/kafka_consumer_txns.py",
            "services/bus/",
            "services/common/",
            "services/sheets/",
            "telemetry/",
            "config/",
            "requirements-kafka.txt"
        )
        RequiresRebuild = $true
    }
    "kafka-consumer-promote" = @{
        Type = "docker"
        ContainerName = "kylo-kafka-consumer-promote"
        CodePaths = @(
            "services/bus/kafka_consumer_promote.py",
            "services/bus/",
            "services/common/",
            "services/rules/",
            "telemetry/",
            "config/",
            "requirements-kafka.txt"
        }
        RequiresRebuild = $true
    }
    "kylo-watcher" = @{
        Type = "process"
        ProcessPattern = "*watch_all*"
        CodePaths = @(
            "bin/watch_all.py",
            "bin/sort_and_post_from_jgdtruth.py",
            "services/rules/",
            "services/sheets/",
            "services/intake/",
            "services/common/",
            "config/",
            "requirements.txt"
        )
        RequiresRebuild = $false
    }
    "scriptHub-server" = @{
        Type = "process"
        ProcessPattern = "*uvicorn*server*"
        CodePaths = @(
            "D:\Project-Kylo\tools\scripthub_legacy\server.py",
            "D:\Project-Kylo\tools\scripthub_legacy\src\",
            "D:\Project-Kylo\tools\scripthub_legacy\config\",
            "D:\Project-Kylo\tools\scripthub_legacy\requirements.txt"
        )
        RequiresRebuild = $false
    }
}

# Function to get file modification time
function Get-FileHash {
    param([string]$FilePath)
    if (Test-Path $FilePath) {
        $file = Get-Item $FilePath
        return @{
            Path = $FilePath
            LastWriteTime = $file.LastWriteTime.Ticks
            Size = $file.Length
        }
    }
    return $null
}

# Function to check if code has changed for a service
function Test-ServiceCodeChanged {
    param(
        [string]$ServiceName,
        [hashtable]$ServiceConfig
    )
    
    if ($Force) {
        return $true
    }
    
    # Load previous state
    $previousState = @{}
    if (Test-Path $stateFile) {
        try {
            $content = Get-Content $stateFile -Raw | ConvertFrom-Json
            $previousState = @{}
            $content.PSObject.Properties | ForEach-Object {
                $previousState[$_.Name] = $_.Value
            }
        } catch {
            # If we can't read state, assume changes
            return $true
        }
    }
    
    # Check each code path
    foreach ($codePath in $ServiceConfig.CodePaths) {
        $fullPath = if ([System.IO.Path]::IsPathRooted($codePath)) {
            $codePath
        } else {
            Join-Path "D:\Project-Kylo" $codePath
        }
        
        # Check if it's a file or directory
        if (Test-Path $fullPath) {
            $item = Get-Item $fullPath
            if ($item.PSIsContainer) {
                # Directory - check all Python files recursively
                $files = Get-ChildItem -Path $fullPath -Recurse -Include *.py,*.txt,*.json -ErrorAction SilentlyContinue
                foreach ($file in $files) {
                    $fileHash = Get-FileHash -FilePath $file.FullName
                    if ($null -eq $fileHash) { continue }
                    
                    $stateKey = $file.FullName
                    
                    if ($previousState.ContainsKey($stateKey)) {
                        $prevHash = $previousState[$stateKey]
                        if ($fileHash.LastWriteTime -ne $prevHash.LastWriteTime -or $fileHash.Size -ne $prevHash.Size) {
                            Write-Host "  [CHANGE] $($file.FullName)" -ForegroundColor Yellow
                            return $true
                        }
                    } else {
                        Write-Host "  [NEW] $($file.FullName)" -ForegroundColor Cyan
                        return $true
                    }
                }
            } else {
                # Single file
                $fileHash = Get-FileHash -FilePath $fullPath
                if ($null -eq $fileHash) { continue }
                
                $stateKey = $fullPath
                
                if ($previousState.ContainsKey($stateKey)) {
                    $prevHash = $previousState[$stateKey]
                    if ($fileHash.LastWriteTime -ne $prevHash.LastWriteTime -or $fileHash.Size -ne $prevHash.Size) {
                        Write-Host "  [CHANGE] $fullPath" -ForegroundColor Yellow
                        return $true
                    }
                } else {
                    Write-Host "  [NEW] $fullPath" -ForegroundColor Cyan
                    return $true
                }
            }
        }
    }
    
    return $false
}

# Function to save current state
function Save-CodeState {
    $currentState = @{}
    
    foreach ($serviceName in $serviceCodeMap.Keys) {
        $serviceConfig = $serviceCodeMap[$serviceName]
        foreach ($codePath in $serviceConfig.CodePaths) {
            $fullPath = if ([System.IO.Path]::IsPathRooted($codePath)) {
                $codePath
            } else {
                Join-Path "D:\Project-Kylo" $codePath
            }
            
            if (Test-Path $fullPath) {
                $item = Get-Item $fullPath
                if ($item.PSIsContainer) {
                    $files = Get-ChildItem -Path $fullPath -Recurse -Include *.py,*.txt,*.json -ErrorAction SilentlyContinue
                    foreach ($file in $files) {
                        $fileHash = Get-FileHash -FilePath $file.FullName
                        if ($null -ne $fileHash) {
                            $currentState[$file.FullName] = $fileHash
                        }
                    }
                } else {
                    $fileHash = Get-FileHash -FilePath $fullPath
                    if ($null -ne $fileHash) {
                        $currentState[$fullPath] = $fileHash
                    }
                }
            }
        }
    }
    
    $currentState | ConvertTo-Json -Depth 10 | Out-File -FilePath $stateFile -Encoding UTF8
}

# Main logic
Write-Host "=== Smart Service Restart ===" -ForegroundColor Cyan
Write-Host ""

$servicesToRestart = @()

foreach ($serviceName in $serviceCodeMap.Keys) {
    $serviceConfig = $serviceCodeMap[$serviceName]
    Write-Host "Checking $serviceName..." -ForegroundColor Yellow
    
    $hasChanges = Test-ServiceCodeChanged -ServiceName $serviceName -ServiceConfig $serviceConfig
    
    if ($hasChanges) {
        Write-Host "  → Code changed, needs restart" -ForegroundColor Red
        $servicesToRestart += $serviceName
    } else {
        Write-Host "  → No changes, skipping" -ForegroundColor Green
    }
}

Write-Host ""

if ($servicesToRestart.Count -eq 0) {
    Write-Host "No services need to be restarted." -ForegroundColor Green
    if (-not $CheckOnly) {
        Save-CodeState
    }
    exit 0
}

Write-Host "Services to restart: $($servicesToRestart.Count)" -ForegroundColor Cyan
foreach ($service in $servicesToRestart) {
    Write-Host "  - $service" -ForegroundColor Yellow
}

if ($CheckOnly) {
    Write-Host "`nCheck-only mode: Not restarting services." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nRestarting services..." -ForegroundColor Cyan

foreach ($serviceName in $servicesToRestart) {
    $serviceConfig = $serviceCodeMap[$serviceName]
    
    Write-Host "`nRestarting $serviceName..." -ForegroundColor Yellow
    
    if ($serviceConfig.Type -eq "docker") {
        if ($serviceConfig.RequiresRebuild) {
            Write-Host "  Rebuilding Docker image..." -ForegroundColor Gray
            docker compose -f docker-compose.kafka-consumer.yml build $serviceName
        }
        Write-Host "  Restarting container..." -ForegroundColor Gray
        docker compose -f docker-compose.kafka-consumer.yml up -d $serviceName
    } elseif ($serviceConfig.Type -eq "process") {
        # Stop the process
        $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                $cmdLine -like $serviceConfig.ProcessPattern
            } catch {
                $false
            }
        }
        
        if ($processes) {
            Write-Host "  Stopping process(es)..." -ForegroundColor Gray
            $processes | Stop-Process -Force
            Start-Sleep -Seconds 2
        }
        
        # Restart using auto_start script logic
        if ($serviceName -eq "kylo-watcher") {
            Write-Host "  Starting watcher..." -ForegroundColor Gray
            $watcherLogDir = ".\.kylo"
            if (!(Test-Path $watcherLogDir)) { New-Item -ItemType Directory -Force -Path $watcherLogDir | Out-Null }
            $logPath = "$watcherLogDir\watch.log"
            
            $watcherWrapperScript = @"
Set-Location "D:\Project-Kylo"
`$env:KYLO_WATCH_INTERVAL_SECS = "300"
`$env:PYTHONUNBUFFERED = "1"
python -u -m bin.watch_all *> "$logPath"
"@
            
            $tempDir = $env:TEMP
            $watcherWrapperFile = "$tempDir/kylo_watcher_wrapper.ps1"
            $watcherWrapperScript | Out-File -FilePath $watcherWrapperFile -Encoding UTF8
            Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-File", $watcherWrapperFile -PassThru | Out-Null
        } elseif ($serviceName -eq "scriptHub-server") {
            Write-Host "  Starting ScriptHub server..." -ForegroundColor Gray
            $scriptHubPath = "D:\Project-Kylo\tools\scripthub_legacy"
            $serverLogPath = "$scriptHubPath\.logs"
            if (!(Test-Path $serverLogPath)) { New-Item -ItemType Directory -Force -Path $serverLogPath | Out-Null }
            $serverLogFile = "$serverLogPath\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
            
            Start-Job -ScriptBlock {
                param($scriptHubPath, $logFile)
                Set-Location $scriptHubPath
                $env:PYTHONPATH = $scriptHubPath
                python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> $logFile
            } -ArgumentList $scriptHubPath, $serverLogFile | Out-Null
        }
    }
}

# Save new state after restart
Save-CodeState

Write-Host "`n=== Restart Complete ===" -ForegroundColor Green

