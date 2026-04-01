# Stops Command Center listeners on ports 8000 and 5173.
# Delegates to command-center/command-center/scripts/stop.ps1
param([int[]]$Ports = @(8000, 5173))

$aiLabRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $aiLabRoot "command-center\command-center\scripts\stop.ps1"
if (-not (Test-Path $target)) {
    Write-Error "Command Center stop script not found: $target"
    exit 1
}
& $target @PSBoundParameters
