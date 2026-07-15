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
    if ($cl -and ($cl -match 'wa_serve|uvicorn|minimal_asgi|nosig')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2

$serve = @'
print("wa_boot", flush=True)
import asyncio
print("asyncio_ok", flush=True)
import uvicorn
print("uvicorn_ok", flush=True)
from worker_assistant.app.main import app
print("app_loaded", app.title, flush=True)

async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info", loop="asyncio", lifespan="off")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print("serving", flush=True)
    await server.serve()

asyncio.run(main())
'@
$servePath = Join-Path $logDir "wa_serve.py"
Set-Content $servePath $serve -Encoding ascii

# no redirect - use python -u writing its own log via Tee inside python? Use Start-Process without redirect
$p = Start-Process -FilePath $py -ArgumentList @("-u", $servePath) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
"pid=$($p.Id)" | Set-Content "$logDir\noredirect_pid.txt"
Start-Sleep 15
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
# process cmdline
try {
  $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $p.Id)).CommandLine
  $lines += "cmd=$cl"
} catch {}
$lines -join "`r`n" | Set-Content "$logDir\noredirect_report.txt"
Get-Content "$logDir\noredirect_report.txt"
