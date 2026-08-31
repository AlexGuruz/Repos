# Sync secrets/gmail from Acheron to worker-node after local OAuth.
# Run on Acheron after: .\scripts\setup_company_gmail_oauth.ps1 -AuthAll
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\sync_gmail_secrets_to_worker.ps1
#
param(
    [string]$AiLabRoot = "",
    [string]$Remote = "worker@worker-node",
    [string]$RemoteAiLab = "C:/Users/worker/ai-lab",
    [switch]$IncludeTokens
)

$ErrorActionPreference = "Stop"
if (-not $AiLabRoot) { $AiLabRoot = Split-Path -Parent $PSScriptRoot }
$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path
$localSecrets = Join-Path $AiLabRoot "secrets\gmail"
$creds = Join-Path $localSecrets "credentials.json"
if (-not (Test-Path -LiteralPath $creds)) {
    throw "Missing $creds - run setup_company_gmail_oauth.ps1 first."
}

$remoteSecrets = "$RemoteAiLab/secrets/gmail"
$mkdirPs = "New-Item -ItemType Directory -Force -Path (('${RemoteAiLab}' -replace '/','\') + '\secrets\gmail\tokens') | Out-Null; 'ok'"
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($mkdirPs))
ssh $Remote "powershell -NoProfile -EncodedCommand $b64" | Out-Null

Write-Host "Copying credentials.json..." -ForegroundColor Cyan
scp $creds "${Remote}:${remoteSecrets}/credentials.json"
if ($LASTEXITCODE -ne 0) { throw "scp credentials failed" }

if ($IncludeTokens) {
    $tokenDir = Join-Path $localSecrets "tokens"
    if (-not (Test-Path -LiteralPath $tokenDir)) {
        throw "No tokens dir at $tokenDir - run --auth for each account first."
    }
    Write-Host "Copying token files..." -ForegroundColor Cyan
    scp (Join-Path $tokenDir "*.json") "${Remote}:${remoteSecrets}/tokens/"
    if ($LASTEXITCODE -ne 0) { throw "scp tokens failed" }
} else {
    Write-Host "Skipped tokens (pass -IncludeTokens after AuthAll)." -ForegroundColor Yellow
}

Write-Host "Verify on worker:" -ForegroundColor Green
Write-Host "  ssh $Remote `"python -m email_sorter.accounts --auth-check`""
Write-Host "  (run from $RemoteAiLab)"
