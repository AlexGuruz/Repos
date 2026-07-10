#Requires -Version 5.1
<#
.SYNOPSIS
  Wrapper for github_repo_sync.py (dry-run or apply).

.PARAMETER Apply
  If set, runs fetch + pull --rebase + push with --apply. Without it, dry-run (still fetches when --fetch is used).

.EXAMPLE
  .\Run-GitHubRepoSync.ps1              # plan only (fetch + show what pull/push would do)
  .\Run-GitHubRepoSync.ps1 -Apply       # actually sync clean repos

  Task Scheduler: Action = powershell.exe
  Arguments = -NoProfile -ExecutionPolicy Bypass -File "E:\Repos\ai-lab\scripts\Run-GitHubRepoSync.ps1" -Apply
#>
param(
    [switch] $Apply
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "python not on PATH"
}
$args = @(
    "scripts/github_repo_sync.py",
    "--fetch",
    "--pull",
    "--push"
)
if ($Apply) {
    $args += "--apply"
}
& $python.Source @args
exit $LASTEXITCODE
