# One-shot helper: prepare secrets/gmail layout and walk through interactive OAuth.
# Run on Acheron (interactive browser required for --auth).
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_company_gmail_oauth.ps1
#
param(
    [string]$AiLabRoot = "",
    [switch]$AuthAll,
    [switch]$AuthCheckOnly,
    [string]$SourceCredentials = ""
)

$ErrorActionPreference = "Stop"
if (-not $AiLabRoot) {
    $AiLabRoot = Split-Path -Parent $PSScriptRoot
}
$AiLabRoot = (Resolve-Path -LiteralPath $AiLabRoot).Path
Set-Location $AiLabRoot

$secretsDir = Join-Path $AiLabRoot "secrets\gmail"
$tokensDir = Join-Path $secretsDir "tokens"
$destCreds = Join-Path $secretsDir "credentials.json"
New-Item -ItemType Directory -Force -Path $tokensDir | Out-Null

Write-Host "=== Company Gmail OAuth setup ===" -ForegroundColor Cyan
Write-Host "AiLabRoot: $AiLabRoot"
Write-Host "Credentials target: $destCreds"
Write-Host ""

if (-not (Test-Path -LiteralPath $destCreds)) {
    $candidates = @()
    if ($SourceCredentials) { $candidates += $SourceCredentials }
    $candidates += @(
        (Join-Path $AiLabRoot "secrets\credentials.json"),
        (Join-Path $AiLabRoot "email_sorter\gmail_portable\credentials.json"),
        (Join-Path $AiLabRoot "Ai\Email-Inbox-Agent---Doo-Made\credentials.json")
    )
    $copied = $false
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) {
            Copy-Item -LiteralPath $c -Destination $destCreds -Force
            Write-Host "Copied OAuth client JSON from: $c" -ForegroundColor Green
            $copied = $true
            break
        }
    }
    if (-not $copied) {
        Write-Host @"
MISSING: $destCreds

Do this in Google Cloud Console (personal project):
  1) Enable Gmail API
  2) OAuth consent = External; add test users for the 3 company Gmails
  3) Scope: https://www.googleapis.com/auth/gmail.modify
  4) Create OAuth client = Desktop app; download JSON
  5) Save as: $destCreds

Then re-run this script with -AuthAll
"@ -ForegroundColor Yellow
        exit 2
    }
} else {
    Write-Host "credentials.json already present." -ForegroundColor Green
}

$py = Join-Path $AiLabRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { $py = "python" }

if ($AuthCheckOnly) {
    & $py -m email_sorter.accounts --auth-check
    exit $LASTEXITCODE
}

if ($AuthAll) {
    foreach ($id in @("jgdproperties", "jagadnursery", "nugzdispo")) {
        Write-Host ""
        Write-Host "=== Auth account: $id (browser will open) ===" -ForegroundColor Cyan
        Write-Host "Sign in as the matching Gmail for this id. Advanced → continue if unverified."
        & $py -m email_sorter.accounts --auth $id
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Auth failed for $id (exit $LASTEXITCODE)" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
}

Write-Host ""
Write-Host "=== Auth check ===" -ForegroundColor Cyan
& $py -m email_sorter.accounts --auth-check
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host "OK — all accounts have tokens. Next: dry-run then --apply on company_inbox_cleaner." -ForegroundColor Green
    Write-Host "  python -m email_sorter.company_inbox_cleaner --limit 10"
    Write-Host "  python -m email_sorter.company_inbox_cleaner --apply --toast --limit 10"
} else {
    Write-Host "Auth incomplete. Re-run with -AuthAll after placing credentials.json." -ForegroundColor Yellow
}
exit $code
