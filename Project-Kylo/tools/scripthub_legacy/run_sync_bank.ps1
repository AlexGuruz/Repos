# Run Kylo Config -> BANK + CLEAN TRANSACTIONS sync.
# Reads rules from Kylo_Config tab (columns K/L), writes Company IDs to BANK sheet
# and to CLEAN TRANSACTIONS tab in the same workbook.
#
# Usage: .\run_sync_bank.ps1
#        .\run_sync_bank.ps1 -DryRun
#        .\run_sync_bank.ps1 -Limit 500

param(
    [switch]$DryRun,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$RepoRoot = (Split-Path -Parent (Split-Path -Parent $ScriptDir))
$PythonExe = if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") { "$RepoRoot\.venv\Scripts\python.exe" } else { "python" }
$SecretsPath = Join-Path $RepoRoot ".secrets\service_account.json"

Set-Location $ScriptDir
$env:PYTHONPATH = $ScriptDir
if (Test-Path $SecretsPath) {
    $env:GOOGLE_APPLICATION_CREDENTIALS = $SecretsPath
}

$args = @("sync_bank.py")
if ($DryRun) { $args += "--dry-run" }
if ($Limit -gt 0) { $args += "--limit"; $args += $Limit }

& $PythonExe @args
exit $LASTEXITCODE
