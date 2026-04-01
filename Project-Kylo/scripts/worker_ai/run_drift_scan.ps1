<#
.SYNOPSIS
  One-shot: ensure tunnel to worker is up, then run drift scan (main rig only).
.DESCRIPTION
  On ACHERON (main rig): checks if worker_assistant is reachable at 127.0.0.1:8765.
  If not, starts the SSH tunnel in the background (using 127.0.0.1 on remote for IPv4), waits, then runs drift_scan.
  Tunnel is left running for reuse.
.PARAMETER SshTarget
  SSH target (user@host). Default: worker@192.168.40.25
.PARAMETER LocalPort
  Local port for tunnel and API. Default: 8765
.EXAMPLE
  .\run_drift_scan.ps1
#>
param(
    [string] $SshTarget = 'worker@192.168.40.25',
    [int]    $LocalPort = 8765
)

$ErrorActionPreference = 'Stop'
$scriptDir = $PSScriptRoot
$baseUrl = "http://127.0.0.1:$LocalPort"
$healthUrl = "$baseUrl/health"

function Test-TunnelUp {
    try {
        $r = Invoke-WebRequest -Uri $healthUrl -Method Get -UseBasicParsing -TimeoutSec 5
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Start-TunnelBackground {
    $sshExe = 'ssh'
    $args = @(
        '-L', "${LocalPort}:127.0.0.1:${LocalPort}",
        '-o', 'ServerAliveInterval=60',
        '-o', 'ServerAliveCountMax=3',
        $SshTarget,
        '-N'
    )
    Write-Host "Starting SSH tunnel (a window will open — enter password there if prompted): $sshExe $($args -join ' ')" -ForegroundColor Cyan
    Start-Process -FilePath $sshExe -ArgumentList $args -WindowStyle Normal
}

# --- Main ---
if (Test-TunnelUp) {
    Write-Host "Tunnel already up at $baseUrl" -ForegroundColor Green
} else {
    Start-TunnelBackground
    $maxWait = 15
    $waited = 0
    while (-not (Test-TunnelUp) -and $waited -lt $maxWait) {
        Start-Sleep -Seconds 2
        $waited += 2
    }
    if (-not (Test-TunnelUp)) {
        Write-Host "Tunnel did not become ready in ${maxWait}s. Enter password in the SSH window if it appeared, then run this script again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Tunnel is up." -ForegroundColor Green
}

& (Join-Path $scriptDir 'drift_scan.ps1') -BaseUrl $baseUrl
