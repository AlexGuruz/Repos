# Script to stop all Kylo and ScriptHub services

Set-Location "D:\Project-Kylo"

Write-Host "=== Stopping All Services ===" -ForegroundColor Cyan

# Stop background jobs
$jobsFile = ".\.kylo\startup\background_jobs.json"
if (Test-Path $jobsFile) {
    $jobs = Get-Content $jobsFile | ConvertFrom-Json
    Write-Host "Stopping background jobs..." -ForegroundColor Yellow
    if ($jobs.kylo_watcher) {
        Stop-Job -Id $jobs.kylo_watcher -ErrorAction SilentlyContinue
        Remove-Job -Id $jobs.kylo_watcher -ErrorAction SilentlyContinue
        Write-Host "  Stopped Kylo watcher (Job ID: $($jobs.kylo_watcher))" -ForegroundColor Gray
    }
    if ($jobs.scriptHub_server) {
        Stop-Job -Id $jobs.scriptHub_server -ErrorAction SilentlyContinue
        Remove-Job -Id $jobs.scriptHub_server -ErrorAction SilentlyContinue
        Write-Host "  Stopped ScriptHub server (Job ID: $($jobs.scriptHub_server))" -ForegroundColor Gray
    }
    if ($jobs.sync_runner) {
        Stop-Job -Id $jobs.sync_runner -ErrorAction SilentlyContinue
        Remove-Job -Id $jobs.sync_runner -ErrorAction SilentlyContinue
        Write-Host "  Stopped sync runner job (Job ID: $($jobs.sync_runner))" -ForegroundColor Gray
    }
    if ($jobs.sync_runner_pid) {
        try {
            Stop-Process -Id ([int]$jobs.sync_runner_pid) -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped sync runner (PID: $($jobs.sync_runner_pid))" -ForegroundColor Gray
        } catch {
            # ignore
        }
    }

    # Stop watcher windows (PID-based), including any future watcher_*_pid keys.
    foreach ($prop in $jobs.PSObject.Properties) {
        try {
            if ($prop.Name -like "watcher_*_pid") {
                $pid = $prop.Value
                if ($pid -and [int]$pid -gt 0) {
                    Stop-Process -Id ([int]$pid) -Force -ErrorAction SilentlyContinue
                    Write-Host "  Stopped watcher window ($($prop.Name) PID: $pid)" -ForegroundColor Gray
                }
            }
        } catch {
            # ignore
        }
    }
}

# Stop all background jobs (catch-all)
$remainingJobs = Get-Job
if ($remainingJobs) {
    Write-Host "Stopping remaining background jobs..." -ForegroundColor Yellow
    $remainingJobs | Stop-Job -ErrorAction SilentlyContinue
    $remainingJobs | Remove-Job -ErrorAction SilentlyContinue
}

# Stop Docker containers
Write-Host "Stopping Docker containers..." -ForegroundColor Yellow
docker compose -f docker-compose.kafka-consumer.yml down 2>&1 | Out-Null
docker compose -f docker-compose.kafka.yml down 2>&1 | Out-Null
docker compose -f docker-compose.yml down 2>&1 | Out-Null
Write-Host "  Docker containers stopped" -ForegroundColor Gray

# Stop any Python processes related to ScriptHub server
Write-Host "Stopping ScriptHub server processes..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*python*" -and (
        (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*uvicorn*server*" -or
        (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*scripts.server*"
    )
}
if ($uvicornProcesses) {
    $uvicornProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Stopped $($uvicornProcesses.Count) uvicorn process(es)" -ForegroundColor Gray
} else {
    Write-Host "  No uvicorn processes found" -ForegroundColor Gray
}

Write-Host "`nAll services stopped!" -ForegroundColor Green

