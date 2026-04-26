<#
.SYNOPSIS
  Run Ollama on the worker and save a demo text file under the worker user's profile.

.DESCRIPTION
  SSH -> worker runs PowerShell -> POST http://127.0.0.1:11434/api/generate -> writes
  %USERPROFILE%\ai-lab-demos\VISIBLE_OLLAMA_DEMO_<utc>.txt and prints path + contents.

.EXAMPLE
  .\scripts\worker_visible_ollama_demo.ps1
#>
param(
    [string] $WorkerUserHost = "worker@worker-node",
    [string] $Model = "qwen2.5-coder:7b"
)

$ErrorActionPreference = "Stop"

$remote = @'
$ProgressPreference = "SilentlyContinue"
$WarningPreference = "SilentlyContinue"
$model = "MODEL_PLACEHOLDER"
$d = Join-Path $env:USERPROFILE "ai-lab-demos"
New-Item -ItemType Directory -Force -Path $d | Out-Null
$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd_HHmmss")
$path = Join-Path $d ("VISIBLE_OLLAMA_DEMO_" + $stamp + ".txt")
$prompt = @"
You are on the worker node for an AI-Lab visibility demo.
Output plain text only:
Line 1 exactly: WORKER OLLAMA DEMO
Then one paragraph (4 sentences): a concrete plan to reduce password-reset and VPN-access tickets using automation; name one KPI with a percent target.
Then 5 lines starting with DASH- each listing a fake ticket id like INC-10023.
Last line exactly: END (model=$model host=$(hostname))
"@
$body = @{ model = $model; prompt = $prompt; stream = $false } | ConvertTo-Json -Compress
try {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 420
} catch {
  ("ERROR: " + $_.Exception.Message) | Set-Content -Path $path -Encoding UTF8
  Write-Output ("WROTE_ERROR_LOG: " + $path)
  Get-Content $path
  exit 1
}
$hdr = @(
  "=== AI-Lab visible worker demo ===",
  ("UTC: " + [DateTime]::UtcNow.ToString("o")),
  ("Machine: " + [Environment]::MachineName),
  ("Ollama model: " + $r.model),
  ""
)
($hdr + $r.response) | Set-Content -Path $path -Encoding UTF8
Write-Output ("WROTE: " + $path)
Get-Content $path
'@

if ($Model -match '["\r\n]') {
  throw "Model name must be a single-line token without quotes."
}
$remote = $remote.Replace("MODEL_PLACEHOLDER", $Model)

Write-Host "SSH -> $WorkerUserHost (worker-local Ollama)..." -ForegroundColor Cyan
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remote))
& ssh -o BatchMode=yes -o ConnectTimeout=20 $WorkerUserHost powershell.exe -NoProfile -EncodedCommand $b64
