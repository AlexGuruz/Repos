# Register hidden Windows Scheduled Task: poll Register 1 close only during EOD window.
# Sun 8:00 PM - midnight (every 5 min). Mon-Sat 10:00 PM - 2:00 AM (every 5 min).
# Run: .\scripts\install_register_close_scheduled_task.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$taskName = "GrowflowRegisterCloseTaxes"

. (Join-Path $PSScriptRoot "scheduled_task_pythonw.ps1")
$action = New-GrowflowPythonwTaskAction `
    -Root $root.Path `
    -RelativeScript "scripts\register_close_taxes_sheet.py" `
    -ScriptArgs @("--once")

function New-WeeklyRepeatingTrigger {
    param(
        [System.DayOfWeek[]]$DaysOfWeek,
        [string]$At,
        [int]$IntervalMinutes,
        [int]$DurationHours
    )
    $weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $At
    $once = New-ScheduledTaskTrigger -Once -At $At `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration (New-TimeSpan -Hours $DurationHours)
    $weekly.Repetition = $once.Repetition
    return $weekly
}

# Sunday: start 8 PM Central, poll every 5 min for 4 hours (covers ~8 PM close).
$sundayTrigger = New-WeeklyRepeatingTrigger -DaysOfWeek Sunday -At "8:00PM" -IntervalMinutes 5 -DurationHours 4

# Mon-Sat: start 10 PM Central, poll every 5 min for 4 hours (covers ~10 PM close).
$weekdayTrigger = New-WeeklyRepeatingTrigger -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday, Saturday `
    -At "10:00PM" -IntervalMinutes 5 -DurationHours 4

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances Queue `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 8) `
    -Hidden

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger @($sundayTrigger, $weekdayTrigger) `
    -Settings $settings `
    -Description "GrowFlow Register 1 EOD close -> Taxes sheet. Sun 8-12 PM, Mon-Sat 10 PM-2 AM, every 5 min." `
    -RunLevel Limited | Out-Null

Write-Host "Installed scheduled task: $taskName"
Write-Host "  Sunday:    8:00 PM - midnight, every 5 min"
Write-Host "  Mon-Sat:   10:00 PM - 2:00 AM, every 5 min"
Write-Host "  Hidden (no CMD window)"
Write-Host "  Log: $(Join-Path $root 'logs\register_close_taxes.log')"
Write-Host ""
Write-Host "Verify: Get-ScheduledTaskInfo -TaskName $taskName"
Write-Host "Remove: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
