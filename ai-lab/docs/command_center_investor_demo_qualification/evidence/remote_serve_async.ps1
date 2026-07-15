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
    if ($cl -and ($cl -match 'uvicorn|worker_assistant|uv_selector|boot_uvicorn|http.server|bindtest|serve_fix')) {
      Stop-Process -Id $_.Id -Force -EA SilentlyContinue
    }
  } catch {}
}
Start-Sleep 2

$serve = @'
import asyncio
import sys

async def _serve():
    print("async_main", flush=True)
    import uvicorn
    config = uvicorn.Config(
        "worker_assistant.app.main:app",
        host="0.0.0.0",
        port=8765,
        log_level="info",
        loop="asyncio",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    print("await serve", flush=True)
    await server.serve()
    print("serve returned", flush=True)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(_serve())
'@
Set-Content "$logDir\serve_fix.py" $serve -Encoding ascii
Remove-Item "$logDir\serve.out","$logDir\serve.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\serve_fix.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\serve.out" -RedirectStandardError "$logDir\serve.err"
Start-Sleep 12
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$lines += "OUT=$(Get-Content $logDir\serve.out -Raw -EA SilentlyContinue)"
$lines += "ERR=$(Get-Content $logDir\serve.err -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -EA SilentlyContinue
foreach ($t in @($tcp)) { $lines += "tcp $($t.State) $($t.LocalAddress) pid=$($t.OwningProcess)" }
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 3
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }

# Fallback: starlette/fastapi TestClient style not useful; try port 18865
$lines -join "`r`n" | Set-Content "$logDir\serve_report.txt"
Get-Content "$logDir\serve_report.txt"
