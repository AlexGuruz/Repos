# Hidden scheduled-task runner: no console window. Logs to logs/register_close_taxes.log
$ErrorActionPreference = "Continue"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
if (-not $env:GROWFLOW_RETAIL_ORG) { $env:GROWFLOW_RETAIL_ORG = "nugzdispensary" }

$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "register_close_taxes.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$script = Join-Path $root "scripts\register_close_taxes_sheet.py"

try {
    $proc = Start-Process -FilePath $pythonw -ArgumentList "`"$script`" --once" `
        -WorkingDirectory $root.Path -WindowStyle Hidden -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        "[$ts] poll exit code $($proc.ExitCode)" | Add-Content -Path $logFile -Encoding utf8
    }
    exit $proc.ExitCode
}
catch {
    "[$ts] poll ERROR: $_" | Add-Content -Path $logFile -Encoding utf8
    exit 1
}
