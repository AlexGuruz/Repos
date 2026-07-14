# Install Growflow Ops Platform scheduled tasks (Task Scheduler).
# Cadence matches GROWFLOW_OPS_PLATFORM.md:
#   ingest ~2h, dashboard/consign/status ~4h, daily transfers+capital+projection, nightly CC/BI

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$pyw = Join-Path $root "scripts\scheduled_task_pythonw.ps1"
if (-not (Test-Path $pyw)) {
    Write-Error "Missing scheduled_task_pythonw.ps1"
}

function Register-GrowflowPyTask {
    param(
        [string]$TaskName,
        [string]$ScriptRel,
        [string]$Args,
        [string]$TriggerDescription,
        [scriptblock]$TriggerFactory
    )
    $scriptPath = Join-Path $root $ScriptRel
    if (-not (Test-Path $scriptPath)) {
        Write-Warning "Skip missing script: $ScriptRel"
        return
    }
    $actionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$pyw`" `"$scriptPath`" $Args"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs -WorkingDirectory $root
    $triggers = & $TriggerFactory
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Registered $TaskName ($TriggerDescription)"
}

# Every 2 hours — incremental fact ingest
Register-GrowflowPyTask -TaskName "GrowflowPlatformIngest2h" -ScriptRel "scripts\ingest_growflow_facts.py" -Args "--days 14" -TriggerDescription "every 2h" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(6) -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 3650))
}

# Every 4 hours — dashboard + consign JSON + status via orchestrator (no live GraphQL if facts fresh enough for build)
Register-GrowflowPyTask -TaskName "GrowflowPlatformDashboard4h" -ScriptRel "scripts\run_platform_orchestrator.py" -Args "--kind full --days 30 --preset last_30_days --no-capital" -TriggerDescription "every 4h" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) -RepetitionInterval (New-TimeSpan -Hours 4) -RepetitionDuration (New-TimeSpan -Days 3650))
}

# Daily 05:30 — transfer receipts rebuild
Register-GrowflowPyTask -TaskName "GrowflowPlatformTransfersDaily" -ScriptRel "scripts\build_transfer_receipts_db.py" -Args "" -TriggerDescription "daily 05:30" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Daily -At 5:30am)
}

# Daily 06:00 — capital rebuild from existing layer2 (buy-plan refresh separate/manual or weekly)
Register-GrowflowPyTask -TaskName "GrowflowPlatformCapitalDaily" -ScriptRel "scripts\build_retail_capital.py" -Args "" -TriggerDescription "daily 06:00" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Daily -At 6:00am)
}

# EOD projection mid-day + late afternoon
Register-GrowflowPyTask -TaskName "GrowflowPlatformProjectionMidday" -ScriptRel "scripts\run_daily_sales_projection.py" -Args "" -TriggerDescription "daily 13:00" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Daily -At 1:00pm)
}
Register-GrowflowPyTask -TaskName "GrowflowPlatformProjectionPreclose" -ScriptRel "scripts\run_daily_sales_projection.py" -Args "" -TriggerDescription "daily 17:00" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Daily -At 5:00pm)
}

# Nightly country cannabis
$ccInstaller = Join-Path $root "scripts\install_country_cannabis_nightly_task.ps1"
if (Test-Path $ccInstaller) {
    Write-Host "==> install_country_cannabis_nightly_task.ps1"
    & $ccInstaller
}

# Nightly company BI report (facts-only OK even without sheets)
Register-GrowflowPyTask -TaskName "GrowflowPlatformCompanyBiNightly" -ScriptRel "scripts\build_company_bi_report.py" -Args "--months 6" -TriggerDescription "daily 02:15" -TriggerFactory {
    @(New-ScheduledTaskTrigger -Daily -At 2:15am)
}

Write-Host "Platform scheduler install complete."
