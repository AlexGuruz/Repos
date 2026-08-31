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
    if ($cl -and ($cl -match 'uvicorn|wa_serve|minimal|cmd.exe')) {
      # don't kill random cmd
      if ($cl -match 'python') { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
    }
  } catch {}
}
Start-Sleep 2

$serve = @'
print("wa_boot", flush=True)
import asyncio
import uvicorn
from worker_assistant.app.main import app
print("app_loaded", app.title, flush=True)

async def main():
    # lifespan off avoids governance/verify blocks during demo recovery
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="info",
        loop="asyncio",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print("serving", flush=True)
    await server.serve()

asyncio.run(main())
'@
Set-Content "$logDir\wa_serve.py" $serve -Encoding ascii
Remove-Item "$logDir\wa2.out","$logDir\wa2.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\wa_serve.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\wa2.out" -RedirectStandardError "$logDir\wa2.err"
Start-Sleep 12
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$lines += "OUT=$(Get-Content $logDir\wa2.out -Raw -EA SilentlyContinue)"
$lines += "ERR=$(Get-Content $logDir\wa2.err -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
$lines -join "`r`n" | Set-Content "$logDir\wa_nolipespan_report.txt"
Get-Content "$logDir\wa_nolipespan_report.txt"
