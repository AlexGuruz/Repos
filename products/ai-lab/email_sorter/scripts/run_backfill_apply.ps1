# Runs Gmail live sort (apply). Intended for Task Scheduler on the old rig.
# Optional: dot-source secrets before this script, or pass -EnvFile to a .ps1 that sets env vars.
param(
    [string]$AiLabRoot = "E:\Repos\products\ai-lab",
    [string]$PythonExe = "",
    [string]$EnvFile = "",
    [int]$Days = 120,
    [int]$Limit = 100
)

$ErrorActionPreference = "Stop"
$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path

if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
    . $EnvFile
}

if (-not $PythonExe) {
    $venvPy = Join-Path $AiLabRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        $PythonExe = $venvPy
    } else {
        $PythonExe = "python"
    }
}

$logDir = Join-Path $AiLabRoot "logs\email_sorter"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "backfill_apply_scheduled_$stamp.log"

Push-Location $AiLabRoot
try {
    & $PythonExe -m email_sorter.backfill --apply --days $Days --limit $Limit *>> $logPath
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
