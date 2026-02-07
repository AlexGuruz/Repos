<#
.SYNOPSIS
  Monitors E:\Repos for changes and syncs file trees plus new subfolder notes to Obsidian Brain.
.DESCRIPTION
  Loads repo_obsidian_map.json, watches repos_root, and updates mapped Obsidian project notes
  with repo structure and new subfolder notes. Supports mirror/flat/slug note naming.
.PARAMETER Watch
  Run continuous monitoring (default).
.PARAMETER RunOnce
  Run one sync and exit.
.PARAMETER Backfill
  Create subfolder notes for all existing folders in mapped repos.
.PARAMETER DryRun
  With Backfill: report what would be created without creating.
#>
param(
    [switch]$Watch = $true,
    [switch]$RunOnce,
    [switch]$Backfill,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ScriptDir "repo_obsidian_map.json"

# Built-in defaults (used when config lacks defaults)
$BuiltInDefaults = @{
    create_subfolder_notes = $true
    note_naming = "mirror"
    ignore_patterns = @(".git", "node_modules", "__pycache__", ".venv", "vendor", "dist", "build", "WinPython64", "site-packages", ".pytest_cache", ".egg-info", ".cursor")
    on_folder_delete = "keep"
}

# ---------------------------------------------------------------------------
# Load config with backward compatibility
# ---------------------------------------------------------------------------
function Get-RepoObsidianMap {
    if (-not (Test-Path $ConfigPath)) {
        throw "Config not found: $ConfigPath"
    }
    $json = Get-Content $ConfigPath -Raw -Encoding UTF8
    return $json | ConvertFrom-Json
}

function Get-Defaults {
    $cfg = Get-RepoObsidianMap
    $createSubfolder = $BuiltInDefaults.create_subfolder_notes
    $noteNaming = $BuiltInDefaults.note_naming
    $ignorePatterns = $BuiltInDefaults.ignore_patterns
    $onDelete = $BuiltInDefaults.on_folder_delete
    if ($cfg.defaults) {
        $d = $cfg.defaults
        if ($null -ne $d.PSObject.Properties['create_subfolder_notes']) { $createSubfolder = [bool]$d.create_subfolder_notes }
        if ($d.note_naming) { $noteNaming = $d.note_naming }
        if ($d.ignore_patterns -and $d.ignore_patterns.Count -gt 0) { $ignorePatterns = [string[]]@($d.ignore_patterns) }
        if ($d.on_folder_delete) { $onDelete = $d.on_folder_delete }
    }
    return @{
        create_subfolder_notes = $createSubfolder
        note_naming = $noteNaming
        ignore_patterns = $ignorePatterns
        on_folder_delete = $onDelete
    }
}

function Get-MappingForPath {
    param([string]$Path)
    $cfg = Get-RepoObsidianMap
    $normalized = $Path.TrimEnd('\').ToLowerInvariant()
    foreach ($m in $cfg.mappings) {
        $repoNorm = $m.repo_path.TrimEnd('\').Replace('\', [char]92).ToLowerInvariant()
        if ($normalized.StartsWith($repoNorm) -or $normalized -eq $repoNorm) {
            return $m
        }
    }
    return $null
}

function Get-ProjectName {
    param([object]$Mapping)
    if ($Mapping.project_name) { return $Mapping.project_name }
    $seg = Split-Path -Leaf ($Mapping.repo_path -replace '\\\\', '\')
    return $seg
}

function Test-Ignored {
    param([string]$FolderName, [string[]]$IgnorePatterns)
    $lower = $FolderName.ToLowerInvariant()
    foreach ($p in $IgnorePatterns) {
        if ($lower -eq $p.ToLowerInvariant()) { return $true }
    }
    return $false
}

function Get-RelativePath {
    param([string]$FullPath, [string]$RepoRoot)
    $full = $FullPath.TrimEnd('\')
    $root = $RepoRoot.TrimEnd('\')
    if ($full -eq $root) { return "" }
    if (-not $full.StartsWith($root)) { return $null }
    $rel = $full.Substring($root.Length).TrimStart('\')
    return $rel -replace '\\', '/'
}

function Sanitize-FileName {
    param([string]$Name)
    $invalid = [System.IO.Path]::GetInvalidFileNameChars() + @('\', '/', ':', '*', '?', '"', '<', '>', '|')
    $out = $Name
    foreach ($c in $invalid) {
        $out = $out.Replace([string]$c, '-')
    }
    $out = $out -replace '-+', '-'
    $out = $out.Trim('-')
    if ([string]::IsNullOrWhiteSpace($out)) { $out = "folder" }
    return $out
}

function Get-ObsidianNotePath {
    param(
        [string]$ObsidianProject,
        [string]$RelativePath,
        [string]$NoteNaming
    )
    $segments = @($RelativePath -split '/' | ForEach-Object { Sanitize-FileName $_ } | Where-Object { $_ })
    if ($segments.Count -eq 0) { return $null }

    $obsBase = $ObsidianProject -replace '/', [System.IO.Path]::DirectorySeparatorChar
    switch ($NoteNaming) {
        "flat" {
            $fileName = $segments -join " - "
            return Join-Path $obsBase "$fileName.md"
        }
        "slug" {
            $slug = ($segments -join "-").ToLowerInvariant() -replace '[^a-z0-9-]', '-'
            return Join-Path $obsBase "$slug.md"
        }
        default {
            # mirror
            $subPath = $segments -join [System.IO.Path]::DirectorySeparatorChar
            return Join-Path $obsBase "$subPath.md"
        }
    }
}

# ---------------------------------------------------------------------------
# Generate markdown file tree (respects ignore_patterns)
# ---------------------------------------------------------------------------
function Get-MarkdownFileTree {
    param(
        [string]$RootPath,
        [string]$Prefix = "",
        [string[]]$IgnorePatterns = @()
    )
    $lines = @()
    $items = Get-ChildItem -Path $RootPath -Force -ErrorAction SilentlyContinue | Sort-Object { -$_.PSIsContainer }, Name
    $count = $items.Count
    $i = 0
    foreach ($item in $items) {
        if ($item.PSIsContainer -and (Test-Ignored -FolderName $item.Name -IgnorePatterns $IgnorePatterns)) {
            $i++
            continue
        }
        $isLast = ($i -eq $count - 1)
        if ($isLast) { $connector = "+-- " } else { $connector = "|-- " }
        $lines += "$Prefix$connector$($item.Name)"
        if ($item.PSIsContainer) {
            if ($isLast) { $subPrefix = $Prefix + "    " } else { $subPrefix = $Prefix + "|   " }
            try {
                $subLines = Get-MarkdownFileTree -RootPath $item.FullName -Prefix $subPrefix -IgnorePatterns $IgnorePatterns
                $lines += $subLines
            } catch { }
        }
        $i++
    }
    return $lines
}

# ---------------------------------------------------------------------------
# Update Obsidian note: replace REPO_STRUCTURE section
# ---------------------------------------------------------------------------
function Update-RepoStructureSection {
    param(
        [string]$NotePath,
        [string]$RepoPath,
        [string[]]$IgnorePatterns = @()
    )
    if (-not (Test-Path $NotePath)) { return }
    $content = Get-Content $NotePath -Raw -Encoding UTF8
    $treeLines = Get-MarkdownFileTree -RootPath $RepoPath -IgnorePatterns $IgnorePatterns
    $tree = ($treeLines -join "`n").Trim()
    $startMarker = "<!-- REPO_STRUCTURE_START -->"
    $endMarker = "<!-- REPO_STRUCTURE_END -->"
    $newBlock = "`n$startMarker`n$tree`n$endMarker`n"
    if ($content -match "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))") {
        $content = $content -replace "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))", $newBlock.TrimEnd()
    } else {
        $content = $content + "`n`n## Repo Structure`n" + $newBlock
    }
    [System.IO.File]::WriteAllText($NotePath, $content, [System.Text.UTF8Encoding]::new($false))
}

# ---------------------------------------------------------------------------
# Create subfolder note and add link to Project Notes section
# ---------------------------------------------------------------------------
function Add-SubfolderNote {
    param(
        [string]$VaultPath,
        [string]$ObsidianProject,
        [string]$ObsidianNotePath,
        [string]$RelativePath,
        [string]$ProjectName,
        [string]$RepoPath,
        [string]$NoteNaming
    )
    $noteRelPath = Get-ObsidianNotePath -ObsidianProject $ObsidianProject -RelativePath $RelativePath -NoteNaming $NoteNaming
    if (-not $noteRelPath) { return }
    $newNotePath = Join-Path $VaultPath $noteRelPath
    $projectNotePath = Join-Path $VaultPath ($ObsidianNotePath -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    $noteDir = Split-Path -Parent $newNotePath
    $noteName = [System.IO.Path]::GetFileNameWithoutExtension($newNotePath)
    $fullRepoPath = Join-Path $RepoPath ($RelativePath -replace '/', '\')

    if (-not (Test-Path $noteDir)) {
        New-Item -ItemType Directory -Path $noteDir -Force | Out-Null
    }

    if (-not (Test-Path $newNotePath)) {
        $titlePart = $RelativePath -replace '/', ' / '
        $noteContent = @"
---
project: $ProjectName
type: project-subfolder
repo_path: $fullRepoPath
relative_path: $RelativePath
created: $(Get-Date -Format "yyyy-MM-dd HH:mm")
updated: $(Get-Date -Format "yyyy-MM-dd HH:mm")
---

# $titlePart

Folder in $ProjectName repo.

**Repo path:** ``$fullRepoPath``

## Related
- [[$ProjectName|Project Hub]]
"@
        [System.IO.File]::WriteAllText($newNotePath, $noteContent, [System.Text.UTF8Encoding]::new($false))
        Write-Host "[repo_obsidian_sync] Created note: $noteRelPath"
    }

    # Add link to Project Notes section - use Obsidian link format
    $linkNote = $noteRelPath -replace '\.md$', ''
    $linkNote = $linkNote -replace [regex]::Escape([System.IO.Path]::DirectorySeparatorChar), '/'
    if (Test-Path $projectNotePath) {
        $content = Get-Content $projectNotePath -Raw -Encoding UTF8
        $link = "[[$linkNote]]"
        if ($content -notmatch [regex]::Escape($link)) {
            $content = $content -replace "(?m)(## Project Notes\s*\r?\n(?:<!--.*?-->)?)\s*", "`$1`n- $link`n"
            [System.IO.File]::WriteAllText($projectNotePath, $content, [System.Text.UTF8Encoding]::new($false))
        }
    }
}

# ---------------------------------------------------------------------------
# Remove subfolder note (on_folder_delete = remove)
# ---------------------------------------------------------------------------
function Remove-SubfolderNote {
    param(
        [string]$VaultPath,
        [string]$ObsidianProject,
        [string]$RelativePath,
        [string]$NoteNaming
    )
    $noteRelPath = Get-ObsidianNotePath -ObsidianProject $ObsidianProject -RelativePath $RelativePath -NoteNaming $NoteNaming
    if (-not $noteRelPath) { return }
    $notePath = Join-Path $VaultPath $noteRelPath
    if (Test-Path $notePath) {
        Remove-Item -LiteralPath $notePath -Force
        Write-Host "[repo_obsidian_sync] Removed note: $noteRelPath"
    }
}

# ---------------------------------------------------------------------------
# Rename/move subfolder note (on Renamed event)
# ---------------------------------------------------------------------------
function Rename-SubfolderNote {
    param(
        [string]$VaultPath,
        [string]$ObsidianProject,
        [string]$OldRelativePath,
        [string]$NewRelativePath,
        [string]$ObsidianNotePath,
        [string]$NoteNaming
    )
    $oldNotePath = Join-Path $VaultPath (Get-ObsidianNotePath -ObsidianProject $ObsidianProject -RelativePath $OldRelativePath -NoteNaming $NoteNaming)
    $newNotePath = Join-Path $VaultPath (Get-ObsidianNotePath -ObsidianProject $ObsidianProject -RelativePath $NewRelativePath -NoteNaming $NoteNaming)
    if (-not (Test-Path $oldNotePath)) { return }
    $newDir = Split-Path -Parent $newNotePath
    if (-not (Test-Path $newDir)) {
        New-Item -ItemType Directory -Path $newDir -Force | Out-Null
    }
    Move-Item -LiteralPath $oldNotePath -Destination $newNotePath -Force
    Write-Host "[repo_obsidian_sync] Renamed note: $OldRelativePath -> $NewRelativePath"
}

# ---------------------------------------------------------------------------
# Append to Change Log section
# ---------------------------------------------------------------------------
function Append-ChangeLog {
    param(
        [string]$NotePath,
        [string]$Action,
        [string]$Path
    )
    if (-not (Test-Path $NotePath)) { return }
    $content = Get-Content $NotePath -Raw -Encoding UTF8
    $entry = "- $(Get-Date -Format 'yyyy-MM-dd HH:mm') | $Action | $Path"
    $startMarker = "<!-- CHANGELOG_START -->"
    $endMarker = "<!-- CHANGELOG_END -->"
    if ($content -match "(?s)$([regex]::Escape($startMarker))(.*?)$([regex]::Escape($endMarker))") {
        $inner = $Matches[1].TrimEnd() + "`n$entry"
        $newBlock = "$startMarker`n$inner`n$endMarker"
        $content = $content -replace "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))", $newBlock
    } else {
        $block = "`n## Change Log`n$startMarker`n$entry`n$endMarker`n"
        $content = $content + $block
    }
    [System.IO.File]::WriteAllText($NotePath, $content, [System.Text.UTF8Encoding]::new($false))
}

# ---------------------------------------------------------------------------
# Process a change for a mapped repo
# ---------------------------------------------------------------------------
function Sync-MappedRepo {
    param(
        [object]$Mapping,
        [string]$ChangedPath,
        [string]$ChangeType,
        [string]$OldPath = $null
    )
    $cfg = Get-RepoObsidianMap
    $defaults = Get-Defaults
    $vaultPath = $cfg.vault_path -replace '\\\\', '\'
    $repoPath = $Mapping.repo_path -replace '\\\\', '\'
    $notePath = Join-Path $vaultPath ($Mapping.obsidian_note -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    $projectName = Get-ProjectName -Mapping $Mapping
    $createNotes = $defaults.create_subfolder_notes
    $noteNaming = $defaults.note_naming
    $ignorePatterns = $defaults.ignore_patterns
    $onFolderDelete = $defaults.on_folder_delete
    if ($Mapping.create_subfolder_notes -ne $null) { $createNotes = [bool]$Mapping.create_subfolder_notes }
    if ($Mapping.note_naming) { $noteNaming = $Mapping.note_naming }
    if ($Mapping.ignore_patterns) { $ignorePatterns = @($Mapping.ignore_patterns) }
    if ($Mapping.on_folder_delete) { $onFolderDelete = $Mapping.on_folder_delete }

    Update-RepoStructureSection -NotePath $notePath -RepoPath $repoPath -IgnorePatterns $ignorePatterns

    if ($ChangeType -eq "Created") {
        $item = Get-Item -LiteralPath $ChangedPath -ErrorAction SilentlyContinue
        if ($item -and $item.PSIsContainer -and $createNotes) {
            $relPath = Get-RelativePath -FullPath $ChangedPath -RepoRoot $repoPath
            if ($relPath) {
                $folderName = Split-Path -Leaf $relPath
                if (-not (Test-Ignored -FolderName $folderName -IgnorePatterns $ignorePatterns)) {
                    Add-SubfolderNote -VaultPath $vaultPath -ObsidianProject $Mapping.obsidian_project -ObsidianNotePath $Mapping.obsidian_note -RelativePath $relPath -ProjectName $projectName -RepoPath $repoPath -NoteNaming $noteNaming
                }
            }
        }
    }
    elseif ($ChangeType -eq "Deleted") {
        $itemWasFolder = $true
        try {
            $parent = Split-Path -Parent $ChangedPath
            $name = Split-Path -Leaf $ChangedPath
            if ($name) {
                $relPath = Get-RelativePath -FullPath $ChangedPath -RepoRoot $repoPath
                if ($relPath -and $onFolderDelete -eq "remove") {
                    Remove-SubfolderNote -VaultPath $vaultPath -ObsidianProject $Mapping.obsidian_project -RelativePath $relPath -NoteNaming $noteNaming
                }
            }
        } catch { }
    }
    elseif ($ChangeType -eq "Renamed" -and $OldPath) {
        $oldRel = Get-RelativePath -FullPath $OldPath -RepoRoot $repoPath
        $newRel = Get-RelativePath -FullPath $ChangedPath -RepoRoot $repoPath
        if ($oldRel -and $newRel) {
            $oldFolderName = Split-Path -Leaf $oldRel
            $newFolderName = Split-Path -Leaf $newRel
            if (-not (Test-Ignored -FolderName $newFolderName -IgnorePatterns $ignorePatterns)) {
                Rename-SubfolderNote -VaultPath $vaultPath -ObsidianProject $Mapping.obsidian_project -OldRelativePath $oldRel -NewRelativePath $newRel -ObsidianNotePath $Mapping.obsidian_note -NoteNaming $noteNaming
            }
        }
    }

    Append-ChangeLog -NotePath $notePath -Action $ChangeType -Path $ChangedPath
}

# ---------------------------------------------------------------------------
# Get all subfolders in repo (recursive, respects ignore_patterns)
# ---------------------------------------------------------------------------
function Get-RepoSubfolders {
    param(
        [string]$RepoPath,
        [string[]]$IgnorePatterns
    )
    $folders = @()
    $items = Get-ChildItem -Path $RepoPath -Directory -Force -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        if (Test-Ignored -FolderName $item.Name -IgnorePatterns $IgnorePatterns) { continue }
        $rel = Get-RelativePath -FullPath $item.FullName -RepoRoot $RepoPath
        if ($rel) { $folders += $rel }
        $subs = Get-RepoSubfolders -RepoPath $item.FullName -IgnorePatterns $IgnorePatterns
        foreach ($s in $subs) {
            $fullRel = "$rel/$s"
            $folders += $fullRel
        }
    }
    return $folders
}

# ---------------------------------------------------------------------------
# Backfill: create notes for all existing subfolders in mapped repos
# ---------------------------------------------------------------------------
function Invoke-Backfill {
    param([switch]$DryRun)
    $cfg = Get-RepoObsidianMap
    $defaults = Get-Defaults
    $vaultPath = $cfg.vault_path -replace '\\\\', '\'
    $createNotes = $defaults.create_subfolder_notes
    $ignorePatterns = $defaults.ignore_patterns
    $noteNaming = $defaults.note_naming

    $totalToCreate = 0
    $totalExisting = 0
    foreach ($m in $cfg.mappings) {
        $repoPath = $m.repo_path -replace '\\\\', '\'
        if (-not (Test-Path $repoPath)) {
            Write-Host "[repo_obsidian_sync] Skip (repo not found): $repoPath"
            continue
        }
        if ($m.create_subfolder_notes -ne $null) { $createNotes = [bool]$m.create_subfolder_notes }
        if ($m.ignore_patterns) { $ignorePatterns = @($m.ignore_patterns) }
        if ($m.note_naming) { $noteNaming = $m.note_naming }
        if (-not $createNotes) {
            Write-Host "[repo_obsidian_sync] Skip (create_subfolder_notes=false): $($m.project_name)"
            continue
        }

        # Update Repo Structure (always)
        $notePath = Join-Path $vaultPath ($m.obsidian_note -replace '/', [System.IO.Path]::DirectorySeparatorChar)
        if (Test-Path $notePath) {
            if (-not $DryRun) {
                Update-RepoStructureSection -NotePath $notePath -RepoPath $repoPath -IgnorePatterns $ignorePatterns
            }
        }

        $projectName = Get-ProjectName -Mapping $m
        $subfolders = Get-RepoSubfolders -RepoPath $repoPath -IgnorePatterns $ignorePatterns
        $toCreate = @()
        foreach ($rel in $subfolders) {
            $noteRelPath = Get-ObsidianNotePath -ObsidianProject $m.obsidian_project -RelativePath $rel -NoteNaming $noteNaming
            if (-not $noteRelPath) { continue }
            $fullNotePath = Join-Path $vaultPath $noteRelPath
            if (Test-Path $fullNotePath) {
                $totalExisting++
            } else {
                $toCreate += $rel
                $totalToCreate++
            }
        }

        Write-Host "[repo_obsidian_sync] $($m.project_name): $($subfolders.Count) subfolders ($($toCreate.Count) to create, $($subfolders.Count - $toCreate.Count) existing)"
        foreach ($rel in $toCreate) {
            $noteRelPath = Get-ObsidianNotePath -ObsidianProject $m.obsidian_project -RelativePath $rel -NoteNaming $noteNaming
            if ($DryRun) {
                Write-Host "  [DRY RUN] Would create: $noteRelPath"
            } else {
                Add-SubfolderNote -VaultPath $vaultPath -ObsidianProject $m.obsidian_project -ObsidianNotePath $m.obsidian_note -RelativePath $rel -ProjectName $projectName -RepoPath $repoPath -NoteNaming $noteNaming
            }
        }
    }

    if ($DryRun) {
        Write-Host "[repo_obsidian_sync] Backfill DRY RUN complete: $totalToCreate notes would be created"
    } else {
        Write-Host "[repo_obsidian_sync] Backfill complete: $totalToCreate notes created"
    }
}

# ---------------------------------------------------------------------------
# Run once: sync all mapped repos
# ---------------------------------------------------------------------------
function Invoke-RunOnce {
    $cfg = Get-RepoObsidianMap
    $defaults = Get-Defaults
    $vaultPath = $cfg.vault_path -replace '\\\\', '\'
    $ignorePatterns = $defaults.ignore_patterns
    foreach ($m in $cfg.mappings) {
        $repoPath = $m.repo_path -replace '\\\\', '\'
        if (Test-Path $repoPath) {
            try {
                Update-RepoStructureSection -NotePath (Join-Path $vaultPath ($m.obsidian_note -replace '/', [System.IO.Path]::DirectorySeparatorChar)) -RepoPath $repoPath -IgnorePatterns $ignorePatterns
                Write-Host "[repo_obsidian_sync] Synced: $($m.obsidian_note)"
            } catch {
                Write-Warning "Sync failed for $repoPath : $_"
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if ($Backfill) {
    Invoke-Backfill -DryRun:$DryRun
    exit 0
}
if ($RunOnce) {
    Invoke-RunOnce
    exit 0
}

$cfg = Get-RepoObsidianMap
$defaults = Get-Defaults
$ReposRoot = if ($cfg.repos_root) { $cfg.repos_root -replace '\\\\', '\' } else { "E:\Repos" }
$DebounceSeconds = if ($null -ne $cfg.debounce_seconds) { [int]$cfg.debounce_seconds } else { 2 }

$sharedState = [hashtable]::Synchronized(@{
    changePending = $false
    lastPath = $null
    lastOldPath = $null
    lastAction = $null
    lastChangeTime = [datetime]::MinValue
})

$onChange = {
    $path = $Event.SourceEventArgs.FullPath
    $changeType = $Event.SourceEventArgs.ChangeType
    $Action = switch ($changeType) {
        "Created" { "Created" }
        "Deleted" { "Deleted" }
        "Renamed" { "Renamed" }
        default { "Changed" }
    }
    $state = $Event.MessageData
    $state.changePending = $true
    $state.lastPath = $path
    $state.lastAction = $Action
    $state.lastChangeTime = [datetime]::UtcNow
}

$onRename = {
    $path = $Event.SourceEventArgs.FullPath
    $oldPath = $Event.SourceEventArgs.OldFullPath
    $state = $Event.MessageData
    $state.changePending = $true
    $state.lastPath = $path
    $state.lastOldPath = $oldPath
    $state.lastAction = "Renamed"
    $state.lastChangeTime = [datetime]::UtcNow
}

Write-Host "[repo_obsidian_sync] Watching $ReposRoot, config: $ConfigPath"

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $ReposRoot
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

$handlers = @(
    Register-ObjectEvent -InputObject $watcher -EventName Created -Action $onChange -MessageData $sharedState
    Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $onChange -MessageData $sharedState
    Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $onRename -MessageData $sharedState
)

Invoke-RunOnce

$debounceMs = $DebounceSeconds * 1000

try {
    Write-Host "[repo_obsidian_sync] Monitoring... Press Ctrl+C to stop."
    while ($true) {
        Start-Sleep -Milliseconds 500
        if ($sharedState.changePending -and $sharedState.lastPath) {
            $elapsed = ([datetime]::UtcNow - $sharedState.lastChangeTime).TotalMilliseconds
            if ($elapsed -ge $debounceMs) {
                $m = Get-MappingForPath -Path $sharedState.lastPath
                if ($m) {
                    try {
                        Sync-MappedRepo -Mapping $m -ChangedPath $sharedState.lastPath -ChangeType $sharedState.lastAction -OldPath $sharedState.lastOldPath
                        Write-Host "[repo_obsidian_sync] Synced change: $($sharedState.lastAction) $($sharedState.lastPath)"
                    } catch {
                        Write-Warning "Sync failed: $_"
                    }
                }
                $sharedState.changePending = $false
                $sharedState.lastPath = $null
                $sharedState.lastOldPath = $null
                $sharedState.lastAction = $null
                $sharedState.lastChangeTime = [datetime]::UtcNow
            }
        }
    }
} finally {
    foreach ($h in $handlers) {
        Unregister-Event -SourceIdentifier $h.Name -ErrorAction SilentlyContinue
    }
    $watcher.Dispose()
}
