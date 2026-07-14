# Hidden scheduled-task runner: no console window. Logs to logs/register_close_taxes.log
$ErrorActionPreference = "Continue"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $env:GROWFLOW_RETAIL_ORG) { $env:GROWFLOW_RETAIL_ORG = "nugzdispensary" }

$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "register_close_taxes.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    Set-Location $root
    $env:PYTHONPATH = $root.Path
    & python "scripts\register_close_taxes_sheet.py" --once
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        "[$ts] poll exit code $exitCode" | Add-Content -Path $logFile -Encoding utf8
    }
    exit $exitCode
}
catch {
    "[$ts] poll ERROR: $_" | Add-Content -Path $logFile -Encoding utf8
    exit 1
}
