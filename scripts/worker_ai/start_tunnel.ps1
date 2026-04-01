<#
.SYNOPSIS
  Starts the SSH tunnel to worker-node so the main rig can reach worker_assistant on port 8765.
.DESCRIPTION
  Runs ssh -L 8765:localhost:8765 worker@worker-node -N in the background. Optionally use -Install
  to register a scheduled task that starts the tunnel at user logon (auto-reconnect after reboot).
.PARAMETER SshTarget
  SSH target (user@host). Default: worker@worker-node.
.PARAMETER LocalPort
  Local port to forward. Default: 8765.
.PARAMETER Install
  Register a scheduled task to run this script at user logon so the tunnel auto-starts after reboot.
.EXAMPLE
  .\start_tunnel.ps1
.EXAMPLE
  .\start_tunnel.ps1 -Install
.EXAMPLE
  .\start_tunnel.ps1 -SshTarget "worker@worker-node" -LocalPort 8765
#>
param(
    [string] $SshTarget = 'worker@192.168.40.25',
    [int]    $LocalPort = 8765,
    [switch] $Install
)

$ErrorActionPreference = 'Stop'
$sshExe = 'ssh'
$taskName = 'WorkerAssistantTunnel'
$scriptDir = $PSScriptRoot

function Start-Tunnel {
    $args = @(
        '-L', "${LocalPort}:localhost:${LocalPort}",
        '-o', 'ServerAliveInterval=60',
        '-o', 'ServerAliveCountMax=3',
        $SshTarget,
        '-N'
    )
    Write-Host "Starting SSH tunnel: $sshExe $($args -join ' ')" -ForegroundColor Cyan
    Start-Process -FilePath $sshExe -ArgumentList $args -WindowStyle Hidden
    Write-Host "Tunnel started. Port $LocalPort forwards to $SshTarget. Use `$env:WORKER_ASSISTANT_URL = 'http://127.0.0.1:$LocalPort' if needed." -ForegroundColor Green
}

function Register-TunnelAtLogon {
    $scriptPath = Join-Path $scriptDir 'start_tunnel.ps1'
    if (-not (Test-Path $scriptPath)) {
        Write-Error "Script not found: $scriptPath"
    }
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "Registered scheduled task '$taskName' to run at logon. Tunnel will auto-start after reboot." -ForegroundColor Green
    Write-Host "To remove: Unregister-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
}

if ($Install) {
    Register-TunnelAtLogon
} else {
    Start-Tunnel
}
