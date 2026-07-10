# ai-lab · setup_worker_tunnel_task.ps1
# Installs/updates a Windows Scheduled Task that runs maintain_worker_tunnel.ps1
# at startup so you never need to keep a terminal open.
#
# Requires:
# - Windows Task Scheduler permissions (Run as admin recommended)
# - SSH works non-interactively for the given user/host (no passphrase prompt)

param(
  [string]$User = "zacle",
  [string]$WorkerHost = "worker-node",
  [string]$TaskName = "AiLabWorkerTunnel",
  [switch]$KillExisting,
  [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"

$_wtcPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "worker_tunnel.local.json"
if (Test-Path $_wtcPath) {
  try {
    $_wtc = Get-Content $_wtcPath -Raw | ConvertFrom-Json
    if ($_wtc.workerHost -and -not $PSBoundParameters.ContainsKey("WorkerHost")) { $WorkerHost = [string]$_wtc.workerHost }
    if ($_wtc.user -and -not $PSBoundParameters.ContainsKey("User")) { $User = [string]$_wtc.user }
  } catch {
    Write-Warning ("Ignoring invalid worker_tunnel.local.json: {0}" -f $_.Exception.Message)
  }
}

function _log([string]$msg) {
  Write-Host ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg)
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WatchScript = Join-Path $ScriptDir "maintain_worker_tunnel.ps1"

if (-not (Test-Path $WatchScript)) {
  throw "Missing script: $WatchScript"
}

Import-Module ScheduledTasks -ErrorAction SilentlyContinue

# If worker_tunnel.local.json exists, do not pass -User/-WorkerHost on the task action so
# maintain_worker_tunnel.ps1 can apply that file (office IP / Tailscale name).
$argList = @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-WindowStyle", "Hidden",
  "-File", $WatchScript
)
if (Test-Path $_wtcPath) {
  _log "worker_tunnel.local.json present: scheduled task will rely on it for SSH user/host."
} else {
  $argList += @("-User", $User, "-WorkerHost", $WorkerHost)
}

if ($KillExisting) {
  $argList += "-KillExisting"
}

$actionArgs = ($argList | ForEach-Object { $_.ToString() }) -join " "

_log "Installing scheduled task '$TaskName' ..."

# If task exists, force update
try {
  $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
} catch {
  $existing = $null
}

$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = $null
if ($RunAsSystem) {
  # Use when your SSH keys are available to SYSTEM (rare).
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
} else {
  # Default: run under the current Windows user so the SSH key + known_hosts are available.
  $winUser = $env:USERNAME
  $winDomain = $env:USERDOMAIN
  if (-not $winUser) { throw "Could not determine current Windows username." }
  if ($winDomain) {
    $principal = New-ScheduledTaskPrincipal -UserId ("{0}\{1}" -f $winDomain, $winUser) -LogonType Interactive -RunLevel Highest
  } else {
    $principal = New-ScheduledTaskPrincipal -UserId $winUser -LogonType Interactive -RunLevel Highest
  }
}
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs

if ($existing) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

Write-Host "Scheduled task installed/updated: $TaskName"

# Start right now (best-effort). If SSH requires an interactive auth, the task will fail until fixed.
try {
  Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Out-Null
} catch {
  # ignore
}

