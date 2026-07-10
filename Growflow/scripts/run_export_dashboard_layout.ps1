# Export full layout map (charts + sheet formatting sample) for the projection dashboard workbook.
# Prereq: copy config/dashboard_sheets.env.example -> config/dashboard_sheets.env and set STASHBOX_SERVICE_ACCOUNT.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $env:PYTHONPATH) { $env:PYTHONPATH = '.' }
if (-not (Test-Path 'config/dashboard_sheets.env')) {
    Write-Warning 'Missing config/dashboard_sheets.env — copy from config/dashboard_sheets.env.example and set STASHBOX_SERVICE_ACCOUNT.'
}
python scripts/export_projection_dashboard_layout.py --print @args
