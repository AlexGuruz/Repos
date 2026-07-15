# Ensure worker_assistant listens on :8765 using asyncio.serve (Windows/SSH-safe).
# Run ON THE WORKER host. Prefer over bare `python -m uvicorn` which can hang pre-bind.
param(
    [string]$RepoRoot = "C:\worker\worker_ai",
    [string]$Port = "8765",
    [string]$LogDir = "C:\worker\logs\worker_assistant"
)

$ErrorActionPreference = "Continue"
$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$servePy = Join-Path $LogDir "wa_serve.py"
$runBat = Join-Path $LogDir "run_wa_serve.bat"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $pythonExe)) {
    Write-Host "Missing venv python: $pythonExe" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $servePy)) {
    Write-Host "Missing $servePy — copy ai-lab/scripts/wa_serve_asyncio.py there as wa_serve.py" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $runBat)) {
    @"
@echo off
set PYTHONPATH=$RepoRoot
set PYTHONUNBUFFERED=1
cd /d $RepoRoot
"$pythonExe" -u "$servePy"
"@ | Set-Content -Path $runBat -Encoding ascii
}

# Stop prior listeners on port (python uvicorn only)
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -match 'python') {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

cmd.exe /c "start `"WorkerAssistant`" /MIN `"$runBat`""
Start-Sleep -Seconds 14
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
    Write-Host ("health ok: " + ($h | ConvertTo-Json -Compress)) -ForegroundColor Green
    exit 0
} catch {
    Write-Host "health failed: $($_.Exception.Message)" -ForegroundColor Yellow
    if (Test-Path (Join-Path $LogDir "trace.txt")) { Get-Content (Join-Path $LogDir "trace.txt") }
    exit 1
}
