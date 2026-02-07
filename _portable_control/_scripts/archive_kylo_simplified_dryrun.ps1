# archive_kylo_simplified_dryrun.ps1
# Archive Dry-Run Script for Kylo-Simplified
# Reads archive_manifest.v1.csv and performs -WhatIf operations only

param(
    [string]$ManifestPath = "D:\_PORTABLE_CONTROL\_manifests\kylo_simplified\archive_manifest.v1.csv",
    [switch]$ShowLog
)

$ErrorActionPreference = "Continue"
$LogFile = "D:\_PORTABLE_CONTROL\_logs\archive_kylo_simplified_dryrun.log"
$AllowedSourceRoots = @("D:\Kylo-Simplified")
$AllowedDestRoots = @("D:\_archive")

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
Write-Log "Kylo-Simplified Archive Dry-Run Script Started" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Manifest: $ManifestPath" "INFO"
Write-Log "Mode: DRY-RUN (WhatIf only - no actual moves)" "INFO"
Write-Log "" "INFO"

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

# Function to check if path is within allowed roots
function Test-AllowedPath {
    param([string]$Path, [string[]]$AllowedRoots)
    foreach ($root in $AllowedRoots) {
        if ($Path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
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
            New-Item -ItemType Directory -Force -Path $DestDir -WhatIf | Out-Null
            $Stats.CreatedDirs++
            Write-Log "  SUCCESS: Would create directory: $DestDir" "INFO"
        } catch {
            Write-Log "  ERROR: Failed to create directory $DestDir : $_" "ERROR"
            $Stats.Errors++
            return
        }
    }

    # Perform action with -WhatIf
    try {
        switch ($Action.ToLower()) {
            "move" {
                Write-Log "  DRY-RUN MOVE: $SourcePath -> $DestPath" "INFO"
                Move-Item -Path $SourcePath -Destination $DestPath -WhatIf -ErrorAction Stop
                $Stats.Move++
                Write-Log "  SUCCESS: Would move directory" "INFO"
            }
            "copy" {
                Write-Log "  DRY-RUN COPY: $SourcePath -> $DestPath" "INFO"
                Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -WhatIf -ErrorAction Stop
                $Stats.Copy++
                Write-Log "  SUCCESS: Would copy directory" "INFO"
            }
            "archive_only" {
                Write-Log "  ARCHIVE ONLY: $SourcePath -> $DestPath (copying to archive, source preserved)" "INFO"
                Write-Log "  NOTE: $Notes" "INFO"
                Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -WhatIf -ErrorAction Stop
                $Stats.ArchiveOnly++
                Write-Log "  SUCCESS: Would copy to archive (source preserved)" "INFO"
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

    # Validate source is within allowed roots
    if (-not (Test-AllowedPath -Path $SourcePath -AllowedRoots $AllowedSourceRoots)) {
        Write-Log "  SKIP: Source outside allowed roots: $SourcePath" "ERROR"
        $Stats.Errors++
        continue
    }

    # Validate destination is within allowed roots
    if (-not (Test-AllowedPath -Path $DestPath -AllowedRoots $AllowedDestRoots)) {
        Write-Log "  SKIP: Destination outside allowed roots: $DestPath" "ERROR"
        $Stats.Errors++
        continue
    }

    # Process single entry
    Process-ManifestEntry -SourcePath $SourcePath -DestPath $DestPath -Action $Action -Confidence $Confidence -Reason $Reason -Notes $Notes -Stats $Stats
}

# Final summary
Write-Log "" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Dry-Run Summary" "INFO"
Write-Log "================================================" "INFO"
Write-Log "Total entries: $($Stats.Total)" "INFO"
Write-Log "Would move: $($Stats.Move)" "INFO"
Write-Log "Would copy: $($Stats.Copy)" "INFO"
Write-Log "Archive only (low confidence): $($Stats.ArchiveOnly)" "INFO"
Write-Log "Skipped: $($Stats.Skip)" "INFO"
Write-Log "Missing sources: $($Stats.Missing)" "INFO"
Write-Log "Errors: $($Stats.Errors)" "INFO"
Write-Log "Directories created: $($Stats.CreatedDirs)" "INFO"
Write-Log "" "INFO"
Write-Log "Dry-Run completed. Review log: $LogFile" "INFO"
Write-Log "To execute moves, run: .\archive_kylo_simplified_execute.ps1 -Execute" "INFO"
Write-Log "================================================" "INFO"
