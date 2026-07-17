# Start the KYLO_2026_SANDBOX live intake mirror (120s poll).
# One-way: LIVE 2026 TRANSACTIONS/BANK (full rows incl. NOTES/log) -> sandbox.
# Does NOT start or touch KYLO_2025 / KYLO_2026 live watchers.
#
# Usage:
#   .\scripts\active\start_sandbox_live_mirror.ps1
#   .\scripts\active\start_sandbox_live_mirror.ps1 -IntervalSecs 120 -Once
#   .\scripts\active\start_sandbox_live_mirror.ps1 -Hidden

param(
    [int]$IntervalSecs = 120,
    [switch]$Once,
    [switch]$Force,
    [switch]$Hidden
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot

$PythonExe = if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
    "$RepoRoot\.venv\Scripts\python.exe"
} else {
    "python"
}

$instanceId = "KYLO_2026_SANDBOX"
$logDir = ".\.kylo\instances\$instanceId\logs"
$logPath = Join-Path $logDir "sandbox_mirror.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path ".\.kylo\instances\$instanceId\health" | Out-Null
New-Item -ItemType Directory -Force -Path ".\.kylo\instances\$instanceId\state" | Out-Null

$argList = @("-u", "scripts\sandbox_live_mirror_daemon.py", "--interval", "$IntervalSecs")
if ($Once) { $argList += "--once" }
if ($Force) { $argList += "--force" }

$env:KYLO_INSTANCE_ID = $instanceId
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"

$windowStyle = if ($Hidden -or -not $Once) { "Hidden" } else { "Normal" }

# Launch python directly (avoids nested PowerShell encoding / Tee issues).
$p = Start-Process -FilePath $PythonExe `
    -ArgumentList $argList `
    -WorkingDirectory $RepoRoot `
    -WindowStyle $windowStyle `
    -PassThru

# Record PID alongside other background jobs if present.
$jobsFile = ".\.kylo\startup\background_jobs.json"
$existing = @{}
if (Test-Path $jobsFile) {
    try { $existing = Get-Content $jobsFile -Raw | ConvertFrom-Json } catch { $existing = @{} }
}
$payload = @{}
if ($existing) {
    $existing.PSObject.Properties | ForEach-Object { $payload[$_.Name] = $_.Value }
}
$payload["sandbox_mirror_pid"] = $p.Id
$payload["sandbox_mirror_instance_id"] = $instanceId
$payload["sandbox_mirror_started_at"] = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
$payload["sandbox_mirror_interval_secs"] = $IntervalSecs
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $jobsFile) | Out-Null
($payload | ConvertTo-Json -Depth 6) | Set-Content -Path $jobsFile -Encoding UTF8

Write-Host "Started sandbox live mirror (PID $($p.Id))" -ForegroundColor Green
Write-Host "  Interval: ${IntervalSecs}s"
Write-Host "  Log:      $logPath"
Write-Host "  Heartbeat:.\.kylo\instances\$instanceId\health\sandbox_mirror.json"
Write-Host "  One-way LIVE TRANSACTIONS/BANK (incl. NOTES/log) -> sandbox"
Write-Host "  Live watchers untouched."
