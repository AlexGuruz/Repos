# Poll GrowFlow for Register 1 close; write Taxes tab in Google Sheet.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
python scripts/register_close_taxes_sheet.py --poll @args
