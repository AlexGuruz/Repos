<#
.SYNOPSIS
  Remap Obsidian repo_obsidian_map.json to senior layout paths.
.DESCRIPTION
  Rewrites vault_path / repo_path strings using layout.json moves.
  Handles both literal and JSON-escaped (\\) Windows paths.
  Default is dry-run; pass -Apply to write. -Backfill (with -Apply) runs
  repo_obsidian_sync.ps1 -Backfill to create missing subfolder notes — it does
  not rewrite existing vault frontmatter repo_path fields.
  For frontmatter remaps, use obsidian_frontmatter_remap.ps1 instead.
#>
param(
    [switch]$Apply,
    [switch]$Backfill
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$candidates = @(
    (Join-Path $root 'tools\scripts\_scripts\repo_obsidian_map.json'),
    (Join-Path $root '_scripts\repo_obsidian_map.json')
)
$mapPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $mapPath) { throw "repo_obsidian_map.json not found" }

Write-MigLog "Map: $mapPath"
$raw = Get-Content -LiteralPath $mapPath -Raw -Encoding UTF8
$orig = $raw

# Apply move replacements (literal paths + JSON-escaped \\ forms used in .json files)
foreach ($m in ($layout.moves | Sort-Object { -$_.from.Length })) {
    $from = $m.from
    $to = ($m.to -replace '/', '\')
    $pathFrom = "E:\Repos\$from"
    $pathTo = "E:\Repos\$to"
    $raw = $raw.Replace($pathFrom, $pathTo)
    $raw = $raw.Replace($pathFrom.Replace('\', '\\'), $pathTo.Replace('\', '\\'))
    $raw = $raw.Replace("E:/Repos/$($from -replace '\\','/')", "E:/Repos/$($m.to -replace '\\','/')")
}
$raw = $raw.Replace('Ai\Obsidian\Brain', 'internal\obsidian-brain\Obsidian\Brain')
$raw = $raw.Replace('Ai\\Obsidian\\Brain', 'internal\\obsidian-brain\\Obsidian\\Brain')
$raw = $raw.Replace('Ai/Obsidian/Brain', 'internal/obsidian-brain/Obsidian/Brain')

$vaultNew = Join-Path $root 'internal\obsidian-brain\Obsidian\Brain'
$vaultOld = Join-Path $root 'Ai\Obsidian\Brain'
$vault = if (Test-Path $vaultNew) { $vaultNew } elseif (Test-Path $vaultOld) { $vaultOld } else { $null }
if ($vault) {
    Write-MigLog "Vault: $vault"
}

$stamp = New-ReportStamp
$backup = Join-Path (Get-ReportsDir) "repo_obsidian_map.backup.$stamp.json"
Set-Content -LiteralPath $backup -Value $orig -Encoding UTF8
Write-MigLog "Backup: $backup"

if ($raw -eq $orig) {
    Write-MigLog "No changes needed (already remapped or no legacy strings)"
} elseif ($Apply) {
    Set-Content -LiteralPath $mapPath -Value $raw -Encoding UTF8
    Write-MigLog "Wrote $mapPath"
} else {
    Write-MigLog "Dry-run: would update map ($($orig.Length) -> $($raw.Length) bytes)" 'WARN'
}

if ($Backfill -and $Apply) {
    $sync = @(
        (Join-Path $root 'tools\scripts\_scripts\repo_obsidian_sync.ps1'),
        (Join-Path $root '_scripts\repo_obsidian_sync.ps1')
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($sync) {
        Write-MigLog "Backfill via $sync"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $sync -Backfill
    } else {
        Write-MigLog "repo_obsidian_sync.ps1 not found" 'WARN'
    }
}
