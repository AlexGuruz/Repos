# Install always-on KYLO_2026_SANDBOX live intake mirror as a Scheduled Task.
# Daemon internal loop polls every 120s (config: sandbox_mirror.interval_seconds).
# Restart-if-dead guard every 5 min. Does NOT touch live KYLO watchers.
#
# Requires an elevated PowerShell if task registration returns Access Denied.
# Run:
#   .\scripts\active\install_sandbox_live_mirror.ps1
#
# If install fails without elevation, use the interactive starter instead:
#   .\scripts\active\start_sandbox_live_mirror.ps1
#   .\scripts\active\start_sandbox_live_mirror.ps1 -Hidden

$ErrorActionPreference = "Stop"

$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$taskName = "KyloSandboxLiveMirror"
$restartGuardMinutes = 5

function Resolve-Pythonw {
    $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $python = if (Test-Path $venvPy) { $venvPy } else {
        $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $cmd) { $cmd = Get-Command python -ErrorAction Stop }
        if ($cmd.Source) { $cmd.Source } else { $cmd.Definition }
    }
    $pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"
    if (Test-Path $pythonw) { return $pythonw }
    return $python
}

$pythonw = Resolve-Pythonw
$scriptPath = Join-Path $RepoRoot "scripts\sandbox_live_mirror_daemon.py"
if (-not (Test-Path $scriptPath)) {
    throw "Missing daemon script: $scriptPath"
}

# Ensure PYTHONPATH via a tiny wrapper env in WorkingDirectory; pythonw runs the daemon.
# Pass --interval from config default via script (reads yaml); no CLI override needed.
$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $RepoRoot

$atStartup = New-ScheduledTaskTrigger -AtStartup
$atLogon = New-ScheduledTaskTrigger -AtLogOn
$guard = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $restartGuardMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -Hidden

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Task needs PYTHONPATH; set via wrapper cmd that exports env then execs pythonw.
# Prefer a PowerShell action so we can set env without a separate .cmd file.
$psAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ("-NoProfile -WindowStyle Hidden -Command `"Set-Location '{0}'; `$env:PYTHONPATH='{0}'; `$env:KYLO_INSTANCE_ID='KYLO_2026_SANDBOX'; `$env:PYTHONUNBUFFERED='1'; & '{1}' '{2}'`"" -f $RepoRoot, $pythonw, $scriptPath)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $psAction `
    -Trigger @($atStartup, $atLogon, $guard) `
    -Settings $settings `
    -Description "Kylo sandbox live mirror: LIVE 2026 TRANSACTIONS/BANK (full rows incl NOTES/log) -> KYLO_2026_SANDBOX every 120s; rebuild BALANCE on change. Never writes live." `
    -RunLevel Limited | Out-Null

Write-Host "Installed scheduled task: $taskName" -ForegroundColor Green
Write-Host "  Always-on daemon (internal 120s loop); restart-if-dead every $restartGuardMinutes min"
Write-Host "  Heartbeat: $(Join-Path $RepoRoot '.kylo\instances\KYLO_2026_SANDBOX\health\sandbox_mirror.json')"
Write-Host "  Log:       $(Join-Path $RepoRoot '.kylo\instances\KYLO_2026_SANDBOX\logs\sandbox_mirror.log')"
Write-Host ""
Write-Host "Start now: Start-ScheduledTask -TaskName $taskName"
Write-Host "Verify:    Get-ScheduledTaskInfo -TaskName $taskName"
Write-Host "Remove:    Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
Write-Host ""
Write-Host "Or run interactively: .\scripts\active\start_sandbox_live_mirror.ps1"
