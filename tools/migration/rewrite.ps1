<#
.SYNOPSIS
  Rewrite hardcoded legacy paths in high-value dirs (DryRun by default).
#>
param(
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$stamp = New-ReportStamp
$reports = Get-ReportsDir
$logPath = Join-Path $reports "rewrite-$stamp.jsonl"
$summaryPath = Join-Path $reports "rewrite-$stamp.md"

$pairs = @()
foreach ($m in $layout.moves) {
    $from = $m.from
    $to = ($m.to -replace '/', '\')
    $pairs += [pscustomobject]@{ old = "E:\Repos\$from"; new = "E:\Repos\$to" }
    $pairs += [pscustomobject]@{ old = "E:/Repos/$($from -replace '\\','/')"; new = "E:/Repos/$($m.to -replace '\\','/')" }
    $pairs += [pscustomobject]@{ old = "C:\worker\repos\$from"; new = "C:\worker\repos\$to" }
    $pairs += [pscustomobject]@{ old = "C:/worker/repos/$($from -replace '\\','/')"; new = "C:/worker/repos/$($m.to -replace '\\','/')" }
    $pairs += [pscustomobject]@{ old = "REPOS_ROOT\$from"; new = "REPOS_ROOT\$to" }
    $pairs += [pscustomobject]@{ old = "REPOS_ROOT/$($from -replace '\\','/')"; new = "REPOS_ROOT/$($m.to)" }
}
$pairs += [pscustomobject]@{ old = 'Ai\Obsidian\Brain'; new = 'internal\obsidian-brain\Obsidian\Brain' }
$pairs += [pscustomobject]@{ old = 'Ai/Obsidian/Brain'; new = 'internal/obsidian-brain/Obsidian/Brain' }
$pairs = $pairs | Sort-Object { -$_.old.Length }

$scanRoots = @()
foreach ($rel in @(
    'products\ai-lab\scripts', 'ai-lab\scripts',
    'products\ai-lab\ops', 'ai-lab\ops',
    'products\ai-lab\operator_desk', 'ai-lab\operator_desk',
    'products\ai-lab\brain', 'ai-lab\brain',
    'products\ai-lab\state', 'ai-lab\state',
    'products\ai-lab-governance\registry', 'ai-lab-governance\registry',
    'docs',
    'tools\scripts\_scripts', '_scripts',
    'products\growflow\scripts', 'Growflow\scripts',
    'products\project-kylo\scripts', 'Project-Kylo\scripts',
    'products\project-kylo\config', 'Project-Kylo\config'
)) {
    $p = Join-Path $root $rel
    if (Test-Path -LiteralPath $p) { $scanRoots += $p }
}
$scanRoots = $scanRoots | Select-Object -Unique

$extOk = @('.ps1', '.py', '.md', '.yml', '.yaml', '.json', '.code-workspace', '.env', '.mdc', '.txt')
$files = @()
foreach ($sr in $scanRoots) {
    if (-not (Test-Path -LiteralPath $sr)) { continue }
    $files += Get-ChildItem -LiteralPath $sr -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $extOk -contains $_.Extension }
}
$files += Get-ChildItem -LiteralPath $root -File -ErrorAction SilentlyContinue |
    Where-Object { $extOk -contains $_.Extension -and $_.Name -match 'workspace|README|repos_to_push' }

Write-MigLog "Mode: $(if ($Apply) { 'APPLY' } else { 'DRY-RUN' }) files=$($files.Count) pairs=$($pairs.Count)"

$changeCount = 0
$fileCount = 0
if (Test-Path $logPath) { Remove-Item $logPath -Force }

foreach ($f in $files) {
    try { $raw = [System.IO.File]::ReadAllText($f.FullName) } catch { continue }
    $new = $raw
    $fileChanges = @()
    foreach ($p in $pairs) {
        if ($new.Contains($p.old)) {
            $n = ([regex]::Matches($new, [regex]::Escape($p.old))).Count
            $new = $new.Replace($p.old, $p.new)
            $fileChanges += @{ old = $p.old; new = $p.new; count = $n }
            $changeCount += $n
        }
    }
    if ($fileChanges.Count -eq 0) { continue }
    $fileCount++
    $rel = $f.FullName.Substring($root.Length).TrimStart('\')
    $entry = [pscustomobject]@{ path = $rel; changes = $fileChanges }
    ($entry | ConvertTo-Json -Compress -Depth 6) | Add-Content -LiteralPath $logPath -Encoding UTF8
    if ($Apply) {
        [System.IO.File]::WriteAllText($f.FullName, $new, [Text.UTF8Encoding]::new($false))
    }
}

$mode = if ($Apply) { 'APPLY' } else { 'DRY-RUN' }
@"
# Rewrite $stamp ($mode)

- Files touched: $fileCount
- Replacements: $changeCount
- Log: ``$logPath``
"@ | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-MigLog "Files=$fileCount Replacements=$changeCount -> $summaryPath"
if (-not $Apply) { Write-MigLog "Dry-run only. Re-run with -Apply to write." 'WARN' }
