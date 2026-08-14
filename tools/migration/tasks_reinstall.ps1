<#
.SYNOPSIS
  Reinstall Growflow / ai-lab scheduled tasks after layout migration.
  Sets REPOS_ROOT and product env vars, then invokes known installers if present.
#>
param(
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$env:REPOS_ROOT = $root
$env:AI_LAB_REPOS_ROOT = $root

try { $env:AI_LAB_ROOT = Get-ProductPath -Id 'ai-lab' } catch { }
try { $env:AI_LAB_GOVERNANCE_ROOT = Get-ProductPath -Id 'ai-lab-governance' } catch { }
try {
    $vaultNew = Join-Path $root 'internal\obsidian-brain\Obsidian\Brain'
    $vaultOld = Join-Path $root 'Ai\Obsidian\Brain'
    if (Test-Path $vaultNew) { $env:OPERATOR_BRAIN_VAULT_ROOT = $vaultNew }
    elseif (Test-Path $vaultOld) { $env:OPERATOR_BRAIN_VAULT_ROOT = $vaultOld }
} catch { }

$installers = @()
try {
    $gf = Get-ProductPath -Id 'growflow'
    $installers += (Join-Path $gf 'scripts\reinstall_growflow_scheduled_tasks.ps1')
} catch { }
try {
    $lab = Get-ProductPath -Id 'ai-lab'
    $installers += (Join-Path $lab 'scripts\setup_prepared_context_tasks.ps1')
} catch { }

Write-MigLog "REPOS_ROOT=$root Apply=$Apply"
foreach ($i in $installers) {
    if (-not (Test-Path -LiteralPath $i)) {
        Write-MigLog "Installer missing: $i" 'WARN'
        continue
    }
    Write-MigLog "$(if ($Apply) {'RUN'} else {'DRY'}) $i"
    if ($Apply) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $i
    }
}

Write-MigLog "Also re-apply Kylo auto-start on power-1 via existing _power1_* scripts after junction."
if (-not $Apply) { Write-MigLog "Dry-run only." 'WARN' }
