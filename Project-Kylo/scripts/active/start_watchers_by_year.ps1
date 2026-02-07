# Start two Kylo watcher instances (2025 + 2026) in separate PowerShell windows.
# Each watcher is labeled with an instance_id: KYLO_<YEAR> (example: KYLO_2025).
# These watchers process ALL companies (NUGZ, EMPIRE, PUFFIN, JGD) but only monitor
# transactions for their assigned year (2025 or 2026) based on year_workbooks config.
#
# Outputs:
#   .\.kylo\instances\<INSTANCE_ID>\logs\watcher.log
#   .\.kylo\instances\<INSTANCE_ID>\state\watch_state.json
#   .\.kylo\instances\<INSTANCE_ID>\state\posting_state.json
#   .\.kylo\instances\<INSTANCE_ID>\health\heartbeat.json
#   .\.kylo\startup\background_jobs.json  (stores watcher_*_pid + watcher_*_instance_id)

param(
    [string]$IntervalSecs = "300"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot

$PythonExe = if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") { "$RepoRoot\.venv\Scripts\python.exe" } else { "python" }

$kyloDir = ".\.kylo"
$startupDir = Join-Path $kyloDir "startup"
if (!(Test-Path $kyloDir)) { New-Item -ItemType Directory -Force -Path $kyloDir | Out-Null }
if (!(Test-Path $startupDir)) { New-Item -ItemType Directory -Force -Path $startupDir | Out-Null }

function Start-WatcherWindow {
    param(
        [Parameter(Mandatory=$true)][string]$Year,
        [Parameter(Mandatory=$true)][string]$WatcherName
    )

    # Use generic instance ID (KYLO_2025, KYLO_2026) so watcher processes ALL companies
    # The year filtering is handled via --years flag, not by company filtering
    $instanceId = "KYLO_$Year"
    $logPath = ".\.kylo\instances\$instanceId\logs\watcher.log"

    # Command executed in the new PowerShell window.
    # Use Tee-Object to show logs in-window AND persist them to a file.
    $cmd = @"
Set-Location '$RepoRoot'
`$env:KYLO_SECRETS_DIR = '$RepoRoot\.secrets'
`$env:WATCHER_NAME = '$WatcherName'
`$env:KYLO_INSTANCE_ID = '$instanceId'
`$env:KYLO_CONFIG_PATH = 'config/global.yaml'
`$env:KYLO_ACTIVE_YEARS = '$Year'
`$env:KYLO_WATCH_INTERVAL_SECS = '$IntervalSecs'
`$env:PYTHONUNBUFFERED = '1'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent '$logPath') | Out-Null
Write-Host \"=== Kylo Watcher $instanceId ($WatcherName) ===\" -ForegroundColor Cyan
Write-Host \"Processing ALL companies (NUGZ, EMPIRE, PUFFIN, JGD) for year $Year\" -ForegroundColor Yellow
Write-Host \"Log: $logPath\" -ForegroundColor Gray
Write-Host \"Instance: $instanceId\" -ForegroundColor Gray
Write-Host \"Config: config/global.yaml (layered with instance config)\" -ForegroundColor Gray
Write-Host \"Active Years: $Year\" -ForegroundColor Gray
Write-Host \"Press Ctrl+C to stop this watcher.\" -ForegroundColor Yellow
Write-Host \"\" -ForegroundColor Gray
 & '$PythonExe' -u -m bin.watch_all --years $Year --instance-id $instanceId 2>&1 | Tee-Object -FilePath '$logPath' -Append
"@

    $p = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-NoExit",
        "-Command",
        $cmd
    ) -PassThru

    return @{
        year = $Year
        instance_id = $instanceId
        watcher_name = $WatcherName
        pid = $p.Id
        log = $logPath
        started_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    }
}

function Start-SyncRunner {
    param(
        [Parameter(Mandatory=$true)][string]$IntervalSecs
    )

    $logPath = ".\.kylo\sync\sync_runner.log"

    $cmd = @"
Set-Location '$RepoRoot'
`$env:KYLO_CONFIG_PATH = 'config/global.yaml'
`$env:KYLO_SYNC_INTERVAL_SECS = '$IntervalSecs'
`$env:PYTHONUNBUFFERED = '1'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent '$logPath') | Out-Null
Write-Host "=== Kylo Sync Runner (every $IntervalSecs s) ===" -ForegroundColor Cyan
Write-Host "Log: $logPath" -ForegroundColor Gray
& '$PythonExe' -u .\tools\scripthub_legacy\sync_runner.py
"@

    $p = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-Command",
        $cmd
    ) -PassThru

    return @{
        pid = $p.Id
        log = $logPath
        started_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    }
}

Write-Host "Starting Kylo watchers in separate windows..." -ForegroundColor Cyan
Write-Host "Processing ALL companies (NUGZ, EMPIRE, PUFFIN, JGD) with year-based routing" -ForegroundColor Yellow
Write-Host ""

$w25 = Start-WatcherWindow -Year "2025" -WatcherName "watcher_2025"
Start-Sleep -Milliseconds 300
$w26 = Start-WatcherWindow -Year "2026" -WatcherName "watcher_2026"
Start-Sleep -Milliseconds 300

$syncRunner = $null
$syncPath = "$RepoRoot\tools\scripthub_legacy\sync_runner.py"
if (Test-Path $syncPath) {
    $syncRunner = Start-SyncRunner -IntervalSecs $IntervalSecs
} else {
    Write-Host "Skipping sync runner (sync_runner.py not found)" -ForegroundColor DarkGray
}

# Merge with existing startup file if present
$jobsFile = ".\.kylo\startup\background_jobs.json"
$existing = @{}
if (Test-Path $jobsFile) {
    try { $existing = Get-Content $jobsFile | ConvertFrom-Json } catch { $existing = @{} }
}

$payload = @{}
foreach ($p in @($existing.PSObject.Properties.Name)) { $payload[$p] = $existing.$p }
$payload["watcher_2025_pid"] = $w25.pid
$payload["watcher_2026_pid"] = $w26.pid
$payload["watcher_2025_log"] = $w25.log
$payload["watcher_2026_log"] = $w26.log
$payload["watcher_2025_instance_id"] = $w25.instance_id
$payload["watcher_2026_instance_id"] = $w26.instance_id
if ($syncRunner) {
    $payload["sync_runner_pid"] = $syncRunner.pid
    $payload["sync_runner_log"] = $syncRunner.log
}
$payload["watcher_started_at"] = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$payload | ConvertTo-Json | Out-File -FilePath $jobsFile -Encoding UTF8

Write-Host "Started watcher 2025 PID=$($w25.pid) log=$($w25.log)" -ForegroundColor Green
Write-Host "Started watcher 2026 PID=$($w26.pid) log=$($w26.log)" -ForegroundColor Green
if ($syncRunner) {
    Write-Host "Started sync runner PID=$($syncRunner.pid) log=$($syncRunner.log)" -ForegroundColor Green
}
Write-Host "Saved watcher PIDs to $jobsFile" -ForegroundColor Gray

