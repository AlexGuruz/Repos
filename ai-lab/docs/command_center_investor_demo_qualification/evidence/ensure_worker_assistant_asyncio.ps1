# Ensure worker_assistant on :8765 using asyncio.serve (Windows-safe).
# Prefer this over bare `python -m uvicorn ...` which can hang before bind on this host.

param(
    [string]$RepoRoot = "C:\worker\worker_ai",
    [string]$Port = "8765"
)

$ErrorActionPreference = "Continue"
$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$logDir = "C:\worker\logs\worker_assistant"
$servePy = Join-Path $logDir "wa_serve.py"
$runBat = Join-Path $logDir "run_wa_serve.bat"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Stop prior listeners on port
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
}

if (-not (Test-Path $servePy)) {
    Write-Host "Missing $servePy — copy from qualification evidence wa_serve.py" -ForegroundColor Red
    exit 1
}

# Detached start via cmd so OpenSSH/scheduler keep process alive
$env:PYTHONPATH = $RepoRoot
cmd.exe /c "start /B `"WA`" `"$runBat`""
Start-Sleep -Seconds 12
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
    Write-Host ("health ok: " + ($h | ConvertTo-Json -Compress)) -ForegroundColor Green
} catch {
    Write-Host "health failed: $($_.Exception.Message)" -ForegroundColor Yellow
    if (Test-Path "$logDir\trace.txt") { Get-Content "$logDir\trace.txt" }
    exit 1
}
