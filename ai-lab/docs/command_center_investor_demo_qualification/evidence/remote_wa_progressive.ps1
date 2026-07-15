$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot

# Aggressive cleanup of python processes for worker_ai only
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  if ($_.CommandLine -and ($_.CommandLine -match 'worker_ai|uvicorn|wa_serve|minimal_asgi|nosig|bindtest|serve_fix|import_step')) {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
Start-Sleep 3

$serve = @'
print("p0", flush=True)
import asyncio
print("p1 asyncio", flush=True)
import uvicorn
print("p2 uvicorn", uvicorn.__version__, flush=True)
from worker_assistant.app.main import app
print("p3 app", app.title, flush=True)

async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info", loop="asyncio", lifespan="off")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print("p4 serve", flush=True)
    await server.serve()

asyncio.run(main())
'@
Set-Content "$logDir\wa_serve.py" $serve -Encoding ascii
Remove-Item "$logDir\p.out","$logDir\p.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "-u","$logDir\wa_serve.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\p.out" -RedirectStandardError "$logDir\p.err"
Start-Sleep 15
@(
  "pid=$($p.Id) exited=$($p.HasExited)"
  "OUT=$(Get-Content $logDir\p.out -Raw -EA SilentlyContinue)"
  "ERR=$(Get-Content $logDir\p.err -Raw -EA SilentlyContinue)"
  "listen=$((Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue | ForEach-Object OwningProcess) -join ',')"
) | Set-Content "$logDir\p_report.txt"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 4
  Add-Content "$logDir\p_report.txt" "health=$($h.StatusCode) $($h.Content)"
} catch { Add-Content "$logDir\p_report.txt" "health_err=$($_.Exception.Message)" }
Get-Content "$logDir\p_report.txt"
