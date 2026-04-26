# Run GrowFlow stock-pool allocation (Retail GraphQL needs org slug).
# Default org matches docs/GROWFLOW_RETAIL_SCHEMA_MAP.md — override if yours differs.
# Usage:
#   .\scripts\run_stock_pool_allocation.ps1
#   .\scripts\run_stock_pool_allocation.ps1 -RetailOrg "yourorg" -Pool 18000 -Days 365
param(
    [double] $Pool = 18000,
    [int] $Days = 365,
    [string] $Credentials = "E:/secrets/gcp/growflowapi.txt",
    [string] $Csv = "data/stock_pool_by_brand.csv",
    [string] $RetailOrg = "nugzdispensary",
    [string] $GraphqlUrl = ""
)
$ErrorActionPreference = "Stop"
$env:GROWFLOW_RETAIL_ORG = $RetailOrg
# Full Retail POST URL (avoids a bad global GROWFLOW_GRAPHQL_URL like .../pgql/... that returns HTML).
if ($GraphqlUrl) {
    $env:GROWFLOW_GRAPHQL_URL = $GraphqlUrl
} else {
    $env:GROWFLOW_GRAPHQL_URL = "https://retail.growflow.com/c/$RetailOrg/graphql"
}
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$csvDir = Split-Path -Parent $Csv
if ($csvDir) { New-Item -ItemType Directory -Force -Path $csvDir | Out-Null }
python allocate_stock_pool_by_brand.py --pool $Pool --days $Days --growflow-credentials $Credentials --csv $Csv
