# Log Viewer Functions
# Provides functions for log viewing, tailing, and filtering

# Global storage for log watchers and positions
$script:logWatchers = @{}
$script:logPositions = @{}
$script:dockerLogJobs = @{}

function Add-LogLine {
    param(
        [System.Windows.Forms.RichTextBox]$RichTextBox,
        [string]$Line,
        [System.Drawing.Color]$SystemColor
    )
    
    try {
        $RichTextBox.SelectionStart = $RichTextBox.TextLength
        $RichTextBox.SelectionLength = 0
        
    # Get theme if not available
    if (-not $script:theme) {
        $themeModule = Join-Path $PSScriptRoot "Theme.ps1"
        if (Test-Path $themeModule) {
            . $themeModule
            $script:theme = Get-Theme
        }
    }
    
    # Determine color based on log level
    $defaultTextColor = if ($script:theme) { $script:theme.Text } else { [System.Drawing.Color]::FromArgb(204, 204, 204) }
    $lineColor = $defaultTextColor
    
    if ($script:theme) {
        if ($Line -match '\[ERROR\]') {
            $lineColor = $script:theme.Status.Error
        } elseif ($Line -match '\[WARN\]|\[WARNING\]') {
            $lineColor = $script:theme.Status.Warning
        } elseif ($Line -match '\[SUCCESS\]') {
            $lineColor = $SystemColor
        } elseif ($Line -match '\[INFO\]') {
            # Dimmed system color
            $lineColor = [System.Drawing.Color]::FromArgb(
                [int]($SystemColor.R * 0.7),
                [int]($SystemColor.G * 0.7),
                [int]($SystemColor.B * 0.7)
            )
        }
    }
        
        # Highlight timestamp if present
        if ($Line -match '\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            $timestampStart = $RichTextBox.TextLength
            $RichTextBox.SelectionColor = $SystemColor
            $RichTextBox.AppendText($matches[0])
            $RichTextBox.SelectionColor = $lineColor
            $remainingText = $Line.Substring($matches[0].Length)
            $RichTextBox.AppendText($remainingText)
        } else {
            $RichTextBox.SelectionColor = $lineColor
            $RichTextBox.AppendText($Line)
        }
        
        $RichTextBox.AppendText("`r`n")
    } catch {
        Write-Warning "Error adding log line: $_"
    }
}

function Start-LogTailing {
    param(
        [string]$LogFile,
        [System.Windows.Forms.RichTextBox]$RichTextBox,
        [System.Drawing.Color]$SystemColor
    )
    
    if (-not (Test-Path $LogFile)) {
        Write-Warning "Log file not found: $LogFile"
        return $null
    }
    
    # Store last file position
    if (-not $script:logPositions.ContainsKey($LogFile)) {
        $script:logPositions[$LogFile] = (Get-Item $LogFile).Length
    }
    
    # Create FileSystemWatcher
    $watcher = New-Object System.IO.FileSystemWatcher
    $watcher.Path = Split-Path $LogFile -Parent
    $watcher.Filter = Split-Path $LogFile -Leaf
    $watcher.NotifyFilter = [System.IO.NotifyFilters]::Size -bor [System.IO.NotifyFilters]::LastWrite
    $watcher.EnableRaisingEvents = $true
    
    # Event handler
    $action = {
        $filePath = $Event.SourceEventArgs.FullPath
        $lastPos = $script:logPositions[$filePath]
        $currentSize = (Get-Item $filePath).Length
        
        # Handle file rotation (size decreased)
        if ($currentSize -lt $lastPos) {
            $lastPos = 0
        }
        
        if ($currentSize -gt $lastPos) {
            try {
                $stream = [System.IO.File]::Open($filePath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
                $stream.Position = $lastPos
                $reader = New-Object System.IO.StreamReader($stream)
                
                $newLines = @()
                while (-not $reader.EndOfStream) {
                    $line = $reader.ReadLine()
                    if ($line) {
                        $newLines += $line
                    }
                }
                
                $reader.Close()
                $stream.Close()
                
                # Update UI thread-safely
                $RichTextBox.Invoke([Action]{
                    foreach ($line in $newLines) {
                        Add-LogLine -RichTextBox $RichTextBox -Line $line -SystemColor $SystemColor
                    }
                    
                    # Check for auto-scroll (need to pass checkbox reference)
                    if ($script:autoScrollEnabled) {
                        $RichTextBox.SelectionStart = $RichTextBox.TextLength
                        $RichTextBox.ScrollToCaret()
                    }
                })
                
                $script:logPositions[$filePath] = $currentSize
            } catch {
                Write-Warning "Error reading log file: $_"
            }
        }
    }
    
    $eventHandler = Register-ObjectEvent -InputObject $watcher -EventName "Changed" -Action $action
    
    # Store watcher and handler for cleanup
    $script:logWatchers[$LogFile] = @{
        Watcher = $watcher
        Handler = $eventHandler
    }
    
    return $watcher
}

function Stop-LogTailing {
    param([string]$LogFile)
    
    if ($script:logWatchers -and $script:logWatchers.ContainsKey($LogFile)) {
        $watcherInfo = $script:logWatchers[$LogFile]
        $watcherInfo.Watcher.EnableRaisingEvents = $false
        $watcherInfo.Watcher.Dispose()
        Unregister-Event -SourceIdentifier $watcherInfo.Handler.Name -ErrorAction SilentlyContinue
        $script:logWatchers.Remove($LogFile)
    }
}

function Load-DockerLogs {
    param(
        [string]$ContainerName,
        [System.Windows.Forms.RichTextBox]$RichTextBox,
        [int]$Lines = 1000
    )
    
    if (-not (Test-DockerAvailable)) {
        $RichTextBox.Text = "Docker is not available"
        return
    }
    
    try {
        $RichTextBox.SuspendLayout()
        $RichTextBox.Clear()
        $RichTextBox.Text = "Loading logs..."
        $RichTextBox.Refresh()
        
        # Get logs using docker logs command
        $logOutput = docker logs --tail $Lines $ContainerName 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $systemColor = Get-ContainerSystemColor -ContainerName $ContainerName
            
            $RichTextBox.Clear()
            foreach ($line in $logOutput) {
                Add-LogLine -RichTextBox $RichTextBox -Line $line -SystemColor $systemColor
            }
        } else {
            $RichTextBox.Text = "Error loading logs: $logOutput"
        }
        
        $RichTextBox.ResumeLayout()
        $RichTextBox.SelectionStart = $RichTextBox.TextLength
        $RichTextBox.ScrollToCaret()
    } catch {
        $RichTextBox.Text = "Error: $_"
    }
}

function Get-ContainerSystemColor {
    param([string]$ContainerName)
    
    # Import theme if not already available
    if (-not $script:theme) {
        $themeModule = Join-Path $PSScriptRoot "Theme.ps1"
        if (Test-Path $themeModule) {
            . $themeModule
            $script:theme = Get-Theme
        }
    }
    
    if (-not $script:theme) {
        return [System.Drawing.Color]::FromArgb(204, 204, 204)  # Default gray
    }
    
    if ($ContainerName -like "*pg*" -or $ContainerName -like "*postgres*") {
        return $script:theme.Systems.PostgreSQL.Primary
    } elseif ($ContainerName -like "*redpanda*") {
        return $script:theme.Systems.Redpanda.Primary
    } elseif ($ContainerName -like "*kafka*") {
        return $script:theme.Systems.KafkaConsumer.Primary
    }
    
    return $script:theme.Text
}

function Start-DockerLogTailing {
    param(
        [string]$ContainerName,
        [System.Windows.Forms.RichTextBox]$RichTextBox,
        [System.Drawing.Color]$SystemColor
    )
    
    if (-not $script:dockerLogJobs) {
        $script:dockerLogJobs = @{}
    }
    
    # Stop existing job if any
    if ($script:dockerLogJobs.ContainsKey($ContainerName)) {
        Stop-Job $script:dockerLogJobs[$ContainerName] -ErrorAction SilentlyContinue
        Remove-Job $script:dockerLogJobs[$ContainerName] -ErrorAction SilentlyContinue
    }
    
    $job = Start-Job -ScriptBlock {
        param($ContainerName)
        
        docker logs --tail 10 --follow $ContainerName 2>&1 | ForEach-Object {
            $_
        }
    } -ArgumentList $ContainerName
    
    $script:dockerLogJobs[$ContainerName] = $job
    
    # Monitor job output using polling (jobs don't have OutputDataReceived event)
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 1000
    $timer.Add_Tick({
        if ($script:dockerLogJobs.ContainsKey($ContainerName)) {
            $job = $script:dockerLogJobs[$ContainerName]
            if ($job.State -eq "Running" -or $job.HasMoreData) {
                $output = Receive-Job $job -ErrorAction SilentlyContinue
                if ($output) {
                    $RichTextBox.Invoke([Action]{
                        foreach ($line in $output) {
                            Add-LogLine -RichTextBox $RichTextBox -Line $line -SystemColor $SystemColor
                        }
                        if ($script:autoScrollEnabled) {
                            $RichTextBox.SelectionStart = $RichTextBox.TextLength
                            $RichTextBox.ScrollToCaret()
                        }
                    })
                }
            }
        }
    })
    $timer.Start()
    
    # Store timer for cleanup
    $script:dockerLogTimers = @{}
    if (-not $script:dockerLogTimers) {
        $script:dockerLogTimers = @{}
    }
    $script:dockerLogTimers[$ContainerName] = $timer
}

function Stop-DockerLogTailing {
    param([string]$ContainerName)
    
    if ($script:dockerLogJobs -and $script:dockerLogJobs.ContainsKey($ContainerName)) {
        Stop-Job $script:dockerLogJobs[$ContainerName] -ErrorAction SilentlyContinue
        Remove-Job $script:dockerLogJobs[$ContainerName] -ErrorAction SilentlyContinue
        $script:dockerLogJobs.Remove($ContainerName)
    }
    
    if ($script:dockerLogTimers -and $script:dockerLogTimers.ContainsKey($ContainerName)) {
        $script:dockerLogTimers[$ContainerName].Stop()
        $script:dockerLogTimers[$ContainerName].Dispose()
        $script:dockerLogTimers.Remove($ContainerName)
    }
}

# Functions are available after dot-sourcing this file

