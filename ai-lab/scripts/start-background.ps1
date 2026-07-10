# Starts Command Center backend + frontend hidden (logs under command-center/.logs/). See BOOT.md.
param([switch]$LocalOnly, [switch]$OpenBrowser)

$aiLabRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $aiLabRoot "command-center\command-center\scripts\start-background.ps1"
if (-not (Test-Path $target)) {
    Write-Error "Not found: $target"
    exit 1
}
Write-Host "Delegating to: $target" -ForegroundColor DarkGray
if ($LocalOnly -and $OpenBrowser) {
    & $target -LocalOnly -OpenBrowser
} elseif ($LocalOnly) {
    & $target -LocalOnly
} elseif ($OpenBrowser) {
    & $target -OpenBrowser
} else {
    & $target
}
