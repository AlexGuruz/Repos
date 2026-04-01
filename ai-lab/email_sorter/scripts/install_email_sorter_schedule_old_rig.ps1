# Install two daily Scheduled Tasks on the OLD RIG (Windows) for email_sorter live apply.
# Runs twice per day during US daytime: default 10:00 and 14:00 LOCAL time on this machine
# (8-hour business band 09:00–17:00 if you use those defaults — adjust to your TZ).
#
# Run elevated:  powershell -ExecutionPolicy Bypass -File .\install_email_sorter_schedule_old_rig.ps1
#
param(
    [string]$TaskName = "AiLab-EmailSorter-BackfillApply",
    [string]$AiLabRoot = "E:\Repos\ai-lab",
    # First run (local clock on old rig)
    [string]$Run1Time = "10:00",
    # Second run (~4h later inside an 8h day band)
    [string]$Run2Time = "14:00",
    # Optional: path to a .ps1 that sets GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE, LLM_BASE_URL, etc.
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$runner = Join-Path $scriptDir "run_backfill_apply.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing runner script: $runner"
}

$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path

$argList = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", "`"$runner`"",
    "-AiLabRoot", "`"$AiLabRoot`""
)
if ($EnvFile) {
    $argList += @("-EnvFile", "`"$EnvFile`"")
}

$argString = $argList -join " "
$ps = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $ps -Argument $argString

# Daily triggers at fixed local times (machine timezone = "US daytime" if rig is in US)
$trig1 = New-ScheduledTaskTrigger -Daily -At $Run1Time
$trig2 = New-ScheduledTaskTrigger -Daily -At $Run2Time

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Run whether user logged on or not — requires stored password on first register, or use -User $env:USERNAME for current user.
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($trig1, $trig2) -Settings $settings -Force `
    -Description "Ai-lab email_sorter Gmail apply: 2x daily (old rig). Edit times in Task Scheduler if needed."

Write-Host "Registered: $TaskName"
Write-Host "  Daily at $Run1Time and $Run2Time (local time on this PC)"
Write-Host "  Action: $ps $argString"
Write-Host ""
Write-Host "Verify:  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
