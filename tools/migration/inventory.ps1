<#
.SYNOPSIS
  Scan high-value dirs for legacy path strings (read-only).
#>
param()
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$stamp = New-ReportStamp
$reports = Get-ReportsDir
$outMd = Join-Path $reports "inventory-$stamp.md"
$outJson = Join-Path $reports "inventory-$stamp.json"

$patterns = @($layout.inventory_patterns)
$scanRoots = @(
    (Join-Path $root 'ai-lab\scripts'),
    (Join-Path $root 'ai-lab\ops'),
    (Join-Path $root 'ai-lab\operator_desk'),
    (Join-Path $root 'ai-lab\brain'),
    (Join-Path $root 'ai-lab-governance\registry'),
    (Join-Path $root 'docs'),
    (Join-Path $root '_scripts'),
    (Join-Path $root 'Growflow\scripts'),
    (Join-Path $root 'Project-Kylo\scripts'),
    (Join-Path $root 'Project-Kylo\config'),
    (Join-Path $root 'tools\migration')
)

$extOk = @('.ps1', '.py', '.md', '.yml', '.yaml', '.json', '.code-workspace', '.env', '.mdc', '.txt')
Write-MigLog "Repos root: $root (scoped inventory)"

$files = @()
foreach ($sr in $scanRoots) {
    if (-not (Test-Path -LiteralPath $sr)) { continue }
    $files += Get-ChildItem -LiteralPath $sr -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $extOk -contains $_.Extension -and $_.FullName -notmatch '\\reports\\' }
}
# Root-level config files
$files += Get-ChildItem -LiteralPath $root -File -ErrorAction SilentlyContinue |
    Where-Object { $extOk -contains $_.Extension }

Write-MigLog "Files to scan: $($files.Count)"

$hits = @()
foreach ($pat in $patterns) {
    $n = 0
    foreach ($f in $files) {
        try {
            $content = [System.IO.File]::ReadAllText($f.FullName)
            if ($content.IndexOf($pat, [StringComparison]::Ordinal) -lt 0) { continue }
            $rel = $f.FullName.Substring($root.Length).TrimStart('\')
            $sev = if ($rel -match '(_power1_|sync_|workers\.yaml|systems\.yaml|repo_registry|repo_obsidian|paths\.py)') { 'Critical' }
                   elseif ($rel -match '\.(ps1|py|json|yaml|yml|env)$') { 'High' }
                   elseif ($rel -match '\.(md|mdc|code-workspace)$') { 'Medium' }
                   else { 'Low' }
            $hits += [pscustomobject]@{ pattern = $pat; path = $rel; severity = $sev }
            $n++
        } catch { }
    }
    Write-MigLog "Pattern '$pat' -> $n hits"
}

$hits = $hits | Sort-Object severity, path, pattern -Unique
$critical = @($hits | Where-Object severity -eq 'Critical').Count
$high = @($hits | Where-Object severity -eq 'High').Count
$medium = @($hits | Where-Object severity -eq 'Medium').Count

$md = @(
    "# Path inventory $stamp",
    "",
    "- Repos root: ``$root``",
    "- Layout status: ``$(Get-LayoutStatus)``",
    "- Files scanned: $($files.Count)",
    "- Hits: $($hits.Count) (Critical=$critical High=$high Medium=$medium)",
    "",
    "| Severity | Pattern | Path |",
    "|----------|---------|------|"
)
foreach ($h in ($hits | Sort-Object @{e={@{'Critical'=0;'High'=1;'Medium'=2;'Low'=3}[$_.severity]}}, path)) {
    $md += "| $($h.severity) | ``$($h.pattern)`` | ``$($h.path)`` |"
}
$md -join "`n" | Set-Content -LiteralPath $outMd -Encoding UTF8
$hits | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $outJson -Encoding UTF8
Write-MigLog "Wrote $outMd"
Write-MigLog "Critical=$critical High=$high Medium=$medium Total=$($hits.Count)"
exit 0
