$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot

Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $_.Id)).CommandLine
    if ($cl -and ($cl -match 'uvicorn|minimal|nosig|serve_fix|wa_serve')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2

$serve = @'
import asyncio, sys
print("wa_boot", flush=True)

async def main():
    import uvicorn
    from worker_assistant.app.main import app
    print("app_loaded", getattr(app, "title", "?"), flush=True)
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print("serving", flush=True)
    await server.serve()

asyncio.run(main())
'@
Set-Content "$logDir\wa_serve.py" $serve -Encoding ascii
# Persist a durable starter for scheduled use
$starter = @'
$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $_.Id)).CommandLine
    if ($cl -and ($cl -match 'uvicorn|wa_serve')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 1
Start-Process -FilePath $py -ArgumentList (Join-Path $logDir "wa_serve.py") -WorkingDirectory $RepoRoot -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir "api.log") -RedirectStandardError (Join-Path $logDir "api.log.err")
Start-Sleep 6
try { Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 5 | ConvertTo-Json -Compress } catch { $_.Exception.Message }
'@
Set-Content "$logDir\start_wa_asyncio.ps1" $starter -Encoding ascii

Remove-Item "$logDir\wa.out","$logDir\wa.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\wa_serve.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\wa.out" -RedirectStandardError "$logDir\wa.err"
Start-Sleep 10
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$lines += "OUT=$(Get-Content $logDir\wa.out -Raw -EA SilentlyContinue)"
$lines += "ERR=$(Get-Content $logDir\wa.err -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
try {
  $r = Invoke-RestMethod http://127.0.0.1:8765/repo_status -TimeoutSec 5
  $lines += "repo_status=$($r | ConvertTo-Json -Compress)"
} catch { $lines += "repo_status_err=$($_.Exception.Message)" }
$lines -join "`r`n" | Set-Content "$logDir\wa_serve_report.txt"
Get-Content "$logDir\wa_serve_report.txt"
