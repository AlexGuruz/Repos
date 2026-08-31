# AI Lab Command Center - Bootstrap: deps + backend + frontend
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "  AI Lab - Command Center - Bootstrap" -ForegroundColor Cyan
Write-Host "  ------------------------------------" -ForegroundColor DarkGray

# Install deps (calls deps.ps1)
& (Join-Path $ScriptDir "deps.ps1")

# Launch backend (venv + uvicorn from backend/ so .env is found)
Write-Host "  Launching backend + frontend..." -ForegroundColor Gray
$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$backendDir = Join-Path $Root "backend"
$backendCmd = "`& '" + $venvPython + "' -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WorkingDirectory $backendDir -WindowStyle Normal -PassThru

# Launch frontend
Start-Sleep -Seconds 1
$frontendDir = Join-Path $Root "frontend"
$frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev" -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru

Write-Host ""
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:5173" -ForegroundColor Green
Write-Host "  WS       -> ws://localhost:8000/ws/events" -ForegroundColor Green
Write-Host ""
$bId = $backendProc.Id
$fId = $frontendProc.Id
Write-Host "  Running in background." -ForegroundColor DarkGray
Write-Host "  To stop: Stop-Process -Id $bId, $fId -Force" -ForegroundColor DarkGray
