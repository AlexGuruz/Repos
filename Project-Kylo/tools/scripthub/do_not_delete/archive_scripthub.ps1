# Archive ScriptHub Before Deletion
# Run this script to safely archive ScriptHub before deleting it

$ErrorActionPreference = "Stop"

$ScriptHubPath = "D:\ScriptHub"
$ArchiveDate = Get-Date -Format "yyyy-MM-dd"
$ArchiveRoot = "D:\_archive\$ArchiveDate\scripthub"
$ArchiveZip = "$ArchiveRoot\ScriptHub.zip"
$ArchiveBundle = "$ArchiveRoot\ScriptHub.bundle"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "ScriptHub Archive Script" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Check if ScriptHub exists
if (-not (Test-Path $ScriptHubPath)) {
    Write-Host "ERROR: ScriptHub not found at $ScriptHubPath" -ForegroundColor Red
    exit 1
}

Write-Host "ScriptHub found: $ScriptHubPath" -ForegroundColor Green
Write-Host ""

# Create archive directory
Write-Host "Creating archive directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null
Write-Host "Archive directory: $ArchiveRoot" -ForegroundColor Green
Write-Host ""

# Create zip archive
Write-Host "Creating ZIP archive (this may take a while)..." -ForegroundColor Yellow
try {
    Compress-Archive -Path $ScriptHubPath -DestinationPath $ArchiveZip -Force
    $zipSize = (Get-Item $ArchiveZip).Length / 1MB
    Write-Host "ZIP archive created: $ArchiveZip ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green
} catch {
    Write-Host "ERROR creating ZIP: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Create git bundle if it's a git repo
if (Test-Path "$ScriptHubPath\.git") {
    Write-Host "ScriptHub is a git repository. Creating bundle..." -ForegroundColor Yellow
    Push-Location $ScriptHubPath
    try {
        git bundle create $ArchiveBundle --all
        $bundleSize = (Get-Item $ArchiveBundle).Length / 1MB
        Write-Host "Git bundle created: $ArchiveBundle ($([math]::Round($bundleSize, 2)) MB)" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: Could not create git bundle: $_" -ForegroundColor Yellow
        Write-Host "  (This is OK if git is not available or repo has issues)" -ForegroundColor Yellow
    }
    Pop-Location
    Write-Host ""
} else {
    Write-Host "ScriptHub is not a git repository. Skipping bundle." -ForegroundColor Yellow
    Write-Host ""
}

# Summary
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Archive Complete!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Archive location: $ArchiveRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Verify the archive files exist and are valid" -ForegroundColor White
Write-Host "2. Test the vendored scripts in Kylo work correctly" -ForegroundColor White
Write-Host "3. Then you can safely move ScriptHub:" -ForegroundColor White
Write-Host "   move D:\ScriptHub D:\_archive\$ArchiveDate\scripthub\ScriptHub_original" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or delete it (after verification):" -ForegroundColor White
Write-Host "   Remove-Item D:\ScriptHub -Recurse -Force" -ForegroundColor Cyan
Write-Host ""
