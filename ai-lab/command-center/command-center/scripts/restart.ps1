# AI Lab Command Center - full stop then start (frontend + backend)
# Same flags as start.ps1
param([switch]$LocalOnly)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $ScriptDir "stop.ps1"
$StartScript = Join-Path $ScriptDir "start.ps1"

& $StopScript
Start-Sleep -Seconds 2

if ($LocalOnly) {
    & $StartScript -LocalOnly
} else {
    & $StartScript
}
