# Retail Operations release gate (build + reconcile).
# Usage:
#   .\scripts\run_retail_release_gate.ps1 -Preset last_30_days -Compare `
#     -ReferenceCsv data\reference\growflow_retail_dashboard_export.csv
param(
    [string]$Preset = "last_30_days",
    [switch]$Compare,
    [string]$ReferenceCsv = "",
    [string]$ReferenceJson = "",
    [switch]$RequireReference,
    [switch]$SkipBuild,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "."

$argsList = @("--preset", $Preset)
if ($Compare) { $argsList += "--compare" }
if ($ReferenceCsv) { $argsList += @("--reference-csv", $ReferenceCsv) }
if ($ReferenceJson) { $argsList += @("--reference-json", $ReferenceJson) }
if ($RequireReference) { $argsList += "--require-reference" }
if ($SkipBuild) { $argsList += "--skip-build" }
if ($Strict) { $argsList += "--strict" }

python scripts/run_retail_release_gate.py @argsList
exit $LASTEXITCODE
