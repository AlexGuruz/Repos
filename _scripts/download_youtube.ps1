# YouTube to MP4 Downloader Script
# This script downloads YouTube videos as MP4 at 720p quality

Write-Host "=" -NoNewline
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "YouTube to MP4 Converter - 720p" -ForegroundColor Cyan
Write-Host "=" -NoNewline
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "Church\Tools\youtube_to_mp4.py"
$downloadsPath = Join-Path $PSScriptRoot "Church\Youtube"

# Check if Python is available
$pythonCmd = $null
$pythonCommands = @("python", "python3", "py")
foreach ($cmd in $pythonCommands) {
    try {
        $result = Get-Command $cmd -ErrorAction Stop
        $pythonCmd = $result.Name
        break
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python or add it to your PATH." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You can download Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Green
Write-Host "Script: $scriptPath" -ForegroundColor Green
Write-Host "Downloads will be saved to: $downloadsPath" -ForegroundColor Green
Write-Host ""

# Check if yt-dlp is installed
Write-Host "Checking for yt-dlp..." -ForegroundColor Yellow
$checkYtdlp = & $pythonCmd -c "import yt_dlp; print('yt-dlp is installed')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: yt-dlp is not installed!" -ForegroundColor Red
    Write-Host "Installing yt-dlp..." -ForegroundColor Yellow
    & $pythonCmd -m pip install yt-dlp
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install yt-dlp. Please install it manually:" -ForegroundColor Red
        Write-Host "  pip install yt-dlp" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "yt-dlp is ready!" -ForegroundColor Green
Write-Host ""

# Run the Python script
Write-Host "Starting download..." -ForegroundColor Cyan
Write-Host ""
& $pythonCmd $scriptPath

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=" -NoNewline
    Write-Host ("=" * 59) -ForegroundColor Green
    Write-Host "Download process completed!" -ForegroundColor Green
    
    if (Test-Path $downloadsPath) {
        $mp4Files = Get-ChildItem $downloadsPath -Filter "*.mp4" -ErrorAction SilentlyContinue
        if ($mp4Files) {
            Write-Host ""
            Write-Host "Downloaded files:" -ForegroundColor Green
            foreach ($file in $mp4Files) {
                $sizeMB = [math]::Round($file.Length / 1MB, 2)
                Write-Host "  - $($file.Name) ($sizeMB MB)" -ForegroundColor White
            }
            Write-Host ""
            Write-Host "Files location: $downloadsPath" -ForegroundColor Cyan
        } else {
            Write-Host ""
            Write-Host "No MP4 files found in downloads folder." -ForegroundColor Yellow
        }
    }
    Write-Host "=" -NoNewline
    Write-Host ("=" * 59) -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERROR: Download failed!" -ForegroundColor Red
    Write-Host "Please check the error messages above." -ForegroundColor Yellow
}
