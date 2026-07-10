# One-shot poll (Windows Task Scheduler: run every 2-5 minutes)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
python scripts/register_close_taxes_sheet.py --once @args
