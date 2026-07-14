# Archive underscore one-off scripts into scripts/_archive/

# Run from Growflow repo root when ready:
#   powershell -File scripts/archive_underscore_scripts.ps1

$ErrorActionPreference = "Stop"
$scripts = Resolve-Path (Join-Path $PSScriptRoot ".")
$dest = Join-Path $scripts "_archive"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$count = 0
Get-ChildItem -Path $scripts -Filter "_*.py" -File | ForEach-Object {
    Move-Item -LiteralPath $_.FullName -Destination (Join-Path $dest $_.Name) -Force
    $count++
}
Write-Host "Moved $count scripts into scripts/_archive/"
