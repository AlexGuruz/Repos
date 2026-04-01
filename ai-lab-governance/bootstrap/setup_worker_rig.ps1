# Setup worker rig (Windows): same as main but for worker machine
# Usage: .\setup_worker_rig.ps1 [-GovernanceRoot "E:\AI\ai-lab-governance"]

param(
    [string]$GovernanceRoot = $env:AI_LAB_GOVERNANCE_ROOT
)

if (-not $GovernanceRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $GovernanceRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

$env:AI_LAB_MACHINE = "worker"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "setup_main_rig.ps1") -GovernanceRoot $GovernanceRoot

Write-Host "Worker rig: AI_LAB_MACHINE=worker"
