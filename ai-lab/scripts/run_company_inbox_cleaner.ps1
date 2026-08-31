# Run company inbox cleaner (label + archive). Intended for Task Scheduler / worker-node.
param(
    [string]$AiLabRoot = "",
    [string]$EnvFile = "",
    [string]$PythonExe = "",
    [int]$Limit = 50,
    [switch]$DryRun,
    [switch]$NoToast,
    [switch]$NoLlm,
    [switch]$UnreadOnly
)

$ErrorActionPreference = "Stop"
if (-not $AiLabRoot) {
    $AiLabRoot = Split-Path -Parent $PSScriptRoot
}
$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path

if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
    . $EnvFile
}

if (-not $PythonExe) {
    $venvPy = Join-Path $AiLabRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) { $PythonExe = $venvPy } else { $PythonExe = "python" }
}

$logDir = Join-Path $AiLabRoot "logs\email_sorter"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "inbox_cleaner_scheduled_$stamp.log"

$argList = @("-m", "email_sorter.company_inbox_cleaner", "--limit", "$Limit")
if (-not $DryRun) { $argList += "--apply" }
if (-not $NoToast) { $argList += "--toast" }
if ($NoLlm) { $argList += "--no-llm" }
if ($UnreadOnly) { $argList += "--unread-only" }

Push-Location $AiLabRoot
try {
    & $PythonExe @argList *>> $logPath
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
