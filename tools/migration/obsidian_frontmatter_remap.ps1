<#
.SYNOPSIS
  Remap Obsidian vault note frontmatter path fields to senior layout paths.
.DESCRIPTION
  Rewrites repo_path (and similar) values inside YAML frontmatter using
  layout.json moves. Does not rewrite note bodies by default.

  Default is dry-run. Pass -Apply to write. A JSONL report is always written
  under tools/migration/reports/. With -Apply, changed files are also copied
  to a stamp-dated backup folder before overwrite.

  Prefer the canonical vault (internal\obsidian-brain). Pass -VaultPath to
  target another tree (e.g. a duplicate under products\ai-lab\Ai\...).
.PARAMETER Apply
  Write changes. Without this switch, only report what would change.
.PARAMETER VaultPath
  Absolute path to the vault root. Defaults to layout.json vault.new_rel.
.PARAMETER IncludeBody
  Also replace the same retired absolute path prefixes anywhere in the note
  body (same mapping as frontmatter). Off by default.
#>
param(
    [switch]$Apply,
    [string]$VaultPath = '',
    [switch]$IncludeBody
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$stamp = New-ReportStamp
$reports = Get-ReportsDir

if (-not $VaultPath) {
    $rel = if ($layout.vault -and $layout.vault.new_rel) {
        ($layout.vault.new_rel -replace '/', '\')
    } else {
        'internal\obsidian-brain\Obsidian\Brain'
    }
    $VaultPath = Join-Path $root $rel
}
if (-not (Test-Path -LiteralPath $VaultPath)) {
    throw "Vault not found: $VaultPath"
}

# Path-like frontmatter keys only (never rewrite free-text keys)
$pathKeys = @(
    'repo_path',
    'vault_path',
    'folder_path',
    'root_path',
    'source_path',
    'path',
    'abs_path',
    'absolute_path'
)

# Longest-first absolute + forward-slash pairs from layout.moves
$pairs = @()
foreach ($m in ($layout.moves | Sort-Object { -$_.from.Length })) {
    $from = $m.from
    $to = ($m.to -replace '/', '\')
    $pairs += [pscustomobject]@{
        old = "E:\Repos\$from"
        new = "E:\Repos\$to"
    }
    $pairs += [pscustomobject]@{
        old = "E:/Repos/$($from -replace '\\','/')"
        new = "E:/Repos/$($m.to -replace '\\','/')"
    }
}
# Relative vault fragment sometimes used in frontmatter
$pairs += [pscustomobject]@{ old = 'Ai\Obsidian\Brain'; new = 'internal\obsidian-brain\Obsidian\Brain' }
$pairs += [pscustomobject]@{ old = 'Ai/Obsidian/Brain'; new = 'internal/obsidian-brain/Obsidian/Brain' }

function Split-Frontmatter {
    param([string]$Text)
    # Require opening --- on first non-empty line
    if ($Text -notmatch '(?s)\A(\s*)---\r?\n') { return $null }
    $m = [regex]::Match($Text, '(?s)\A(\s*)---\r?\n(.*?)\r?\n---(\r?\n|$)(.*)\z')
    if (-not $m.Success) { return $null }
    return [pscustomobject]@{
        Prefix = $m.Groups[1].Value
        Front  = $m.Groups[2].Value
        Sep    = $m.Groups[3].Value
        Body   = $m.Groups[4].Value
    }
}

function Rewrite-PathValue {
    param([string]$Value, [object[]]$PathPairs)
    $out = $Value
    $hits = @()
    foreach ($p in $PathPairs) {
        if ($out.Contains($p.old)) {
            # Boundary-safe: only replace when old is a path prefix or exact match
            # Avoid turning E:\Repos\ai-lab into products\ai-lab then rematching Ai
            $pattern = [regex]::Escape($p.old) + '(?=\\|\/|$|"|'')'
            $n = ([regex]::Matches($out, $pattern)).Count
            if ($n -gt 0) {
                $out = [regex]::Replace($out, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{
                    param($match)
                    return $p.new
                })
                $hits += [pscustomobject]@{ old = $p.old; new = $p.new; count = $n }
            }
        }
    }
    return [pscustomobject]@{ Value = $out; Hits = $hits }
}

function Rewrite-FrontmatterBlock {
    param([string]$Front, [string[]]$Keys, [object[]]$PathPairs)
    $lines = $Front -split '\r?\n', -1
    $changed = $false
    $fileHits = @()
    $keySet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($k in $Keys) { [void]$keySet.Add($k) }

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line -notmatch '^\s*([A-Za-z0-9_]+)\s*:\s*(.*)$') { continue }
        $key = $Matches[1]
        if (-not $keySet.Contains($key)) { continue }
        $rawVal = $Matches[2]
        # Strip optional surrounding quotes for rewrite, preserve quoting style
        $quote = ''
        $inner = $rawVal
        if ($rawVal -match '^"(.*)"\s*$') { $quote = '"'; $inner = $Matches[1] }
        elseif ($rawVal -match "^'(.*)'\s*$") { $quote = "'"; $inner = $Matches[1] }

        $rw = Rewrite-PathValue -Value $inner -PathPairs $PathPairs
        if ($rw.Value -eq $inner) { continue }
        $changed = $true
        $fileHits += $rw.Hits
        $indent = ''
        if ($line -match '^(\s*)') { $indent = $Matches[1] }
        if ($quote) {
            $lines[$i] = '{0}{1}: {2}{3}{2}' -f $indent, $key, $quote, $rw.Value
        } else {
            $lines[$i] = '{0}{1}: {2}' -f $indent, $key, $rw.Value
        }
    }
    return [pscustomobject]@{
        Front   = ($lines -join "`n")
        Changed = $changed
        Hits    = $fileHits
    }
}

$files = Get-ChildItem -LiteralPath $VaultPath -Recurse -File -Filter '*.md' -ErrorAction SilentlyContinue
$mode = if ($Apply) { 'APPLY' } else { 'DRY-RUN' }
Write-MigLog "Mode=$mode Vault=$VaultPath Notes=$($files.Count) IncludeBody=$IncludeBody"

$backupRoot = $null
if ($Apply) {
    $backupRoot = Join-Path $reports "vault-frontmatter-backup.$stamp"
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    Write-MigLog "Backup dir: $backupRoot"
}

$logPath = Join-Path $reports "vault-frontmatter-remap-$stamp.jsonl"
$summaryPath = Join-Path $reports "vault-frontmatter-remap-$stamp.md"
if (Test-Path $logPath) { Remove-Item $logPath -Force }

$scanned = 0
$withFm = 0
$wouldChange = 0
$changed = 0
$replacementCount = 0
$unmappedFlat = 0
$byFrom = @{}

foreach ($f in $files) {
    $scanned++
    try {
        $raw = [System.IO.File]::ReadAllText($f.FullName)
    } catch {
        continue
    }
    $parts = Split-Frontmatter -Text $raw
    if (-not $parts) { continue }
    $withFm++

    $fmRw = Rewrite-FrontmatterBlock -Front $parts.Front -Keys $pathKeys -PathPairs $pairs
    $newFront = $fmRw.Front
    $body = $parts.Body
    $bodyHits = @()

    if ($IncludeBody) {
        $br = Rewrite-PathValue -Value $body -PathPairs $pairs
        if ($br.Value -ne $body) {
            $body = $br.Value
            $bodyHits = $br.Hits
        }
    }

    if (-not $fmRw.Changed -and $bodyHits.Count -eq 0) {
        # Track remaining flat E:\Repos\<retired> in frontmatter for reporting
        if ($parts.Front -match '(?m)^\s*repo_path:\s*E:\\Repos\\') {
            $stillFlat = $true
            foreach ($p in $pairs) {
                if ($parts.Front.Contains($p.new)) { $stillFlat = $false; break }
            }
            # If repo_path still points at a non-zoned top-level, count as unmapped
            if ($parts.Front -match '(?m)^\s*repo_path:\s*E:\\Repos\\([^\\/\r\n]+)') {
                $top = $Matches[1]
                $zoned = @('products', 'internal', 'tools', 'concepts', 'archive', 'vendor', 'docs')
                if ($zoned -notcontains $top) { $unmappedFlat++ }
            }
        }
        continue
    }

    $wouldChange++
    $allHits = @($fmRw.Hits) + @($bodyHits)
    foreach ($h in $allHits) {
        $replacementCount += [int]$h.count
        $key = $h.old
        if (-not $byFrom.ContainsKey($key)) { $byFrom[$key] = 0 }
        $byFrom[$key] += [int]$h.count
    }

    $newText = $parts.Prefix + "---`n" + $newFront + "`n---" + $parts.Sep + $body
    # Normalize: if original used CRLF, preserve via WriteAllText after detecting
    $useCrlf = $raw.Contains("`r`n")
    if ($useCrlf) {
        $newText = $newText -replace '(?<!\r)\n', "`r`n"
    }

    $rel = $f.FullName.Substring($VaultPath.Length).TrimStart('\')
    $entry = [pscustomobject]@{
        path         = $rel
        frontmatter  = [bool]$fmRw.Changed
        body         = ($bodyHits.Count -gt 0)
        replacements = $allHits
    }
    ($entry | ConvertTo-Json -Compress -Depth 8) | Add-Content -LiteralPath $logPath -Encoding UTF8

    if ($Apply) {
        $bak = Join-Path $backupRoot $rel
        $bakDir = Split-Path -Parent $bak
        if (-not (Test-Path -LiteralPath $bakDir)) {
            New-Item -ItemType Directory -Force -Path $bakDir | Out-Null
        }
        [System.IO.File]::Copy($f.FullName, $bak, $true)
        $enc = [Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText($f.FullName, $newText, $enc)
        $changed++
    }
}

# After apply, recount remaining flat repo_path
$remainingFlat = 0
$remainingFiles = Get-ChildItem -LiteralPath $VaultPath -Recurse -File -Filter '*.md' -ErrorAction SilentlyContinue
foreach ($f in $remainingFiles) {
    try { $raw = [System.IO.File]::ReadAllText($f.FullName) } catch { continue }
    $parts = Split-Frontmatter -Text $raw
    if (-not $parts) { continue }
    if ($parts.Front -match '(?m)^\s*repo_path:\s*E:\\Repos\\([^\\/\r\n]+)') {
        $top = $Matches[1]
        $zoned = @('products', 'internal', 'tools', 'concepts', 'archive', 'vendor', 'docs')
        if ($zoned -notcontains $top) { $remainingFlat++ }
    }
}

$byFromLines = ($byFrom.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
    "- ``$($_.Key)``: $($_.Value)"
}) -join "`n"

@"
# Vault frontmatter remap $stamp ($mode)

- Vault: ``$VaultPath``
- Notes scanned: $scanned
- Notes with YAML frontmatter: $withFm
- Notes with remappable path fields: $wouldChange
- Notes written: $changed
- Path replacements: $replacementCount
- IncludeBody: $IncludeBody
- Remaining flat ``repo_path`` tops after run: $remainingFlat
- Unmapped flat (no layout pair matched this pass): $unmappedFlat
- Log: ``$logPath``
$(if ($backupRoot) { "- Backup: ``$backupRoot``" } else { '- Backup: (dry-run; none)' })

## Replacements by retired prefix

$byFromLines
"@ | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-MigLog "WouldChange=$wouldChange Written=$changed Replacements=$replacementCount RemainingFlat=$remainingFlat -> $summaryPath"
if (-not $Apply) { Write-MigLog "Dry-run only. Re-run with -Apply to write." 'WARN' }

# Emit machine-readable summary for callers
[pscustomobject]@{
    Mode           = $mode
    Vault          = $VaultPath
    Scanned        = $scanned
    WithFrontmatter= $withFm
    WouldChange    = $wouldChange
    Written        = $changed
    Replacements   = $replacementCount
    RemainingFlat  = $remainingFlat
    SummaryPath    = $summaryPath
    LogPath        = $logPath
} | ConvertTo-Json -Compress | Write-Output
