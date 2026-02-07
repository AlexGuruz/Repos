$DriveRoot = "D:\"
$MainRoot  = "D:\Project-Kylo"
$OutDir    = "D:\_PORTABLE_CONTROL\_audit\kylo_duplicates"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Report = Join-Path $OutDir "kylo_duplicate_candidates.csv"

# Fingerprint markers typical of Kylo-style repos
$Markers = @(
  "docker-compose.yml",
  "pyproject.toml",
  "requirements.txt",
  "run.py",
  "start.py",
  "config\kylo.config.yaml",
  "config\kylo.config.yml",
  "config\instances",
  "config\companies",
  "services",
  "scripts",
  "docs"
)

# Folders to skip (noise)
$SkipDirs = @(
  "$DriveRoot`System Volume Information",
  "$DriveRoot`$RECYCLE.BIN",
  "$DriveRoot`Windows",
  "$DriveRoot`Program Files",
  "$DriveRoot`Program Files (x86)"
)

function Get-Score($path) {
  $score = 0
  foreach ($m in $Markers) {
    if (Test-Path (Join-Path $path $m)) { $score++ }
  }
  return $score
}

# Find candidate folders: any folder that contains at least 3 marker hits
$candidates = Get-ChildItem -LiteralPath $DriveRoot -Directory -Force -ErrorAction SilentlyContinue |
  Where-Object { $SkipDirs -notcontains $_.FullName } |
  ForEach-Object {
    $p = $_.FullName
    $score = Get-Score $p
    if ($score -ge 3) {
      $hasGit = Test-Path (Join-Path $p ".git")
      $size = (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
      [PSCustomObject]@{
        path = $p
        score = $score
        has_git = $hasGit
        size_bytes = [int64]$size
      }
    }
  }

# Add main repo fingerprint info for reference
$mainScore = Get-Score $MainRoot

$candidates |
  Sort-Object score -Descending |
  Export-Csv -NoTypeInformation -Encoding UTF8 -Path $Report

Write-Host "Main repo marker score: $mainScore"
Write-Host "Wrote: $Report"
