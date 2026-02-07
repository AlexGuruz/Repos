# Wrapper script to run ScriptHub sync scripts from Kylo
# Resolves Python from Kylo venv if present, falls back to system Python

param(
    [string]$Script = "run_both_syncs.py"
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Join-Path $ScriptDir "scripts"

# Try to find Python from Kylo venv first
$KyloRoot = $env:KYLO_ROOT
if (-not $KyloRoot) {
    # Resolve Kylo root by going up from tools/scripthub/do_not_delete
    $KyloRoot = (Get-Item $ScriptDir).Parent.Parent.Parent.FullName
}

$VenvPython = Join-Path $KyloRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Host "Using Kylo venv Python: $PythonExe"
} else {
    # Fallback to system Python
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Error "Python not found. Please install Python or set up Kylo venv."
        exit 1
    }
    Write-Host "Using system Python: $PythonExe"
}

# Set PYTHONPATH to include parent directory for src imports
$env:PYTHONPATH = $ScriptDir

# Change to scripts directory
Set-Location $ScriptsDir

# Run the requested script
$ScriptPath = Join-Path $ScriptsDir $Script
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

Write-Host "Running: $ScriptPath"
& $PythonExe $ScriptPath @args

exit $LASTEXITCODE
