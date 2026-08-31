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
    if ($cl -and ($cl -match 'wa_serve|uvicorn|minimal')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2
Remove-Item "$logDir\trace.txt" -Force -EA SilentlyContinue

$serve = @'
def log(msg):
    with open(r"C:\worker\logs\worker_assistant\trace.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()

log("wa_boot")
import asyncio
log("asyncio_ok")
import uvicorn
log("uvicorn_ok")
from worker_assistant.app.main import app
log("app_loaded " + str(getattr(app, "title", "?")))

async def main():
    log("main_enter")
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info", loop="asyncio", lifespan="off")
    log("config_ok")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    log("serving")
    await server.serve()
    log("serve_done")

log("asyncio_run")
asyncio.run(main())
log("exit")
'@
Set-Content "$logDir\wa_serve.py" $serve -Encoding ascii
$p = Start-Process -FilePath $py -ArgumentList @("-u", "$logDir\wa_serve.py") -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
Start-Sleep 15
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$lines += "TRACE=$(Get-Content $logDir\trace.txt -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
$lines -join "`r`n" | Set-Content "$logDir\trace_report.txt"
Get-Content "$logDir\trace_report.txt"
