# Diagnose and repair AiLab email scheduled tasks on worker-node.
# Prefer CompanyInboxCleaner over legacy EmailSorter-BackfillApply.
#
# Run ON worker-node (or remotely via ssh + powershell -File):
#   powershell -ExecutionPolicy Bypass -File .\scripts\fix_worker_email_tasks.ps1
#
param(
    [string]$AiLabRoot = "C:\Users\worker\ai-lab",
    [string]$LegacyRoot = "C:\Repos\Repos\ai-lab",
    [string]$EnvFile = "C:\secrets\email_sorter_env.ps1",
    [int]$IntervalMinutes = 5,
    [switch]$DisableLegacy,
    [switch]$InstallCleaner,
    [switch]$DryRunCleanerDefault
)

$ErrorActionPreference = "Continue"
Write-Host "=== Worker email task repair ===" -ForegroundColor Cyan

foreach ($root in @($AiLabRoot, $LegacyRoot)) {
    Write-Host ("Root {0}: exists={1}" -f $root, (Test-Path -LiteralPath $root))
}

# Prefer synced worker tree if present; else legacy repos mirror.
$activeRoot = $null
if (Test-Path -LiteralPath (Join-Path $AiLabRoot "email_sorter\company_inbox_cleaner.py")) {
    $activeRoot = $AiLabRoot
} elseif (Test-Path -LiteralPath (Join-Path $LegacyRoot "email_sorter\company_inbox_cleaner.py")) {
    $activeRoot = $LegacyRoot
} elseif (Test-Path -LiteralPath $AiLabRoot) {
    $activeRoot = $AiLabRoot
} else {
    $activeRoot = $LegacyRoot
}
Write-Host "Active AiLabRoot: $activeRoot" -ForegroundColor Green

# Ensure secrets env scaffolding (no tokens written here).
$secretsDir = Split-Path -Parent $EnvFile
if (-not (Test-Path -LiteralPath $secretsDir)) {
    New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    $example = Join-Path $activeRoot "scripts\email_sorter_env.example.ps1"
    if (Test-Path -LiteralPath $example) {
        $content = Get-Content -LiteralPath $example -Raw
        # Point GOOGLE paths at active root
        $content = $content -replace 'E:\\Repos\\ai-lab', ($activeRoot -replace '\\', '\\')
        Set-Content -LiteralPath $EnvFile -Value $content -Encoding UTF8
        Write-Host "Created $EnvFile from example (edit tokens paths after OAuth)." -ForegroundColor Yellow
    } else {
        @"
`$env:GOOGLE_CREDENTIALS_FILE = "$activeRoot\secrets\gmail\credentials.json"
`$env:OLLAMA_HOST = "http://127.0.0.1:11434"
`$env:OLLAMA_MODEL = "llama3.1:8b"
`$env:ACHERON_SSH = "zacle@acheron"
`$env:ACHERON_TOAST_SCRIPT = "E:\Repos\ai-lab\scripts\show_email_toast.ps1"
"@ | Set-Content -LiteralPath $EnvFile -Encoding UTF8
        Write-Host "Created minimal $EnvFile" -ForegroundColor Yellow
    }
} else {
    Write-Host "Env file present: $EnvFile"
}

# Inspect legacy task last result
$legacyName = "AiLab-EmailSorter-BackfillApply"
try {
    $info = Get-ScheduledTaskInfo -TaskName $legacyName
    Write-Host ("Legacy {0}: LastResult={1} LastRun={2}" -f $legacyName, $info.LastTaskResult, $info.LastRunTime)
    if ($DisableLegacy) {
        Disable-ScheduledTask -TaskName $legacyName -ErrorAction SilentlyContinue | Out-Null
        Write-Host "Disabled $legacyName" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Legacy task not found ($legacyName)"
}

if ($InstallCleaner) {
    $installer = Join-Path $activeRoot "scripts\install_company_inbox_cleaner_schedule.ps1"
    if (-not (Test-Path -LiteralPath $installer)) {
        throw "Missing installer: $installer. Sync ai-lab to this machine first."
    }
    $psArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", $installer,
        "-AiLabRoot", $activeRoot,
        "-EnvFile", $EnvFile,
        "-IntervalMinutes", "$IntervalMinutes"
    )
    if ($DryRunCleanerDefault) {
        $psArgs += "-DryRunDefault"
    }
    & powershell @psArgs
}

Write-Host "Done. After OAuth tokens exist on this host, Start-ScheduledTask AiLab-CompanyInboxCleaner" -ForegroundColor Cyan
