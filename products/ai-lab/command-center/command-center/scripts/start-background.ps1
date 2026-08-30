# Command Center — same setup as start.ps1, but backend + frontend run hidden (no console windows).
# Logs: .logs/backend.log, .logs/backend.err.log, .logs/frontend.log, .logs/frontend.err.log
# Usage: .\start-background.ps1   |   .\start-background.ps1 -LocalOnly   |   .\start-background.ps1 -OpenBrowser
param(
    [switch]$LocalOnly,
    [switch]$OpenBrowser,
    # Windows: --reload often leaves zombie workers holding :8000 while HTTP hangs.
    [switch]$Reload
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$AI_LAB_ROOT = (Split-Path -Parent (Split-Path -Parent $Root))
$VenvPath = Join-Path $Root ".venv"
$venvPython = Join-Path $VenvPath "Scripts\python.exe"
$venvPip = Join-Path $VenvPath "Scripts\pip.exe"
$LogDir = Join-Path $Root ".logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

Write-Host ""
Write-Host "  AI Lab Command Center (background)" -ForegroundColor Cyan
Write-Host "  -----------------------------------" -ForegroundColor DarkGray

$envPath = Join-Path $Root "backend\.env"
$envMinimal = Join-Path $Root "backend\env.minimal"
if ($LocalOnly -or (-not (Test-Path $envPath))) {
    Write-Host "  [1/4] Using env.minimal (local-only)" -ForegroundColor Yellow
    Copy-Item $envMinimal $envPath -Force
} else {
    Write-Host "  [1/4] .env found" -ForegroundColor Gray
}

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
        Write-Host "  [warn] Python 3.12/3.11 not found." -ForegroundColor Yellow
        if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
        & python -m venv $VenvPath
    }
}
$backendPath = Join-Path $Root "backend"
& $venvPip install -r (Join-Path $backendPath "requirements.txt") -q
if ($LASTEXITCODE -ne 0) { & $venvPip install -r (Join-Path $backendPath "requirements.txt") }

Write-Host "  [3/4] Frontend deps..." -ForegroundColor Gray
Push-Location (Join-Path $Root "frontend")
try {
    cmd /c "npm install --silent"
    if ($LASTEXITCODE -ne 0) { cmd /c "npm install" }
} finally { Pop-Location }

$backendDir = Join-Path $Root "backend"
$frontendDir = Join-Path $Root "frontend"
$backendLog = Join-Path $LogDir "backend.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$frontendLog = Join-Path $LogDir "frontend.log"
$frontendErr = Join-Path $LogDir "frontend.err.log"
foreach ($f in @($backendLog, $backendErr, $frontendLog, $frontendErr)) {
    "`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') start-background =====`n" | Out-File -FilePath $f -Append -Encoding utf8
}

Write-Host "  [4/4] Starting backend + frontend (hidden)..." -ForegroundColor Gray
Write-Host "  Logs -> $LogDir" -ForegroundColor DarkGray

# PS 5.1: no Start-Process -Environment; use cmd to set PYTHONPATH for this process tree.
$p = @{ WindowStyle = "Hidden" }
$reloadFlag = if ($Reload) { " --reload" } else { "" }
if ($Reload) {
    Write-Host "  [warn] --reload enabled (can wedge :8000 on Windows)." -ForegroundColor Yellow
}
# Prefer single-process launcher (avoids --workers/--reload supervisor quirks on Windows).
if ($Reload) {
    $backendCmd = "set PYTHONPATH=$AI_LAB_ROOT&& set OPERATOR_DESK_ENABLED=1&& cd /d `"$backendDir`" && `"$venvPython`" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
} else {
    $backendCmd = "set PYTHONPATH=$AI_LAB_ROOT&& set OPERATOR_DESK_ENABLED=1&& set CC_LIGHT_MODE=1&& `"$venvPython`" `"$Root\scripts\run_uvicorn_once.py`""
}
Start-Process @p -FilePath "cmd.exe" -ArgumentList @("/c", $backendCmd) `
    -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr | Out-Null

Start-Sleep -Seconds 2

Start-Process @p -FilePath "cmd.exe" -ArgumentList @("/c", "npm run dev") -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr | Out-Null

if ($OpenBrowser) {
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:5173"
}

Write-Host ""
Write-Host "  UI  -> http://localhost:5173" -ForegroundColor Green
Write-Host "  API -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  WS  -> ws://127.0.0.1:8000/ws/events" -ForegroundColor Green
Write-Host ""
Write-Host "  Stop: .\stop.ps1" -ForegroundColor DarkGray
