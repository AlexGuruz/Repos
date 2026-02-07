# Setup Windows Task Scheduler - System Monitor
# Creates a task that runs the system monitor continuously
# The monitor ensures all services stay running and sync scripts execute periodically

$ErrorActionPreference = "Stop"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "ERROR: Administrator privileges required!" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run PowerShell as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Right-click PowerShell" -ForegroundColor Yellow
    Write-Host "2. Select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "3. Navigate to: D:\Project-Kylo" -ForegroundColor Yellow
    Write-Host "4. Run: .\scripts\setup_system_monitor.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETTING UP WINDOWS TASK SCHEDULER - SYSTEM MONITOR" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$ScriptDir = "D:\Project-Kylo"
$MonitorScript = Join-Path $ScriptDir "scripts\system_monitor.ps1"

if (-not (Test-Path $MonitorScript)) {
    Write-Host "ERROR: Monitor script not found: $MonitorScript" -ForegroundColor Red
    exit 1
}

# Task configuration
$TaskName = "KyloSystemMonitor"
$TaskDescription = "Continuously monitors and ensures all Kylo and ScriptHub services stay running. Restarts services if they stop and runs sync scripts periodically."

# Build the command
$Command = "powershell.exe"
$Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$MonitorScript`""

Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
Write-Host "Monitor Script: $MonitorScript" -ForegroundColor Yellow
Write-Host "Command: $Command $Arguments" -ForegroundColor Yellow
Write-Host ""

# Check if task already exists
try {
    $null = schtasks /Query /TN $TaskName 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Task already exists. Deleting existing task..." -ForegroundColor Yellow
        schtasks /Delete /TN $TaskName /F | Out-Null
        Start-Sleep -Seconds 2
    }
} catch {
    # Task doesn't exist, which is fine - we'll create it
}

# Create the task
Write-Host "Creating Windows Task Scheduler task..." -ForegroundColor Yellow

# Create task that runs on startup and user login
# We'll use multiple triggers: startup, logon, and periodic check
$result = schtasks /Create /TN $TaskName `
    /SC ONSTART `
    /RL HIGHEST `
    /F `
    /TR "$Command $Arguments" `
    /RU "SYSTEM" `
    /RP "" `
    /ST 00:00 `
    /SD "01/01/2000" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[FAILED] Failed to create task" -ForegroundColor Red
    Write-Host "Error: $result" -ForegroundColor Red
    Write-Host ""
    if ($result -match "Access is denied") {
        Write-Host "Note: This requires Administrator privileges. Please run PowerShell as Administrator." -ForegroundColor Yellow
    }
    exit 1
}

# Note: Task runs as SYSTEM for better startup reliability
# All paths in the monitor script are absolute, so SYSTEM user will work correctly
# If you need user-specific environment variables, uncomment below:
# Write-Host "Setting user context..." -ForegroundColor Yellow
# $logonResult = schtasks /Change /TN $TaskName /RU "$env:USERDOMAIN\$env:USERNAME" /RP "" 2>&1
# if ($LASTEXITCODE -ne 0) {
#     Write-Host "Warning: Could not set user context, using SYSTEM" -ForegroundColor Yellow
# }

# Configure task settings for continuous operation
Write-Host "Configuring task settings..." -ForegroundColor Yellow
schtasks /Change /TN $TaskName /ENABLE | Out-Null
schtasks /Change /TN $TaskName /RL HIGHEST | Out-Null

# Set task to restart if it fails
$xmlPath = "$env:TEMP\kylo_monitor_task.xml"
schtasks /Query /TN $TaskName /XML | Out-File -FilePath $xmlPath -Encoding UTF8

# Modify XML to add restart on failure
$xml = [xml](Get-Content $xmlPath)
$settings = $xml.Task.Settings
if ($null -eq $settings.RestartOnFailure) {
    $restartOnFailure = $xml.CreateElement("RestartOnFailure")
    $restartOnFailure.SetAttribute("Interval", "PT1M")
    $restartOnFailure.SetAttribute("Count", "3")
    $settings.AppendChild($restartOnFailure) | Out-Null
} else {
    $settings.RestartOnFailure.Interval = "PT1M"
    $settings.RestartOnFailure.Count = "3"
}

# Also ensure it doesn't stop if idle
if ($null -eq $settings.IdleSettings) {
    $idleSettings = $xml.CreateElement("IdleSettings")
    $idleSettings.SetAttribute("StopOnIdleEnd", "false")
    $settings.AppendChild($idleSettings) | Out-Null
}

$xml.Save($xmlPath) | Out-Null

# Delete and recreate with modified XML
schtasks /Delete /TN $TaskName /F | Out-Null
Start-Sleep -Seconds 1
schtasks /Create /TN $TaskName /XML $xmlPath /F | Out-Null
Remove-Item $xmlPath -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    schtasks /Query /TN $TaskName /V /FO LIST | Select-String -Pattern "Task Name|Status|Next Run|Triggers|Task To Run" | ForEach-Object { Write-Host $_ }
    Write-Host ""
    Write-Host "The system monitor will:" -ForegroundColor Green
    Write-Host "  - Start automatically on system startup" -ForegroundColor Green
    Write-Host "  - Start automatically on user logon" -ForegroundColor Green
    Write-Host "  - Monitor all services every 60 seconds" -ForegroundColor Green
    Write-Host "  - Run sync scripts every 5 minutes" -ForegroundColor Green
    Write-Host "  - Restart services if they stop" -ForegroundColor Green
    Write-Host "  - Restart itself if it fails (up to 3 times)" -ForegroundColor Green
    Write-Host ""
    Write-Host "To test it now, run: schtasks /Run /TN $TaskName" -ForegroundColor Yellow
    Write-Host "To view logs: Get-Content D:\Project-Kylo\.kylo\monitor.log -Tail 50" -ForegroundColor Yellow
    Write-Host "To disable it, run: schtasks /Change /TN $TaskName /DISABLE" -ForegroundColor Yellow
    Write-Host "To enable it, run: schtasks /Change /TN $TaskName /ENABLE" -ForegroundColor Yellow
    Write-Host "To delete it, run: schtasks /Delete /TN $TaskName /F" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "[FAILED] Failed to create task with advanced settings" -ForegroundColor Red
    Write-Host "Basic task may have been created. Check with: schtasks /Query /TN $TaskName" -ForegroundColor Yellow
    exit 1
}

