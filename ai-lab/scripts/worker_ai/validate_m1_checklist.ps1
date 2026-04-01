<#
.SYNOPSIS
    Validates that the main rig can reach Ollama on the worker (e.g. M1/second PC).

.DESCRIPTION
    From the main rig, run this to confirm connectivity to Ollama on the worker.
    Ollama listens on port 11434 by default. The script checks TCP and optionally
    calls the Ollama API (e.g. /api/version or /api/tags).

.PARAMETER WorkerIP
    LAN IP address (or hostname) of the worker PC where Ollama is running.

.PARAMETER OllamaPort
    Port Ollama listens on (default 11434).

.EXAMPLE
    .\scripts\worker_ai\validate_m1_checklist.ps1 -WorkerIP 192.168.1.100
    .\scripts\worker_ai\validate_m1_checklist.ps1 -WorkerIP 192.168.1.100 -OllamaPort 11434
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $WorkerIP,

    [Parameter(Mandatory = $false)]
    [int] $OllamaPort = 11434
)

$ErrorActionPreference = "Stop"
$baseUrl = "http://${WorkerIP}:${OllamaPort}"

Write-Host "Validate main rig -> Ollama on worker" -ForegroundColor Cyan
Write-Host "  Worker: $WorkerIP`:$OllamaPort" -ForegroundColor Gray
Write-Host ""

# 1. TCP connectivity
Write-Host "[1] TCP port $OllamaPort..." -NoNewline
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.ConnectAsync($WorkerIP, $OllamaPort).Wait(3000) | Out-Null
    if ($tcp.Connected) {
        Write-Host " OK" -ForegroundColor Green
        $tcp.Close()
    } else {
        Write-Host " FAIL (not connected)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host " FAIL ($_)" -ForegroundColor Red
    exit 1
}

# 2. Ollama API (version or tags)
Write-Host "[2] Ollama API $baseUrl..." -NoNewline
try {
    $versionUrl = "$baseUrl/api/version"
    $response = Invoke-RestMethod -Uri $versionUrl -Method Get -TimeoutSec 5
    if ($response.version) {
        Write-Host " OK (Ollama $($response.version))" -ForegroundColor Green
    } else {
        Write-Host " OK (API responded)" -ForegroundColor Green
    }
} catch {
    Write-Host " FAIL ($_)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Main rig can reach Ollama on worker." -ForegroundColor Green
