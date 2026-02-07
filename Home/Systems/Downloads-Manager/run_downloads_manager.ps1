# Downloads-Manager - watch Downloads folder and organize files
# Dry run (scan once, log only): .\run_downloads_manager.ps1 -DryRun
# Run once (scan and move):      .\run_downloads_manager.ps1 -RunOnce
# Watch continuously:           .\run_downloads_manager.ps1

param(
    [switch]$DryRun,
    [switch]$RunOnce
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$scriptArgs = @("scripts/organize_downloads.py")
if ($DryRun) { $scriptArgs += "--dry-run" }
if ($RunOnce) { $scriptArgs += "--run-once" }

& $python @scriptArgs
