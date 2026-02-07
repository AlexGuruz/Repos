# move_project_kylo_execute.ps1
# Agent 2 - Execute Script (requires -Execute flag)
# Reads move_manifest.csv and performs actual moves/copies

param(
    [Parameter(Mandatory=$false)]
    [switch]$Execute,
    
    [string]$ManifestPath = "D:\_PORTABLE_CONTROL\_manifests\project_kylo\move_manifest.csv",
    [switch]$ShowLog
)

$ErrorActionPreference = "Continue"
$LogFile = "D:\_PORTABLE_CONTROL\_logs\move_project_kylo_execute.log"
$ChunkRoot = "D:\Project-Kylo\"

# Safety check - require -Execute flag
if (-not $Execute) {
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "SAFETY CHECK FAILED" -ForegroundColor Red
    Write-Host "================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "This script performs ACTUAL file moves and copies." -ForegroundColor Yellow
    Write-Host "To execute, you MUST provide the -Execute flag:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  .\move_project_kylo_execute.ps1 -Execute" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Running dry-run instead..." -ForegroundColor Yellow
    Write-Host ""
    
    # Run dry-run script instead
    & "D:\_PORTABLE_CONTROL\_scripts\move_project_kylo_dryrun.ps1" -ShowLog:$ShowLog
    exit 0
}

# Initialize log file
$LogDir = Split-Path -Parent $LogFile
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $LogMessage
    if ($ShowLog -or $Level -eq "ERROR" -or $Level -eq "WARN") {
        Write-Host $LogMessage
    }
}

Write-Log "================================================" "INFO"
Write-Log "Project-Kylo Move Execute Script Started" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Manifest: $ManifestPath" "INFO"
Write-Log "Chunk Root: $ChunkRoot" "INFO"
Write-Log "Mode: EXECUTE (ACTUAL MOVES/COPIES)" "WARN"
Write-Log "" "INFO"

# Final confirmation prompt
Write-Host ""
Write-Host "WARNING: This will perform ACTUAL file operations!" -ForegroundColor Red
Write-Host "Press Ctrl+C to cancel, or any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Validate manifest exists
if (-not (Test-Path $ManifestPath)) {
    Write-Log "ERROR: Manifest file not found: $ManifestPath" "ERROR"
    exit 1
}

# Read manifest
Write-Log "Reading manifest CSV..." "INFO"
try {
    $Manifest = Import-Csv -Path $ManifestPath
    Write-Log "Loaded $($Manifest.Count) manifest entries" "INFO"
} catch {
    Write-Log "ERROR: Failed to read manifest CSV: $_" "ERROR"
    exit 1
}

# Validate CSV columns
$RequiredColumns = @("source_path", "dest_path", "reason", "confidence", "action", "notes")
$ActualColumns = $Manifest[0].PSObject.Properties.Name
$MissingColumns = $RequiredColumns | Where-Object { $_ -notin $ActualColumns }

if ($MissingColumns.Count -gt 0) {
    Write-Log "ERROR: Manifest missing required columns: $($MissingColumns -join ', ')" "ERROR"
    exit 1
}

# Statistics
$Stats = @{
    Total = $Manifest.Count
    Move = 0
    Copy = 0
    ArchiveOnly = 0
    Skip = 0
    Missing = 0
    Errors = 0
    CreatedDirs = 0
}

# Function to process a single manifest entry
function Process-ManifestEntry {
    param(
        [string]$SourcePath,
        [string]$DestPath,
        [string]$Action,
        [double]$Confidence,
        [string]$Reason,
        [string]$Notes,
        [hashtable]$Stats
    )

    # Check if source exists
    if (-not (Test-Path $SourcePath)) {
        Write-Log "  WARN: Source does not exist, skipping: $SourcePath" "WARN"
        $Stats.Missing++
        return
    }

    # Validate confidence for move/copy actions
    if ($Action -in @("move", "copy") -and $Confidence -lt 0.80) {
        Write-Log "  WARN: Confidence $Confidence < 0.80 for $Action action. Changing to archive_only." "WARN"
        $Action = "archive_only"
    }

    # Create destination directory
    $DestDir = Split-Path -Parent $DestPath
    if (-not (Test-Path $DestDir)) {
        Write-Log "  INFO: Creating destination directory: $DestDir" "INFO"
        try {
            New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
            $Stats.CreatedDirs++
            Write-Log "  SUCCESS: Created directory: $DestDir" "INFO"
        } catch {
            Write-Log "  ERROR: Failed to create directory $DestDir : $_" "ERROR"
            $Stats.Errors++
            return
        }
    }

    # Perform actual action
    try {
        switch ($Action.ToLower()) {
            "move" {
                Write-Log "  EXECUTING MOVE: $SourcePath -> $DestPath" "WARN"
                Move-Item -Path $SourcePath -Destination $DestPath -ErrorAction Stop
                $Stats.Move++
                Write-Log "  SUCCESS: Moved file" "INFO"
            }
            "copy" {
                Write-Log "  EXECUTING COPY: $SourcePath -> $DestPath" "WARN"
                Copy-Item -Path $SourcePath -Destination $DestPath -ErrorAction Stop
                $Stats.Copy++
                Write-Log "  SUCCESS: Copied file" "INFO"
            }
            "archive_only" {
                Write-Log "  ARCHIVE ONLY: $SourcePath -> $DestPath (copying to archive, source preserved)" "INFO"
                Write-Log "  NOTE: $Notes" "INFO"
                Copy-Item -Path $SourcePath -Destination $DestPath -ErrorAction Stop
                $Stats.ArchiveOnly++
                Write-Log "  SUCCESS: Copied to archive (source preserved)" "INFO"
            }
            default {
                Write-Log "  WARN: Unknown action '$Action', skipping" "WARN"
                $Stats.Errors++
            }
        }
    } catch {
        Write-Log "  ERROR: Failed to process $Action for $SourcePath : $_" "ERROR"
        $Stats.Errors++
    }
}

# Process each manifest entry
foreach ($Entry in $Manifest) {
    $SourcePath = $Entry.source_path
    $DestPath = $Entry.dest_path
    $Action = $Entry.action.ToLower()
    $Confidence = [double]$Entry.confidence
    $Reason = $Entry.reason
    $Notes = $Entry.notes

    Write-Log "Processing: $SourcePath" "INFO"
    Write-Log "  -> Action: $Action | Confidence: $Confidence | Reason: $Reason" "INFO"

    # Handle skip actions
    if ($Action -eq "skip") {
        Write-Log "  SKIP: $Notes" "INFO"
        $Stats.Skip++
        continue
    }

    # Hard-skip wildcards/globs to prevent unintended moves
    if ($SourcePath -match '[\*\?]' -or $DestPath -match '[\*\?]' -or $SourcePath -match '\\\*' -or $SourcePath -match '\*\*') {
        Write-Log "  SKIP: Wildcard/glob entry not supported in v1: $SourcePath -> $DestPath" "WARN"
        $Stats.Skip++
        continue
    }

    # Hard-skip anything outside the chunk root
    if (-not ($SourcePath.StartsWith($ChunkRoot, [System.StringComparison]::OrdinalIgnoreCase)) -or
        -not ($DestPath.StartsWith($ChunkRoot, [System.StringComparison]::OrdinalIgnoreCase))) {
        Write-Log "  SKIP: Outside chunk root: $SourcePath -> $DestPath" "ERROR"
        $Stats.Errors++
        continue
    }

    # Process single entry
    Process-ManifestEntry -SourcePath $SourcePath -DestPath $DestPath -Action $Action -Confidence $Confidence -Reason $Reason -Notes $Notes -Stats $Stats
}

# Final summary
Write-Log "" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Execute Summary" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Total entries: $($Stats.Total)" "INFO"
Write-Log "Moved: $($Stats.Move)" "INFO"
Write-Log "Copied: $($Stats.Copy)" "INFO"
Write-Log "Archive only (low confidence): $($Stats.ArchiveOnly)" "INFO"
Write-Log "Skipped: $($Stats.Skip)" "INFO"
Write-Log "Missing sources: $($Stats.Missing)" "INFO"
Write-Log "Errors: $($Stats.Errors)" "INFO"
Write-Log "Directories created: $($Stats.CreatedDirs)" "INFO"
Write-Log "" "INFO"
Write-Log "Execute completed. Review log: $LogFile" "INFO"
Write-Log "================================================" "INFO"
