<#
.SYNOPSIS
  Start SSH tunnel for Syncthing to reach old rig (WORKER-NODE).
.DESCRIPTION
  Forwards local port 22001 to old rig's Syncthing (127.0.0.1:22000).
  In Syncthing on this machine, add the old rig with address: tcp://127.0.0.1:22001
#>
param(
    [string]$OldRigHost = "192.168.40.25",
    [string]$SshUser = "worker",
    [int]$LocalPort = 22001,
    [int]$RemotePort = 22000
)

$ErrorActionPreference = "Stop"
Write-Host "Syncthing SSH tunnel: localhost:$LocalPort -> $SshUser@${OldRigHost}:$RemotePort"
Write-Host "Add old rig in Syncthing with address: tcp://127.0.0.1:$LocalPort"
Write-Host "Press Ctrl+C to stop."
ssh -L "${LocalPort}:127.0.0.1:${RemotePort}" "${SshUser}@${OldRigHost}" -N
