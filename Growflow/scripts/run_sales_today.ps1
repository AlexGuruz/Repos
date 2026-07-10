# Today's sales (UTC) from GrowFlow Retail GraphQL. Run from normal Windows PowerShell.
# Requires: config/config.yaml with growflow.org_id, or set GROWFLOW_RETAIL_ORG.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
python scripts/_sales_today.py
