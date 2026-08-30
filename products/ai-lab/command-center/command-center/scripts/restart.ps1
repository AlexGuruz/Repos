# AI Lab Command Center - full stop then start (frontend + backend)
# Same flags as start.ps1
param(
    [switch]$LocalOnly,
    [switch]$FullMode,
    [switch]$Reload
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $ScriptDir "stop.ps1"
$StartScript = Join-Path $ScriptDir "start.ps1"

& $StopScript
Start-Sleep -Seconds 2

$startArgs = @()
if ($LocalOnly) { $startArgs += "-LocalOnly" }
if ($FullMode) { $startArgs += "-FullMode" }
if ($Reload) { $startArgs += "-Reload" }

if ($startArgs.Count -gt 0) {
    & $StartScript @startArgs
} else {
    & $StartScript
}
