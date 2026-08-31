# AI Lab Command Center - Windows start script (local only)
# Usage: .\start.ps1                light mode (CC_LIGHT_MODE=1) — compat / demos only
#        .\start.ps1 -FullMode      daily operator path (CC_LIGHT_MODE=0, real full stack)
#        .\start.ps1 -LocalOnly     force env.minimal (no governance repo required)
#        .\start.ps1 -Reload        enable uvicorn --reload (can wedge :8000 on Windows)
# Backend uses .venv with Python 3.12/3.11 (Python 3.14 has no pydantic-core wheels and needs Rust).
param(
    [switch]$LocalOnly,
    # Daily use: full stack (telemetry poller, prepared context, multi-channel). Prefer this.
    [switch]$FullMode,
    # Windows: --reload often leaves zombie workers holding :8000 while HTTP hangs.
    # Default is a single stable uvicorn process. Pass -Reload only for local file watching.
    [switch]$Reload
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$AI_LAB_ROOT = (Split-Path -Parent (Split-Path -Parent $Root))
$VenvPath = Join-Path $Root ".venv"
$venvPython = Join-Path $VenvPath "Scripts\python.exe"
$venvPip = Join-Path $VenvPath "Scripts\pip.exe"

# Light mode is unsafe for multi-channel daily ops / investor demo. FullMode is the daily path.
$lightMode = if ($FullMode) { "0" } else { "1" }
$modeLabel = if ($FullMode) { "FULL (CC_LIGHT_MODE=0)" } else { "LIGHT (CC_LIGHT_MODE=1) — use -FullMode for daily ops" }

Write-Host ""
Write-Host "  AI Lab Command Center (local)" -ForegroundColor Cyan
Write-Host "  ---------------------------------" -ForegroundColor DarkGray
Write-Host "  Mode: $modeLabel" -ForegroundColor $(if ($FullMode) { "Green" } else { "Yellow" })

# 1) Env
$envPath = Join-Path $Root "backend\.env"
$envMinimal = Join-Path $Root "backend\env.minimal"
if ($LocalOnly -or (-not (Test-Path $envPath))) {
    Write-Host "  [1/4] Using env.minimal (local-only)" -ForegroundColor Yellow
    Copy-Item $envMinimal $envPath -Force
} else {
    Write-Host "  [1/4] .env found" -ForegroundColor Gray
}

# 2) Backend venv + deps (use Python 3.12/3.11 — 3.14 lacks pydantic-core wheels)
Write-Host "  [2/4] Backend deps..." -ForegroundColor Gray
$needRecreate = $false
if (Test-Path $venvPython) {
    $ver = & $venvPython -c "import sys; print(sys.version_info.minor)" 2>$null
    if ($ver -ge 14) { $needRecreate = $true }
}
if (-not (Test-Path $venvPython) -or $needRecreate) {
    if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
    $created = $false
    foreach ($v in @("3.12", "3.11", "3.10")) {
        if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
        & py -$v -m venv $VenvPath 2>$null | Out-Null
        if (Test-Path $venvPython) { $created = $true; break }
    }
    if (-not $created) {
        Write-Host "  [warn] Python 3.12/3.11 not found. Install: winget install Python.Python.3.12" -ForegroundColor Yellow
        if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
        & python -m venv $VenvPath
    }
}
$backendPath = Join-Path $Root "backend"
& $venvPip install -r (Join-Path $backendPath "requirements.txt") -q
if ($LASTEXITCODE -ne 0) { & $venvPip install -r (Join-Path $backendPath "requirements.txt") }

# 3) Frontend deps
Write-Host "  [3/4] Frontend deps..." -ForegroundColor Gray
Push-Location (Join-Path $Root "frontend")
try {
    cmd /c "npm install --silent"
    if ($LASTEXITCODE -ne 0) { cmd /c "npm install" }
} finally { Pop-Location }

# 4) Launch backend and frontend (backend uses .venv + PYTHONPATH for ai-lab root)
$backendDir = Join-Path $Root "backend"
$frontendDir = Join-Path $Root "frontend"
Write-Host "  [4/4] Starting backend and frontend..." -ForegroundColor Gray
# Bind loopback only so port 8000 is not shared with stray 0.0.0.0 listeners from other uvicorn runs.
# CC_LIGHT_MODE must be set in the child before run_uvicorn_once.py (that launcher setdefaults light=1).
if ($Reload) {
    Write-Host "  [warn] --reload enabled (can wedge :8000 on Windows). Prefer default for Approve/Deny." -ForegroundColor Yellow
    $backendCmd = "`$env:PYTHONPATH = '$AI_LAB_ROOT'; `$env:OPERATOR_DESK_ENABLED = '1'; `$env:CC_LIGHT_MODE = '$lightMode'; Set-Location '$backendDir'; & '$venvPython' -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
} else {
    # Single-process launcher (no --reload / --workers supervisor quirks).
    $backendCmd = "`$env:PYTHONPATH = '$AI_LAB_ROOT'; `$env:OPERATOR_DESK_ENABLED = '1'; `$env:CC_LIGHT_MODE = '$lightMode'; & '$venvPython' '$Root\scripts\run_uvicorn_once.py'"
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru | Out-Null
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev" -PassThru | Out-Null

# Open browser after short delay
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "  UI  -> http://localhost:5173  (browser opened)" -ForegroundColor Green
Write-Host "  API -> http://localhost:8000" -ForegroundColor Green
Write-Host "  WS  -> ws://localhost:8000/ws/control (+ ops/chat; telemetry on Compute)" -ForegroundColor Green
Write-Host "  Mode: CC_LIGHT_MODE=$lightMode  FullMode=$($FullMode.IsPresent)" -ForegroundColor DarkGray
Write-Host "  Backend reload: $($Reload.IsPresent)" -ForegroundColor DarkGray
Write-Host ""
if (-not $FullMode) {
    Write-Host "  Tip: for daily multi-channel use run:  .\scripts\start.ps1 -FullMode" -ForegroundColor Yellow
    Write-Host ""
}
Write-Host "  Stop: .\stop.ps1   (or close the two spawned PowerShell windows)" -ForegroundColor DarkGray
