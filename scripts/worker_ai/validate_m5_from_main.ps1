<#
.SYNOPSIS
  Validates M5 (worker-assistant reachable from main rig) by calling GET /health and POST /retrieve.
.DESCRIPTION
  Run on the main rig with the SSH tunnel up. Optionally set $env:WORKER_ASSISTANT_URL.
  Exits 0 if both endpoints succeed, non-zero otherwise; on failure reminds you to start the tunnel.
.EXAMPLE
  .\scripts\worker_ai\validate_m5_from_main.ps1
#>

$ErrorActionPreference = 'Stop'
$baseUrl = if ($env:WORKER_ASSISTANT_URL) { $env:WORKER_ASSISTANT_URL.TrimEnd('/') } else { 'http://127.0.0.1:8765' }
$healthUrl = "$baseUrl/health"
$retrieveUrl = "$baseUrl/retrieve"

function Write-FailureReminder {
    Write-Host ""
    Write-Host "M5 validation failed. Ensure the tunnel is running from ACHERON (main rig):" -ForegroundColor Yellow
    Write-Host "  ssh -L 8765:localhost:8765 worker@192.168.40.25 -N" -ForegroundColor Cyan
    Write-Host "Or: & 'E:\Repos\scripts\worker_ai\start_tunnel.ps1'" -ForegroundColor Gray
    Write-Host "Optionally: `$env:WORKER_ASSISTANT_URL = 'http://127.0.0.1:8765'" -ForegroundColor Gray
    Write-Host "Then run this script again: .\scripts\worker_ai\validate_m5_from_main.ps1" -ForegroundColor Gray
}

try {
    # GET /health
    $healthResponse = Invoke-WebRequest -Uri $healthUrl -Method Get -UseBasicParsing -TimeoutSec 10
    if ($healthResponse.StatusCode -ne 200) {
        Write-Host "GET /health returned $($healthResponse.StatusCode), expected 200." -ForegroundColor Red
        Write-FailureReminder
        exit 1
    }
    Write-Host "GET /health OK (200)" -ForegroundColor Green

    # POST /retrieve (fixed query, top_k: 2)
    $body = @{ query = 'M5 validation query'; top_k = 2 } | ConvertTo-Json
    $retrieveResponse = Invoke-WebRequest -Uri $retrieveUrl -Method Post -Body $body -ContentType 'application/json' -UseBasicParsing -TimeoutSec 15
    if ($retrieveResponse.StatusCode -ne 200) {
        Write-Host "POST /retrieve returned $($retrieveResponse.StatusCode), expected 200." -ForegroundColor Red
        Write-FailureReminder
        exit 1
    }
    Write-Host "POST /retrieve OK (200)" -ForegroundColor Green

    Write-Host "M5 validation passed." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-FailureReminder
    exit 1
}
