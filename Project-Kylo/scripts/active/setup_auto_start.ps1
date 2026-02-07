# Script to create Windows Task Scheduler job for auto-starting Kylo
# Run this once to set up auto-start on login

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Set-Location "D:\Project-Kylo"

$taskName = "Kylo Auto-Start"
$scriptPath = "D:\Project-Kylo\scripts\active\auto_start_kylo.ps1"

# Verify the script exists
if (!(Test-Path $scriptPath)) {
    Write-Host "ERROR: Auto-start script not found: $scriptPath" -ForegroundColor Red
    exit 1
}

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create the action (run the PowerShell script)
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory "D:\Project-Kylo"

# Create the trigger (on user login)
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# Create the principal (run as current user, highest privileges)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

# Register the task
Write-Host "Creating scheduled task: $taskName" -ForegroundColor Green
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Automatically starts all Kylo services (Docker, Kafka, consumers, watcher) and ScriptHub services on user login" | Out-Null

Write-Host ""
Write-Host "✅ Task Scheduler job created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Task Details:" -ForegroundColor Cyan
Write-Host "  Name: $taskName" -ForegroundColor Gray
Write-Host "  Trigger: On user login" -ForegroundColor Gray
Write-Host "  Script: $scriptPath" -ForegroundColor Gray
Write-Host ""
Write-Host "To manage the task:" -ForegroundColor Yellow
Write-Host "  - View: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  - Disable: Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  - Enable: Enable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  - Delete: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor Gray
Write-Host "  - Run now: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host ""
Write-Host "The task will run automatically the next time you log in." -ForegroundColor Green

