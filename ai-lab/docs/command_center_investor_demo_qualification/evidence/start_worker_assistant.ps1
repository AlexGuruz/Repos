# Start the worker_assistant FastAPI app (worker rig).
# When ai-lab governance root exists, runs verify_governance; if missing, starts in autonomous (read-only) mode.
# Logs to C:\worker\logs\worker_assistant\api.log if dir exists; otherwise console.
# Port from env WORKER_ASSISTANT_PORT (default 8765).

$ErrorActionPreference = "Stop"
$port = if ($env:WORKER_ASSISTANT_PORT) { $env:WORKER_ASSISTANT_PORT } else { "8765" }
$logDir = "C:\worker\logs\worker_assistant"
$logFile = Join-Path $logDir "api.log"
$governanceRoot = "C:\Users\worker\ai-lab"

# Repo root = worker_ai (script lives in worker_ai\scripts)
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonExe = "python"
if (Test-Path (Join-Path $repoRoot ".venv\Scripts\python.exe")) {
    $pythonExe = (Join-Path $repoRoot ".venv\Scripts\python.exe")
}

# Governance: if ai-lab present and verify_governance passes, use it; else start autonomous (app runs read-only).
$verifyScript = Join-Path $governanceRoot "Ai\scripts\verify_governance.py"
if (Test-Path $verifyScript) {
    $env:AI_LAB_GOVERNANCE_ROOT = $governanceRoot
    $env:AI_LAB_MACHINE = "worker"
    $env:AI_LAB_ENFORCEMENT = "1"
    & $pythonExe $verifyScript 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $env:AI_LAB_GOVERNANCE_ROOT = ""
        Write-Host "Governance verification skipped (autonomous mode)." -ForegroundColor Yellow
    }
} else {
    $env:AI_LAB_GOVERNANCE_ROOT = ""
    Write-Host "Governance root missing; starting in autonomous (read-only) mode." -ForegroundColor Yellow
}

$env:PYTHONPATH = $repoRoot
Set-Location $repoRoot

if (Test-Path $logDir) {
    Write-Host "Starting worker_assistant on port $port (logging to $logFile)" -ForegroundColor Cyan
    Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "worker_assistant.app.main:app", "--host", "0.0.0.0", "--port", $port -NoNewWindow -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err"
} else {
    Write-Host "Starting worker_assistant on port $port (console)" -ForegroundColor Cyan
    & $pythonExe -m uvicorn worker_assistant.app.main:app --host 0.0.0.0 --port $port
}
