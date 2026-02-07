# Script to show Kylo watcher logs in real-time
Set-Location "D:\Project-Kylo"

$logFile = ".\.kylo\watch.log"
$logDir = ".\.kylo"

Write-Host "=== Kylo Watcher Logs Monitor ===" -ForegroundColor Cyan
Write-Host "Log file: $logFile" -ForegroundColor Gray
Write-Host "Press Ctrl+C to close this window`n" -ForegroundColor Yellow

# Create log file if it doesn't exist
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

if (!(Test-Path $logFile)) {
    Write-Host "Waiting for watcher to start and create log file..." -ForegroundColor Yellow
    Write-Host "If this persists, check if the watcher is running:`n" -ForegroundColor Yellow
    Write-Host "  Get-Job | Where-Object { `$_.Id -eq (Get-Content .\.kylo\startup\background_jobs.json | ConvertFrom-Json).kylo_watcher }" -ForegroundColor Gray
    Write-Host ""
}

# Monitor the log file in real-time
$lastSize = 0
if (Test-Path $logFile) {
    $lastSize = (Get-Item $logFile).Length
    # Show existing content
    Get-Content $logFile -Tail 50
    Write-Host "`n--- Following new log entries (Ctrl+C to stop) ---`n" -ForegroundColor Green
}

while ($true) {
    if (Test-Path $logFile) {
        $currentSize = (Get-Item $logFile).Length
        if ($currentSize -gt $lastSize) {
            # New content available
            # IMPORTANT (Windows):
            # Open with FileShare.ReadWrite so we don't block the watcher from writing to watch.log.
            $fs = [System.IO.File]::Open($logFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $reader = [System.IO.StreamReader]::new($fs)
            try {
                $reader.BaseStream.Position = $lastSize
                while ($null -ne ($line = $reader.ReadLine())) {
                    Write-Host $line
                }
            } finally {
                $reader.Close()
                $fs.Close()
            }
            $lastSize = $currentSize
        }
    } else {
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
    Start-Sleep -Milliseconds 500
}

