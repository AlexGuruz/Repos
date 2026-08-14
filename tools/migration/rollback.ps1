<#
.SYNOPSIS
  Best-effort reverse of the latest migrate-*.json log.
#>
param(
    [string]$LogJson,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$reports = Get-ReportsDir
if (-not $LogJson) {
    $LogJson = Get-ChildItem -LiteralPath $reports -Filter 'migrate-*.json' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $LogJson -or -not (Test-Path -LiteralPath $LogJson)) {
    throw "No migrate log found in $reports"
}

Write-MigLog "Rollback using $LogJson (Apply=$Apply)"
$entries = Get-Content -LiteralPath $LogJson -Raw | ConvertFrom-Json
# Reverse order
[array]::Reverse($entries)

foreach ($e in $entries) {
    if ($e.status -notin @('moved', 'dry-run')) { continue }
    $from = $e.to
    $to = $e.from
    if (-not (Test-Path -LiteralPath $from)) {
        Write-MigLog "SKIP missing: $from" 'WARN'
        continue
    }
    if (Test-Path -LiteralPath $to) {
        Write-MigLog "SKIP target exists: $to" 'WARN'
        continue
    }
    Write-MigLog "$(if ($Apply) {'RESTORE'} else {'DRY'}) $from -> $to"
    if ($Apply) {
        $parent = Split-Path -Parent $to
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Move-Item -LiteralPath $from -Destination $to
    }
}
Write-MigLog "Rollback complete (Apply=$Apply)"
