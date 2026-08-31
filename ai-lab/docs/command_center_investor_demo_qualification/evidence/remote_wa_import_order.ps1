$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Remove-Item "$logDir\trace.txt" -Force -EA SilentlyContinue

$serve = @'
def log(msg):
    with open(r"C:\worker\logs\worker_assistant\trace.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n"); f.flush()

log("wa_boot")
from worker_assistant.app.main import app
log("app_loaded " + str(app.title))
import asyncio
log("asyncio_ok")
import uvicorn
log("uvicorn_ok")

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
Start-Sleep 20
$out = @("pid=$($p.Id) exited=$($p.HasExited)")
$out += "TRACE=$(Get-Content $logDir\trace.txt -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$out += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $out += "health=$($h.StatusCode) $($h.Content)"
} catch { $out += "health_err=$($_.Exception.Message)" }
$out -join "`r`n" | Set-Content "$logDir\order_report.txt"
Get-Content "$logDir\order_report.txt"
