# AI Lab Command Center - Install backend + frontend dependencies
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$VenvPath = Join-Path $Root ".venv"

Write-Host ""
Write-Host "  AI Lab - Command Center - Deps" -ForegroundColor Cyan
Write-Host "  -------------------------------" -ForegroundColor DarkGray

$envPath = Join-Path $Root "backend\.env"
$envMinimal = Join-Path $Root "backend\env.minimal"
if (-not (Test-Path $envPath)) {
    Write-Host "  [warn] No .env - copying env.minimal (local-only)" -ForegroundColor Yellow
    Copy-Item $envMinimal $envPath
}

# Prefer Python 3.12/3.11 - 3.14 lacks prebuilt wheels for pydantic-core (needs Rust)
$venvPython = Join-Path $VenvPath "Scripts\python.exe"
$needRecreate = $false
if (Test-Path $venvPython) {
    $ver = & $venvPython -c "import sys; print(sys.version_info.minor)" 2>$null
    if ($ver -ge 14) { $needRecreate = $true }
}
if (-not (Test-Path $venvPython) -or $needRecreate) {
    if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host "  [1/3] Creating .venv..." -ForegroundColor Gray
    $created = $false
    foreach ($v in @("3.12", "3.11", "3.10")) {
        if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
        & py -$v -m venv $VenvPath 2>$null | Out-Null
        if (Test-Path $venvPython) { $created = $true; break }
    }
    if (-not $created) {
        Write-Host "  [warn] Python 3.12/3.11 not found. Install via: winget install Python.Python.3.12" -ForegroundColor Yellow
        if (Test-Path $VenvPath) { Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue }
        & python -m venv $VenvPath
    }
}
Write-Host "  [2/3] Installing backend deps..." -ForegroundColor Gray
$pip = Join-Path $VenvPath "Scripts\pip.exe"
& $pip install -r (Join-Path $Root "backend\requirements.txt") -q

Write-Host "  [3/3] Installing frontend deps..." -ForegroundColor Gray
Push-Location (Join-Path $Root "frontend")
npm install --silent
Pop-Location

Write-Host ""
$msg = "  Dependencies installed."
Write-Host $msg -ForegroundColor Green
Write-Host ""
