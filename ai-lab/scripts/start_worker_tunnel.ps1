# Start SSH tunnel from main rig to worker so 127.0.0.1:8765,5678,11434 forward to the worker.
# Run this on the MAIN RIG and leave the window open. Replace USER and WORKER_HOST with your SSH target.
# Example: .\start_worker_tunnel.ps1 -User worker -Host worker-rig.local
# Then run: python scripts/check_worker_connectivity.py

param(
    [string]$User = "zacle",
    [string]$WorkerHost = "worker-node"
)

Write-Host "Starting tunnel: ssh -N -L 8765:127.0.0.1:8765 -L 5678:127.0.0.1:5678 -L 11434:127.0.0.1:11434 ${User}@${WorkerHost}"
Write-Host "Leave this window open. On another terminal run: python scripts/check_worker_connectivity.py"
& ssh -N -L 8765:127.0.0.1:8765 -L 5678:127.0.0.1:5678 -L 11434:127.0.0.1:11434 "${User}@${WorkerHost}"
