# Install repeating Scheduled Task for company inbox cleaner (label + archive + toast).
# Default: every 5 minutes. Run elevated if you need "whether user logged on or not".
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_company_inbox_cleaner_schedule.ps1 `
#     -AiLabRoot "E:\Repos\ai-lab" -EnvFile "C:\secrets\email_sorter_env.ps1"
#
param(
    [string]$TaskName = "AiLab-CompanyInboxCleaner",
    [string]$AiLabRoot = "",
    [string]$EnvFile = "",
    [int]$IntervalMinutes = 5,
    [switch]$DryRunDefault
)

$ErrorActionPreference = "Stop"
if (-not $AiLabRoot) {
    $AiLabRoot = Split-Path -Parent $PSScriptRoot
}
$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path
$runner = Join-Path $AiLabRoot "scripts\run_company_inbox_cleaner.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing runner: $runner"
}

$argList = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", "`"$runner`"",
    "-AiLabRoot", "`"$AiLabRoot`""
)
if ($EnvFile) {
    $argList += @("-EnvFile", "`"$EnvFile`"")
}
if ($DryRunDefault) {
    $argList += "-DryRun"
}

$argString = $argList -join " "
$ps = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $ps -Argument $argString

# Start soon, repeat every N minutes for a long finite window (MaxValue is rejected by schtasks).
$start = (Get-Date).AddMinutes(1)
$repeatFor = New-TimeSpan -Days 3650
$trig = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration $repeatFor
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trig -Settings $settings -Force `
    -Description "Company Gmail inbox cleaner: label + archive + Acheron toast every ${IntervalMinutes}m."

Write-Host "Registered: $TaskName"
Write-Host "  Every $IntervalMinutes minute(s)"
Write-Host "  Action: $ps $argString"
Write-Host "Verify:  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
