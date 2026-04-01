# Starts Command Center (Vite + FastAPI). Safe to run from E:\Repos\ai-lab.
# Delegates to command-center/command-center/scripts/start.ps1 — see command-center/command-center/BOOT.md
param([switch]$LocalOnly)

$aiLabRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $aiLabRoot "command-center\command-center\scripts\start.ps1"
if (-not (Test-Path $target)) {
    Write-Error "Command Center start script not found: $target"
    exit 1
}
Write-Host "Delegating to: $target" -ForegroundColor DarkGray
if ($LocalOnly) {
    & $target -LocalOnly
} else {
    & $target
}
