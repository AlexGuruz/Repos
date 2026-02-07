# Auto-start Kylo + ScriptHub (clean, minimal, non-interactive)
# - Starts Docker services (via start_all_services.ps1)
# - Starts Kylo watcher as a PowerShell background job
# - Starts ScriptHub FastAPI server (local folder) as a PowerShell background job
# - Writes job IDs to .\.kylo\startup\background_jobs.json so stop_all_services.ps1 can stop them

$ErrorActionPreference = "Stop"

$repoRoot = "D:\Project-Kylo"
$scriptHubPath = Join-Path $repoRoot "tools\scripthub_legacy"

Set-Location $repoRoot

$startupDir = ".\.kylo\startup"
if (!(Test-Path $startupDir)) { New-Item -ItemType Directory -Force -Path $startupDir | Out-Null }
$logFile = Join-Path $startupDir ("auto_start_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss"))

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[{0}] {1}" -f $ts, $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Write-Log "=== Kylo Auto-Start (minimal) ==="
Write-Log ("Repo: " + $repoRoot)
Write-Log ("Log:  " + $logFile)

# Wait for Docker Desktop (up to 120s)
Write-Log "Waiting for Docker Desktop..."
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    try {
        docker ps | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
    } catch {}
    Start-Sleep -Seconds 5
}
try { docker ps | Out-Null } catch {}
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: Docker not ready; start Docker Desktop and rerun."
    exit 1
}
Write-Log "Docker is ready."

# Start docker-based services (Postgres/Redpanda/consumers)
Write-Log "Starting Kylo docker services (start_all_services.ps1)..."
& "$repoRoot\start_all_services.ps1"
Write-Log "Kylo docker services started."

# Start Kylo watcher as a background job
Write-Log "Starting Kylo watcher job..."
$watcherJob = Start-Job -Name "kylo_watcher" -ScriptBlock {
    param($root)
    Set-Location $root
    # Default behavior: watch BOTH 2025 + 2026 unless the user explicitly overrides.
    # This ensures "uncheck Column F to re-run" works for prior-year workbooks too.
    if (-not $env:KYLO_ACTIVE_YEARS) {
        $env:KYLO_ACTIVE_YEARS = "2025,2026"
    }
    $env:KYLO_WATCH_INTERVAL_SECS = "300"
    $env:PYTHONUNBUFFERED = "1"
    python -u -m bin.watch_all *> .\.kylo\watch.log
} -ArgumentList $repoRoot
Write-Log ("Watcher job started (Job ID: {0})" -f $watcherJob.Id)

# Start ScriptHub server as a background job (local folder)
$scriptHubJob = $null
if (Test-Path $scriptHubPath) {
    Write-Log "Starting ScriptHub server job..."
    $scriptHubJob = Start-Job -Name "scripthub_server" -ScriptBlock {
        param($path)
        Set-Location $path
        $env:PYTHONPATH = $path
        $logs = ".\.logs"
        if (!(Test-Path $logs)) { New-Item -ItemType Directory -Force -Path $logs | Out-Null }
        $serverLog = Join-Path $logs ("server_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss"))
        python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> $serverLog
    } -ArgumentList $scriptHubPath
    Write-Log ("ScriptHub server job started (Job ID: {0})" -f $scriptHubJob.Id)
} else {
    Write-Log ("WARNING: ScriptHub directory not found: " + $scriptHubPath)
}

# Start sync runner as a background job
Write-Log "Starting sync runner job..."
$syncRunnerJob = Start-Job -Name "kylo_sync_runner" -ScriptBlock {
    param($root)
    Set-Location $root
    $env:KYLO_CONFIG_PATH = "config/global.yaml"
    $env:KYLO_SYNC_INTERVAL_SECS = "300"
    $env:PYTHONUNBUFFERED = "1"
    $syncLogDir = ".\.kylo\sync"
    if (!(Test-Path $syncLogDir)) { New-Item -ItemType Directory -Force -Path $syncLogDir | Out-Null }
    & "$root\.venv\Scripts\python.exe" -u .\tools\scripthub_legacy\sync_runner.py *> (Join-Path $syncLogDir "sync_runner.log")
} -ArgumentList $repoRoot
Write-Log ("Sync runner job started (Job ID: {0})" -f $syncRunnerJob.Id)

# Save job IDs for stop_all_services.ps1
$jobsFile = ".\.kylo\startup\background_jobs.json"
$payload = @{
    kylo_watcher    = if ($watcherJob) { $watcherJob.Id } else { $null }
    scriptHub_server = if ($scriptHubJob) { $scriptHubJob.Id } else { $null }
    sync_runner     = if ($syncRunnerJob) { $syncRunnerJob.Id } else { $null }
    timestamp       = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}
$payload | ConvertTo-Json | Out-File -FilePath $jobsFile -Encoding UTF8
Write-Log ("Background job IDs saved to: " + $jobsFile)
Write-Log "=== Auto-Start Complete ==="

