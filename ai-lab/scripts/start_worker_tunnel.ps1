# Start SSH tunnel from main rig to worker so 127.0.0.1:8765,5678,11434 forward to the worker.
# Run this on the MAIN RIG and leave the window open. Replace USER and WORKER_HOST with your SSH target.
# Example: .\start_worker_tunnel.ps1 -User worker -Host worker-rig.local
# Then run: python scripts/check_worker_connectivity.py

param(
    [string]$User = "zacle",
    [string]$WorkerHost = "worker-node"
)

$_wtcPath = Join-Path $PSScriptRoot "worker_tunnel.local.json"
if (Test-Path $_wtcPath) {
  try {
    $_wtc = Get-Content $_wtcPath -Raw | ConvertFrom-Json
    if ($_wtc.workerHost -and -not $PSBoundParameters.ContainsKey("WorkerHost")) { $WorkerHost = [string]$_wtc.workerHost }
    if ($_wtc.user -and -not $PSBoundParameters.ContainsKey("User")) { $User = [string]$_wtc.user }
  } catch {
    Write-Warning ("Ignoring invalid worker_tunnel.local.json: {0}" -f $_.Exception.Message)
  }
}

Write-Host "Starting tunnel: ssh -N -L 8765:127.0.0.1:8765 -L 5678:127.0.0.1:5678 -L 11434:127.0.0.1:11434 ${User}@${WorkerHost}"
Write-Host "Leave this window open. On another terminal run: python scripts/check_worker_connectivity.py"
& ssh -N -L 8765:127.0.0.1:8765 -L 5678:127.0.0.1:5678 -L 11434:127.0.0.1:11434 "${User}@${WorkerHost}"
