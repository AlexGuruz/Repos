<#
.SYNOPSIS
  Drift scan: checks worker-assistant /health and /retrieve from the main rig.
.DESCRIPTION
  Run on the main rig with the SSH tunnel up. Pass -BaseUrl or set $env:WORKER_ASSISTANT_URL.
.PARAMETER BaseUrl
  Base URL of the worker assistant (e.g. http://127.0.0.1:8765 when using tunnel).
.EXAMPLE
  .\scripts\worker_ai\drift_scan.ps1 -BaseUrl "http://127.0.0.1:8765"
#>
param(
    [string] $BaseUrl = $(if ($env:WORKER_ASSISTANT_URL) { $env:WORKER_ASSISTANT_URL.TrimEnd('/') } else { 'http://127.0.0.1:8765' })
)

$ErrorActionPreference = 'Stop'
$baseUrl = $BaseUrl.TrimEnd('/')
$healthUrl = "$baseUrl/health"
$retrieveUrl = "$baseUrl/retrieve"

function Write-FailureReminder {
    Write-Host ""
    Write-Host "Drift scan failed. Ensure the tunnel is running from ACHERON (main rig):" -ForegroundColor Yellow
    Write-Host "  ssh -L 8765:127.0.0.1:8765 worker@192.168.40.25 -N" -ForegroundColor Cyan
    Write-Host "Or: & 'E:\Repos\Project-Kylo\scripts\worker_ai\start_tunnel.ps1'" -ForegroundColor Gray
    Write-Host "Then run: & '$(Join-Path (Split-Path -Parent $PSCommandPath) 'drift_scan.ps1')' -BaseUrl 'http://127.0.0.1:8765'" -ForegroundColor Gray
    Write-Host "If you get 404 for /repo_status or /health, restart worker_assistant on the worker (latest code)." -ForegroundColor Gray
}

try {
    $healthResponse = Invoke-WebRequest -Uri $healthUrl -Method Get -UseBasicParsing -TimeoutSec 10
    if ($healthResponse.StatusCode -ne 200) {
        Write-Host "GET /health returned $($healthResponse.StatusCode), expected 200." -ForegroundColor Red
        Write-FailureReminder
        exit 1
    }
    Write-Host "GET /health OK (200)" -ForegroundColor Green

    $body = @{ query = 'drift scan check'; top_k = 2 } | ConvertTo-Json
    $retrieveResponse = Invoke-WebRequest -Uri $retrieveUrl -Method Post -Body $body -ContentType 'application/json' -UseBasicParsing -TimeoutSec 15
    if ($retrieveResponse.StatusCode -ne 200) {
        Write-Host "POST /retrieve returned $($retrieveResponse.StatusCode), expected 200." -ForegroundColor Red
        Write-FailureReminder
        exit 1
    }
    Write-Host "POST /retrieve OK (200)" -ForegroundColor Green

    Write-Host "Drift scan passed." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-FailureReminder
    exit 1
}
