# Restarts Command Center (stop ports 8000/5173, then start.ps1).
# Delegates to command-center/command-center/scripts/restart.ps1
param([switch]$LocalOnly)

$aiLabRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $aiLabRoot "command-center\command-center\scripts\restart.ps1"
if (-not (Test-Path $target)) {
    Write-Error "Command Center restart script not found: $target"
    exit 1
}
if ($LocalOnly) {
    & $target -LocalOnly
} else {
    & $target
}
