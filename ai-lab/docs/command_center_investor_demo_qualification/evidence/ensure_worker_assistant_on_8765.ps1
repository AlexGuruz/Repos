# Ensure worker_assistant is running on port 8765 with current repo code (includes GET /repo_status).
# Run on the WORKER rig, as the user that runs worker_assistant (e.g. worker).
# If the existing process was started by another user or elevated, stop it manually first.

param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$Port = "8765"
)

$ErrorActionPreference = "Continue"
$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }

# Find python process listening on $Port (do not stop ssh)
$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $conns) {
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq "python") {
        Write-Host "Port $Port in use by PID $($proc.Id) (python). Stopping..." -ForegroundColor Yellow
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Start-Sleep -Seconds 2
            Write-Host "Stopped." -ForegroundColor Green
        } catch {
            Write-Host "Could not stop process (run as same user or stop manually): $_" -ForegroundColor Red
            exit 1
        }
        break
    }
}

$env:PYTHONPATH = $RepoRoot
Set-Location $RepoRoot
$logDir = "C:\worker\logs\worker_assistant"
if (Test-Path $logDir) {
    $logFile = Join-Path $logDir "api.log"
    Write-Host "Starting worker_assistant on port $Port (logging to $logFile)" -ForegroundColor Cyan
    Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "worker_assistant.app.main:app", "--host", "0.0.0.0", "--port", $Port -NoNewWindow -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err"
} else {
    Write-Host "Starting worker_assistant on port $Port (console)" -ForegroundColor Cyan
    Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "worker_assistant.app.main:app", "--host", "0.0.0.0", "--port", $Port -NoNewWindow
}
Start-Sleep -Seconds 3
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/repo_status" -Method Get -TimeoutSec 5
    if ($r.ok) { Write-Host "GET /repo_status OK. worker_assistant is running with current code." -ForegroundColor Green } else { Write-Host "Unexpected response: $r" -ForegroundColor Yellow }
} catch {
    Write-Host "Warning: /repo_status check failed: $_" -ForegroundColor Yellow
}
