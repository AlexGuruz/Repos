# Run Drive Watcher - checks Google Drive for new sales CSVs
# Folder: https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

# Run once
& $python scripts/drive_watcher.py --run-once

# To run continuously (every 5 min): remove --run-once
# & $python scripts/drive_watcher.py
