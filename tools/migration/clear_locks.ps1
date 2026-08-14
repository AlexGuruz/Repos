<#
.SYNOPSIS
  Clear migration file locks before folder moves.
  Stops robocopy, optional python workers under Repos, and prints Cursor guidance.
#>
param(
    [switch]$StopPythonUnderRepos,
    [switch]$Apply
)
$ErrorActionPreference = 'Continue'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
Write-MigLog "clear_locks root=$root Apply=$Apply"

# 1) Always safe: stop Robocopy
$robos = @(Get-Process Robocopy -ErrorAction SilentlyContinue)
foreach ($p in $robos) {
    Write-MigLog "Stop Robocopy PID $($p.Id)"
    if ($Apply) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
}

# 2) Stop migrate.ps1 child shells that are stuck (name match via command line if possible)
try {
    $procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'tools\\migration\\migrate\.ps1|tools\\migration\\edrive' }
    foreach ($p in $procs) {
        Write-MigLog "Stop migrate shell PID $($p.ProcessId)"
        if ($Apply) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    }
} catch {
    Write-MigLog "CIM process query skipped: $_" 'WARN'
}

# 3) Optional: stop python whose cwd/path is under Repos (can lock Growflow/Kylo)
if ($StopPythonUnderRepos) {
    Get-Process python,pythonw -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $path = $_.Path
            if ($path -and $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
                Write-MigLog "Stop python PID $($_.Id) ($path)"
                if ($Apply) { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
            }
        } catch { }
    }
}

Write-Host ""
Write-Host "=== MANUAL (Cursor / editors) ===" -ForegroundColor Yellow
Write-Host "1. Close tabs under E:\Repos\products\..., internal\..., tools\winpython (retired flat names no longer apply)"
Write-Host "2. Prefer opening ONLY E:\Repos\tools\migration until migrate finishes"
Write-Host "3. Disable file watchers on heavy folders if Syncthing is syncing Repos"
Write-Host "4. Re-run: .\clear_locks.ps1 -Apply   then   .\migrate.ps1 -Apply"
Write-Host ""

if (-not $Apply) {
    Write-MigLog "Dry-run only. Pass -Apply to stop processes." 'WARN'
} else {
    Write-MigLog "Locks cleared (process-level). Close Cursor tabs if Move-Item still fails."
}
