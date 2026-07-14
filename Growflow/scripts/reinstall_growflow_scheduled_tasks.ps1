# Re-register all Growflow scheduled tasks (pythonw direct — no PowerShell/CMD flash).
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$installers = @(
    "install_consignment_paid_off_watch_scheduled_task.ps1",
    "install_consignment_net_terms_watch_scheduled_task.ps1",
    "install_consignment_refresh_scheduled_task.ps1",
    "install_consignment_scheduled_task.ps1",
    "install_register_close_scheduled_task.ps1",
    "install_balance_misc_snapshot_scheduled_task.ps1",
    "install_petty_cash_snapshot_scheduled_task.ps1",
    "install_platform_scheduler.ps1"
)
foreach ($name in $installers) {
    $path = Join-Path $root "scripts\$name"
    if (-not (Test-Path $path)) {
        Write-Warning "Skip missing: $name"
        continue
    }
    Write-Host "==> $name"
    & $path
    Write-Host ""
}
