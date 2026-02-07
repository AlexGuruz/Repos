# Run Kylo Config -> BANK + CLEAN TRANSACTIONS sync (convenience launcher).
# Reads rules from Kylo_Config, writes Company IDs to BANK and CLEAN TRANSACTIONS.
#
# Usage from repo root:
#   .\scripts\active\run_sync_bank.ps1
#   .\scripts\active\run_sync_bank.ps1 -DryRun
#   .\scripts\active\run_sync_bank.ps1 -Limit 500

param(
    [switch]$DryRun,
    [int]$Limit = 0
)

$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$SyncScript = Join-Path $RepoRoot "tools\scripthub_legacy\run_sync_bank.ps1"
if (!(Test-Path $SyncScript)) {
    Write-Error "Sync script not found: $SyncScript"
    exit 1
}
& $SyncScript -DryRun:$DryRun -Limit $Limit
exit $LASTEXITCODE
