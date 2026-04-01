# ai-lab · maintain_worker_tunnel.ps1
# Keeps the SSH tunnel from this "main rig" to the worker machine alive.
#
# Why this exists:
# - You don't want to keep a terminal open.
# - SSH tunnels can drop; this script auto-restarts them.
#
# Typical use:
#   .\maintain_worker_tunnel.ps1 -User zacle -WorkerHost worker-node
#
# For background/auto-start on boot:
#   .\setup_worker_tunnel_task.ps1 -User zacle -WorkerHost worker-node

param(
  [string]$User = "zacle",
  [string]$WorkerHost = "worker-node",
  [string]$TaskName = "AiLabWorkerTunnel",
  [int]$RetryDelaySeconds = 5,
  [int]$PortProbeTimeoutSeconds = 20,
  [switch]$KillExisting
)

$ErrorActionPreference = "Stop"

$LogDir = "E:\Repos\ai-lab\logs\worker_tunnel"
$null = New-Item -ItemType Directory -Path $LogDir -Force
$LogFile = Join-Path $LogDir ("tunnel_watch_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function _log([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $LogFile -Value ("[{0}] {1}" -f $ts, $msg)
  Write-Host ("{0} {1}" -f $ts, $msg)
}

function _kill_existing_ssh_on_ports {
  # Kill ssh.exe processes that look like they are forwarding our known ports.
  # This is intentionally conservative: it only kills ssh.exe whose command line contains all 3 forwards.
  $forwards = @("-L 8765:127.0.0.1:8765", "-L 5678:127.0.0.1:5678", "-L 11434:127.0.0.1:11434")
  $sshProcs = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" 2>$null
  foreach ($p in $sshProcs) {
    try {
      $cmd = $p.CommandLine
      if ($forwards | Where-Object { $cmd -like "*$_*" } | Measure-Object | Select-Object -ExpandProperty Count) {
        # Ensure all forwards exist in cmdline.
        $all = $true
        foreach ($f in $forwards) {
          if ($cmd -notlike ("*{0}*" -f $f)) { $all = $false }
        }
        if ($all) {
          _log ("Killing existing tunnel ssh.exe pid={0}" -f $p.ProcessId)
          Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
      }
    } catch {
      # ignore per-process parsing errors
    }
  }
}

function _ports_ok {
  $ports = @(8765, 5678, 11434)
  foreach ($pt in $ports) {
    try {
      $ok = Test-NetConnection -ComputerName "127.0.0.1" -Port $pt -InformationLevel Quiet -WarningAction SilentlyContinue
      if (-not $ok) { return $false }
    } catch {
      return $false
    }
  }
  return $true
}

while ($true) {
  try {
    if ($KillExisting) {
      _kill_existing_ssh_on_ports
    }

    if (_ports_ok) {
      _log "Tunnel ports already reachable; sleeping 30s"
      Start-Sleep -Seconds 30
      continue
    }

    _log ("Starting SSH tunnel to {0}@{1} ..." -f $User, $WorkerHost)

    $sshArgs = @(
      "-N",
      "-o", "ExitOnForwardFailure=yes",
      "-o", "ServerAliveInterval=30",
      "-o", "ServerAliveCountMax=3",
      "-L", "8765:127.0.0.1:8765",
      "-L", "5678:127.0.0.1:5678",
      "-L", "11434:127.0.0.1:11434",
      ("{0}@{1}" -f $User, $WorkerHost)
    )

    $proc = Start-Process -FilePath "ssh" -ArgumentList $sshArgs -WindowStyle Hidden -PassThru

    # Probe ports until ready or timeout
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $PortProbeTimeoutSeconds) {
      if (_ports_ok) {
        _log ("Tunnel is up (ssh pid={0}). Waiting for ssh to exit..." -f $proc.Id)
        break
      }
      Start-Sleep -Seconds 1
    }

    if (-not ( _ports_ok )) {
      _log ("Tunnel probe failed; stopping ssh pid={0} and retrying..." -f $proc.Id)
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds $RetryDelaySeconds
      continue
    }

    # Block until ssh exits, then loop/restart
    Wait-Process -Id $proc.Id
    _log ("ssh tunnel process exited (pid={0}); restarting in {1}s..." -f $proc.Id, $RetryDelaySeconds)
  } catch {
    _log ("Tunnel watcher error: {0}" -f $_.Exception.Message)
    Start-Sleep -Seconds $RetryDelaySeconds
  }
}

